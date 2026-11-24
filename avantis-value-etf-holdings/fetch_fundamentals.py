"""Fetch company fundamentals for every U.S. stock in the holdings files.

Source: SEC XBRL "companyconcept" API (public domain), one request per company
and concept, cached under .cache/sec/ (not committed). For each company:

  net income   NetIncomeLoss, else NetIncomeLossAvailableToCommonStockholdersBasic,
               else ProfitLoss; trailing twelve months = latest 10-K year
               + latest year-to-date 10-Q figure - the same period a year earlier
  book equity  StockholdersEquity at the latest balance sheet date, else the
               figure including noncontrolling interests
  shares       dei:EntityCommonStockSharesOutstanding from the latest cover page,
               else the latest quarter's weighted average diluted shares

Only 10-K, 10-Q, 20-F and 40-F facts filed on or before DATE count, so the
figures are what was public at the Nov 20, 2026 close even when the data is
pulled later.

Prices come from the holdings files themselves (iShares lists a price per row;
Avantis gives market value and share quantity), so every figure is as of the
same close. The SEC asks automated clients to identify themselves: set
SEC_USER_AGENT (e.g. "YourName contact@example.com") before running.

Writes data/fundamentals_<date>.csv.

Usage:
    SEC_USER_AGENT="..." python3 fetch_fundamentals.py
"""

import csv
import json
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
CACHE = HERE / ".cache" / "sec"
DATE = "2026-11-20"
STALE_BEFORE = date(2026, 3, 31)  # latest net income period must end after this
COVER_STALE_BEFORE = "2025-06-30"  # older cover-page share counts are not used

US_FUNDS = ["AVLV", "AVUV", "AVMV"]
ISHARES = ["IWB", "IWD", "IWF", "IWM", "IWN", "IWO"]
NI_CONCEPTS = [
    ("us-gaap", "NetIncomeLoss"),
    ("us-gaap", "NetIncomeLossAvailableToCommonStockholdersBasic"),
    ("us-gaap", "ProfitLoss"),
    ("ifrs-full", "ProfitLossAttributableToOwnersOfParent"),
    ("ifrs-full", "ProfitLoss"),
]
EQ_CONCEPTS = [
    ("us-gaap", "StockholdersEquity"),
    ("us-gaap", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"),
    ("ifrs-full", "EquityAttributableToOwnersOfParent"),
    ("ifrs-full", "Equity"),
]
SH_CONCEPTS = [
    ("dei", "EntityCommonStockSharesOutstanding"),
    ("us-gaap", "WeightedAverageNumberOfDilutedSharesOutstanding"),
]

UA = os.environ.get("SEC_USER_AGENT", "")
_last = [0.0]
_lock = threading.Lock()  # SEC fair access: at most 10 requests a second


def key(t: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(t).upper())


def num(x: str) -> float:
    s = str(x).replace(",", "").replace("%", "").strip()
    return 0.0 if s in ("", "-", "null", "None") else float(s)


def sec_get(url: str, cache: Path) -> dict | None:
    if cache.exists():
        text = cache.read_text()
        return json.loads(text) if text else None
    with _lock:
        wait = 0.125 - (time.time() - _last[0])
        if wait > 0:
            time.sleep(wait)
        _last[0] = time.time()
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for attempt in range(4):
        try:
            body = urllib.request.urlopen(req, timeout=60).read()
            cache.write_bytes(body)
            return json.loads(body)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                cache.write_text("")
                return None
            time.sleep(2 * (attempt + 1))
        except (urllib.error.URLError, TimeoutError):
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"failed: {url}")


# A company that re-registers under a new CIK files its first 10-Qs with no
# 10-K behind them. Merge the predecessor's facts so a trailing year can be
# built. ExxonMobil Holdings Corp (Texas, from Jul 1, 2026) succeeded Exxon
# Mobil Corp (New Jersey).
PREDECESSOR = {2115436: 34088}


def concept(cik: int, tax: str, name: str) -> list[dict]:
    facts = []
    for c in (cik, PREDECESSOR.get(cik)):
        if c is None:
            continue
        url = f"https://data.sec.gov/api/xbrl/companyconcept/CIK{c:010d}/{tax}/{name}.json"
        d = sec_get(url, CACHE / f"{c}_{name}.json")
        if not d:
            continue
        for unit, rows in d["units"].items():
            if unit not in ("USD", "shares", "USD/shares"):
                continue
            facts.extend(rows)
    return facts


def d_(s: str) -> date:
    return date.fromisoformat(s)


PERIODIC = ("10-K", "10-K/A", "10-KT", "10-Q", "10-Q/A", "20-F", "20-F/A", "40-F")


def periodic(rows: list[dict]) -> list[dict]:
    """Facts from periodic reports filed on or before the snapshot date.
    Proxy statements (pay-versus-performance tables) and 8-Ks re-file the same
    numbers later and would otherwise win the "most recently filed" tie-break
    with the wrong form. Reports filed after DATE were not public at the close
    the holdings describe, so they are left out (the data is pulled later)."""
    return [r for r in rows if r.get("form") in PERIODIC and r.get("filed", "") <= DATE]


def latest_filed(rows: list[dict]) -> dict[tuple, dict]:
    """One fact per (start, end), keeping the most recently filed value."""
    out: dict[tuple, dict] = {}
    for r in periodic(rows):
        k = (r.get("start"), r["end"])
        if k not in out or r["filed"] > out[k]["filed"]:
            out[k] = r
    return out


def ttm(rows: list[dict]) -> tuple[float, str, str] | None:
    """(TTM value, period end, method) from duration facts."""
    facts = [r for r in latest_filed(rows).values() if r.get("start")]
    annual = [r for r in facts if 350 <= (d_(r["end"]) - d_(r["start"])).days <= 380]
    if not annual:
        return None
    a = max(annual, key=lambda r: r["end"])
    ae = d_(a["end"])
    ytd = [
        r
        for r in facts
        if abs((d_(r["start"]) - ae).days - 1) <= 7
        and d_(r["end"]) > ae
        and (d_(r["end"]) - d_(r["start"])).days < 340
    ]
    if not ytd:
        return float(a["val"]), a["end"], "annual"
    y = max(ytd, key=lambda r: r["end"])
    dur = (d_(y["end"]) - d_(y["start"])).days
    target_end = d_(y["end"]) - timedelta(days=364)
    prior = [
        r
        for r in facts
        if abs((d_(r["end"]) - target_end).days) <= 10
        and abs((d_(r["end"]) - d_(r["start"])).days - dur) <= 10
    ]
    if not prior:
        return float(a["val"]), a["end"], "annual (no prior-year YTD)"
    p = max(prior, key=lambda r: r["filed"])
    return float(a["val"]) + float(y["val"]) - float(p["val"]), y["end"], "ttm"


def latest_instant(rows: list[dict]) -> tuple[float, str] | None:
    facts = [r for r in periodic(rows) if not r.get("start")]
    if not facts:
        return None
    end = max(r["end"] for r in facts)
    best = max((r for r in facts if r["end"] == end), key=lambda r: r["filed"])
    return float(best["val"]), end


def cover_shares(rows: list[dict]) -> tuple[float, str] | None:
    """Sum of cover-page share counts in the latest filing (one per class when a
    company reports classes without dimensions)."""
    rows = periodic(rows)
    if not rows:
        return None
    filed = max(r["filed"] for r in rows)
    latest = [r for r in rows if r["filed"] == filed]
    end = max(r["end"] for r in latest)
    if end < COVER_STALE_BEFORE:
        # Multi-class companies (Visa, Berkshire) report cover shares by class
        # with dimensions, which this API omits; the last undimensioned value
        # can be a decade old. Use weighted diluted shares instead.
        return None
    vals = {r["val"] for r in latest if r["end"] == end}
    return float(sum(vals)), end


def wavg_diluted(rows: list[dict]) -> tuple[float, str] | None:
    facts = [
        r
        for r in latest_filed(rows).values()
        if r.get("start") and (d_(r["end"]) - d_(r["start"])).days < 100
    ]
    if not facts:
        return None
    r = max(facts, key=lambda r: r["end"])
    return float(r["val"]), r["end"]


def universe() -> dict[str, dict]:
    """Normalized ticker -> {ticker, name, price} over every U.S. holding."""
    out: dict[str, dict] = {}
    for t in ISHARES:
        lines = (DATA / f"ishares_{t}_{DATE}.csv").read_text().splitlines()
        head = next(i for i, ln in enumerate(lines) if ln.startswith("Ticker,"))
        for r in csv.DictReader(lines[head:]):
            if r.get("Asset Class") != "Equity" or not r.get("Price"):
                continue
            out.setdefault(
                key(r["Ticker"]),
                {"ticker": r["Ticker"], "name": r["Name"], "price": num(r["Price"])},
            )
    for t in US_FUNDS:
        for r in csv.DictReader((DATA / f"avantis_{t}_{DATE}.csv").open()):
            if r["securityType"] != "COMMON STOCK":
                continue
            q = num(r["shareQuantity"])
            if q <= 0:
                continue
            out.setdefault(
                key(r["ticker"]),
                {
                    "ticker": r["ticker"],
                    "name": r["name"],
                    "price": num(r["baseMarketValue"]) / q,
                },
            )
    return out


def main() -> None:
    if "@" not in UA:
        sys.exit("set SEC_USER_AGENT to 'Name contact@example.com' first")
    CACHE.mkdir(parents=True, exist_ok=True)
    tick = sec_get(
        "https://www.sec.gov/files/company_tickers.json", CACHE / "company_tickers.json"
    )
    # Plain tickers first: SEC's list also carries preferred and unit listings
    # ("T-PC" for an AT&T preferred), which collapse onto other companies'
    # tickers ("TPC", Tutor Perini) once punctuation is stripped.
    cik_of: dict[str, int] = {}
    entries = sorted(tick.values(), key=lambda v: not v["ticker"].isalnum())
    for v in entries:
        cik_of.setdefault(key(v["ticker"]), int(v["cik_str"]))
    uni = universe()
    print(f"{len(uni)} U.S. tickers; {sum(k in cik_of for k in uni)} map to a CIK")

    def one(item: tuple[str, dict]) -> dict:
        k, u = item
        cik = cik_of.get(k)
        rec = {"key": k, **u, "cik": cik or ""}
        if cik:
            # Companies switch tags over time (Cummins last used NetIncomeLoss in
            # 2011), so keep trying until a current figure turns up and keep the
            # freshest one found.
            best = None
            for tax, name in NI_CONCEPTS:
                got = ttm(concept(cik, tax, name))
                if got and (best is None or got[1] > best[0][1]):
                    best = (got, name)
                if best and best[0][1] > STALE_BEFORE.isoformat():
                    break
            if best:
                got, name = best
                rec.update(ni_ttm=got[0], ni_end=got[1], ni_method=got[2], ni_concept=name)
            best_eq = None
            for tax, name in EQ_CONCEPTS:
                got = latest_instant(concept(cik, tax, name))
                if got and (best_eq is None or got[1] > best_eq[1]):
                    best_eq = got
                if best_eq and best_eq[1] > STALE_BEFORE.isoformat():
                    break
            if best_eq:
                rec.update(book=best_eq[0], book_end=best_eq[1])
            got = cover_shares(concept(cik, *SH_CONCEPTS[0]))
            src = "cover"
            if not got:
                got = wavg_diluted(concept(cik, *SH_CONCEPTS[1]))
                src = "wavg_diluted"
            if got:
                rec.update(shares=got[0], shares_end=got[1], shares_src=src)
        return rec

    with ThreadPoolExecutor(max_workers=20) as pool:
        rows = list(pool.map(one, sorted(uni.items())))

    fields = [
        "key", "ticker", "name", "price", "cik", "ni_ttm", "ni_end", "ni_method",
        "ni_concept", "book", "book_end", "shares", "shares_end", "shares_src",
    ]  # fmt: skip
    out = DATA / f"fundamentals_{DATE}.csv"
    with out.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    have = sum(1 for r in rows if "ni_ttm" in r)
    print(f"wrote {out.name}: {len(rows)} rows, {have} with net income")


if __name__ == "__main__":
    main()
