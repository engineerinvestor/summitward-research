"""VTSAX vs FZROX vs FSKAX: how different are the portfolios and the returns?

Reads the CSVs that fetch_data.py writes (committed in data/) and prints:

1. Concentration of each fund's equity holdings, by issuer, from SEC N-PORT-P.
2. How much of VTSAX and FSKAX sits in issuers smaller than the smallest one
   FZROX holds, measured by size rank so that no cross-fund matching is needed.
3. The weight of VTSAX and FSKAX issuers that FZROX's filing does not hold
   (matched on CUSIP issuer code, ISIN, then name). The three filings are dated
   one to two months apart, so this mixes real index differences with timing.
4. Month-end total returns from August 31, 2018 (FZROX's first month end) to
   September 30, 2026: annualized returns, calendar years, pairwise tracking.
5. Five-year returns of the three ZERO index funds against the counterparts
   the ZERO-funds guide compares them with.

Standard library only:  python3 analyze.py
"""

import csv
import math
import re
import statistics
from collections import defaultdict
from pathlib import Path

DATA = Path(__file__).resolve().parent / "data"
FUNDS = ["VTSAX", "FZROX", "FSKAX"]
FEES = {"VTSAX": 0.0004, "FZROX": 0.0, "FSKAX": 0.00015}

# Corporate actions between the filing dates that changed an issuer's CUSIP.
# Exxon Mobil (30231G) became a subsidiary of ExxonMobil Holdings Corp (30233Q)
# when it redomiciled to Texas on July 1, 2026 (Form S-8 POS, SEC CIK 2115436).
ALIASES = {"C30233Q": "C30231G"}

SUFFIXES = (
    r"\b(INC|CORP|CORPORATION|CO|COS|LTD|PLC|NV|SA|AG|LLC|LP|HOLDINGS?|GROUP|"
    r"THE|CLASS|CL|COM|COMMON|STOCK|SHS|NEW|REIT|TRUST|INCORPORATED|COMPANY)\b"
)


def norm_name(name: str) -> str:
    n = re.sub(r"[^A-Z0-9 ]", " ", name.upper())
    n = re.sub(SUFFIXES, " ", n)
    return " ".join(n.split())


def load_holdings(ticker: str):
    path = DATA / f"holdings_{ticker}.csv"
    with path.open() as f:
        header = f.readline().strip("# \n")
        rows = [r for r in csv.DictReader(f) if r["asset_cat"] == "EC"]
    issuers = defaultdict(lambda: {"value": 0.0, "keys": set(), "name": ""})
    for r in rows:
        cusip = r["cusip"] if re.fullmatch(r"[0-9A-Z]{9}", r["cusip"]) else ""
        cusip = "" if cusip == "000000000" else cusip
        isin = r["isin"]
        name = norm_name(r["name"])
        # Issuer key: first six CUSIP characters, else the ISIN's issuer part,
        # else the cleaned name. Share classes of one company collapse together.
        if cusip:
            key = "C" + cusip[:6]
        elif isin.startswith("US") and len(isin) == 12:
            key = "C" + isin[2:8]
        elif isin:
            key = "I" + isin[:8]
        else:
            key = "N" + name
        key = ALIASES.get(key, key)
        iss = issuers[key]
        iss["value"] += float(r["value_usd"])
        iss["keys"] |= {k for k in (key, "N" + name, isin and "I" + isin[:8]) if k}
        iss["name"] = iss["name"] or r["name"]
    return header, len(rows), issuers


def concentration(ticker, header, n_pos, issuers):
    vals = sorted((i["value"] for i in issuers.values()), reverse=True)
    tot = sum(vals)
    w = [v / tot for v in vals]
    return {
        "ticker": ticker,
        "header": header,
        "positions": n_pos,
        "issuers": len(vals),
        "top10": sum(w[:10]),
        "n_eff": 1 / sum(x * x for x in w),
        "weights": w,
        "total": tot,
    }


def holdings_section():
    data = {t: load_holdings(t) for t in FUNDS}
    conc = {t: concentration(t, *data[t]) for t in FUNDS}
    print("1. Equity holdings by issuer (SEC N-PORT-P)")
    for t in FUNDS:
        c = conc[t]
        print(f"   {c['header']}")
        print(
            f"   {t}: {c['positions']} equity positions, {c['issuers']} issuers, "
            f"top 10 issuers {100 * c['top10']:.2f}%, "
            f"effective number of issuers {c['n_eff']:.0f}"
        )

    k = conc["FZROX"]["issuers"]
    print(f"\n2. Weight in issuers ranked below FZROX's issuer count ({k})")
    for t in ("VTSAX", "FSKAX"):
        w = conc[t]["weights"]
        print(
            f"   {t}: issuers ranked {k + 1}-{len(w)} ({len(w) - k} names) hold "
            f"{100 * sum(w[k:]):.3f}% of equity value; ranked 3001+ hold "
            f"{100 * sum(w[3000:]):.3f}%"
        )

    print("\n3. Weight in issuers FZROX's filing does not hold")
    fz_keys = set().union(*(i["keys"] for i in data["FZROX"][2].values()))
    for t in ("VTSAX", "FSKAX"):
        issuers = data[t][2]
        tot = sum(i["value"] for i in issuers.values())
        missing = sorted(
            (i for i in issuers.values() if not (i["keys"] & fz_keys)),
            key=lambda i: -i["value"],
        )
        share = sum(i["value"] for i in missing) / tot
        print(f"   {t}: {len(missing)} issuers, {100 * share:.2f}% of equity value")
        for i in missing[:8]:
            print(f"      {i['name'][:40]:40s} {100 * i['value'] / tot:.3f}%")


def load_prices(tickers=FUNDS):
    with (DATA / "monthly_prices.csv").open() as f:
        rows = list(csv.DictReader(f))
    dates = [r["date"] for r in rows]
    px = {t: [float(r[t]) if r[t] else math.nan for r in rows] for t in tickers}
    return dates, px


def ann(total_growth: float, months: int) -> float:
    return total_growth ** (12 / months) - 1


def returns_section():
    dates, px = load_prices()
    months = len(dates) - 1
    print(f"\n4. Total returns, {dates[0]} to {dates[-1]} ({months} months)")
    r = {t: [px[t][i + 1] / px[t][i] - 1 for i in range(months)] for t in FUNDS}
    a = {t: ann(px[t][-1] / px[t][0], months) for t in FUNDS}
    for t in FUNDS:
        grown = 10_000 * px[t][-1] / px[t][0]
        print(f"   {t}: {100 * a[t]:.2f}% a year; $10,000 grew to ${grown:,.0f}")

    print("\n   Calendar years (December to December month ends), %")
    print("   year   " + "  ".join(f"{t:>7s}" for t in FUNDS))
    dec = {d[:4]: i for i, d in enumerate(dates) if d[5:7] == "12"}
    for y in range(2019, 2026):
        i0, i1 = dec[str(y - 1)], dec[str(y)]
        cells = "  ".join(f"{100 * (px[t][i1] / px[t][i0] - 1):7.2f}" for t in FUNDS)
        print(f"   {y}   {cells}")

    print("\n   Pairs (A minus B)")
    for x, y in (("FZROX", "VTSAX"), ("FZROX", "FSKAX"), ("FSKAX", "VTSAX")):
        d = [r[x][i] - r[y][i] for i in range(months)]
        te = math.sqrt(12) * statistics.stdev(d)
        corr = statistics.correlation(r[x], r[y])
        rel = [px[x][i] / px[x][0] / (px[y][i] / px[y][0]) - 1 for i in range(months + 1)]
        gap = a[x] - a[y]
        fee = FEES[y] - FEES[x]

        def lead(window):
            n = wins = 0
            for i in range(window, months + 1):
                gx = px[x][i] / px[x][i - window]
                gy = px[y][i] / px[y][i - window]
                n += 1
                wins += gx > gy
            return wins, n

        w36, n36 = lead(36)
        w60, n60 = lead(60)
        print(
            f"   {x}-{y}: gap {100 * gap:+.3f} pts/yr (fee gap {100 * fee:+.3f}), "
            f"tracking error {100 * te:.3f} pts, correlation {corr:.5f}"
        )
        print(
            f"      relative wealth low {100 * min(rel):+.2f}% high {100 * max(rel):+.2f}% "
            f"end {100 * rel[-1]:+.2f}%; {x} ahead in {w36} of {n36} rolling "
            f"36-month and {w60} of {n60} rolling 60-month windows"
        )


def zero_funds_section():
    pairs = (("FZROX", "VTSAX"), ("FZILX", "VTIAX"), ("FNILX", "FXAIX"))
    dates, px = load_prices([t for p in pairs for t in p])
    months = 60
    i0 = len(dates) - 1 - months
    print(f"\n5. ZERO funds vs counterparts, {dates[i0]} to {dates[-1]}, % a year")
    for z, c in pairs:
        az = ann(px[z][-1] / px[z][i0], months)
        ac = ann(px[c][-1] / px[c][i0], months)
        print(f"   {z} {100 * az:6.2f}   {c} {100 * ac:6.2f}   gap {100 * (az - ac):+.2f}")


if __name__ == "__main__":
    holdings_section()
    returns_section()
    zero_funds_section()
