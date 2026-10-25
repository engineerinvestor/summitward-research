# voo-schd-qqq

Numbers behind four Summitward comparison pages:
<https://summitward.com/compare/voo-vs-schd>,
<https://summitward.com/compare/voo-vs-qqq>,
<https://summitward.com/compare/schd-vs-qqq> and
<https://summitward.com/compare/voo-vs-schd-vs-qqq>.

```bash
python3 voo-schd-qqq/fetch_data.py   # refreshes the four data files (needs yfinance)
python3 voo-schd-qqq/analyze.py      # stdlib only; prints every number the pages quote
```

## Data

| File | Source | As of |
|---|---|---|
| `data/closes.csv` | Yahoo Finance daily closes, VOO SCHD QQQ (split-adjusted, not dividend-adjusted) | 2011-10-20 to 2026-09-30 |
| `data/distributions.csv` | Yahoo Finance distributions per share by ex-date | same window |
| `data/long_closes.csv` | Yahoo Finance daily closes, QQQ and SPY | 1999-03-10 to 2026-09-30 |
| `data/long_distributions.csv` | Yahoo Finance distributions, QQQ and SPY | same window |
| `data/qqq_holdings_2026-10-23.csv` | Invesco QQQ page, expanded holdings list (100 lines, 99.74% of assets), copied by hand because the export is a download | 2026-10-23 |
| `data/schd_holdings_2026-10-13.csv` | Schwab, copied from the `voo-schd-overlap` folder | 2026-10-13 |

SPY stands in for VOO before VOO's September 2010 launch; both track the S&P 500.

## Checks against the issuers (all for periods ending 2026-09-30)

| Figure | This script | Issuer |
|---|---|---|
| SCHD 10-yr / 5-yr / 2026 YTD | 12.45% / 9.47% / 21.5% | Schwab 12.44% / 9.48% / 21.46% (NAV) |
| VOO 10-yr / 5-yr / 2026 YTD | 15.30% / 13.77% / 12.7% | Vanguard 15.30% / 13.76% / 12.74% (market price) |
| QQQ 10-yr / since 1999 | 20.89% / 10.88% | Invesco 20.91% / 10.88% (NAV) |
| QQQ 10-yr after tax held / sold | 20.70% / 18.08% | Invesco 20.70% / 18.08% |
| SCHD trailing 12-month yield | 3.24% | Schwab 3.24% |

## Method

Total returns are built from closes and distributions, with each distribution
reinvested at its ex-date close. Volatility is the standard deviation of
month-end returns times the square root of 12; worst declines use daily closes.
After-tax returns follow the SEC method at 23.8% (the top qualified-dividend
rate plus the net investment income tax), treat every dividend as qualified,
and assume no capital-gain distributions; the "after sale" figure also taxes
the gain over basis at 23.8% at the end. The SCHD-QQQ overlap sums the
smaller weight in each shared stock after dropping QQQ's cash and futures
lines; the two holdings dates differ by ten days and weights are not repriced.

## Full output of `analyze.py`

```
Window: 2011-10-20 to 2026-09-30

Trailing 12-month distribution yield at 2026-09-30
  VOO: 1.06%
  SCHD: 3.24%
  QQQ: 0.42%

Monthly series 2011-10 to 2026-09 (179 months)

Since SCHD inception: 2011-10-20 to 2026-09-30 (14.95 yrs)
fund   annual   $10k ->    vol   max DD  DD trough
VOO    15.10%    81,803  13.9%   -34.0% 2020-03-23
SCHD   13.09%    62,852  13.6%   -33.4% 2020-03-23
QQQ    19.80%   148,732  17.4%   -35.1% 2022-11-03

Ten years: 2016-09-30 to 2026-09-30 (10.00 yrs)
fund   annual   $10k ->    vol   max DD  DD trough
VOO    15.30%    41,509  15.3%   -34.0% 2020-03-23
SCHD   12.45%    32,317  15.3%   -33.4% 2020-03-23
QQQ    20.89%    66,675  19.0%   -35.1% 2022-11-03

Five years: 2021-09-30 to 2026-09-30 (5.00 yrs)
fund   annual   $10k ->    vol   max DD  DD trough
VOO    13.77%    19,059  15.7%   -24.5% 2022-10-12
SCHD    9.47%    15,722  15.1%   -16.8% 2022-09-30
QQQ    16.32%    21,290  20.9%   -35.1% 2022-11-03

Calendar-year total returns
year       VOO    SCHD     QQQ   leader
2012     16.0%   11.4%   18.1%   QQQ
2013     32.4%   32.9%   36.6%   QQQ
2014     12.9%   11.7%   19.2%   QQQ
2015      1.3%   -0.3%    9.4%   QQQ
2016     12.2%   16.4%    7.1%   SCHD
2017     21.8%   20.8%   32.7%   QQQ
2018     -4.5%   -5.6%   -0.1%   QQQ
2019     31.4%   27.3%   39.0%   QQQ
2020     18.3%   15.1%   48.4%   QQQ
2021     28.8%   29.9%   27.4%   SCHD
2022    -18.2%   -3.2%  -32.6%   SCHD
2023     26.3%    4.6%   54.9%   QQQ
2024     25.0%   11.7%   25.6%   QQQ
2025     17.8%    4.3%   20.8%   QQQ
2026     12.7%   21.5%   20.8%   SCHD (YTD)

Full calendar years 2012-2025 in which the first fund beat the second
  QQQ over VOO: 11 of 14 (2012, 2013, 2014, 2015, 2017, 2018, 2019, 2020, 2023, 2024, 2025)
  SCHD over VOO: 4 of 14 (2013, 2016, 2021, 2022)
  SCHD over QQQ: 3 of 14 (2016, 2021, 2022)

Correlation of monthly returns
  VOO-SCHD: 0.84
  VOO-QQQ: 0.91
  SCHD-QQQ: 0.62

After-tax, SEC method at 23.8%, Ten years (10.00 yrs)
fund   pretax  after dist  after sale  dist cost
VOO    15.30%      14.85%      12.81%      0.45%
SCHD   12.45%      11.55%      10.13%      0.90%
QQQ    20.89%      20.70%      18.08%      0.19%

After-tax, SEC method at 23.8%, Since SCHD inception (14.95 yrs)
fund   pretax  after dist  after sale  dist cost
VOO    15.10%      14.62%      13.03%      0.48%
SCHD   13.09%      12.24%      11.01%      0.85%
QQQ    19.80%      19.55%      17.63%      0.25%

Long history, QQQ vs SPY: 1999-03-10 to 2026-09-30
  QQQ: 10.88% a year over 27.6 yrs; worst decline -83.0% (2000-03-27 to 2002-10-09), back to that peak 2015-02-20
  SPY: 8.53% a year over 27.6 yrs; worst decline -55.2% (2007-10-09 to 2009-03-09), back to that peak 2012-08-16
  QQQ from 2000-03-27 to 2002-10-09: -83.0%
  SPY from 2000-03-27 to 2002-10-09: -46.9%

SCHD-QQQ holdings overlap
  shared stocks: 8 (TXN, QCOM, AMGN, PEP, ADP, CMCSA, FAST, PAYX)
  overlap by weight: 5.2%
  share of SCHD in shared stocks: 23.7%
  share of QQQ in shared stocks: 5.2%
```
