# does-national-debt-cause-inflation

Supports https://summitward.com/learn/does-national-debt-cause-inflation.

Two descriptive analyses:

- `debt_vs_inflation.py` asks whether a high public-debt level, or a large
  deficit, has been followed by higher inflation across 18 advanced economies
  since 1870.
- `us_debt_decomposition.py` splits each fiscal year's change in US federal
  debt held by the public (as a share of GDP) into primary deficits, interest,
  inflation, real growth and a residual, FY1946-2025.

```bash
./fetch_data.sh                          # downloads source data into .cache/
python3 debt_vs_inflation.py --json      # prints tables; writes output/debt_vs_inflation.json
python3 us_debt_decomposition.py --json  # prints tables; writes output/us_debt_decomposition.json
```

Requires pandas, numpy and openpyxl (an exception to this repo's stdlib-only
rule, as for `minimum-volatility-investing`: the inputs are Stata and Excel
files).

## Data

Neither source file is committed. `fetch_data.sh` downloads them.

- **Jordà-Schularick-Taylor Macrohistory Database, release 6**
  (https://www.macrohistory.net/database/). Variables used: `debtgdp`, `cpi`,
  `revenue`, `expenditure`, `gdp`. The terms of use bar commercial data
  providers from integrating or selling the data, so it is downloaded rather
  than redistributed. SHA-256 of the file used:
  `b0ebb74a8d1b5b1bc9033fc46a6dcc578736afff8ce1e1086b7840f2649e79b3`.
  The download link ends `.xlsx` on some pages but serves the Stata file.
- **OMB Historical Tables, FY2027 Budget** (April 2026), Tables 1.1, 3.1, 7.1
  and 10.1 (https://www.whitehouse.gov/omb/information-resources/budget/historical-tables/).
  Read 2026-10-18.

## Method: debt_vs_inflation.py

- Forward inflation: average annual CPI change from year t to t+5, only where
  both CPI observations exist exactly five years apart.
- Debt: `debtgdp` at t (gross public debt in most countries, so the US figure
  differs from debt held by the public). Deficit: (expenditure - revenue) / GDP
  at t.
- Buckets: debt below 30, 30-60, 60-90, 90+ (% of GDP); deficit below 0, 0-3,
  3-6, 6+. Reported: country-years, countries, median, interquartile range,
  share of windows above 10% a year. Starting years 1870-2015.
- "Excluding war years" drops t in 1914-18 and 1939-45. Eras: 1870-1913,
  1914-45, 1946-72, 1973-90, 1991-2015.
- A within-country slope (country means removed, standard errors clustered by
  country) is printed for reference; the guide does not rely on it.

### Limitations

- Overlapping five-year windows: the 2,232 peacetime country-years hold far
  fewer independent observations.
- Reverse causation: inflation lowers debt ratios, so low debt often follows
  high inflation (most visible in 1973-90).
- Missing debt data during the worst fiscal inflations: Germany 1914-1926 and
  France 1939-1948 have no `debtgdp`. Japan's wartime deficits computed from
  `revenue` and `expenditure` are negative, which suggests those series omit
  military accounts; the war-excluded tables are unaffected.

### Output the guide quotes (peacetime, starting years 1870-2015)

| Debt, % of GDP | Country-years | Median inflation, next 5 yrs | Share above 10% | Median, 1991-2015 |
|---|---|---|---|---|
| Below 30 | 709 | 2.50 | 10.3% | 2.43 |
| 30-60 | 774 | 2.33 | 7.4% | 1.74 |
| 60-90 | 416 | 1.66 | 6.0% | 1.77 |
| 90+ | 333 | 1.51 | 3.9% | 1.55 |

| Deficit, % of GDP | Country-years | Median | Share above 10% | Median, 1991-2015 |
|---|---|---|---|---|
| Surplus | 743 | 1.91 | 5.5% | 1.98 |
| 0-3 | 1,054 | 1.83 | 5.9% | 1.79 |
| 3-6 | 296 | 2.23 | 10.8% | 1.66 |
| 6+ | 172 | 4.58 | 21.5% | 1.48 |

No 1991-2015 bucket has a window above 10%. Japan: `debtgdp` 94.2% (1995) to
253.9% (2020); CPI averaged 0.17% a year and fell in 14 of the 26 years
1995-2020. For the US 1973-81 figure the guide uses BLS CPI-U annual averages
(41.8 in 1972, 90.9 in 1981: 9.0% a year) rather than JST's US CPI, which gives
8.5%.

## Method: us_debt_decomposition.py

With debt ratio b = B/Y, nominal growth 1+g = (1+gamma)(1+pi) from OMB GDP and
the GDP chained price index (fiscal years), primary deficit PD = deficit - net
interest, and stock-flow residual SF:

    db = PD/Y + NI/Y - b0*pi/(1+g) - b0*gamma*(1+pi)/(1+g) + SF/Y

The identity holds exactly; SF absorbs cash-balance changes, credit programs and
the 1976 transition quarter (whose flows are added to the FY1977 step).

### Output the guide quotes (percentage points of GDP)

| Fiscal years | Start | End | Primary deficits | Interest | Inflation | Real interest | Real growth | Residual |
|---|---|---|---|---|---|---|---|---|
| 1946-1974 | 103.9 | 23.2 | -20.9 | +38.8 | -55.7 | -16.9 | -33.5 | -9.3 |
| 1975-2007 | 23.2 | 35.2 | +7.0 | +77.4 | -38.2 | +39.2 | -36.2 | +2.0 |
| 2008-2019 | 35.2 | 78.9 | +43.9 | +17.0 | -11.8 | +5.2 | -15.0 | +9.6 |
| 2020-2025 | 78.9 | 99.5 | +36.6 | +13.7 | -19.1 | -5.5 | -13.8 | +3.3 |
| 2021-2023 | 98.5 | 95.8 | +17.8 | +5.8 | -13.4 | -7.6 | -9.8 | -3.1 |

### Validation

Hall and Sargent (2011, AEJ: Macroeconomics) attribute 12.5 of a 54.9-point fall
in US debt/GDP from 1945 to 1974 (about 23%) to negative real returns caused by
inflation. On OMB's par-value series the real-interest term is -16.9 of -80.7
points, about 21%. Real growth is 42% here against their 39%, and primary
surpluses 26% against their 38%; the residual (-9.3) and the different debt
measures account for the gap.
