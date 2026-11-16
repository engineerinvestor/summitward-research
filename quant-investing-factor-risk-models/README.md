# quant-investing-factor-risk-models

Supports https://summitward.com/learn/quant-investing-factor-risk-models.

`analyze.py` asks how much of a factor fund's difference from the total market
is factor exposure, and how stable that difference is:

A. Each fund's monthly return minus VTI's, regressed on six factors (the
   Fama-French five plus momentum) over the common window October 2019 to
   September 2026 (84 months, set by AVUV's history) and over each fund's own
   history. In-sample OLS splits tracking-error variance exactly into a factor
   part, db' S_f db, and a residual part; the script asserts the identity. It
   reports tracking error, the factor share, residual tracking error, each
   factor's Euler contribution db_k (S_f db)_k, and residual correlations.
   Funds: VBR, AVUV, DFSVX, USMV, QUAL and MTUM against VTI.
A2. The same active returns with 11 industry-minus-market spreads from French's
   12 industry portfolios added, to see how much of what the six factors miss
   is industry tilts. Adjusted R-squared is reported beside raw R-squared.
B. Five mixes against VTI over the common window (70% VTI with 30% in AVUV, or
   split between AVUV and DFSVX, MTUM or QUAL; and 70% VTI with 30% USMV),
   monthly rebalanced, with the same decomposition.
C. A 30% DFSVX sleeve against the French market (Mkt-RF + RF), March 1993 to
   September 2026: trailing 60-month tracking error against the realized
   tracking error of the next 12 months, compared with the 90% band that
   i.i.d. normal sampling of a 12-month standard deviation would produce. The
   windows overlap, so shares of months are descriptive, not independent trials.
D. Pipeline check: AVUV minus VTI on the five factors over October 2019 to
   August 2026 reproduces the loadings published by
   `factor-loadings-expected-returns` to 2 dp (asserted).

It also writes `output/quant-risk-model.json`, the data behind the guide's
Tracking Error Decomposer: each fund's active loadings, the factor covariance
over the common window and since July 1963, the residual covariance across the
funds, and section C's series. The script checks that the calculator's formula
reproduces section B exactly.

Like a few other folders in this repo, the script needs third-party packages:

```bash
pip install numpy pandas yfinance
python3 analyze.py
```

Methods: every variance uses the n - 1 divisor; tracking error is sqrt(12)
times the monthly standard deviation of the return difference; alpha is 12
times the monthly intercept. Mixes rebalance monthly and are gross of trading
costs and taxes. DFSVX's "own history" against VTI starts in July 2001, VTI's
first full month. The Dimensional U.S. Small Cap Value ETF (DFSV) merged into
DFSVX as a share class on September 25, 2026; DFSVX's record is used here.

The printed output of the run the guide quotes is in `output/output.txt`.

## Data

- Kenneth R. French,
  [Data Library](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html),
  files built from the 202609 CRSP database, downloaded 2026-11-16; used with
  attribution. Committed in `data/`: `F-F_Research_Data_5_Factors_2x3.csv`,
  `F-F_Momentum_Factor.csv`, `12_Industry_Portfolios.csv`. Since its January
  2025 release the library uses CRSP's CIZ files, so figures can differ
  slightly from studies built on earlier releases.
- Yahoo Finance dividend-adjusted daily closes via yfinance, resampled to
  month end, read 2026-11-16. Not committed; the script downloads them.
  Yahoo revises adjusted closes, so a rerun can differ from the guide in the
  fourth decimal.

Downloads are cached in `.cache/`, which is not committed. Delete it to
refetch.
