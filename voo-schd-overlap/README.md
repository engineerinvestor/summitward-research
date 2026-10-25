# voo-schd-overlap

Numbers behind <https://summitward.com/learn/voo-schd-overlap>: VOO and SCHD
holdings overlap, how the funds' returns move together, and their Fama-French
five-factor loadings.

```bash
python3 voo-schd-overlap/fetch_data.py   # refreshes prices, closes, factors
python3 voo-schd-overlap/analyze.py      # prints the report, writes out/results.json
```

Needs numpy, pandas and yfinance. `analyze.py` prints every number the guide
quotes; `out/` is gitignored, so rerun it to regenerate the JSON.

## Data

| File | Source | As of |
|---|---|---|
| `data/schd_holdings_2026-10-13.csv` | Schwab, schwabassetmanagement.com/allholdings/SCHD (copied from the page, which refuses scripted requests) | 2026-10-13 |
| `data/ivv_latest.csv` | iShares IVV holdings CSV (S&P 500; VOO proxy) | 2026-10-22 |
| `data/ijh_latest.csv` | iShares IJH holdings CSV (S&P MidCap 400) | 2026-10-23 |
| `data/constituent_closes.csv` | Yahoo Finance unadjusted closes for every IVV stock | 2026-10-13 and 2026-10-22 |
| `data/fund_prices_daily.csv` | Yahoo Finance adjusted closes: VOO SCHD IVV RSP IJH VXUS BND | 2011-10-03 to 2026-10-23 |
| `data/F-F_Research_Data_5_Factors_2x3.csv` | Kenneth French Data Library | 202608 CRSP file |

## Method notes

- iShares serves only its latest holdings file, so IVV weights are repriced to
  the SCHD date as share quantity times the 2026-10-13 close. Without repricing
  the overlap is 8.29%; with it, 7.67%. SCHD rose 6.1% and VOO fell 1.8%
  between the two dates.
- Overlap is the sum of the smaller weight in each shared stock, with each
  fund's stock weights rescaled to sum to one (SCHD's non-stock lines are
  0.04%). Matched by ticker. A Hologic stub left in IVV at $0.01 after the
  company went private is dropped.
- The RSP overlap assumes equal weights at a rebalance (1/503 per line).
- Monthly statistics use full months, 2011-11 to 2026-09; daily use
  2011-10-21 to 2026-10-23. Factor regressions run 2011-11 to 2026-08 with
  Newey-West (6 lag) standard errors.

## Headline output

- Overlap 7.67%; 45 shared stocks of SCHD's 98; 94.97% of SCHD in S&P 500
  stocks; 53 SCHD stocks (5.03%) outside it. VOO's weight is the smaller one
  in all 45 shared stocks.
- Monthly correlation with VOO: IVV 1.00, RSP 0.94, IJH 0.90, SCHD 0.84,
  VXUS 0.83, BND 0.36. IJH holds none of the S&P 500 stocks.
- VOO-SCHD daily correlation: 0.95 in 2020, 0.60 in 2024, 0.73 in 2025, 0.20
  in 2026 through October 23.
- SCHD FF5: market 0.83, SMB 0.07, HML 0.20, RMW 0.33, CMA 0.30, R² 0.852.
