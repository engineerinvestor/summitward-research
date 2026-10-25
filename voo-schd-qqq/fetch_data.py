"""Download the price and distribution history that analyze.py reads.

Writes two files from Yahoo Finance (via yfinance), both split-adjusted for
SCHD's 3-for-1 split effective after the close on 2024-10-10:

    data/closes.csv         date, then the daily close of each fund
                            (split-adjusted, not dividend-adjusted)
    data/distributions.csv  ex_date, ticker, amount per share
    data/long_closes.csv    QQQ and SPY from QQQ's 1999 launch (SPY stands in
                            for VOO, which launched in 2010)
    data/long_distributions.csv

Usage:
    python3 fetch_data.py
"""

import csv
from pathlib import Path

import yfinance as yf

DATA = Path(__file__).resolve().parent / "data"
FUNDS = ["VOO", "SCHD", "QQQ"]
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


def fetch_long() -> None:
    start, end = "1999-03-10", "2026-10-01"
    closes, rows = {}, []
    for t in ("QQQ", "SPY"):
        tk = yf.Ticker(t)
        hist = tk.history(start=start, end=end, auto_adjust=False)
        closes[t] = {d.strftime("%Y-%m-%d"): float(c) for d, c in hist["Close"].items()}
        for d, amt in tk.dividends.items():
            ds = d.strftime("%Y-%m-%d")
            if start <= ds < end:
                rows.append((ds, t, round(float(amt), 6)))
    dates = sorted(set(closes["QQQ"]) & set(closes["SPY"]))
    with open(DATA / "long_closes.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "QQQ", "SPY"])
        for d in dates:
            w.writerow([d, f"{closes['QQQ'][d]:.6f}", f"{closes['SPY'][d]:.6f}"])
    with open(DATA / "long_distributions.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["ex_date", "ticker", "amount"])
        w.writerows(sorted(rows))
    print(f"long_closes.csv: {len(dates)} days {dates[0]} to {dates[-1]}")


if __name__ == "__main__":
    main()
    fetch_long()
