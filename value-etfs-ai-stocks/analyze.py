"""What value ETFs hold, how they behaved in the autumn 2026 AI selloff, and
what their factor loadings say.

Supports https://summitward.com/learn/value-etfs-ai-stocks.

Requires numpy, pandas and yfinance.

Sources (holdings and Ken French CSVs committed in ./data/ by fetch_data.py;
Yahoo downloaded on first run and cached in ./.cache/, which is not committed):
  * Issuer holdings files: iShares (IWD, IWF, IVE, VLUE, SOXX) and Avantis
    (AVLV, AVUV, AVGV and its five other sleeves) and Dimensional (DFLV, DFSV)
    as of Nov 12, 2026; Vanguard (VTV, VTI) as of Sep 30, 2026, the latest
    month-end file Vanguard had posted.
  * Dimensional fund-center characteristics as of Oct 31, 2026.
  * Ken French data library, monthly, cut through September 2026 (202609
    CRSP): five factors (2x3), momentum, and the three-factor file from 1926.
  * Yahoo Finance via yfinance: daily adjusted closes (auto_adjust=True).

Sections:
  1. Holdings: number of stocks, GICS Information Technology and Communication
     Services weights, and the weights of selected companies, for each fund.
     AVGV is looked through to its six Avantis sleeves.
  2. Returns over the selloff: Oct 6, 2026 close (Nvidia's and the Russell
     1000 Growth ETF's closing high) to Nov 12, 2026 close, and year to date
     through Oct 30, 2026.
  3. Semiconductor sensitivity: weekly (Thursday-close) returns of each fund
     regressed on VTI and on SOXX minus VTI, Jun 29, 2023 (AVGV's first close
     in the Yahoo data) to Nov 12, 2026, with Newey-West (4 lag) standard
     errors. Repeated with the sample ending Oct 1, 2026, before the selloff.
     3b applies the full-sample coefficients to the selloff window; 3c
     regresses the difference between two funds' returns on the same factors.
  4. Fama-French five factors plus momentum, monthly excess returns over RF,
     Newey-West (6 lag): each fund's own history through Sep 2026, and the
     common window Jan 2023 to Sep 2026 (DFLV's first full month sets the start).
  5. HML record: annualized arithmetic mean (12 x monthly mean), share of
     positive months and compound annual return, Jul 1926 to Dec 2007, Jan 2008
     to Mar 2025, Jan 2008 to Sep 2026, and Jul 1926 to Sep 2026.
  6. AVUV against VTI, Oct 2019 to Oct 2026: CAGR, arithmetic mean, volatility.

Nothing here is a forecast. Every figure describes a named past window.
"""

from __future__ import annotations

import csv
import json
import math
import time
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
CACHE = HERE / ".cache"
OUT = HERE / "output"
for p in (CACHE, OUT):
    p.mkdir(exist_ok=True)

HOLDINGS_DATE = "2026-11-12"
EVENT_START, EVENT_END = "2026-10-06", "2026-11-12"
YTD_START, YTD_END = "2025-12-31", "2026-10-30"
WEEKLY_START, PRE_SELLOFF_END = "2023-06-29", "2026-10-01"
FACTOR_END, COMMON_START = "2026-09", "2023-01"
Z95 = 1.959964

VALUE_FUNDS = ["VTV", "IWD", "IVE", "VLUE", "AVLV", "DFLV", "AVUV", "DFSV", "AVGV"]
FUND_INFO = {
    "VTV": "Vanguard Morningstar Value ETF (Morningstar US Large Cap Value, formerly CRSP)",
    "IWD": "iShares Russell 1000 Value ETF",
    "IVE": "iShares S&P 500 Value ETF",
    "VLUE": "iShares MSCI USA Value Factor ETF (MSCI USA Enhanced Value)",
    "AVLV": "Avantis U.S. Large Cap Value ETF",
    "DFLV": "Dimensional US Large Cap Value ETF",
    "AVUV": "Avantis U.S. Small Cap Value ETF",
    "DFSV": "Dimensional US Small Cap Value (ETF share class)",
    "AVGV": "Avantis All Equity Markets Value ETF",
    "VTI": "Vanguard Morningstar Total Stock Market ETF",
    "IWF": "iShares Russell 1000 Growth ETF",
    "IWN": "iShares Russell 2000 Value ETF",
    "SOXX": "iShares Semiconductor ETF",
    "NVDA": "Nvidia",
}
# Selected companies: Zweig's named examples that are not omitted here, the
# largest names in the MSCI USA Value index, and other large AI-linked companies.
NAMES = {
    "MSFT": "Microsoft",
    "AAPL": "Apple",
    "META": "Meta",
    "NVDA": "Nvidia",
    "MU": "Micron",
    "SNDK": "Sandisk",
    "GOOGL": "Alphabet A",
    "GOOG": "Alphabet C",
    "AVGO": "Broadcom",
    "ORCL": "Oracle",
    "AMD": "AMD",
}
# GICS 2023 sub-industries in Information Technology and Communication Services,
# used to classify Vanguard's sub-industry labels.
IT_SUB = {
    "IT Consulting & Other Services",
    "Internet Services & Infrastructure",
    "Application Software",
    "Systems Software",
    "Communications Equipment",
    "Technology Hardware, Storage & Peripherals",
    "Electronic Equipment & Instruments",
    "Electronic Components",
    "Electronic Manufacturing Services",
    "Technology Distributors",
    "Semiconductor Materials & Equipment",
    "Semiconductors",
}
CS_SUB = {
    "Alternative Carriers",
    "Integrated Telecommunication Services",
    "Wireless Telecommunication Services",
    "Advertising",
    "Broadcasting",
    "Cable & Satellite",
    "Publishing",
    "Movies & Entertainment",
    "Interactive Home Entertainment",
    "Interactive Media & Services",
}
RESULTS: dict = {"holdings_date": HOLDINGS_DATE}


def norm_ticker(t: str) -> str:
    t = (t or "").upper().strip()
    if t.endswith(" US"):
        t = t[:-3]
    return t.replace("/", ".").replace(" ", ".")


def sector_bucket(s: str) -> str:
    s = (s or "").strip().upper()
    if s in ("INFORMATION TECHNOLOGY", "IT"):
        return "IT"
    if s == "COMMUNICATION SERVICES" or s == "COMMUNICATION":
        return "CS"
    return "OTHER"


def num(x: str) -> float:
    s = str(x).replace(",", "").replace("%", "").strip()
    return 0.0 if s in ("", "-", "null", "None") else float(s)


# ---------------------------------------------------------------- holdings
def read_ishares(ticker: str) -> pd.DataFrame:
    lines = (DATA / f"ishares_{ticker}.csv").read_text(encoding="utf-8").splitlines()
    head = next(i for i, ln in enumerate(lines) if ln.startswith("Ticker,"))
    body = []
    for ln in lines[head:]:
        if not ln.strip() or ln.startswith("\xa0"):
            break
        body.append(ln)
    rows = list(csv.DictReader(body))
    wcol = "Weight (%)" if "Weight (%)" in rows[0] else "Market Weight"
    df = pd.DataFrame(
        {
            "ticker": [norm_ticker(r["Ticker"]) for r in rows],
            "name": [r["Name"] for r in rows],
            "sector": [r["Sector"] for r in rows],
            "equity": [r["Asset Class"] == "Equity" for r in rows],
            "mv": [num(r["Market Value"]) for r in rows],
            "listed_weight": [num(r[wcol]) for r in rows],
        }
    )
    # Weights from market value: the listed weights are rounded to 0.01%, which
    # zeroes out the smallest positions.
    df["weight"] = 100 * df["mv"] / df["mv"].sum()
    return df


def read_avantis(ticker: str) -> pd.DataFrame:
    rows = list(csv.DictReader((DATA / f"avantis_{ticker}_{HOLDINGS_DATE}.csv").open()))
    return pd.DataFrame(
        {
            "ticker": [norm_ticker(r["ticker"]) for r in rows],
            "name": [r["name"] for r in rows],
            "sector": [r["sector"] for r in rows],
            "equity": [
                r["securityType"] in ("COMMON STOCK", "ORDINARY SHARES", "REIT")
                or "STOCK" in r["securityType"]
                or "DEPOSITARY" in r["securityType"]
                for r in rows
            ],
            "mv": [num(r["baseMarketValue"]) for r in rows],
            "listed_weight": [num(r["weight"]) for r in rows],
            "cusip": [r["cusip"] for r in rows],
        }
    ).pipe(lambda d: d.assign(weight=100 * d["mv"] / d["mv"].sum()))


def read_vanguard(ticker: str) -> pd.DataFrame:
    path = next(DATA.glob(f"vanguard_{ticker}_*.json"))
    payload = json.loads(path.read_text())
    as_of = payload["latestEffectiveDate"]
    eq = payload[as_of]["equity"]
    sub = [h["sector"] for h in eq]
    return pd.DataFrame(
        {
            "ticker": [norm_ticker(h["ticker"]) for h in eq],
            "name": [h["holdingName"] for h in eq],
            "sub": sub,
            "sector": [
                "INFORMATION TECHNOLOGY"
                if s in IT_SUB
                else "COMMUNICATION SERVICES"
                if s in CS_SUB
                else "OTHER"
                for s in sub
            ],
            "equity": True,
            "weight": [num(h["percentOfFunds"]) for h in eq],
            "cusip": [h["cusip"] for h in eq],
        }
    ).assign(as_of=as_of)


VTI_MAP = read_vanguard("VTI")
CUSIP_TICKER = dict(zip(VTI_MAP["cusip"], VTI_MAP["ticker"], strict=False))
CUSIP_SECTOR = dict(zip(VTI_MAP["cusip"], VTI_MAP["sector"], strict=False))


def read_dimensional(ticker: str) -> pd.DataFrame:
    date = HOLDINGS_DATE.replace("-", "")
    rows = list(csv.DictReader((DATA / f"dimensional_{ticker}_{date}.csv").open()))
    out = []
    for r in rows:
        cusip = r["identifier"]
        is_cash = "CASH" in r["description"].upper() or not cusip
        is_future = not r["isin"] and not is_cash
        out.append(
            {
                "ticker": CUSIP_TICKER.get(cusip, norm_ticker(r["ticker"])),
                "name": r["description"],
                "sector": CUSIP_SECTOR.get(cusip, "UNMAPPED")
                if not (is_cash or is_future)
                else "OTHER",
                "equity": not (is_cash or is_future),
                "weight": 100 * num(r["weight"]),
                "cusip": cusip,
                "mapped": cusip in CUSIP_SECTOR,
            }
        )
    return pd.DataFrame(out)


def summarize(df: pd.DataFrame) -> dict:
    eq = df[df["equity"] & (df["weight"] > 0)]
    buckets = eq["sector"].map(sector_bucket)
    w = eq["weight"]
    names = {t: float(eq.loc[eq["ticker"] == t, "weight"].sum()) for t in NAMES}
    res = {
        "n_stocks": int(len(eq)),
        "equity_weight": float(w.sum()),
        "it": float(w[buckets == "IT"].sum()),
        "cs": float(w[buckets == "CS"].sum()),
        "names": names,
    }
    if "mapped" in eq:
        res["unmapped_weight"] = float(eq.loc[~eq["mapped"], "weight"].sum())
    return res


print(
    f"1. Holdings (Vanguard as of {VTI_MAP['as_of'].iloc[0]}; others {HOLDINGS_DATE})"
)
H: dict[str, dict] = {}
for t in ["IWD", "IVE", "VLUE", "IWF", "SOXX", "IWV"]:
    H[t] = summarize(read_ishares(t))
for t in ["VTV", "VTI"]:
    H[t] = summarize(read_vanguard(t))
    H[t]["as_of"] = "2026-09-30"
for t in ["AVLV", "AVUV", "AVMV", "AVIV", "AVDV", "AVES"]:
    H[t] = summarize(read_avantis(t))
for t in ["DFLV", "DFSV"]:
    H[t] = summarize(read_dimensional(t))

# AVGV look-through: sleeve weight x sleeve figure.
avgv = read_avantis("AVGV")
sleeves = {
    r.ticker: r.weight / 100
    for r in avgv.itertuples()
    if r.ticker in ("AVLV", "AVUV", "AVMV", "AVIV", "AVDV", "AVES")
}
H["AVGV"] = {
    "sleeves": {k: 100 * v for k, v in sleeves.items()},
    "n_stocks": None,
    "it": sum(w * H[s]["it"] for s, w in sleeves.items()),
    "cs": sum(w * H[s]["cs"] for s, w in sleeves.items()),
    "names": {t: sum(w * H[s]["names"][t] for s, w in sleeves.items()) for t in NAMES},
}
RESULTS["holdings"] = H

# Dimensional's own sector weights (Oct 31) as a check on the CUSIP mapping.
for t in ("DFLV", "DFSV"):
    path = next(DATA.glob(f"dimensional_{t}_detail_*.json"))
    d = json.loads(path.read_text())["data"]
    own = {}
    for g in d["lensGroups"]:
        for lens in (g.get("data") or {}).get("lenses", []) or []:
            ld = lens.get("data") or {}
            if ld.get("slug") == "charsEquityAllocationByGics":
                for a in ld["blends"][0]["data"]["allocations"]:
                    own[a["name"]] = 100 * a["weight"]["value"]
    H[t]["dimensional_reported_oct31"] = {
        "it": own.get("Information Technology"),
        "cs": own.get("Communication Services"),
    }

cols = ["n", "IT", "CS", "IT+CS"] + list(NAMES)
print(f"{'fund':6}" + "".join(f"{c:>8}" for c in cols))
for t in VALUE_FUNDS + ["VTI", "IWV", "IWF", "SOXX"]:
    h = H[t]
    n = "" if h["n_stocks"] is None else str(h["n_stocks"])
    vals = [h["it"], h["cs"], h["it"] + h["cs"]] + [h["names"][k] for k in NAMES]
    print(f"{t:6}{n:>8}" + "".join(f"{v:8.2f}" for v in vals))
print("AVGV sleeves (%):", {k: round(v, 2) for k, v in H["AVGV"]["sleeves"].items()})
for t in ("DFLV", "DFSV"):
    print(
        f"{t}: unmapped equity weight {H[t]['unmapped_weight']:.2f}%; "
        f"Dimensional-reported Oct 31 IT {H[t]['dimensional_reported_oct31']['it']:.2f}, "
        f"CS {H[t]['dimensional_reported_oct31']['cs']:.2f}"
    )


# ---------------------------------------------------------------- prices
def yahoo_daily(ticker: str) -> pd.Series:
    local = CACHE / f"{ticker}.csv"
    if not local.exists():
        import yfinance as yf

        for attempt in range(3):
            px = yf.download(
                ticker,
                start="1999-12-01",
                end="2026-11-13",
                auto_adjust=True,
                progress=False,
            )
            if len(px):
                break
            time.sleep(3 * (attempt + 1))
        close = px["Close"]
        if isinstance(close, pd.DataFrame):
            close = close.iloc[:, 0]
        close.to_csv(local)
    s = pd.read_csv(local, index_col=0, parse_dates=True).iloc[:, 0]
    return s.loc[:"2026-11-12"].dropna()


TICKERS = VALUE_FUNDS + ["VTI", "IWF", "IWN", "SOXX", "NVDA"]
PX = {t: yahoo_daily(t) for t in TICKERS}


def window_return(t: str, a: str, b: str) -> float:
    s = PX[t]
    return float(s.loc[b] / s.loc[a] - 1)


print(f"\n2. Returns, {EVENT_START} close to {EVENT_END} close, and YTD to {YTD_END}")
ev = {}
for t in TICKERS:
    ev[t] = {
        "selloff": window_return(t, EVENT_START, EVENT_END),
        "ytd_oct30": window_return(t, YTD_START, YTD_END),
    }
    print(
        f"{t:6} selloff {100 * ev[t]['selloff']:7.2f}%   "
        f"vs VTI {100 * (ev[t]['selloff'] - window_return('VTI', EVENT_START, EVENT_END)):6.2f} pts   "
        f"YTD {100 * ev[t]['ytd_oct30']:7.2f}%"
    )
for t in ["NVDA", "IWF", "SOXX"]:
    s = PX[t].loc["2026-09-01":EVENT_END]
    print(f"{t} closing high Sep 1 to Nov 12: {s.idxmax().date()} ({s.max():.2f})")
RESULTS["returns"] = {
    "window": [EVENT_START, EVENT_END],
    "ytd": [YTD_START, YTD_END],
    "by_fund": ev,
}


# ---------------------------------------------------------------- regressions
def nw_cov(u: np.ndarray, lags: int) -> np.ndarray:
    n = len(u)
    S = u.T @ u / n
    for L in range(1, lags + 1):
        G = u[L:].T @ u[:-L] / n
        S += (1 - L / (lags + 1)) * (G + G.T)
    return S


def ols(y: pd.Series, X: pd.DataFrame, lags: int) -> dict:
    d = pd.concat([y.rename("y"), X], axis=1).dropna()
    yv = d["y"].to_numpy()
    Xv = np.column_stack([np.ones(len(d)), d[X.columns].to_numpy()])
    n, k = Xv.shape
    XtXi = np.linalg.inv(Xv.T @ Xv)
    b = XtXi @ Xv.T @ yv
    e = yv - Xv @ b
    u = Xv * e[:, None]
    V = XtXi @ (nw_cov(u, lags) * n) @ XtXi * n / (n - k)
    se = np.sqrt(np.diag(V))
    names = ["alpha"] + list(X.columns)
    return {
        "start": str(d.index[0].date()),
        "end": str(d.index[-1].date()),
        "n": int(n),
        "r2": float(1 - (e @ e) / np.sum((yv - yv.mean()) ** 2)),
        "coef": {nm: float(v) for nm, v in zip(names, b, strict=True)},
        "se_nw": {nm: float(v) for nm, v in zip(names, se, strict=True)},
    }


print(f"\n3. Weekly semiconductor sensitivity, {WEEKLY_START} to {EVENT_END}")
W = pd.DataFrame({t: PX[t] for t in TICKERS}).loc[WEEKLY_START:EVENT_END]
W = W.resample("W-THU").last().pct_change().dropna()
X = pd.DataFrame({"VTI": W["VTI"], "SOXX_minus_VTI": W["SOXX"] - W["VTI"]})
semis = {}
for t in VALUE_FUNDS + ["VTI", "IWF", "IWN", "NVDA"]:
    full = ols(W[t], X, 4)
    pre = ols(W[t].loc[:PRE_SELLOFF_END], X.loc[:PRE_SELLOFF_END], 4)
    semis[t] = {"full": full, "pre_selloff": pre}
    b, s = full["coef"]["SOXX_minus_VTI"], full["se_nw"]["SOXX_minus_VTI"]
    bp, sp = pre["coef"]["SOXX_minus_VTI"], pre["se_nw"]["SOXX_minus_VTI"]
    print(
        f"{t:6} n={full['n']} {full['start']}..{full['end']}  "
        f"VTI {full['coef']['VTI']:.2f}  semis {b:+.3f} "
        f"[{b - Z95 * s:+.3f}, {b + Z95 * s:+.3f}]  R2 {full['r2']:.2f}   "
        f"pre-selloff semis {bp:+.3f} [{bp - Z95 * sp:+.3f}, {bp + Z95 * sp:+.3f}]"
    )
RESULTS["semis"] = semis

print(
    f"\n3b. Selloff decomposition with the weekly betas, {EVENT_START} to {EVENT_END}"
)
r_vti = window_return("VTI", EVENT_START, EVENT_END)
r_soxx = window_return("SOXX", EVENT_START, EVENT_END)
decomp = {}
for t in VALUE_FUNDS + ["IWF", "IWN"]:
    c = semis[t]["full"]["coef"]
    market_part = c["VTI"] * r_vti
    semis_part = c["SOXX_minus_VTI"] * (r_soxx - r_vti)
    actual = ev[t]["selloff"]
    decomp[t] = {
        "actual": actual,
        "market_part": market_part,
        "semis_part": semis_part,
        "predicted": market_part + semis_part,
        "residual": actual - market_part - semis_part,
        "vs_vti": actual - r_vti,
    }
    print(
        f"{t:6} actual {100 * actual:+6.2f}  vs VTI {100 * (actual - r_vti):+6.2f}  "
        f"market part {100 * market_part:+6.2f}  semis part {100 * semis_part:+5.2f}  "
        f"predicted {100 * (market_part + semis_part):+6.2f}  "
        f"residual {100 * (actual - market_part - semis_part):+6.2f}"
    )
RESULTS["selloff_decomposition"] = decomp

print("\n3c. Weekly semiconductor coefficient gaps (fund minus fund)")
semis_gaps = {}
for a, b in (("AVGV", "IWD"), ("AVLV", "IWD"), ("AVLV", "VTV")):
    res = ols(W[a] - W[b], X, 4)
    semis_gaps[f"{a}-{b}"] = res
    g, se = res["coef"]["SOXX_minus_VTI"], res["se_nw"]["SOXX_minus_VTI"]
    print(
        f"{a}-{b} n={res['n']} semis gap {g:+.3f} "
        f"[{g - Z95 * se:+.3f}, {g + Z95 * se:+.3f}]"
    )
RESULTS["semis_gaps"] = semis_gaps


def french(name: str) -> pd.DataFrame:
    lines = (DATA / f"{name}.csv").read_text(encoding="latin-1").splitlines()
    for i, ln in enumerate(lines):
        if ln.startswith(","):
            cols = [c.strip() for c in ln.split(",")[1:]]
            rows = []
            for row in lines[i + 1 :]:
                parts = [p.strip() for p in row.split(",")]
                if len(parts[0]) != 6 or not parts[0].isdigit():
                    break
                rows.append(parts)
            idx = pd.to_datetime([r[0] for r in rows], format="%Y%m")
            return (
                pd.DataFrame(
                    [[float(x) for x in r[1:]] for r in rows],
                    index=idx + pd.offsets.MonthEnd(0),
                    columns=cols,
                )
                / 100.0
            )
    raise ValueError(name)


ff5 = french("F-F_Research_Data_5_Factors_2x3")
mom = french("F-F_Momentum_Factor")
mom.columns = [c.strip() for c in mom.columns]
F = ff5.join(mom[["Mom"]], how="left")
assert F.index[-1].strftime("%Y-%m") == FACTOR_END, F.index[-1]
FACT = ["Mkt-RF", "SMB", "HML", "RMW", "CMA", "Mom"]

print(f"\n4. Five factors + momentum, monthly, through {FACTOR_END}")
M = {t: PX[t].resample("ME").last().pct_change() for t in TICKERS}
loadings = {}
for t in [
    "VTV", "IWD", "IVE", "VLUE", "AVLV", "DFLV", "AVUV", "DFSV", "IWN", "VTI", "IWF"
]:  # fmt: skip
    r = M[t]
    # Drop the partial first month after inception.
    first_full = PX[t].index[0] + pd.offsets.MonthEnd(1)
    r = r.loc[first_full + pd.offsets.MonthEnd(0) : FACTOR_END].dropna()
    ex = r - F["RF"].reindex(r.index)
    own = ols(ex, F[FACT].reindex(ex.index), 6)
    com = ols(ex.loc[COMMON_START:], F[FACT].reindex(ex.loc[COMMON_START:].index), 6)
    loadings[t] = {"own": own, "common": com}
    for label, res in (("own", own), ("common", com)):
        c, s = res["coef"], res["se_nw"]
        print(
            f"{t:5} {label:6} {res['start'][:7]}..{res['end'][:7]} n={res['n']:3}  "
            + "  ".join(f"{f} {c[f]:+.2f}({s[f]:.2f})" for f in FACT)
            + f"  a {12 * c['alpha']:+.3f}  R2 {res['r2']:.3f}"
        )
RESULTS["loadings"] = loadings

print("\n4b. Loading gaps: fund minus index ETF, over the fund's own history")
gaps = {}
for fund, index in (
    ("AVLV", "IWD"),
    ("DFLV", "IWD"),
    ("VLUE", "IWD"),
    ("AVUV", "IWN"),
    ("DFSV", "IWN"),
):
    start = loadings[fund]["own"]["start"][:7]
    d = (M[fund] - M[index]).loc[start:FACTOR_END].dropna()
    res = ols(d, F[FACT].reindex(d.index), 6)
    gaps[f"{fund}-{index}"] = res
    c, s_ = res["coef"], res["se_nw"]
    print(
        f"{fund}-{index} {res['start'][:7]}..{res['end'][:7]} n={res['n']}  "
        + "  ".join(
            f"{f} {c[f]:+.2f} [{c[f] - Z95 * s_[f]:+.2f},{c[f] + Z95 * s_[f]:+.2f}]"
            for f in ("SMB", "HML", "RMW", "CMA")
        )
        + f"  alpha {12 * c['alpha']:+.3f} (NW se {12 * s_['alpha']:.3f})  R2 {res['r2']:.2f}"
    )
RESULTS["loading_gaps"] = gaps

g = gaps["AVLV-IWD"]
win = F.loc[g["start"][:7] : g["end"][:7]]
beta_part = 12 * g["coef"]["Mkt-RF"] * win["Mkt-RF"].mean()
diff = (M["AVLV"] - M["IWD"]).loc[g["start"][:7] : g["end"][:7]]
print(
    f"AVLV-IWD: market-beta gap {g['coef']['Mkt-RF']:+.3f} "
    f"(NW se {g['se_nw']['Mkt-RF']:.3f}) x mean Mkt-RF = {100 * beta_part:+.2f} pts/yr "
    f"of an arithmetic gap of {100 * 12 * diff.mean():+.2f} pts/yr"
)
RESULTS["avlv_iwd_beta_part"] = {
    "beta_gap": g["coef"]["Mkt-RF"],
    "beta_part_ann": float(beta_part),
    "arith_gap_ann": float(12 * diff.mean()),
}

print("\n4c. Realized: fund against index ETF over the fund's own history to Oct 2026")
realized = {}
for fund, index in (("AVLV", "IWD"), ("DFLV", "IWD"), ("AVUV", "IWN"), ("DFSV", "IWN")):
    start = loadings[fund]["own"]["start"][:7]
    a = M[fund].loc[start:"2026-10"].dropna()
    b = M[index].reindex(a.index)
    ca = float(np.prod(1 + a) ** (12 / len(a)) - 1)
    cb = float(np.prod(1 + b) ** (12 / len(b)) - 1)
    te = float((a - b).std(ddof=1) * math.sqrt(12))
    realized[f"{fund}-{index}"] = {
        "start": start,
        "end": "2026-10",
        "months": len(a),
        "cagr_fund": ca,
        "cagr_index": cb,
        "tracking_error": te,
    }
    print(
        f"{fund} {100 * ca:.2f}% vs {index} {100 * cb:.2f}% a year, "
        f"{start}..2026-10 ({len(a)} months), tracking error {100 * te:.2f}%"
    )
RESULTS["realized_vs_index"] = realized

print("\n5. HML record (three-factor file)")
ff3 = french("F-F_Research_Data_Factors")
hml = ff3["HML"]
hml_stats = {}
for a, b in (
    ("1926-07", "2007-12"),
    ("2008-01", "2025-03"),
    ("2008-01", "2026-09"),
    ("1926-07", "2026-09"),
):
    x = hml.loc[a:b]
    cagr = float(np.prod(1 + x) ** (12 / len(x)) - 1)
    hml_stats[f"{a}..{b}"] = {
        "months": len(x),
        "mean_x12": float(12 * x.mean()),
        "share_positive": float((x > 0).mean()),
        "compound_annual": cagr,
    }
    print(
        f"{a}..{b}: {len(x)} months, mean x12 {100 * 12 * x.mean():.2f}%, "
        f"positive {100 * (x > 0).mean():.1f}%, compound {100 * cagr:.2f}%"
    )
RESULTS["hml"] = hml_stats

print("\n6. AVUV vs VTI, Oct 2019 to Oct 2026 (monthly)")
avuv = {}
for t in ("AVUV", "VTI"):
    r = M[t].loc["2019-10":"2026-10"].dropna()
    cagr = float(np.prod(1 + r) ** (12 / len(r)) - 1)
    avuv[t] = {
        "months": len(r),
        "cagr": cagr,
        "mean_x12": float(12 * r.mean()),
        "vol": float(r.std(ddof=1) * math.sqrt(12)),
    }
    print(
        f"{t}: {len(r)} months, CAGR {100 * cagr:.2f}%, arithmetic {100 * 12 * r.mean():.2f}%, "
        f"volatility {100 * r.std(ddof=1) * math.sqrt(12):.2f}%"
    )
RESULTS["avuv_vs_vti"] = avuv

(OUT / "results.json").write_text(json.dumps(RESULTS, indent=1, default=float))

# Compact export for the guide's chart.
chart = [
    {"ticker": t, "label": t, "selloff": round(100 * ev[t]["selloff"], 2)}
    for t in VALUE_FUNDS + ["VTI", "IWF", "SOXX"]
]
export = {
    "window": {"start": EVENT_START, "end": EVENT_END},
    "returns": chart,
}
(OUT / "value-etfs-ai-stocks.json").write_text(json.dumps(export, indent=1) + "\n")
print("\nWrote output/results.json and output/value-etfs-ai-stocks.json")
