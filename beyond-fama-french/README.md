# beyond-fama-french

Supports https://summitward.com/learn/beyond-fama-french-factor-models.

`models_analysis.py` measures two things:

1. How the factors of rival models overlap, January 1967 to December 2025
   (708 months): correlations among HML, AQR's HML Devil, RMW, CMA, the
   q-factor investment (I/A), ROE and expected-growth (EG) factors, AQR's QMJ
   and BAB, and momentum; and spanning regressions of each factor on the
   rival model (for example RMW on q5, R_ROE on Fama-French five factors plus
   momentum).
2. The same seven funds regressed on eight models over one window, January
   2014 to December 2025 (144 months): CAPM, FF3, Carhart, FF5, FF6
   (FF5 + momentum), q4, q5, and an "AQR set" of AQR's own US market, SMB,
   HML Devil, UMD, QMJ and BAB series. A ninth run swaps French's market
   factor into the AQR set. Funds: VTI, VBR, DFSVX, USMV, QUAL, MTUM and
   QCELX. AVUV is run separately from November 2019 because its history is
   shorter.

AQR does not publish an "AQR model". The AQR set is our grouping of series
from AQR's data library, the same factors Portfolio Visualizer offers as
add-ons.

```bash
pip install numpy pandas openpyxl yfinance
python3 models_analysis.py
```

The printed output of the run the guide quotes is in `output/output.txt`,
and every figure is in `output/results.json`.

Methods: fund returns are in excess of French RF (one-month T-bills) for
every model. Alpha is 12 times the monthly intercept, with classical and
Newey-West (Bartlett, 6 lags) t-statistics from a numpy OLS; section 3 of
the script repeats the fund regressions with 12 lags. With 12 lags, one
result crosses |t| = 1.96: DFSVX on the AQR set with French's market factor
moves from t = -1.75 to -2.07. No other significance call changes.

Two checks that matter for reading the output:

- global-q's `R_MKT` is already an excess return (January 1967: 8.19%
  against French Mkt-RF 8.15%). An early run of this script subtracted
  `R_F` a second time, which gave VTI a spurious q-model alpha of about
  +1.5% a year. The committed script does not.
- AQR's US market series averaged about 1 percentage point a year less than
  French's Mkt-RF over 2014-2025 (10.8% against 11.8%), with a correlation of
  0.998. That gap alone moves VTI's alpha under the AQR set, which is why the
  French-market variant is reported.

QCELX changed its principal investment strategies effective 4 May 2026
(AQR fund page). Every month in the 2014-2025 window is under the earlier
strategy.

These are descriptions of past windows, not forecasts. With 144 months,
alpha standard errors are roughly 0.6 to 4 percentage points a year
depending on the fund, so small differences between funds or models are
within noise.

## Data

- Kenneth R. French,
  [Data Library](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html),
  files built from the 202608 CRSP database, downloaded 2026-09-30; used with
  attribution. Committed in `data/`.
- Kewei Hou, Haitao Mo, Chen Xue and Lu Zhang,
  [q-factors data library](https://global-q.org/factors.html),
  `q5_factors_monthly_2025.csv` (1967-01 to 2025-12), downloaded
  2026-09-30; used with attribution. Committed in `data/`.
- AQR Capital Management,
  [Quality Minus Junk: Factors, Monthly](https://www.aqr.com/Insights/Datasets/Quality-Minus-Junk-Factors-Monthly)
  (sheets QMJ Factors, MKT, SMB, HML Devil, UMD) and
  [Betting Against Beta: Equity Factors, Monthly](https://www.aqr.com/Insights/Datasets/Betting-Against-Beta-Equity-Factors-Monthly),
  data through 2026-07. Not committed and not redistributed; the script
  downloads them. AQR reconstructs the full history on each update, so later
  downloads can move the figures.
- Yahoo Finance dividend-adjusted daily closes via yfinance, resampled to
  month end. Not committed; the script downloads them.

Downloads are cached in `.cache/`, which is not committed. Delete it to
refetch.
