# does-a-crash-prove-a-bubble

Supports https://summitward.com/learn/does-a-crash-prove-a-bubble.

Tests the claim in Jeff Yass's November 6, 2026 Wall Street Journal op-ed
("There's No Such Thing as a Stock-Market Bubble") that investors who held the
whole internet sector long enough came out ahead.

| Script | What it does | Output |
| --- | --- | --- |
| `analyze.py` | Growth of $1 in Ken French's HiTec industry portfolio (value- and equal-weighted) against the total US market and T-bills, nominal and after inflation, from four entry dates fixed in advance (close of Dec 1998, Dec 1999, Mar 2000, Dec 2000) to Sep 2026; recovery dates against the starting dollar, inflation, T-bills and the market; the quarterly chart series from Mar 2000 | `results.json`, `out.txt` (printed output) |

Standard library only:

```bash
python3 analyze.py
```

## Data (in `data/`)

| File | Source | Terms |
| --- | --- | --- |
| `5_Industry_Portfolios.csv` | [Ken French Data Library](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html), 5 industry portfolios, built from the 202609 CRSP database | Copyright Eugene F. Fama and Kenneth R. French; redistributed here unmodified for reproduction, as in other folders of this repo |
| `F-F_Research_Data_Factors.csv` | Same library, Fama-French 3 factors, 202609 CRSP cut. Market = Mkt-RF + RF; T-bills = RF | As above |
| `Siccodes5.txt` | Same library, SIC definitions of the 5 industries. HiTec = Business Equipment, Telephone and Television Transmission | As above |
| `cpi_u_nsa.json` | BLS CPI-U, U.S. city average, all items, not seasonally adjusted (CUUR0000SA0), from the BLS public API, Jan 1998 to Oct 2026 | Public domain (U.S. government work) |

BLS did not publish October 2025 CPI (2025 lapse in appropriations).
`analyze.py` fills it with the geometric mean of September and November 2025;
it affects only real-return dates near that month.

## Definitions and caveats

- HiTec is broader than "internet stocks": it holds hardware, software,
  semiconductors and telecom carriers. Most e-commerce firms (SIC 5000-5999)
  sit in the Cnsmr portfolio, so this is the closest long public series, not a
  replica of a 1999 internet basket.
- Returns include dividends (full-history check: HiTec 10.77% and the market
  10.32% a year, July 1926 to December 2025, which a price-only series could
  not reach). French's page does not document delisting treatment.
- "For good" dates are the month after the last month-end below the
  comparison line. "First back" dates are also in `results.json`, but for
  entries before the March 2000 peak they can fall before the peak, so the
  guide quotes only the "for good" dates.
- No fees, trading costs or taxes.

## Output quoted in the guide (`out.txt`)

Entry at the close of March 2000, to September 2026 (26.5 years):

- HiTec value-weighted: $1 to $7.56 (7.9% a year), real $3.84 (5.2% a year);
  maximum drawdown 77.9% at September 2002; back above $1 for good from July
  2016; ahead of T-bills for good from July 2017; real recovery for good from
  January 2019; still behind the market (0.89 of the market's ending wealth;
  low 0.40).
- Total market: $1 to $8.49 (8.4% a year). T-bills: $1 to $1.64.
- HiTec equal-weighted: $1 to $5.81 (0.68 of the market).

Other entry dates (HiTec value-weighted vs market, ending wealth):

| Entry (close of) | HiTec | Market | Ahead of the market for good from |
| --- | --- | --- | --- |
| Dec 1998 | 14.34 | 11.06 | May 2023 |
| Dec 1999 | 8.53 | 8.83 | still behind |
| Mar 2000 | 7.56 | 8.49 | still behind |
| Dec 2000 | 13.80 | 9.99 | Mar 2023 |

## Break-even tables

The guide's break-even probabilities are closed-form, not simulated:
p* = (P (1 + r)^T − X_lose) / (X_win − X_lose), with P = $100, X_win = $1,000,
X_lose = $0, annual compounding. The calculator in the guide implements the
same formula.
