# inflation-beta

Supports https://summitward.com/learn/inflation-beta.

`inflation_beta.py` regresses six assets' returns on three CPI series under
two shock definitions, January 1960 to the latest month, and prints the same
asset's inflation beta under each choice side by side, for the whole sample
and for 1991 to 2018 (the period in Vanguard's 2019 paper). It also writes
`output/inflation-beta-monthly.json`, the monthly index levels the guide's
rolling-beta explorer regresses in the browser. Assets: S&P 500 total return,
a constant-maturity 10-year Treasury approximation, 3-month T-bills, gold spot,
and the World Bank total and energy commodity spot indices. Shocks: the month's
log CPI change against the monthly return, and the change in trailing 12-month
inflation from a year earlier against the trailing 12-month return (Newey-West
standard errors, lag 11). The docstring states the construction of every
series.

Data:

- `data/fred/*.csv`: CPIAUCSL (headline), CPILFESL (core), CPIENGSL (energy)
  and TB3MS (3-month bill rate), downloaded from FRED on the run date and
  cached; BLS and Federal Reserve series, public domain. `--refresh` re-downloads.
- `data/shiller_monthly.csv`: monthly S&P Composite price, dividends, earnings,
  CPI and GS10 yield from Robert J. Shiller's `ie_data.xls`; `.meta.json`
  records the retrieval date and the file's footnotes.
- `data/worldbank_pink_sheet_monthly.csv`: gold and the Total, Energy,
  Non-energy, Agriculture, Metals & Minerals and Precious Metals indices from
  the World Bank Commodity Price Data (Pink Sheet), CC BY 4.0. The `.meta.json`
  explains why two releases are spliced: the September 2026 file is rounded to
  one decimal, so the January 2026 full-precision file is the base and the
  eight later months are chained onto it.
- `export_sources.py` regenerates the two CSVs from the vendor spreadsheets. It
  needs pandas, xlrd and openpyxl and is not required to reproduce the figures.

```bash
python3 inflation_beta.py             # cached FRED data
python3 inflation_beta.py --refresh   # re-download FRED
python3 export_sources.py             # optional: refresh the Shiller and World Bank CSVs
```

Output quoted in the guide (run 2026-09-20, CPI through 2026-08):

```
Full sample, shock = monthly, 1960-01 to 2026-08, classical standard errors
  asset            headline beta (t)  corr    R2      core beta (t)  corr    R2
  sp500            -0.50 ( -1.2)     -0.04  0.002    -0.65 ( -1.3)  -0.04  0.002
  treasury10       -1.10 ( -5.2)     -0.18  0.033    -0.49 ( -1.8)  -0.06  0.004
  tbill            +0.37 (+14.3)     +0.45  0.204    +0.64 (+21.3)  +0.60  0.363
  gold             +2.25 ( +4.4)     +0.15  0.024    +1.35 ( +2.0)  +0.07  0.005
  commodities      +6.29 (+12.7)     +0.41  0.168    +1.36 ( +2.0)  +0.07  0.005
  energy          +10.29 (+10.0)     +0.33  0.112    +2.73 ( +2.0)  +0.07  0.005

Full sample, shock = change12, 1960-01 to 2026-08, Newey-West lag 11
  sp500            -0.87 ( -0.8)     -0.11  0.012    -3.23 ( -3.4)  -0.31  0.097
  treasury10       -1.69 ( -3.6)     -0.38  0.148    -2.19 ( -3.2)  -0.37  0.139
  tbill            -0.19 ( -0.8)     -0.12  0.014    -0.11 ( -0.3)  -0.05  0.003
  gold             +4.94 ( +3.1)     +0.40  0.160    +4.84 ( +2.2)  +0.29  0.086
  commodities      +8.66 ( +8.4)     +0.73  0.535    +6.39 ( +4.0)  +0.40  0.163
  energy          +14.06 ( +4.7)     +0.64  0.406   +12.71 ( +3.0)  +0.43  0.186

1991-01 to 2018-12, shock = monthly: sp500 headline +1.55 (t +2.1); gold +3.19
(t +4.3); commodities +11.21 (t +13.0). Shock = change12: sp500 +2.31 (t +1.3),
core -1.97 (t -0.7); commodities +10.22 (t +9.2).

S&P 500 beta to headline CPI, monthly shock, by decade:
  1960s -2.92 (t -2.2)   1970s -1.88 (t -1.7)   1980s -1.83 (t -1.8)
  1990s -5.64 (t -3.5)   2000s +1.60 (t +1.5)   2010s +3.97 (t +3.1)
  2020-2026 -0.37 (t -0.3)

60-month rolling beta, monthly shock, headline CPI:
  sp500        min  -9.59 (1995-07)  max +11.67 (2020-03)  negative 67.8%  23 sign changes / 730 windows
  treasury10   min  -5.28 (1989-03)  max  +1.86 (2001-04)  negative 89.9%  10 sign changes
  commodities  min  -3.31 (1995-11)  max +22.46 (2020-03)  negative  7.8%   9 sign changes
  gold         min  -7.27 (1972-12)  max +14.74 (1980-01)  negative 28.7%  20 sign changes
```

Three limits, all stated in the guide. Gold and the commodity indices are spot
prices, so they omit the collateral and roll return of a futures position and
are not the return of a commodity fund. The 10-year Treasury series is built
from the GS10 yield, not from a bond index. The CPI series are seasonally
adjusted, while TIPS accrue on the non-seasonally-adjusted index. The guide
states all three.
