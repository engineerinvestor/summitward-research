# quality-minus-junk

Supports https://summitward.com/learn/quality-minus-junk.

`qmj_analysis.py` measures three things:

1. AQR's US and Global Quality Minus Junk factors by period: the 1957-2016
   sample of Asness, Frazzini and Pedersen (2019), and January 2017 onward,
   after that sample ends. It also reruns the post-2016 figures without July
   2026, the largest month in the US file, to show how much one month moves
   the average.
2. QMJ regressed on Fama-French factors: four-factor (market, size, value,
   momentum) from July 1957 as a check against the paper's Table 4, and
   five-factor plus momentum, with and without AQR's Betting Against Beta,
   before and after 2017.
3. Loadings of AVUV, DFSV, DFAT, IJS, VBR, IWN, QUAL, SPHQ, JQUA and VTI on
   three models: FF5 + momentum (RMW is the profitability loading), FF3 +
   momentum + QMJ (the quality loading), and FF5 + momentum + QMJ (whether
   QMJ adds anything once RMW is in the model). Each fund is run over its own
   history and over a common window from November 2019.

The script needs third-party packages:

```bash
pip install numpy pandas openpyxl yfinance
python3 qmj_analysis.py
```

The printed output of the run the guide quotes is in `output/output.txt`, and
every figure is in `output/results.json`.

Methods: annualized mean is 12 times the monthly mean and volatility is
sqrt(12) times the monthly standard deviation; QMJ and BAB are
self-financing long/short returns, so their Sharpe ratios need no risk-free
adjustment. Fund returns are in excess of French RF (one-month T-bills).
Alpha is 12 times the monthly intercept, with classical and Newey-West
(6 lags) t-statistics from a numpy OLS. Each fund's first month is dropped
in the own-window runs because it can be a partial month.

These are descriptions of past windows, not forecasts. The fund windows are
short (52 months for DFSV, 81 months for the common window), so the
loadings carry wide standard errors.

## Data

- Kenneth R. French,
  [Data Library](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html),
  files built from the 202608 CRSP database, downloaded 2026-09-29; used with
  attribution. Committed in `data/`: `F-F_Research_Data_Factors.csv`,
  `F-F_Research_Data_5_Factors_2x3.csv`, `F-F_Momentum_Factor.csv`.
- AQR Capital Management,
  [Quality Minus Junk: Factors, Monthly](https://www.aqr.com/Insights/Datasets/Quality-Minus-Junk-Factors-Monthly)
  and
  [Betting Against Beta: Equity Factors, Monthly](https://www.aqr.com/Insights/Datasets/Betting-Against-Beta-Equity-Factors-Monthly),
  data through 2026-07, downloaded 2026-09-29. Not committed and not
  redistributed; the script downloads them. AQR reconstructs the full history
  on each update, so later downloads can move every QMJ figure, and the
  figures here differ from the published paper's tables.
- Yahoo Finance dividend-adjusted daily closes via yfinance, resampled to
  month end, read 2026-09-29. Not committed; the script downloads them.

Downloads are cached in `.cache/`, which is not committed. Delete it to
refetch.
