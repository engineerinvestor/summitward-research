# why-i-avoid-schd

Numbers behind the after-tax section of
<https://summitward.com/learn/why-i-avoid-schd>: what SCHD's dividend yield
costs a taxable investor, separating tax paid early from wealth lost.

```bash
python3 why-i-avoid-schd/fetch_data.py   # refreshes closes and distributions (needs yfinance)
python3 why-i-avoid-schd/analyze.py      # stdlib only; prints every number the guide quotes
```

## Data

| File | Source | As of |
|---|---|---|
| `data/closes.csv` | Yahoo Finance daily closes for SCHD, VTI, VOO (split-adjusted, not dividend-adjusted) | 2011-10-20 to 2026-09-30 |
| `data/distributions.csv` | Yahoo Finance distributions per share by ex-date (split-adjusted) | 2011-12 to 2026-09 |

Checks against the issuers: the trailing 12-month SCHD yield computed from
these files on 2026-09-30 is 3.24%, the figure Schwab's SCHD page shows for
that date. Recomputing SCHD's 10-year SEC-style after-tax returns at 23.8%
gives 12.45% / 11.55% / 10.13% (pretax / after distributions / after sale);
Schwab reports 12.44% / 11.49% / 10.07% for the ten years to 2026-09-30.

## Method

- **Study A (controlled model).** Two funds earn the same constant pretax
  return (7%); yields 3.24% and 1.06% (the 2026-09-30 trailing yields of SCHD
  and VTI). Each year's dividend is taxed and the remainder reinvested, adding
  to basis. Three end states: never sold (also the step-up or donation case),
  sold at the horizon at the same rate, sold at a different rate.
- **Study B (SCHD's actual payouts).** SCHD's daily total return is built from
  its closes and distributions. Two payout schedules are laid on that same
  path: SCHD's own distributions, and VTI's payout fraction on VTI's ex-dates.
  Pretax wealth is identical by construction, so the gap is the tax cost of
  SCHD's payout policy alone. Taxes are paid on the ex-date and the rest
  reinvested at that day's close.
- **Study C (retiree spending).** Tax owed to raise $40,000 of after-tax cash
  from dividends versus from selling shares at several basis ratios.
- All dividends treated as qualified (SCHD: 98.5% in 2025; VTI: 93.58%), no
  capital-gain distributions (SCHD paid none in fiscal 2021-2025), no state tax.

## Headline output

- Year-1 extra dividend tax per $100,000: $327 at 15%, $410 at 18.8%, $519 at 23.8%.
- Study A, 20 years at 15%: extra dividend tax paid $12,492; low-yield lead
  $22,337 (0.33 pts/yr) if never sold, $8,368 (0.13 pts/yr) after a full sale.
  15% now and 23.8% at sale: $174. 0% now and 15% at sale: high yield ahead
  by $13,406.
- Study B, from SCHD's launch: 0.25 pts/yr never sold and 0.10 pts/yr ($717 per
  $10,000) after a sale at 15%; 0.39 and 0.15 ($995) at 23.8%. After-sale cost
  across 2012-2021 start dates: 0.08-0.10 pts/yr at 15%, 0.12-0.16 at 23.8%.
- Study C at 15%: $7,059 of tax from dividends; $1,885 / $3,243 / $4,693 from
  sales at basis ratios of 70% / 50% / 30%.

Full output of `analyze.py`:

```

==============================================================================
STUDY B  SCHD's actual payouts, closes to 2026-09-30
==============================================================================
SCHD trailing-12-month distribution yield at 2026-09-30: 3.24%
VTI trailing-12-month distribution yield at 2026-09-30: 1.06%
VOO trailing-12-month distribution yield at 2026-09-30: 1.06%

Same SCHD pretax path, two payout schedules: SCHD's actual payouts vs VTI's payout yield.
Values per $10,000. 'hold' = before any sale; 'sale' = after selling everything at the same rate.
bp = annualized advantage of the low-payout schedule.
start         yrs   rate   pretax    tax paid S/V  hold bp  sale bp  sale $
2011-10-20   14.9  15.0%   62,852   2,126/1,034       24.5     10.0     717
2012-12-31   13.7  15.0%   53,578   1,772/846         25.9     10.3     580
2013-12-31   12.7  15.0%   40,317   1,303/612         26.5     10.1     409
2014-12-31   11.7  15.0%   36,099   1,132/523         27.5     10.0     338
2015-12-31   10.7  15.0%   36,212   1,097/498         28.9     10.0     308
2016-12-30    9.7  15.0%   31,100     904/400         30.0      9.9     239
2017-12-29    8.8  15.0%   25,737     712/307         31.2      9.7     177
2018-12-31    7.7  15.0%   27,251     712/297         34.0     10.1     170
2019-12-31    6.7  15.0%   21,410     518/207         35.3      9.6     115
2020-12-31    5.7  15.0%   18,605     406/159         35.2      8.0      72
2011-10-20   14.9  23.8%   62,852   3,287/1,618       38.8     15.4     995
2012-12-31   13.7  23.8%   53,578   2,747/1,326       41.0     15.6     807
2013-12-31   12.7  23.8%   40,317   2,023/961         42.0     15.3     569
2014-12-31   11.7  23.8%   36,099   1,761/822         43.6     15.1     472
2015-12-31   10.7  23.8%   36,212   1,709/783         45.7     15.1     430
2016-12-30    9.7  23.8%   31,100   1,411/630         47.6     14.8     335
2017-12-29    8.8  23.8%   25,737   1,114/484         49.5     14.4     249
2018-12-31    7.7  23.8%   27,251   1,115/468         53.9     15.0     239
2019-12-31    6.7  23.8%   21,410     813/327         55.9     14.2     162
2020-12-31    5.7  23.8%   18,605     639/252         55.7     11.7     102

Each fund's own after-tax return (different pretax returns; this is investor experience,
not the tax effect). Annualized, 100% qualified, sale at the end at the same rate.

10 yr: 2016-09-30 to 2026-09-30 (10.0 yrs)
fund     rate  pretax  after div  after sale
SCHD    20.0%  12.45%     11.69%      10.52%
VTI     20.0%  14.70%     14.34%      12.69%
VOO     20.0%  15.30%     14.92%      13.24%
SCHD    23.8%  12.45%     11.55%      10.13%
VTI     23.8%  14.70%     14.27%      12.28%
VOO     23.8%  15.30%     14.85%      12.81%

since SCHD inception: 2011-10-20 to 2026-09-30 (14.9 yrs)
fund     rate  pretax  after div  after sale
SCHD    20.0%  13.09%     12.37%      11.36%
VTI     20.0%  14.73%     14.34%      13.04%
VOO     20.0%  15.10%     14.70%      13.38%
SCHD    23.8%  13.09%     12.24%      11.01%
VTI     23.8%  14.73%     14.26%      12.69%
VOO     23.8%  15.10%     14.62%      13.03%
==============================================================================
STUDY A  controlled model: $100,000, 7% pretax total return, yields 3.24% vs 1.06%
==============================================================================

Year-1 dividend tax per $100,000
   rate  high yield  low yield    extra
   0.0%           0          0        0
  15.0%         486        159      327
  18.8%         609        199      410
  23.8%         771        252      519

Low-yield advantage. 'extra tax' = sum of extra dividend tax the high-yield fund paid;
'no sale' = gap if never sold, which is also the step-up/donation result; 'full sale' = gap after selling and paying gains tax at the sale rate. bp = annualized.
dividend rate / sale rate  yrs  extra tax  no sale $     bp full sale $     bp
15.0% / 15.0%               10      4,382      5,851   32.7      1,248    7.3
15.0% / 15.0%               20     12,492     22,337   32.7      8,368   13.2
15.0% / 15.0%               30     27,487     63,962   32.7     31,004   17.4
18.8% / 18.8%               10      5,450      7,283   41.0      1,488    8.9
18.8% / 18.8%               20     15,378     27,593   41.0      9,919   16.3
18.8% / 18.8%               30     33,439     78,418   41.0     36,523   21.6
23.8% / 23.8%               10      6,830      9,137   51.9      1,758   10.8
23.8% / 23.8%               20     19,012     34,273   51.9     11,628   20.0
23.8% / 23.8%               30     40,700     96,440   51.9     42,474   26.8
Rate changes between now and the sale (20 years):
15.0% / 23.8%               20     12,492     22,337   32.7        174    0.3
23.8% / 15.0%               20     19,012     34,273   51.9     20,001   32.8
0.0% / 15.0%                20          0          0    0.0    -13,406  -20.0
15.0% / 0.0%                20     12,492     22,337   32.7     22,337   32.7

==============================================================================
STUDY C  tax to fund $40,000 of after-tax spending
==============================================================================
Dividends are fully taxable; a share sale is taxable only on the gain
(sale price minus basis). Basis ratio = basis / market value of the shares sold.
  rate  dividends  sell b=100%    b=70%    b=50%    b=30%
  0.0%          0            0        0        0        0
 15.0%      7,059            0    1,885    3,243    4,693
 18.8%      9,261            0    2,391    4,150    6,062
```
