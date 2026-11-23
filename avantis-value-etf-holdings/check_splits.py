"""Look up stock splits for issuers whose SEC market cap disagrees with the
index file (analyze.py's cap_flags), between the cover-page share date and the
snapshot date, and write data/splits_<date>.json for analyze.py.

Usage:
    python3 analyze.py && python3 check_splits.py && python3 analyze.py
"""

import csv
import json
import re
from pathlib import Path

import pandas as pd
import yfinance as yf

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
DATE = "2026-11-20"


def key(t: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(t).upper())


def main() -> None:
    fund = {r["key"]: r for r in csv.DictReader((DATA / f"fundamentals_{DATE}.csv").open())}
    flags = json.loads((HERE / "output" / "holdings_summary.json").read_text())["cap_flags"]
    path = DATA / f"splits_{DATE}.json"
    out = json.loads(path.read_text()) if path.exists() else {}
    for f in flags:
        k = key(f["ticker"])
        r = fund.get(k)
        if not r or not r.get("shares_end") or k in out:
            continue
        sp = yf.Ticker(r["ticker"].replace(".", "-")).splits
        if sp.empty:
            continue
        idx = sp.index.tz_localize(None) if sp.index.tz is not None else sp.index
        sp = pd.Series(sp.values, index=idx)
        after = sp[(sp.index > pd.Timestamp(r["shares_end"])) & (sp.index <= pd.Timestamp(DATE))]
        if len(after):
            factor = float(after.prod())
            out[k] = factor
            print(f"{r['ticker']}: {factor} since {r['shares_end']} (ratio was {f['ratio']})")
    path.write_text(json.dumps(out, indent=1, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
