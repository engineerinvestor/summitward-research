# dividend-stocks-vs-bonds-diversification

Supports https://summitward.com/learn/dividend-stocks-vs-bonds-diversification.

Tests a BofA Global Research statistic from its November 2, 2026 equity strategy
report, as summarized by [UnHideA](https://unhidea.com/en/articles/research-8f1495dd025e4d9f88a04525e661bf9b-en)
(the report itself is members-only): "a factor constructed from the
highest-yielding tenth of S&P 500 stocks had returns relative to the index that
were negatively correlated with index returns in 34 of the past 40 years. In
four of the past five years, its negative correlation was stronger than that of
gold, bonds, real estate and alternative assets."

Within any sample, Cov(R_D - R_M, R_M) = (beta - 1) Var(R_M), so the relative
correlation is negative exactly when the portfolio's beta is below 1. The script
counts calendar years with a negative absolute correlation, Corr(R_D, R_M), and
with a negative relative correlation, Corr(R_D - R_M, R_M), for high-dividend
portfolios, two stock/T-bill mixes, bonds, gold and REITs, then runs CAPM,
Fama-French three-factor and five-factor-plus-momentum regressions.

| Script | What it does | Output |
| --- | --- | --- |
| `analyze.py` | Calendar-year absolute and relative correlations and betas, 1986-2025 (also 1928-2025), for French's top 10%, 20% and 30% dividend-yield portfolios against the CRSP market, with an S&P 500 total-return robustness check; a 70/30 stock/T-bill mix and a beta-matched mix; VUSTX, VBMFX, GLD, GC=F and VGSIX on the same tests; full-period betas, volatilities and the beta_rel = beta - 1 check; factor regressions with Newey-West t-statistics; daily-return counts for SPYD, SCHD and VYM against SPY; the 2021-2026 daily comparison against TLT, IEF, BND, GLD and VNQ; 2022 returns, the value factor's returns in 2000, 2001 and 2022, the 2020 crash and trailing correlations | `results.json`, `out.txt` (printed output) |

Needs numpy, pandas and yfinance:

```bash
pip install numpy pandas yfinance
python3 analyze.py
```

## Data

| Source | Use | Terms |
| --- | --- | --- |
| `data/Portfolios_Formed_on_D-P.csv`, [Ken French Data Library](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html), built from the 202609 CRSP database, downloaded 2026-11-24 | Portfolios formed each June on trailing 12-month dividends over June market equity, NYSE breakpoints, NYSE/AMEX/NASDAQ stocks. Sections "Value Weight Returns -- Monthly", "Equal Weight Returns -- Monthly" and "Number of Firms in Portfolios" | Copyright Eugene F. Fama and Kenneth R. French; redistributed unmodified for reproduction, as in other folders of this repo |
| `data/F-F_Research_Data_Factors.csv`, same library and cut | Market = Mkt-RF + RF (CRSP value-weighted); T-bills = RF; FF3 regressions | As above |
| `data/F-F_Research_Data_5_Factors_2x3.csv`, `data/F-F_Momentum_Factor.csv`, same library and cut | Five-factor plus momentum regressions | As above |
| Yahoo Finance via yfinance, daily dividend-adjusted closes, 1985-01-01 to the 2026-11-23 close | ^SP500TR, VUSTX, VBMFX, VGSIX, GLD, GC=F, SPY, SPYD, SCHD, VYM, TLT, IEF, BND, VNQ | Not committed; downloaded into `.cache/` on first run. Yahoo revises adjusted closes, so a rerun can move the fourth decimal |

## Definitions and caveats

- French's top dividend-yield decile held 107 to 207 stocks a month over
  1986-2025 (median 163), drawn from all NYSE, AMEX and NASDAQ payers. BofA's
  factor is the top tenth of the S&P 500, about 50 stocks. This is an
  independent test of the same statistic, not a replication.
- BofA's return frequency, weighting and treatment of the other assets are not
  in the public summary. French and mutual-fund series here use 12 monthly
  returns per calendar year; ETFs use daily returns.
- Mutual-fund returns (VUSTX, VBMFX, VGSIX) depend on Yahoo's distribution
  adjustment. GC=F is a rolled front-month futures price series and is reported
  only as a sensitivity for GLD.
- The 2020 crash is measured from each fund's highest close in January or
  February 2020 to its lowest close through April 30, 2020.
- No fees, taxes or trading costs.

## Output quoted in the guide (`out.txt`)

```
Top 10% by yield, value-weighted     1986-2025: abs neg  3/40, rel neg 35/40
Top 10% by yield, equal-weighted     1986-2025: abs neg  0/40, rel neg 31/40
Top 20% by yield, value-weighted     1986-2025: abs neg  0/40, rel neg 34/40
Top 20% by yield, equal-weighted     1986-2025: abs neg  0/40, rel neg 34/40
Top 30% by yield, value-weighted     1986-2025: abs neg  0/40, rel neg 36/40
70% market, 30% T-bills                        abs neg 0/40, rel neg 40/40
Long-term Treasuries (VUSTX)   1987-2025: abs neg 20/39, rel neg 38/39
Total bond market (VBMFX)      1987-2025: abs neg 17/39, rel neg 39/39
Gold (GLD)                     2005-2025: abs neg  8/21, rel neg 21/21
REITs (VGSIX)                  1997-2025: abs neg  1/29, rel neg 20/29
```

Top 10% value-weighted, 1986-01 to 2025-12 (n = 480): beta 0.667, volatility
16.9% (market 15.6%); five-factor plus momentum alpha +0.91% a year (Newey-West
t 0.51), market 0.770, HML 0.630, CMA 0.312, Mom -0.122, adjusted R-squared
0.661.

2021-2025, daily returns against SPY: SPYD's relative correlation was below
every other asset's absolute correlation in 5 of 5 years and below every other
asset's relative correlation in 0 of 5.

Value factor (HML) by year: 2000 +44.5%, 2001 +15.6%, 2022 +31.7% (CRSP market
-11.6%, -11.2%, -19.9%).
