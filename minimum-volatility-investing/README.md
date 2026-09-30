# minimum-volatility-investing

Supports https://summitward.com/learn/minimum-volatility-investing.

`minvol_analysis.py` measures the low-risk anomaly and the live record of
minimum-volatility ETFs:

1. The security market line in Kenneth French's beta- and variance-sorted
   quintiles, July 1963 to August 2026, with sub-periods.
2. AQR's US Betting Against Beta factor, split at January 2014 (publication of
   Frazzini and Pedersen), with Fama-French five-factor plus momentum
   regressions.
3. USMV, SPLV, ACWV and BTAL against VTI and VT, November 2011 (USMV's first
   full month) to August 2026: CAGR, volatility, Sharpe, drawdowns, CAPM beta
   and alpha, capture ratios and calendar-year returns.
4. A VTI + T-bill mix matched to USMV's volatility and to its beta, and USMV
   levered to VTI's volatility and to beta 1 at two financing spreads.
5. Factor regressions for USMV, SPLV and ACWV, with and without BAB.
6. Interest-rate sensitivity of USMV minus VTI against IEF.
7. International min-vol funds against their parents and the February to
   March 2020 crash on daily closes.

It also writes `output/min-vol-chart.json`, the data behind the guide's two
charts.

Unlike most folders in this repo, the script needs third-party packages:

```bash
pip install numpy pandas openpyxl yfinance
python3 minvol_analysis.py
```

Methods: annualized mean is 12 times the monthly mean and volatility is
sqrt(12) times the monthly standard deviation; Sharpe ratios use excess
returns over French RF (one-month T-bills); alpha is 12 times the monthly
intercept, with classical and Newey-West (6 lags) t-statistics from a numpy
OLS. Hypothetical mixes rebalance monthly and are gross of trading costs and
taxes. The 78% and 66% mix weights come from USMV's realized volatility and
beta over the same window, so they use hindsight.

## Data

- Kenneth R. French,
  [Data Library](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html),
  files built from the 202608 CRSP database, downloaded 2026-09-29; used with
  attribution. Committed in `data/`:
  `F-F_Research_Data_5_Factors_2x3.csv`, `F-F_Momentum_Factor.csv`,
  `Portfolios_Formed_on_BETA.csv`, `Portfolios_Formed_on_VAR.csv`.
- AQR Capital Management,
  [Betting Against Beta: Equity Factors, Monthly](https://www.aqr.com/Insights/Datasets/Betting-Against-Beta-Equity-Factors-Monthly),
  USA column, data through 2026-07, downloaded 2026-09-29. Not committed; the
  script downloads it. AQR revises the full history on each update, so later
  downloads can move the BAB figures.
- Yahoo Finance dividend-adjusted daily closes via yfinance, resampled to
  month end, read 2026-09-29. Not committed; the script downloads them.
  Yahoo revises adjusted closes, so a rerun can differ from the guide in the
  fourth decimal of the chart data.

Downloads are cached in `.cache/`, which is not committed. Delete it to
refetch.

## Output quoted in the guide

Full printed output (run 2026-09-29) is in `output/output.txt` and every
number is in `output/results.json`. The sections the guide leans on most:

```
3. USMV live record 2011-11..2026-08
  USMV  2011-11..2026-08 n=178: CAGR 11.69% vol 11.1% Sharpe 0.91 MaxDD -19.1% (2020-01->2020-03, rec 2020-11)
  SPLV  2011-11..2026-08 n=178: CAGR 10.12% vol 11.7% Sharpe 0.75 MaxDD -21.4% (2020-01->2020-03, rec 2021-04)
  VTI   2011-11..2026-08 n=178: CAGR 14.64% vol 14.3% Sharpe 0.92 MaxDD -24.8% (2021-12->2022-09, rec 2023-12)
  ITOT  2011-11..2026-08 n=178: CAGR 14.68% vol 14.3% Sharpe 0.93 MaxDD -24.8% (2021-12->2022-09, rec 2023-12)
  ACWV  2011-11..2026-08 n=178: CAGR 8.75% vol 10.0% Sharpe 0.74 MaxDD -17.5% (2021-12->2022-09, rec 2024-03)
  VT    2011-11..2026-08 n=178: CAGR 11.44% vol 13.8% Sharpe 0.74 MaxDD -25.5% (2021-12->2022-09, rec 2023-12)
  BTAL  2011-11..2026-08 n=178: CAGR -2.94% vol 14.5% Sharpe -0.24 MaxDD -50.6% (2020-03->2026-06, rec None)
  IEF   2011-11..2026-08 n=178: CAGR 1.45% vol 6.2% Sharpe 0.01 MaxDD -23.2% (2020-07->2023-10, rec None)
  USMV vs VTI: beta 0.662 (t=21.4), alpha +1.41%/yr (t=0.89, NW t=0.94), R2 0.72, n=178 2011-11..2026-08
     up capture 72% (n=122), down capture 64% (n=56); beat VTI in 4/14 full calendar years; worst year 2023 -15.7pp; best 2022 +10.1pp; CAGR gap -2.95pp/yr
  SPLV vs VTI: beta 0.598 (t=14.2), alpha +0.89%/yr (t=0.41, NW t=0.44), R2 0.53, n=178 2011-11..2026-08
     up capture 64% (n=122), down capture 56% (n=56); beat VTI in 4/14 full calendar years; worst year 2023 -25.5pp; best 2022 +14.6pp; CAGR gap -4.52pp/yr
  USMV vs SPLV: beta 0.887 (t=34.2), alpha +2.36%/yr (t=2.20, NW t=2.47), R2 0.87, n=178 2011-11..2026-08
     up capture 96% (n=110), down capture 81% (n=68); beat SPLV in 10/14 full calendar years; worst year 2022 -4.5pp; best 2023 +9.8pp; CAGR gap +1.57pp/yr
  ACWV vs VT: beta 0.595 (t=19.3), alpha +1.23%/yr (t=0.82, NW t=0.88), R2 0.68, n=178 2011-11..2026-08
     up capture 65% (n=117), down capture 56% (n=59); beat VT in 4/14 full calendar years; worst year 2023 -13.8pp; best 2018 +8.3pp; CAGR gap -2.69pp/yr

  Calendar-year total returns (last year is YTD through 2026-08)
  year   USMV    SPLV     VTI  USMV-VTI  ACWV     VT   BTAL
  2012    10.8%   10.1%   16.5%    -5.6pp   10.7%   17.1%   -7.0%
  2013    25.1%   23.1%   33.4%    -8.4pp   17.4%   22.9%  -13.8%
  2014    16.3%   17.3%   12.5%    +3.8pp   10.6%    3.7%    8.7%
  2015     5.4%    4.0%    0.4%    +5.1pp    2.9%   -1.9%    0.1%
  2016    10.6%   10.1%   12.8%    -2.2pp    7.5%    8.5%   -4.7%
  2017    18.9%   17.3%   21.2%    -2.3pp   18.6%   24.5%   -2.1%
  2018     1.3%   -0.2%   -5.2%    +6.6pp   -1.4%   -9.8%   15.1%
  2019    27.7%   27.9%   30.7%    -3.0pp   21.0%   26.8%    1.1%
  2020     5.6%   -1.4%   21.1%   -15.4pp    3.0%   16.6%  -13.9%
  2021    20.8%   24.0%   25.7%    -4.8pp   14.0%   18.3%   -6.8%
  2022    -9.4%   -4.9%  -19.5%   +10.1pp  -10.4%  -18.0%   20.5%
  2023    10.3%    0.5%   26.0%   -15.7pp    8.2%   22.0%  -15.1%
  2024    15.7%   13.9%   23.8%    -8.1pp   11.4%   16.5%   12.8%
  2025     7.6%    4.1%   17.1%    -9.4pp   11.0%   22.4%  -20.2%
  2026*    8.6%    6.1%   13.5%    -4.9pp    8.1%   14.5%  -14.8%

==============================================================================
4. Hypothetical: VTI + cash vs USMV, and levered USMV vs VTI (monthly rebalanced, gross)
  USMV beta to VTI 0.662; vol USMV 11.13% vs VTI 14.29%
  strategy                                           CAGR    Vol Sharpe   MaxDD  beta
  VTI 66% + cash (beta-matched)                    10.32%   9.5%   0.92  -16.7%  0.66  (2011-11..2026-08 n=178, DD 2021-12->2022-09)
  VTI 78% + cash (vol-matched)                     11.83%  11.1%   0.92  -19.5%  0.78  (2011-11..2026-08 n=178, DD 2021-12->2022-09)
  USMV                                             11.69%  11.1%   0.91  -19.1%  0.66  (2011-11..2026-08 n=178, DD 2020-01->2020-03)
  VTI                                              14.64%  14.3%   0.92  -24.8%  1.00  (2011-11..2026-08 n=178, DD 2021-12->2022-09)
  USMV x1.28 (vol-matched), fin RF+0.5%            14.30%  14.3%   0.90  -24.2%  0.85  (2011-11..2026-08 n=178, DD 2020-01->2020-03)
  USMV x1.51 (beta 1), fin RF+0.5%                 16.34%  16.8%   0.90  -28.2%  1.00  (2011-11..2026-08 n=178, DD 2020-01->2020-03)
  USMV x1.28 (vol-matched), fin RF+1.5%            13.98%  14.3%   0.88  -24.2%  0.85  (2011-11..2026-08 n=178, DD 2020-01->2020-03)
  USMV x1.51 (beta 1), fin RF+1.5%                 15.75%  16.8%   0.87  -28.2%  1.00  (2011-11..2026-08 n=178, DD 2020-01->2020-03)


BAB FF5+Mom 1963-07..2013-12: alpha 2.55%/yr t 1.74 n 606 RMW 0.57
```
