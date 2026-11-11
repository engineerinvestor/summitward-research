"""Download the holdings files that analyze.py reads.

1. Avantis daily holdings for AVUC, AVUS, AVNC, AVTM and the Avantis ETFs that
   AVTM holds (AVDE, AVEM, AVUQ). Each fund page embeds the full daily holdings
   list (the same file Avantis publishes "on each business day, before
   commencement of trading") in its page data; this script reads it from the
   page HTML and writes data/<TICKER>_<YYYY-MM-DD>.csv.
2. iShares "latest-holdings.csv" files for the iShares ETFs in AVUC's
   contributed sleeve, plus IWV (Russell 3000) as the benchmark proxy, written
   to data/ishares_<TICKER>.csv. iShares serves only the latest file.

3. State Street daily holdings workbooks for XLY and SPY.

Usage:
    python3 fetch_data.py                        # everything
    python3 fetch_data.py --avantis --ishares    # a subset
"""

import csv
import re
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

DATA = Path(__file__).resolve().parent / "data"
UA = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    )
}
AVANTIS = "https://www.avantisinvestors.com/avantis-investments/"
AVANTIS_PAGES = {
    "AVUC": "avantis-us-core-equity-etf",
    "AVUS": "avantis-us-equity-etf",
    "AVNC": "avantis-all-international-core-equity-etf",
    "AVTM": "avantis-total-equity-markets-etf",
    "AVDE": "avantis-international-equity-etf",
    "AVEM": "avantis-emerging-markets-equity-etf",
    "AVUQ": "avantis-us-quality-etf",
}
# iShares product pages (id/slug) for the iShares ETFs in AVUC's contributed sleeve.
ISHARES = {
    "IWF": "239706/ishares-russell-1000-growth-etf",
    "IWD": "239708/ishares-russell-1000-value-etf",
    "IWB": "239707/ishares-russell-1000-etf",
    "IVV": "239726/ishares-core-s-p-500-etf",
    "OEF": "239723/ishares-sp-100-etf",
    "IYW": "239522/ishares-us-technology-etf",
    "IWO": "239709/ishares-russell-2000-growth-etf",
    "SOXX": "239705/ishares-phlx-semiconductor-etf",
    "IJH": "239763/ishares-core-sp-midcap-etf",
    "IWV": "239714/ishares-russell-3000-etf",  # Russell 3000 benchmark proxy
}
# State Street daily holdings workbooks.
SSGA = ["XLY", "SPY"]
FIELDS = [
    "name", "ticker", "securityType", "cusip", "isin", "sedol", "shareQuantity",
    "contractCount", "baseMarketValue", "weight", "coupon", "maturityDate",
    "sector", "country",
]  # fmt: skip


def get(url: str) -> str:
    req = urllib.request.Request(url, headers=UA)
    return urllib.request.urlopen(req, timeout=60).read().decode("utf-8-sig")


def parse_avantis(html: str) -> tuple[str, list[dict]]:
    as_of = re.search(r'etfHoldingsAsOfDate:"([0-9/]+)"', html).group(1)
    start = html.index("etfHoldings:[{") + len("etfHoldings:[")
    end = html.index("}]", start) + 1
    block = html[start:end]
    rows = []
    for obj in re.finditer(r"\{(.*?)\}(?=,\{|$)", block, flags=re.S):
        row = {}
        for key in FIELDS:
            m = re.search(rf'(?:^|,){key}:("((?:[^"\\]|\\.)*)"|[^,]*)', obj.group(1))
            if m is None:
                raise ValueError(f"missing {key} in {obj.group(1)[:120]}")
            row[key] = m.group(2) if m.group(2) is not None else m.group(1)
        rows.append(row)
    return datetime.strptime(as_of, "%m/%d/%Y").strftime("%Y-%m-%d"), rows


def fetch_avantis() -> None:
    for ticker, slug in AVANTIS_PAGES.items():
        as_of, rows = parse_avantis(get(AVANTIS + slug + "/"))
        bad = [
            r
            for r in rows
            if not r["baseMarketValue"].replace(".", "").lstrip("-").isdigit()
        ]
        out = DATA / f"{ticker}_{as_of}.csv"
        with out.open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS)
            w.writeheader()
            w.writerows(rows)
        print(
            f"{ticker}: {len(rows)} lines as of {as_of} -> data/{out.name}"
            + (f" ({len(bad)} non-numeric values)" if bad else "")
        )


def fetch_ishares() -> None:
    for ticker, path in ISHARES.items():
        url = f"https://www.ishares.com/us/products/{path}/latest-holdings.csv"
        text = get(url)
        first = text.splitlines()[:3]
        (DATA / f"ishares_{ticker}.csv").write_text(text, encoding="utf-8")
        print(f"{ticker}: {len(text.splitlines())} lines; header {first[:2]}")


def fetch_ssga() -> None:
    base = (
        "https://www.ssga.com/us/en/intermediary/library-content/products/"
        "fund-data/etfs/us/holdings-daily-us-en-{t}.xlsx"
    )
    for ticker in SSGA:
        req = urllib.request.Request(base.format(t=ticker.lower()), headers=UA)
        blob = urllib.request.urlopen(req, timeout=60).read()
        (DATA / f"ssga_{ticker}.xlsx").write_bytes(blob)
        print(f"{ticker}: {len(blob):,} bytes")


if __name__ == "__main__":
    DATA.mkdir(exist_ok=True)
    only = [a for a in sys.argv[1:] if a.startswith("--")]
    if not only or "--avantis" in only:
        fetch_avantis()
    if not only or "--ishares" in only:
        fetch_ishares()
    if not only or "--ssga" in only:
        fetch_ssga()
