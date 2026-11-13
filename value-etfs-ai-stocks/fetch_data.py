"""Download the holdings files and factor data that analyze.py reads.

1. iShares "latest-holdings.csv" for IWD (Russell 1000 Value), IWF (Russell
   1000 Growth), IVE (S&P 500 Value), VLUE (MSCI USA Enhanced Value), SOXX
   (semiconductors) and IWV (Russell 3000, used only as a ticker-to-sector map).
   iShares serves only the latest file.
2. Avantis daily holdings for AVLV, AVUV and AVGV, and for the five other
   Avantis ETFs AVGV holds (AVMV, AVIV, AVDV, AVES), read from the data embedded
   in each fund page.
3. Dimensional daily holdings for DFLV and DFSV on a chosen date, and each
   fund's characteristics (sector weights, aggregate price-to-book, weighted
   average profitability) as of its latest month end.
4. Vanguard holdings for VTV and VTI from the advisor-site API, which posts
   month-end files about six weeks after the month ends.
5. Ken French monthly factors: the five-factor file, momentum, and the
   three-factor file (which starts in 1926).

Usage:
    python3 fetch_data.py                  # everything, Dimensional for 2026-11-12
    python3 fetch_data.py --date 20261112  # Dimensional date
    python3 fetch_data.py --ishares --avantis
"""

import csv
import json
import re
import sys
import urllib.request
import zipfile
from datetime import datetime
from io import BytesIO
from pathlib import Path

DATA = Path(__file__).resolve().parent / "data"
UA = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/128.0 Safari/537.36"
    )
}
ISHARES = {
    "IWD": "239708/ishares-russell-1000-value-etf",
    "IWF": "239706/ishares-russell-1000-growth-etf",
    "IVE": "239728/ishares-sp-500-value-etf",
    "VLUE": "251616/ishares-msci-usa-value-factor-etf",
    "SOXX": "239705/ishares-phlx-semiconductor-etf",
    "IWV": "239714/ishares-russell-3000-etf",
}
AVANTIS = "https://www.avantisinvestors.com/avantis-investments/en-us/"
AVANTIS_PAGES = {
    "AVLV": "avantis-us-large-cap-value-etf",
    "AVUV": "avantis-us-small-cap-value-etf",
    "AVGV": "avantis-all-equity-markets-value-etf",
    "AVMV": "avantis-us-mid-cap-value-etf",
    "AVIV": "avantis-international-large-cap-value-etf",
    "AVDV": "avantis-international-small-cap-value-etf",
    "AVES": "avantis-emerging-markets-value-etf",
}
AVANTIS_FIELDS = [
    "name", "ticker", "securityType", "cusip", "isin", "sedol", "shareQuantity",
    "contractCount", "baseMarketValue", "weight", "coupon", "maturityDate",
    "sector", "country",
]  # fmt: skip
DIMENSIONAL = {"DFLV": "1422", "DFSV": "1526"}
VANGUARD = {"VTV": "0966", "VTI": "0970"}
FRENCH = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/{}_CSV.zip"
FRENCH_FILES = [
    "F-F_Research_Data_5_Factors_2x3",
    "F-F_Momentum_Factor",
    "F-F_Research_Data_Factors",
]


def get(url: str, data: bytes | None = None, headers: dict | None = None) -> bytes:
    req = urllib.request.Request(url, data=data, headers={**UA, **(headers or {})})
    return urllib.request.urlopen(req, timeout=90).read()


def fetch_ishares() -> None:
    for ticker, path in ISHARES.items():
        url = f"https://www.ishares.com/us/products/{path}/latest-holdings.csv"
        text = get(url).decode("utf-8-sig")
        (DATA / f"ishares_{ticker}.csv").write_text(text, encoding="utf-8")
        print(f"{ticker}: {len(text.splitlines())} lines; {text.splitlines()[1]}")


def parse_avantis(html: str) -> tuple[str, list[dict]]:
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
    return datetime.strptime(as_of, "%m/%d/%Y").strftime("%Y-%m-%d"), rows


def fetch_avantis() -> None:
    for ticker, slug in AVANTIS_PAGES.items():
        as_of, rows = parse_avantis(get(AVANTIS + slug + "/").decode("utf-8"))
        out = DATA / f"avantis_{ticker}_{as_of}.csv"
        with out.open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=AVANTIS_FIELDS)
            w.writeheader()
            w.writerows(rows)
        print(f"{ticker}: {len(rows)} lines as of {as_of}")


def fetch_dimensional(date: str) -> None:
    for ticker, number in DIMENSIONAL.items():
        blob = get(f"https://tools-blob.dimensional.com/etf/{date}/{ticker}.csv")
        (DATA / f"dimensional_{ticker}_{date}.csv").write_bytes(blob)
        detail = get(
            "https://etf.dimensional.com/public/v2/fundcenter/funddetail",
            data=json.dumps({"portfolioNumber": number}).encode(),
            headers={"x-selected-country": "US", "Content-Type": "application/json"},
        )
        d = json.loads(detail)["data"]
        as_of = d["asOfDate"]["value"]
        (DATA / f"dimensional_{ticker}_detail_{as_of}.json").write_bytes(detail)
        print(f"{ticker}: holdings {date}, characteristics {as_of}")


def fetch_vanguard() -> None:
    for ticker, fund_id in VANGUARD.items():
        url = (
            "https://advisors.vanguard.com/investments/products/api/funds/"
            f"{fund_id}/holdings/latest"
        )
        payload = json.loads(get(url))
        as_of = payload["latestEffectiveDate"]
        (DATA / f"vanguard_{ticker}_{as_of}.json").write_text(json.dumps(payload))
        n = len(payload[as_of]["equity"])
        print(f"{ticker}: {n} equity lines as of {as_of}")


def fetch_french() -> None:
    for name in FRENCH_FILES:
        z = zipfile.ZipFile(BytesIO(get(FRENCH.format(name))))
        text = z.read(z.namelist()[0]).decode("latin-1")
        (DATA / f"{name}.csv").write_text(text, encoding="latin-1")
        print(f"{name}: {text.splitlines()[:4][-1][:60]}")


if __name__ == "__main__":
    DATA.mkdir(exist_ok=True)
    args = sys.argv[1:]
    date = args[args.index("--date") + 1] if "--date" in args else "20261112"
    only = [a for a in args if a.startswith("--") and a != "--date"]
    if not only or "--ishares" in only:
        fetch_ishares()
    if not only or "--avantis" in only:
        fetch_avantis()
    if not only or "--dimensional" in only:
        fetch_dimensional(date)
    if not only or "--vanguard" in only:
        fetch_vanguard()
    if not only or "--french" in only:
        fetch_french()
