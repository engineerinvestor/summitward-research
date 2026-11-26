# sports-team-etfs

Supports https://summitward.com/learn/sports-team-etfs

`analyze.py` produces the two original figures in the guide:

- **How many sports team ETFs have been proposed.** EDGAR full-text search
  for 485APOS filings from June 1 to November 25, 2026 that mention "FSPI" or
  "FutureSports" (the CME FutureSports Performance Indexes the funds would
  reference). For each filing it counts the new fund series on the EDGAR
  filing index, then classifies them by issuer, league and leverage. On
  November 25, 2026: 15 filings, 462 funds (LeagueShares 184, REX/Alpha
  Sports 124, Volatility Shares 92, Roundhill 62; NHL 192, MLB 180, NBA 90;
  154 leveraged). It also confirms that no 485BPOS, 497 or 497K mentions
  FSPI, i.e. no sports team fund had an effective prospectus.
- **How much of an NBA team index is zero-sum across the league.** Uses only
  the scoring rules stated in the LeagueShares NBA 485APOS of November 24,
  2026. Regular-season wins and losses (+10/-10) cancel. Playoff
  qualification adds 16 x 80 - 14 x 80 = +160 to the league total, each
  playoff game adds 20 - 5 = +15, and the champion adds 250. With 60 to 105
  playoff games, the 30 indexes together gain 1,310 to 1,985 points on a
  225,000 base (+0.58% to +0.88%) from these constituents.

Caveats:

- Part 2 leaves out the game statistics. The filing says "most are mirrored"
  between opponents and gives only some point values, so the true league
  total can drift more than computed here. Free throws missed has no listed
  counterpart and can only push the total down; NBA teams miss thousands of
  free throws a season, so depending on its undisclosed weight the league
  total can fall instead of rise. The figure above is the result-and-playoff
  component only. The in-season tournament
  final bonus (at most one playoff-win value) is also left out.
- The cancellation is exact only for the same number of contracts on every
  team. Equal dollar amounts in each team's 1x ETF hold more contracts of
  low-priced teams and keep some team-specific risk.
- No FutureSports index values are read or stored. FutureSports' FSPI Data
  Terms of Use (https://futuresports.com/docs/fspi-data-terms-of-use.pdf) bar
  compiling, analyzing or republishing index values without written consent,
  so the guide quotes historical values only from SEC filings.
- EDGAR full-text search indexes document text; a filing that never names
  FSPI or FutureSports would be missed. The four issuers' own filing lists
  (CIKs 1122649, 1884021, 1976517, 2043954) were checked by hand for the same
  window.

Data: SEC EDGAR (public). Output: `output/sports-team-etfs.json`, copied
byte-for-byte to the site's `web/src/data/sports-team-etfs.json`. Rerunning
after November 25, 2026 changes the window end only if `END` is edited.
