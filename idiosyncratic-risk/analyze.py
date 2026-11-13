"""Idiosyncratic risk: Nvidia's CEO exit and how much of it reaches index funds.

Supports https://summitward.com/learn/idiosyncratic-risk.

1. Event study: NVDA abnormal returns from the first spy report (Oct 29, 2026)
   through Jensen Huang's resignation (announced Nov 12, 2026) under three
   benchmarks: SPY, SOXX, and SPY + SOXX.
2. Nvidia's direct contribution to SPY on Nov 12, 2026 (weight x return).
3. Effective number of companies (1 / sum of squared weights) for SPY, ACWI and
   IJS from issuer holdings files, plus equal weight by construction.
4. Nvidia's company-specific share of each holding's variance:
   (w_NVDA * sigma_eps)^2 / sigma_fund^2, with sigma_eps from weekly NVDA
   returns regressed on ACWI, and on ACWI + SOXX.

Needs numpy, pandas, openpyxl, yfinance. Downloads are cached in .cache/.
Writes output/idiosyncratic-risk.json.
"""

from __future__ import annotations

import csv
import io
import json
import re
import sys
import urllib.request
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

HERE = Path(__file__).resolve().parent
CACHE = HERE / ".cache"
OUT = HERE / "output"
CACHE.mkdir(exist_ok=True)
OUT.mkdir(exist_ok=True)

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
HOLDINGS = {
    "spy.xlsx": "https://www.ssga.com/library-content/products/fund-data/etfs/us/holdings-daily-us-en-spy.xlsx",
    "acwi.csv": "https://www.ishares.com/us/products/239600/ishares-msci-acwi-etf/latest-holdings.csv",
    "ijs.csv": "https://www.ishares.com/us/products/239775/ishares-sp-smallcap-600-value-etf/latest-holdings.csv",
}

# Event calendar (trading days). Huang's admission letter was Sunday Nov 8.
EST_END = "2026-10-27"  # last day of the estimation window
EST_DAYS = 250
BASE = "2026-10-28"  # close before the first spy report
PHASES = {
    "phase1_reports_and_chip_selloff": ("2026-10-29", "2026-11-06"),
    "phase2_admission_to_resignation": ("2026-11-09", "2026-11-12"),
    "total": ("2026-10-29", "2026-11-12"),
}
WEEKLY_END = "2026-10-23"  # last Friday before the first report

TICKERS = ["NVDA", "SPY", "SOXX", "^SOX", "ACWI", "VT", "IJS", "RSP"]


def fetch(name: str) -> Path:
    path = CACHE / name
    if not path.exists():
        req = urllib.request.Request(HOLDINGS[name], headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=60) as r:
            path.write_bytes(r.read())
    return path


def prices() -> pd.DataFrame:
    path = CACHE / "prices.csv"
    if path.exists():
        return pd.read_csv(path, index_col=0, parse_dates=True)
    end = (date.today() + timedelta(days=1)).isoformat()
    df = yf.download(
        TICKERS, start="2020-01-01", end=end, auto_adjust=True, progress=False
    )["Close"]
    df = df[TICKERS].dropna(how="all")
    df.to_csv(path)
    return df


# ---------------------------------------------------------------- holdings
DUAL_CLASS = {"GOOG": "GOOGL", "FOX": "FOXA", "NWS": "NWSA"}


def spy_weights() -> tuple[pd.Series, str]:
    raw = pd.read_excel(fetch("spy.xlsx"), header=None)
    as_of = str(raw.iloc[2, 1]).replace("As of ", "")
    hdr = raw.index[raw.iloc[:, 0] == "Name"][0]
    df = raw.iloc[hdr + 1 :, :].copy()
    df.columns = raw.iloc[hdr].tolist()
    df = df[pd.to_numeric(df["Weight"], errors="coerce").notna()]
    df = df[df["Ticker"].notna() & (df["Ticker"] != "-")]
    df["Weight"] = df["Weight"].astype(float)
    df["company"] = df["Ticker"].map(lambda t: DUAL_CLASS.get(t, t))
    return df.groupby("company")["Weight"].sum() / 100, as_of


def ishares_weights(name: str) -> tuple[pd.Series, str]:
    text = fetch(name).read_text(encoding="utf-8-sig")
    lines = text.splitlines()
    as_of = next(l for l in lines if l.startswith("Fund Holdings as of")).split(",", 1)[1].strip('"')
    start = next(i for i, l in enumerate(lines) if l.startswith("Ticker,"))
    rows = list(csv.reader(io.StringIO("\n".join(lines[start:]))))
    hdr, body = rows[0], rows[1:]
    wcol = "Weight (%)" if "Weight (%)" in hdr else "Market Weight"
    recs = []
    for r in body:
        if len(r) != len(hdr):
            continue
        d = dict(zip(hdr, r))
        if d.get("Asset Class") != "Equity":
            continue
        try:
            w = float(d[wcol].replace(",", ""))
        except ValueError:
            continue
        # Merge share classes of one issuer: strip class suffixes from the name.
        key = re.sub(r"\s+(CLASS|CL)\s+[A-Z]$|\s+[A-Z]$", "", d["Name"].strip())
        recs.append((key, d["Ticker"], w))
    df = pd.DataFrame(recs, columns=["company", "ticker", "w"])
    s = df.groupby("company")["w"].sum()
    nvda = df.loc[df["ticker"] == "NVDA", "w"].sum()
    return s / s.sum(), as_of, nvda / s.sum() if s.sum() else 0.0


def concentration(w: pd.Series) -> dict:
    w = w / w.sum()
    ws = w.sort_values(ascending=False)
    return {
        "companies": int((w > 0).sum()),
        "effective_n": round(float(1 / (w**2).sum()), 1),
        "top10_share": round(float(ws.iloc[:10].sum()), 4),
        "largest": ws.index[0],
        "largest_weight": round(float(ws.iloc[0]), 4),
    }


# ---------------------------------------------------------------- regressions
def ols(y: np.ndarray, X: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    X1 = np.column_stack([np.ones(len(y)), X])
    b, *_ = np.linalg.lstsq(X1, y, rcond=None)
    return b, y - X1 @ b


def main() -> None:
    px = prices()
    last = px.index[-1].date().isoformat()
    print(f"price data through {last}")
    if last < PHASES["total"][1]:
        print("WARNING: Nov 12 close not in data yet; event windows are partial")
    rets = px.pct_change()

    out: dict = {"price_data_through": last}

    # ------------------------------------------------------------ closes
    closes = {}
    for d in ["2026-10-28", "2026-11-06", "2026-11-09", "2026-11-10", "2026-11-11", "2026-11-12"]:
        if pd.Timestamp(d) in px.index:
            closes[d] = {t: round(float(px.loc[d, t]), 2) for t in ["NVDA", "SPY", "SOXX"]}
    out["closes_adjusted"] = closes

    # ------------------------------------------------------------ event study
    est = rets.loc[:EST_END].dropna(subset=["NVDA", "SPY", "SOXX"]).iloc[-EST_DAYS:]
    out["estimation_window"] = [est.index[0].date().isoformat(), est.index[-1].date().isoformat()]
    specs = {"SPY": ["SPY"], "SOXX": ["SOXX"], "SPY+SOXX": ["SPY", "SOXX"], "^SOX": ["^SOX"]}
    event = {}
    for name, xs in specs.items():
        e = est.dropna(subset=xs)
        b, resid = ols(e["NVDA"].values, e[xs].values)
        sd = resid.std(ddof=len(xs) + 1)
        ev = rets.loc["2026-10-29":].dropna(subset=["NVDA"] + xs)
        ar = ev["NVDA"] - (b[0] + ev[xs].values @ b[1:])
        res = {
            "alpha_daily": round(float(b[0]), 5),
            "betas": {x: round(float(v), 3) for x, v in zip(xs, b[1:])},
            "resid_sd_daily": round(float(sd), 4),
            "daily_ar": {d.date().isoformat(): round(float(v), 4) for d, v in ar.items()},
        }
        for ph, (a, z) in PHASES.items():
            w = ar.loc[a:z]
            car = float(w.sum())
            res[ph] = {
                "days": int(len(w)),
                "car": round(car, 4),
                "t": round(car / (sd * np.sqrt(len(w))), 2) if len(w) else None,
            }
        event[name] = res
    out["event_study"] = event

    raw = {}
    for t in ["NVDA", "SPY", "SOXX", "^SOX"]:
        base = px.loc[BASE, t]
        s = px.loc[BASE:, t] / base - 1
        raw[t] = {d.date().isoformat(): round(float(v), 4) for d, v in s.items()}
    out["cumulative_from_oct28"] = raw
    for ph, (a, z) in PHASES.items():
        prev = px.index[px.index.get_loc(pd.Timestamp(a)) - 1]
        out.setdefault("raw_phase_returns", {})[ph] = {
            t: round(float(px.loc[z, t] / px.loc[prev, t] - 1), 4)
            for t in ["NVDA", "SPY", "SOXX", "^SOX"]
            if pd.Timestamp(z) in px.index
        }

    # ------------------------------------------------------------ holdings
    spy_w, spy_asof = spy_weights()
    acwi_w, acwi_asof, acwi_nvda = ishares_weights("acwi.csv")
    ijs_w, ijs_asof, ijs_nvda = ishares_weights("ijs.csv")
    nvda_w = {
        "SPY": round(float(spy_w.get("NVDA", 0.0)), 5),
        "ACWI": round(float(acwi_nvda), 5),
        "IJS": round(float(ijs_nvda), 5),
        "RSP": round(1 / len(spy_w), 5),  # equal weight at rebalance
    }
    out["holdings"] = {
        "SPY": {"as_of": spy_asof, **concentration(spy_w)},
        "ACWI": {"as_of": acwi_asof, **concentration(acwi_w)},
        "IJS": {"as_of": ijs_asof, **concentration(ijs_w)},
        "RSP": {
            "as_of": "by construction at quarterly rebalance",
            "companies": len(spy_w),
            "effective_n": float(len(spy_w)),
        },
        "nvda_weight": nvda_w,
    }

    # ------------------------------------------------------------ Nov 12 contribution
    if pd.Timestamp("2026-11-12") in rets.index:
        r_n = float(rets.loc["2026-11-12", "NVDA"])
        r_s = float(rets.loc["2026-11-12", "SPY"])
        w = nvda_w["SPY"]
        out["nov12"] = {
            "nvda_return": round(r_n, 4),
            "spy_return": round(r_s, 4),
            "nvda_contribution_pp": round(100 * w * r_n, 3),
            "spy_ex_nvda_return_implied": round((r_s - w * r_n) / (1 - w), 4),
        }
    # Implied daily SPY weight, backed out from the Nov 11 holdings file by
    # relative price (ignores index changes and share-count updates), and
    # Nvidia's contribution to SPY: raw and abnormal (SPY+SOXX model).
    w11 = nvda_w["SPY"]
    rel = (px["NVDA"] / px.loc["2026-11-11", "NVDA"]) / (px["SPY"] / px.loc["2026-11-11", "SPY"])
    w_imp = w11 * rel  # SPY's value includes NVDA, so this is exact
    ar_both = pd.Series(event["SPY+SOXX"]["daily_ar"])
    ar_both.index = pd.to_datetime(ar_both.index)
    contrib = {}
    for ph, (a, z) in PHASES.items():
        days = rets.loc[a:z].index
        prev_w = w_imp.shift(1).loc[days]
        contrib[ph] = {
            "raw_pp": round(float(100 * (prev_w * rets.loc[days, "NVDA"]).sum()), 3),
            "abnormal_pp": round(float(100 * (prev_w * ar_both.reindex(days)).sum()), 3),
        }
    out["spy_contribution"] = {
        "implied_weight_oct28": round(float(w_imp.loc[BASE]), 4),
        "implied_weight_nov06": round(float(w_imp.loc["2026-11-06"]), 4),
        **contrib,
    }
    d1 = rets.loc[:EST_END, "SPY"].dropna().iloc[-252:]
    out["spy_daily_sd_1y"] = round(float(d1.std()), 4)

    # ------------------------------------------------------------ risk share
    wk = px.loc[:WEEKLY_END].resample("W-FRI").last().pct_change()
    share = {}
    for label, years in [("3y", 3), ("5y", 5)]:
        start = pd.Timestamp(WEEKLY_END) - pd.DateOffset(years=years)
        w_ = wk.loc[start:].dropna(subset=["NVDA", "ACWI", "SOXX", "SPY", "IJS", "RSP"])
        n_wk = len(w_)
        sig = lambda s: float(s.std() * np.sqrt(52))  # noqa: E731
        res = {"weeks": n_wk, "window": [w_.index[0].date().isoformat(), w_.index[-1].date().isoformat()]}
        for spec, xs in [("market", ["ACWI"]), ("market+chips", ["ACWI", "SOXX"])]:
            b, eps = ols(w_["NVDA"].values, w_[xs].values)
            s_eps = float(eps.std(ddof=len(xs) + 1) * np.sqrt(52))
            s_nvda = sig(w_["NVDA"])
            mix = 0.1 * w_["NVDA"] + 0.9 * w_["ACWI"]
            rows = {
                "NVDA alone": (1.0, s_nvda),
                "10% NVDA + 90% ACWI": (0.1 + 0.9 * nvda_w["ACWI"], sig(mix)),
                "SPY (S&P 500)": (nvda_w["SPY"], sig(w_["SPY"])),
                "ACWI (global)": (nvda_w["ACWI"], sig(w_["ACWI"])),
                "RSP (equal weight)": (nvda_w["RSP"], sig(w_["RSP"])),
                "IJS (small-cap value)": (nvda_w["IJS"], sig(w_["IJS"])),
            }
            res[spec] = {
                "betas": {x: round(float(v), 3) for x, v in zip(xs, b[1:])},
                "nvda_resid_vol": round(s_eps, 4),
                "nvda_total_vol": round(s_nvda, 4),
                "rows": {
                    k: {
                        "nvda_weight": round(wt, 4),
                        "holding_vol": round(v, 4),
                        "nvda_specific_share": round((wt * s_eps) ** 2 / v**2, 4),
                    }
                    for k, (wt, v) in rows.items()
                },
            }
        share[label] = res
    out["risk_share"] = share

    (OUT / "idiosyncratic-risk.json").write_text(json.dumps(out, indent=2))
    json.dump(out, sys.stdout, indent=1)


if __name__ == "__main__":
    main()
