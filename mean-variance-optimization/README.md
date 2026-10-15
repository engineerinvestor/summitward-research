# mean-variance-optimization

Supports https://summitward.com/learn/mean-variance-optimization-out-of-sample
(slug may change before publication).

Two questions:

1. When the true return distribution is known, how much does estimating it from
   a finite history cost a mean-variance investor, and at what history length
   does the estimated optimum beat equal weights (1/N)?
2. Does DeMiguel, Garlappi and Uppal's (2009) finding that no optimizer
   consistently beats 1/N out of sample hold on the 21 years of data since
   their sample ended, and on a do-it-yourself asset-class universe?

## Pre-registration (written 2026-10-15, before any evaluation was run)

Everything below was fixed before the script was first run. Any change made
after seeing results is listed under "Deviations" with the reason, and every
variant run is reported in `results.json`.

### Part A: known-parameter simulation

Monthly returns are drawn IID multivariate normal from stated annual
parameters (excess of cash; monthly mean = annual / 12, monthly covariance =
annual / 12). For each history length T in {5, 10, 20, 40, 100} years, 2,000
histories are drawn (seed 20261015). Each strategy chooses long-only, fully
invested weights; each choice is scored by its certainty equivalent (CE)
under the **true** parameters, CE = w'mu - (gamma/2) w'Sigma w, annualized.

Calibration 1, three assets (US stocks, international stocks, bonds):

| | Excess return | Volatility |
| --- | --- | --- |
| US stocks | 5.0% | 16% |
| International stocks | 5.0% | 17% |
| Bonds | 1.5% | 6% |

Correlations: US-international 0.80, each stock-bond pair 0.10.

Calibration 2 adds gold: excess return 1.0%, volatility 16%, correlation 0.0
with every other asset.

gamma is set so the true optimum in calibration 1 holds about 60% in stocks;
the same gamma is used for calibration 2. These are round, illustrative
inputs, not forecasts.

Strategies (solved by exhaustive search over a weight grid: 1% steps for three
assets, 2% for four, so the browser tool can reproduce them exactly):

- `true_optimum`: the optimum under the true parameters (the control).
- `equal_weight`: 1/N.
- `mv_sample`: sample mean and sample covariance.
- `mv_bayes_stein`: Jorion (1986) Bayes-Stein mean, sample covariance.
- `mv_lw_cov`: sample mean, Ledoit-Wolf (2004) constant-correlation shrinkage
  covariance.
- `min_variance`: minimum variance with the sample covariance.

Reported: mean and 5th/95th percentile CE loss against the true optimum (basis
points a year); share of histories in which each strategy's true CE beats
1/N; spread (5th to 95th percentile) of each asset's weight. Control check: the
grid optimum under the true parameters must match a continuous solver to
within the grid step.

### Part B1: ten US industry portfolios, monthly, July 1926 to August 2026

Data: Kenneth French 10 industry portfolios, value-weighted, and the one-month
T-bill rate from the Fama-French factors file (both the 202608 CRSP vintage).
Returns are in excess of the T-bill rate. Market capitalization for the
value-weighted benchmark = number of firms x average firm size at the start of
each month.

Walk-forward: at the end of month t the strategy uses only months t-M+1..t,
chooses weights, and earns month t+1's return. Base case M = 120 (DeMiguel et
al.'s window), rebalanced monthly. Robustness: M = 60.

Strategies:

1. `equal_weight`: 1/N, rebalanced monthly.
2. `market_cap`: industry market-cap weights (an index investor's portfolio).
3. `max_sharpe_sample`: long-only, fully invested tangency portfolio from the
   sample mean and covariance (the method retail "max Sharpe" optimizers use).
4. `mv_unconstrained`: DeMiguel et al.'s sample mean-variance, weights
   proportional to Sigma^-1 mu, normalized by |1' Sigma^-1 mu|.
5. `min_var_unconstrained`: global minimum variance, sample covariance.
6. `min_var_long_only`: long-only minimum variance, sample covariance.
7. `min_var_lw`: long-only minimum variance, Ledoit-Wolf constant-correlation
   covariance.
8. `max_sharpe_bs_lw`: long-only tangency, Bayes-Stein mean, Ledoit-Wolf
   covariance.
9. `max_sharpe_const_sharpe`: long-only tangency with every expected excess
   return set to the same Sharpe ratio times that asset's estimated volatility,
   Ledoit-Wolf covariance (a "plausible inputs" prior in the spirit of
   Kritzman, Page and Turkington 2010; the common Sharpe ratio cancels).
10. `max_sharpe_expanding`: long-only tangency from the sample mean and
    covariance of all data since July 1926 (Kritzman et al.'s long-sample
    argument).
11. `blend_half`: 50% `equal_weight` + 50% `max_sharpe_sample`, a fixed
    blend. This is a simple stand-in for Tu and Zhou (2011), not their
    estimated combination.

Evaluation periods (out-of-sample months):

- `dgu_window`: July 1973 to November 2004 (estimation from July 1963,
  matching DeMiguel et al.'s industry sample).
- `post_publication`: December 2004 to August 2026, the primary test.
- `pre_1963`: July 1936 to June 1963.
- `full`: July 1936 to August 2026.

Metrics: annualized Sharpe ratio of monthly excess returns (mean / sd x
sqrt(12)); CE at gamma = 1, annualized (12 x (mean - var/2)); turnover = mean
monthly sum of |w_target(t+1) - w_drifted(t)|, which counts both buys and
sells, as DeMiguel et al. do; Sharpe ratio net of 10 basis points per unit
traded; annualized volatility; maximum drawdown of the excess-return index;
average largest single weight.

Inference: for each strategy against `equal_weight`, a two-sided p-value for
the Sharpe-ratio difference from the Jobson-Korkie test with Memmel's (2003)
correction, and a 95% interval from a circular block bootstrap (12-month
blocks, 5,000 resamples, seed 20261015).

The primary result is the `post_publication` comparison of each optimizer
with `equal_weight` and `market_cap` on net Sharpe ratio and CE.

### Part B2: do-it-yourself asset classes, annual, 1928 to 2025

Data: Aswath Damodaran's annual returns (extracted 2026-05-20): S&P 500, US
small cap, 10-year Treasury bond, Baa corporate bond, gold, each in excess of
the 3-month T-bill. Real estate is excluded because the series is a home-price
index, not an investable total return.

Walk-forward as in B1 with annual rebalancing, a 20-year rolling window (base)
and an expanding window. Strategies: `equal_weight`, `sixty_forty` (60% S&P
500, 40% Treasury bond), and strategies 3, 6, 7, 8, 9, 10 and 11 from B1.
Out-of-sample years 1948 to 2025, also split 1948-1986 and 1987-2025. Same
metrics with annual data (Sharpe = mean / sd of annual excess returns), CE at
gamma = 1 and gamma = 5, and the same tests with 3-year bootstrap blocks.
With 78 annual observations the test has little power; this universe is
reported as a second check, not the headline.

### What is not modelled

Taxes, fund fees, borrowing, fat tails beyond what the historical data
contain, and any household goal. Results are gross of fees except for the
stated trading-cost assumption.

## Deviations from the pre-registration

None yet.
