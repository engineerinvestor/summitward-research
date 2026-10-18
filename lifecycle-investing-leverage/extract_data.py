"""Build the monthly real-return series behind the lifecycle-leverage guide.

Writes ``data/lifecycle_leverage_monthly.json``:
one row per month from January 1871, each holding that month's real return
(month t to t+1) on four assets.

* **Stocks**: Robert Shiller's real total-return price (ie_data.xls column
  "Real Total Return Price"), S&P Composite with dividends reinvested. This
  is the same series Ayres and Nalebuff's 2010 workbook uses.
* **Bonds**: Shiller's real total bond return index (10-year Treasury).
* **Short rate**: NBER Macrohistory call money rates (series m13001, the
  broker call loan rate Ayres and Nalebuff use) through June 1926, then the
  one-month T-bill return from the Ken French data library (daily RF,
  compounded within each month) from July 1926.
* **Call money** where NBER has it (to November 1970), so the backtest can
  measure how far call loans ran above bills.

Nominal rates are deflated by Shiller's CPI over the same month (CPI t to
t+1), matching the stock and bond series' timing.

Usage:
    python extract_data.py [ie_data.xls] [m13001.dat]

With no arguments the script downloads both files. Shiller's file lives on
shillerdata.com behind a URL that changes when he republishes, so the link is
scraped from the landing page rather than hardcoded.
"""

from __future__ import annotations

import json
import re
import sys
import tempfile
import urllib.request
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
FRENCH_DAILY = HERE / "data" / "us_market_daily.json"
OUTPUTS = [HERE / "data" / "lifecycle_leverage_monthly.json"]
SHILLER_LANDING = "https://shillerdata.com/"
NBER_CALL_MONEY = "https://data.nber.org/databases/macrohistory/rectdata/13/m13001.dat"
UA = {"User-Agent": "Mozilla/5.0"}
FIRST = (1871, 1)
SPLICE = (1926, 7)  # first month of French RF


def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=120) as resp:  # noqa: S310
        return resp.read()


def download_shiller(dest: Path) -> tuple[Path, str]:
    html = _get(SHILLER_LANDING).decode("utf-8", "replace")
    m = re.search(r'(//img1\.wsimg\.com[^"\s]+ie_data\.xls[^"\s]*)', html)
    if not m:
        raise RuntimeError("ie_data.xls link not found on shillerdata.com")
    url = "https:" + m.group(1)
    dest.write_bytes(_get(url))
    return dest, url


def load_shiller(path: Path) -> pd.DataFrame:
    df = pd.read_excel(path, "Data", skiprows=7).dropna(subset=["Date"])
    df = df[pd.to_numeric(df["Date"], errors="coerce").notna()].copy()
    df["year"] = df["Date"].astype(float).astype(int)
    df["month"] = (df["Date"].astype(float).round(2) * 100).round().astype(int) % 100
    # Shiller's sheet repeats column titles; pandas suffixes the duplicates.
    # "Price.1" is the real total-return price, "Returns.1" the real total
    # bond return index (both checked against their nominal counterparts).
    out = pd.DataFrame(
        {
            "year": df["year"].values,
            "month": df["month"].values,
            "cpi": pd.to_numeric(df["CPI"], errors="coerce").values,
            "tr_real": pd.to_numeric(df["Price.1"], errors="coerce").values,
            "bond_real_idx": pd.to_numeric(df["Returns.1"], errors="coerce").values,
        }
    )
    return out.reset_index(drop=True)


def load_call_money(path: Path) -> dict[tuple[int, int], float]:
    rates = {}
    for line in path.read_text().splitlines():
        parts = line.split()
        if len(parts) < 3 or parts[2] == ".":
            continue
        rates[(int(parts[0]), int(parts[1]))] = float(parts[2]) / 100.0
    return rates


def load_french_monthly() -> dict[tuple[int, int], float]:
    raw = json.loads(FRENCH_DAILY.read_text())
    dates = np.asarray(raw["dates"])
    rf = np.asarray(raw["rf_bp"], dtype=float) / 10000.0
    ym = dates // 100
    out = {}
    for key in np.unique(ym):
        mask = ym == key
        out[(int(key // 100), int(key % 100))] = float(np.prod(1.0 + rf[mask]) - 1.0)
    last = int(dates[-1])
    # Drop a final partial month.
    if last % 100 < 28:
        out.pop((last // 10000, (last // 100) % 100), None)
    return out


def build(shiller_path: Path, nber_path: Path, shiller_url: str) -> dict:
    sh = load_shiller(shiller_path)
    call = load_call_money(nber_path)
    bills = load_french_monthly()

    rows = []
    for i in range(len(sh) - 1):
        y, m = int(sh.at[i, "year"]), int(sh.at[i, "month"])
        if (y, m) < FIRST:
            continue
        nxt = sh.iloc[i + 1]
        cur = sh.iloc[i]
        if any(
            pd.isna(v)
            for v in (cur.cpi, nxt.cpi, cur.tr_real, nxt.tr_real)
            + (cur.bond_real_idx, nxt.bond_real_idx)
        ):
            break
        infl = nxt.cpi / cur.cpi
        if (y, m) < SPLICE:
            short_nom = (1.0 + call[(y, m)]) ** (1 / 12) - 1.0
        elif (y, m) in bills:
            short_nom = bills[(y, m)]
        else:
            break
        cm = call.get((y, m))
        rows.append(
            {
                "ym": y * 100 + m,
                "stock": nxt.tr_real / cur.tr_real - 1.0,
                "bond": nxt.bond_real_idx / cur.bond_real_idx - 1.0,
                "short": (1.0 + short_nom) / infl - 1.0,
                "call": None if cm is None else (1.0 + cm) ** (1 / 12) / infl - 1.0,
                "infl": infl - 1.0,
            }
        )

    def col(key, digits=7):
        return [None if r[key] is None else round(r[key], digits) for r in rows]

    return {
        "_metadata": {
            "description": (
                "Monthly real returns (month t to t+1), deflated by Shiller CPI "
                "over the same month."
            ),
            "first_month": rows[0]["ym"],
            "last_month": rows[-1]["ym"],
            "months": len(rows),
            "sources": {
                "stock": (
                    "Shiller ie_data.xls, Real Total Return Price (S&P Composite, "
                    "dividends reinvested)"
                ),
                "bond": "Shiller ie_data.xls, Real Total Bond Returns (10-year)",
                "short": (
                    "NBER Macrohistory m13001 call money rate to 1926-06; Ken French "
                    "one-month T-bill (RF) from 1926-07"
                ),
                "call": "NBER Macrohistory m13001 call money rate (to 1970-11)",
            },
            "urls": {
                "shiller": shiller_url,
                "shiller_landing": SHILLER_LANDING,
                "nber": NBER_CALL_MONEY,
                "french": (
                    "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/"
                    "data_library.html"
                ),
            },
            "generated": date.today().isoformat(),
            "script": "extract_data.py",
        },
        "ym": [r["ym"] for r in rows],
        "stock": col("stock"),
        "bond": col("bond"),
        "short": col("short"),
        "call": col("call"),
        "infl": col("infl"),
    }


def main(argv: list[str]) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        if len(argv) > 1:
            shiller_path, shiller_url = Path(argv[1]), "local file"
        else:
            shiller_path, shiller_url = download_shiller(tmpdir / "ie_data.xls")
        if len(argv) > 2:
            nber_path = Path(argv[2])
        else:
            nber_path = tmpdir / "m13001.dat"
            nber_path.write_bytes(_get(NBER_CALL_MONEY))
        payload = build(shiller_path, nber_path, shiller_url)

    meta = payload["_metadata"]
    print(f"{meta['months']} months, {meta['first_month']} to {meta['last_month']}")
    for key in ("stock", "bond", "short"):
        x = np.array(payload[key], dtype=float)
        print(f"  {key:6s} geometric real {np.prod(1 + x) ** (12 / len(x)) - 1:+.4f}")
    for out in OUTPUTS:
        out.write_text(json.dumps(payload, separators=(",", ":")) + "\n")
        print(f"wrote {out.relative_to(HERE)}")


if __name__ == "__main__":
    main(sys.argv)
