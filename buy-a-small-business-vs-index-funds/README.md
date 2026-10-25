# buy-a-small-business-vs-index-funds

Supports https://summitward.com/learn/buy-a-small-business-vs-index-funds.

`sba_7a_outcomes.py` reads SBA's loan-level 7(a) FOIA file and reports how
often loans to laundromats, HVAC and plumbing contractors, full-service
restaurants, car washes and self-storage lessors were charged off, plus a
comparison of acquisition loans with startup and existing-business loans.

Data: `FOIA_7a_FY2010_FY2019_asof_260630.csv` from
https://data.sba.gov/dataset/7a-504-foia (U.S. government work, status as of
2026-06-30). About 255 MB; the script downloads it into `.cache/`, which is
not committed.

```bash
python3 sba_7a_outcomes.py
```

Output quoted in the guide (run 2026-10-25):

```
Table 1. FY2010-2016 approvals, disbursed loans, status as of 2026-06-30
                                                loans  charged off    active    $ lost
  All 7(a) loans                              323,018         7.0%      4.7%      3.1%
  Laundromats (812310)                          1,193         4.4%      5.2%      1.6%
  HVAC and plumbing contractors (238220)        4,179         6.2%      3.7%      4.5%
  Full-service restaurants (722110/722511)     16,413         9.0%      5.3%      4.6%
  Car washes (811192)                           1,394         6.1%      9.8%      2.1%
  Self-storage lessors (531130)                   574         0.7%      9.8%      0.1%

  Same, terms of 10 years or less (excludes most real estate loans)
                                                loans  charged off    active    $ lost
  All 7(a) loans                              251,934         8.2%      0.9%      5.5%
  Laundromats (812310)                            819         5.5%      0.5%      3.1%
  HVAC and plumbing contractors (238220)        3,527         6.8%      0.7%      6.2%
  Full-service restaurants (722110/722511)     12,290        10.6%      1.5%      7.5%
  Car washes (811192)                             445        10.8%      0.4%      4.4%
  Self-storage lessors (531130)                    64         3.1%      3.1%      1.2%

Table 2. FY2018-2019 approvals by business age, all industries
                                                loans  charged off    active    $ lost
  All 7(a) loans                               99,866         7.3%     26.1%      2.4%
  Change of ownership                           9,572         4.6%     36.0%      2.2%
  Startup or under 1 year                      18,598         8.1%     28.7%      3.2%
  Existing business                            54,805         7.3%     25.5%      2.3%
  Unanswered                                   16,891         8.2%     19.3%      2.0%

  charged off = CHGOFF / disbursed loans; active = EXEMPT / disbursed loans;
  $ lost = gross charge-off amount / gross approval amount.
```

Reading the numbers:

- Cancelled loans (never disbursed) are excluded.
- A charge-off is the lender's loss after collateral and guarantees. Owners
  can lose their equity on a loan that was repaid in full, so these rates
  understate how often owners lose money.
- SBA withholds the status of disbursed loans that are still active (FOIA
  Exemption 4, `EXEMPT`). They are counted as not charged off, so every
  charge-off rate is a lower bound for loans still paying down.
- SBA records "Change of Ownership" as a business-age value only for FY2018
  and FY2019 approvals in this file, so Table 2 is the only acquisition-loan
  comparison. Those loans are six to seven years old, 36% are still active,
  and SBA paid principal and interest on many 7(a) loans in 2020-2021 under
  section 1112 of the CARES Act, which delayed defaults.
- NAICS codes are self-reported at approval. 238220 covers plumbing as well
  as HVAC; 531130 is the self-storage lessor code.
