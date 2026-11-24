"""Trailing operating cash flow for every U.S. stock in AVLV and the Russell
1000 (IWB, which contains the Russell 1000 Value), so the guide can compare a
company's cash profitability with the fund, the value index and the market on
the same unadjusted basis. AVLV's prospectus names
"adjusted cash from operations to book value" as its profitability measure;
Avantis does not publish its adjustments, so these filed figures approximate it.

Trailing twelve months = latest 10-K year + latest year-to-date 10-Q - the same
period a year earlier (fetch_fundamentals.ttm). Writes data/cfo_<date>.csv.

Usage:
    SEC_USER_AGENT="..." python3 fetch_cfo.py
"""

import csv
import json
import re
from concurrent.futures import ThreadPoolExecutor

import fetch_fundamentals as ff

EXTRA = ["LYFT", "M", "CROX", "GATX", "MATX"]  # AVUV names the guide discusses


def key(t: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", t.upper())


def tickers() -> list[str]:
    out = set(EXTRA)
    for r in csv.DictReader((ff.DATA / f"avantis_AVLV_{ff.DATE}.csv").open()):
        if r["securityType"] == "COMMON STOCK":
            out.add(r["ticker"])
    for etf in ("IWD", "IWB"):
        lines = (ff.DATA / f"ishares_{etf}_{ff.DATE}.csv").read_text().splitlines()
        head = next(i for i, ln in enumerate(lines) if ln.startswith("Ticker,"))
        for r in csv.DictReader(lines[head:]):
            if r.get("Asset Class") == "Equity":
                out.add(r["Ticker"])
    return sorted(out)


def main() -> None:
    ff.CACHE.mkdir(parents=True, exist_ok=True)
    fund = {r["key"]: r for r in csv.DictReader((ff.DATA / f"fundamentals_{ff.DATE}.csv").open())}

    def one(t: str) -> dict:
        r = fund.get(key(t))
        if not r or not r["cik"]:
            return {"key": key(t), "ticker": t, "cik": "", "cfo_ttm": "", "cfo_end": ""}
        got = ff.ttm(
            ff.concept(int(r["cik"]), "us-gaap", "NetCashProvidedByUsedInOperatingActivities")
        )
        return {
            "key": key(t), "ticker": t, "cik": r["cik"],
            "cfo_ttm": got[0] if got else "", "cfo_end": got[1] if got else "",
        }  # fmt: skip

    with ThreadPoolExecutor(max_workers=12) as pool:
        rows = list(pool.map(one, tickers()))
    out = ff.DATA / f"cfo_{ff.DATE}.csv"
    with out.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {out.name}: {len(rows)} rows, {sum(1 for r in rows if r['cfo_ttm'])} with CFO")


if __name__ == "__main__":
    main()
