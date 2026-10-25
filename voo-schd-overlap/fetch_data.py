"""Download the inputs that analyze.py reads.

1. data/schd_holdings_2026-10-13.csv is committed as captured: Schwab's full
   SCHD holdings page (schwabassetmanagement.com/allholdings/SCHD, "As of
   10/13/26"), copied by hand because the page refuses scripted requests.
2. data/ijh_latest.csv: iShares IJH (S&P MidCap 400) holdings, to confirm it
   shares no stocks with the S&P 500.
   data/ivv_latest.csv: iShares IVV holdings (S&P 500), used as the VOO proxy.
   iShares serves only the latest file, so analyze.py reprices it to the
   SCHD date using each stock's share quantity and its 2026-10-13 close.
3. data/constituent_closes.csv: unadjusted closes of every IVV stock on the
   SCHD holdings date and the IVV file date (Yahoo Finance via yfinance).
4. data/fund_prices_daily.csv: adjusted daily closes for the funds compared.
5. data/F-F_Research_Data_5_Factors_2x3.csv: Kenneth French five-factor file.

Usage:
    python3 fetch_data.py
"""

import csv
import io
import urllib.request
import zipfile
from pathlib import Path

import pandas as pd
import yfinance as yf

DATA = Path(__file__).resolve().parent / "data"
UA = {"User-Agent": "Mozilla/5.0 (summitward-research)"}

IJH_URL = (
    "https://www.ishares.com/us/products/239763/ishares-core-sp-midcap-etf/"
    "latest-holdings.csv"
)
IVV_URL = (
    "https://www.ishares.com/us/products/239726/ishares-core-s-p-500-etf/"
    "latest-holdings.csv"
)
FRENCH_URL = (
    "https://mba.tuck.dartmouth.edu/pages/faculty/Ken.French/ftp/"
    "F-F_Research_Data_5_Factors_2x3_CSV.zip"
)
FUNDS = ["VOO", "SCHD", "IVV", "RSP", "IJH", "VXUS", "BND"]
START, END = "2011-10-01", "2026-10-24"  # END is exclusive in yfinance
SCHD_DATE, IVV_DATE = "2026-10-13", "2026-10-22"


def get(url: str) -> bytes:
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA)).read()


def ivv_tickers() -> list[str]:
    text = (DATA / "ivv_latest.csv").read_text(encoding="utf-8-sig")
    lines = text.splitlines()
    head = next(i for i, ln in enumerate(lines) if ln.startswith("Ticker,"))
    rows = csv.DictReader(lines[head:])
    # HOLX remains as an unlisted $0.01 stub after Hologic went private.
    return [
        r["Ticker"]
        for r in rows
        if r.get("Asset Class") == "Equity" and r["Exchange"] != "NO MARKET (E.G. UNLISTED)"
    ]


def yahoo_symbol(t: str) -> str:
    # iShares writes share classes with a space ("BRK B"); Yahoo uses a dash.
    return t.replace(" ", "-").replace(".", "-")


def fetch_constituent_closes() -> None:
    tickers = ivv_tickers()
    syms = [yahoo_symbol(t) for t in tickers]
    px = yf.download(
        syms,
        start=SCHD_DATE,
        end="2026-10-23",
        auto_adjust=False,
        progress=False,
        threads=True,
    )["Close"]
    px = px.loc[[SCHD_DATE, IVV_DATE]].T
    px.index = [tickers[syms.index(s)] for s in px.index]
    px.columns = ["close_schd_date", "close_ivv_date"]
    px.index.name = "ticker"
    px.to_csv(DATA / "constituent_closes.csv")
    missing = px[px.isna().any(axis=1)]
    print(f"constituent closes: {len(px)} tickers, {len(missing)} missing")
    if len(missing):
        print(missing)


def fetch_fund_prices() -> None:
    px = yf.download(FUNDS, start=START, end=END, auto_adjust=True, progress=False)
    px["Close"][FUNDS].to_csv(DATA / "fund_prices_daily.csv")
    print("fund prices:", px.index[0].date(), "to", px.index[-1].date())


def fetch_french() -> None:
    z = zipfile.ZipFile(io.BytesIO(get(FRENCH_URL)))
    text = z.read(z.namelist()[0]).decode("latin-1")
    (DATA / "F-F_Research_Data_5_Factors_2x3.csv").write_text(text, encoding="latin-1")
    print("French file:", text.splitlines()[0][:80])


if __name__ == "__main__":
    DATA.mkdir(exist_ok=True)
    if not (DATA / "ivv_latest.csv").exists():
        (DATA / "ivv_latest.csv").write_bytes(get(IVV_URL))
    if not (DATA / "ijh_latest.csv").exists():
        (DATA / "ijh_latest.csv").write_bytes(get(IJH_URL))
    fetch_constituent_closes()
    fetch_fund_prices()
    fetch_french()
