# does-technical-analysis-work

Supports https://summitward.com/learn/does-technical-analysis-work.

Three scripts:

- `ta_rules.py` tests published moving-average trading rules on daily US
  stock market returns from 1928 to September 2026 and writes `results.json`
  and the compact `web_results.json` the guide's chart reads. Needs numpy.
- `overfitting_lab.py` is the reference implementation of the guide's
  Backtest Overfitting Lab; the browser component reproduces its
  `tool_check` output. Needs numpy.
- `render_random_walk_chart.py` draws the guide's hero image (chart-pattern
  lines fitted to a simulated random walk). Needs numpy and matplotlib.

`fetch_data.py` refreshes `data/` (needs pandas and xlrd; `--gspc` also needs
yfinance and caches Yahoo prices in the uncommitted `.cache/`).

```bash
python3 ta_rules.py            # about 5 minutes; --quick skips the bootstrap
python3 overfitting_lab.py     # tool_check; --zero-edge-test for the null check
python3 render_random_walk_chart.py
```

## The test

Rules, fixed in advance:

- Brock, Lakonishok and LeBaron's (1992) ten variable-length moving-average
  rules: short/long averages of 1/50, 1/150, 5/150, 1/200 and 2/200 days,
  each with a 0% and a 1% band. Long the market when the short average is
  above the long one by more than the band, in T-bills when below it by more
  than the band, otherwise unchanged.
- The 50/200-day golden cross.
- Faber's 10-month rule (month-end price above its 10-month average).
- 12-month time-series momentum (trailing 12 calendar months of market
  return above T-bills, checked at month end).

Conventions:

- Market total return is French's daily Mkt-RF plus a daily T-bill rate
  built from French's monthly one-month T-bill return, spread geometrically
  over each month's trading days. (French's daily RF column is rounded to
  whole basis points, which overstates 2025 cash returns by about a point.)
- Signals use a price index: total return minus Shiller's monthly S&P
  dividend yield (D/12/P) spread over each month's trading days. On the
  1/200-day rule this agrees with a signal built from ^GSPC closes on 96.7%
  of 24,554 days since 1928, against 94.8% for a total-return signal.
  Shiller's dividends after June 2026 are carried forward (`d_filled`).
- A signal from the close of day t is traded at the close of day t+1, so the
  first return earned is day t+2's. The same-close variant (first return day
  t+1) is reported separately because index autocorrelation from stale prices
  before 1987 makes it look much better.
- 5 basis points per unit of exposure traded; 0, 10 and 25 also reported.
- CAGR uses calendar years. Volatility and Sharpe annualize with the window's
  own trading days per year: the data has Saturday sessions through May 1952,
  so a fixed 252 understates early annual figures.
- Benchmarks: buy and hold; a static stock/T-bill mix at the rule's average
  exposure; a static mix at the rule's realized volatility. Both mixes
  rebalance daily at no cost and use hindsight weights.
- Uncertainty: stationary block bootstrap of paired days, 2,000 draws, mean
  blocks of 63 and 250 days and the Politis-White automatic length; White's
  Reality Check per window, both across the ten BLL rules (quoted in the guide)
  and across all 13 rules (in `results.json`).
- After tax (January 1993 on): single-lot total-market fund, $100,000 start;
  exits realize gains, short-term if held a year or less; wash sales applied
  (loss disallowed, added to basis, holding period carried over) when a loss
  exit is followed by re-entry within 30 days; dividends reinvested and taxed
  at the qualified rate unless earned in a holding spell under 61 days;
  T-bill interest taxed as ordinary income; each year's tax paid the next
  April out of the position. Losses net short against long and carry forward;
  the $3,000 ordinary offset and state tax are ignored. Today's rates are
  applied to every year.

## Output the guide quotes

Median across Brock et al.'s ten rules (percentage points a year of CAGR):

| Window | Buy and hold | Edge vs buy and hold | Edge vs same-exposure mix | Rules ahead of mix | Reality Check p (ten rules, vs mix) |
| --- | --- | --- | --- | --- | --- |
| 1928-1986 | 9.30% | +1.08 | +2.96 | 10 | 0.011 |
| 1933-1986 | 11.94% | -0.94 | +1.93 | 10 | 0.047 |
| 1962-2011 | 9.37% | -0.28 | +0.91 | 10 | 0.126 |
| 1987-1996 | 14.73% | -4.87 | -2.83 | 0 | 0.932 |
| 1987-2026 | 11.34% | -2.27 | -0.37 | 1 | 0.671 |
| 1993-2026 | 10.94% | -1.96 | -0.05 | 4 | 0.532 |
| 2013-2026 | 14.81% | -3.51 | -1.29 | 0 | 0.847 |

Lag-1 autocorrelation of daily market returns: +0.082 (1928-61), +0.230
(1962-86), -0.045 (1987-2026). Same-close execution lifts the 1928-86 median
edge over buy and hold from +1.08 to +1.84.

1993 to September 2026, 5 bp, next close:

| Rule | CAGR | Exposure | Exits/yr | vs buy and hold | vs same-exposure mix (90%) | Max drawdown |
| --- | --- | --- | --- | --- | --- | --- |
| Buy and hold | 10.94% | 100% | 0 | | | -54.7% |
| 1/200-day | 9.64% | 75% | 3.1 | -1.31 | +0.53 (-2.2, +3.4) | -22.9% |
| Golden cross | 10.29% | 75% | 0.4 | -0.66 | +1.14 (-1.6, +3.9) | -34.3% |
| Faber 10-month | 9.94% | 75% | 0.8 | -1.00 | +0.84 (-2.0, +3.8) | -21.6% |
| 12-month trend | 9.43% | 78% | 0.4 | -1.52 | +0.05 (-2.9, +3.1) | -40.4% |
| 1/50-day | 4.89% | 68% | 8.7 | -6.06 | -3.64 (-6.2, -1.1) | -30.8% |

A static 75% stock mix over the same period had a max drawdown of -43.4%.

After tax, $100,000 from January 1993, 32% bracket plus the 3.8% NIIT
(35.8% ordinary, 18.8% long-term and qualified dividends):

| | Before tax | After tax, liquidated | After-tax CAGR | Wash sales / loss exits |
| --- | --- | --- | --- | --- |
| Buy and hold | $3,324,845 | $2,506,559 | 10.02% | 0 / 0 |
| Golden cross | $2,722,089 | $1,567,935 | 8.50% | 0 / 4 |
| Faber 10-month | $2,445,912 | $1,319,403 | 7.95% | 4 / 9 |
| 12-month trend | $2,089,365 | $1,279,835 | 7.85% | 1 / 5 |
| 1/200-day | $2,228,376 | $1,180,902 | 7.59% | 52 / 68 |
| 1/50-day | $500,454 | $282,380 | 3.12% | 185 / 220 |

At 24% with no NIIT: buy and hold $2,660,487, 1/200-day $1,393,893.

Grid check (5 short x 6 long averages, no band): the best rule over 1928-86
was 2/100-day, +2.14 points a year over buy and hold (grid median +1.11);
over 1987-2026 it returned -2.75 against buy and hold (grid median -2.23)
and -0.69 against its same-exposure mix, 21st of 30.

Episodes (decline / next 12 months), market vs 1/200-day rule: 1987 crash
-33%/+28% vs -14%/+3%; 2000-02 -50%/+40% vs -19%/+23%; 2008-09 -55%/+75% vs
-9%/+23%; 2020 -34%/+87% vs -11%/+36%; 2022 -25%/+22% vs -11%/+1%.

`overfitting_lab.py` tool_check (seed 42, 30 rules, 5 bp, no premium):
featured market winner 5/100-day, backtest edge +1.36, live -5.28; over 300
markets the winner's mean backtest edge is +2.20 and live edge -0.43 points a
year, and it beat buy and hold live in 45%. Mean backtest edge by rules
searched (1, 6, 18, 30): -0.78, +1.01, +1.69, +2.20; live: -0.72, -0.82,
-0.63, -0.43. Zero-edge test (1/200-day alone, no cost, seed 7): backtest
-0.14, live +0.24.

Full output, including every rule, window, cost level, delay and signal
variant, is in `results.json`; `out_full.txt` is the printed report.

## Data

- Kenneth R. French,
  [Data Library](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html):
  `F-F_Research_Data_Factors_daily.csv` and `F-F_Research_Data_Factors.csv`
  from the 202609 CRSP update (read November 5, 2026). Used with attribution.
- Robert J. Shiller, [U.S. stock market data](https://shillerdata.com/)
  (`ie_data.xls`, read November 5, 2026), reduced to monthly price and
  dividends in `shiller_monthly.csv`. Used with attribution.
