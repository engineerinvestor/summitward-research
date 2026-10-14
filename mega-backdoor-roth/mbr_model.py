"""What a mega backdoor Roth is worth: the same after-tax 401(k) room invested
for 25 years in a Roth versus a taxable brokerage account.

Limits are 2026, under age 50 (IRS Notice 2025-67). Stdlib only.
Usage: python3 mbr_model.py
"""

TOTAL_415C = 72_000      # 401(k) annual additions limit, all sources, before catch-ups
DEFERRAL = 24_500        # employee elective deferral limit
SALARY = 200_000
EMPLOYER_RATE = 0.04
EMPLOYER = round(SALARY * EMPLOYER_RATE)
MEGA = TOTAL_415C - DEFERRAL - EMPLOYER   # voluntary after-tax room
IRA = 7_500              # IRA contribution limit, for the backdoor Roth IRA comparison

R = 0.07       # annual total return, same investments in both accounts
YLD = 0.015    # qualified dividend yield, taxed each year and reinvested
TAX = 0.15     # rate on qualified dividends and long-term gains
YEARS = 25
INFLATION = 0.025


def run(c=MEGA, r=R, yld=YLD, tax=TAX, years=YEARS):
    """Contributions at the end of each year. The taxable account pays tax on
    dividends each year, reinvests the rest (which adds to basis), and is sold
    once in the final year."""
    roth = taxable = basis = div_tax = 0.0
    for _ in range(years):
        roth = roth * (1 + r) + c
        d = taxable * yld
        div_tax += d * tax
        taxable = taxable * (1 + r - yld) + d * (1 - tax) + c
        basis += d * (1 - tax) + c
    gain_tax = tax * (taxable - basis)
    after = taxable - gain_tax
    return {
        "contributed": c * years,
        "roth": roth,
        "pre_sale": taxable,
        "basis": basis,
        "gain_tax": gain_tax,
        "taxable": after,
        "div_tax": div_tax,
        "div_growth": roth - taxable - div_tax,   # growth the dividend taxes would have earned
        "adv": roth - after,
        "adv_never_sold": roth - taxable,
    }


def series(c=MEGA):
    """Year-by-year (Roth, taxable after a hypothetical sale) values, years 0..YEARS."""
    roth_s, tax_s = [0.0], [0.0]
    for n in range(1, YEARS + 1):
        b = run(c=c, years=n)
        roth_s.append(b["roth"])
        tax_s.append(b["taxable"])
    return roth_s, tax_s


def k(v):
    return f"${round(v / 1e3) + 0:,}K"


if __name__ == "__main__":
    b = run()
    print(f"room: {TOTAL_415C:,} - {DEFERRAL:,} - {EMPLOYER:,} employer = {MEGA:,}")
    print(f"contributed        {b['contributed']:>12,.0f}")
    print(f"Roth               {b['roth']:>12,.0f}")
    print(f"taxable pre-sale   {b['pre_sale']:>12,.0f}")
    print(f"taxable after sale {b['taxable']:>12,.0f}")
    print(f"advantage          {b['adv']:>12,.0f}")
    print(f"  dividend taxes paid      {b['div_tax']:>10,.0f}")
    print(f"  growth on those taxes    {b['div_growth']:>10,.0f}")
    print(f"  capital gains tax at sale{b['gain_tax']:>10,.0f}")
    print(f"never sold (or step-up)    {b['adv_never_sold']:>10,.0f}")
    print(f"in today's dollars at {INFLATION:.1%}: {b['adv'] / (1 + INFLATION) ** YEARS:,.0f}")
    ira = run(c=IRA)
    print(f"backdoor Roth IRA ({IRA:,}/yr): {ira['adv']:,.0f}  ratio {b['adv'] / ira['adv']:.2f}"
          f" vs contribution ratio {MEGA / IRA:.2f}")
    print("return:  " + "  ".join(f"{r:.0%} {k(run(r=r)['adv'])}" for r in (0.05, 0.07, 0.09)))
    print("tax:     " + "  ".join(f"{t:.1%} {k(run(tax=t)['adv'])}" for t in (0, 0.10, 0.15, 0.188, 0.238)))
    print("horizon: " + "  ".join(f"{n}y {k(run(years=n)['adv'])}" for n in (15, 25, 35)))
