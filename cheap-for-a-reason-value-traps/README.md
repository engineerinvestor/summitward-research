# cheap-for-a-reason-value-traps

Supports https://summitward.com/learn/cheap-for-a-reason-value-traps.

`analyze.py` asks how the stocks where value traps should cluster have done as
a diversified group. It reads Kenneth French's portfolios sorted
independently on book-to-market (BE/ME) and operating profitability (OP) and
prints annualized returns by period, volatility, growth of $1, drawdowns,
average firm counts, the full 5x5 grid, five-factor regressions, rolling
ten-year win rates, and the HML and RMW factor record. `--chart PATH` also
writes the year-end growth-of-$1 series the guide's chart reads.

Definitions: "cheap and unprofitable" is the 5x5 `HiBM LoOP` portfolio
(highest BE/ME quintile, lowest OP quintile); "cheap and profitable" is
`HiBM HiOP`; "expensive and profitable" is `LoBM HiOP`; "expensive and
unprofitable" is `LoBM LoOP`. The small and big splits are the corner
quartiles of the 2x4x4 size x BE/ME x OP sort. OP is operating profits over
book equity, so the low-OP groups hold low-margin firms as well as
money-losers. Market is Mkt-RF plus RF. Returns are value-weighted unless a
key ends in `_ew`; annualized returns are geometric. The cheap-and-profitable
cells are thin (28 firms on average in the 5x5, 41 small and 8 big in the
2x4x4, sometimes one), so read them as noisy. Research portfolios carry no
fees, trading costs or taxes, so they are not investable returns.

Data (Kenneth R. French,
[Data Library](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html),
files built from the 202608 CRSP database, downloaded 2026-09-29; used with
attribution):

- `data/25_Portfolios_BEME_OP_5x5.csv`
- `data/32_Portfolios_ME_BEME_OP_2x4x4.csv`
- `data/F-F_Research_Data_5_Factors_2x3.csv`
- `data/F-F_Research_Data_Factors.csv`

```bash
python3 analyze.py
python3 analyze.py --chart value-trap-corners.json
```

Output quoted in the guide (run 2026-09-29):

```
Data 196307 to 202608, 758 months. Value-weighted unless marked _ew.

Annualized geometric return by period
                                   full  1963-1990  1991-2006  2007-2020  2021-2026
  cheap_unprofitable              13.1%      14.5%      15.4%       0.9%      34.1%
  cheap_profitable                12.5%       8.0%      27.3%       7.4%       8.1%
  expensive_profitable            11.6%      10.4%      11.7%      13.0%      13.5%
  expensive_junk                   3.4%      -0.4%       2.0%      13.4%       2.6%
  market                          10.9%      10.0%      12.1%      10.1%      13.8%
  tbill                            4.4%       6.9%       3.9%       0.8%       3.2%
  cheap_unprofitable_ew           17.0%      17.9%      28.6%       6.6%       9.1%
  cheap_profitable_ew             14.6%      15.5%      23.2%       3.0%      17.4%
  expensive_profitable_ew         11.3%      10.3%      14.3%      10.8%       9.0%
  expensive_junk_ew                2.9%       3.5%       3.3%       6.4%      -8.3%
  small_cheap_unprofitable        13.4%      14.0%      19.9%       4.5%      15.8%
  small_cheap_profitable          17.8%      20.8%      26.3%       5.1%      14.0%
  big_cheap_unprofitable          11.0%      13.0%      12.2%       1.8%      22.2%
  big_cheap_profitable             6.7%       6.0%      19.1%      -4.3%       5.6%
  small_expensive_junk             2.3%       0.6%      -0.0%       9.2%       0.7%

Full sample: arithmetic mean, volatility, growth of $1, max drawdown
  cheap_unprofitable         arith   14.65% vol    21.2%  $1 -> $ 2,430.59  maxDD   -63.3% (200705-200902)
  cheap_profitable           arith   16.06% vol    29.4%  $1 -> $ 1,658.89  maxDD   -88.7% (196811-197412)
  expensive_profitable       arith   12.25% vol    15.9%  $1 -> $   999.38  maxDD   -52.3% (197212-197409)
  expensive_junk             arith    7.24% vol    27.8%  $1 -> $     8.23  maxDD   -88.7% (200002-200209)
  market                     arith   11.58% vol    15.4%  $1 -> $   684.89  maxDD   -50.3% (200710-200902)
  tbill                      arith    4.35% vol     0.9%  $1 -> $    15.52  maxDD     0.0% (None-None)
  small_cheap_unprofitable   arith   15.30% vol    23.0%  $1 -> $ 2,807.55  maxDD   -67.9% (200705-200902)
  small_cheap_profitable     arith   20.76% vol    29.1%  $1 -> $31,993.50  maxDD   -86.5% (196811-197412)
  big_cheap_unprofitable     arith   12.02% vol    17.5%  $1 -> $   729.27  maxDD   -70.4% (200705-200902)
  big_cheap_profitable       arith   11.36% vol    32.5%  $1 -> $    60.58  maxDD   -91.5% (200806-201602)
  small_expensive_junk       arith    6.47% vol    28.8%  $1 -> $     4.19  maxDD   -87.9% (200002-200902)

Average number of firms per month
  cheap_unprofitable         mean    490  min  123
  cheap_profitable           mean     28  min    2
  expensive_profitable       mean    311  min  141
  expensive_junk             mean    319  min   24
  small_cheap_unprofitable   mean    370  min   81
  small_cheap_profitable     mean     41  min    1
  big_cheap_unprofitable     mean     97  min   60
  big_cheap_profitable       mean      8  min    1
  small_expensive_junk       mean    405  min   44

5x5 grid, full-sample annualized geometric return (rows BE/ME low->high, cols OP low->high)
  BM1      3.4%     8.5%     9.4%    10.5%    11.6%
  BM2      7.3%     8.8%    10.9%    12.0%    11.5%
  BM3      7.6%    11.3%    11.4%    13.8%    13.6%
  BM4      9.7%    10.9%    13.9%    13.0%    14.6%
  BM5     13.1%    13.1%    15.4%    16.0%    12.5%

Five-factor regressions of monthly excess returns (alpha annualized)
  cheap_unprofitable         alpha    0.12% (t  0.12)  Mkt-RF  1.14  SMB  0.31  HML  0.72  RMW -0.38  CMA -0.05  R2 0.86
  cheap_profitable           alpha   -2.18% (t -0.85)  Mkt-RF  1.22  SMB  0.72  HML  0.84  RMW  0.24  CMA -0.06  R2 0.55
  expensive_profitable       alpha    0.66% (t  1.27)  Mkt-RF  0.98  SMB -0.05  HML -0.26  RMW  0.38  CMA  0.03  R2 0.94
  expensive_junk             alpha    0.16% (t  0.11)  Mkt-RF  1.12  SMB  0.36  HML -0.56  RMW -0.89  CMA -0.52  R2 0.83
  cheap_unprofitable_ew      alpha    4.50% (t  3.52)  Mkt-RF  0.93  SMB  1.00  HML  0.28  RMW -0.31  CMA  0.17  R2 0.81
  cheap_profitable_ew        alpha    0.13% (t  0.05)  Mkt-RF  1.13  SMB  1.11  HML  0.87  RMW  0.17  CMA -0.20  R2 0.61
  expensive_profitable_ew    alpha   -1.81% (t -2.85)  Mkt-RF  1.07  SMB  0.71  HML -0.05  RMW  0.38  CMA -0.02  R2 0.94
  expensive_junk_ew          alpha   -2.14% (t -1.29)  Mkt-RF  1.04  SMB  1.16  HML -0.45  RMW -0.92  CMA -0.18  R2 0.82

Rolling 10-year windows, full sample
  cheap_unprofitable beat market in 374 of 639 windows (59%)
  expensive_junk beat tbill in 207 of 639 windows (32%)
  small_cheap_profitable beat small_cheap_unprofitable in 449 of 639 windows (70%)

HML and RMW
  HML mean since 192607:    4.22% per year
  HML worst drawdown   -57.8% (200612 to 202009); now   -32.1% from that peak
  full         HML    3.53%  RMW    3.02%
  1963-1990    HML    5.10%  RMW    2.24%
  1991-2006    HML    6.77%  RMW    4.33%
  2007-2020    HML   -5.32%  RMW    2.80%
  2021-2026    HML    8.60%  RMW    3.60%

Wrote results.json
```
