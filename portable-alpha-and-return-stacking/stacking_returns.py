"""Live record of capital-efficient ETFs for the Summitward return-stacking guide.

Reads auto-adjusted (dividends reinvested) daily closes from Yahoo Finance via
yfinance and writes results.json next to this script. Market-price returns,
not NAV returns.

    pip install numpy pandas yfinance
    python3 stacking_returns.py [--end YYYY-MM-DD]
"""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

HERE = Path(__file__).resolve().parent
TICKERS = [
    "NTSX", "RSSB", "RSST", "SPLS", "SPY", "VT", "AOR", "VBIAX",
    "AGG", "IEF", "DBMF", "KMLM", "BIL",
]


def period_return(px: pd.Series, start, end) -> float:
    s = px.dropna()
    s = s[(s.index >= start) & (s.index <= end)]
    return float(s.iloc[-1] / s.iloc[0] - 1)


def max_drawdown(daily: pd.Series) -> float:
    wealth = pd.concat([pd.Series([1.0]), (1 + daily).cumprod().reset_index(drop=True)])
    return float((wealth / wealth.cummax() - 1).min())


def pct(x: float) -> float:
    return round(100 * x, 1)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--end", default=None, help="last date to include")
    args = ap.parse_args()

    close = yf.download(
        TICKERS, start="2018-12-01", end=None, auto_adjust=True, progress=False
    )["Close"][TICKERS].dropna(how="all")
    if args.end:
        close = close[close.index <= args.end]
    rets = close.pct_change()
    end = close.index[-1]
    out: dict = {"data_end": str(end.date()), "first_close": {}}

    # 1. Calendar-year returns; first year is partial, measured from the first close.
    years: dict = {}
    for t in TICKERS:
        s = close[t].dropna()
        out["first_close"][t] = str(s.index[0].date())
        row = {}
        for y in range(2019, end.year + 1):
            this = s[s.index.year == y]
            prior = s[s.index.year < y]
            if this.empty:
                continue
            base = prior.iloc[-1] if len(prior) else this.iloc[0]
            row[str(y) + ("" if len(prior) else "*")] = pct(this.iloc[-1] / base - 1)
        years[t] = row
    out["calendar_year_pct"] = years

    # 2. 2022: NTSX against a costless daily-rebalanced 90/60 built from ETFs.
    in22 = (rets.index > "2021-12-31") & (rets.index <= "2022-12-31")
    manual_9060 = 0.9 * rets.SPY + 0.6 * rets.IEF - 0.5 * rets.BIL
    out["y2022"] = {
        name: {
            "return_pct": pct(float((1 + s[in22]).prod() - 1)),
            "max_drawdown_pct": pct(max_drawdown(s[in22])),
        }
        for name, s in [
            ("NTSX", rets.NTSX), ("SPY", rets.SPY), ("VBIAX", rets.VBIAX),
            ("AGG", rets.AGG), ("manual_90_60", manual_9060),
        ]
    }

    # 3. RSST against SPY, with managed-futures ETFs' excess over BIL for context.
    rsst0 = close.RSST.first_valid_index()
    periods = [
        (rsst0, pd.Timestamp("2023-12-31")),
        (pd.Timestamp("2023-12-29"), pd.Timestamp("2024-12-31")),
        (pd.Timestamp("2024-12-31"), pd.Timestamp("2025-12-31")),
        (pd.Timestamp("2025-12-31"), end),
        (rsst0, end),
    ]
    labels = ["2023 partial", "2024", "2025", f"{end.year} YTD", "since inception"]
    rsst = {}
    for lab, (a, b) in zip(labels, periods, strict=True):
        r = {t: period_return(close[t], a, b) for t in ["RSST", "SPY", "DBMF", "KMLM", "BIL"]}
        rsst[lab] = {
            "RSST": pct(r["RSST"]), "SPY": pct(r["SPY"]),
            "RSST_minus_SPY": pct(r["RSST"] - r["SPY"]),
            "DBMF_minus_BIL": pct(r["DBMF"] - r["BIL"]),
            "KMLM_minus_BIL": pct(r["KMLM"] - r["BIL"]),
        }
    out["rsst_vs_spy_pct"] = rsst

    window = close.loc[rsst0:]
    trailing = window / window.shift(252) - 1
    gap = (trailing.RSST - trailing.SPY).dropna()
    worst_end = gap.idxmin()
    worst_start = window.index[window.index.get_loc(worst_end) - 252]
    out["rsst_worst_12m"] = {
        "start": str(worst_start.date()), "end": str(worst_end.date()),
        "gap_pct": pct(float(gap.min())),
        "RSST_pct": pct(float(trailing.RSST[worst_end])),
        "SPY_pct": pct(float(trailing.SPY[worst_end])),
    }

    best_end = gap.idxmax()
    best_start = window.index[window.index.get_loc(best_end) - 252]
    out["rsst_best_12m"] = {
        "start": str(best_start.date()), "end": str(best_end.date()),
        "gap_pct": pct(float(gap.max())),
    }

    # 4. RSSB against VT and a costless daily-rebalanced VT + IEF - BIL 100/100.
    rssb0 = close.RSSB.first_valid_index()
    manual_100 = rets.VT + rets.IEF - rets.BIL
    since = rets.index > rssb0
    rssb = {}
    for lab, (a, b) in zip(
        ["2023 partial", "2024", "2025", f"{end.year} YTD", "since inception"],
        [(rssb0, pd.Timestamp("2023-12-31"))] + periods[1:4] + [(rssb0, end)],
        strict=True,
    ):
        m = (rets.index > a) & (rets.index <= b)
        rssb[lab] = {
            "RSSB": pct(period_return(close.RSSB, a, b)),
            "VT": pct(period_return(close.VT, a, b)),
            "manual_100_100": pct(float((1 + manual_100[m]).prod() - 1)),
        }
    out["rssb_vs_vt_pct"] = rssb
    out["rssb_risk"] = {
        name: {
            "ann_vol_pct": pct(float(s[since].std() * np.sqrt(252))),
            "max_drawdown_pct": pct(max_drawdown(s[since].dropna())),
        }
        for name, s in [("RSSB", rets.RSSB), ("VT", rets.VT), ("manual_100_100", manual_100)]
    }

    # 5. Correlation with SPY and volatility since RSST's first close.
    d = rets[rets.index > rsst0]
    overlay = d.RSST - d.SPY
    out["since_rsst_corr_vol"] = {
        name: {
            "corr_with_SPY": round(float(d.SPY.corr(s)), 2),
            "ann_vol_pct": pct(float(s.std() * np.sqrt(252))),
        }
        for name, s in [
            ("RSST_minus_SPY", overlay), ("DBMF", d.DBMF), ("KMLM", d.KMLM),
            ("IEF", d.IEF), ("SPY", d.SPY), ("RSST", d.RSST),
        ]
    }

    # 6. Stock-bond correlation by calendar year (SPY vs IEF daily returns).
    sb = yf.download(["SPY", "IEF"], start="2002-08-01", auto_adjust=True, progress=False)[
        "Close"
    ].pct_change().dropna()
    sb = sb[sb.index <= end]
    by_year = sb.groupby(sb.index.year).apply(lambda g: round(float(g.SPY.corr(g.IEF)), 2))
    out["spy_ief_corr_by_year"] = {str(k): v for k, v in by_year.items()}
    pre = sb[(sb.index >= "2003-01-01") & (sb.index <= "2021-12-31")]
    out["spy_ief_corr_2003_2021"] = round(float(pre.SPY.corr(pre.IEF)), 2)

    path = HERE / "results.json"
    path.write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps(out, indent=2))
    print(f"Saved {path.name}")


if __name__ == "__main__":
    main()
