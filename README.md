# summitward-research

Scripts and data behind the numbers in Summitward's Learn guides, published so
that any figure a guide attributes to "our calculation" can be re-run.

Each folder is named for the guide slug it supports and contains the script,
the data files it reads, and a README stating the guide URL, the data
provenance and read dates, and the output the guide quotes. Every script runs
with the Python standard library only:

```bash
python3 <folder>/<script>.py
```

| Folder | Guide | What it reproduces |
| --- | --- | --- |
| `mortgage-rate-below-ten-percent` | [A 9% Mortgage Does Not Lose to 10% Stocks](https://summitward.com/learn/mortgage-rate-below-ten-percent) | Share of overlapping historical windows in which the S&P 500 beat a guaranteed return |
| `social-security-discount-rate` | [What Discount Rate Belongs on Social Security?](https://summitward.com/learn/social-security-discount-rate) | Present value of claiming at 62, 67 and 70 by real discount rate, with SSA mortality, and the crossover rates |
| `robo-advisor-returns` | [What Wealthfront's 9.8% Return Actually Measures](https://summitward.com/learn/robo-advisor-returns) | A published robo-advisor allocation rebuilt from index returns over two eras, and the reported risk-score ladder |

## Data sources

- S&P 500, Baa corporate and 10-year Treasury annual returns: Aswath Damodaran,
  [Historical Returns on Stocks, Bonds and Bills](https://pages.stern.nyu.edu/~adamodar/New_Home_Page/datafile/histretSP.html),
  NYU Stern. Used with attribution.
- Developed ex-US and emerging market annual returns: Kenneth R. French,
  [Data Library](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html).
  Used with attribution.
- Period life table: Social Security Administration, Office of the Chief
  Actuary, [2023 period life table](https://www.ssa.gov/oact/STATS/table4c6.html),
  embedded in the script. US government work, public domain.
- Wealthfront risk-score ladder: twenty values read from Wealthfront's public
  [historical performance page](https://www.wealthfront.com/historical-performance)
  on the date stated in the file. Facts, reproduced for comment and analysis.

## License

Code is MIT licensed (see `LICENSE`). Data files carry the terms of their
sources above.

## Corrections

Open an issue if a script does not reproduce the figure a guide quotes, or if
a data file has drifted from its source.
