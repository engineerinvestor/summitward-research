# should-you-index-bonds

Supports https://summitward.com/learn/should-you-index-bonds.

Compares two bond index ETFs (iShares AGG, Vanguard BND) with two systematic
core bond ETFs (Dimensional DFCF, Avantis AVIG) and Dimensional's older
Aggregate-benchmarked mutual fund (DFAPX, against Vanguard's VBTLX):

- **A. Holdings mix** of AGG, BND, DFCF and AVIG by SEC N-PORT category, as a
  percent of net assets, from each fund's latest public N-PORT-P filing.
- **B. Corporate issuer concentration** in AGG and BND: corporate and REIT
  debt grouped by legal entity identifier (LEI), falling back to the issuer
  name when no LEI is reported.
- **C. Fund vs index fund** over each common live window: CAGR, volatility,
  maximum drawdown, tracking error, beta, t-statistic of the mean monthly
  difference.
- **D. Factor regression** of the monthly return difference on a term factor
  (IEF minus BIL) and a credit factor (SPIB minus IEI, two ETFs of similar
  duration), OLS with Newey-West standard errors (lags = floor(4(n/100)^(2/9))).
  Robustness: credit as LQD minus IEF.
- **E. Static replica** for DFCF and AVIG: BND plus VCIT, with the VCIT weight
  set so the replica's corporate share equals the fund's in its first public
  N-PORT filing, using the BND and VCIT filings on or before that date.
  Rebalanced every January. The fund minus the replica is analyzed as in C and
  D. Sensitivity runs (not the pre-set test): monthly rebalancing, and the
  weight implied by the latest filings, which uses end-of-window information.
- **F. Detection math**: years before an edge reaches t = 1.96 on average at
  the measured tracking error, (1.96 x TE / edge)^2.

These rules were fixed before the run. One definitional change was made after
inspecting the filings: supranational and foreign-agency issuers (World Bank,
EIB, KfW and similar), which Vanguard and Avantis file as corporate and
Dimensional files as "Supranational", are reclassified as government-related
for every fund so corporate shares are comparable. It moves the replica
weights by about 0.01 to 0.02 and does not change any conclusion.

```bash
pip install numpy pandas yfinance
SEC_USER_AGENT="Your Name you@example.com" python3 fetch_data.py   # writes data/
python3 analyze.py                                                  # writes output/
```

Data are frozen at October 2026 (`END_MONTH` in `fetch_data.py`); rerunning
`fetch_data.py` later will pull newer filings and prices and shift every number.
`analyze.py` reads only `data/`.

## Data

- `data/holdings_<TICKER>_<period>.csv.gz`: every position in the N-PORT-P
  filing named in the file's first line (SEC EDGAR, public domain).
- `data/monthly_prices.csv`: month-end dividend-adjusted closes from Yahoo
  Finance via yfinance. ETF returns are market-price returns, not NAV.

## Output

The printed output of the run the guide quotes is in `output/output.txt`,
everything is in `output/results.json`, and the compact file the guide reads
is `output/should-you-index-bonds.json`.

Results the guide quotes:

| Item | Value |
| --- | --- |
| AGG mix (N-PORT 2026-08-31): Treasury, agency MBS, corporate | 46.02%, 23.71%, 24.52% |
| BND mix (N-PORT 2026-06-30): Treasury, agency MBS, corporate | 48.14%, 19.78%, 25.55% |
| AGG corporate issuers; largest (JPMorgan); top 10; top 25 | 1,160; 0.572%; 3.89%; 6.56% |
| BND largest corporate issuer (JPMorgan); top 10 | 0.609%; 3.81% |
| Corporate share: DFCF (2026-07-31), AVIG (2026-08-31) | 48.52%, 60.63% |
| AVIG vs AGG, 2020-11 to 2026-10: CAGR, TE, credit beta (NW t), alpha (NW t) | -0.19 vs -0.21%; 0.76%; 0.168 (3.3); +0.02%/yr (0.12) |
| DFCF vs AGG, 2021-12 to 2026-10 | -0.10 vs -0.23%; 1.08%; 0.224 (2.6); -0.10%/yr (-0.25) |
| DFAPX vs VBTLX, 2011-04 to 2026-10 | 2.60 vs 2.25%; 0.89%; active t 1.59; alpha +0.17%/yr (1.02) |
| AVIG vs replica (38.1% VCIT): CAGR, gap, t | -0.19 vs +0.19%; -0.38; -2.18 |
| DFCF vs replica (33.4% VCIT) | -0.10 vs +0.17%; -0.28; -0.72 |
| Years for a 0.25%/yr edge to reach t = 1.96 at AVIG's TE vs AGG | 35 |
