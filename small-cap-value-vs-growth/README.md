# small-cap-value-vs-growth

Supports https://summitward.com/learn/small-cap-value-vs-small-cap-growth.

`analyze.py` compares small-cap value with small-cap growth using Kenneth
French's value-weighted size and book-to-market portfolios, calendar
1927-2025, and prints annualized returns, volatility, drawdowns, decade
returns, sub-periods, rolling-window win rates and the longest relative
drawdown. The 5x5 sort supplies the "tiny" corners (smallest size quintile,
lowest and highest book-to-market quintile). `--funds` adds index funds over
matching windows and needs `yfinance`; the committed `results.json` already
holds that section, and a run without the flag keeps it.

Definitions follow the Fama-French 2x3 sort: small growth is `SMALL LoBM`,
small value is `SMALL HiBM`, "small" and "big" are the equal averages of the
three portfolios on each side (the legs of SMB), and the market is Mkt-RF plus
RF. Research portfolios carry no fees, trading costs or taxes, so they are not
investable returns.

Data (Kenneth R. French,
[Data Library](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html),
files built from the 202608 CRSP database, downloaded 2026-09-28; used with
attribution):

- `data/6_Portfolios_2x3.csv`
- `data/25_Portfolios_5x5.csv`
- `data/F-F_Research_Data_Factors.csv`

Fund returns for `--funds`: Yahoo Finance adjusted closes (dividends
reinvested, net of expense ratios), month end to month end, read 2026-09-28.

```bash
python3 analyze.py
python3 analyze.py --funds   # needs yfinance
```

Output quoted in the guide (run 2026-09-28):

```
Data through 202608. Full window 1927-2025, 1188 months
  small_growth  ann   8.81%  vol  25.8%  maxDD  -88.9%  $1 -> $4,259
  small_value   ann  14.16%  vol  28.1%  maxDD  -88.7%  $1 -> $493,097
  large_growth  ann  10.21%  vol  18.3%  maxDD  -81.7%  $1 -> $15,156
  large_value   ann  12.28%  vol  24.6%  maxDD  -89.2%  $1 -> $95,100
  small         ann  12.03%  vol  25.4%  maxDD  -87.7%  $1 -> $76,854
  big           ann  11.06%  vol  19.9%  maxDD  -86.9%  $1 -> $32,501
  market        ann  10.27%  vol  18.4%  maxDD  -83.7%  $1 -> $15,952
  tbill         ann   3.29%  vol   0.9%  maxDD   -0.1%  $1 -> $25
  tiny_growth   ann   2.47%  vol  41.2%  maxDD  -98.6%  $1 -> $11
  tiny_value    ann  15.89%  vol  31.7%  maxDD  -90.9%  $1 -> $2,188,134

By decade (annualized %): small value, small growth, spread, small, big, market
  1930s         1.8    4.5   -2.7    4.2   -1.5   -0.3
  1940s        21.3   11.3   10.0   15.7   11.6    9.5
  1950s        20.2   17.5    2.7   18.8   19.7   18.3
  1960s        15.7   10.7    5.0   13.3    8.9    8.3
  1970s        15.0    5.8    9.2   10.4    8.3    6.1
  1980s        21.2   10.1   11.1   17.1   17.8   16.9
  1990s        16.3   11.5    4.8   14.6   17.1   18.0
  2000s        10.4   -1.5   11.9    6.3    2.2   -0.4
  2010s        11.0   12.6   -1.6   12.2   13.1   13.6
  2020-2025    11.3    9.7    1.6   10.3   14.6   14.8

Sub-periods (annualized %)
  1927-1962: small_value 12.6  small_growth 9.0  market 9.2  small 11.1  big 10.0  tiny_value 14.6  tiny_growth -1.3  tbill 1.3
  1963-2025: small_value 15.1  small_growth 8.7  market 10.9  small 12.6  big 11.7  tiny_value 16.6  tiny_growth 4.7  tbill 4.4
  1990-2025: small_value 12.3  small_growth 7.7  market 10.9  small 10.9  big 11.3  tiny_value 14.5  tiny_growth 2.5  tbill 2.7
  2000-2025: small_value 10.8  small_growth 6.3  market 8.3  small 9.5  big 9.1  tiny_value 13.2  tiny_growth 1.0  tbill 1.9
  2010-2025: small_value 11.1  small_growth 11.5  market 14.1  small 11.5  big 13.7  tiny_value 13.7  tiny_growth 6.0  tbill 1.3

2026 through 202608: {'through': '202608', 'small_value': 21.7, 'small_growth': 20.9, 'market': 12.7}

Rolling windows (monthly steps): share in which small value beat small growth
   1y: 1177 windows, value won 63.0%, median 4.5pp, worst -67.8pp (ending 200002), best 108.8pp
   5y: 1129 windows, value won 79.9%, median 4.6pp, worst -12.4pp (ending 202101), best 26.7pp
  10y: 1069 windows, value won 86.4%, median 6.5pp, worst -6.1pp (ending 202012), best 15.3pp
  20y: 949 windows, value won 98.5%, median 6.7pp, worst -0.7pp (ending 202510), best 12.4pp

Longest stretch with the SV/SG wealth ratio below its prior high: 138 months, 193209 to 194402
Calendar years small value beat small growth: 59 of 99

Index funds vs. research portfolios, same months (annualized %)
  2000-08 to 2025-12: {'IWN': 8.82, 'IWO': 6.54}  FF small value 10.57  small growth 6.57  tiny growth 0.99
  2004-02 to 2025-12: {'VBR': 9.15, 'VBK': 9.37, 'IJS': 8.66, 'IJT': 9.56}  FF small value 8.45  small growth 8.44  tiny growth 2.82
  2019-10 to 2025-12: {'AVUV': 13.9, 'VBR': 10.57, 'VBK': 9.06, 'IWN': 9.0, 'IWO': 9.33}  FF small value 12.39  small growth 11.54  tiny growth 6.29

wrote results.json
```
