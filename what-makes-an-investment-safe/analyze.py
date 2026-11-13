"""Print every table quoted in the `what-makes-an-investment-safe` Learn guide.

Same assets, different bills: how often money set aside in T-bills, a 10-year
Treasury (rolled or held to maturity), the S&P 500 or a 60/40 mix failed to
cover a fixed-dollar bill or a CPI-linked bill over historical windows, and how
flexibility (waiting or trimming) changes the answer. Also replicates the
"years underwater in real terms" chart on year-end data.

Data: Damodaran annual returns (data/damodaran_returns.json, 1928-2025) and
year-end 10-year yields from the same workbook (data/treasury_10y_yields.json).
Conventions live in safe_asset_scorecard.py.

Usage:
    python3 analyze.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import safe_asset_scorecard as sc  # noqa: E402

ROLLING = ("tbill", "tbond", "sp500", "sixty_forty")
HORIZONS = (1, 3, 5, 10, 20, 30)
TAX = 0.24


def pct(x: float) -> str:
    return f"{x:.0%}"


def main() -> None:
    d = sc.load_data()
    print(f"Data {d['first_year']}-{d['last_year']}, US, annual, before fees.\n")

    print("1. Share of windows that fell short: nominal | real (worst real outcome)")
    head = "".join(f"{sc.LABELS[s][:22]:>26}" for s in ROLLING)
    print(f"{'horizon':>8}{'windows':>9}{'~indep.':>9}{head}")
    for h in HORIZONS:
        cells = []
        for s in ROLLING:
            n = sc.shortfall(d, s, h, "nominal")
            r = sc.shortfall(d, s, h, "real")
            cells.append(
                f"{pct(n['share_short'])} | {pct(r['share_short'])} ({r['worst']:+.0%})"
            )
        windows = n["windows"]
        indep = (d["last_year"] - d["first_year"] + 1) // h
        print(f"{h:>8}{windows:>9}{indep:>9}" + "".join(f"{c:>26}" for c in cells))
    print()

    print(f"2. T-bills after a {TAX:.0%} tax on interest, real yardstick")
    for h in HORIZONS:
        r = sc.shortfall(d, "tbill_after_tax", h, "real", tax_rate=TAX)
        print(f"   {h:>2}y: {pct(r['share_short'])} short, worst {r['worst']:+.0%}")
    print()

    print("3. 10-year Treasury bought at the prior year-end yield, held to maturity")
    n = sc.shortfall(d, "held_10y", 10, "nominal")
    r = sc.shortfall(d, "held_10y", 10, "real")
    roll = sc.shortfall(d, "tbond", 10, "real")
    print(f"   windows {r['windows']} (starts {r['first_start']}-{r['last_start']})")
    print(f"   nominal: {pct(n['share_short'])} short (paid its promise every time)")
    print(
        f"   real:    {pct(r['share_short'])} short ({r['short']} windows), "
        f"worst {r['worst']:+.1%}, median {r['median']:+.1%}"
    )
    print(f"   real short start years: {r['short_years']}")
    print(
        f"   rolled 10-year Treasury, real, same windows: {pct(roll['share_short'])} short"
    )
    print()

    print("4. Longest spells below a prior real year-end high")
    for s in ("tbond", "sp500", "tbill", "sixty_forty"):
        for sp in sc.underwater_spells(d, s, "real")[:3]:
            rec = sp["recovery_year"] or f"open at {d['last_year']}"
            extra = (
                f", {sp['depth_now']:+.1%} at {d['last_year']}"
                if "depth_now" in sp
                else ""
            )
            print(
                f"   {sc.LABELS[s]:<32} peak {sp['peak_year']}  trough {sp['trough_year']} "
                f"({sp['depth']:+.1%})  recovered {rec}  -> {sp['years']} years{extra}"
            )
    print()

    print("5. Flexibility, real yardstick (windows that complete horizon + 3 years)")
    for h in (3, 5, 10):
        yrs = sc.start_years(d, h, 3)
        print(f"   horizon {h}y, {len(yrs)} windows (starts {yrs[0]}-{yrs[-1]})")
        print(
            f"   {'':<32}{'firm':>7}{'wait 1':>8}{'wait 3':>8}{'cut 10%':>9}{'cut 20%':>9}"
        )
        for s in ROLLING:
            row = [
                sc.shortfall(d, s, h, "real", window_years=yrs),
                sc.shortfall(d, s, h, "real", can_delay=1, window_years=yrs),
                sc.shortfall(d, s, h, "real", can_delay=3, window_years=yrs),
                sc.shortfall(d, s, h, "real", can_cut=0.10, window_years=yrs),
                sc.shortfall(d, s, h, "real", can_cut=0.20, window_years=yrs),
            ]
            widths = (7, 8, 8, 9, 9)
            cells = "".join(
                f"{pct(x['share_short']):>{w}}"
                for x, w in zip(row, widths, strict=True)
            )
            print(f"   {sc.LABELS[s]:<32}{cells}")
        print()

    print("6. Flexibility, nominal yardstick (fixed-dollar bill), stocks")
    for h in (1, 3, 5):
        yrs = sc.start_years(d, h, 3)
        firm = sc.shortfall(d, "sp500", h, "nominal", window_years=yrs)
        wait3 = sc.shortfall(d, "sp500", h, "nominal", can_delay=3, window_years=yrs)
        print(
            f"   S&P 500 {h}y: firm {pct(firm['share_short'])} short "
            f"(worst {firm['worst']:+.0%}), wait 3 years {pct(wait3['share_short'])}"
        )


if __name__ == "__main__":
    main()
