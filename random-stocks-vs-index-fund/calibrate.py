"""Calibrate the random-portfolio model to current S&P 500 members.

Supports https://summitward.com/learn/random-stocks-vs-index-fund.

1. Reads SPY's daily holdings file (State Street) for the current constituent
   list and weights; counts share classes per company.
2. Downloads 60 month-end total-return closes (Yahoo, adjusted) for every
   constituent and for SPY, November 2021 to October 2026.
3. Regresses each stock's monthly return on SPY's (single-index model) and
   reports idiosyncratic volatility, beta and total volatility across stocks:
   median, interquartile range, root-mean-square (the figure that sets the
   tracking error of an equal-weight portfolio) and cap-weighted RMS.

Current members are survivors, so these volatilities understate the
idiosyncratic risk of a constituent drawn at an earlier date. That bias makes
small random portfolios look safer than they were.

Needs numpy, pandas, openpyxl, yfinance. Downloads are cached in .cache/.
Writes output/calibration.json.
"""

from __future__ import annotations

import json
import urllib.request
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
SPY_URL = (
    "https://www.ssga.com/library-content/products/fund-data/etfs/us/"
    "holdings-daily-us-en-spy.xlsx"
)
START, END = "2021-10-01", "2026-11-01"  # month-ends Oct 2021 .. Oct 2026
FIRST_RETURN, LAST_RETURN = "2021-11", "2026-10"
MIN_MONTHS = 60
DUAL_CLASS = {"GOOG": "GOOGL", "FOX": "FOXA", "NWS": "NWSA"}  # second class -> first


def spy_holdings() -> tuple[pd.DataFrame, str]:
    path = CACHE / "spy.xlsx"
    if not path.exists():
        req = urllib.request.Request(SPY_URL, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=60) as r:
            path.write_bytes(r.read())
    raw = pd.read_excel(path, header=None)
    as_of = str(raw.iloc[2, 1]).replace("As of ", "")
    hdr = raw.index[raw.iloc[:, 0] == "Name"][0]
    df = raw.iloc[hdr + 1 :, :].copy()
    df.columns = raw.iloc[hdr].tolist()
    df = df[pd.to_numeric(df["Weight"], errors="coerce").notna()]
    df["Ticker"] = df["Ticker"].astype(str).str.strip()
    # Drop the cash line and unlisted stubs (e.g. a $0.01 Hologic contra line).
    df = df[df["Ticker"].str.fullmatch(r"[A-Z]{1,5}(\.[A-Z])?")].copy()
    df["Weight"] = df["Weight"].astype(float) / 100
    return df[["Name", "Ticker", "Weight"]].reset_index(drop=True), as_of


def yahoo(t: str) -> str:
    return t.replace(".", "-").replace(" ", "-")


def monthly_returns(tickers: list[str]) -> pd.DataFrame:
    path = CACHE / "monthly_closes.csv"
    if path.exists():
        closes = pd.read_csv(path, index_col=0, parse_dates=True)
    else:
        daily = yf.download(
            tickers, start=START, end=END, auto_adjust=True, progress=False,
            threads=True,
        )["Close"]
        closes = daily.resample("ME").last()
        closes.to_csv(path)
    rets = closes.pct_change(fill_method=None).loc[FIRST_RETURN:LAST_RETURN]
    return rets


def main() -> None:
    hold, as_of = spy_holdings()
    # Companies with more than one share class in the file.
    present = set(hold["Ticker"])
    multi = {a: [a, b] for b, a in DUAL_CLASS.items() if a in present and b in present}

    tickers = [yahoo(t) for t in hold["Ticker"]]
    rets = monthly_returns(tickers + ["SPY"])
    mkt = rets["SPY"]

    rows = []
    for t, ytk, w in zip(hold["Ticker"], tickers, hold["Weight"]):
        if ytk not in rets:
            continue
        r = rets[ytk]
        ok = r.notna() & mkt.notna()
        if ok.sum() < MIN_MONTHS:
            continue
        y, x = r[ok].to_numpy(), mkt[ok].to_numpy()
        X = np.column_stack([np.ones_like(x), x])
        coef, *_ = np.linalg.lstsq(X, y, rcond=None)
        resid = y - X @ coef
        idio = resid.std(ddof=2) * np.sqrt(12)
        rows.append(
            {
                "ticker": t,
                "weight": w,
                "beta": coef[1],
                "idio_vol": idio,
                "total_vol": y.std(ddof=1) * np.sqrt(12),
            }
        )
    df = pd.DataFrame(rows)
    # Fund weights stay out of the committed file (State Street's terms limit
    # redistributing holdings data); only price-derived statistics are saved.
    df.drop(columns="weight").to_csv(
        OUT / "per_stock.csv", index=False, float_format="%.5f"
    )

    def summ(col: str) -> dict:
        s = df[col]
        w = df["weight"] / df["weight"].sum()
        out = {
            "median": round(float(s.median()), 4),
            "p25": round(float(s.quantile(0.25)), 4),
            "p75": round(float(s.quantile(0.75)), 4),
            "mean": round(float(s.mean()), 4),
        }
        if col != "beta":
            out["rms"] = round(float(np.sqrt((s**2).mean())), 4)
            out["cap_weighted_rms"] = round(float(np.sqrt((w * s**2).sum())), 4)
        else:
            out["sd"] = round(float(s.std(ddof=1)), 4)
        return out

    mkt_vol = float(mkt.std(ddof=1) * np.sqrt(12))
    company_w = (
        hold.assign(c=hold["Ticker"].replace({b: a for b, a in DUAL_CLASS.items()}))
        .groupby("c")["Weight"]
        .sum()
    )
    company_w = company_w / company_w.sum()
    closes = pd.read_csv(CACHE / "monthly_closes.csv", index_col=0, parse_dates=True)
    last = closes.iloc[-1].drop("SPY").dropna()
    result = {
        "holdings_as_of": as_of,
        "equity_securities": int(len(hold)),
        "companies": int(len(hold) - len(multi)),
        "companies_with_two_share_classes": multi,
        "window": f"{FIRST_RETURN} to {LAST_RETURN} (monthly, total return)",
        "stocks_with_full_history": int(len(df)),
        "securities_dropped_short_history": int(len(hold) - len(df)),
        "spy_annualized_vol": round(mkt_vol, 4),
        "top10_company_share": round(float(company_w.nlargest(10).sum()), 4),
        "effective_n_companies": round(float(1 / (company_w**2).sum()), 1),
        "share_price_month_end": f"{closes.index[-1]:%Y-%m-%d}",
        "stocks_above_1000": int((last > 1000).sum()),
        "stocks_above_500": int((last > 500).sum()),
        "highest_share_price": round(float(last.max()), 2),
        "idiosyncratic_vol": summ("idio_vol"),
        "total_vol": summ("total_vol"),
        "beta": summ("beta"),
    }
    (OUT / "calibration.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
