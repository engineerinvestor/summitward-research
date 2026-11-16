# better-small-cap-value-fund

Supports https://summitward.com/learn/better-small-cap-value-fund.

`analyze.py` measures funds that each tried one way to improve on plain
small-cap value against AVUV, using the Fama-French five factors plus
momentum:

| Ticker | Fund | Idea |
| --- | --- | --- |
| AVUV | Avantis U.S. Small Cap Value ETF | Baseline |
| DFSVX | Dimensional U.S. Small Cap Value Portfolio (DFSV's fund since 2026-09-25) | Baseline |
| DFFVX | Dimensional U.S. Targeted Value Portfolio (DFAT's fund) | Wider, adds mid caps |
| BOSVX | Bridgeway Omni Small-Cap Value (BSVO's sibling mutual fund) | Deeper value, smaller stocks |
| CALF | Pacer US Small Cap Cash Cows ETF | Free-cash-flow yield |
| XSVM | Invesco S&P SmallCap Value with Momentum ETF | Value plus momentum |
| VBR, IWN | Vanguard and iShares small-cap value index ETFs | Plain index |
| AIEQ | Amplify AI Powered Equity ETF | Machine learning, all caps |

Sections:

- **A.** Common window October 2019 to September 2026 (84 months, set by
  AVUV): each fund's excess return on six factors with Newey-West (6 lag)
  standard errors; CAGR, volatility, maximum drawdown.
- **B.** Each fund minus AVUV: loading gaps, alpha gap, raw and residual
  tracking error, the t-statistic of the raw active mean.
- **C.** Implied edge over AVUV: loading gaps times July 1963 to September
  2026 factor means, minus the fee difference, with and without the market
  term, at full premiums and at 0.42x (McLean-Pontiff).
- **F.** After-the-fact attribution of each gap to the factor returns realized
  in the window.
- **D.** Own-history regressions by regime: DFSVX since 1993, DFFVX since 2000,
  BOSVX since 2011, CALF since 2017, XSVM since its June 2019 index change,
  AIEQ split at its January 2024 move from active management to an index.
- **E.** Pipeline check: AVUV's five-factor loadings over 2019-10 to 2026-08
  match those published by `factor-loadings-expected-returns` to three decimal
  places (the script asserts two); the fourth differs because that guide used
  the 202608 data cut.

```bash
pip install numpy pandas yfinance
python3 analyze.py
```

The printed output of the run the guide quotes is in `output/output.txt`,
everything is in `output/results.json`, and the compact file the guide's
tables and calculator read is `output/better-scv-scoreboard.json`.

Results the guide quotes (October 2019 to September 2026 unless noted):

| Item | Value |
| --- | --- |
| CAGR: AVUV, BOSVX, DFSVX, DFFVX, XSVM, CALF | 14.81, 14.07, 13.70, 13.41, 13.37, 13.14% |
| CAGR: VBR, IWN, AIEQ, VTI | 10.98, 10.42, 10.18, 15.52% |
| Alpha gap vs AVUV, five small-value alternatives | -0.79 to +0.57%/yr, t -0.85 to +0.42 |
| Tracking error vs AVUV: DFSVX, BOSVX, DFFVX, CALF, XSVM | 3.53, 3.83, 3.56, 8.82, 10.27% |
| Style-only implied edge vs AVUV, full premiums: XSVM | +1.28%/yr, 95% -1.86 to +4.43 |
| Six-factor alpha: VBR, IWN | -2.87 (t -3.05), -2.31 (t -2.57)%/yr |
| Market loading gap x realized market return, DFSVX/DFFVX/BOSVX/CALF | -1.04, -0.93, -1.10, -0.95 pts/yr |
| SMB mean in window | -1.93%/yr |
| AIEQ vs VTI, Nov 2017 to Sep 2026 | 9.69 vs 14.14%/yr; alpha -2.42 (t -1.04) |
| BOSVX own history since Sep 2011 | alpha -0.20%/yr (t -0.21) |

Methods: numpy OLS with an intercept; Newey-West uses a Bartlett kernel with
6 lags for fund regressions and 12 for premium means. Fund returns are in
excess of the French T-bill rate for loading regressions; active returns
(fund minus AVUV) need no T-bill adjustment. Annualized means are 12 times the
monthly mean; tracking error is the monthly standard deviation times the
square root of 12. Fees are current net expense ratios (November 2026) and are
used only for the fee difference in section C; fund returns are already net
of fees.

These are descriptions of past windows, not forecasts.

## Data

- Kenneth R. French,
  [Data Library](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html),
  `F-F_Research_Data_5_Factors_2x3` and `F-F_Momentum_Factor`, files built
  from the 202609 CRSP database (CIZ format), the same files as
  `quant-investing-factor-risk-models`; used with attribution. Committed in
  `data/`.
- Yahoo Finance dividend-adjusted daily closes via yfinance, resampled to
  month end, read 2026-11-16. Not committed; the script downloads them into
  `.cache/`, which is not committed. Delete it to refetch (later reads extend
  and may revise the series).
