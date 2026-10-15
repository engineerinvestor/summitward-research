# factor-loadings-expected-returns

Supports https://summitward.com/learn/factor-loadings-expected-returns.

`analyze.py` measures how precisely Fama-French loadings and premiums are
known, and what that does to the expected return a loading implies:

1. Premiums, July 1963 to August 2026 (758 months): the annualized arithmetic
   mean of Mkt-RF, SMB, HML, RMW, CMA and Mom, with classical and Newey-West
   (6 and 12 lag) standard errors, 95% intervals, the years of i.i.d. data a
   +/-1 and +/-2 point interval would need, and rolling 10-, 20- and 30-year
   means. Also the Newey-West covariance of the five factor means.
2. Five-factor loadings for VTI, VBR, DFSVX and AVUV over the common window
   October 2019 to August 2026 (83 months, set by AVUV's history) and over
   each fund's own history.
3. The implied edge of each small-value fund over VTI: the loading gap times
   the premium vector, under four premium scenarios (full history, style
   premia x 0.42, x 0.5, and zero), with standard errors from the premium
   covariance and from the loading-gap covariance. The loading gap comes from
   regressing the fund's return minus VTI's on the five factors.
4. Realized returns over the common window: CAGR, arithmetic mean and
   volatility for each fund, and the loading gap times the factor returns
   realized in that window.

```bash
pip install numpy pandas yfinance
python3 analyze.py
```

The printed output of the run the guide quotes is in `output/output.txt`,
and every figure is in `output/results.json`. The guide's calculator reads a
compact export of `results.json`.

Results the guide quotes:

| Item | Value |
| --- | --- |
| HML mean, 1963-07 to 2026-08 | 3.53%/yr, NW(12) SE 1.60, 95% 0.40 to 6.65 |
| SMB mean | 2.24%/yr, 95% -0.62 to 5.10 |
| Years of data for a +/-1 pt HML interval (i.i.d.) | 407 |
| AVUV value loading, 2019-10 to 2026-08 | 0.545, NW(6) SE 0.050 |
| AVUV implied edge over VTI, full premia | 4.81%/yr, 95% 1.51 to 8.11 |
| Same, style premia x 0.42 | 2.30%/yr, 95% 0.79 to 3.81 |
| AVUV vs VTI realized, 2019-10 to 2026-08 | arithmetic +1.93, CAGR +0.09 |
| HML trailing 20-year mean to 2026-08 | -1.16%/yr |

Methods: numpy OLS. Newey-West uses a Bartlett kernel; 12 lags for premium
means, 6 for fund regressions. Fund returns are in excess of French RF for
the loading regressions. Annualized means are 12 times the monthly mean. The
premium bands assume 1963-2026 is one stationary regime; post-publication
decay or a change in pricing would move them. Rolling windows overlap, so
shares of negative windows are descriptive.

Check against Summitward's factor-exposure blender, which hard-codes premia
for July 1963 to June 2026 of 7.21 / 2.24 / 3.58 / 2.87 / 2.95: the same
window in this data cut gives 7.21 / 2.25 / 3.56 / 2.91 / 2.93. The small
differences come from data-library revisions between cuts.

These are descriptions of past windows, not forecasts.

## Data

- Kenneth R. French,
  [Data Library](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html),
  `F-F_Research_Data_5_Factors_2x3` and `F-F_Momentum_Factor`, files built
  from the 202608 CRSP database (CIZ format, which the library has used since
  its January 2025 release), downloaded 2026-10-14; used with attribution.
  Committed in `data/`.
- Yahoo Finance dividend-adjusted daily closes via yfinance, resampled to
  month end. Not committed; the script downloads them.

Downloads are cached in `.cache/`, which is not committed. Delete it to
refetch.
