"""Download the SEC N-PORT holdings and monthly prices that analyze.py reads.

Holdings: for AGG, BND, DFCF and AVIG, the most recent public N-PORT-P filing,
plus the first public filing of DFCF and AVIG and the BND and VCIT filings
closest to (on or before) those first dates, which set the static replica's
weights in analyze.py. Each filing becomes data/holdings_<TICKER>_<period>.csv.gz
with one row per position (gzipped). Raw XML is cached in .cache/ (not committed).

Filing dates: the EDGAR filing date (the day a filing became public) of every
holdings file in data/, written to data/filing_dates.csv. analyze.py starts the
static replica's window only after the filings that set its weights were public.

Prices: daily adjusted closes from Yahoo Finance via yfinance, reduced to
month-end values through END_MONTH, written to data/monthly_prices.csv.
Adjusted close is a market-price total return (dividends reinvested), not NAV.

    SEC_USER_AGENT="Your Name you@example.com" python3 fetch_data.py

Needs yfinance and pandas for the prices step; the holdings step is standard
library only.
"""

import csv
import gzip
import html
import os
import re
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
CACHE = HERE / ".cache"

END_MONTH = "2026-10"  # last complete month when the guide was written

# SEC rejects requests whose User-Agent lacks a contact address.
UA = {
    "User-Agent": os.environ.get(
        "SEC_USER_AGENT", "summitward-research research@example.com"
    )
}

# ticker: (registrant CIK, series ID), from sec.gov/files/company_tickers_mf.json.
# BND is one share class of the Vanguard Total Bond Market Index Fund series,
# which files a single N-PORT for all classes (VBTLX is another class).
SERIES = {
    "AGG": ("1100663", "S000004362"),
    "BND": ("794105", "S000002564"),
    "DFCF": ("1816125", "S000073559"),
    "AVIG": ("1710607", "S000069304"),
    "VCIT": ("1021882", "S000026863"),
}

PRICE_TICKERS = [
    "AGG", "BND", "VBTLX", "AVIG", "DFCF", "DFAPX",  # funds compared
    "VCIT",  # corporate leg of the static replica
    "IEF", "BIL", "SPIB", "IEI", "LQD",  # term and credit proxies
]

FIELDS = [
    "name", "lei", "title", "cusip", "isin", "balance", "units", "val_usd",
    "pct_val", "payoff", "asset_cat", "issuer_cat", "inv_country",
    "maturity", "coupon_kind", "coupon_rate",
]


def get(url: str) -> bytes:
    for attempt in range(4):
        try:
            time.sleep(0.15)  # stay under SEC's 10 requests per second
            req = urllib.request.Request(url, headers=UA)
            return urllib.request.urlopen(req, timeout=120).read()
        except Exception as exc:  # noqa: BLE001 - retry any network error
            if attempt == 3:
                raise
            print(f"  retry {url}: {exc}", file=sys.stderr)
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(url)


def tag(block: str, name: str) -> str:
    m = re.search(rf"<{name}>(.*?)</{name}>", block, re.S)
    return html.unescape(m.group(1).strip()) if m else ""


def attr(block: str, name: str, key: str) -> str:
    m = re.search(rf'<{name}[^>]*\b{key}="([^"]*)"', block)
    return m.group(1).strip() if m else ""


def nport_filings(series: str) -> list[dict]:
    """Every public NPORT-P filing (amendments excluded) for a series."""
    out, start = [], 0
    while True:
        url = (
            "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany"
            f"&CIK={series}&type=NPORT-P&dateb=&owner=include&start={start}"
            "&count=100&output=atom"
        )
        atom = get(url).decode()
        entries = re.findall(r"<entry>(.*?)</entry>", atom, re.S)
        for e in entries:
            if tag(e, "filing-type") == "NPORT-P":
                out.append({"filed": tag(e, "filing-date"), "href": tag(e, "filing-href")})
        if len(entries) < 100:
            break
        start += 100
    return out


def primary_doc(cik: str, href: str) -> tuple[str, str]:
    acc = re.search(r"/(\d{18})/", href).group(1)
    path = CACHE / f"{cik}_{acc}.xml"
    url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/primary_doc.xml"
    if not path.exists():
        CACHE.mkdir(exist_ok=True)
        path.write_bytes(get(url))
    return path.read_text(), url


def period_of(xml: str) -> str:
    return tag(xml, "repPdDate")


def write_holdings(ticker: str, xml: str, url: str) -> Path:
    period = period_of(xml)
    rows = []
    for b in re.findall(r"<invstOrSec>(.*?)</invstOrSec>", xml, re.S):
        debt = tag(b, "debtSec")
        rows.append(
            {
                "name": tag(b, "name"),
                "lei": tag(b, "lei"),
                "title": tag(b, "title"),
                "cusip": tag(b, "cusip"),
                "isin": attr(b, "isin", "value"),
                "balance": tag(b, "balance"),
                "units": tag(b, "units"),
                "val_usd": tag(b, "valUSD"),
                "pct_val": tag(b, "pctVal"),
                "payoff": tag(b, "payoffProfile"),
                "asset_cat": tag(b, "assetCat") or attr(b, "assetConditional", "desc"),
                "issuer_cat": tag(b, "issuerCat") or attr(b, "issuerConditional", "desc"),
                "inv_country": tag(b, "invCountry"),
                "maturity": tag(debt, "maturityDt"),
                "coupon_kind": tag(debt, "couponKind"),
                "coupon_rate": tag(debt, "annualizedRt"),
            }
        )
    path = DATA / f"holdings_{ticker}_{period}.csv.gz"
    with gzip.open(path, "wt", newline="") as f:
        f.write(
            f"# {ticker} N-PORT-P series {tag(xml, 'seriesId')}, period {period}, "
            f"net assets {tag(xml, 'netAssets')}, {url}\n"
        )
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    print(f"{ticker} {period}: {len(rows)} positions -> {path.relative_to(HERE)}")
    return path


def fetch_holdings() -> None:
    DATA.mkdir(exist_ok=True)
    lists = {t: nport_filings(s) for t, (_, s) in SERIES.items()}
    docs: dict[str, list[tuple[str, str, str]]] = {}
    for t, (cik, _) in SERIES.items():
        # Browse-edgar lists newest first.
        docs[t] = []
        for f in lists[t]:
            docs[t].append((f["filed"], f["href"], cik))

    def load(t: str, i: int) -> tuple[str, str]:
        filed, href, cik = docs[t][i]
        return primary_doc(cik, href)

    # Latest filing for the four funds compared.
    for t in ("AGG", "BND", "DFCF", "AVIG"):
        xml, url = load(t, 0)
        write_holdings(t, xml, url)

    # First filing of each systematic fund, and the BND and VCIT filings whose
    # period is closest on or before it (the replica weights use only data
    # public near the start of each fund's window).
    for t in ("DFCF", "AVIG"):
        xml, url = load(t, len(docs[t]) - 1)
        first_period = period_of(xml)
        write_holdings(t, xml, url)
        for leg in ("BND", "VCIT"):
            best = None
            for i in range(len(docs[leg])):
                x, u = load(leg, i)
                p = period_of(x)
                if p <= first_period:
                    best = (x, u)
                    break  # newest first, so the first match is the closest
            if best is None:
                sys.exit(f"no {leg} filing on or before {first_period}")
            write_holdings(leg, *best)


def fetch_filing_dates() -> None:
    """Filing date of each holdings file already in data/ (no holdings re-fetch)."""
    wanted: dict[str, dict[str, str]] = {}
    for path in sorted(DATA.glob("holdings_*.csv.gz")):
        with gzip.open(path, "rt") as f:
            header = f.readline()
        ticker, period = path.name.removesuffix(".csv.gz").split("_")[1:3]
        acc = re.search(r"/(\d{18})/primary_doc", header).group(1)
        wanted.setdefault(ticker, {})[acc] = period
    rows = []
    for ticker, accs in wanted.items():
        for f in nport_filings(SERIES[ticker][1]):
            acc = re.search(r"/(\d{18})/", f["href"]).group(1)
            if acc in accs:
                rows.append({"ticker": ticker, "period": accs[acc], "accession": acc, "filed": f["filed"]})
        missing = set(accs) - {r["accession"] for r in rows if r["ticker"] == ticker}
        if missing:
            sys.exit(f"{ticker}: no filing date for {sorted(missing)}")
    rows.sort(key=lambda r: (r["ticker"], r["period"]))
    with (DATA / "filing_dates.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["ticker", "period", "accession", "filed"])
        w.writeheader()
        w.writerows(rows)
    for r in rows:
        print(f"{r['ticker']} {r['period']}: filed {r['filed']}")


def fetch_prices() -> None:
    import pandas as pd
    import yfinance as yf

    closes = {}
    for t in PRICE_TICKERS:
        df = yf.Ticker(t).history(period="max", auto_adjust=True)
        s = df["Close"]
        s.index = s.index.tz_localize(None)
        closes[t] = s.resample("ME").last()
    out = pd.DataFrame(closes)
    out.index = out.index.strftime("%Y-%m")
    out = out.loc[:END_MONTH]
    out.index.name = "month"
    out.to_csv(DATA / "monthly_prices.csv", float_format="%.6f")
    print(f"prices: {len(out)} months through {out.index[-1]} -> data/monthly_prices.csv")


if __name__ == "__main__":
    steps = sys.argv[1:] or ["holdings", "filing_dates", "prices"]
    if "holdings" in steps:
        fetch_holdings()
    if "filing_dates" in steps:
        fetch_filing_dates()
    if "prices" in steps:
        fetch_prices()
