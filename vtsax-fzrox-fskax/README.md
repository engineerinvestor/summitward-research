# vtsax-fzrox-fskax

Supports https://summitward.com/compare/vtsax-vs-fzrox-vs-fskax and the
figures it shares with https://summitward.com/learn/fidelity-zero-funds and
https://summitward.com/compare/fzrox-vs-vtsax.

`analyze.py` compares Vanguard's total-market fund (VTSAX, Admiral shares of
the Vanguard Morningstar Total Stock Market Index Fund), Fidelity ZERO Total
Market Index Fund (FZROX) and Fidelity Total Market Index Fund (FSKAX) in two
ways:

- **Holdings.** Equity positions from each fund's latest public SEC Form
  N-PORT-P, grouped by issuer (first six CUSIP characters, else ISIN, else
  name). It reports how much of VTSAX and FSKAX sits in issuers ranked below
  FZROX's issuer count by size, which needs no cross-fund matching, and the
  weight of VTSAX and FSKAX issuers that FZROX's filing does not hold.
- **Returns.** Month-end total returns from August 31, 2018, FZROX's first
  month end, to September 30, 2026: annualized and calendar-year returns,
  tracking error, and rolling 36- and 60-month comparisons. Section 5 adds
  five-year returns of the three ZERO index funds (FZROX, FZILX, FNILX)
  against VTSAX, VTIAX and FXAIX for the ZERO-funds guide.

Caveats:

- The three filings have different period ends (VTSAX June 30, FSKAX May 31,
  FZROX July 31, 2026) because the funds' fiscal quarters do not line up, so
  the "not held by FZROX" figure mixes index differences with timing. Example:
  SpaceX listed on June 12, 2026, is in VTSAX's June 30 filing and absent from
  FZROX's July 31 filing. Exxon Mobil's July 1, 2026 move to a Texas holding
  company changed its CUSIP between filings; `ALIASES` maps the two.
- The concentration figures (top 10, effective number of issuers) come from
  different dates and are not comparable across funds. The page quotes
  top-10 weights from the issuers' own September 2026 fund pages instead.
- Rolling windows overlap heavily: 62 rolling 36-month windows in 97 months
  hold about 2.7 independent three-year periods.
- Calendar-year figures here are month-end to month-end from adjusted closes;
  they match the issuers' published calendar-year returns to within 0.02
  points. The page quotes the issuers' figures.

Data:

- `data/holdings_*.csv`: SEC EDGAR N-PORT-P filings (URLs in each file's
  first line), downloaded 2026-10-15. US government records, public domain.
- `data/monthly_prices.csv`: Yahoo Finance adjusted closes (dividends and
  capital gains reinvested, net of expense ratios), month ends, read
  2026-10-15.

```bash
python3 analyze.py         # standard library only
python3 fetch_data.py      # re-download; prices need yfinance
```

`fetch_data.py` asks the SEC for files, and the SEC rejects requests without
a contact address in the User-Agent; set `SEC_USER_AGENT="Name you@example.com"`.

Output quoted on the pages (run 2026-10-15; growth of $10,000 added 2026-10-16):

```
1. Equity holdings by issuer (SEC N-PORT-P)
   VTSAX N-PORT-P series S000002848, period 2026-06-30, https://www.sec.gov/Archives/edgar/data/36405/000003640526000480/primary_doc.xml
   VTSAX: 3528 equity positions, 3498 issuers, top 10 issuers 33.51%, effective number of issuers 61
   FZROX N-PORT-P series S000063106, period 2026-07-31, https://www.sec.gov/Archives/edgar/data/819118/000003540226006318/primary_doc.xml
   FZROX: 2640 equity positions, 2615 issuers, top 10 issuers 34.77%, effective number of issuers 55
   FSKAX N-PORT-P series S000006026, period 2026-05-31, https://www.sec.gov/Archives/edgar/data/819118/000003540226004751/primary_doc.xml
   FSKAX: 3736 equity positions, 3698 issuers, top 10 issuers 36.01%, effective number of issuers 53

2. Weight in issuers ranked below FZROX's issuer count (2615)
   VTSAX: issuers ranked 2616-3498 (883 names) hold 0.089% of equity value; ranked 3001+ hold 0.018%
   FSKAX: issuers ranked 2616-3698 (1083 names) hold 0.089% of equity value; ranked 3001+ hold 0.021%

3. Weight in issuers FZROX's filing does not hold
   VTSAX: 928 issuers, 0.51% of equity value
      Space Exploration Technologies Corp      0.140%
      Waste Connections Inc                    0.059%
      Chart Industries Inc                     0.014%
      TopBuild Corp                            0.014%
      JFrog Ltd                                0.013%
      Forgent Power Solutions Inc              0.010%
      Nuvalent Inc                             0.009%
      Janus Henderson Group PLC                0.009%
   FSKAX: 1085 issuers, 0.25% of equity value
      TOPBUILD CORP                            0.016%
      CHART INDUSTRIES INC                     0.013%
      MASIMO CORP                              0.011%
      CLEARWATER ANALYTICS HOLDINGS INC        0.010%
      JANUS HENDERSON GROUP PLC                0.009%
      NUVALENT INC                             0.008%
      TAYLOR MORRISON HOME CORP                0.008%
      FORGENT POWER SOLUTIONS INC              0.006%

4. Total returns, 2018-08-31 to 2026-09-30 (97 months)
   VTSAX: 13.71% a year; $10,000 grew to $28,254
   FZROX: 13.85% a year; $10,000 grew to $28,529
   FSKAX: 13.71% a year; $10,000 grew to $28,251

   Calendar years (December to December month ends), %
   year     VTSAX    FZROX    FSKAX
   2019     30.79    31.15    30.92
   2020     20.98    20.51    20.79
   2021     25.72    26.00    25.66
   2022    -19.52   -19.21   -19.53
   2023     25.99    26.20    26.12
   2024     23.74    23.94    23.89
   2025     17.12    17.23    17.06

   Pairs (A minus B)
   FZROX-VTSAX: gap +0.136 pts/yr (fee gap +0.040), tracking error 0.215 pts, correlation 0.99992
      relative wealth low -0.32% high +0.99% end +0.97%; FZROX ahead in 58 of 62 rolling 36-month and 38 of 38 rolling 60-month windows
   FZROX-FSKAX: gap +0.138 pts/yr (fee gap +0.015), tracking error 0.185 pts, correlation 0.99994
      relative wealth low -0.14% high +1.03% end +0.98%; FZROX ahead in 62 of 62 rolling 36-month and 38 of 38 rolling 60-month windows
   FSKAX-VTSAX: gap -0.002 pts/yr (fee gap +0.025), tracking error 0.123 pts, correlation 0.99998
      relative wealth low -0.25% high +0.03% end -0.01%; FSKAX ahead in 40 of 62 rolling 36-month and 28 of 38 rolling 60-month windows

5. ZERO funds vs counterparts, 2021-09-30 to 2026-09-30, % a year
   FZROX  12.79   VTSAX  12.55   gap +0.24
   FZILX   9.97   VTIAX   9.30   gap +0.67
   FNILX  13.49   FXAIX  13.77   gap -0.29
```
