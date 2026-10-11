"""How fast do higher market yields reach France's interest bill?

Rolls France's nominal State debt (fixed-rate OATs plus BTF bills) forward ten
years from the AFT line table of October 2026. Each year the bonds that mature,
plus new net borrowing, are refinanced at a scenario yield; everything else
keeps its existing coupon. The output is the effective interest rate on the
nominal stock and the interest bill, compared with the shortcut of repricing
the whole stock at today's yields at once.

Stdlib only. Run:  python3 france_refinancing.py
"""

from __future__ import annotations

import csv
import datetime as dt
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LINES = HERE / "data" / "france_lines.csv"

# Banque de France constant-maturity OAT yields (TEC), 9 October 2026, percent.
CURVE_2026_10_09 = {1: 3.251, 2: 3.602, 5: 4.111, 10: 4.795, 30: 5.357}

# Assumed maturity mix of new medium/long-term issuance (years: share). Average
# maturity 9.9 years, close to AFT's 9y33d average life of the medium/long-term
# stock at 30 September 2026. AFT publishes its 2027 programme in December 2026.
ISSUANCE_MIX = {2: 0.20, 5: 0.30, 10: 0.35, 30: 0.15}

# Net new medium/long-term borrowing per year, EUR. The 2027 finance bill caps
# the net change in nominal negotiable debt over one year at EUR 160.5bn
# (AFT press release, 29 September 2026). Held flat; no feedback from higher
# interest to higher borrowing.
NET_NEW_BORROWING = 160.5e9

# BTF stock held at its October 2026 level and rolled continuously at the
# one-year rate. Its current cost is set at 3.0%, the level of October auctions.
BTF_CURRENT_RATE = 3.0

# Nominal GDP growth forecast, PLF 2027 debt annex Table 1 (2026-2030); held at
# 2.9% after 2030.
NOMINAL_GROWTH = {2026: 2.0, 2027: 2.7, 2028: 2.8, 2029: 2.8, 2030: 2.9}

START_YEAR, END_YEAR = 2027, 2036
SCENARIOS = {"curve -100bp": -1.0, "curve held at 9 Oct 2026": 0.0, "curve +100bp": 1.0}


def load_lines():
    oats, btf_total = [], 0.0
    with LINES.open() as f:
        for row in csv.DictReader(f):
            face = float(row["face_eur"])
            if row["instrument_type"] == "BTF":
                btf_total += face
            elif row["instrument_type"] == "OAT":
                mat = dt.date.fromisoformat(row["maturity_date"])
                oats.append(
                    {
                        "face": face,
                        "coupon": float(row["coupon_pct"] or 0),
                        "year": mat.year,
                    }
                )
    return oats, btf_total


def issuance_yield(shift: float) -> float:
    return sum(w * (CURVE_2026_10_09[m] + shift) for m, w in ISSUANCE_MIX.items())


def run(shift: float, instant: bool = False):
    """Roll the nominal stock forward; returns one row per calendar year."""
    oats, btf = load_lines()
    new_yield = issuance_yield(shift)
    bill_rate = CURVE_2026_10_09[1] + shift
    bonds = [dict(b, coupon=new_yield) if instant else dict(b) for b in oats]

    def issue(amount: float, year: int):
        return [
            {"face": amount * w, "coupon": new_yield, "year": year + m}
            for m, w in ISSUANCE_MIX.items()
        ]

    # Redemptions in October-December 2026 are refinanced at the end of 2026.
    maturing = sum(b["face"] for b in bonds if b["year"] <= 2026)
    bonds = [b for b in bonds if b["year"] > 2026] + issue(maturing, 2026)

    rows = []
    for year in range(START_YEAR, END_YEAR + 1):
        opening = sum(b["face"] for b in bonds)
        due = [b for b in bonds if b["year"] == year]
        survivors = [b for b in bonds if b["year"] > year]
        redeem = sum(b["face"] for b in due)
        gross = redeem + NET_NEW_BORROWING
        # Mid-year convention: bonds maturing this year pay half a year of
        # coupon, and bonds issued through the year pay half a year.
        interest = sum(b["face"] * b["coupon"] for b in survivors)
        interest += 0.5 * sum(b["face"] * b["coupon"] for b in due)
        interest += 0.5 * gross * new_yield
        if instant or year > START_YEAR:
            interest += btf * bill_rate
        else:  # bills issued before the shock run off over the first year
            interest += btf * 0.5 * (BTF_CURRENT_RATE + bill_rate)
        interest /= 100
        bonds = survivors + issue(gross, year)
        average_stock = opening + 0.5 * NET_NEW_BORROWING + btf
        rows.append(
            {
                "year": year,
                "interest_bn": interest / 1e9,
                "stock_bn": (opening + NET_NEW_BORROWING + btf) / 1e9,
                "eff_rate": 100 * interest / average_stock,
            }
        )
    return rows


def avg_coupon(oats):
    return sum(b["face"] * b["coupon"] for b in oats) / sum(b["face"] for b in oats)


def main():
    oats, btf = load_lines()
    print(
        f"Nominal OATs: EUR {sum(b['face'] for b in oats) / 1e9:,.1f}bn, "
        f"face-weighted coupon {avg_coupon(oats):.3f}%"
    )
    print(f"BTF stock: EUR {btf / 1e9:,.1f}bn")
    print(f"Issuance-mix yield at 9 Oct 2026 curve: {issuance_yield(0):.3f}%")
    # Share of today's OAT face still outstanding (not yet refinanced) by year.
    total = sum(b["face"] for b in oats)
    print("\nShare of October 2026 OAT face still at its old coupon, end of year:")
    for y in (2027, 2028, 2029, 2031, 2036):
        left = sum(b["face"] for b in oats if b["year"] > y)
        print(f"  {y}: {100 * left / total:5.1f}%")

    results = {name: run(shift) for name, shift in SCENARIOS.items()}
    shortcut = run(0.0, instant=True)

    print("\nEffective rate on nominal debt (%), interest bill (EUR bn):")
    header = "  year  " + "  ".join(
        f"{n:>26}" for n in [*SCENARIOS, "shortcut (all at once)"]
    )
    print(header)
    for i, year in enumerate(range(START_YEAR, END_YEAR + 1)):
        cells = [results[n][i] for n in SCENARIOS] + [shortcut[i]]
        print(
            f"  {year}  "
            + "  ".join(
                f"{c['eff_rate']:>12.2f}% {c['interest_bn']:>10.1f}bn" for c in cells
            )
        )

    base, up = results["curve held at 9 Oct 2026"], results["curve +100bp"]
    print("\nExtra interest from a permanent +100bp shift vs held curve (EUR bn):")
    for k in (0, 1, 4):
        print(
            f"  year {k + 1} ({base[k]['year']}): +{up[k]['interest_bn'] - base[k]['interest_bn']:.1f}"
        )
    print(
        "  AFT/DG Tresor, PLF 2027 debt annex: +3.4 (year 1), +8.1 (year 2), ~+19.2 (year 5),"
        " all negotiable debt incl. linkers"
    )


def stabilizing_primary_balance(debt_ratio: float, r: float, g: float) -> float:
    """Primary surplus (% of GDP) that holds debt/GDP flat: (r - g)/(1 + g) * b."""
    return (r - g) / (100 + g) * debt_ratio


def r_minus_g_check():
    """The Economist's thought experiment: all debt refinanced at the 5-year yield."""
    r5 = CURVE_2026_10_09[5]
    print(
        "\nDebt-stabilizing primary balance, all debt at the 5-year OAT yield"
        f" ({r5:.2f}%), Maastricht debt 119.3% of GDP:"
    )
    for g in (2.0, 2.5, 2.7):
        print(
            f"  nominal growth {g:.1f}%: primary surplus {stabilizing_primary_balance(119.3, r5, g):.2f}% of GDP"
        )
    oats, _ = load_lines()
    c = avg_coupon(oats)
    print(
        f"  at the stock's {c:.2f}% average OAT coupon and 2.7% growth: "
        f"{stabilizing_primary_balance(119.3, c, 2.7):.2f}% of GDP"
    )


def write_json(path: Path):
    results = {name: run(shift) for name, shift in SCENARIOS.items()}
    shortcut = run(0.0, instant=True)
    rows = []
    for i, year in enumerate(range(START_YEAR, END_YEAR + 1)):
        rows.append(
            {
                "year": year,
                "down": round(results["curve -100bp"][i]["eff_rate"], 2),
                "held": round(results["curve held at 9 Oct 2026"][i]["eff_rate"], 2),
                "up": round(results["curve +100bp"][i]["eff_rate"], 2),
                "shortcut": round(shortcut[i]["eff_rate"], 2),
                "growth": NOMINAL_GROWTH.get(year, 2.9),
            }
        )
    path.write_text(json.dumps(rows, indent=1) + "\n")
    print(f"\nWrote {path.relative_to(HERE)}")


if __name__ == "__main__":
    main()
    r_minus_g_check()
    if "--json" in sys.argv:
        write_json(HERE / "effective_rate_paths.json")
