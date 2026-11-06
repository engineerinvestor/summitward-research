"""How much displayed exchange order volume ever trades? SEC MIDAS metrics.

Supports https://summitward.com/learn/more-buyers-than-sellers.

Reads the SEC's "Market Structure Metrics by Exchange" download, the aggregate
file etp_stock_timeseries3.csv (daily, 2012-01-03 onward), and prints period
averages of two metrics for corporate stocks and exchange-traded products:

- Trade-Order Volume (percent): shares traded during continuous trading divided
  by the share volume of every displayed limit order added, across 12-13
  exchange feeds. Opening and closing crosses are excluded.
- Cancel-Trade Ratio: number of cancel events divided by number of trade
  events.

Averages are simple means of the daily values in each period, computed here;
the SEC does not publish quarterly averages in the file.

Usage:
    python sec_order_metrics.py             # uses the committed CSV in data/
    python sec_order_metrics.py --refresh   # re-downloads it from the SEC

The committed data/etp_stock_timeseries3.csv is extracted unchanged from the
SEC zip below (U.S. government work, public domain).

SEC asks automated clients to identify themselves; set
SEC_USER_AGENT="Your Name you@example.com".
"""

from __future__ import annotations

import argparse
import csv
import io
import os
import statistics
import urllib.request
import zipfile
from pathlib import Path

URL = (
    "https://www.sec.gov/files/opa/data/market-structure/"
    "summary-metrics-exchange/metrics_by_exchange_q2_2026.zip"
)
HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
MEMBER = "etp_stock_timeseries3.csv"
CSV = DATA / MEMBER
UA = {
    "User-Agent": os.environ.get(
        "SEC_USER_AGENT", "summitward-research research@example.com"
    )
}

COLS = {
    "stock_t2o": "Stock Trade-Order Volume",
    "etp_t2o": "ETP Trade-Order Volume",
    "stock_c2t": "Stock Cancel-Trade Ratio",
    "etp_c2t": "ETP Cancel-Trade Ratio",
}

PERIODS = [
    ("2012", "20120101", "20121231"),
    ("2019", "20190101", "20191231"),
    ("2025", "20250101", "20251231"),
    ("Q2 2026", "20260401", "20260630"),
]


def fetch() -> None:
    DATA.mkdir(exist_ok=True)
    req = urllib.request.Request(URL, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        blob = r.read()
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        CSV.write_bytes(z.read(MEMBER))


def load() -> list[dict[str, str]]:
    with CSV.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def mean(rows: list[dict[str, str]], col: str) -> float:
    vals = [float(r[col]) for r in rows if r[col].strip()]
    return statistics.fmean(vals)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true")
    args = ap.parse_args()
    if args.refresh or not CSV.exists():
        fetch()
    rows = load()
    print(f"File: {MEMBER}, {rows[0]['Date']} to {rows[-1]['Date']}, {len(rows)} days")
    header = f"{'Period':<9}{'days':>6}{'stock T/O %':>13}{'ETP T/O %':>11}"
    header += f"{'stock C/T':>11}{'ETP C/T':>9}"
    print(header)
    for label, lo, hi in PERIODS:
        sub = [r for r in rows if lo <= r["Date"] <= hi]
        print(
            f"{label:<9}{len(sub):>6}"
            f"{mean(sub, COLS['stock_t2o']):>13.2f}"
            f"{mean(sub, COLS['etp_t2o']):>11.2f}"
            f"{mean(sub, COLS['stock_c2t']):>11.1f}"
            f"{mean(sub, COLS['etp_c2t']):>9.1f}"
        )
    q2 = [r for r in rows if "20260401" <= r["Date"] <= "20260630"]
    t2o = mean(q2, COLS["stock_t2o"])
    print(
        f"\nQ2 2026: of every 100 shares in displayed stock orders added to "
        f"exchange books, about {t2o:.1f} traded; the rest were canceled or "
        f"expired."
    )


if __name__ == "__main__":
    main()
