"""Same funds, seven factor models: how much of "alpha" depends on the model.

Supports https://summitward.com/learn/beyond-fama-french-factor-models.

Requires numpy, pandas, openpyxl (AQR spreadsheets) and yfinance.

Sources (Ken French and global-q CSVs committed in ./data/; AQR and Yahoo
downloaded on first run and cached in ./.cache/, which is not committed):
  * Ken French data library (Tuck), monthly, percent converted to decimals:
      - F-F_Research_Data_Factors: Mkt-RF, SMB, HML, RF
      - F-F_Research_Data_5_Factors_2x3: Mkt-RF, SMB, HML, RMW, CMA, RF
      - F-F_Momentum_Factor: Mom
  * global-q.org q5_factors_monthly_2025.csv (Hou, Mo, Xue and Zhang):
    R_F, R_MKT, R_ME, R_IA, R_ROE, R_EG, percent, 1967-01 to 2025-12.
  * AQR "Quality Minus Junk: Factors, Monthly" xlsx, USA column of the sheets
    "QMJ Factors", "MKT", "SMB", "HML Devil" and "UMD"; AQR "Betting Against
    Beta: Equity Factors, Monthly" xlsx, sheet "BAB Factors", USA column.
    AQR's series are hypothetical research portfolios, not the returns of any
    AQR fund, and are not redistributed here.
  * Yahoo Finance via yfinance: daily adjusted closes (auto_adjust=True),
    resampled to month-end.

Models (all on the same fund excess returns, fund return minus French RF):
  CAPM     Mkt-RF
  FF3      Mkt-RF SMB HML                       (FF3 file)
  Carhart  FF3 + Mom
  FF5      Mkt-RF SMB HML RMW CMA               (FF5 2x3 file)
  FF6      FF5 + Mom
  q4       R_MKT R_ME R_IA R_ROE                (global-q)
  q5       q4 + R_EG
  AQR set  MKT SMB HML-Devil UMD QMJ BAB        (AQR files; our grouping,
                                                 AQR publishes no such model)
  AQR_ffmkt  the AQR set with French's Mkt-RF in place of AQR's MKT

Sections:
  1. Factor overlap, 1967-01 to 2025-12: correlations, and spanning
     regressions of each factor on the rival models.
  2. Funds, common window 2014-01 to 2025-12 (144 months), every model.
     AVUV is run separately over its own shorter window.
  3. Robustness: the section-2 alphas re-estimated with 12 Newey-West lags.

Methods:
  * OLS by numpy with classical and Newey-West (Bartlett) t-stats, 6 lags by
    default. Alpha is 12 x the monthly intercept.
  * Nothing here is a forecast. Every figure describes a named past window.
"""

from __future__ import annotations

import json
import time
import urllib.request
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
CACHE = HERE / ".cache"
OUT = HERE / "output"
for p in (DATA, CACHE, OUT):
    p.mkdir(exist_ok=True)
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0 Safari/537.36"
)
FRENCH = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/{}_CSV.zip"
Q5_URL = "https://global-q.org/uploads/1/2/2/6/122679606/q5_factors_monthly_2025.csv"
AQR_BASE = "https://www.aqr.com/-/media/AQR/Documents/Insights/Data-Sets/"
AQR_QMJ = AQR_BASE + "Quality-Minus-Junk-Factors-Monthly.xlsx"
AQR_BAB = AQR_BASE + "Betting-Against-Beta-Equity-Factors-Monthly.xlsx"

FUNDS = [
    ("VTI", "Vanguard Total Stock Market ETF", "Market"),
    ("VBR", "Vanguard Morningstar Small-Cap Value ETF", "Small value"),
    ("DFSVX", "DFA U.S. Small Cap Value Portfolio (Institutional)", "Small value"),
    ("USMV", "iShares MSCI USA Min Vol Factor ETF", "Defensive"),
    ("QUAL", "iShares MSCI USA Quality Factor ETF", "Quality"),
    ("MTUM", "iShares MSCI USA Momentum Factor ETF", "Momentum"),
    # QCELX changed its principal strategies on 2026-05-04 (AQR fund page);
    # the window below ends 2025-12, so every month is under the old strategy.
    ("QCELX", "AQR Large Cap Multi-Style Fund (I)", "Multi-style"),
]
SHORT = [("AVUV", "Avantis US Small Cap Value ETF", "Small value")]
START, END = "2014-01", "2025-12"

MODELS = {
    "CAPM": ["Mkt-RF"],
    "FF3": ["Mkt-RF3", "SMB3", "HML3"],
    "Carhart": ["Mkt-RF3", "SMB3", "HML3", "Mom"],
    "FF5": ["Mkt-RF", "SMB", "HML", "RMW", "CMA"],
    "FF6": ["Mkt-RF", "SMB", "HML", "RMW", "CMA", "Mom"],
    "q4": ["R_MKT", "R_ME", "R_IA", "R_ROE"],
    "q5": ["R_MKT", "R_ME", "R_IA", "R_ROE", "R_EG"],
    "AQR": ["A_MKT", "A_SMB", "HML_Devil", "A_UMD", "QMJ", "BAB"],
    # AQR's US market series runs about 1 point a year below French's over
    # 2014-2025, which on its own moves a market fund's alpha. This variant
    # swaps in French's market factor to isolate that effect.
    "AQR_ffmkt": ["Mkt-RF", "A_SMB", "HML_Devil", "A_UMD", "QMJ", "BAB"],
}
NW_LAGS = 6
RESULTS: dict = {"sources": {}, "failures": []}


# ---------------------------------------------------------------- utilities
def fetch(url: str, dest: Path) -> Path:
    if not dest.exists():
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=60) as r:
            dest.write_bytes(r.read())
    return dest


def ym(idx) -> str:
    return pd.Timestamp(idx).strftime("%Y-%m")


def french_main(name: str) -> pd.DataFrame:
    """The first monthly (YYYYMM-indexed) block of a French CSV, in decimals."""
    local = DATA / f"{name}.csv"
    if local.exists():
        text = local.read_text(encoding="latin-1")
    else:
        z = zipfile.ZipFile(fetch(FRENCH.format(name), CACHE / f"{name}.zip"))
        text = z.read(z.namelist()[0]).decode("latin-1")
        local.write_text(text, encoding="latin-1")
    lines = text.splitlines()
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
            frame = pd.DataFrame(
                [[float(x) for x in r[1:]] for r in rows],
                index=idx + pd.offsets.MonthEnd(0),
                columns=cols,
            )
            return frame / 100.0
    raise ValueError(f"no monthly block in {name}")


def q5_factors() -> pd.DataFrame:
    local = DATA / "q5_factors_monthly_2025.csv"
    fetch(Q5_URL, local)
    q = pd.read_csv(local)
    idx = pd.to_datetime(
        q["year"].astype(str) + "-" + q["month"].astype(str).str.zfill(2) + "-01"
    ) + pd.offsets.MonthEnd(0)
    q.index = idx
    # R_MKT is already an excess return (1967-01: 8.19% vs French Mkt-RF 8.15%).
    q = q[["R_F", "R_MKT", "R_ME", "R_IA", "R_ROE", "R_EG"]] / 100.0
    return q


def aqr_sheet(url: str, dest: str, sheet: str, col: str = "USA") -> pd.Series:
    raw = pd.read_excel(fetch(url, CACHE / dest), sheet, header=None)
    hdr = raw.index[raw.iloc[:, 0].astype(str).str.strip() == "DATE"][0]
    body = raw.iloc[hdr + 1 :].copy()
    body.columns = [str(c).strip() for c in raw.iloc[hdr]]
    dates = pd.to_datetime(body["DATE"], format="%m/%d/%Y", errors="coerce")
    body = body[dates.notna()]
    body.index = dates[dates.notna()] + pd.offsets.MonthEnd(0)
    return pd.to_numeric(body[col], errors="coerce").dropna()


def ols(y: pd.Series, X: pd.DataFrame, lags: int = NW_LAGS) -> dict:
    d = pd.concat([y.rename("y"), X], axis=1).dropna()
    yv = d["y"].to_numpy()
    Xv = np.column_stack([np.ones(len(d)), d[X.columns].to_numpy()])
    n, k = Xv.shape
    XtXi = np.linalg.inv(Xv.T @ Xv)
    b = XtXi @ Xv.T @ yv
    e = yv - Xv @ b
    s2 = e @ e / (n - k)
    se = np.sqrt(np.diag(s2 * XtXi))
    u = Xv * e[:, None]
    S = u.T @ u
    for L in range(1, lags + 1):
        w = 1 - L / (lags + 1)
        G = u[L:].T @ u[:-L]
        S += w * (G + G.T)
    V = XtXi @ S @ XtXi * n / (n - k)
    se_nw = np.sqrt(np.diag(V))
    sst = np.sum((yv - yv.mean()) ** 2)
    r2 = 1 - (e @ e) / sst
    adj_r2 = 1 - (1 - r2) * (n - 1) / (n - k)
    names = ["alpha"] + list(X.columns)
    return {
        "start": ym(d.index[0]),
        "end": ym(d.index[-1]),
        "n": int(n),
        "r2": float(r2),
        "adj_r2": float(adj_r2),
        "resid_vol_ann": float(np.sqrt(12 * s2)),
        "alpha_ann": float(12 * b[0]),
        "coef": {nm: float(v) for nm, v in zip(names, b, strict=True)},
        "t": {nm: float(v) for nm, v in zip(names, b / se, strict=True)},
        "t_nw": {nm: float(v) for nm, v in zip(names, b / se_nw, strict=True)},
    }


# ---------------------------------------------------------------- load data
print("Loading factors")
ff3 = french_main("F-F_Research_Data_Factors").rename(
    columns={"Mkt-RF": "Mkt-RF3", "SMB": "SMB3", "HML": "HML3"}
)
ff5 = french_main("F-F_Research_Data_5_Factors_2x3")
mom = french_main("F-F_Momentum_Factor").iloc[:, 0].rename("Mom")
q = q5_factors()
aqr = pd.concat(
    {
        "A_MKT": aqr_sheet(AQR_QMJ, "qmj.xlsx", "MKT"),
        "A_SMB": aqr_sheet(AQR_QMJ, "qmj.xlsx", "SMB"),
        "HML_Devil": aqr_sheet(AQR_QMJ, "qmj.xlsx", "HML Devil"),
        "A_UMD": aqr_sheet(AQR_QMJ, "qmj.xlsx", "UMD"),
        "QMJ": aqr_sheet(AQR_QMJ, "qmj.xlsx", "QMJ Factors"),
        "BAB": aqr_sheet(AQR_BAB, "bab.xlsx", "BAB Factors"),
    },
    axis=1,
)
fac = (
    ff5.join(ff3[["Mkt-RF3", "SMB3", "HML3"]], how="inner")
    .join(mom, how="inner")
    .join(q, how="left")
    .join(aqr, how="left")
)
for name, frame in [("french_ff5", ff5), ("global_q5", q), ("aqr", aqr.dropna())]:
    RESULTS["sources"][name] = [ym(frame.index[0]), ym(frame.index[-1])]
    print(f"  {name}: {ym(frame.index[0])}..{ym(frame.index[-1])}")

# Sanity: French and q market factors should track each other closely.
chk = fac.loc["1967-01":END, ["Mkt-RF", "R_MKT", "A_MKT"]].dropna()
RESULTS["market_factor_corr"] = chk.corr().round(4).to_dict()
print("  market factor correlations:\n", chk.corr().round(4))

# ============================================================ 1. overlap
print("\n1. Factor overlap, 1967-01..2025-12")
OV = ["HML", "HML_Devil", "RMW", "CMA", "R_IA", "R_ROE", "R_EG", "QMJ", "BAB", "Mom"]
ov = fac.loc["1967-01":END, OV + ["Mkt-RF", "SMB", "R_MKT", "R_ME"]].dropna()
RESULTS["overlap_window"] = [ym(ov.index[0]), ym(ov.index[-1]), len(ov)]
corr = ov[OV].corr().round(2)
RESULTS["overlap_corr"] = corr.to_dict()
print(corr.to_string())
means = {c: float(12 * ov[c].mean()) for c in OV}
RESULTS["factor_means_ann_1967_2025"] = means
w14 = fac.loc[START:END, OV].dropna()
RESULTS["factor_means_ann_2014_2025"] = {c: float(12 * w14[c].mean()) for c in OV}
print("  annualized means 1967-2025:", {k: round(v * 100, 2) for k, v in means.items()})
print(
    "  annualized means 2014-2025:",
    {k: round(v * 100, 2) for k, v in RESULTS["factor_means_ann_2014_2025"].items()},
)

SPAN = {
    "RMW~q5": ("RMW", MODELS["q5"]),
    "CMA~q5": ("CMA", MODELS["q5"]),
    "HML~q5": ("HML", MODELS["q5"]),
    "R_ROE~FF6": ("R_ROE", MODELS["FF6"]),
    "R_IA~FF6": ("R_IA", MODELS["FF6"]),
    "R_EG~FF6": ("R_EG", MODELS["FF6"]),
    "QMJ~FF6": ("QMJ", MODELS["FF6"]),
    "QMJ~q5": ("QMJ", MODELS["q5"]),
    "BAB~FF6": ("BAB", MODELS["FF6"]),
    "BAB~q5": ("BAB", MODELS["q5"]),
    "HML_Devil~FF6": ("HML_Devil", MODELS["FF6"]),
    "Mom~q5": ("Mom", MODELS["q5"]),
}
RESULTS["spanning"] = {}
for key, (dep, cols) in SPAN.items():
    r = ols(ov[dep], ov[cols])
    RESULTS["spanning"][key] = r
    print(
        f"  {key:14s} alpha {r['alpha_ann'] * 100:+6.2f}%/yr "
        f"(NW t {r['t_nw']['alpha']:+.2f}) R2 {r['r2']:.2f}  "
        + " ".join(f"{c}={r['coef'][c]:+.2f}" for c in cols)
    )


# ============================================================ 2. funds
print("\nLoading Yahoo Finance")
tickers = [t for t, _, _ in FUNDS + SHORT]
px_cache = CACHE / "yahoo_daily.csv"
if px_cache.exists():
    px = pd.read_csv(px_cache, index_col=0, parse_dates=True)
else:
    import yfinance as yf

    frames = {}
    for t in tickers:
        for attempt in range(5):
            try:
                d = yf.download(t, start="2005-01-01", auto_adjust=True, progress=False)
                if len(d):
                    frames[t] = d["Close"].squeeze().rename(t)
                    break
            except Exception as exc:  # noqa: BLE001
                print("   retry", t, exc)
            time.sleep(3 * (attempt + 1))
        else:
            RESULTS["failures"].append(f"Yahoo {t}")
    px = pd.DataFrame(frames)
    px.to_csv(px_cache)
rets = px.resample("ME").last().pct_change(fill_method=None)
RESULTS["sources"]["yahoo_last_day"] = str(px.index.max().date())
for t in tickers:
    s = rets[t].dropna()
    big = s[s.abs() > 0.25]
    print(
        f"   {t:5s} {ym(s.index[0])}..{ym(s.index[-1])} n={len(s)}"
        + (f"  |r|>25%: {[(ym(i), round(v, 3)) for i, v in big.items()]}" if len(big) else "")
    )


def fund_block(funds, start, end, lags=NW_LAGS) -> list[dict]:
    rows = []
    for t, label, group in funds:
        y = (rets[t] - fac["RF"]).loc[start:end].dropna()
        row = {"ticker": t, "label": label, "group": group, "models": {}}
        for m, cols in MODELS.items():
            row["models"][m] = ols(y, fac.loc[start:end, cols], lags)
        rows.append(row)
    return rows


def show(rows: list[dict]) -> None:
    print("  " + " " * 6 + "".join(f"{m:>16s}" for m in MODELS))
    for row in rows:
        cells = []
        for m in MODELS:
            r = row["models"][m]
            cells.append(f"{r['alpha_ann'] * 100:+6.2f}({r['t_nw']['alpha']:+5.2f})")
        print(f"  {row['ticker']:6s}" + "".join(f"{c:>16s}" for c in cells))
    print("  adj R2:")
    for row in rows:
        print(
            f"  {row['ticker']:6s}"
            + "".join(f"{row['models'][m]['adj_r2']:>16.3f}" for m in MODELS)
        )


print(f"\n2. Funds {START}..{END}: annualized alpha % (NW{NW_LAGS} t)")
main = fund_block(FUNDS, START, END)
show(main)
for row in main:
    print(f"  {row['ticker']} loadings:")
    for m in ("FF6", "q5", "AQR"):
        r = row["models"][m]
        print(
            f"     {m:4s} "
            + " ".join(
                f"{c}={r['coef'][c]:+.2f}({r['t_nw'][c]:+.1f})" for c in MODELS[m]
            )
        )
avuv_start = ym(rets["AVUV"].dropna().index[1])
print(f"\n2b. AVUV {avuv_start}..{END}")
short = fund_block(SHORT, avuv_start, END)
show(short)

# ============================================================ 3. robustness
print("\n3. Same funds, NW 12 lags")
rob = fund_block(FUNDS, START, END, lags=12)
show(rob)
flips = []
for a, b in zip(main, rob, strict=True):
    for m in MODELS:
        t6, t12 = a["models"][m]["t_nw"]["alpha"], b["models"][m]["t_nw"]["alpha"]
        if (abs(t6) >= 1.96) != (abs(t12) >= 1.96):
            flips.append(f"{a['ticker']} {m}: t6={t6:.2f} t12={t12:.2f}")
print("  significance changes at 1.96:", flips or "none")

RESULTS["window"] = {"start": START, "end": END, "nw_lags": NW_LAGS}
RESULTS["funds"] = main
RESULTS["funds_short"] = {"start": avuv_start, "end": END, "rows": short}
RESULTS["robustness_nw12"] = {
    r["ticker"]: {m: r["models"][m]["t_nw"]["alpha"] for m in MODELS} for r in rob
}
RESULTS["robustness_flips"] = flips
(OUT / "results.json").write_text(json.dumps(RESULTS, indent=2, default=str))
print(f"\nSaved {(OUT / 'results.json').relative_to(HERE)}")
if RESULTS["failures"]:
    print("FAILURES:", RESULTS["failures"])
