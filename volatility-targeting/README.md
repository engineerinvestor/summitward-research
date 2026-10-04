# volatility-targeting

Supports https://summitward.com/learn/volatility-targeting.

`vt_analysis.py` tests a constant-volatility rule on the US stock market with
daily data from July 1926 to May 2026 and writes `results.json`. Standard
library only:

```bash
python3 vt_analysis.py
```

## The rule

Exposure to the market on day t is `min(cap, target / sigma)`, where `sigma`
is the annualized standard deviation of daily excess returns over the
trailing window ending on day t-1. The rest sits in one-month T-bills.
Exposure above 100% borrows at the T-bill rate plus a spread. Trading cost is
charged on the absolute daily change in exposure. The base case is a 21-day
window, 12% target, 100% cap and 5 basis points per unit traded.

Every comparison includes a static stock and T-bill mix whose weight is set so
its realized volatility equals the vol-targeted strategy's over the same
window. That weight uses hindsight; it exists to separate "less risk" from
"better risk-adjusted return".

The script also runs:

- the same rule from 1936 (excluding the Great Depression), from 1990 and from
  2000;
- a 12-cell grid of window (21, 63, 126 days) by target (8%, 10%, 12%, 15%);
- trading costs of 0, 5, 20 and 50 basis points;
- monthly and 10-point-band rebalancing;
- a levered version (16% target, 150% cap) at 0.5% and 1.5% borrowing spreads;
- an excess-return index version (exposure earns the market return minus
  T-bills and no cash credit), the construction used by many volatility-control
  indices in fixed indexed annuities, from 1995 with a 10% target and 150% cap;
- Moreira and Muir's monthly inverse-variance scaling, with the scaling
  constant from the full sample (look-ahead) and from an expanding window
  (real time);
- returns over named episodes.

Methods: CAGR from compounded daily returns; volatility is the daily standard
deviation times sqrt(252); Sharpe ratios use daily excess returns over the
T-bill rate; max drawdown is on daily wealth; vol-of-vol is the standard
deviation across month ends of trailing 63-day realized volatility. Results
are gross of taxes.

## Output the guide quotes (base case, 1927 to May 2026)

| | CAGR | Volatility | Sharpe | Max drawdown | Worst month | Vol-of-vol |
| --- | --- | --- | --- | --- | --- | --- |
| Buy and hold | 9.81% | 17.1% | 0.46 | -84.1% | -29.1% | 8.8% |
| Vol target 12% | 9.04% | 11.2% | 0.56 | -58.2% | -14.6% | 2.5% |
| Static 65% stock mix | 7.77% | 11.2% | 0.46 | -67.9% | -19.9% | 5.7% |

Turnover 2.75 times a year. From 2000: Sharpe 0.48 against 0.42; max
drawdown -37.5% against -35.7% for the matched static mix. From 1936: Sharpe
0.60 against 0.53; max drawdown -45.0% against -41.3%.

Full output, including the grid, cost sensitivity, episodes and the Moreira
and Muir comparison, is in `results.json`.

## Data

Kenneth R. French,
[Data Library](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html),
`F-F_Research_Data_Factors_daily`: value-weighted US market return (Mkt-RF
plus RF) and RF, converted to basis points in `data/us_market_daily.json`
(generated 2026-07-18, data through 2026-05-29). Used with attribution.
