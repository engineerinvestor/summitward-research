# idiosyncratic-risk

Supports https://summitward.com/learn/idiosyncratic-risk.

`analyze.py` measures how much of Nvidia's November 2026 CEO exit was
company-specific, and how much company-specific risk reaches index funds:

1. **Event study.** NVDA daily abnormal returns from Oct 29, 2026 (first spy
   report) through Nov 12, 2026 (resignation announced), from market models fitted
   by OLS on the 250 trading days ending Oct 27, 2026. Four benchmarks: SPY, SOXX,
   SPY + SOXX, and the PHLX Semiconductor index (^SOX) as a robustness check.
   Cumulative abnormal returns are reported for Oct 29 to Nov 6, Nov 9 to Nov 12,
   and the whole window, with t-statistics equal to the CAR divided by the
   estimation-window residual standard deviation times the square root of the
   window length.
2. **Index contribution.** Nvidia's daily SPY weight, backed out from the Nov 11,
   2026 State Street holdings file by relative price (weight x NVDA/SPY price
   ratio; exact when share counts and index membership do not change), times its
   raw and abnormal daily returns.
3. **Effective number of companies,** 1 / sum of squared weights, for SPY (State
   Street), the iShares MSCI ACWI ETF and the iShares S&P SmallCap 600 Value ETF
   (IJS), with share classes of one issuer combined. The equal-weight S&P 500
   (RSP) is treated as 1/N at rebalance.
4. **Nvidia's company-specific share of variance** for each holding,
   (w_NVDA x sigma_eps)^2 / sigma_holding^2, where sigma_eps is the annualized
   residual volatility of weekly NVDA returns regressed on ACWI (and on ACWI plus
   SOXX), over the three and five years ending Oct 23, 2026. The share assumes
   Nvidia's residual is uncorrelated with the rest of each fund.

The script writes `output/idiosyncratic-risk.json`, which holds every figure the
guide quotes and the data behind its two charts.

Like a few other folders in this repo, it needs third-party packages:

```bash
pip install numpy pandas openpyxl yfinance
python3 analyze.py
```

## Data

- Yahoo Finance dividend-adjusted daily closes via yfinance for NVDA, SPY, SOXX,
  ^SOX, ACWI, VT, IJS and RSP, read 2026-11-12 after the close. Not committed;
  the script downloads them. Yahoo revises adjusted closes, so a rerun can move
  figures in the last decimal.
- State Street Global Advisors, SPY daily holdings file (as of 11-Nov-2026), and
  iShares holdings files for ACWI (as of Nov 10, 2026) and IJS (as of Nov 11,
  2026). Not committed; the script downloads the current files, so a later rerun
  uses later holdings. The figures in the guide use the dates above.

Downloads are cached in `.cache/`, which is not committed. Delete it to refetch.

## Limits

SPY and SOXX hold Nvidia, so part of Nvidia's own move sits inside each
benchmark and the abnormal returns are slightly understated. The disclosure
sequence ran over two weeks, so no single date isolates the news. An event study
measures repricing on the news, not eventual damage to the business.
