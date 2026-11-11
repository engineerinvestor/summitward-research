# avantis-avuc-avnc-avtm

Numbers behind <https://summitward.com/learn/avantis-avuc-avnc-avtm>,
<https://summitward.com/compare/avuc-vs-avus> and
<https://summitward.com/compare/avtm-vs-avge>: what the three Avantis ETFs
seeded through Section 351 exchanges in 2026 (AVUC, AVNC, AVTM) actually hold,
and how far AVUC's portfolio sits from AVUS, the older Avantis fund whose
prospectus strategy text it repeats.

```bash
python3 avantis-avuc-avnc-avtm/fetch_data.py   # refreshes every holdings file
python3 avantis-avuc-avnc-avtm/analyze.py      # prints the report, writes out/results.json
```

`analyze.py` needs numpy, pandas and openpyxl; `fetch_data.py` uses only the
standard library. Running `fetch_data.py` again replaces the iShares and State
Street files with that day's holdings, so the committed `data/` folder is the
record of what the guide quotes. `out/` is gitignored.

## Data

All holdings files are dated **2026-11-09**, so nothing is repriced. The fact-sheet file is dated Sep 30, 2026.

| File | Source |
|---|---|
| `data/AVUC_2026-11-09.csv`, `AVUS_`, `AVNC_`, `AVTM_`, `AVDE_`, `AVEM_`, `AVUQ_` | Avantis daily holdings, read from the page data embedded in each fund page at avantisinvestors.com/avantis-investments/ |
| `data/ishares_<TICKER>.csv` | iShares `latest-holdings.csv` for IWF, IWD, IWB, IVV, OEF, IYW, IWO, SOXX, IJH, and IWV (Russell 3000, the benchmark proxy) |
| `data/ssga_XLY.xlsx`, `data/ssga_SPY.xlsx` | State Street daily holdings workbooks |
| `data/factsheets_2026-09-30.csv` | Weighted average market cap, book/market and profits/book from the Sep 30, 2026 quarterly fact sheets of AVNC, AVNM, AVDE and AVEM and their benchmarks (URLs in the file) |
| `data/trading_2026-11-09.csv` | 30-day median bid-ask spread, that day's spread and volume from the trading data embedded in each Avantis fund page, as of Nov 9, 2026 |
| `data/ncsr_2026-08-31_tax_basis.csv` | Federal tax cost and net tax appreciation of investments, American Century ETF Trust Form N-CSR for the year ended Aug 31, 2026 (filed Oct 29, 2026), sec.gov/Archives/edgar/data/1710607/000171060726000330/ |

## Method notes

- Issuers are keyed by the first six CUSIP characters so share classes
  collapse. iShares files have no CUSIP; their tickers are mapped to CUSIPs
  through the U.S.-listed lines of the Avantis and State Street files. The
  international funds are left out of that map because local tickers collide
  with U.S. ones (Deutsche Telekom is "DTE" in Frankfurt). After the fix,
  0.06% of AVUC's look-through weight stays keyed by ticker, mostly REITs that
  neither AVUC nor AVUS holds.
- Overlap is the sum of the smaller weight in each shared issuer, with each
  portfolio's stocks rescaled to sum to one. Active share = 100 - overlap.
- Look-through expands an ETF line into that ETF's stock weights. AVUC's ETF
  sleeve is 18.54% of the fund: 15.36% is expanded, 0.45% is SGOV (T-bills,
  dropped), and 2.73% stays unexpanded (largest: QQQ 0.42%, VTV 0.26%, VUG
  0.15%, SMH 0.15%). Unexpanded lines are dropped and the rest rescaled.
- IWV holds about 2,590 stocks against the Russell 3000's roughly 3,000 and
  excludes some foreign-domiciled names that AVUS holds (Seagate, TE
  Connectivity, MercadoLibre); 0.78% of AVUS sits outside it.
- Size bands rank Russell 3000 issuers by IWV weight: the largest names that
  make up 50% of the index, the next 40%, and the last 10%.
- "Russell value share" covers Russell 1000 stocks only. Each stock's cap is
  split between the Russell 1000 Value and Growth indexes, so
  w_IWB = a * w_IWD + (1 - a) * w_IWF; the fit gives a = 0.5513 with
  R² = 1.00000. A stock's value fraction is a * w_IWD / w_IWB, and a fund's
  value share is its weight-averaged value fraction. The Russell 1000 scores
  55.1% by construction. Russell's style split uses book-to-price for value
  and growth forecasts for growth, which differs from Avantis's own
  book-to-price and cash-profitability measures.
- Style buckets for AVUC's ETFs are assigned by hand from fund names
  (`BUCKET` in `analyze.py`).
- Bounds: the central look-through figures drop the unexpanded ETF lines and
  rescale. The bounds keep those lines (2.74% of AVUC's equity, excluding
  T-bills and cash) in the denominator and assign them the least and most
  favorable stocks: no overlap or full overlap with AVUS, none or all in the
  smallest-10% band, all growth or all value.
- The 70/30 AVDE + AVEM blend weights the two fact sheets' characteristics
  70/30 (AVNM's target split). Weighted averages are linear in portfolio
  weights, so this approximates a 70/30 portfolio; ACWI ex USA IMI is not
  exactly 70/30, and its own figures are printed for comparison.

## Headline output (holdings of Nov 9, 2026)

AVUC ($361.9M):
- 81.38% stocks, 18.54% ETFs in 70 positions, 0.07% cash. ETF sleeve by
  sponsor: iShares 14.71, Vanguard 1.42, State Street 1.23, Invesco 0.50,
  Avantis 0.30. By style: growth 7.71, value 6.39, broad 1.75, sector 1.73.
  Largest: IWF 6.67, IWD 5.87, XLY 0.77, SGOV 0.45, QQQ 0.42.
- 2.19% in 70 non-U.S. stocks (Novartis ADR 0.64, Nestle ADR 0.35, Nu
  Holdings 0.26, TSMC ADR 0.20). AVUS holds none.
- Overlap with AVUS: 62.86% (direct stocks only), 65.69% (look-through).
- Overlap with the Russell 3000 proxy: AVUS 74.36%, AVUC look-through 74.33%.
- Size bands (top 50% / next 40% / bottom 10% / outside the proxy):
  AVUS 42.03 / 42.22 / 14.97 / 0.78; AVUC look-through 52.37 / 40.87 / 4.25 /
  2.51; Russell 3000 proxy 50.2 / 39.8 / 10.0.
- Russell value share: AVUS 60.5%, AVUC direct stocks 59.6%, AVUC
  look-through 57.8%, Russell 1000 55.1%. IWF and IWD in the proportions AVUC
  holds them score 48.8%, so the pair leans slightly growth.
- Largest active weights, AVUC look-through minus AVUS (points): Berkshire
  Hathaway +1.81, JPMorgan +1.67, Johnson & Johnson +1.26, Alphabet +1.06,
  Mastercard +1.01, Philip Morris +0.90 (AVUS holds none), Procter & Gamble
  +0.86; Meta -0.75, Amazon -1.02, Micron -1.16. Top-10 issuers: AVUC
  34.21%, AVUS 30.42%, Russell 3000 proxy 34.66%.
- Most of each overweight is held directly (share of the whole fund):
  Berkshire 2.33, JPMorgan 2.82, Johnson & Johnson 1.80, Mastercard 1.48,
  Procter & Gamble 1.10, Philip Morris 0.82.
- Bounds for the 2.74% of equity left unexpanded: overlap with AVUS 64.96 to
  67.70; smallest-10% band 4.14 to 6.88 (AVUS 14.97); Russell value share 56.2
  to 59.0 (AVUS 60.5).
- "Non-U.S." follows Avantis's country field, which tags some
  foreign-domiciled companies in AVUS (Accenture, Medtronic, Chubb, Linde) as
  United States.

AVNC ($98.7M): ETFs 17.41% in 25 positions (VWO 9.07, AVDV 1.69, VEU 1.50,
AVEM 0.93, AAUS 0.76, VXUS 0.56); Vanguard 11.14, Avantis 3.06. U.S. stocks
held directly 5.61% (38 names) plus 0.78% in U.S. equity ETFs (AAUS, AAEQ).

AVTM ($761.8M): ETFs 18.23%, all Avantis (AVDE 10.24, AVEM 4.74, AVUQ 3.18,
AVDV 0.06). Look-through U.S. weight 84.96%.

AVNC against like-for-like portfolios, Sep 30, 2026 fact sheets (weighted
book/market, profits/book, market cap): AVNC 0.34, 0.38, $299.0B; 70% AVDE +
30% AVEM 0.495, 0.342, $183.6B; AVNM 0.55, 0.35, $132.1B; MSCI ACWI ex USA IMI
0.39, 0.32, $226.8B. AVNM held Avantis value funds (AVIV 20.23, AVES 9.92,
AVDV 6.86) besides AVDE 39.76, AVEM 18.85 and AVDS 2.14.

30-day median bid-ask spreads on Nov 9, 2026: AVUC 0.06, AVUS 0.02, AVNC 0.23,
AVNM 0.11, AVTM 0.11, AVGE 0.09, AVDE 0.01, AVEM 0.02. Volume that day: AVUC
309 shares, AVNC 755, AVTM 395.

Unrealized gain as a share of investments on Aug 31, 2026 (N-CSR): AVTM
61.9% ($490.7M on $793.0M), AVUS 30.2%, AVGE 24.1%, AVNM 21.7%. Neither AVTM
nor AVUS distributed long-term capital gains in fiscal 2026; AVUS and AVGE
also paid none in fiscal 2025. AVTM received $869.6M of securities in kind
and paid out $216.4M in kind in its first period (Jan 29 to Aug 31, 2026).
