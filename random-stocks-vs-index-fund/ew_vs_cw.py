"""Equal weight vs cap weight in live funds: RSP against SPY.

Supports https://summitward.com/learn/random-stocks-vs-index-fund.

A random-stock rule that puts equal dollars into each draw earns, in
expectation, the equal-weighted return of its universe. RSP (Invesco S&P 500
Equal Weight ETF) is the live, investable version of that tilt for the S&P 500;
SPY is the cap-weighted version. Both series are Yahoo adjusted closes (total
return, net of each fund's expense ratio). Monthly, from RSP's first full
month (June 2003; Yahoo has no complete May) to October 2026.

Reports annualized returns for the full period and for calendar decades,
rolling 10-year annualized return differences, and the share of rolling
10-year windows in which RSP finished ahead.

Needs pandas, yfinance. Writes output/ew_vs_cw.json.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

HERE = Path(__file__).resolve().parent
CACHE = HERE / ".cache"
OUT = HERE / "output"
CACHE.mkdir(exist_ok=True)
OUT.mkdir(exist_ok=True)
START, END = "2003-04-01", "2026-11-01"


def monthly() -> pd.DataFrame:
    path = CACHE / "rsp_spy_monthly.csv"
    if path.exists():
        return pd.read_csv(path, index_col=0, parse_dates=True)
    d = yf.download(["RSP", "SPY"], start=START, end=END, auto_adjust=True, progress=False)
    m = d["Close"].resample("ME").last()
    m.to_csv(path)
    return m


def ann(r: pd.Series) -> float:
    return float((1 + r).prod() ** (12 / len(r)) - 1)


def main() -> None:
    px = monthly()
    r = px.pct_change(fill_method=None).loc["2003-05":"2026-10"].dropna()
    out = {
        "window": f"{r.index[0]:%Y-%m} to {r.index[-1]:%Y-%m}",
        "months": int(len(r)),
        "full_period": {t: round(ann(r[t]), 4) for t in ("RSP", "SPY")},
        "vol": {t: round(float(r[t].std() * np.sqrt(12)), 4) for t in ("RSP", "SPY")},
    }
    periods = {
        "2003-06 to 2012-12": ("2003-06", "2012-12"),
        "2013-01 to 2022-12": ("2013-01", "2022-12"),
        "2023-01 to 2026-10": ("2023-01", "2026-10"),
        "2023-01 to 2025-12": ("2023-01", "2025-12"),
        "2026-01 to 2026-10": ("2026-01", "2026-10"),
        "last 12m (2025-11 to 2026-10)": ("2025-11", "2026-10"),
        "last 10y (2016-11 to 2026-10)": ("2016-11", "2026-10"),
        "last 5y (2021-11 to 2026-10)": ("2021-11", "2026-10"),
    }
    out["periods"] = {
        k: {t: round(ann(r.loc[a:b, t]), 4) for t in ("RSP", "SPY")}
        for k, (a, b) in periods.items()
    }
    out["cumulative"] = {
        k: {t: round(float((1 + r.loc[a:b, t]).prod() - 1), 4) for t in ("RSP", "SPY")}
        for k, (a, b) in periods.items()
        if k.startswith(("2023-01 to 2025", "2026-01", "last 12m"))
    }
    w = 120
    roll = {
        t: (1 + r[t]).rolling(w).apply(np.prod, raw=True) ** (12 / w) - 1
        for t in ("RSP", "SPY")
    }
    diff = (roll["RSP"] - roll["SPY"]).dropna()
    out["rolling_10y"] = {
        "windows": int(len(diff)),
        "first_window_end": f"{diff.index[0]:%Y-%m}",
        "share_rsp_ahead": round(float((diff > 0).mean()), 4),
        "max_lead": [round(float(diff.max()), 4), f"{diff.idxmax():%Y-%m}"],
        "max_lag": [round(float(diff.min()), 4), f"{diff.idxmin():%Y-%m}"],
        "latest": round(float(diff.iloc[-1]), 4),
    }
    # $1 at the start of each month for 120 months into RSP vs into SPY:
    # ending wealth of the RSP account as a multiple of the SPY account.
    rr = r[["RSP", "SPY"]].to_numpy()
    ratios, ends = [], []
    for e in range(w, len(rr) + 1):
        win = rr[e - w : e]
        grow = np.cumprod((1 + win)[::-1], axis=0)[::-1]  # value at end of $1 put in at t
        ratios.append(float(grow[:, 0].sum() / grow[:, 1].sum()))
        ends.append(r.index[e - 1])
    ratios = np.array(ratios)
    out["monthly_contributions_10y"] = {
        "windows": int(len(ratios)),
        "note": "overlapping windows; ends from first_end to last_end",
        "first_end": f"{ends[0]:%Y-%m}",
        "last_end": f"{ends[-1]:%Y-%m}",
        "latest": round(float(ratios[-1]), 4),
        "median": round(float(np.median(ratios)), 4),
        "min": [round(float(ratios.min()), 4), f"{ends[int(ratios.argmin())]:%Y-%m}"],
        "max": [round(float(ratios.max()), 4), f"{ends[int(ratios.argmax())]:%Y-%m}"],
        "share_below_0_90": round(float((ratios < 0.90).mean()), 4),
        "share_above_1_10": round(float((ratios > 1.10).mean()), 4),
    }
    out["rolling_10y_series"] = [
        {"end": f"{i:%Y-%m}", "rsp_minus_spy": round(float(v), 4)} for i, v in diff.items()
    ]
    (OUT / "ew_vs_cw.json").write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps({k: v for k, v in out.items() if k != "rolling_10y_series"}, indent=2))


if __name__ == "__main__":
    main()
