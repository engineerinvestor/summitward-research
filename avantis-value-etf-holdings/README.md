# avantis-value-etf-holdings

Supports https://summitward.com/learn/avantis-value-etf-holdings.

What AVLV, AVUV, AVDV and AVGV held at the Nov 20, 2026 close, measured
against the Russell indexes, with SEC-filed earnings and book values for every
U.S. stock.

| Script | What it does |
|---|---|
| `fetch_data.py` | Avantis daily holdings (AVLV, AVUV, AVDV, AVGV and AVGV's other sleeves AVIV, AVES, AVMV) from the data embedded in each fund page, and iShares `latest-holdings.csv` for IWB, IWD, IWF, IWM, IWN and IWO. Refuses to finish if the as-of dates differ. Rerunning it overwrites the snapshot with today's files. |
| `fetch_fundamentals.py` | For every U.S. stock in those files: trailing-twelve-month net income (latest 10-K year + latest year-to-date 10-Q - the same period a year earlier), latest stockholders' equity and cover-page shares outstanding, from the SEC XBRL `companyconcept` API. Only 10-K/10-Q/20-F/40-F facts count; proxy statements re-file the same numbers later and would otherwise win the latest-filed tie-break. Needs `SEC_USER_AGENT` set to a name and contact address. |
| `analyze.py` | The guide's numbers: active weights for a fixed list of names, loss share, trailing P/E bands, aggregate P/E and P/B, the share Russell classifies as growth (IWB = a·IWD + (1-a)·IWF, solved by least squares, as in `../avantis-avuc-avnc-avtm`), active share, AVDV country and sector mix, and AVGV's look-through. Writes `output/holdings_summary.json`. |
| `fetch_cfo.py` | Trailing operating cash flow for every U.S. stock in AVLV and IWD (plus the AVUV names the guide discusses), so single companies and fund averages can be compared on the same unadjusted cash-flow/book basis (AVLV's prospectus names "adjusted cash from operations to book value"). Writes `data/cfo_2026-11-20.csv`. |
| `check_splits.py` | For issuers whose SEC market cap disagrees with the index weights (`cap_flags` in the output), looks up Yahoo splits after the cover-page share date and writes `data/splits_2026-11-20.json` (Sandisk's 8-for-1 on Nov 20, 2026). |
| `micron_history.py` | Micron's trailing P/E at each fiscal year end since 2009 (10-K diluted EPS, Yahoo close on the fiscal year-end date) and the next year's EPS change. Writes `output/micron_history.json`. |

```bash
pip install numpy yfinance
python3 fetch_data.py                                   # optional: today's files
SEC_USER_AGENT="Name contact@example.com" python3 fetch_fundamentals.py
SEC_USER_AGENT="Name contact@example.com" python3 fetch_cfo.py
python3 analyze.py && python3 check_splits.py && python3 analyze.py
SEC_USER_AGENT="Name contact@example.com" python3 micron_history.py
```

## Data files

| File | Source |
|---|---|
| `data/avantis_<TICKER>_2026-11-20.csv` | Avantis fund pages, holdings as of Nov 20, 2026 |
| `data/avantis_page_characteristics_2026-11-20.json` | Fund-page characteristics (holdings, P/E, P/B), as of Oct 31, 2026 |
| `data/ishares_<TICKER>_2026-11-20.csv` | iShares holdings files, as of Nov 20, 2026 |
| `data/factsheets_2026-09-30.csv` | Book/market, profits/book, weighted cap and holdings for each fund and its benchmark, from the Sep 30, 2026 Avantis fact sheets (URLs in the file) |
| `data/fundamentals_2026-11-20.csv` | SEC XBRL extracts (public domain); prices from the holdings files |
| `data/cfo_2026-11-20.csv` | SEC XBRL operating cash flow, AVLV and IWD holdings |
| `data/splits_2026-11-20.json` | Split factors applied to cover-page share counts |

`output/holdings_summary.json` is copied byte for byte to
`web/src/data/avantis-value-holdings.json` in the Summitward site, and
`output/micron_history.json` to `web/src/data/micron-pe-history.json`.

## Definitions and limits

- Weights are shares of each fund's stocks by market value (cash, rights and
  warrants excluded). Issuers are keyed by SEC CIK, so Alphabet's two share
  classes count once.
- A trailing net income counts only if its period ends after Mar 31, 2026.
  Market cap is the holdings-file price times the latest cover-page share
  count (else the latest quarter's weighted diluted shares). P/E bands use
  trailing net income over that market cap. The guide quotes the weighted
  median P/E over profitable companies, which matched Avantis's published fund
  P/Es (AVLV 16.1 against 16.55, AVUV 11.8 against 12.06); the weighted
  harmonic mean is also in the output but is pulled down by one-off GAAP gains
  such as Lyft's 2025 tax benefit.
- "All-growth by Russell" uses each stock's weights in IWB, IWD and IWF (or
  IWM, IWN and IWO) to infer how much of it FTSE Russell assigns to value; a
  stock with no value weight counts as all growth. It is an inference from the
  ETF files, not the index provider's published probabilities.
  `russell_growth_share` in the output weights every stock by its growth
  fraction, which gives the value index itself a non-zero score; the guide
  does not use it.
- The loss share, P/E bands, harmonic P/E and the named-stock list were fixed
  before computing. The weighted median P/E, the not-in-value-index and
  all-growth shares, and the unadjusted fund averages were added after a first
  look at the results; the guide says so.
- Splits are looked up only for flagged caps (ratio below 0.6 or above 25), so
  a 3-for-2 split after a cover date would be missed. Multi-class companies
  with no usable share count (Berkshire, Visa) count as uncovered. Neither
  moves a quoted figure by more than about a point.
- AVDV and the international sleeves of AVGV have no per-stock fundamentals
  here: the SEC does not hold filings for most of their companies.
- Avantis does not publish security-level scores, so nothing here explains why
  the fund holds a given stock. The numbers describe what it holds.
