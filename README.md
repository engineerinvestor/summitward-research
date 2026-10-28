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
numpy, pandas, openpyxl and yfinance, and downloads its AQR and Yahoo inputs;
`portable-alpha-and-return-stacking` and `factor-loadings-expected-returns` need numpy, pandas and yfinance;
`mean-variance-optimization` needs numpy and scipy;
`r-squared-trap`, `most-stocks-lose-to-tbills` and `dividends-are-not-free-money`
need numpy and matplotlib, and `safe-withdrawal-rate` and `tals-leverage-simulator`
also need pandas; these five render Shorts and need ffmpeg for the video, and
each video renderer takes `--stats-only` to print its numbers without it):

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
| `cheap-for-a-reason-value-traps` | [Cheap for a Reason: Value Traps](https://summitward.com/learn/cheap-for-a-reason-value-traps) | Returns, firm counts and five-factor loadings of Fama-French portfolios sorted on book-to-market and operating profitability since 1963, including the cheap-and-unprofitable corner |
| `roic-etfs` | [ROIC Explained](https://summitward.com/learn/roic-return-on-invested-capital) | Fama-French five-factor plus momentum loadings of ETFs that select on return on invested capital (MOAT, LCOW, GFLW) against QUAL, AVUV and VTI |
| `volatility-targeting` | [Volatility Targeting: Does Scaling Risk Improve Returns?](https://summitward.com/learn/volatility-targeting) | A constant-volatility rule on daily US market returns since 1926 against buy and hold and a volatility-matched stock and T-bill mix, with parameter, cost, episode and Moreira-Muir comparisons |
| `r-squared-trap` | [The R² Trap](https://summitward.com/learn/r-squared-trap) | In-sample R² of rolling P/E vs. 10-year return regressions in 5,000 simulated markets with zero predictability, under random-walk and mean-reverting valuation, plus the video that shows it and a second Short on what R² does not measure |
| `safe-withdrawal-rate` | [Safe Withdrawal Rate: Why the 4% Rule Isn't Enough](https://summitward.com/learn/safe-withdrawal-rate) | A 4% constant-real withdrawal from a 60/40 portfolio over every 30- and 50-year window since 1871, and the Short built on it |
| `most-stocks-lose-to-tbills` | [Most Stocks Lose to T-Bills. The Market Still Wins.](https://summitward.com/learn/most-stocks-lose-to-tbills) | 1,000 identical simulated stocks whose compounding produces the skew Bessembinder documents, and the Short built on it |
| `dividends-are-not-free-money` | [Dividends Are Not Free Money](https://summitward.com/learn/dividends-are-not-free-money) | The ex-dividend price drop, the homemade-dividend comparison and its tax timing, as worked examples in a Short |
| `tals-leverage-simulator` | [We Open-Sourced a TALS Simulator](https://summitward.com/learn/tals-leverage-simulator) | A Short rendered from talsim v0.5.0's leverage sweep and scenario comparison: harvested losses and tax benefit by book, and the paired wealth difference against long-only |
| `factor-loadings-expected-returns` | [Do Higher Factor Loadings Mean Higher Expected Returns?](https://summitward.com/learn/factor-loadings-expected-returns) | Fama-French premium means and Newey-West intervals since 1963, small-value fund loadings since 2019, and the 95% band those put around each fund's implied edge over VTI |
| `government-debt-crisis-bonds` | [Will Government Bonds Blow Up?](https://summitward.com/learn/government-debt-crisis-bonds) | France's nominal State debt rolled forward bond by bond from the AFT line table: effective interest rate and interest bill under three yield curves, against the reprice-everything shortcut, validated against the French budget's own rate sensitivity |
| `portable-alpha-and-return-stacking` | [Do You Need Return Stacking?](https://summitward.com/learn/portable-alpha-and-return-stacking) | NTSX, RSSB and RSST against SPY, VT, a 60/40 fund and costless ETF replicas: 2022 losses, RSST's gap to the S&P 500 by year and worst 12 months, RSSB's tracking of a 100/100, and stock-bond correlation by year since 2002 |
| `mega-backdoor-roth` | [The Mega Backdoor Roth Is a Much Bigger Deal Than the Backdoor Roth IRA](https://summitward.com/learn/mega-backdoor-roth) | $39,500 a year of 2026 after-tax 401(k) room held 25 years in a Roth against a taxable account with dividend drag and a final sale, with return, tax-rate and horizon sensitivities, and the Short built on it |
| `mean-variance-optimization` | [Mean-Variance Optimization Out of Sample](https://summitward.com/learn/mean-variance-optimization-out-of-sample) | A known-parameter simulation of estimated mean-variance portfolios against the true optimum and 1/N, and a pre-registered walk-forward rerun of DeMiguel, Garlappi and Uppal's 1/N test on French's 10 industries through August 2026 and on Damodaran asset classes |
| `vtsax-fzrox-fskax` | [VTSAX vs FZROX vs FSKAX](https://summitward.com/compare/vtsax-vs-fzrox-vs-fskax) | Issuer-level holdings of the three total-market funds from SEC N-PORT filings and from same-date (August 31, 2026) issuer holdings files: overlap, active share and the weight in names FZROX omits; plus month-end returns since August 2018 |
| `tips-safer-than-they-seem` | [Are TIPS Safer Than They Seem? We Re-Ran Elm's Spending-Risk Test](https://summitward.com/learn/tips-safer-than-they-seem) | Elm Wealth's spending-risk test rebuilt from Fed and Treasury yield curves and CPI: annual change in 50-year real annuity spending for rolled 30-year TIPS, 30-year Treasuries and T-bills, 2000 to 2026, plus a 30-year-horizon rerun and duration table |
| `lifecycle-investing-leverage` | [Should Young Investors Use Leverage?](https://summitward.com/learn/lifecycle-investing-leverage) | Ayres and Nalebuff's leveraged lifecycle rule rebuilt on Shiller, NBER call money and French T-bill data: their 2008 Table V, 112 cohorts retiring 1915-2025 at borrowing spreads from 0 to 8 points, the same rule without borrowing, margin calls, a contribution pause and a block bootstrap; plus an exact check against the authors' workbook |
| `millionaire-renter` | [Why Would a Millionaire Rent? What 2025 Fed Data Shows](https://summitward.com/learn/millionaire-renter) | Share of U.S. families with $1M+ net worth, net worth excluding home equity, or financial assets who rent, from the 2025 and 2022 SCF with replicate-weight standard errors; a profile of millionaire renters vs owners; and a year-one user-cost example for a $1.5M home at October 2026 rates |
| `w2-vs-self-employed` | [Are W-2 Jobs a Scam? What Fed Data Shows About Getting Rich on a Salary](https://summitward.com/learn/are-w2-jobs-a-scam) | Net worth, net worth excluding business equity, financial assets and income of employee-headed vs self-employed-headed families from the 2025 and 2022 SCF, by age band, with replicate-weight standard errors; the work-status mix of $1M+, $3M+ and $10M+ families |

## Data sources

- S&P 500, Baa corporate and 10-year Treasury annual returns: Aswath Damodaran,
  [Historical Returns on Stocks, Bonds and Bills](https://pages.stern.nyu.edu/~adamodar/New_Home_Page/datafile/histretSP.html),
  NYU Stern. Used with attribution.
- Developed ex-US and emerging market annual returns, and US size and
  book-to-market, beta and variance portfolios and factors, and US
  book-to-market x operating profitability portfolios: Kenneth R. French,
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
  `safe-withdrawal-rate` uses the
  [datasets/s-and-p-500](https://github.com/datasets/s-and-p-500) CSV of the
  same series, which its maintainer dedicates to the public domain (ODC PDDL)
  and whose Shiller rows end in June 2023.
- Gold and commodity price indices: World Bank,
  [Commodity Price Data (Pink Sheet)](https://www.worldbank.org/en/research/commodity-markets).
  CC BY 4.0.
- Wealthfront risk-score ladder: twenty values read from Wealthfront's public
  [historical performance page](https://www.wealthfront.com/historical-performance)
  on the date stated in the file. Facts, reproduced for comment and analysis.

- Stock-level lifetime returns and wealth creation, 1926-2025: Hendrik
  Bessembinder (2026), "One Hundred Years in the U.S. Stock Markets,"
  [SSRN 6438198](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6438198).
  Summary figures quoted from the paper and hardcoded in the script.
- Trinity Study success rates: Cooley, Hubbard and Walz (1999), *Financial
  Counseling and Planning* 10(1), Table 2. Quoted figures.
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
