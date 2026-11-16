# is-the-value-premium-back

Supports https://summitward.com/learn/is-the-value-premium-back.

`analyze.py` measures what drove the 2025-26 run in systematic small-value
funds. The value-spread figures in the same guide come from
[`../value-spread`](../value-spread).

```bash
pip install numpy pandas yfinance
python3 analyze.py
```

## Sections

1. **Issuer NAV returns as published** for AVUV, AVDV, QVAL and their
   benchmarks (Oct 31, 2026) and DFSV (Sep 30, 2026), typed in with source
   URLs. Not recomputed.
2. **DFSV calendar returns before and after the Sep 25, 2026 merger** of the
   stand-alone ETF into the U.S. Small Cap Value Portfolio (DFSVX) as an ETF
   share class: Dimensional's Dec 31, 2025 fact sheet against its Sep 30, 2026
   fact sheet.
3. **Matched-window market-price returns,** Sep 30, 2019 to Oct 31, 2026 (85
   months; AVUV and AVDV began trading Sep 24, 2019), and trailing 12 and 36
   months: CAGR, annualized monthly volatility, worst month-end drawdown.
   Rolling 12-month windows in which AVUV beat VTI, VT and IWN. Extra windows:
   AVUV and AVDV from Oct 2023 to Oct 2025 (where AVDV's three-year lead was
   built), the single months Oct 2025 and Oct 2026, and Yahoo calendar-year
   returns for the old DFSV ETF and DFSVX. Also recorded: Sep 30, 2026 issuer
   figures, AVDV's Nov 13 premium to NAV, AVES's 2026 distribution estimate
   and the X post's Portfolio Visualizer table.
4. **Out-of-sample factor attribution.** Fama-French five factors plus
   momentum, monthly excess returns, Newey-West (6 lag). Loadings estimated
   Oct 2019 to Sep 2025 (72 months) are multiplied by each factor's summed
   monthly return over Oct 2025 to Sep 2026; the residual is the realized
   excess return minus that implied figure. This is an after-the-fact
   attribution: the loadings are estimated beforehand, the factor returns are
   the ones the year delivered. U.S. factors for AVUV, DFSVX, IWN and
   VTI; developed ex-US factors for AVDV. The AVUV-minus-IWN gap is
   attributed with loadings from a regression of the return difference. Also
   the RMW trailing 12-month sum against every 12-month window since 1963.
5. **Full-window intercepts,** Oct 2019 to Sep 2026 (84 months), with 95%
   Newey-West intervals.

## Output the guide quotes

- AVUV, Oct 2025 to Sep 2026: loadings implied 13.5 points of excess return,
  summed monthly (market 11.5, value 5.3, size 1.3, profitability -4.3, other
  -0.3); actual 15.4; residual volatility 4.2% a year over the estimation
  window.
- RMW summed -15.6% over the 12 months, at or below all but 2.7% of 748
  rolling windows since mid-1964 (worst -44.5%, year to Feb 2000).
- AVUV minus IWN: implied -1.9 points, actual -0.4 (sums of monthly returns).
- Since Sep 2019 (market prices): AVUV 15.39% a year, VTI 15.20%, VT 13.04%,
  IWN 10.67%; AVUV's worst month-end drawdown -42.4%.
- Full-window intercepts: AVUV +0.51% a year (95% interval -2.09% to +3.12%),
  IWN -2.31% (-4.08% to -0.55%).

The printed run is `output/output.txt`; every figure is in
`output/results.json`; `output/is-the-value-premium-back.json` is the compact
export behind the guide's attribution chart.

## Data

- **Ken French data library (committed, `data/`).** Five factors (2x3),
  momentum, developed ex-US five factors and momentum, 202609 vintage,
  downloaded Nov 15, 2026.
- **Yahoo Finance (not committed).** Dividend-adjusted daily closes via
  yfinance through Nov 13, 2026, cached in `.cache/`. Yahoo revises adjusted
  closes after later distributions, so a rerun can move the last decimal.
- **Issuer figures** are typed into `analyze.py` with their URLs and as-of
  dates.

Nothing here is a forecast. Every figure describes a named past window.
