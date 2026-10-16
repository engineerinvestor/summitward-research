"""Replicate Elm Wealth's "TIPS: Safer Than They Seem" spending-risk exhibit.

Haghani and White (Elm Wealth, 2026-10-14) measure wealth as the level annual
spending it can buy through a 50-year real annuity, and compare how that
spending changed each year (years ending September 30) for someone holding
T-bills, 30-year nominal Treasuries, or 30-year TIPS. This script rebuilds the
exhibit from public data for the Summitward guide
https://summitward.com/learn/tips-safer-than-they-seem

Usage:
    python3 replicate_elm_tips.py --fetch   # rebuild data/*.csv from the sources
    python3 replicate_elm_tips.py           # compute and print (add --ts to write TS)

Inputs (``data/``), all public:
  - Long real yield on each September 30. From 2010-02-22, Treasury's 30-year
    par real yield. Before that, the 20-year par TIPS yield from the Federal
    Reserve's Gurkaynak-Sack-Wright TIPS curve (feds200805), the longest
    maturity it publishes; Elm likewise used "the longest maturity bond
    available" before 30-year issuance resumed.
  - 30-year nominal par yield from the Fed's GSW nominal curve (feds200628),
    which has no 2002-2006 gap, unlike Treasury's 30-year CMT.
  - Month-end 3-month Treasury CMT yields (Treasury daily par yield curve).
  - CPI-U NSA (BLS series CUUR0000SA0).

Method, each year ending September 30:
  - TIPS: buy a new 30-year TIPS at par at that day's long real yield (coupon
    floored at Treasury's 0.125% minimum), reprice a year later as a 29-year bond
    at the new long real yield, add the coupon. Principal accretes with the
    reference CPI (June/July interpolation per 31 CFR 356 App. B), and the
    result is deflated by September-to-September CPI, so the indexation lag
    shows up.
  - Nominal: same with a 30-year nominal par bond, deflated by CPI.
  - T-bills: roll the 3-month bill monthly at the month-start yield, deflated.
  - Spending change: (1 + real return) * A(start) / A(end) - 1, where A is the
    level 50-year real annuity factor at the long real yield (flat curve).
Flat-yield pricing and a flat annuity curve are simplifications Elm's own
description implies; the guide states both.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import math
import statistics
import sys
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parent
DATA = REPO / "data"
CACHE = REPO / ".cache"
OUT = REPO / "output" / "tips-spending-risk.ts"

FIRST_YEAR = 1999  # GSW TIPS curve starts 1999-01-04, so first window is 1999-2000
LAST_YEAR = 2026
TREASURY_30Y_REAL_START = date(2010, 2, 22)
MIN_TIPS_COUPON = 0.00125
ANNUITY_YEARS = 50
BOND_YEARS = 30

GSW_TIPS_URL = "https://www.federalreserve.gov/data/yield-curve-tables/feds200805.csv"
GSW_NOMINAL_URL = (
    "https://www.federalreserve.gov/data/yield-curve-tables/feds200628.csv"
)
TREASURY_URL = (
    "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
    "daily-treasury-rates.csv/{year}/all?type={kind}"
    "&field_tdr_date_value={year}&page&_format=csv"
)
BLS_URL = "https://api.bls.gov/publicAPI/v2/timeseries/data/"
USER_AGENT = "summitward-guide-data/1.0"

ASSETS = ("tips", "nominal", "bills")


# --------------------------------------------------------------------------
# Fetch: raw sources -> two small CSVs under data/
# --------------------------------------------------------------------------


def _get(url: str, cache_name: str, refresh: bool) -> str:
    CACHE.mkdir(parents=True, exist_ok=True)
    cached = CACHE / cache_name
    if cached.exists() and not refresh:
        return cached.read_text()
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=120) as resp:  # noqa: S310
        text = resp.read().decode("utf-8-sig")
    cached.write_text(text)
    return text


def _num(raw: str | None) -> float | None:
    try:
        value = float((raw or "").strip())
    except ValueError:
        return None
    return None if math.isnan(value) else value


def _gsw_series(text: str, column: str) -> dict[date, float]:
    rows = list(csv.reader(io.StringIO(text)))
    start = next(i for i, r in enumerate(rows) if r and r[0] == "Date")
    header = rows[start]
    idx = header.index(column)
    out: dict[date, float] = {}
    for row in rows[start + 1 :]:
        value = _num(row[idx]) if len(row) > idx else None
        if value is not None:
            out[date.fromisoformat(row[0])] = value
    return out


def _treasury_series(kind: str, column: str, years: range, refresh: bool):
    out: dict[date, float] = {}
    for year in years:
        # Completed years never change; always refetch the current one.
        text = _get(
            TREASURY_URL.format(year=year, kind=kind),
            f"{kind}-{year}.csv",
            refresh or year == date.today().year,
        )
        for row in csv.DictReader(io.StringIO(text)):
            value = _num(row.get(column))
            if value is not None:
                day = datetime.strptime(row["Date"].strip(), "%m/%d/%Y").date()
                out[day] = value
    return out


def _bls_cpi(refresh: bool) -> dict[str, float]:
    cached = CACHE / "bls-CUUR0000SA0.json"
    if cached.exists() and not refresh:
        return json.loads(cached.read_text())
    out: dict[str, float] = {}
    for start in range(FIRST_YEAR - 1, LAST_YEAR + 1, 10):
        body = json.dumps(
            {
                "seriesid": ["CUUR0000SA0"],
                "startyear": str(start),
                "endyear": str(min(start + 9, LAST_YEAR)),
            }
        ).encode()
        req = urllib.request.Request(
            BLS_URL,
            data=body,
            headers={"Content-type": "application/json", "User-Agent": USER_AGENT},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310
            payload = json.loads(resp.read())
        if payload.get("status") != "REQUEST_SUCCEEDED":
            raise SystemExit(f"BLS request failed: {payload.get('message')}")
        for obs in payload["Results"]["series"][0]["data"]:
            value = _num(obs["value"])  # October 2025 was never collected: "-"
            if obs["period"].startswith("M") and obs["period"] != "M13" and value:
                out[f"{obs['year']}-{obs['period'][1:]}"] = value
    CACHE.mkdir(parents=True, exist_ok=True)
    cached.write_text(json.dumps(out, sort_keys=True, indent=0))
    return out


def _on_or_before(series: dict[date, float], day: date) -> tuple[date, float]:
    for back in range(10):
        probe = day - timedelta(days=back)
        if probe in series:
            return probe, series[probe]
    raise SystemExit(f"no observation within 10 days before {day}")


def _month_ends(start: date, end: date) -> list[date]:
    days, y, m = [], start.year, start.month
    while True:
        nxt = date(y + (m == 12), m % 12 + 1, 1) - timedelta(days=1)
        if nxt > end:
            break
        days.append(nxt)
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return days


def fetch(refresh: bool) -> None:
    gsw_tips = _get(GSW_TIPS_URL, "feds200805.csv", refresh)
    gsw_nom = _get(GSW_NOMINAL_URL, "feds200628.csv", refresh)
    tips20 = _gsw_series(gsw_tips, "TIPSPY20")
    nom30 = _gsw_series(gsw_nom, "SVENPY30")
    years = range(FIRST_YEAR, LAST_YEAR + 1)
    real30 = _treasury_series(
        "daily_treasury_real_yield_curve", "30 YR", range(2010, LAST_YEAR + 1), refresh
    )
    bill3m = _treasury_series("daily_treasury_yield_curve", "3 Mo", years, refresh)
    cpi = _bls_cpi(refresh)

    DATA.mkdir(parents=True, exist_ok=True)
    with (DATA / "annual.csv").open("w", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(
            [
                "sep30",
                "real_long_pct",
                "real_long_source",
                "real_long_obs_date",
                "gsw_tips20_par_pct",
                "nominal30_par_pct",
                "cpi_jun",
                "cpi_jul",
                "cpi_sep",
            ]
        )
        for year in years:
            day = date(year, 9, 30)
            g_day, g20 = _on_or_before(tips20, day)
            if day >= TREASURY_30Y_REAL_START:
                r_day, r_long = _on_or_before(real30, day)
                source = "treasury_30y_par_real"
            else:
                r_day, r_long, source = g_day, g20, "gsw_20y_par_tips"
            _, n30 = _on_or_before(nom30, day)
            w.writerow(
                [
                    day.isoformat(),
                    f"{r_long:.4f}",
                    source,
                    r_day.isoformat(),
                    f"{g20:.4f}",
                    f"{n30:.4f}",
                    cpi[f"{year}-06"],
                    cpi[f"{year}-07"],
                    cpi[f"{year}-09"],
                ]
            )
    with (DATA / "bills.csv").open("w", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["month_end", "bill3m_pct", "obs_date"])
        for m_end in _month_ends(date(FIRST_YEAR, 9, 1), date(LAST_YEAR, 9, 30)):
            o_day, value = _on_or_before(bill3m, m_end)
            w.writerow([m_end.isoformat(), f"{value:.2f}", o_day.isoformat()])
    print(f"wrote {(DATA / 'annual.csv').relative_to(REPO)} and bills.csv")


# --------------------------------------------------------------------------
# Compute
# --------------------------------------------------------------------------


def bond_price(coupon: float, yld: float, years: int) -> float:
    """Price per 1 of par, semiannual coupons, flat yield (bond-equivalent)."""
    k, h = 2 * years, yld / 2
    if abs(h) < 1e-12:
        return coupon / 2 * k + 1
    return coupon / 2 * (1 - (1 + h) ** -k) / h + (1 + h) ** -k


def annuity_factor(yld: float, years: int) -> float:
    """Level annual real annuity, first payment in one year, flat yield."""
    r = (1 + yld / 2) ** 2 - 1
    return float(years) if abs(r) < 1e-12 else (1 - (1 + r) ** -years) / r


def modified_duration_bond(coupon: float, yld: float, years: int) -> float:
    h = 1e-5
    up, dn = bond_price(coupon, yld + h, years), bond_price(coupon, yld - h, years)
    return -(up - dn) / (2 * h) / bond_price(coupon, yld, years)


def modified_duration_annuity(yld: float, years: int) -> float:
    h = 1e-5
    up, dn = annuity_factor(yld + h, years), annuity_factor(yld - h, years)
    return -(up - dn) / (2 * h) / annuity_factor(yld, years)


def load_inputs() -> tuple[list[dict], dict[date, float]]:
    with (DATA / "annual.csv").open() as fh:
        annual = list(csv.DictReader(fh))
    with (DATA / "bills.csv").open() as fh:
        bills = {
            date.fromisoformat(r["month_end"]): float(r["bill3m_pct"]) / 100
            for r in csv.DictReader(fh)
        }
    return annual, bills


def bill_growth(bills: dict[date, float], start: date, end: date) -> float:
    ends = sorted(d for d in bills if start <= d <= end)
    growth = 1.0
    for a, b in zip(ends, ends[1:], strict=False):
        growth *= 1 + bills[a] * (b - a).days / 365
    return growth


def compute(annuity_years: int = ANNUITY_YEARS) -> list[dict]:
    annual, bills = load_inputs()
    rows = []
    for prev, cur in zip(annual, annual[1:], strict=False):
        r0 = float(prev["real_long_pct"]) / 100
        r1 = float(cur["real_long_pct"]) / 100
        n0 = float(prev["nominal30_par_pct"]) / 100
        n1 = float(cur["nominal30_par_pct"]) / 100
        cpi_ratio = float(cur["cpi_sep"]) / float(prev["cpi_sep"])

        def ref_cpi(row: dict) -> float:
            jun, jul = float(row["cpi_jun"]), float(row["cpi_jul"])
            return jun + (29 / 30) * (jul - jun)  # Ref CPI for September 30

        coupon = max(r0, MIN_TIPS_COUPON)
        tips_index = (bond_price(coupon, r1, BOND_YEARS - 1) + coupon) / bond_price(
            coupon, r0, BOND_YEARS
        )
        real = {
            "tips": tips_index * (ref_cpi(cur) / ref_cpi(prev)) / cpi_ratio - 1,
            "nominal": (bond_price(n0, n1, BOND_YEARS - 1) + n0) / cpi_ratio - 1,
            "bills": bill_growth(
                bills,
                date.fromisoformat(prev["sep30"]),
                date.fromisoformat(cur["sep30"]),
            )
            / cpi_ratio
            - 1,
        }
        a0, a1 = annuity_factor(r0, annuity_years), annuity_factor(r1, annuity_years)
        row = {
            "year": int(cur["sep30"][:4]),
            "realYieldStart": r0,
            "realYieldEnd": r1,
            "inflation": cpi_ratio - 1,
        }
        for asset in ASSETS:
            row[f"{asset}Price"] = real[asset]
            row[f"{asset}Spending"] = (1 + real[asset]) * a0 / a1 - 1
        rows.append(row)
    return rows


def summarize(rows: list[dict]) -> dict:
    out = {}
    for asset in ASSETS:
        for yardstick in ("Price", "Spending"):
            xs = [r[f"{asset}{yardstick}"] for r in rows]
            out[f"{asset}{yardstick}"] = {
                "mean": statistics.mean(xs),
                "sd": statistics.stdev(xs),
                "worst": min(xs),
                "best": max(xs),
                "cumulative": math.prod(1 + x for x in xs) - 1,
            }
    return out


def pct(x: float, nd: int = 1) -> str:
    return f"{100 * x:.{nd}f}%"


def report(rows: list[dict], label: str) -> dict:
    s = summarize(rows)
    print(f"\n{label}: years ending Sep 30, {rows[0]['year']}-{rows[-1]['year']}")
    print(
        f"{'':10s}{'spend mean':>11s}{'spend sd':>10s}{'price sd':>10s}"
        f"{'worst sp':>10s}{'cum sp':>9s}"
    )
    for asset in ASSETS:
        sp, pr = s[f"{asset}Spending"], s[f"{asset}Price"]
        print(
            f"{asset:10s}{pct(sp['mean'], 2):>11s}{pct(sp['sd']):>10s}"
            f"{pct(pr['sd']):>10s}{pct(sp['worst']):>10s}{pct(sp['cumulative']):>9s}"
        )
    return s


def ts_number(x: float, nd: int = 2) -> str:
    return f"{100 * x:.{nd}f}"


def write_ts(rows: list[dict], base: dict, alt30: dict, durations: list[dict]) -> None:
    annual, _ = load_inputs()
    last_obs = annual[-1]["real_long_obs_date"]

    def row_literal(r: dict) -> str:
        fields = [
            f"year: {r['year']}",
            f"realYieldStart: {ts_number(r['realYieldStart'])}",
            f"realYieldEnd: {ts_number(r['realYieldEnd'])}",
            f"inflation: {ts_number(r['inflation'])}",
        ]
        for asset in ASSETS:
            fields.append(f"{asset}Price: {ts_number(r[f'{asset}Price'], 1)}")
            fields.append(f"{asset}Spending: {ts_number(r[f'{asset}Spending'], 1)}")
        return "  {\n" + "".join(f"    {f},\n" for f in fields) + "  },"

    def stats_literal(name: str, s: dict) -> str:
        lines = [f"export const {name}: Record<SeriesKey, SeriesStats> = {{"]
        for key in sorted(s):
            v = s[key]
            lines.append(
                f"  {key}: {{ mean: {ts_number(v['mean'])}, sd: {ts_number(v['sd'])}, "
                f"worst: {ts_number(v['worst'], 1)}, best: {ts_number(v['best'], 1)}, "
                f"cumulative: {ts_number(v['cumulative'], 1)} }},"
            )
        lines.append("};")
        return "\n".join(lines)

    dur_lines = "\n".join(
        f"  {{ realYield: {d['y']:.2f}, bond30: {d['bond30']:.1f}, "
        f"annuity50: {d['ann50']:.1f}, annuity30: {d['ann30']:.1f} }},"
        for d in durations
    )

    body = f"""// GENERATED FILE - do not hand-edit.
// Regenerate with: python3 replicate_elm_tips.py --ts
//
// Replication of Elm Wealth's "TIPS: Safer Than They Seem" (Haghani and White,
// 2026-10-14) exhibit: the annual change in level real spending a 50-year real
// annuity could buy, for an investor holding rolled 30-year TIPS, rolled
// 30-year nominal Treasuries, or T-bills, years ending September 30.
//
// Sources: Federal Reserve Gurkaynak-Sack-Wright TIPS and nominal yield curves
// (feds200805, feds200628); U.S. Treasury daily par real and nominal yield
// curves; BLS CPI-U NSA (CUUR0000SA0). Long real yield is Treasury's 30-year par
// real yield from 2010-02-22 and the GSW 20-year par TIPS yield before then.
// Flat-yield bond pricing; flat real curve for the annuity factor.
// All values are percents. Last observation {last_obs}.

export type SeriesKey =
  | "tipsPrice"
  | "tipsSpending"
  | "nominalPrice"
  | "nominalSpending"
  | "billsPrice"
  | "billsSpending";

export interface SeriesStats {{
  mean: number;
  sd: number;
  worst: number;
  best: number;
  cumulative: number;
}}

export interface SpendingRiskYear {{
  /** Year ending September 30. */
  year: number;
  /** Long real yield at the start and end of the year. */
  realYieldStart: number;
  realYieldEnd: number;
  /** September-to-September CPI-U change. */
  inflation: number;
  /** Real total return (the "price" yardstick). */
  tipsPrice: number;
  /** Change in 50-year real annuity spending the holding could buy. */
  tipsSpending: number;
  nominalPrice: number;
  nominalSpending: number;
  billsPrice: number;
  billsSpending: number;
}}

export const SPENDING_RISK_LAST_OBS = "{last_obs}";

export const SPENDING_RISK_YEARS: SpendingRiskYear[] = [
{chr(10).join(row_literal(r) for r in rows)}
];

{stats_literal("SPENDING_RISK_STATS", base)}

/** Same assets measured against a 30-year (not 50-year) real annuity. */
{stats_literal("SPENDING_RISK_STATS_30Y", alt30)}

/** Modified durations at a flat real yield (percent). */
export const DURATION_TABLE = [
{dur_lines}
];
"""
    OUT.write_text(body)
    print(f"\nwrote {OUT.relative_to(REPO)}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fetch", action="store_true", help="rebuild input CSVs")
    parser.add_argument("--refresh", action="store_true", help="ignore the cache")
    parser.add_argument("--ts", action="store_true", help="also write output/*.ts")
    args = parser.parse_args()

    if args.fetch:
        fetch(args.refresh)

    rows = compute()
    base = report(rows, "Elm spec (50-year annuity)")
    print(
        "\nElm published (inset, 1999-2026): TIPS 1.3% / 2.8%, "
        "30-yr Treasury 0.7% / 6.7%, T-bills 0.2% / 14.2%"
    )
    report([r for r in rows if r["year"] >= 2011], "Treasury 30Y real on both ends")
    report([r for r in rows if r["year"] != 2022], "Excluding 2022")
    alt30 = report(compute(annuity_years=30), "Against a 30-year annuity")

    durations = []
    for y in (0.0, 0.01, 0.02, 0.03):
        c = max(y, MIN_TIPS_COUPON)
        durations.append(
            {
                "y": 100 * y,
                "bond30": modified_duration_bond(c, y, BOND_YEARS),
                "ann50": modified_duration_annuity(y, 50),
                "ann30": modified_duration_annuity(y, 30),
            }
        )
    print("\nModified duration at a flat real yield")
    for d in durations:
        print(
            f"  {d['y']:.0f}%: 30y bond {d['bond30']:.1f}  50y annuity "
            f"{d['ann50']:.1f}  30y annuity {d['ann30']:.1f}"
        )
    print("\nYear-by-year (spending change, %):")
    for r in rows:
        print(
            f"  {r['year']}  real {ts_number(r['realYieldStart'])}->"
            f"{ts_number(r['realYieldEnd'])}  TIPS {ts_number(r['tipsSpending'], 1):>6s}"
            f"  nominal {ts_number(r['nominalSpending'], 1):>6s}"
            f"  bills {ts_number(r['billsSpending'], 1):>6s}"
            f"  | TIPS price {ts_number(r['tipsPrice'], 1):>6s}"
        )

    if args.ts:
        OUT.parent.mkdir(exist_ok=True)
        write_ts(rows, base, alt30, durations)
    return 0


if __name__ == "__main__":
    sys.exit(main())
