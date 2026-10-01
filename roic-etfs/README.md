# roic-etfs

Supports https://summitward.com/learn/roic-return-on-invested-capital.

`roic_etf_loadings.py` asks whether ETFs that select stocks on return on
invested capital, or on ratings built on it, carry measurable exposure to the
Fama-French profitability factor (RMW). It regresses monthly excess returns of
MOAT, LCOW, GFLW, QUAL, AVUV and VTI on the five Fama-French factors plus
momentum over each fund's full history, reruns every fund on FF5 without
momentum, and splits MOAT and QUAL at January 2020.

```bash
pip install numpy pandas yfinance
python3 roic_etf_loadings.py
```

The printed output of the run the guide quotes is in `output/output.txt`, and
every figure is in `output/results.json`.

Methods: fund returns are month-end changes in Yahoo Finance adjusted closes,
in excess of French RF (one-month T-bills). Each fund's first month is dropped
because it can be partial. Alpha is 12 times the monthly intercept;
t-statistics are Newey-West with 6 lags, from a numpy OLS. French factors are
from the 202608 CRSP database and committed in `data/`; Yahoo prices are
cached in `.cache/` and not redistributed.

LCOW (from July 2025) and GFLW (from February 2025) have under two years of
returns, so their loadings carry little information. They are printed for
completeness.

These are descriptions of past windows, not forecasts.
