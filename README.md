# summitward-research

Scripts and data behind the numbers in Summitward's Learn guides, published so
that any figure a guide attributes to "our calculation" can be re-run.

Each folder is named for the guide slug it supports and contains the script,
the data files it reads, and a README stating the guide URL, the data
provenance and read dates, and the output the guide quotes. Every analysis
script runs with the Python standard library only (`inflation-beta` also
carries an optional exporter that converts vendor spreadsheets to CSV and needs
pandas or openpyxl; the committed CSVs make running it unnecessary; `small-cap-value-vs-growth` has
an optional `--funds` flag that needs yfinance, and its committed
`results.json` already holds that output; `minimum-volatility-investing` needs
numpy, pandas, openpyxl and yfinance, and downloads its AQR and Yahoo inputs):

```bash
python3 <folder>/<script>.py
```

| Folder | Guide | What it reproduces |
| --- | --- | --- |
| `mortgage-rate-below-ten-percent` | [A 9% Mortgage Does Not Lose to 10% Stocks](https://summitward.com/learn/mortgage-rate-below-ten-percent) | Share of overlapping historical windows in which the S&P 500 beat a guaranteed return |
| `social-security-discount-rate` | [What Discount Rate Belongs on Social Security?](https://summitward.com/learn/social-security-discount-rate) | Present value of claiming at 62, 67 and 70 by real discount rate, with SSA mortality, and the crossover rates |
| `robo-advisor-returns` | [What Wealthfront's 9.8% Return Actually Measures](https://summitward.com/learn/robo-advisor-returns) | A published robo-advisor allocation rebuilt from index returns over two eras, and the reported risk-score ladder |
| `inflation-beta` | [Inflation Beta Is Not One Number](https://summitward.com/learn/inflation-beta) | Full-sample and rolling inflation betas for six assets under three CPI series and two shock definitions, 1960 to date, plus the data behind the guide's explorer |
| `small-cap-value-vs-growth` | [Small-Cap Value vs. Small-Cap Growth](https://summitward.com/learn/small-cap-value-vs-small-cap-growth) | 99 years of Fama-French small value, small growth and tiny-growth returns by decade and rolling window, plus index funds over matching windows |
| `minimum-volatility-investing` | [Minimum Volatility and Betting Against Beta](https://summitward.com/learn/minimum-volatility-investing) | USMV's live record against VTI and a volatility-matched stock and T-bill mix, French beta quintiles since 1963, and AQR's BAB factor before and after publication |

## Data sources

- S&P 500, Baa corporate and 10-year Treasury annual returns: Aswath Damodaran,
  [Historical Returns on Stocks, Bonds and Bills](https://pages.stern.nyu.edu/~adamodar/New_Home_Page/datafile/histretSP.html),
  NYU Stern. Used with attribution.
- Developed ex-US and emerging market annual returns, and US size and
  book-to-market, beta and variance portfolios and factors: Kenneth R. French,
  [Data Library](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html).
  Used with attribution.
- Period life table: Social Security Administration, Office of the Chief
  Actuary, [2023 period life table](https://www.ssa.gov/oact/STATS/table4c6.html),
  embedded in the script. US government work, public domain.
- CPI-U (headline, core, energy) and the 3-month Treasury bill rate: Federal
  Reserve Bank of St. Louis, [FRED](https://fred.stlouisfed.org/) series
  CPIAUCSL, CPILFESL, CPIENGSL (BLS) and TB3MS. US government work, public
  domain; citation requested.
- Monthly S&P Composite price, dividends and 10-year Treasury yield: Robert J.
  Shiller, [ie_data.xls](https://shillerdata.com/). Used with attribution.
- Gold and commodity price indices: World Bank,
  [Commodity Price Data (Pink Sheet)](https://www.worldbank.org/en/research/commodity-markets).
  CC BY 4.0.
- Wealthfront risk-score ladder: twenty values read from Wealthfront's public
  [historical performance page](https://www.wealthfront.com/historical-performance)
  on the date stated in the file. Facts, reproduced for comment and analysis.

- Betting Against Beta factor returns: AQR Capital Management,
  [data sets](https://www.aqr.com/Insights/Datasets), downloaded by the script
  and not redistributed here.
- ETF prices: Yahoo Finance adjusted closes via yfinance, downloaded by the
  scripts that use them and not redistributed here.

## License

Code is MIT licensed (see `LICENSE`). Data files carry the terms of their
sources above.

## Corrections

Open an issue if a script does not reproduce the figure a guide quotes, or if
a data file has drifted from its source.
