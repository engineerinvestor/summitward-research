# spaxx-vs-fdrxx

Supports https://summitward.com/learn/spaxx-vs-fdrxx and
https://summitward.com/compare/spaxx-vs-fdrxx.

Fidelity Government Money Market Fund (SPAXX class) and Fidelity Government
Cash Reserves (FDRXX) are run by the same managers under the same investment
policy. This folder tests whether their yield gap comes from the portfolio or
from the fee, using the funds' own monthly reports to the SEC.

`fetch_data.py` downloads every Form N-MFP2 and N-MFP3 report from October
2016 (the first N-MFP2 month) to October 2026 for SPAXX, FDRXX and the
Treasury-only fund FDLXX, 121 months each, and writes:

- `data/nmfp_monthly.csv`: per fund and month, the series-level 7-day gross
  yield, the share class's 7-day net yield, net assets, WAM and WAL. N-MFP2
  reports one month-end value; N-MFP3 (from June 2024) reports daily values,
  and the file keeps the last reported day plus the month's average.
- `data/nmfp_composition.csv`: per fund and month, the share of net assets in
  each SEC investment category (Treasury debt, agency debt, Treasury repo,
  agency repo, other) and agency debt by issuer (FHLB, Farm Credit, Fannie
  Mae, Freddie Mac, TVA, other).

`analyze.py` reads those files and prints the figures the guide quotes:

```
1. FDRXX minus SPAXX, month-end 7-day yields, 2016-10 to 2026-10
   months: 120
   gross spread within 1bp: 114/120; within 2bp: 117/120
   months with |gross spread| > 1bp: 2022-07 -2.0bp, 2022-08 -3.0bp,
     2022-09 -2.0bp, 2022-10 -4.0bp, 2022-11 -4.0bp, 2022-12 -2.0bp
   last 12 months (2025-11..2026-10): mean net spread +7.0bp
   FDRXX net ahead: 89 months, tied: 27, behind: 4
   identity check (net = gross + expense gap), max residual: 0.000000

   Implied expense ratio (gross minus net 7-day yield), calendar-year mean
   year   SPAXX  FDRXX   gap      mean SPAXX gross
   2018   0.43   0.38   +4.3bp   1.93%
   2019   0.42   0.38   +4.7bp   2.23%
   2020   0.25   0.24   +1.0bp   0.47%   (fee waivers from April)
   2021   0.07   0.07   -0.1bp   0.08%   (fee waivers)
   2022   0.36   0.32   +4.3bp   1.76%   (waivers through April)
   2023   0.42   0.41   +1.1bp   5.13%
   2024   0.42   0.39   +2.8bp   5.19%
   2025   0.42   0.37   +5.4bp   4.29%
   2026   0.42   0.35   +6.6bp   3.77%   (Jan-Oct)

   Correlation of net spread with gross yield, months with gross >= 1% and
   no waiver floor (n=85): -0.37

3. Calendar-year total returns from the prospectuses: FDRXX ahead of SPAXX
   in 9 of 10 years 2016-2025 (5, 5, 5, 6, 1, 0, 3, 1, 3, 6 bp), tied 2021.

4. Composition, Oct 31, 2026 (% of net assets)
   SPAXX: Treasury 44.63, agency 27.40 (FHLB + Farm Credit 26.98), repo 28.60
   FDRXX: Treasury 40.53, agency 27.69 (FHLB + Farm Credit 27.24), repo 32.65
   SPAXX repo share Jan 2024-Oct 2026: 28.6% to 57.5%

5. After-tax income on $100,000, 24% federal, Nov 13, 2026 7-day yields
   (SPAXX 3.55%, FDRXX 3.61%, FDLXX 3.62%) and 2025 tax status
   no state income tax            SPAXX $2,698  FDRXX $2,744  FDLXX $2,751
   5% state, pro rata exemption   SPAXX $2,611  FDRXX $2,657  FDLXX $2,749
   California 9.3%, 50% test      SPAXX $2,368  FDRXX $2,408  FDLXX $2,747
   HSA in California (9.3%)       FDLXX ahead of FDRXX by $341
   FDRXX's extra 1.27 points of 2025 exempt share: $2.29 a year at 5% state
```

The full printout has more rows (2024 and 2025 actual returns under each tax
case, HSA cases, gross-yield buckets).

Caveats:

- **Gross yield is series level, net yield is class level.** SPAXX is one of
  seven classes of its fund; the gross figure covers the whole portfolio. For
  FDRXX (one class) the two coincide.
- **SPAXX's September 2017 report looks wrong.** It shows a 0.98% net yield on
  a 1.09% gross yield, which would imply 0.11% of expenses in a year when every
  other month implies about 0.42%, and SPAXX's 2017 calendar return trailed
  FDRXX's. It stays in the CSV and is excluded from the statistics and the
  chart (`ANOMALIES` in `analyze.py`).
- **N-MFP3 dates.** In some October 2026 filings the yield rows run one day
  behind the NAV and flow rows. The script takes the last reported yield of
  each month rather than matching dates.
- **7-day yields round to 0.01%,** so single-month gaps carry up to 1 bp of
  rounding noise; the calendar-year means are steadier.
- **Repurchase-agreement shares** use the SEC categories; a forward-settling
  repo filed as "Other Instrument" is counted under other.
- **After-tax figures** apply fixed marginal rates to a full year at one
  day's yields, treat all income as federally taxable ordinary income, use
  2025 tax status (the latest published) as a stand-in for 2026, and ignore
  the federal deduction for state tax. They are illustrations, not forecasts.
- Fee components quoted in the guide (FDRXX's income-related fee of 0.06%,
  0.11% and 0.09% of assets in fiscal 2022, fiscal 2023 and the six months to
  May 2026) come from the funds' N-CSR reports, not from this script.

Data:

- SEC EDGAR Form N-MFP2/N-MFP3 filings, downloaded 2026-11-13. US government
  records, public domain. Series IDs: SPAXX S000007051 (class C000019230),
  FDRXX S000007149 (class C000019553), FDLXX S000007053 (class C000019232).
- Calendar-year returns: prospectus bar charts (SPAXX/FDLXX prospectus dated
  June 29, 2026; FDRXX prospectus dated January 29, 2026).
- Government-securities income shares: Fidelity's 2024 and 2025 supplemental
  tax letters.

```bash
python3 analyze.py         # standard library only, reads data/
SEC_USER_AGENT="Name you@example.com" python3 fetch_data.py   # re-download (stdlib)
```

The SEC rejects requests without a contact address in the User-Agent. Raw
XML is cached in `.cache/` (about 260 MB, not committed).
