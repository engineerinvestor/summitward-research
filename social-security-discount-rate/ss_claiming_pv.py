"""Present value of Social Security by claiming age and real discount rate.

Reproduces the tables in https://summitward.com/learn/social-security-discount-rate
(and the summary figures repeated in the Mr. Money Mustache fact-check and the
Good Heuristics, Bad Theorems hub).

The claiming-age answer is decided by the real discount rate applied to the
benefit stream. Discounting an inflation-indexed, lifetime benefit at an expected
equity return makes early claiming win almost automatically; discounting it at a
long TIPS yield makes the three ages close.

Benefit factors are statutory (42 U.S.C. 402(q), 402(w); 20 C.F.R. 404.313,
404.409, 404.410); the survival table is SSA's 2023 period life table as used in
the 2026 Trustees Report: https://www.ssa.gov/oact/STATS/table4c6.html
(read 2026-09-14).

Three crossovers are printed for each sex, because they differ and the
difference matters: the rate below which 70 beats 62, the rate below which 70
beats 67, and the rate below which 67 beats 62. "70 has the highest present
value" requires the second, not the first.

Run:
    python3 ss_claiming_pv.py
    python3 ss_claiming_pv.py --haircut 0.78:69   # 78% payable from age 69
"""

import argparse

FRA = 67

# SSA period life table 2023 (2026 TR), "number of lives" column, ages 62+.
# Only the survivor counts are needed; ratios give survival probabilities.
LIVES: dict[int, tuple[int, int]] = {
    62: (82563, 89767),
    63: (81473, 89029),
    64: (80314, 88238),
    65: (79084, 87399),
    66: (77783, 86508),
    67: (76416, 85567),
    68: (74984, 84569),
    69: (73486, 83509),
    70: (71916, 82374),
    71: (70269, 81158),
    72: (68539, 79847),
    73: (66722, 78433),
    74: (64811, 76904),
    75: (62797, 75248),
    76: (60675, 73454),
    77: (58429, 71510),
    78: (56024, 69387),
    79: (53477, 67087),
    80: (50785, 64606),
    81: (47960, 61946),
    82: (44998, 59099),
    83: (41922, 56068),
    84: (38760, 52857),
    85: (35529, 49469),
    86: (32236, 45919),
    87: (28901, 42223),
    88: (25563, 38399),
    89: (22265, 34475),
    90: (19063, 30504),
    91: (16023, 26564),
    92: (13194, 22732),
    93: (10617, 19087),
    94: (8320, 15697),
    95: (6333, 12612),
    96: (4672, 9877),
    97: (3335, 7519),
    98: (2298, 5554),
    99: (1534, 3977),
    100: (999, 2758),
    101: (633, 1849),
    102: (389, 1196),
    103: (232, 745),
    104: (133, 446),
    105: (74, 256),
    106: (39, 141),
    107: (20, 73),
    108: (10, 36),
    109: (4, 17),
    110: (2, 7),
    111: (1, 3),
    112: (0, 1),
}
MAX_AGE = 112
AGES = (62, 67, 70)
RATES = (0.0, 0.01, 0.02, 0.03, 0.04, 0.05, 0.06)


def benefit_factor(claim_age: int) -> float:
    """Benefit as a share of the primary insurance amount, FRA 67.

    Early: 5/9 of 1% per month for the first 36 months, 5/12 of 1% beyond.
    Delayed: 8% per year of delay past FRA, to age 70.
    """
    if claim_age < FRA:
        months = round((FRA - claim_age) * 12)
        reduction = min(months, 36) * (5 / 9) / 100
        reduction += max(months - 36, 0) * (5 / 12) / 100
        return 1 - reduction
    return 1 + min(claim_age - FRA, 3) * 0.08


def survival(age: int, sex: str, from_age: int = 62) -> float:
    """Probability of being alive at `age`, given alive at `from_age`."""
    if age > MAX_AGE:
        return 0.0
    i = 0 if sex == "male" else 1
    start = LIVES[from_age][i]
    return LIVES[age][i] / start if start else 0.0


def survival_monthly(age_months: int, sex: str) -> float:
    """Survival at an age in months from 62, interpolated within each year."""
    age = 62 + age_months // 12
    frac = (age_months % 12) / 12
    lo = survival(age, sex)
    hi = survival(age + 1, sex)
    return lo + (hi - lo) * frac


def payable(age: int, haircut: tuple[float, int] | None) -> float:
    """Share of the scheduled benefit actually paid at `age`."""
    if haircut and age >= haircut[1]:
        return haircut[0]
    return 1.0


def pv_fixed(claim_age: int, death_age: int, real_rate: float) -> float:
    """PV at 62 per $1 of PIA, assuming death at a fixed age (no mortality risk)."""
    return sum(
        benefit_factor(claim_age) / (1 + real_rate) ** (age - 62)
        for age in range(claim_age, death_age)
    )


def pv_mortality(
    claim_age: int,
    real_rate: float,
    sex: str,
    haircut: tuple[float, int] | None = None,
) -> float:
    """Expected PV at 62 per $1 of PIA, weighting each year by survival.

    Benefits are paid once a year in advance. `haircut` is (factor, from_age):
    the share of the scheduled benefit paid from that age on, which is how a
    trust-fund shortfall lands on someone who is 62 today.
    """
    return sum(
        benefit_factor(claim_age)
        * payable(age, haircut)
        * survival(age, sex)
        / (1 + real_rate) ** (age - 62)
        for age in range(claim_age, MAX_AGE + 1)
    )


def pv_mortality_monthly(claim_age: int, real_rate: float, sex: str) -> float:
    """Same as pv_mortality with monthly payments and interpolated survival.

    Printed only to show how much the annual-payment simplification moves the
    crossover; the guide quotes the annual model.
    """
    total = 0.0
    for m in range((claim_age - 62) * 12, (MAX_AGE - 62) * 12 + 12):
        total += (
            benefit_factor(claim_age)
            / 12
            * survival_monthly(m, sex)
            / (1 + real_rate) ** (m / 12)
        )
    return total


def crossover(pv_fn, later: int, earlier: int, lo: float = 0.0, hi: float = 0.25):
    """Highest real rate at which claiming at `later` still beats `earlier`."""
    if pv_fn(later, lo) - pv_fn(earlier, lo) <= 0:
        return lo
    for _ in range(200):
        mid = (lo + hi) / 2
        if pv_fn(later, mid) - pv_fn(earlier, mid) > 0:
            lo = mid
        else:
            hi = mid
    return lo


def print_table(title: str, pv_fn, rates=RATES) -> None:
    print(f"\n{title}")
    print(f"{'real rate':>10}{'claim 62':>10}{'claim 67':>10}{'claim 70':>10}  highest")
    for r in rates:
        vals = {a: pv_fn(a, r) for a in AGES}
        winner = max(vals, key=lambda k: vals[k])
        print(f"{r:>9.0%}{vals[62]:>10.2f}{vals[67]:>10.2f}{vals[70]:>10.2f}  {winner}")


def print_crossovers(label: str, pv_fn) -> None:
    c70_62 = crossover(pv_fn, 70, 62)
    c70_67 = crossover(pv_fn, 70, 67)
    c67_62 = crossover(pv_fn, 67, 62)
    print(
        f"  {label:<28} 70 beats 62 below {c70_62:.2%}   "
        f"70 beats 67 below {c70_67:.2%}   67 beats 62 below {c67_62:.2%}"
    )


def parse_haircut(text: str) -> tuple[float, int]:
    factor, age = text.split(":")
    return float(factor), int(age)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--haircut",
        type=parse_haircut,
        default=(0.78, 69),
        metavar="FACTOR:AGE",
        help="scheduled-benefit share paid from AGE on (default 0.78:69, the "
        "2026 Trustees Report OASI figure landing on someone who is 62 in 2026)",
    )
    args = parser.parse_args()

    print("Benefit as a share of PIA:")
    for a in AGES:
        print(f"  claim at {a}: {benefit_factor(a):.0%}")

    print_table(
        "Table 1. PV at 62 per $1 of PIA, death assumed at 85",
        lambda a, r: pv_fixed(a, 85, r),
    )

    for sex in ("male", "female"):
        print_table(
            f"Table 2 ({sex}). Mortality-weighted expected PV at 62 per $1 of PIA, "
            "SSA 2023 period life table, scheduled benefits",
            lambda a, r, s=sex: pv_mortality(a, r, s),
        )

    h_factor, h_age = args.haircut
    for sex in ("male", "female"):
        print_table(
            f"Table 3 ({sex}). Same, with {h_factor:.0%} of the scheduled benefit "
            f"paid from age {h_age}",
            lambda a, r, s=sex: pv_mortality(a, r, s, args.haircut),
        )

    print("\nCrossovers (annual payments, the model the guide quotes)")
    for death_age in (80, 85, 90, 95):
        print_crossovers(
            f"fixed death at {death_age}",
            lambda a, r, d=death_age: pv_fixed(a, d, r),
        )
    for sex in ("male", "female"):
        print_crossovers(
            f"mortality-weighted, {sex}", lambda a, r, s=sex: pv_mortality(a, r, s)
        )
    for sex in ("male", "female"):
        print_crossovers(
            f"{h_factor:.0%} from {h_age}, {sex}",
            lambda a, r, s=sex: pv_mortality(a, r, s, args.haircut),
        )

    print("\nCrossovers with monthly payments (sensitivity check only)")
    for sex in ("male", "female"):
        print_crossovers(
            f"monthly, {sex}", lambda a, r, s=sex: pv_mortality_monthly(a, r, s)
        )


if __name__ == "__main__":
    main()
