"""How often did stocks beat a guaranteed return, over historical windows?

Reproduces the table in
https://summitward.com/learn/mortgage-rate-below-ten-percent.

The claim under test: because the S&P 500 has averaged about 10% a year, any
debt costing less than 10% should be carried rather than repaid. An average is
not an outcome, so the question is how often the average actually showed up
over a holding period.

Data: data/sp500_returns.json, annual S&P 500 total returns including dividends,
1928-2025, from Aswath Damodaran's histretSP.xls (NYU Stern).

Caveats that belong with any figure produced here: the windows overlap, so they
are not independent observations; the pre-1957 index is a reconstruction; and
nothing below models taxes, the mortgage interest deduction, or the fact that
debt repayment happens on a schedule rather than as a lump sum.

Run: python3 guaranteed_vs_equity_windows.py
"""

import json
import statistics as st
from math import prod
from pathlib import Path

DATA = Path(__file__).resolve().parent / "data" / "sp500_returns.json"
RATES = (0.03, 0.05, 0.06, 0.07, 0.08, 0.09)
HORIZONS = (5, 10, 20, 30)


def load_returns() -> list[float]:
    raw = json.loads(DATA.read_text())
    years = sorted(int(y) for y in raw)
    # Values are stored as decimals already (0.4381 == +43.81%).
    return [raw[str(y)] for y in years], years[0], years[-1]


def beat_share(returns: list[float], rate: float, horizon: int) -> tuple[int, int]:
    """Windows in which buy-and-hold beat a guaranteed `rate`, and the total."""
    wins = total = 0
    for i in range(len(returns) - horizon + 1):
        growth = prod(1 + r for r in returns[i : i + horizon])
        total += 1
        if growth > (1 + rate) ** horizon:
            wins += 1
    return wins, total


def main() -> None:
    returns, first, last = load_returns()
    geo = prod(1 + r for r in returns) ** (1 / len(returns)) - 1
    print(f"S&P 500 annual total returns, {first}-{last}, n={len(returns)}")
    print(
        f"  arithmetic mean {st.mean(returns):.2%}   "
        f"geometric {geo:.2%}   stdev {st.pstdev(returns):.2%}"
    )
    print()
    print("Share of overlapping windows in which stocks beat a GUARANTEED return")
    header = f"{'guaranteed':>12}" + "".join(f"{str(h) + 'yr':>9}" for h in HORIZONS)
    print(header)
    for rate in RATES:
        row = f"{rate:>11.0%} "
        for horizon in HORIZONS:
            wins, total = beat_share(returns, rate, horizon)
            row += f"{wins / total:>8.0%} "
        print(row)
    print()
    for horizon in (10, 20, 30):
        wins, total = beat_share(returns, 0.09, horizon)
        print(
            f"  9% guaranteed, {horizon}-year windows: stocks won {wins} of "
            f"{total} ({wins / total:.0%}), lost {total - wins} ({1 - wins / total:.0%})"
        )


if __name__ == "__main__":
    main()
