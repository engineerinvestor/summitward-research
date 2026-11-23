"""Download the same-date holdings files that analyze.py reads.

1. Avantis daily holdings for AVLV, AVUV, AVDV and AVGV, and for the three other
   Avantis ETFs AVGV holds (AVIV, AVES, AVMV), read from the data embedded in
   each fund page. The pages also carry each fund's month-end characteristics
   (holdings count, P/E, P/B, weighted average market cap), saved alongside.
2. iShares "latest-holdings.csv" for the Russell 1000 (IWB), Russell 1000 Value
   (IWD) and Growth (IWF), Russell 2000 (IWM), Russell 2000 Value (IWN) and
   Growth (IWO). iShares serves only the latest file.

Every file states its own as-of date. The script refuses to finish if the
dates disagree, because active weights computed across dates mix real
differences with price moves.

Usage:
    python3 fetch_data.py
"""

import csv
import json
import re
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

DATA = Path(__file__).resolve().parent / "data"
UA = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/128.0 Safari/537.36"
    )
}
ISHARES = {
    "IWB": "239707/ishares-russell-1000-etf",
    "IWD": "239708/ishares-russell-1000-value-etf",
    "IWF": "239706/ishares-russell-1000-growth-etf",
    "IWM": "239710/ishares-russell-2000-etf",
    "IWN": "239712/ishares-russell-2000-value-etf",
    "IWO": "239709/ishares-russell-2000-growth-etf",
}
AVANTIS = "https://www.avantisinvestors.com/avantis-investments/en-us/"
AVANTIS_PAGES = {
    "AVLV": "avantis-us-large-cap-value-etf",
    "AVUV": "avantis-us-small-cap-value-etf",
    "AVDV": "avantis-international-small-cap-value-etf",
    "AVGV": "avantis-all-equity-markets-value-etf",
    "AVIV": "avantis-international-large-cap-value-etf",
    "AVES": "avantis-emerging-markets-value-etf",
    "AVMV": "avantis-us-mid-cap-value-etf",
}
AVANTIS_FIELDS = [
    "name", "ticker", "securityType", "cusip", "isin", "sedol", "shareQuantity",
    "contractCount", "baseMarketValue", "weight", "coupon", "maturityDate",
    "sector", "country",
]  # fmt: skip
CHARACTERISTICS = [
    "numberOfHoldings",
    "priceEarningsRatio",
    "priceBookRatio",
    "weightedAverageMarketCap",
]


def get(url: str) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    return urllib.request.urlopen(req, timeout=90).read()


def ishares_date(text: str) -> str:
    m = re.search(r'Fund Holdings as of,"([A-Za-z]{3} \d{1,2}, \d{4})"', text)
    return datetime.strptime(m.group(1), "%b %d, %Y").strftime("%Y-%m-%d")


def fetch_ishares() -> dict[str, str]:
    dates = {}
    for ticker, path in ISHARES.items():
        url = f"https://www.ishares.com/us/products/{path}/latest-holdings.csv"
        text = get(url).decode("utf-8-sig")
        if not text.startswith("iShares"):
            raise ValueError(f"{ticker}: not a holdings file ({text[:60]!r})")
        dates[ticker] = ishares_date(text)
        (DATA / f"ishares_{ticker}_{dates[ticker]}.csv").write_text(
            text, encoding="utf-8"
        )
        print(f"{ticker}: {len(text.splitlines())} lines as of {dates[ticker]}")
    return dates


def parse_avantis(html: str) -> tuple[str, list[dict], dict]:
    as_of = re.search(r'etfHoldingsAsOfDate:"([0-9/]+)"', html).group(1)
    start = html.index("etfHoldings:[{") + len("etfHoldings:[")
    end = html.index("}]", start) + 1
    rows = []
    for obj in re.finditer(r"\{(.*?)\}(?=,\{|$)", html[start:end], flags=re.S):
        row = {}
        for key in AVANTIS_FIELDS:
            m = re.search(rf'(?:^|,){key}:("((?:[^"\\]|\\.)*)"|[^,]*)', obj.group(1))
            if m is None:
                raise ValueError(f"missing {key} in {obj.group(1)[:120]}")
            row[key] = m.group(2) if m.group(2) is not None else m.group(1)
        rows.append(row)
    chars = {}
    for key in CHARACTERISTICS:
        m = re.search(rf'{key}:"?([0-9.]+)"?', html)
        chars[key] = m.group(1) if m else None
    m = re.search(r'characteristicsAsOfDate:"([0-9/]+)"', html)
    chars["asOf"] = m.group(1) if m else None
    day = datetime.strptime(as_of, "%m/%d/%Y").strftime("%Y-%m-%d")
    return day, rows, chars


def fetch_avantis() -> dict[str, str]:
    dates, chars_all = {}, {}
    for ticker, slug in AVANTIS_PAGES.items():
        as_of, rows, chars = parse_avantis(get(AVANTIS + slug + "/").decode("utf-8"))
        dates[ticker] = as_of
        chars_all[ticker] = chars
        out = DATA / f"avantis_{ticker}_{as_of}.csv"
        with out.open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=AVANTIS_FIELDS)
            w.writeheader()
            w.writerows(rows)
        print(f"{ticker}: {len(rows)} lines as of {as_of}; {chars}")
    day = sorted(set(dates.values()))[-1]
    (DATA / f"avantis_page_characteristics_{day}.json").write_text(
        json.dumps(chars_all, indent=1) + "\n"
    )
    return dates


if __name__ == "__main__":
    DATA.mkdir(exist_ok=True)
    dates = {**fetch_avantis(), **fetch_ishares()}
    if len(set(dates.values())) != 1:
        sys.exit(f"as-of dates disagree: {dates}")
    print(f"all files as of {next(iter(dates.values()))}")
