"""SBA 7(a) loan outcomes for the industries in the "buy a small business" guide.

Supports https://summitward.com/learn/buy-a-small-business-vs-index-funds.

Reads SBA's loan-level 7(a) FOIA file (FY2010 to FY2019 approvals, as of
2026-06-30) and prints two tables:

1. FY2010-2016 approvals by industry: how many loans were charged off, how
   many are still active, and the share of approved dollars charged off.
2. FY2018-2019 approvals by business age, all industries. These are the only
   years in which SBA records "Change of Ownership" as a business-age value,
   so this is the only place acquisition loans can be separated from startups
   and existing businesses.

A charge-off is a lender loss. It undercounts owner losses: an owner can lose
the equity in a business and still repay the loan. SBA withholds the status of
disbursed loans that are still active (FOIA Exemption 4, shown as EXEMPT), so
the charge-off rates below count those loans as not charged off and are lower
bounds for any cohort that is still paying down.

Standard library only. The CSV (about 255 MB) downloads into .cache/ on first
run and is not committed.

    python3 sba_7a_outcomes.py
"""

import csv
import sys
import urllib.request
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
CACHE = HERE / ".cache"
FILE = "FOIA_7a_FY2010_FY2019_asof_260630.csv"
URL = "https://data.sba.gov/sites/default/files/uploaded_resources/" + FILE

# 2012 NAICS replaced 722110 (full-service restaurants) with 722511.
INDUSTRIES = {
    "Laundromats (812310)": {"812310"},
    "HVAC and plumbing contractors (238220)": {"238220"},
    "Full-service restaurants (722110/722511)": {"722110", "722511"},
    "Car washes (811192)": {"811192"},
    "Self-storage lessors (531130)": {"531130"},
}

AGE_GROUPS = {
    "Change of Ownership": "Change of ownership",
    "Startup, Loan Funds will Open Business": "Startup or under 1 year",
    "New, Less than 1 Year old": "Startup or under 1 year",
    "Unanswered": "Unanswered",
    "": "Unanswered",
}


def load_rows():
    path = CACHE / FILE
    if not path.exists():
        CACHE.mkdir(exist_ok=True)
        print(f"Downloading {FILE} into .cache/ ...", file=sys.stderr)
        req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req) as r, open(path, "wb") as f:
            while chunk := r.read(1 << 20):
                f.write(chunk)
    with open(path, newline="", encoding="latin-1") as f:
        yield from csv.DictReader(f)


def new_cell():
    return {"n": 0, "chgoff": 0, "exempt": 0, "approved": 0.0, "chgoff_amt": 0.0}


def add(cell, row):
    cell["n"] += 1
    cell["approved"] += float(row["GrossApproval"] or 0)
    if row["LoanStatus"] == "CHGOFF":
        cell["chgoff"] += 1
        cell["chgoff_amt"] += float(row["GrossChargeOffAmount"] or 0)
    elif row["LoanStatus"] == "EXEMPT":
        cell["exempt"] += 1


def fmt(label, c):
    n = c["n"]
    return (
        f"  {label:<42}{n:>9,}{100 * c['chgoff'] / n:>12.1f}%"
        f"{100 * c['exempt'] / n:>9.1f}%{100 * c['chgoff_amt'] / c['approved']:>9.1f}%"
    )


HEADER = f"  {'':<42}{'loans':>9}{'charged off':>13}{'active':>10}{'$ lost':>10}"


def main():
    by_industry = defaultdict(new_cell)
    by_industry_short = defaultdict(new_cell)
    by_age = defaultdict(new_cell)
    naics_to_label = {
        code: label for label, codes in INDUSTRIES.items() for code in codes
    }

    for row in load_rows():
        if row["LoanStatus"] in ("CANCLD", "COMMIT"):
            continue  # never disbursed
        fy = int(row["ApprovalFY"])
        if 2010 <= fy <= 2016:
            short = float(row["TermInMonths"] or 0) <= 120
            label = naics_to_label.get(row["NaicsCode"])
            for key in ("All 7(a) loans", label):
                if key:
                    add(by_industry[key], row)
                    if short:
                        add(by_industry_short[key], row)
        if fy in (2018, 2019):
            age = AGE_GROUPS.get(row["BusinessAge"], "Existing business")
            add(by_age[age], row)
            add(by_age["All 7(a) loans"], row)

    order = ["All 7(a) loans", *INDUSTRIES]
    print("Table 1. FY2010-2016 approvals, disbursed loans, status as of 2026-06-30")
    print(HEADER)
    for key in order:
        print(fmt(key, by_industry[key]))
    print("\n  Same, terms of 10 years or less (excludes most real estate loans)")
    print(HEADER)
    for key in order:
        print(fmt(key, by_industry_short[key]))

    print("\nTable 2. FY2018-2019 approvals by business age, all industries")
    print(HEADER)
    for key in [
        "All 7(a) loans",
        "Change of ownership",
        "Startup or under 1 year",
        "Existing business",
        "Unanswered",
    ]:
        print(fmt(key, by_age[key]))
    print(
        "\n  charged off = CHGOFF / disbursed loans; active = EXEMPT / disbursed loans;"
        "\n  $ lost = gross charge-off amount / gross approval amount."
    )


if __name__ == "__main__":
    main()
