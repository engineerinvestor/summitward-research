"""What AVLV, AVUV, AVDV and AVGV hold on one day, measured against their indexes.

Inputs (fetch_data.py, fetch_fundamentals.py), all as of the Nov 20, 2026 close:
  Avantis daily holdings for AVLV, AVUV, AVDV, AVGV and AVGV's other sleeves
  (AVIV, AVES, AVMV); iShares holdings for the Russell 1000 (IWB), 1000 Value
  (IWD), 1000 Growth (IWF), 2000 (IWM), 2000 Value (IWN) and 2000 Growth (IWO);
  SEC-filed trailing net income, book equity and share counts for every U.S.
  stock; the Sep 30, 2026 Avantis fact-sheet characteristics.

Metrics fixed before the numbers were computed:
  - holdings, active share against the market index (IWB or IWM)
  - share of stock weight in companies with a trailing-twelve-month loss
  - share of stock weight by trailing P/E band (loss, under 15, 15-30, over 30)
  - aggregate P/E and P/B (weighted harmonic means; P/E over profitable
    companies only)
  - SEC coverage (share of stock weight with a usable filing)
  - a fixed list of named stocks with fund, market and value-index weights

Added after a first look at the results (reported as such in the guide):
  - weighted median P/E, because the harmonic mean sat well below Avantis's
    published fund P/Es and one-off GAAP gains (Lyft's tax benefit) drove it;
    the median matched Avantis's figures closely
  - share of weight in stocks the value index does not hold, and in stocks
    Russell assigns entirely to growth (value fractions inferred from
    IWB = a*IWD + (1-a)*IWF and the small-cap equivalent)
  - unadjusted weighted book/market and operating-cash-flow/book for AVLV and
    IWD, to set beside single companies on the same basis

Writes output/holdings_summary.json and prints every number the guide quotes.

Usage:
    python3 analyze.py
"""

from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
OUT = HERE / "output"
DATE = "2026-11-20"
FRESH_AFTER = "2026-03-31"  # net income period must end after this to count

US_STOCK = {"COMMON STOCK"}
SELECTED = {
    # AVLV names, fixed before computing; ticker -> label
    "MSFT": "Microsoft",
    "AAPL": "Apple",
    "META": "Meta Platforms",
    "NVDA": "Nvidia",
    "GOOGL": "Alphabet",
    "MU": "Micron",
    "SNDK": "Sandisk",
    "QCOM": "Qualcomm",
    "COST": "Costco",
    "LLY": "Eli Lilly",
    "XOM": "Exxon Mobil",
    "JPM": "JPMorgan Chase",
}
SELECTED_SMALL = {
    "LYFT": "Lyft",
    "M": "Macy's",
    "CROX": "Crocs",
    "GATX": "GATX",
    "MATX": "Matson",
}
SLEEVE_REGION = {
    "AVLV": "U.S.",
    "AVUV": "U.S.",
    "AVMV": "U.S.",
    "AVIV": "Developed ex-U.S.",
    "AVDV": "Developed ex-U.S.",
    "AVES": "Emerging",
}
SLEEVE_SIZE = {
    "AVLV": "large",
    "AVMV": "mid",
    "AVUV": "small",
    "AVIV": "large",
    "AVDV": "small",
    "AVES": "all",
}


def key(t: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(t).upper())


def num(x) -> float:
    s = str(x).replace(",", "").replace("%", "").strip()
    return 0.0 if s in ("", "-", "null", "None") else float(s)


# ---------------------------------------------------------------- fundamentals
FUND: dict[str, dict] = {}
for r in csv.DictReader((DATA / f"fundamentals_{DATE}.csv").open()):
    FUND[r["key"]] = r
CIK_OF = {k: r["cik"] for k, r in FUND.items() if r["cik"]}


def issuer(ticker: str) -> str:
    k = key(ticker)
    return "CIK" + CIK_OF[k] if k in CIK_OF else "T:" + k


# Stock splits between a company's latest cover-page share count and the
# snapshot date (Yahoo split history, checked for every flagged issuer by
# check_caps() below). Sandisk split 8-for-1 effective Nov 20, 2026, so its
# Oct 26 cover count must be multiplied by 8 to meet the Nov 20 price.
SPLITS = json.loads((DATA / f"splits_{DATE}.json").read_text())

# Issuer-level fundamentals: one record per CIK, price from its first-seen
# ticker. Alphabet's two classes share a CIK and trade within a few dollars.
ISSUER: dict[str, dict] = {}
for k, r in FUND.items():
    iss = "CIK" + r["cik"] if r["cik"] else "T:" + k
    if iss in ISSUER:
        continue
    rec = {"name": r["name"], "ticker": r["ticker"]}
    price = num(r["price"])
    shares = num(r["shares"]) if r.get("shares") else 0.0
    shares *= SPLITS.get(k, 1.0)
    cap = price * shares if price and shares else None
    ni = num(r["ni_ttm"]) if r.get("ni_ttm") else None
    fresh = bool(r.get("ni_end")) and r["ni_end"] > FRESH_AFTER
    book = num(r["book"]) if r.get("book") else None
    rec.update(cap=cap, ni=ni if fresh else None, book=book, ni_end=r.get("ni_end"))
    ISSUER[iss] = rec


# ---------------------------------------------------------------- holdings
def read_ishares(t: str) -> dict[str, float]:
    lines = (DATA / f"ishares_{t}_{DATE}.csv").read_text().splitlines()
    head = next(i for i, ln in enumerate(lines) if ln.startswith("Ticker,"))
    w: dict[str, float] = defaultdict(float)
    for r in csv.DictReader(lines[head:]):
        if r.get("Asset Class") != "Equity":
            continue
        if r.get("Exchange", "").startswith("NO MARKET"):
            continue  # unlisted stubs
        w[issuer(r["Ticker"])] += num(r["Market Value"])
    tot = sum(w.values())
    return {k: v / tot for k, v in w.items()}


def read_avantis_rows(t: str) -> list[dict]:
    return list(csv.DictReader((DATA / f"avantis_{t}_{DATE}.csv").open()))


def avantis_us(t: str) -> tuple[dict[str, float], float]:
    """Issuer weights within the fund's U.S. stocks, and the non-stock share."""
    rows = read_avantis_rows(t)
    total = sum(num(r["baseMarketValue"]) for r in rows)
    w: dict[str, float] = defaultdict(float)
    for r in rows:
        if r["securityType"] in US_STOCK:
            w[issuer(r["ticker"])] += num(r["baseMarketValue"])
    stocks = sum(w.values())
    return {k: v / stocks for k, v in w.items()}, 1 - stocks / total


def avantis_intl(t: str) -> tuple[dict[str, float], list[dict]]:
    """ISIN-keyed weights within the fund's stocks, plus the raw stock rows."""
    rows = [
        r
        for r in read_avantis_rows(t)
        if "COMMON" in (r["securityType"] or "") or "ADR" in (r["securityType"] or "")
    ]
    tot = sum(num(r["baseMarketValue"]) for r in rows)
    w: dict[str, float] = defaultdict(float)
    for r in rows:
        w[r["isin"] or r["name"]] += num(r["baseMarketValue"]) / tot
    return dict(w), rows


ISH = {t: read_ishares(t) for t in ["IWB", "IWD", "IWF", "IWM", "IWN", "IWO"]}
AV_US = {t: avantis_us(t) for t in ["AVLV", "AVUV", "AVMV"]}


def check_caps() -> list[dict]:
    """Flag SEC market caps that disagree with the index file.

    An index fund's weight in a stock is proportional to its float-adjusted
    market cap, so weight / SEC cap is roughly constant across an index. A
    ratio of SEC cap to the index-implied float cap below 0.6 means a stale or
    short share count (a split after the cover date, a share class missing from
    the cover). Ratios up to about 20 are real: closely held companies such as
    CNA Financial or Ubiquiti have small floats. Above 25 the share count is
    mis-scaled or the ticker matched the wrong company. Flagged issuers get
    their split checked
    (check_splits.py); any still flagged are left out of the P/E and P/B
    figures and counted as uncovered.
    """
    flags = []
    for idx in ("IWB", "IWM"):
        w = ISH[idx]
        pairs = [(k, w[k] / ISSUER[k]["cap"]) for k in w if ISSUER.get(k, {}).get("cap")]
        kmed = float(np.median([v for _, v in pairs]))
        for k, v in pairs:
            ratio = kmed / v  # SEC cap over index-implied float cap
            if ratio < 0.6 or ratio > 25:
                rec = ISSUER[k]
                flags.append(
                    {"issuer": k, "ticker": rec["ticker"], "index": idx,
                     "ratio": round(ratio, 3), "weight": round(100 * w[k], 4)}
                )  # fmt: skip
    return flags


SECTOR: dict[str, str] = {}
for t in ISH:
    _lines = (DATA / f"ishares_{t}_{DATE}.csv").read_text().splitlines()
    _head = next(i for i, ln in enumerate(_lines) if ln.startswith("Ticker,"))
    for _r in csv.DictReader(_lines[_head:]):
        if _r.get("Asset Class") == "Equity":
            SECTOR.setdefault(issuer(_r["Ticker"]), _r["Sector"].upper())
for t in AV_US:
    for _r in read_avantis_rows(t):
        if _r["securityType"] in US_STOCK:
            SECTOR.setdefault(issuer(_r["ticker"]), (_r["sector"] or "").upper())
CFO: dict[str, float] = {}
for _r in csv.DictReader((DATA / f"cfo_{DATE}.csv").open()):
    if _r["cfo_ttm"]:
        CFO.setdefault(issuer(_r["ticker"]), float(_r["cfo_ttm"]))


def unadjusted_tilts(w: dict[str, float]) -> dict:
    """Weighted average book/market and operating-cash-flow/book from filed,
    unadjusted figures. Cash flow/book leaves out financials, whose operating
    cash flow is not a profitability measure (JPMorgan's was negative)."""
    bm = bmw = pb_ = pbw = 0.0
    for k, x in w.items():
        rec = ISSUER.get(k)
        if not rec or not rec.get("cap") or rec.get("cap_flag"):
            continue
        book = rec.get("book")
        if not book or book <= 0:
            continue
        bm += x * book / rec["cap"]
        bmw += x
        if k in CFO and SECTOR.get(k, "") != "FINANCIALS":
            pb_ += x * CFO[k] / book
            pbw += x
    return {
        "book_to_market": round(bm / bmw, 3),
        "book_to_market_coverage": pct(bmw, 1),
        "cfo_to_book_ex_financials": round(pb_ / pbw, 3),
        "cfo_to_book_coverage": pct(pbw, 1),
    }


FLAGS = check_caps()
for f in FLAGS:
    ISSUER[f["issuer"]]["cap_flag"] = True


# ---------------------------------------------------------------- metrics
def coverage_and_bands(w: dict[str, float]) -> dict:
    cov = loss = 0.0
    bands = {"loss": 0.0, "under 15": 0.0, "15 to 30": 0.0, "over 30": 0.0}
    ep_sum = ep_w = 0.0  # harmonic P/E over profitable names
    pe_pts: list[tuple[float, float]] = []  # (P/E, weight) for the weighted median
    bp_sum = bp_w = 0.0
    for k, wk in w.items():
        rec = ISSUER.get(k)
        if not rec or rec["ni"] is None or not rec["cap"] or rec.get("cap_flag"):
            continue
        cov += wk
        ni, cap = rec["ni"], rec["cap"]
        if ni < 0:
            loss += wk
            bands["loss"] += wk
        else:
            pe = cap / ni if ni > 0 else float("inf")
            band = "under 15" if pe < 15 else ("15 to 30" if pe <= 30 else "over 30")
            bands[band] += wk
            ep_sum += wk * ni / cap
            ep_w += wk
            if ni > 0:
                pe_pts.append((cap / ni, wk))
        if rec["book"] and rec["book"] > 0:
            bp_sum += wk * rec["book"] / cap
            bp_w += wk
    pe_pts.sort()
    half, run, median_pe = sum(x for _, x in pe_pts) / 2, 0.0, float("nan")
    for v, x in pe_pts:
        run += x
        if run >= half:
            median_pe = v
            break
    return {
        "median_pe": median_pe,
        "coverage": cov,
        "loss_share": loss / cov,
        "bands": {b: v / cov for b, v in bands.items()},
        "pe_profitable": ep_w / ep_sum,
        "pb": bp_w / bp_sum,
    }


def active_share(a: dict, b: dict) -> float:
    keys = set(a) | set(b)
    return 0.5 * sum(abs(a.get(k, 0.0) - b.get(k, 0.0)) for k in keys)


def value_fractions(b: dict, v: dict, g: dict) -> tuple[dict, float, float]:
    keys = sorted(b)
    y = np.array([b[k] for k in keys])
    xv = np.array([v.get(k, 0.0) for k in keys])
    xg = np.array([g.get(k, 0.0) for k in keys])
    d = xv - xg
    a = float(np.dot(d, y - xg) / np.dot(d, d))
    fit = a * xv + (1 - a) * xg
    r2 = 1 - np.sum((y - fit) ** 2) / np.sum((y - y.mean()) ** 2)
    frac = {}
    for k in keys:
        den = a * v.get(k, 0.0) + (1 - a) * g.get(k, 0.0)
        if den > 0:
            frac[k] = a * v.get(k, 0.0) / den
    return frac, a, float(r2)


def growth_share(w: dict, frac: dict) -> tuple[float, float]:
    inside = {k: x for k, x in w.items() if k in frac}
    tot = sum(inside.values())
    return 1 - sum(x * frac[k] for k, x in inside.items()) / tot, tot


def pct(x: float, nd: int = 2) -> float:
    return round(float(x) * 100, nd)


def main() -> None:
    OUT.mkdir(exist_ok=True)
    res: dict = {"as_of": DATE}

    frac_l, a_l, r2_l = value_fractions(ISH["IWB"], ISH["IWD"], ISH["IWF"])
    frac_s, a_s, r2_s = value_fractions(ISH["IWM"], ISH["IWN"], ISH["IWO"])
    res["russell_split"] = {
        "large_value_share_of_iwb": round(a_l, 4),
        "large_fit_r2": round(r2_l, 4),
        "small_value_share_of_iwm": round(a_s, 4),
        "small_fit_r2": round(r2_s, 4),
    }

    groups = {
        "large": (["AVLV", "IWD", "IWB"], "IWB", frac_l),
        "small": (["AVUV", "IWN", "IWM"], "IWM", frac_s),
    }
    res["portfolios"] = {}
    val_of = {"AVLV": "IWD", "IWD": "IWD", "IWB": "IWD", "AVUV": "IWN", "IWN": "IWN", "IWM": "IWN"}
    for _grp, (names, mkt, frac) in groups.items():
        for p in names:
            w = AV_US[p][0] if p in AV_US else ISH[p]
            m = coverage_and_bands(w)
            g, inside = growth_share(w, frac)
            res["portfolios"][p] = {
                "issuers": len(w),
                "active_share_vs_market": pct(active_share(w, ISH[mkt]), 1),
                "coverage": pct(m["coverage"], 1),
                "loss_share": pct(m["loss_share"], 1),
                "pe_bands": {b: pct(v, 1) for b, v in m["bands"].items()},
                "pe_profitable": round(m["pe_profitable"], 1),
                "pe_weighted_median": round(m["median_pe"], 1),
                "pb": round(m["pb"], 2),
                "russell_growth_share": pct(g, 1),
                "share_not_in_value_index": pct(
                    sum(x for k, x in w.items() if k not in ISH[val_of[p]]), 1
                ),
                "share_pure_growth": pct(
                    sum(
                        x
                        for k, x in w.items()
                        if (frac_l.get(k) if k in ISH["IWB"] else frac_s.get(k)) == 0
                    ),
                    1,
                ),
                "share_inside_russell": pct(inside, 1),
                "share_in_russell_1000": pct(
                    sum(x for k, x in w.items() if k in ISH["IWB"]), 1
                ),
            }
            if p in AV_US:
                res["portfolios"][p]["non_stock_share"] = pct(AV_US[p][1], 2)
            if p in ("AVLV", "IWD"):
                res["portfolios"][p]["unadjusted"] = unadjusted_tilts(w)


    def named(sel: dict, fund: str, mkt: str, val: str) -> list[dict]:
        out = []
        w = AV_US[fund][0]
        rank = {k: i + 1 for i, (k, _) in enumerate(sorted(w.items(), key=lambda kv: -kv[1]))}
        for t, label in sel.items():
            k = issuer(t)
            rec = ISSUER.get(k, {})
            pe = (
                rec["cap"] / rec["ni"]
                if rec.get("cap") and rec.get("ni") and rec["ni"] > 0
                and not rec.get("cap_flag")
                else None
            )
            out.append(
                {
                    "ticker": t,
                    "name": label,
                    "fund": pct(w.get(k, 0.0)),
                    "market": pct(ISH[mkt].get(k, 0.0)),
                    "value_index": pct(ISH[val].get(k, 0.0)),
                    "active_vs_market": pct(w.get(k, 0.0) - ISH[mkt].get(k, 0.0)),
                    "active_vs_value_index": pct(w.get(k, 0.0) - ISH[val].get(k, 0.0)),
                    "ratio_to_market": (
                        round(w.get(k, 0.0) / ISH[mkt][k], 2)
                        if ISH[mkt].get(k)
                        else None
                    ),
                    "trailing_pe": round(pe, 1) if pe else None,
                    "ttm_net_income_bn": (
                        round(rec["ni"] / 1e9, 2) if rec.get("ni") is not None else None
                    ),
                    "ni_period_end": rec.get("ni_end"),
                    "rank_in_fund": rank.get(k),
                    "book_to_market": (
                        round(rec["book"] / rec["cap"], 3)
                        if rec.get("book") and rec.get("cap") and not rec.get("cap_flag")
                        else None
                    ),
                    "cfo_ttm_bn": round(CFO[k] / 1e9, 2) if k in CFO else None,
                    "cfo_to_book": (
                        round(CFO[k] / rec["book"], 3)
                        if k in CFO
                        and SECTOR.get(k, "") != "FINANCIALS"
                        and rec.get("book")
                        else None
                    ),
                    "russell_growth_fraction": (
                        round(1 - (frac_l if mkt == "IWB" else frac_s).get(k, 0), 3)
                        if k in (frac_l if mkt == "IWB" else frac_s)
                        else None
                    ),
                }
            )
        return out

    res["named_large"] = named(SELECTED, "AVLV", "IWB", "IWD")
    res["named_small"] = named(SELECTED_SMALL, "AVUV", "IWM", "IWN")

    # ------------------------------------------------------------ AVDV
    w_dv, rows_dv = avantis_intl("AVDV")
    tot = sum(num(r["baseMarketValue"]) for r in rows_dv)
    by_country: dict[str, float] = defaultdict(float)
    by_sector: dict[str, float] = defaultdict(float)
    for r in rows_dv:
        by_country[r["country"].title()] += num(r["baseMarketValue"]) / tot
        by_sector[r["sector"].title()] += num(r["baseMarketValue"]) / tot
    top10 = sorted(w_dv.values(), reverse=True)[:10]
    name_of = {(r["isin"] or r["name"]): r["name"] for r in rows_dv}
    top_names = sorted(w_dv.items(), key=lambda kv: -kv[1])[:10]
    res["avdv"] = {
        "stocks": len(w_dv),
        "countries_ex_us": sum(
            1 for c, v in by_country.items() if c != "United States" and v >= 0.0001
        ),
        "top10_weight": pct(sum(top10), 1),
        "country_top6": [
            {"country": c, "weight": pct(v, 1)}
            for c, v in sorted(by_country.items(), key=lambda kv: -kv[1])[:6]
        ],
        "sector_top5": [
            {"sector": c, "weight": pct(v, 1)}
            for c, v in sorted(by_sector.items(), key=lambda kv: -kv[1])[:5]
        ],
        "top10": [{"name": name_of[k], "weight": pct(v)} for k, v in top_names],
    }

    # ------------------------------------------------------------ AVGV
    sleeves = {}
    for r in read_avantis_rows("AVGV"):
        if r["securityType"] == "MANAGED INVESTMENT COMPANIES":
            sleeves[r["ticker"]] = num(r["baseMarketValue"])
    stot = sum(sleeves.values())
    sleeves = {t: v / stot for t, v in sleeves.items()}
    look: dict[str, float] = defaultdict(float)
    label: dict[str, str] = {}
    for t, ws in sleeves.items():
        if t in AV_US:
            for k, wk in AV_US[t][0].items():
                look[k] += ws * wk
                label.setdefault(k, ISSUER.get(k, {}).get("name", k))
        else:
            wi, rows_i = avantis_intl(t)
            for k, wk in wi.items():
                look[k] += ws * wk
            for r in rows_i:
                label.setdefault(r["isin"] or r["name"], r["name"])
    region: dict[str, float] = defaultdict(float)
    for t, ws in sleeves.items():
        region[SLEEVE_REGION[t]] += ws
    ranked = sorted(look.values(), reverse=True)
    res["avgv"] = {
        "sleeves": {t: pct(v) for t, v in sorted(sleeves.items(), key=lambda kv: -kv[1])},
        "regions": {r: pct(v, 1) for r, v in region.items()},
        "look_through_stocks": len(look),
        "top10_weight": pct(sum(ranked[:10]), 1),
        "top50_weight": pct(sum(ranked[:50]), 1),
        "named": [
            {"name": lbl, "weight": pct(look.get(issuer(t), 0.0))}
            for t, lbl in SELECTED.items()
        ],
        "small_cap_sleeves": pct(sleeves.get("AVUV", 0) + sleeves.get("AVDV", 0), 1),
    }
    # U.S. part of AVGV: loss share across the three U.S. sleeves combined
    us_w: dict[str, float] = defaultdict(float)
    us_tot = sum(sleeves.get(t, 0) for t in AV_US)
    for t in AV_US:
        for k, wk in AV_US[t][0].items():
            us_w[k] += sleeves.get(t, 0) / us_tot * wk
    m = coverage_and_bands(us_w)
    res["avgv"]["us_sleeves_loss_share"] = pct(m["loss_share"], 1)
    res["avgv"]["us_sleeves_coverage"] = pct(m["coverage"], 1)

    # ------------------------------------------------------------ fact sheets
    fs = list(csv.DictReader((DATA / "factsheets_2026-09-30.csv").open()))
    res["factsheets_2026_09_30"] = [
        {k: r[k] for k in ("portfolio", "benchmark_of", "book_to_market",
                           "profits_to_book", "mkt_cap_bn", "holdings")}
        for r in fs
    ]  # fmt: skip
    chars = json.loads(
        (DATA / f"avantis_page_characteristics_{DATE}.json").read_text()
    )
    res["avantis_published_pe_2026_10_31"] = {
        t: chars[t]["priceEarningsRatio"] for t in ("AVLV", "AVUV", "AVDV")
    }

    res["cap_flags"] = sorted(FLAGS, key=lambda f: -f["weight"])
    (OUT / "holdings_summary.json").write_text(json.dumps(res, indent=1) + "\n")
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
