# lifecycle-investing-leverage

Guide: [Should Young Investors Use Leverage? Ayres and Nalebuff Re-Tested Through 2025](https://summitward.com/learn/lifecycle-investing-leverage)

Re-tests the leveraged lifecycle rule in Ian Ayres and Barry Nalebuff,
"Life-Cycle Investing and Leverage: Buying Stock on Margin Can Reduce
Retirement Risk" (NBER w14094, 2008; revised as "Diversification Across Time,"
*Journal of Portfolio Management*, 2013). The rule holds a fixed share of
savings plus the present value of future savings in stocks, borrowing up to
2x while that exceeds savings.

```bash
python3 extract_data.py       # rebuild data/lifecycle_leverage_monthly.json (pandas, xlrd)
python3 backtest.py           # all results; writes results.json, prints output.txt (numpy)
python3 validate_workbook.py  # exact check against the authors' workbook (openpyxl)
```

This folder needs numpy (and pandas/openpyxl for the two optional scripts), an
exception to the repo's standard-library rule.

## Data

- `data/lifecycle_leverage_monthly.json`: monthly real returns (month t to
  t+1), January 1871 to May 2026, deflated by Shiller CPI over the same month.
  - Stocks: Robert Shiller's real total-return S&P Composite
    ([shillerdata.com](https://shillerdata.com/), `ie_data.xls`, downloaded
    2026-10-17). The same series the authors' 2010 workbook uses.
  - Bonds: Shiller's real total bond returns (10-year Treasury).
  - Short rate: NBER Macrohistory call money rates
    ([m13001](https://data.nber.org/databases/macrohistory/rectdata/13/m13001.dat),
    copy in `data/m13001.dat`) to June 1926, then the one-month T-bill from
    the [Ken French data library](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html).
- `data/us_market_daily.json`: Ken French daily value-weighted market and
  T-bill returns, July 1926 to May 2026 (margin-call check).
- Wage profile: SSA Actuarial Note 2004.3, Table 6, medium earner, ages 21-64
  (the table the 2008 paper cites), grown 1.07% a year in real terms (2004
  Trustees Report: 3.9% wage growth over 2.8% CPI). Peak wage $58,782 at age
  51, as in the paper.
- The authors' own workbook (`Core_simulation.xlsx`, posted at
  [lifecycleinvesting.net](http://lifecycleinvesting.net/data.html)) carries no
  license; `validate_workbook.py` downloads it into `.cache/`, which is not
  committed.

## Design

Worker saves 4% of the wage profile monthly for 44 years from each January,
pays 0.30% a year, rebalances monthly. Leveraged rule: 88% of lifetime wealth
(the paper's target for relative risk aversion 2), cap 2x, future savings
discounted at 6.35%. Borrowing: T-bills plus a spread; before July 1926, call
money minus its 1926-1970 average gap over bills (1.38 points). Benchmarks:
100% stocks, a 90%-to-50% linear glide, and the same 88% rule capped at 100%
of savings (no borrowing).

The 6.35% discount rate is a finding of the replication. The paper's text
describes a 2.63% risk-free discount, but Table V is reproduced only with the
6.35% blended return listed under its Table IV. `backtest.py` reports the
2.63% version as a sensitivity.

## Output the guide quotes

See `output.txt` and `results.json`. Headlines:

- Replication of 2008 Table V (94 cohorts, 1871-2007), leveraged vs 100%
  stocks: mean +19.1% (paper +19.3%), median +27.0% (+27.0%), 10th percentile
  +23.6% (+23.4%), 89 of 94 cohorts ahead (89).
- 112 cohorts retiring 1915-2025, leveraged vs 100% stocks: at T-bills + 1.5%,
  107 of 112 ahead, median +27.9%; at + 8%, 20 of 112 ahead, median -6.1%.
- Same rule without borrowing vs 100% stocks: mean -4.6%, median -1.3%.
- Break-even spread over T-bills: 5.1 points (mean), 6.5 (median), 4.7
  (CRRA 4 certainty equivalent), 3.4 (worst cohort).
- Block bootstrap (10,000 paths, 5-year blocks) at + 1.5%: 85% of paths ahead
  of 100% stocks; certainty equivalent +14.3% at CRRA 2, +2.0% at 4, -22.4%
  at 8 (1-year blocks: +13.0%, -6.2%, -34.9%).
- `validate_workbook.py` (`validate_output.txt`): reproduces the workbook's
  Summary sheet to the dollar with the workbook's timing; the standard-timing
  engine is within 0.8% on every statistic.
