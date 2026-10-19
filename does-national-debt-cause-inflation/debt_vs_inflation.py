"""Does a high public-debt level predict inflation? JST Macrohistory, 1870-2020.

For each country-year t we compare public debt/GDP at t (a stock) and the
government deficit at t (a flow) with average annual CPI inflation over the
next five years, t to t+5. Results are descriptive: overlapping windows,
countries clustered, no causal claim.

    python3 debt_vs_inflation.py            # prints the tables
    python3 debt_vs_inflation.py --json     # also writes output/debt_vs_inflation.json

Data: Jorda-Schularick-Taylor Macrohistory Database, release 6
(https://www.macrohistory.net/database/). Run fetch_data.sh first; the file is
not redistributed here (see README).
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).parent
JST = HERE / ".cache" / "JSTdatasetR6.dta"
HORIZON = 5

DEBT_BUCKETS = [(0, 30), (30, 60), (60, 90), (90, 1000)]
DEFICIT_BUCKETS = [(-1000, 0), (0, 3), (3, 6), (6, 1000)]
ERAS = [
    ("1870-1913 gold standard", 1870, 1913),
    ("1914-1945 wars and interwar", 1914, 1945),
    ("1946-1972 Bretton Woods", 1946, 1972),
    ("1973-1990 floating, high inflation", 1973, 1990),
    ("1991-2015 inflation targeting", 1991, 2015),
]
WAR_YEARS = set(range(1914, 1919)) | set(range(1939, 1946))


def load() -> pd.DataFrame:
    d = pd.read_stata(JST)[
        ["country", "iso", "year", "debtgdp", "cpi", "revenue", "expenditure", "gdp"]
    ].copy()
    d["year"] = d["year"].astype(int)
    d = d.sort_values(["iso", "year"])
    d["debt_pct"] = 100 * d["debtgdp"]
    d["deficit_pct"] = 100 * (d["expenditure"] - d["revenue"]) / d["gdp"]
    # Forward average annual inflation, t to t+HORIZON, only where both CPI
    # observations exist exactly HORIZON years apart.
    fwd = d.groupby("iso")[["year", "cpi"]].shift(-HORIZON)
    ok = fwd["year"] == d["year"] + HORIZON
    d["fwd_infl"] = np.where(
        ok, 100 * ((fwd["cpi"] / d["cpi"]) ** (1 / HORIZON) - 1), np.nan
    )
    d["war"] = d["year"].isin(WAR_YEARS)
    return d


def bucket_table(d: pd.DataFrame, col: str, buckets) -> list[dict]:
    rows = []
    for lo, hi in buckets:
        s = d[(d[col] >= lo) & (d[col] < hi)]["fwd_infl"].dropna()
        if s.empty:
            continue
        rows.append(
            {
                "bucket": f"{lo}-{hi}" if hi < 1000 else f">={lo}",
                "n": int(s.size),
                "countries": int(d.loc[s.index, "iso"].nunique()),
                "median": round(float(s.median()), 2),
                "p25": round(float(s.quantile(0.25)), 2),
                "p75": round(float(s.quantile(0.75)), 2),
                "share_above_10": round(float((s > 10).mean()), 3),
            }
        )
    return rows


def within_country_slope(d: pd.DataFrame, col: str) -> dict:
    """OLS slope of forward inflation on col after removing country means.

    Reported with a crude cluster-by-country standard error. Descriptive only.
    """
    s = d[["iso", col, "fwd_infl"]].dropna()
    s = s[np.isfinite(s[col])]
    if len(s) < 30:
        return {}
    x = s[col] - s.groupby("iso")[col].transform("mean")
    y = s["fwd_infl"] - s.groupby("iso")["fwd_infl"].transform("mean")
    beta = float((x * y).sum() / (x * x).sum())
    resid = y - beta * x
    meat = sum(
        float((x[g] * resid[g]).sum()) ** 2 for g in s.groupby("iso").groups.values()
    )
    se = (meat**0.5) / float((x * x).sum())
    return {
        "beta_pp_per_10pt": round(10 * beta, 3),
        "se_pp_per_10pt": round(10 * se, 3),
        "n": int(len(s)),
        "countries": int(s["iso"].nunique()),
    }


def main() -> None:
    d = load()
    out = {"horizon_years": HORIZON, "eras": {}}
    peace = d[~d["war"]]

    print(f"Forward window: {HORIZON} years. Inflation = avg annual CPI change.\n")
    blocks = [("All years, 1870-2015", d), ("Excluding war years", peace)]
    blocks += [(name, d[(d.year >= lo) & (d.year <= hi)]) for name, lo, hi in ERAS]
    for name, sub in blocks:
        res = {
            "by_debt": bucket_table(sub, "debt_pct", DEBT_BUCKETS),
            "by_deficit": bucket_table(sub, "deficit_pct", DEFICIT_BUCKETS),
            "slope_debt": within_country_slope(sub, "debt_pct"),
            "slope_deficit": within_country_slope(sub, "deficit_pct"),
        }
        out["eras"][name] = res
        print(f"== {name}")
        for key, label in [("by_debt", "debt/GDP %"), ("by_deficit", "deficit/GDP %")]:
            print(
                f"  {label:14s} {'n':>5s} {'ctry':>4s} {'median':>7s} "
                f"{'p25':>6s} {'p75':>6s} {'>10%':>6s}"
            )
            for r in res[key]:
                print(
                    f"  {r['bucket']:14s} {r['n']:5d} {r['countries']:4d} "
                    f"{r['median']:7.2f} {r['p25']:6.2f} {r['p75']:6.2f} "
                    f"{r['share_above_10']:6.1%}"
                )
        for key in ("slope_debt", "slope_deficit"):
            r = res[key]
            if r:
                print(
                    f"  within-country {key[6:]}: {r['beta_pp_per_10pt']:+.2f}pp "
                    f"per 10 pts (cluster SE {r['se_pp_per_10pt']:.2f}), n={r['n']}"
                )
        print()

    # Countries and years with the highest debt, and what followed.
    top = (
        d.dropna(subset=["debt_pct", "fwd_infl"])
        .query("not war")
        .sort_values("debt_pct", ascending=False)
        .drop_duplicates("iso")
        .head(18)[["country", "year", "debt_pct", "deficit_pct", "fwd_infl"]]
    )
    print("Peak peacetime debt year per country, and the next five years' inflation:")
    print(top.round(1).to_string(index=False))
    out["peak_debt_by_country"] = top.round(2).to_dict(orient="records")

    if "--json" in sys.argv:
        (HERE / "output").mkdir(exist_ok=True)
        (HERE / "output" / "debt_vs_inflation.json").write_text(
            json.dumps(out, indent=2)
        )


if __name__ == "__main__":
    main()
