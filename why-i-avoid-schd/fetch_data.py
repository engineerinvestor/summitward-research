"""Download the price and distribution history that analyze.py reads.

Writes two files from Yahoo Finance (via yfinance), both split-adjusted for
SCHD's 3-for-1 split effective after the close on 2024-10-10:

    data/closes.csv         date, then the daily close of each fund
                            (split-adjusted, not dividend-adjusted)
    data/distributions.csv  ex_date, ticker, amount per share

Usage:
    python3 fetch_data.py
"""

import csv
from pathlib import Path

import yfinance as yf

DATA = Path(__file__).resolve().parent / "data"
FUNDS = ["SCHD", "VTI", "VOO"]
START, END = "2011-10-20", "2026-10-01"  # SCHD inception; END is exclusive


def main() -> None:
    DATA.mkdir(exist_ok=True)
    closes: dict[str, dict[str, float]] = {}
    dist_rows = []
    for t in FUNDS:
        tk = yf.Ticker(t)
        hist = tk.history(start=START, end=END, auto_adjust=False)
        closes[t] = {d.strftime("%Y-%m-%d"): float(c) for d, c in hist["Close"].items()}
        divs = tk.dividends
        for d, amt in divs.items():
            ds = d.strftime("%Y-%m-%d")
            if START <= ds < END:
                dist_rows.append((ds, t, round(float(amt), 6)))

    dates = sorted(set.intersection(*(set(v) for v in closes.values())))
    with open(DATA / "closes.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", *FUNDS])
        for d in dates:
            w.writerow([d, *(f"{closes[t][d]:.6f}" for t in FUNDS)])
    with open(DATA / "distributions.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["ex_date", "ticker", "amount"])
        w.writerows(sorted(dist_rows))
    print(f"closes.csv: {len(dates)} days {dates[0]} to {dates[-1]}")
    print(f"distributions.csv: {len(dist_rows)} rows")


if __name__ == "__main__":
    main()
