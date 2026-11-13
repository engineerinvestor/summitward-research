# value-etfs-ai-stocks

Supports https://summitward.com/learn/value-etfs-ai-stocks.

`fetch_data.py` downloads the holdings snapshot and factor files into `data/`.
`analyze.py` reads them and measures, for nine value ETFs plus VTI, IWF, IWN
and SOXX:

1. **Holdings.** Number of stocks, GICS Information Technology and
   Communication Services weights, and the weights of selected AI-linked
   companies. AVGV is looked through to its six Avantis sleeves.
2. **Returns over the autumn 2026 AI selloff,** Oct 6, 2026 close (Nvidia's
   and IWF's closing high) to Nov 12, 2026 close, and year to date through
   Oct 30, 2026.
3. **Semiconductor sensitivity.** Weekly (Thursday-close) returns regressed on
   VTI and on SOXX minus VTI, Jun 29, 2023 (AVGV's first close) to Nov 12,
   2026, 176 weeks, Newey-West (4 lag) standard errors. Repeated ending Oct 1,
   2026, before the selloff. The full-sample coefficients are then applied to
   the selloff window to split each fund's return into market, semiconductor
   and residual parts, and fund-minus-fund differences (AVGV and AVLV against
   IWD, AVLV against VTV) are regressed on the same two factors.
4. **Fama-French five factors plus momentum,** monthly excess returns over RF,
   Newey-West (6 lag), each fund's own history and the common window Jan 2023
   to Sep 2026; loading gaps of each fund minus its index ETF (AVLV, DFLV and
   VLUE against IWD; AVUV and DFSV against IWN); realized return and tracking
   error against the index ETF.
5. **HML record** from the three-factor file: Jul 1926 to Dec 2007, Jan 2008 to
   Mar 2025, Jan 2008 to Sep 2026.
6. **AVUV against VTI,** Oct 2019 to Oct 2026.

```bash
pip install numpy pandas yfinance
python3 fetch_data.py   # optional: refetches today's files and overwrites data/
python3 analyze.py
```

The printed output of the run the guide quotes is in `output/output.txt`; every
figure is in `output/results.json`. `output/value-etfs-ai-stocks.json` is the
compact export behind the guide's chart.

## Data

- **Holdings (committed, `data/`).** iShares `latest-holdings.csv` for IWD,
  IWF, IVE, VLUE, SOXX and IWV, as of Nov 12, 2026. Avantis daily holdings
  embedded in each fund page (AVLV, AVUV, AVGV, AVMV, AVIV, AVDV, AVES), as of
  Nov 12, 2026. Dimensional daily holdings files for DFLV and DFSV, Nov 12,
  2026, and Dimensional fund-center characteristics (sector weights, aggregate
  price-to-book, weighted average profitability) as of Oct 31, 2026. Vanguard
  advisor-site holdings for VTV and VTI as of Sep 30, 2026, the latest
  month-end file posted when read on Nov 13, 2026. All read Nov 13, 2026.
  `fetch_data.py` only fetches the current files, so a rerun of it replaces
  this snapshot.
- **Ken French data library (committed).** Five factors (2x3), momentum and
  the three-factor file, cut through September 2026 (202609 CRSP), downloaded
  Nov 13, 2026.
- **Yahoo Finance (not committed).** Dividend-adjusted daily closes via
  yfinance, ending Nov 12, 2026, cached in `.cache/`. Yahoo revises adjusted
  closes after later distributions, so a rerun can move figures in the last
  decimal.

## Results the guide quotes

| Item | Value |
| --- | --- |
| VLUE Micron weight, Nov 12 | 18.63% |
| VTV Micron weight, Sep 30 (largest holding) | 4.56% |
| IWD Microsoft / Apple / Meta, Nov 12 | 5.05% / 6.12% / 0.65%; no Micron or Sandisk |
| AVLV Microsoft / Apple / Meta / Micron / Sandisk, Nov 12 | 3.40% / 2.91% / 2.93% / 2.59% / 0.39% |
| AVUV and DFSV, selected names | none held |
| Oct 6 to Nov 12 close: VTV / IWD / AVLV / AVUV / VLUE | +4.58% / +4.37% / +2.18% / +1.12% / -4.92% |
| Same window: VTI / IWF / SOXX / NVDA | -2.59% / -10.06% / -21.12% / -30.53% |
| YTD to Oct 30: IWD / IWF | +24.28% / -0.34% |
| Semiconductor coefficient, weekly 2023-07 to 2026-11: VLUE / IWD / AVLV / AVUV | +0.17 / -0.10 / -0.03 / -0.08 |
| Semiconductor term in the selloff, value funds except VLUE | +0.6 to +2.1 pts, against 2.5 to 7.2 pts of outperformance over VTI |
| VLUE predicted vs actual, selloff window | -5.25% vs -4.92% |
| AVGV minus IWD, weekly semiconductor gap | +0.065 (95% +0.037 to +0.092) |
| HML loading, own history: IWD / AVLV / DFLV / AVUV | 0.31 / 0.29 / 0.54 / 0.55 |
| HML loading, Jan 2023 to Sep 2026: AVLV / IWD / DFLV / VLUE | 0.32 / 0.41 / 0.54 / 0.60 |
| AVLV minus IWD, Oct 2021 to Sep 2026 | HML +0.00 (95% -0.14 to +0.15), RMW -0.04 (-0.14 to +0.06) |
| AVLV vs IWD, Oct 2021 to Oct 2026 | 15.11% vs 12.46% a year; beta gap +0.107 explains about 1.0 pt a year; tracking error 4.61% |
| AVUV minus IWN, Oct 2019 to Sep 2026 | HML +0.15 (+0.04 to +0.26), RMW +0.23 (+0.07 to +0.38) |
| HML mean x 12: Jul 1926 to Dec 2007 / Jan 2008 to Sep 2026 / Jul 1926 to Sep 2026 | 5.30% / -0.56% / 4.20% |
| AVUV vs VTI, Oct 2019 to Oct 2026 | 15.39% vs 15.20% a year; volatility 25.40% vs 16.96% |

## Limits

- Holdings dates differ: Vanguard's latest file is Sep 30; the rest are Nov 12.
  Sector weights use each issuer's GICS classification (Vanguard's sub-industry
  labels mapped to GICS sectors here; Dimensional's own Oct 31 sector table).
  For DFLV and DFSV, a CUSIP match to VTI's sub-industries is printed as a
  check; it leaves 0.95% and 3.77% of equity weight unmapped.
- The "selected companies" are a named list, not a definition of AI exposure.
  The semiconductor regression measures one return-based sensitivity, to SOXX
  relative to the market; it does not cover software or cloud businesses.
- The selloff window starts at a peak picked after the fact, which flatters
  any fund that held less of what fell.
- Loadings over 45 to 60 months carry wide intervals; compare funds with the
  gap regressions, not by subtracting point estimates. US factors do not
  describe AVGV, a global fund, so it is not in the factor tables.
- The weekly regressions use raw returns, not excess returns; at weekly
  frequency the risk-free rate is small relative to the slopes reported.

These are descriptions of past windows, not forecasts.
