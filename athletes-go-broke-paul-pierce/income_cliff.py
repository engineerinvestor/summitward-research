"""Arithmetic behind https://summitward.com/learn/athletes-go-broke-paul-pierce.

Standard library only. Every input is printed with its source. Reported court
figures are as TMZ described a filing on October 27, 2026; they are claims in a
contested family-law case, not a verified balance sheet.
"""

# --- Reported figures (TMZ, Oct 27 2026; monthly, dollars) -----------------
CASH = 300_000  # "about $300K in the bank"
CHILD_SUPPORT = 28_000
SPOUSAL_SUPPORT = 20_000
BILLS = 48_000  # "around $48K a month in bills", itemized below
BILL_ITEMS = {
    "childcare": 8_000,
    "groceries": 5_000,
    "eating out": 7_000,
    "utilities": 3_200,
    "clothes": 1_000,
    "entertainment": 3_500,
}
BUSINESS_INCOME = 23_000  # "last month", from business interests

# --- Withdrawal-rate heuristic ----------------------------------------------
# Morningstar's State of Retirement Income research released December 2025:
# 3.9% starting safe withdrawal rate, 30 years, 90% probability of money left,
# 30-50% equity (up from 3.7% a year earlier).
SWR = 0.039

# --- BLS Displaced Worker Survey, January 2026, Table 7 (thousands) ----------
# Long-tenured displaced workers who lost full-time wage and salary jobs and
# were reemployed full time in January 2026, by earnings vs. the lost job.
# https://www.bls.gov/news.release/disp.t07.htm (last modified Aug 27, 2026)
BLS_FT_TOTAL = 1_593  # includes people who did not report earnings
BLS = {
    "20%+ below": 369,
    "below, within 20%": 317,
    "equal or above, within 20%": 354,
    "20%+ above": 302,
}

# --- Carlson, Kim, Lusardi & Camerer (2015), NBER w21085 --------------------
NFL_HAZARD = 0.0119  # annual bankruptcy hazard in retirement, NFL sample
STW_25_34 = 0.0117  # Sullivan, Thorne & Warren (2001), court records, ages 25-34
NLSY_MEN = 0.0038  # NLSY97 men in same cohorts, self-reported

# --- Career salary (read Oct 27 2026) ----------------------------------------
BREF_SALARY = 198_120_632  # Basketball-Reference, "may be incomplete", 20 rows
SPOTRAC_SALARY = 195_132_032  # Spotrac career earnings


def runway_table():
    print("Cash runway, months (cash / (outflows - income)):")
    support = CHILD_SUPPORT + SPOUSAL_SUPPORT
    for label, out in (
        ("bills are in addition to support", support + BILLS),
        ("bills include support", BILLS),
    ):
        for inc in (0, BUSINESS_INCOME):
            gap = out - inc
            print(
                f"  {label:34s} outflows ${out:>7,} income ${inc:>6,}"
                f"  gap ${gap:>7,}  runway {CASH / gap:5.1f}"
            )
    items = sum(BILL_ITEMS.values())
    print(
        f"  itemized bill lines sum to ${items:,} of ${BILLS:,};"
        f" ${BILLS - items:,} unitemized"
    )
    gap = support + BILLS - BUSINESS_INCOME
    eat = BILL_ITEMS["eating out"]
    print(
        f"  eating out ${eat:,} closes {eat / gap:.1%} of a ${gap:,} gap;"
        f" runway {CASH / gap:.1f} -> {CASH / (gap - eat):.1f} months"
    )


def fi_numbers():
    print(f"\nInvested assets needed at a {SWR:.1%} starting withdrawal rate:")
    for monthly in (10_000, 25_000, 48_000, 96_000):
        annual = monthly * 12
        print(f"  ${monthly:>6,}/mo = ${annual:>9,}/yr -> ${annual / SWR / 1e6:6.2f}M")


def bls_shares():
    reported = sum(BLS.values())
    below = BLS["20%+ below"] + BLS["below, within 20%"]
    print("\nBLS DWS Jan 2026, reemployed full time (earnings reported):")
    print(f"  reported {reported:,}k of {BLS_FT_TOTAL:,}k full-time reemployed")
    print(f"  earn less than before:   {below / reported:.1%}")
    print(f"  earn 20%+ less:          {BLS['20%+ below'] / reported:.1%}")
    same_or_more = reported - below
    print(f"  earn as much or more:    {same_or_more / reported:.1%}")


def carlson():
    print("\nCarlson et al. hazard comparisons:")
    print(f"  NFL / STW ages 25-34: {NFL_HAZARD / STW_25_34:.2f}x")
    print(f"  NFL / NLSY97 men:     {NFL_HAZARD / NLSY_MEN:.1f}x")


def salary():
    print("\nCareer NBA salary:")
    print(f"  Basketball-Reference ${BREF_SALARY:,}")
    print(f"  Spotrac              ${SPOTRAC_SALARY:,}")
    print(f"  difference           ${BREF_SALARY - SPOTRAC_SALARY:,}")


# --- Peak-window model (mirrors web/src/lib/peak-window-math.ts) -------------
def annuity_factor(n, r):
    if n <= 0:
        return 0.0
    return float(n) if r == 0 else (1 - (1 + r) ** -n) / r


def present_value(incomes, r, start=0):
    return sum(x / (1 + r) ** (t - start + 1) for t, x in enumerate(incomes) if t >= start)


def peak_window(assets, peak, peak_years, after, after_years, floor, retire_years, r, spend):
    incomes = [peak] * peak_years + [after] * after_years + [floor] * retire_years
    n = len(incomes)
    sustainable = (assets + present_value(incomes, r)) / annuity_factor(n, r)
    bal = assets
    for t in range(peak_years):
        bal = bal * (1 + r) + incomes[t] - spend
    after_cliff = (bal + present_value(incomes, r, peak_years)) / annuity_factor(
        n - peak_years, r
    )
    keep, depleted = assets, None
    for t in range(n):
        keep = keep * (1 + r) + incomes[t] - spend
        if keep < 0:
            depleted = t
            break
    return sustainable, 1 - sustainable / peak, bal, after_cliff, depleted


PRESETS = {
    # name: (age, cliff, stop, end, assets, peak, after, floor, spend)
    "tech engineer, 10 peak years": (35, 45, 60, 95, 500_000, 300_000, 210_000, 40_000, 230_000),
    "pro athlete, 5-year career": (23, 28, 62, 95, 0, 700_000, 70_000, 35_000, 350_000),
    "pro athlete, 15-year career": (22, 37, 62, 95, 0, 4_000_000, 150_000, 120_000, 2_000_000),
}


def presets(r=0.03):
    print(f"\nPeak-window presets at a {r:.0%} real return (illustrative households):")
    for name, (age, cliff, stop, end, a, pk, af, fl, sp) in PRESETS.items():
        s, rate, bal, after, dep = peak_window(
            a, pk, cliff - age, af, stop - cliff, fl, end - stop, r, sp
        )
        runs_out = "never" if dep is None else f"age {age + dep}"
        print(
            f"  {name}: sustainable ${s:,.0f}/yr, peak savings rate {rate:.0%},"
            f" spending ${sp:,} -> ${after:,.0f}/yr after {cliff}"
            f" ({1 - after / sp:.0%} cut),"
            f" unchanged spending runs out {runs_out}"
        )


if __name__ == "__main__":
    runway_table()
    fi_numbers()
    bls_shares()
    carlson()
    salary()
    presets()
