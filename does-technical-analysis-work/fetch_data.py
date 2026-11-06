"""Download and tidy the inputs for ta_rules.py.

Supports https://summitward.com/learn/does-technical-analysis-work.

Writes, into data/:

- F-F_Research_Data_Factors_daily.csv and F-F_Research_Data_Factors.csv,
  straight from the Kenneth R. French Data Library (unzipped, unmodified).
- shiller_monthly.csv: year, month, S&P Composite price P and annualized
  dividend D from Robert Shiller's ie_data.xls (shillerdata.com). Shiller
  publishes D with a lag of a few months; the last published D is carried
  forward and flagged in the `d_filled` column.

With --gspc it also caches Yahoo Finance ^GSPC daily closes in .cache/ (not
committed; Yahoo data is not redistributable). ta_rules.py uses that file only
for an optional signal cross-check.

Needs pandas and xlrd (for the .xls); --gspc also needs yfinance.
"""

import argparse
import csv
import io
import re
import urllib.request
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
CACHE = HERE / ".cache"
FRENCH = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/{}_CSV.zip"
SHILLER_LANDING = "https://shillerdata.com/"
UA = {"User-Agent": "Mozilla/5.0"}


def get(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=120) as resp:  # noqa: S310
        return resp.read()


def french(name):
    with zipfile.ZipFile(io.BytesIO(get(FRENCH.format(name)))) as z:
        for member in z.namelist():
            (DATA / Path(member).name).write_bytes(z.read(member))
            print(f"wrote data/{Path(member).name}")


def shiller():
    import pandas as pd

    html = get(SHILLER_LANDING).decode("utf-8", "replace")
    m = re.search(r'href="(//img1\.wsimg\.com/[^"]+/ie_data\.xls[^"]*)"', html)
    if not m:
        raise SystemExit("could not find ie_data.xls on shillerdata.com")
    xls = DATA / "ie_data.xls"
    xls.write_bytes(get("https:" + m.group(1)))
    df = pd.read_excel(xls, "Data", skiprows=7).dropna(subset=["Date"])
    df = df[pd.to_numeric(df["Date"], errors="coerce").notna()]
    rows = []
    last_d = None
    for date, p, d in zip(df["Date"], df["P"], df["D"], strict=True):
        year = int(float(date))
        month = round(float(date) * 100) % 100
        if pd.isna(p):
            continue
        filled = 0
        if pd.isna(d):
            d, filled = last_d, 1
        last_d = d
        rows.append((year, month, float(p), float(d), filled))
    with (DATA / "shiller_monthly.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["year", "month", "P", "D", "d_filled"])
        w.writerows(rows)
    xls.unlink()
    print(f"wrote data/shiller_monthly.csv ({len(rows)} months)")


def gspc():
    import yfinance as yf

    CACHE.mkdir(exist_ok=True)
    df = yf.download("^GSPC", start="1927-12-01", auto_adjust=False, progress=False)
    close = df["Close"].squeeze()
    with (CACHE / "gspc_daily.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "close"])
        for ts, v in close.items():
            w.writerow([ts.strftime("%Y%m%d"), f"{float(v):.4f}"])
    print(f"wrote .cache/gspc_daily.csv ({len(close)} days)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gspc", action="store_true")
    args = ap.parse_args()
    DATA.mkdir(exist_ok=True)
    french("F-F_Research_Data_Factors_daily")
    french("F-F_Research_Data_Factors")
    shiller()
    if args.gspc:
        gspc()


if __name__ == "__main__":
    main()
