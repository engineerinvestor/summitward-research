# random-stocks-vs-index-fund

Supports https://summitward.com/learn/random-stocks-vs-index-fund.

Tests a rule some DIY investors use instead of an index fund: buy one randomly
chosen index constituent with each contribution and never sell.

| Script | What it does | Output |
| --- | --- | --- |
| `calibrate.py` | Current S&P 500 members from SPY's holdings file (State Street, as of Nov 17, 2026); 60 months of Yahoo total returns, Nov 2021 to Oct 2026; single-index regression of each stock on SPY | `output/calibration.json`, `output/per_stock.csv` |
| `simulate.py` | Random portfolios against an index fund in a model calibrated to the above: fixed-N buy and hold, and one random stock a month for 10, 20 and 30 years; baseline, measured beta/volatility (CAPM), and fat-tailed variants | `output/simulation.json` |
| `ew_vs_cw.py` | RSP (equal weight) against SPY (cap weight), June 2003 to October 2026: annualized returns by period and rolling 10-year differences | `output/ew_vs_cw.json` |
| `survivor_check.py` | Spread of random portfolios drawn from current members' actual returns against the model; equal-weighting today's members against RSP over the same five years | `output/survivor_check.json` |

Run in order (later scripts read the earlier ones' cache and output):

```bash
pip install numpy pandas openpyxl yfinance
python3 calibrate.py && python3 simulate.py && python3 ew_vs_cw.py && python3 survivor_check.py
```

Downloads are cached in `.cache/` (gitignored). The SPY holdings file is not
redistributed, and `per_stock.csv` omits fund weights; only statistics derived
from prices are committed.

## Model

Monthly arithmetic returns. The index return is normal with 9% expected annual
return (3% risk-free plus 6% premium, assumptions) and 15.47% volatility
(SPY, measured). Each stock earns the risk-free rate plus beta times the
index excess return plus an independent shock. Baseline: beta 1 for every
stock and shock volatility equal to the root-mean-square idiosyncratic
volatility of current members (30.91%), so random portfolios have the index's
expected return and any gap is noise. A portfolio's ending wealth is divided
by the index fund's ending wealth on the same contributions and market path.
No trading costs, taxes, or bankruptcies (the fat-tailed variant uses
Student-t shocks with 4 degrees of freedom). Seed 20261118.

Current members are survivors, so the calibration understates the
idiosyncratic risk of stocks drawn in the past. `survivor_check.py` finds the
actual five-year spread slightly wider than the model's.

## Output quoted in the guide

Calibration (492 stocks with 60 months): idiosyncratic volatility RMS 30.91%,
median 25.28%, interquartile range 21.0% to 31.8%; SPY volatility 15.47%;
503 equity securities, 500 companies (GOOGL/GOOG, FOXA/FOX, NWSA/NWS); top 10
companies 38.6% of SPY (effective number 45.9); at the October 30, 2026 close, 13
members traded above $1,000 a share and 43 above $500 (highest $5,958.56).

Fixed-N, bought once and held 10 years (baseline, 10,000 paths), ending wealth
relative to the index fund:

| N | Volatility (closed form) | 5th pct | Median | 95th pct | Trail by >10% | Trail by >25% |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 34.6% | 0.122 | 0.630 | 3.208 | 64.0% | 57.1% |
| 5 | 20.7% | 0.393 | 0.872 | 2.022 | 52.7% | 37.7% |
| 10 | 18.3% | 0.518 | 0.920 | 1.708 | 47.4% | 28.4% |
| 30 | 16.5% | 0.685 | 0.969 | 1.410 | 36.7% | 11.4% |
| 100 | 15.8% | 0.814 | 0.986 | 1.222 | 22.1% | 1.1% |

Ten stocks held 30 years: median 0.695, 5th to 95th percentile 0.228 to 2.753,
54.2% trail by more than 25%.

One random stock a month (baseline):

| Years | 5th pct | Median | 95th pct | Trail by >10% | Trail by >25% | Distinct | Median effective N | 0.03% fee drag avoided |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 10 | 0.858 | 0.992 | 1.163 | 13.3% | 0.07% | 106.7 | 57.0 | 0.17% |
| 20 | 0.808 | 0.980 | 1.242 | 24.0% | 1.1% | 190.9 | 53.4 | 0.37% |
| 30 | 0.747 | 0.964 | 1.361 | 32.6% | 5.2% | 256.7 | 40.5 | 0.61% |

Effective N by year (30-year run): 41.8 at 5, 56.9 at 10, peak 58.7 at 13, 57.9
at 15, 53.8 at 20, 46.8 at 25, 40.5 at 30. A 0.20% fund fee (RSP) costs 1.13%,
2.47% and 3.97% of ending wealth over 10, 20 and 30 years of monthly buying. Measured-pairs variant, 10 years: 0.837 to 1.171,
20.1% trail by more than 10%. Fat tails, 10 years: 0.862 to 1.159, 12.6%.

RSP vs SPY, June 2003 to October 2026: 10.86% vs 11.17% a year; June 2003 to
December 2012 8.44% vs 6.22%; 2013 to 2022 12.07% vs 12.45%; January 2023 to
October 2026 13.86% vs 20.93% (cumulative 2023 to 2025: 42.6% vs 85.5%;
January to October 2026: 15.3% vs 11.7%); RSP ahead in 46.3% of 162 rolling 10-year
windows; latest window -3.08 points a year. $1 a month for 120 months into RSP
vs SPY (162 overlapping windows ending 2013-05 to 2026-10): RSP account 0.840
times SPY's in the latest window, median 0.953, range 0.778 to 1.111, below 0.90
in 32.1% of windows.

Survivorship check, November 2021 to October 2026: standard deviation of log
relative wealth, actual vs model, 0.257 vs 0.239 (10 stocks) and 0.077 vs
0.076 (100 stocks); equal-weighting today's 492 members ended 1.075 times SPY (1.068
rebalanced quarterly), while RSP ended 0.855 times SPY.

Yahoo data read November 18, 2026. Re-running later extends nothing (the
windows are fixed) but Yahoo occasionally revises adjusted closes.
