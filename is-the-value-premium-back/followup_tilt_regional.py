"""Follow-up figures for the Nov 2026 revision of is-the-value-premium-back.

Two questions the first version left open:

1. Did value's recovery start in 2025-26, or earlier, and does the answer
   differ by region? Calendar-year HML returns, U.S. and developed ex-US,
   from the committed Ken French files (202609 vintage).
2. What did a measured tilt do to a portfolio, as opposed to the fund on its
   own? Monthly-rebalanced core/tilt mixes from the same Yahoo Finance
   month-end adjusted closes that analyze.py caches in ./.cache/.
3. How do French's six size/book-to-market portfolios rank over the full
   history? (Context for the small value minus small growth edge in the
   value-spread forward test: small growth is the weakest of the six.)
   Reads ../value-spread/data/6_Portfolios_2x3.csv.

Run analyze.py first so ./.cache/ holds the price files. This script does not
download anything and does not change analyze.py's output.

    python3 followup_tilt_regional.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
CACHE = HERE / ".cache"

START = "2019-09-30"  # first month-end after AVUV/AVDV began trading
END = "2026-10-31"


def load_french_monthly(path: Path) -> pd.DataFrame:
    """Monthly rows (YYYYMM) of a French CSV, in decimals. Stops at the annual block."""
    rows = []
    header = None
    for line in path.read_text().splitlines():
        parts = [p.strip() for p in line.split(",")]
        if header is None and len(parts) > 3 and parts[0] == "" and "HML" in parts:
            header = parts[1:]
            continue
        if header is not None:
            if len(parts[0]) == 6 and parts[0].isdigit():
                rows.append(parts)
            elif rows:
                break
    df = pd.DataFrame(rows).set_index(0).astype(float) / 100
    df.columns = header
    return df


def hml_section(name: str, df: pd.DataFrame) -> None:
    h = df["HML"]
    wealth = (1 + h).cumprod()
    print(f"\n{name} HML ({h.index[0]} to {h.index[-1]})")
    for year in range(2018, 2027):
        months = h[[i for i in h.index if i.startswith(str(year))]]
        print(f"  {year}: {((1 + months).prod() - 1) * 100:+6.1f}%  ({len(months)} months)")
    after_2006 = wealth[wealth.index >= "200601"]
    trough = after_2006.idxmin()
    peak = wealth[wealth.index <= trough].idxmax()
    print(
        f"  pre-trough peak {peak}, trough {trough}, "
        f"drawdown {(wealth[trough] / wealth[peak] - 1) * 100:.1f}%"
    )
    print(f"  {h.index[-1]} vs trough: {(wealth.iloc[-1] / wealth[trough] - 1) * 100:+.1f}%")
    print(f"  {h.index[-1]} vs pre-trough peak: {(wealth.iloc[-1] / wealth[peak] - 1) * 100:+.1f}%")
    print(
        f"  series high {wealth.idxmax()}; {h.index[-1]} is "
        f"{wealth.iloc[-1] / wealth.max() * 100:.1f}% of it"
    )
    for start in ("201909", "202009", "202109", "202309", "202509"):
        growth = wealth.iloc[-1] / wealth[start] - 1
        years = (len(wealth) - 1 - list(wealth.index).index(start)) / 12
        print(
            f"  end {start} to {h.index[-1]}: {growth * 100:+.1f}% total, "
            f"{((1 + growth) ** (1 / years) - 1) * 100:+.1f}% a year"
        )


def month_end_prices(ticker: str) -> pd.Series:
    df = pd.read_csv(CACHE / f"{ticker}.csv")
    s = pd.Series(df[df.columns[1]].values, index=pd.to_datetime(df[df.columns[0]]))
    s = s[(s.index >= "2019-09-01") & (s.index <= END)]
    return s.resample("ME").last()


def stats(r: pd.Series) -> tuple[float, float, float]:
    wealth = (1 + r).cumprod()
    cagr = wealth.iloc[-1] ** (12 / len(r)) - 1
    vol = r.std() * np.sqrt(12)
    drawdown = (wealth / wealth.cummax() - 1).min()
    return cagr, vol, drawdown


def tilt_section() -> None:
    print(f"\nCore plus tilt, month-end market prices, {START} to {END}, rebalanced monthly")
    print("(no costs, no taxes; tracking error is annualized vs the core alone)")
    for core, tilt in (("VTI", "AVUV"), ("VXUS", "AVDV"), ("VT", "AVUV")):
        prices = pd.concat([month_end_prices(core), month_end_prices(tilt)], axis=1).dropna()
        prices.columns = ["core", "tilt"]
        prices = prices[prices.index >= START]
        r = prices.pct_change().dropna()
        print(f"\n  {core} + {tilt}: {r.index[0].date()} to {r.index[-1].date()}, {len(r)} months")
        for w in (0.0, 0.1, 0.2, 0.3, 1.0):
            mix = (1 - w) * r["core"] + w * r["tilt"]
            cagr, vol, dd = stats(mix)
            te = (mix - r["core"]).std() * np.sqrt(12)
            print(
                f"    {int(w * 100):3d}% {tilt}: return {cagr * 100:5.2f}%  "
                f"vol {vol * 100:4.1f}%  worst drawdown {dd * 100:5.1f}%  "
                f"tracking error {te * 100:4.1f}%"
            )


def six_portfolios_section() -> None:
    path = HERE.parent / "value-spread" / "data" / "6_Portfolios_2x3.csv"
    df = load_french_monthly_generic(path)
    n = len(df)
    print(f"\nFrench 6 portfolios (2x3), value-weighted, {df.index[0]} to {df.index[-1]}")
    for col in df.columns:
        cagr = (1 + df[col]).prod() ** (12 / n) - 1
        print(f"  {col:12s} compound {cagr * 100:5.2f}% a year")


def load_french_monthly_generic(path: Path) -> pd.DataFrame:
    """First monthly block of a French portfolio CSV (value-weighted returns)."""
    rows = []
    header = None
    for line in path.read_text().splitlines():
        parts = [p.strip() for p in line.split(",")]
        if header is None and len(parts) > 3 and parts[0] == "":
            header = parts[1:]
            continue
        if header is not None:
            if len(parts[0]) == 6 and parts[0].isdigit():
                rows.append(parts)
            elif rows:
                break
    df = pd.DataFrame(rows).set_index(0).astype(float) / 100
    df.columns = header
    return df


def main() -> None:
    us = load_french_monthly(DATA / "F-F_Research_Data_5_Factors_2x3.csv")
    dev = load_french_monthly(DATA / "Developed_ex_US_5_Factors.csv")
    hml_section("U.S.", us)
    hml_section("Developed ex-US", dev)
    tilt_section()
    six_portfolios_section()


if __name__ == "__main__":
    main()
