#!/usr/bin/env python3
"""One-time exporter: vendor spreadsheets to the CSV files inflation_beta.py reads.

Two of the inputs behind https://summitward.com/learn/inflation-beta ship as
spreadsheets rather than CSV, so they cannot be read with the standard library
alone. This script converts them once and writes the CSVs committed under
``data/`` with a sidecar ``*.meta.json`` recording the source, the retrieval
date and the file's own "updated" stamp. Re-run it only to refresh the data;
``inflation_beta.py`` never needs it.

Sources:

1.  Robert J. Shiller, ``ie_data.xls`` (the dataset behind *Irrational
    Exuberance*), sheet "Data": monthly S&P Composite price (P), dividends (D),
    earnings (E), CPI and the 10-year Treasury yield (GS10) from January 1871.
    P is the monthly average of daily closes except for the current month,
    which is a single close. D and E are 12-month trailing totals interpolated
    to months. Download from shillerdata.com; the Yale mirror is frozen at
    2023.09. No redistribution restriction is stated; the data are attributed
    to Robert J. Shiller.

2.  World Bank Commodity Price Data (the "Pink Sheet"), monthly file: gold
    ($/troy oz) from the "Monthly Prices" sheet and the Total, Energy,
    Non-energy, Agriculture, Metals & Minerals and Precious Metals indices
    (2010 = 100) from the "Monthly Indices" sheet, January 1960 onward. All
    are nominal US dollar spot prices, not investable futures returns.
    Licence: CC BY 4.0 (World Bank Data Catalog).

    The World Bank's September 2026 release rounds every value to one decimal
    (gold to the dollar), which is too coarse for 1960s index levels near 2.
    So the export takes two files: the January 2026 release at full precision
    as the base (its rows run through 2025M12; the sheet's own stamp reads
    "Updated on January 06, 2025", a typo for 2026 given its contents) and the
    current release to extend the series, chaining each later month onto the
    base by the ratio of consecutive rounded values. At 2026 price levels the
    rounding costs at most a few hundredths of a percent per month.

Requires pandas (with xlrd for the .xls) and openpyxl.

Usage:
    python3 export_sources.py                 # downloads all three files
    python3 export_sources.py --shiller ie_data.xls \
        --worldbank-base CMO-Historical-Data-Monthly-jan2026.xlsx \
        --worldbank-extend CMO-Historical-Data-Monthly.xlsx
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import tempfile
import urllib.request
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"

SHILLER_URL = (
    "https://img1.wsimg.com/blobby/go/e5e77e0b-59d1-44d9-ab25-4763ac982e53/"
    "downloads/e27e58c1-8ae0-488c-a976-a298708c7175/ie_data.xls"
)
SHILLER_LANDING = "https://shillerdata.com/"
WORLDBANK_URL = (
    "https://thedocs.worldbank.org/en/doc/"
    "74e8be41ceb20fa0da750cda2f6b9e4e-0050012026/related/"
    "CMO-Historical-Data-Monthly.xlsx"
)
WORLDBANK_BASE_URL = (
    "https://thedocs.worldbank.org/en/doc/"
    "18675f1d1639c7a34d463f59263ba0a2-0050012025/related/"
    "CMO-Historical-Data-Monthly.xlsx"
)
WORLDBANK_LANDING = "https://www.worldbank.org/en/research/commodity-markets"


def download(url: str, dest: Path) -> Path:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=120) as resp, open(dest, "wb") as fh:
        fh.write(resp.read())
    return dest


def shiller_month(value: float) -> str:
    """Shiller writes dates as YYYY.MM with October as YYYY.1, so format first."""
    text = f"{value:.2f}"
    year, month = text.split(".")
    return f"{year}-{month}"


def export_shiller(path: Path) -> None:
    import pandas as pd

    df = pd.read_excel(path, sheet_name="Data", header=None)
    # Row 7 (0-indexed) holds the short column names; data start at row 8.
    rows = []
    for _, row in df.iloc[8:].iterrows():
        raw = row.iloc[0]
        if not isinstance(raw, (int, float)) or math.isnan(raw):
            continue
        month = shiller_month(float(raw))

        def cell(i: int) -> str:
            v = row.iloc[i]
            if isinstance(v, (int, float)) and not math.isnan(v):
                return f"{float(v):.6f}".rstrip("0").rstrip(".")
            return ""

        rows.append(
            {
                "month": month,
                "p": cell(1),
                "d": cell(2),
                "e": cell(3),
                "cpi": cell(4),
                "gs10": cell(6),
            }
        )
    out = DATA / "shiller_monthly.csv"
    with open(out, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    footnotes = [
        str(v)
        for v in df.iloc[-1].tolist()
        if isinstance(v, str) and v.strip()
    ]
    meta = {
        "source": "Robert J. Shiller, ie_data.xls (Irrational Exuberance dataset), sheet Data",
        "landing_page": SHILLER_LANDING,
        "url": SHILLER_URL,
        "retrieved": date.today().isoformat(),
        "first_month": rows[0]["month"],
        "last_month": rows[-1]["month"],
        "columns": {
            "p": "S&P Composite price, monthly average of daily closes (current month: one close)",
            "d": "Dividends per share, 12-month trailing, interpolated to months",
            "e": "Earnings per share, 12-month trailing, interpolated to months",
            "cpi": "CPI-U as carried in Shiller's file (recent months estimated by Shiller)",
            "gs10": "10-year Treasury constant maturity yield, percent",
        },
        "file_footnotes": footnotes,
        "licence": "No redistribution restriction stated on shillerdata.com; attributed to Robert J. Shiller. Used with attribution.",
    }
    (DATA / "shiller_monthly.meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    print(f"wrote {out} ({len(rows)} rows, {rows[0]['month']} to {rows[-1]['month']})")


WB_INDEX_COLUMNS = {
    "Total Index": "total",
    "Energy": "energy",
    "Non-energy **": "non_energy",
    "Agriculture **": "agriculture",
    "Metals  & Minerals": "metals_minerals",
    "Precious Metals": "precious_metals",
}
WB_SERIES = ["gold", *WB_INDEX_COLUMNS.values()]


def read_worldbank(path: Path) -> tuple[str, dict[str, dict[str, float]]]:
    """Return (updated stamp, {month: {series: value}}) from one Pink Sheet file."""
    import openpyxl

    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)

    prices = wb["Monthly Prices"]
    price_rows = list(prices.iter_rows(values_only=True))
    updated = next(
        (str(r[0]) for r in price_rows[:6] if r[0] and str(r[0]).startswith("Updated")),
        "",
    )
    gold_col = price_rows[4].index("Gold")
    gold = {}
    for r in price_rows[6:]:
        if r[0] and isinstance(r[gold_col], (int, float)):
            gold[str(r[0])] = float(r[gold_col])

    indices = wb["Monthly Indices"]
    index_rows = list(indices.iter_rows(values_only=True))
    cols = {}
    for row in index_rows[5:8]:
        for j, name in enumerate(row):
            if isinstance(name, str) and name.strip() in WB_INDEX_COLUMNS:
                cols[WB_INDEX_COLUMNS[name.strip()]] = j
    missing = set(WB_INDEX_COLUMNS.values()) - set(cols)
    if missing:
        raise SystemExit(f"World Bank index columns not found: {sorted(missing)}")

    table: dict[str, dict[str, float]] = {}
    for r in index_rows[9:]:
        if not r[0] or "M" not in str(r[0]):
            continue
        label = str(r[0])
        year, month = label.split("M")
        rec: dict[str, float] = {}
        if label in gold:
            rec["gold"] = gold[label]
        for key, j in cols.items():
            if isinstance(r[j], (int, float)):
                rec[key] = float(r[j])
        table[f"{year}-{month}"] = rec
    return updated, table


def export_worldbank(base_path: Path, extend_path: Path) -> None:
    base_stamp, base = read_worldbank(base_path)
    extend_stamp, extend = read_worldbank(extend_path)

    months = sorted(base)
    merged = {m: dict(base[m]) for m in months}
    last = months[-1]
    chained = []
    for m in sorted(extend):
        if m <= last:
            continue
        prev = merged[months[-1]]
        cur = extend[m]
        prev_raw = extend.get(months[-1], {})
        rec = {}
        for key in WB_SERIES:
            if key in prev and key in cur and key in prev_raw and prev_raw[key]:
                rec[key] = prev[key] * cur[key] / prev_raw[key]
        merged[m] = rec
        months.append(m)
        chained.append(m)

    def fmt(v: float | None) -> str:
        return f"{v:.4f}".rstrip("0").rstrip(".") if v is not None else ""

    rows = [
        {"month": m, **{k: fmt(merged[m].get(k)) for k in WB_SERIES}} for m in months
    ]
    out = DATA / "worldbank_pink_sheet_monthly.csv"
    with open(out, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["month", *WB_SERIES])
        writer.writeheader()
        writer.writerows(rows)
    meta = {
        "source": "World Bank Commodity Price Data (The Pink Sheet), monthly historical file",
        "landing_page": WORLDBANK_LANDING,
        "base_file": {
            "url": WORLDBANK_BASE_URL,
            "file_updated_stamp": base_stamp,
            "note": "Full-precision release whose rows run through "
            + last
            + ". The stamp reads 2025 but the contents are the January 2026 release.",
        },
        "extension_file": {
            "url": WORLDBANK_URL,
            "file_updated_stamp": extend_stamp,
            "months_chained": chained,
            "note": "This release rounds values to one decimal. Months after the base file's last row are chained onto the base by the ratio of consecutive rounded values.",
        },
        "retrieved": date.today().isoformat(),
        "first_month": rows[0]["month"],
        "last_month": rows[-1]["month"],
        "columns": {
            "gold": "Gold, $/troy oz, monthly average (Monthly Prices sheet)",
            "total": "Total commodity index, nominal USD, 2010=100 (Monthly Indices sheet)",
            "energy": "Energy index, 2010=100",
            "non_energy": "Non-energy index, 2010=100",
            "agriculture": "Agriculture index, 2010=100",
            "metals_minerals": "Metals & Minerals index, 2010=100",
            "precious_metals": "Precious Metals index, 2010=100",
        },
        "notes": "Spot prices and spot-price indices. They are not the return of a collateralized futures position and include no roll or collateral yield.",
        "licence": "CC BY 4.0 (World Bank Data Catalog). Used with attribution.",
    }
    (DATA / "worldbank_pink_sheet_monthly.meta.json").write_text(
        json.dumps(meta, indent=2) + "\n"
    )
    print(f"wrote {out} ({len(rows)} rows, {rows[0]['month']} to {rows[-1]['month']})")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--shiller", type=Path, help="local ie_data.xls")
    parser.add_argument(
        "--worldbank-base", type=Path, help="local full-precision Pink Sheet (Jan 2026 release)"
    )
    parser.add_argument(
        "--worldbank-extend", type=Path, help="local current Pink Sheet release"
    )
    args = parser.parse_args()
    DATA.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        shiller = args.shiller or download(SHILLER_URL, Path(tmp) / "ie_data.xls")
        base = args.worldbank_base or download(WORLDBANK_BASE_URL, Path(tmp) / "cmo_base.xlsx")
        extend = args.worldbank_extend or download(WORLDBANK_URL, Path(tmp) / "cmo.xlsx")
        export_shiller(shiller)
        export_worldbank(base, extend)


if __name__ == "__main__":
    main()
