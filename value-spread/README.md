# value-spread

Supports https://summitward.com/markets/value-spread and
https://summitward.com/learn/is-the-value-premium-back.

The value spread is the book-to-market ratio of the value portfolio divided by
that of the growth portfolio, which equals growth's price-to-book divided by
value's. `extract.py` builds it from portfolio characteristics in the Kenneth
French Data Library; the math is in `value_spread.py` (standard library only).

```bash
python3 extract.py            # uses the committed 202609 CSVs in data/
python3 extract.py --refresh  # downloads the current French files over them
```

## What it computes

1. **Small-cap and large-cap spreads, monthly since June 1926.** From
   `6_Portfolios_2x3`: value is the top 30% of book-to-market within each size
   half, growth the bottom 30%, value-weighted. French's block
   "BE_FYt-1/ME_June t" gives each portfolio's book-to-market at June prices
   when the portfolios are formed (the July row of each year). Between Junes,
   each portfolio's book-to-market is rolled forward on its value-weighted
   return without dividends (`6_Portfolios_2x3_Wout_Div`), holding book value
   per share fixed.
2. **Profitability-controlled spreads, annual since 1963.** From
   `32_Portfolios_ME_BEME_OP_2x4x4`: within each size half and each
   operating-profitability quartile, the highest book-to-market quartile over
   the lowest, averaged geometrically across the four quartiles.
3. **All-stock spreads on book, earnings and cash flow, annual.** Top 30% over
   bottom 30% from the "Sum of X / Sum of ME" blocks of the univariate sorts
   (December prices of the prior year).
4. **Percentiles.** Empirical ranks: the share of observations at or below
   the latest reading, over the full history and since 1963. No normal
   distribution is assumed.
5. **What each June reading was followed by.** Annualized total return of
   value minus growth (same size half) over the next 5 and 10 years from each
   July, by tercile of the starting spread (ranked with hindsight); an
   in-sample regression of that return on the log spread with Newey-West
   standard errors (lag = horizon in years, since windows overlap); and a
   Campbell-Thompson out-of-sample R-squared in which each forecast is fit
   only on outcomes already known at its date and compared with the running
   historical mean.
6. **Re-sort revisions.** The change in the spread at each June, between last
   year's portfolios rolled forward 12 months and the newly formed portfolios.
7. **Recent returns** of the four corner portfolios and of HML and SMB.

## Output quoted on the site (202609 data)

- Small caps: 6.33 at the June 2026 formation (8.09 in June 2025), an
  estimated 6.52 for September 2026, higher than in 82% of months since 1926
  and 92% since 1963.
- Large caps: 9.71 in June 2026, an estimated 10.06 for September 2026,
  higher than in 97% of months since 1926. Holding the June 2025 portfolios
  fixed, prices narrowed the spread to 7.74 by June 2026; the June 2026
  re-sort put it at 9.71.
- Profitability-controlled small caps: 6.45 in June 2026.
- All stocks at December 2025 prices: book-to-market spread 9.90, earnings
  4.35, cash flow 4.46.
- Small caps, 5 years after each June 1926-2021: widest third of starting
  spreads +4.8% a year (value trailed in 38%), narrowest third +5.3% (22%);
  out-of-sample R-squared -1.7% at 5 years and -14.3% at 10.

Every figure is in `output/value_spread.json`; the printed run is in
`output/output.txt`.

## Data

Kenneth R. French Data Library, CSVs extracted from the library's zip files,
202609 CRSP vintage, downloaded Nov 15, 2026: `6_Portfolios_2x3`,
`6_Portfolios_2x3_Wout_Div`, `32_Portfolios_ME_BEME_OP_2x4x4`,
`32_Portfolios_ME_BEME_OP_2x4x4_Wout_Div`, `Portfolios_Formed_on_BE-ME`,
`Portfolios_Formed_on_E-P`, `Portfolios_Formed_on_CF-P`,
`F-F_Research_Data_Factors`. Copyright Eugene F. Fama and Kenneth R. French;
see https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html.
French's monthly updates extend every series and can revise history, so a
rerun with `--refresh` will move the figures.

## Limits

U.S. stocks only: French's developed and emerging market files carry returns
but not valuation ratios. Book value omits most intangible capital. These are
portfolio-level characteristics, not any fund's holdings.
