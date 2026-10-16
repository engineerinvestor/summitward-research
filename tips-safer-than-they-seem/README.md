# tips-safer-than-they-seem

Guide: [Are TIPS Safer Than They Seem? We Re-Ran Elm's Spending-Risk Test](https://summitward.com/learn/tips-safer-than-they-seem)

Rebuilds the exhibit in Elm Wealth's
["TIPS: Safer Than They Seem"](https://elmwealth.com/tips-inflation-risk/)
(Victor Haghani and James White, October 14, 2026): the annual change in level
real spending a 50-year real annuity could buy for someone holding rolled
30-year TIPS, rolled 30-year nominal Treasuries, or T-bills, years ending
September 30. Also reruns it against a 30-year spending stream and prints the
duration table the guide quotes.

```bash
python3 replicate_elm_tips.py          # standard library only; reads data/
python3 replicate_elm_tips.py --fetch  # rebuild data/*.csv from the sources
```

## Data (read 2026-10-16)

- `data/annual.csv`: one row per September 30, 1999 to 2026.
  - Long real yield: U.S. Treasury
    [daily par real yield curve](https://home.treasury.gov/resource-center/data-chart-center/interest-rates/TextView?type=daily_treasury_real_yield_curve),
    30-year, from 2010-02-22 (public domain). Before then, the 20-year par
    TIPS yield (`TIPSPY20`) from the Federal Reserve's
    [Gurkaynak-Sack-Wright TIPS curve](https://www.federalreserve.gov/data/tips-yield-curve-and-inflation-compensation.htm),
    the longest maturity it publishes.
  - 30-year nominal par yield (`SVENPY30`) from the Fed's
    [GSW nominal curve](https://www.federalreserve.gov/data/nominal-yield-curve.htm).
  - CPI-U NSA (BLS `CUUR0000SA0`) for June, July and September (public domain).
- `data/bills.csv`: month-end 3-month Treasury CMT yields from the Treasury
  daily par yield curve.

The Fed curves are staff research products, not official statistical releases.

## Method

Each year a new 30-year bond is bought at par at that day's yield (TIPS coupon
floored at 0.125%) and repriced a year later as a 29-year bond at the new
yield. TIPS principal accretes with the reference CPI (31 CFR 356 App. B
interpolation of June and July for September 30) and returns are deflated by
September-to-September CPI. Bills roll monthly. Spending change is
`(1 + real return) * A(start) / A(end) - 1`, with `A` the level real annuity
factor at the long real yield. Flat-yield pricing throughout; no taxes or
trading costs. The Fed TIPS curve starts in January 1999, so the first window
is 1999-2000, one year later than Elm's.

## Output the guide quotes

See `output.txt`. Headline (years ending Sep 30, 2000-2026): spending standard
deviation 2.3% for TIPS, 6.3% for nominal bonds, 14.7% for T-bills (Elm: 2.8%,
6.7%, 14.2%); real market value standard deviation 14.7%, 12.6%, 2.3%.
Against a 30-year spending stream the TIPS figure rises to 6.7%.
