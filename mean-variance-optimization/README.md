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

1. **Part B2 gold (added 2026-10-15, after the first quick run).** Damodaran's
   gold series before 1972 is an administered price: it moves by less than 1%
   in most years from 1935 to 1967, with jumps at the 1933-34 revaluation.
   US residents also could not legally hold gold bullion from 1934 to 1974.
   The optimizers read the series as a near-riskless asset and the
   minimum-variance rules held up to 94% of the portfolio in it, so the
   pre-registered B2 run mostly measures that artifact. The pre-registered
   run is kept in `results.json` under `part_b2_asset_classes.with_gold`, and
   a variant without gold (S&P 500, small cap, Treasury bond, Baa corporate)
   is added under `ex_gold`, with the same windows, strategies and periods.
   The guide quotes `ex_gold`. This was a design error: the trap was already
   documented in the Summitward notes and should have been caught before
   pre-registration.

Note that in B2's expanding-window mode `max_sharpe_sample` and
`max_sharpe_expanding` are the same rule by construction.

## Running it

```bash
python3 mvo_retest.py          # about 70 seconds; writes results.json
python3 mvo_retest.py --quick  # 200 histories, 500 bootstraps; results_quick.json
```

Needs numpy and scipy. `tool_check` in `results.json` reproduces the browser
tool's default run (20 years, 300 histories, seed 42, mulberry32 and
Box-Muller), so the tool's displayed numbers can be checked against it:
mean shortfall 51.2 basis points, 1% of histories beating 1/N, and an average
in-sample ("promised") excess return of 5.38% against 3.69% at the true
parameters. The browser tool reproduced these figures exactly on 2026-10-15.

`export_replay.py` reruns the 120-month industry walk-forward for five rules
(1/N, market cap, max Sharpe with historical inputs, long-only minimum
variance, max Sharpe with equal Sharpe ratios) and writes `replay.json`: each
rule's monthly excess return, the T-bill rate, and the two optimizers'
quarterly weights. It stops unless the Sharpe ratios recomputed from the
rounded series match `results.json` to within 0.002 in all four periods. With
`--ts PATH` it also writes the data module behind the guide's replay chart.

## Replication check

Over DeMiguel et al.'s industry window (July 1973 to November 2004
out-of-sample, M = 120), this script gives monthly Sharpe ratios of 0.137 for
1/N, 0.151 for unconstrained minimum variance and 0.145 for long-only minimum
variance. Their December 2005 working paper reports 0.135, 0.155 and 0.143.
French's data have been revised since 2004, so exact agreement is not
expected. Their sample mean-variance strategy is negative in both (-0.084
here, -0.036 there).

## Output the guide quotes

Sharpe ratios annualized; CE at gamma = 1, % a year; p is the Memmel-corrected
Jobson-Korkie p-value against 1/N. Full output, including bootstrap
intervals, M = 60, CE net of costs and the weight paths, is in
`results.json`.

### Part A (2,000 histories per cell)

Calibration 1 (three assets), gamma = 2.5: true optimum 42% US, 22%
international, 36% bonds. 1/N falls 1.6 basis points a year short of it.
With 20 years of monthly data, sample mean-variance holds anywhere from 0% to
100% in stocks (5th to 95th percentile), loses 54 basis points a year of CE
against the true optimum on average, and beats 1/N in 1.3% of histories.

Calibration 2 (adds gold): 1/N falls 28 basis points short of the true
optimum. Share of histories in which sample mean-variance beats 1/N: 10%
(5 years), 13% (10), 20% (20), 29% (40), 55% (100). Its average loss is
still larger than 1/N's at 100 years (32 against 28 basis points).

### Part B1, ten industries, M = 120

| Strategy | Sharpe 1973-2004 | p | Sharpe Dec 2004-Aug 2026 | p | Vol 2004-26 | Turnover/month 2004-26 |
| --- | --- | --- | --- | --- | --- | --- |
| `equal_weight` | 0.475 | | 0.660 | | 15.0% | 0.025 |
| `market_cap` | 0.409 | 0.04 | 0.669 | 0.86 | 15.2% | 0.003 |
| `max_sharpe_sample` | 0.327 | 0.18 | 0.670 | 0.94 | 15.4% | 0.144 |
| `mv_unconstrained` | -0.290 | 0.001 | 0.394 | 0.34 | 23.2% | 0.858 |
| `min_var_unconstrained` | 0.524 | 0.71 | 0.656 | 0.98 | 11.9% | 0.143 |
| `min_var_long_only` | 0.501 | 0.80 | 0.726 | 0.58 | 11.8% | 0.050 |
| `min_var_lw` | 0.498 | 0.83 | 0.718 | 0.63 | 11.8% | 0.044 |
| `max_sharpe_bs_lw` | 0.334 | 0.14 | 0.672 | 0.92 | 12.9% | 0.110 |
| `max_sharpe_const_sharpe` | 0.500 | 0.63 | 0.703 | 0.44 | 13.6% | 0.046 |
| `max_sharpe_expanding` | 0.423 | 0.50 | 0.595 | 0.50 | 13.0% | 0.012 |
| `blend_half` | 0.415 | 0.32 | 0.699 | 0.58 | 14.4% | 0.080 |

In the post-publication period no strategy's Sharpe ratio differs from 1/N's
at conventional significance. Long-only minimum variance cut volatility from
15.0% to 11.8% at a similar Sharpe ratio. `max_sharpe_const_sharpe` is the
only rule at or above 1/N in all four periods (by 0.02 to 0.04), and none of
those gaps is significant.

In-sample illustration: a long-only max-Sharpe portfolio fit on January 1995
to December 2004 holds 39% health, 36% energy, 12% consumer non-durables and
the rest in three other industries, with an in-sample Sharpe ratio of 0.87
against 0.69 for 1/N. Held from January 2005 to August 2026 (rebalanced
monthly) it earned 0.63 against 0.65 for 1/N.

The M = 120 max-Sharpe portfolio at August 2026 holds 79% high-tech, 17%
utilities and 4% energy.

### Part B2, asset classes without gold, 20-year rolling window

| Strategy | Sharpe 1948-1986 | Sharpe 1987-2025 | Sharpe 1948-2025 | p (full) |
| --- | --- | --- | --- | --- |
| `equal_weight` | 0.459 | 0.574 | 0.514 | |
| `sixty_forty` | 0.439 | 0.632 | 0.532 | 0.77 |
| `max_sharpe_sample` | 0.249 | 0.630 | 0.373 | 0.15 |
| `min_var_long_only` | 0.078 | 0.583 | 0.324 | 0.09 |
| `min_var_lw` | 0.081 | 0.597 | 0.328 | 0.12 |
| `max_sharpe_bs_lw` | 0.243 | 0.669 | 0.352 | 0.12 |
| `max_sharpe_const_sharpe` | 0.211 | 0.551 | 0.389 | 0.13 |
| `max_sharpe_expanding` | 0.177 | 0.617 | 0.398 | 0.16 |
| `blend_half` | 0.379 | 0.626 | 0.481 | 0.53 |

In 1948 the 20-year max-Sharpe rule, estimated on 1928-1947 (when the
10-year Treasury's excess return had a Sharpe ratio of 0.70 against 0.24 for
the S&P 500), held 98% in Treasuries. From 1948 to 1981 the Treasury's
excess return averaged -1.45% a year.
