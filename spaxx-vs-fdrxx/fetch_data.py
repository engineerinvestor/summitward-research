"""Download the SEC Form N-MFP filings that analyze.py reads.

For SPAXX (Fidelity Government Money Market Fund), FDRXX (Fidelity Government
Cash Reserves) and FDLXX (Fidelity Treasury Only Money Market Fund), this
pulls every monthly N-MFP2 and N-MFP3 report from October 2016 (the first
N-MFP2 month) onward, applies amendments (a later filing for the same report
month replaces the earlier one), and writes:

- data/nmfp_monthly.csv: one row per fund and month with the series-level
  7-day gross yield, the share class's 7-day net yield, net assets, WAM, WAL.
  N-MFP2 reports one month-end value; N-MFP3 reports daily values, so the
  file keeps the last reported day and the month's average of daily values.
- data/nmfp_composition.csv: one row per fund and month with the share of
  net assets in each SEC investment category and in agency debt by issuer.

Raw XML is cached in .cache/ (not committed). Standard library only:

    SEC_USER_AGENT="Your Name you@example.com" python3 fetch_data.py
"""

import csv
import os
import re
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
CACHE = HERE / ".cache"

# SEC rejects requests whose User-Agent lacks a contact address.
UA = {
    "User-Agent": os.environ.get(
        "SEC_USER_AGENT", "summitward-research research@example.com"
    )
}

# ticker: (trust CIK, series ID, class ID), from sec.gov/files/company_tickers_mf.json
FUNDS = {
    "SPAXX": ("917286", "S000007051", "C000019230"),
    "FDRXX": ("278001", "S000007149", "C000019553"),
    "FDLXX": ("917286", "S000007053", "C000019232"),
}
FIRST_MONTH = "2016-10"
FORMS = {"N-MFP2", "N-MFP2/A", "NT N-MFP2", "N-MFP3", "N-MFP3/A"}

AGENCY_ISSUERS = [
    ("FHLB", "home loan bank"),
    ("Farm Credit", "farm credit"),
    ("Fannie Mae", "national mortgage"),
    ("Freddie Mac", "home loan mortgage"),
    ("TVA", "tennessee valley"),
]


def get(url: str) -> bytes:
    for attempt in range(4):
        try:
            time.sleep(0.15)  # stay under SEC's 10 requests per second
            req = urllib.request.Request(url, headers=UA)
            return urllib.request.urlopen(req, timeout=60).read()
        except Exception as exc:  # noqa: BLE001 - retry any network error
            if attempt == 3:
                raise
            print(f"  retry {url}: {exc}", file=sys.stderr)
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(url)


def tag(block: str, name: str) -> str:
    m = re.search(rf"<{name}>(.*?)</{name}>", block, re.S)
    return m.group(1).strip() if m else ""


def filings(series: str) -> list[dict]:
    """Every N-MFP2/3 filing (with amendments and NT filings) for a series."""
    out = []
    for type_ in ("N-MFP", "NT+N-MFP"):
        start = 0
        while True:
            url = (
                "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany"
                f"&CIK={series}&type={type_}&dateb=&owner=include&start={start}"
                "&count=100&output=atom"
            )
            atom = get(url).decode()
            entries = re.findall(r"<entry>(.*?)</entry>", atom, re.S)
            for e in entries:
                form = tag(e, "filing-type")
                if form in FORMS:
                    out.append(
                        {
                            "form": form,
                            "filed": tag(e, "filing-date"),
                            "href": tag(e, "filing-href"),
                        }
                    )
            if len(entries) < 100:
                break
            start += 100
    seen, unique = set(), []
    for f in out:
        if f["href"] not in seen:
            seen.add(f["href"])
            unique.append(f)
    return unique


def primary_doc(cik: str, href: str) -> str:
    acc = re.search(r"/(\d{18})/", href).group(1)
    path = CACHE / f"{cik}_{acc}.xml"
    if not path.exists():
        CACHE.mkdir(exist_ok=True)
        url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/primary_doc.xml"
        path.write_bytes(get(url))
    return path.read_text()


def yields(block: str, name: str) -> list[tuple[str, float]]:
    """(date, value) pairs. N-MFP2 carries one bare value with no date."""
    pairs = re.findall(
        rf"<{name}>\s*<{name}Value>(.*?)</{name}Value>\s*<{name}Date>(.*?)</{name}Date>",
        block,
        re.S,
    )
    if pairs:
        return sorted((d.strip(), float(v)) for v, d in pairs)
    bare = tag(block, name)
    return [("", float(bare))] if bare else []


def parse(xml: str, series: str, class_id: str) -> tuple[dict, dict]:
    report = tag(xml, "reportDate")
    series_info = tag(xml, "seriesLevelInfo")
    gross = yields(series_info, "sevenDayGrossYield")
    cls = next(
        b
        for b in re.findall(r"<classLevelInfo>(.*?)</classLevelInfo>", xml, re.S)
        if tag(b, "classesId") == class_id
    )
    net = yields(cls, "sevenDayNetYield")
    row = {
        "report_month": report[:7],
        "report_date": report,
        "form": tag(xml, "submissionType"),
        "gross_last": gross[-1][1] if gross else "",
        "gross_last_date": gross[-1][0] if gross else "",
        "gross_avg": sum(v for _, v in gross) / len(gross) if gross else "",
        "net_last": net[-1][1] if net else "",
        "net_last_date": net[-1][0] if net else "",
        "net_avg": sum(v for _, v in net) / len(net) if net else "",
        "net_assets_series": tag(series_info, "netAssetOfSeries"),
        "net_assets_class": tag(cls, "netAssetsOfClass"),
        "wam_days": tag(series_info, "averagePortfolioMaturity"),
        "wal_days": tag(series_info, "averageLifeMaturity"),
    }
    comp: dict[str, float] = {}
    for sec in re.findall(
        r"<scheduleOfPortfolioSecuritiesInfo>(.*?)</scheduleOfPortfolioSecuritiesInfo>",
        xml,
        re.S,
    ):
        cat = tag(sec, "investmentCategory")
        pct = float(tag(sec, "percentageOfMoneyMarketFundNetAssets") or 0)
        if cat.startswith("U.S. Treasury Debt"):
            key = "treasury_debt"
        elif cat.startswith("U.S. Government Agency Debt"):
            key = "agency_debt"
            issuer = tag(sec, "nameOfIssuer").lower()
            label = next((k for k, s in AGENCY_ISSUERS if s in issuer), "Other agency")
            ikey = "agency_" + re.sub(r"\W+", "_", label.lower())
            comp[ikey] = comp.get(ikey, 0.0) + pct
        elif cat.startswith("U.S. Treasury Repurchase"):
            key = "treasury_repo"
        elif cat.startswith("U.S. Government Agency Repurchase"):
            key = "agency_repo"
        else:
            key = "other"
        comp[key] = comp.get(key, 0.0) + pct
    comp_row = {"report_month": report[:7], **{k: round(v, 6) for k, v in comp.items()}}
    return row, comp_row


def main() -> None:
    DATA.mkdir(exist_ok=True)
    monthly, composition = [], []
    for ticker, (cik, series, class_id) in FUNDS.items():
        found = filings(series)
        by_month: dict[str, tuple[str, dict, dict]] = {}
        for f in found:
            xml = primary_doc(cik, f["href"])
            if tag(xml, "seriesId") != series:
                continue
            row, comp = parse(xml, series, class_id)
            if row["report_month"] < FIRST_MONTH:
                continue
            prev = by_month.get(row["report_month"])
            # A later filing for the same month (amendment) replaces the earlier one.
            if prev is None or f["filed"] > prev[0]:
                by_month[row["report_month"]] = (f["filed"], row, comp)
        months = sorted(by_month)
        print(
            f"{ticker}: {len(found)} filings listed, {len(months)} months {months[0]}..{months[-1]}"
        )
        for m in months:
            filed, row, comp = by_month[m]
            monthly.append({"ticker": ticker, "filed": filed, **row})
            composition.append({"ticker": ticker, **comp})

    with (DATA / "nmfp_monthly.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(monthly[0]))
        w.writeheader()
        w.writerows(monthly)
    keys = ["ticker", "report_month"]
    for r in composition:
        keys += [k for k in r if k not in keys]
    with (DATA / "nmfp_composition.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys, restval=0)
        w.writeheader()
        w.writerows(composition)
    print("wrote data/nmfp_monthly.csv and data/nmfp_composition.csv")


if __name__ == "__main__":
    main()
