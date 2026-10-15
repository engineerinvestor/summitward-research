"""Download the inputs that analyze.py reads.

1. Equity holdings of VTSAX, FZROX and FSKAX from each fund's most recent
   public SEC Form N-PORT-P filing, written to data/holdings_<TICKER>.csv.
2. Month-end adjusted closes for the three funds, VTI and three ZERO-fund
   comparison pairs from Yahoo Finance,
   written to data/monthly_prices.csv. Needs yfinance.

The committed CSVs already hold this output, so analyze.py runs without
re-fetching. Usage:

    python3 fetch_data.py            # both
    python3 fetch_data.py --holdings # SEC only (stdlib)
"""

import csv
import os
import re
import sys
import urllib.request
from pathlib import Path

DATA = Path(__file__).resolve().parent / "data"

# SEC rejects requests whose User-Agent lacks a contact address. Set
# SEC_USER_AGENT="Your Name you@example.com" to identify yourself.
UA = {"User-Agent": os.environ.get("SEC_USER_AGENT", "summitward-research research@example.com")}

# Accession folders of the N-PORT-P filings used (period end in comments).
NPORT = {
    "FZROX": "819118/000003540226006318",  # Fidelity ZERO Total Market, 2026-07-31
    "FSKAX": "819118/000003540226004751",  # Fidelity Total Market, 2026-05-31
    "VTSAX": "36405/000003640526000480",  # Vanguard Total Stock Market, 2026-06-30
}

# The three total-market funds, VTI, and the other ZERO funds with the
# counterparts the ZERO-funds guide compares them with.
TICKERS = ["VTSAX", "FZROX", "FSKAX", "VTI", "FZILX", "VTIAX", "FNILX", "FXAIX"]
START, END = "2018-07-31", "2026-10-01"


def tag(block: str, name: str) -> str:
    m = re.search(rf"<{name}>(.*?)</{name}>", block, re.S)
    return m.group(1).strip() if m else ""


def fetch_holdings() -> None:
    for ticker, folder in NPORT.items():
        url = f"https://www.sec.gov/Archives/edgar/data/{folder}/primary_doc.xml"
        xml = urllib.request.urlopen(urllib.request.Request(url, headers=UA)).read()
        xml = xml.decode()
        period = tag(xml, "repPdDate")
        series = tag(xml, "seriesId")
        rows = []
        for block in re.findall(r"<invstOrSec>(.*?)</invstOrSec>", xml, re.S):
            isin = re.search(r'<isin value="(.*?)"', block)
            rows.append(
                {
                    "name": tag(block, "name"),
                    "title": tag(block, "title"),
                    "cusip": tag(block, "cusip"),
                    "isin": isin.group(1) if isin else "",
                    "asset_cat": tag(block, "assetCat"),
                    "value_usd": tag(block, "valUSD"),
                }
            )
        out = DATA / f"holdings_{ticker}.csv"
        with out.open("w", newline="") as f:
            f.write(f"# {ticker} N-PORT-P series {series}, period {period}, {url}\n")
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
        print(f"{ticker}: {len(rows)} positions, period {period} -> data/{out.name}")


def fetch_prices() -> None:
    import yfinance as yf

    px = yf.download(TICKERS, start=START, end=END, auto_adjust=True, progress=False)
    # Keep every month end where the three total-market funds all have a
    # price; a later-starting ticker is written blank until its first price.
    month_end = px["Close"].resample("ME").last().dropna(subset=["VTSAX", "FZROX", "FSKAX"])
    out = DATA / "monthly_prices.csv"
    with out.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", *TICKERS])
        for dt, row in month_end.iterrows():
            cells = ("" if row[t] != row[t] else f"{row[t]:.6f}" for t in TICKERS)
            w.writerow([dt.date().isoformat(), *cells])
    print(f"{len(month_end)} month-ends -> data/{out.name}")


if __name__ == "__main__":
    DATA.mkdir(exist_ok=True)
    fetch_holdings()
    if "--holdings" not in sys.argv:
        fetch_prices()
