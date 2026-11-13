# what-makes-an-investment-safe

Supports https://summitward.com/learn/what-makes-an-investment-safe.

`analyze.py` scores the same strategies against two kinds of bill over every
historical window in Damodaran's annual US data: a fixed-dollar bill (the
money must come back as at least the same number of dollars) and a bill that
rises with CPI-U (it must come back with at least the same purchasing power).
Strategies: 3-month T-bills rolled (before tax and with interest taxed at
24%), the 10-year Treasury rolled at constant maturity, a 10-year Treasury
bought at the prior year-end yield and held to maturity, the S&P 500, and 60/40
rebalanced yearly. It also measures how flexibility changes the result (the
bill can wait up to N extra years, or be trimmed by X%), and lists the longest
spells below a prior real year-end high.

`safe_asset_scorecard.py` holds the conventions; its docstring states each
one. Python standard library only.

Data (`data/`):

- `damodaran_returns.json`: annual nominal and real total returns and CPI-U
  inflation (December to December), 1928-2025, from Aswath Damodaran's
  [histretSP.xls](https://pages.stern.nyu.edu/~adamodar/New_Home_Page/datafile/histretSP.html)
  (2026-01 release).
- `treasury_10y_yields.json`: year-end constant-maturity 10-year Treasury
  yields, 1927-2025, from the "T.Bond rate" column of the same workbook's
  "S&P 500 & Raw Data" sheet (August 2026 file; its bond returns match the
  returns file for every year).

Limits: US data only, before fees; stocks and the rolled bond are before tax.
Windows overlap, so a 20-year horizon over 98 years has 79 windows but only
about four separate periods. Year-end data misses intra-year peaks such as
September 1929. The held-to-maturity bond is treated as a zero-coupon bond at
the par yield.

```bash
python3 analyze.py
```

Output quoted in the guide (run 2026-11-12):

```
Data 1928-2025, US, annual, before fees.

1. Share of windows that fell short: nominal | real (worst real outcome)
 horizon  windows  ~indep.           T-bills, rolled    10-year Treasury, roll                   S&P 500    60/40 stocks/10-year T
       1       98       98           0% | 41% (-15%)          20% | 43% (-23%)          27% | 32% (-38%)          21% | 28% (-24%)
       3       96       32           0% | 45% (-23%)           6% | 35% (-31%)          16% | 21% (-55%)           9% | 26% (-30%)
       5       94       19           0% | 47% (-27%)           5% | 39% (-34%)          12% | 23% (-42%)           4% | 12% (-24%)
      10       89        9           0% | 48% (-40%)           0% | 37% (-39%)           6% | 12% (-32%)           0% | 11% (-24%)
      20       79        4           0% | 35% (-45%)           0% | 33% (-37%)            0% | 0% (+13%)             0% | 1% (-2%)
      30       69        3           0% | 35% (-39%)           0% | 33% (-35%)           0% | 0% (+253%)           0% | 0% (+138%)

2. T-bills after a 24% tax on interest, real yardstick
    1y: 54% short, worst -15%
    3y: 58% short, worst -23%
    5y: 61% short, worst -27%
   10y: 57% short, worst -41%
   20y: 71% short, worst -47%
   30y: 75% short, worst -44%

3. 10-year Treasury bought at the prior year-end yield, held to maturity
   windows 89 (starts 1928-2016)
   nominal: 0% short (paid its promise every time)
   real:    28% short (25 windows), worst -31.2%, median +12.8%
   real short start years: [1937, 1938, 1939, 1940, 1941, 1942, 1943, 1944, 1945, 1946, 1947, 1950, 1965, 1966, 1967, 1968, 1969, 1971, 1972, 1973, 1974, 2012, 2013, 2015, 2016]
   rolled 10-year Treasury, real, same windows: 37% short

4. Longest spells below a prior real year-end high
   10-year Treasury, rolled         peak 1940  trough 1981 (-55.5%)  recovered 1991  -> 51 years
   10-year Treasury, rolled         peak 2012  trough 2013 (-10.4%)  recovered 2019  -> 7 years
   10-year Treasury, rolled         peak 2002  trough 2003 (-1.5%)  recovered 2007  -> 5 years
   S&P 500                          peak 1999  trough 2008 (-42.2%)  recovered 2013  -> 14 years
   S&P 500                          peak 1972  trough 1974 (-48.0%)  recovered 1984  -> 12 years
   S&P 500                          peak 1936  trough 1941 (-41.8%)  recovered 1945  -> 9 years
   T-bills, rolled                  peak 1933  trough 1951 (-45.8%)  recovered 1997  -> 64 years
   T-bills, rolled                  peak 2008  trough 2022 (-23.0%)  recovered open at 2025  -> 17 years, -18.7% at 2025
   T-bills, rolled                  peak 2001  trough 2005 (-3.5%)  recovered 2008  -> 7 years
   60/40 stocks/10-year Treasury    peak 1972  trough 1974 (-35.2%)  recovered 1985  -> 13 years
   60/40 stocks/10-year Treasury    peak 1936  trough 1941 (-24.3%)  recovered 1945  -> 9 years
   60/40 stocks/10-year Treasury    peak 1928  trough 1931 (-28.6%)  recovered 1933  -> 5 years

5. Flexibility, real yardstick (windows that complete horizon + 3 years)
   horizon 3y, 93 windows (starts 1928-2020)
                                      firm  wait 1  wait 3  cut 10%  cut 20%
   T-bills, rolled                     44%     43%     39%       8%       2%
   10-year Treasury, rolled            34%     28%     23%      13%       4%
   S&P 500                             22%     18%      8%      17%      11%
   60/40 stocks/10-year Treasury       25%     14%      4%      10%       4%

   horizon 5y, 91 windows (starts 1928-2018)
                                      firm  wait 1  wait 3  cut 10%  cut 20%
   T-bills, rolled                     45%     42%     38%      12%       8%
   10-year Treasury, rolled            37%     34%     26%      20%       3%
   S&P 500                             24%     14%      8%      15%       9%
   60/40 stocks/10-year Treasury       12%      9%      5%       7%       3%

   horizon 10y, 86 windows (starts 1928-2013)
                                      firm  wait 1  wait 3  cut 10%  cut 20%
   T-bills, rolled                     47%     44%     38%      27%      16%
   10-year Treasury, rolled            35%     31%     26%      24%      10%
   S&P 500                             13%     12%      6%      10%       7%
   60/40 stocks/10-year Treasury       12%     10%      3%       8%       3%

6. Flexibility, nominal yardstick (fixed-dollar bill), stocks
   S&P 500 1y: firm 27% short (worst -44%), wait 3 years 8%
   S&P 500 3y: firm 16% short (worst -62%), wait 3 years 5%
   S&P 500 5y: firm 12% short (worst -49%), wait 3 years 0%
```
