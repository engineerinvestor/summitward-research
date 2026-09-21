#!/usr/bin/env python3
"""Rolling and full-sample inflation betas for six assets, three CPI series, two shocks.

Every Summitward-calculated number in https://summitward.com/learn/inflation-beta
comes from this script, and the JSON it writes is the data behind the guide's
rolling inflation-beta explorer. It exists so those figures are auditable rather
than remembered.

The guide's claim is that an asset's "inflation beta" is a regression estimate
whose value depends on which inflation series is used, how the shock is
defined, the horizon of the returns and the sample. This script measures that
directly on free data, 1960 to the latest month, and prints the same asset's
beta under each choice side by side.

Assets (monthly total-return index levels, base 100):

* ``sp500``       S&P Composite, price plus one twelfth of the trailing
                  twelve-month dividend each month, from Shiller's file.
* ``treasury10``  A constant-maturity 10-year Treasury approximation: each
                  month a par bond bought at last month's GS10 yield is
                  repriced at this month's yield (semiannual coupons, ten
                  years to maturity) plus one month of coupon accrual. This is
                  the same construction Damodaran uses for his annual series.
                  It is an approximation, not an index.
* ``tbill``       Cash: last month's 3-month T-bill rate (FRED TB3MS,
                  secondary-market discount basis) divided by twelve.
* ``gold``        Gold spot, $/troy oz, World Bank Pink Sheet monthly average.
* ``commodities`` World Bank Total commodity price index, 2010 = 100.
* ``energy``      World Bank Energy price index, 2010 = 100.

The last three are spot prices. A collateralized futures position earns
collateral interest and a roll return that spot prices do not carry, so these
are not the return an investor in a commodity fund would have earned. The guide
says so where it quotes them.

Inflation series (FRED, seasonally adjusted, BLS): CPIAUCSL headline, CPILFESL
core (all items less food and energy), CPIENGSL energy.

Shock definitions:

* ``monthly``   The month's log change in the CPI, in percent, against the
                asset's monthly return in percent. One observation per month,
                classical standard errors.
* ``change12``  The change in trailing twelve-month inflation from a year
                earlier (this year's y/y CPI minus last year's y/y CPI), against
                the asset's trailing twelve-month return. This is the first of
                the two definitions AQR blends in "Inflation Redux?" and treats
                expectations as a random walk. Observations overlap eleven of
                twelve months, so standard errors are Newey-West with lag 11.

In both cases the slope is in return percentage points per percentage point of
the inflation measure, so a beta of 1 means the asset's return moved
one-for-one with the inflation shock over the sample, holding nothing else
constant.

Output:

* A printed table of full-sample beta, t-statistic, correlation and R^2 for
  every asset x series x definition, for the whole sample and for 1991-2018
  (the period in Vanguard's 2019 paper, for comparison), plus the S&P 500's
  headline beta by decade and a summary of each asset's 60-month rolling beta.
* ``output/inflation-beta-monthly.json``: month labels, the three CPI levels
  and the six asset index levels, which the browser explorer regresses
  itself. Values are index levels rounded to three decimals.

FRED series are downloaded on first run and cached under ``data/fred/`` so a
later run reproduces the published figures offline; pass ``--refresh`` to
re-download. Standard library only.

Usage:
    python3 inflation_beta.py
    python3 inflation_beta.py --refresh
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import urllib.request
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
FRED_DIR = DATA / "fred"
OUTPUT = HERE / "output" / "inflation-beta-monthly.json"

FRED_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={id}"
FRED_SERIES = {
    "CPIAUCSL": "headline",
    "CPILFESL": "core",
    "CPIENGSL": "energy",
    "TB3MS": "tbill_yield",
}

START = "1959-12"  # base month; first return is 1960-01
ASSETS = {
    "sp500": "S&P 500, total return",
    "treasury10": "10-year Treasury, constant-maturity approximation",
    "tbill": "3-month Treasury bills",
    "gold": "Gold, spot",
    "commodities": "Commodities, World Bank total index, spot",
    "energy": "Energy commodities, World Bank index, spot",
}
SERIES = ["headline", "core", "energy"]
WINDOWS = (36, 60, 120)


# ---------------------------------------------------------------- data loading


def fetch_fred(series_id: str, refresh: bool) -> dict[str, float]:
    FRED_DIR.mkdir(parents=True, exist_ok=True)
    path = FRED_DIR / f"{series_id}.csv"
    if refresh or not path.exists():
        req = urllib.request.Request(
            FRED_URL.format(id=series_id), headers={"User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            path.write_bytes(resp.read())
    out: dict[str, float] = {}
    with open(path, newline="") as fh:
        for row in csv.DictReader(fh):
            value = row.get(series_id) or row.get("value") or ""
            if value not in ("", "."):
                out[row["observation_date"][:7]] = float(value)
    return out


def load_csv(path: Path) -> dict[str, dict[str, float]]:
    table: dict[str, dict[str, float]] = {}
    with open(path, newline="") as fh:
        for row in csv.DictReader(fh):
            table[row["month"]] = {
                k: float(v) for k, v in row.items() if k != "month" and v != ""
            }
    return table


def month_range(first: str, last: str) -> list[str]:
    y, m = (int(x) for x in first.split("-"))
    ly, lm = (int(x) for x in last.split("-"))
    out = []
    while (y, m) <= (ly, lm):
        out.append(f"{y:04d}-{m:02d}")
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return out


# ------------------------------------------------------- asset index building


def bond_price(coupon_pct: float, yield_pct: float, years: int = 10) -> float:
    """Price per 100 face of a semiannual-coupon bond."""
    c = coupon_pct / 2.0
    r = yield_pct / 200.0
    n = years * 2
    if abs(r) < 1e-12:
        return c * n + 100.0
    return c * (1 - (1 + r) ** -n) / r + 100.0 * (1 + r) ** -n


def build_assets(
    months: list[str],
    shiller: dict[str, dict[str, float]],
    worldbank: dict[str, dict[str, float]],
    tbill_yield: dict[str, float],
) -> dict[str, list[float | None]]:
    levels: dict[str, list[float | None]] = {k: [None] * len(months) for k in ASSETS}

    def chain(key: str, i: int, gross: float | None) -> None:
        """Extend the index; a series starts at 100 in the month before its first return."""
        if gross is None:
            return
        prev = levels[key][i - 1]
        if prev is None:
            if any(v is not None for v in levels[key][:i]):
                return  # a gap after the series started; leave it broken
            prev = levels[key][i - 1] = 100.0
        levels[key][i] = prev * gross

    for i, m in enumerate(months):
        if i == 0:
            continue
        prev_m = months[i - 1]
        s0, s1 = shiller.get(prev_m, {}), shiller.get(m, {})
        # S&P 500 total return
        if "p" in s0 and "p" in s1 and "d" in s1:
            chain("sp500", i, (s1["p"] + s1["d"] / 12.0) / s0["p"])
        # 10-year Treasury approximation
        if "gs10" in s0 and "gs10" in s1:
            y0, y1 = s0["gs10"], s1["gs10"]
            chain("treasury10", i, 1 + y0 / 1200.0 + (bond_price(y0, y1) - 100.0) / 100.0)
        # T-bills
        if prev_m in tbill_yield:
            chain("tbill", i, 1 + tbill_yield[prev_m] / 1200.0)
        # Spot commodities and gold
        w0, w1 = worldbank.get(prev_m, {}), worldbank.get(m, {})
        for key, col in (("gold", "gold"), ("commodities", "total"), ("energy", "energy")):
            if col in w0 and col in w1 and w0[col]:
                chain(key, i, w1[col] / w0[col])
    return levels


# ------------------------------------------------------------------ statistics


def ols(x: list[float], y: list[float], nw_lag: int = 0) -> dict[str, float]:
    """Simple regression y = a + b x. Newey-West SE for the slope when nw_lag > 0."""
    n = len(x)
    mx, my = sum(x) / n, sum(y) / n
    sxx = sum((xi - mx) ** 2 for xi in x)
    syy = sum((yi - my) ** 2 for yi in y)
    sxy = sum((xi - mx) * (yi - my) for xi, yi in zip(x, y))
    beta = sxy / sxx
    alpha = my - beta * mx
    resid = [yi - alpha - beta * xi for xi, yi in zip(x, y)]
    sse = sum(e * e for e in resid)
    se_classical = math.sqrt(sse / (n - 2) / sxx)
    corr = sxy / math.sqrt(sxx * syy)
    r2 = corr * corr

    if nw_lag > 0:
        # Sandwich estimator with Bartlett weights on the 2x2 moment matrix.
        xtx_inv = _inv2([[n, sum(x)], [sum(x), sum(xi * xi for xi in x)]])
        u = [(e, e * xi) for xi, e in zip(x, resid)]
        s = [[0.0, 0.0], [0.0, 0.0]]
        for lag in range(0, nw_lag + 1):
            w = 1.0 if lag == 0 else 1.0 - lag / (nw_lag + 1.0)
            for i in range(lag, n):
                a, b = u[i], u[i - lag]
                for r in range(2):
                    for c in range(2):
                        term = a[r] * b[c]
                        s[r][c] += w * (term if lag == 0 else term + a[c] * b[r])
        v = _mul2(_mul2(xtx_inv, s), xtx_inv)
        se = math.sqrt(max(v[1][1], 0.0))
    else:
        se = se_classical

    return {
        "n": n,
        "alpha": alpha,
        "beta": beta,
        "se": se,
        "t": beta / se if se > 0 else float("nan"),
        "corr": corr,
        "r2": r2,
    }


def _inv2(m: list[list[float]]) -> list[list[float]]:
    det = m[0][0] * m[1][1] - m[0][1] * m[1][0]
    return [[m[1][1] / det, -m[0][1] / det], [-m[1][0] / det, m[0][0] / det]]


def _mul2(a: list[list[float]], b: list[list[float]]) -> list[list[float]]:
    return [
        [sum(a[r][k] * b[k][c] for k in range(2)) for c in range(2)] for r in range(2)
    ]


# ------------------------------------------------------------ shock and return


def shocks(cpi: list[float | None], definition: str) -> list[float | None]:
    out: list[float | None] = [None] * len(cpi)
    if definition == "monthly":
        for i in range(1, len(cpi)):
            a, b = cpi[i - 1], cpi[i]
            if a and b:
                out[i] = 100.0 * math.log(b / a)
        return out
    # change12: y/y inflation now minus y/y inflation twelve months ago
    yoy: list[float | None] = [None] * len(cpi)
    for i in range(12, len(cpi)):
        a, b = cpi[i - 12], cpi[i]
        if a and b:
            yoy[i] = 100.0 * (b / a - 1.0)
    for i in range(24, len(cpi)):
        if yoy[i] is not None and yoy[i - 12] is not None:
            out[i] = yoy[i] - yoy[i - 12]
    return out


def returns(levels: list[float | None], definition: str) -> list[float | None]:
    span = 1 if definition == "monthly" else 12
    out: list[float | None] = [None] * len(levels)
    for i in range(span, len(levels)):
        a, b = levels[i - span], levels[i]
        if a and b:
            out[i] = 100.0 * (b / a - 1.0)
    return out


def paired(
    x: list[float | None], y: list[float | None], months: list[str], first: str, last: str
) -> tuple[list[float], list[float]]:
    xs, ys = [], []
    for m, xi, yi in zip(months, x, y):
        if first <= m <= last and xi is not None and yi is not None:
            xs.append(xi)
            ys.append(yi)
    return xs, ys


def rolling_betas(
    x: list[float | None], y: list[float | None], window: int
) -> list[float | None]:
    out: list[float | None] = [None] * len(x)
    for end in range(window - 1, len(x)):
        xs, ys = [], []
        for i in range(end - window + 1, end + 1):
            if x[i] is not None and y[i] is not None:
                xs.append(x[i])
                ys.append(y[i])
        if len(xs) == window:
            out[end] = ols(xs, ys)["beta"]
    return out


# ------------------------------------------------------------------ reporting


def fmt(v: float, digits: int = 2) -> str:
    return f"{v:+.{digits}f}" if digits else f"{v:.0f}"


def print_table(
    title: str,
    months: list[str],
    cpi: dict[str, list[float | None]],
    assets: dict[str, list[float | None]],
    definition: str,
    first: str,
    last: str,
) -> None:
    lag = 11 if definition == "change12" else 0
    print(f"\n{title}")
    print(f"  shock = {definition}, sample {first} to {last}, "
          f"{'Newey-West lag 11' if lag else 'classical'} standard errors")
    head = f"  {'asset':<12}" + "".join(f"{s:>26}" for s in SERIES) + "     n"
    print(head)
    print(f"  {'':<12}" + "".join(f"{'beta (t)  corr    R2':>26}" for _ in SERIES))
    for key in ASSETS:
        ret = returns(assets[key], definition)
        cells = []
        n_obs = 0
        for series in SERIES:
            xs, ys = paired(shocks(cpi[series], definition), ret, months, first, last)
            if len(xs) < 24:
                cells.append(f"{'n/a':>26}")
                continue
            st = ols(xs, ys, lag)
            n_obs = st["n"]
            cells.append(
                f"{fmt(st['beta']):>7} ({fmt(st['t'], 1):>5}) {fmt(st['corr']):>6} {st['r2']:>6.3f}"
            )
        print(f"  {key:<12}" + "".join(cells) + f"  {n_obs:>4}")


def print_decades(months, cpi, assets) -> None:
    print("\nS&P 500 beta to headline CPI, monthly shock, by decade")
    ret = returns(assets["sp500"], "monthly")
    sh = shocks(cpi["headline"], "monthly")
    for start in range(1960, 2030, 10):
        first, last = f"{start}-01", f"{start + 9}-12"
        xs, ys = paired(sh, ret, months, first, last)
        if len(xs) < 24:
            continue
        st = ols(xs, ys)
        end_year = min(int(last[:4]), int(months[-1][:4]))
        print(
            f"  {first[:4]}-{end_year}: beta {fmt(st['beta'])} (t {fmt(st['t'], 1)}), "
            f"corr {fmt(st['corr'])}, n {st['n']}"
        )


def print_rolling_summary(months, cpi, assets, window: int, definition: str) -> None:
    print(f"\n{window}-month rolling beta, shock = {definition}: range, share negative, sign changes")
    for key in ASSETS:
        ret = returns(assets[key], definition)
        for series in ("headline", "core"):
            rb = rolling_betas(shocks(cpi[series], definition), ret, window)
            vals = [(m, v) for m, v in zip(months, rb) if v is not None]
            if not vals:
                continue
            lo = min(vals, key=lambda t: t[1])
            hi = max(vals, key=lambda t: t[1])
            neg = sum(1 for _, v in vals if v < 0) / len(vals)
            flips = sum(
                1 for (_, a), (_, b) in zip(vals, vals[1:]) if (a < 0) != (b < 0)
            )
            print(
                f"  {key:<12}{series:<9} min {fmt(lo[1]):>7} ({lo[0]})  max {fmt(hi[1]):>7} ({hi[0]})"
                f"  negative {neg:5.1%}  sign changes {flips:>3}  windows {len(vals)}"
            )


# ----------------------------------------------------------------------- main


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--refresh", action="store_true", help="re-download FRED series")
    args = parser.parse_args()

    fred = {name: fetch_fred(sid, args.refresh) for sid, name in FRED_SERIES.items()}
    shiller = load_csv(DATA / "shiller_monthly.csv")
    worldbank = load_csv(DATA / "worldbank_pink_sheet_monthly.csv")

    last = max(fred["headline"])
    months = month_range(START, last)
    cpi = {s: [fred[s].get(m) for m in months] for s in SERIES}
    assets = build_assets(months, shiller, worldbank, fred["tbill_yield"])

    ends = {k: max(m for m, v in zip(months, assets[k]) if v is not None) for k in ASSETS}
    print(f"Sample: {months[1]} to {last} (CPI). Asset series end: "
          + ", ".join(f"{k} {v}" for k, v in ends.items()))

    for definition in ("monthly", "change12"):
        print_table("Full sample", months, cpi, assets, definition, "1960-01", last)
        print_table("Vanguard (2019) comparison period", months, cpi, assets, definition,
                    "1991-01", "2018-12")
    print_decades(months, cpi, assets)
    print_rolling_summary(months, cpi, assets, 60, "monthly")
    print_rolling_summary(months, cpi, assets, 60, "change12")

    meta = {
        "generated": date.today().isoformat(),
        "guide": "https://summitward.com/learn/inflation-beta",
        "script": "https://github.com/engineerinvestor/summitward-research/tree/main/inflation-beta",
        "months": f"{months[0]} to {months[-1]}",
        "cpi": {
            "source": "FRED, BLS CPI-U seasonally adjusted: CPIAUCSL (headline), CPILFESL (core), CPIENGSL (energy)",
            "licence": "US government work, public domain; citation requested",
            "last_observation": last,
        },
        "assets": {
            "sp500": {
                "label": ASSETS["sp500"],
                "source": "Robert J. Shiller, ie_data.xls: monthly average price plus one twelfth of trailing twelve-month dividends",
                "last": ends["sp500"],
            },
            "treasury10": {
                "label": ASSETS["treasury10"],
                "source": "Shiller GS10 yield; par 10-year semiannual bond repriced monthly plus coupon accrual (approximation)",
                "last": ends["treasury10"],
            },
            "tbill": {
                "label": ASSETS["tbill"],
                "source": "FRED TB3MS, prior month's rate divided by twelve",
                "last": ends["tbill"],
            },
            "gold": {
                "label": ASSETS["gold"],
                "source": "World Bank Pink Sheet, gold $/troy oz, monthly average (CC BY 4.0)",
                "last": ends["gold"],
            },
            "commodities": {
                "label": ASSETS["commodities"],
                "source": "World Bank Pink Sheet, Total index 2010=100, spot (CC BY 4.0)",
                "last": ends["commodities"],
            },
            "energy": {
                "label": ASSETS["energy"],
                "source": "World Bank Pink Sheet, Energy index 2010=100, spot (CC BY 4.0)",
                "last": ends["energy"],
            },
        },
        "notes": [
            "Index levels, base 100 at the first month. Regress monthly or trailing 12-month percent changes on the matching CPI change to reproduce the guide's betas.",
            "Commodity and gold series are spot prices, not collateralized futures returns.",
            "The 10-year Treasury series is a yield-based approximation, not a bond index.",
        ],
    }
    payload = {
        "_metadata": meta,
        "months": months,
        "cpi": {s: [round(v, 3) if v is not None else None for v in cpi[s]] for s in SERIES},
        "assets": {
            k: {
                "label": ASSETS[k],
                "values": [round(v, 3) if v is not None else None for v in assets[k]],
            }
            for k in ASSETS
        },
    }
    OUTPUT.parent.mkdir(exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, separators=(",", ":")) + "\n")
    print(f"\nwrote {OUTPUT} ({OUTPUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
