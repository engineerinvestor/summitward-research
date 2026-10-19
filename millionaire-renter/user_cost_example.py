"""Year-one economic cost of owning vs. renting for one modeled high-income couple.

Supports the worked example in https://summitward.com/learn/millionaire-renter.

Framework: the housing user cost of Himmelberg, Mayer and Sinai (2005, JEP 19(4)),
annual cost = forgone return on equity + mortgage interest + property tax
+ insurance + maintenance/depreciation + amortized transaction costs
- income-tax savings - expected appreciation. Principal repayment is not a
cost: it moves cash from the bank account into home equity.

Rates as of mid-October 2026:
  - 30-year fixed mortgage 7.40%, Freddie Mac PMMS, week of 2026-10-15
  - 10-year Treasury 5.19%, 10-year breakeven inflation 2.32%, Summitward
    market feed (Treasury par yield curve), 2026-10-14

Tax rules for 2026 (IRS Pub 505, Pub 936): SALT deduction cap $40,400 phased
down by 30% of MAGI above $505,000 to a $10,000 floor (reached near $606,333);
mortgage interest deductible on the first $750,000 of acquisition debt;
standard deduction $32,200 married filing jointly.

Every input is an assumption for one scenario. Change them and the answer moves.
Run: python3 user_cost_example.py   (stdlib only)
"""

from __future__ import annotations

PRICE = 1_500_000
DOWN = 0.20
MORTGAGE_RATE = 0.0740  # PMMS 30-year, 2026-10-15
TERM_YEARS = 30
PROPERTY_TAX = 0.010  # of value
INSURANCE = 0.0035  # of value
MAINTENANCE = 0.020  # maintenance + depreciation + HOA, of value (HMS use 2.5%)
BUY_COST = 0.02  # closing costs, of price
SELL_COST = 0.06  # commissions and transfer costs, of sale price
APPRECIATION = 0.03  # nominal; 2.32% breakeven inflation + ~0.7% real
TREASURY_10Y = 0.0519
EQUITY_RETURN = 0.075  # nominal expected stock return assumption
FED_MARGINAL = 0.35
NIIT = 0.038
STATE_MARGINAL = 0.0  # state tax on investment income; 0 here, see note below
QDI_RATE = 0.20 + NIIT  # long-term gains / qualified dividends
TAX_DRAG_EQUITY = 0.006  # annual tax drag on a taxable index portfolio (~2% yield x 23.8% + small gains)
STD_DEDUCTION = 32_200
SALT_FLOOR = 10_000  # MAGI above ~$606k
DEBT_CAP = 750_000
HOLDS = (5, 10, 20)


def year_one_interest(loan: float, rate: float, years: int) -> float:
    r = rate / 12
    n = years * 12
    pmt = loan * r / (1 - (1 + r) ** -n)
    bal, interest = loan, 0.0
    for _ in range(12):
        i = bal * r
        interest += i
        bal -= pmt - i
    return interest


def tax_saving(interest: float, loan: float) -> float:
    """Incremental federal tax saved by owning vs. the same couple renting.

    The couple's state income tax already exceeds the $10,000 SALT floor, so
    property tax adds no deduction. As renters they take the standard
    deduction; as owners they itemize deductible interest plus $10,000 SALT.
    """
    deductible_interest = interest * min(1.0, DEBT_CAP / loan) if loan else 0.0
    itemized = deductible_interest + SALT_FLOOR
    return max(0.0, itemized - STD_DEDUCTION) * FED_MARGINAL


def scenario(label: str, down: float, opp_rate: float, hold: int) -> dict:
    equity = PRICE * down + PRICE * BUY_COST
    loan = PRICE * (1 - down)
    interest = year_one_interest(loan, MORTGAGE_RATE, TERM_YEARS) if loan else 0.0
    rows = {
        "forgone return on equity": equity * opp_rate,
        "mortgage interest": interest,
        "property tax": PRICE * PROPERTY_TAX,
        "insurance": PRICE * INSURANCE,
        "maintenance, depreciation, HOA": PRICE * MAINTENANCE,
        f"buy+sell costs spread over {hold} yrs": PRICE * (BUY_COST + SELL_COST) / hold,
        "federal tax saving": -tax_saving(interest, loan),
        "expected appreciation": -PRICE * APPRECIATION,
    }
    total = sum(rows.values())
    return {"label": label, "rows": rows, "total": total, "user_cost": total / PRICE,
            "breakeven_rent_month": total / 12, "price_to_annual_rent": PRICE / total}  # fmt: skip


def main() -> None:
    safe_after_tax = TREASURY_10Y * (1 - FED_MARGINAL - NIIT - STATE_MARGINAL)
    stock_after_tax = EQUITY_RETURN - TAX_DRAG_EQUITY
    print(
        f"After-tax opportunity cost: Treasuries {safe_after_tax:.2%}, stocks {stock_after_tax:.2%}"
    )
    print(
        f"Year-one interest on ${PRICE * (1 - DOWN):,.0f}: ${year_one_interest(PRICE * (1 - DOWN), MORTGAGE_RATE, TERM_YEARS):,.0f}"
    )
    for hold in HOLDS:
        print(f"\n===== hold {hold} years =====")
        for label, down, opp in [
            ("20% down, equity earns Treasury rate", DOWN, safe_after_tax),
            ("20% down, equity earns stock rate", DOWN, stock_after_tax),
            ("all cash, cash earns Treasury rate", 1.0, safe_after_tax),
            ("all cash, cash earns stock rate", 1.0, stock_after_tax),
        ]:
            s = scenario(label, down, opp, hold)
            print(f"\n{label}")
            if hold == 10:
                for k, v in s["rows"].items():
                    print(f"   {k:40s} {v:>10,.0f}")
            print(f"   {'TOTAL annual economic cost':40s} {s['total']:>10,.0f}   user cost {s['user_cost']:.2%}"
                  f"   break-even rent ${s['breakeven_rent_month']:,.0f}/mo   price/rent {s['price_to_annual_rent']:.1f}x")  # fmt: skip


if __name__ == "__main__":
    main()
