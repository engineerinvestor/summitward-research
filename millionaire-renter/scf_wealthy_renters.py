"""How many wealthy U.S. families rent, and who are they? 2025 and 2022 SCF.

Supports https://summitward.com/learn/millionaire-renter.

Data: Federal Reserve Survey of Consumer Finances public summary extract
(SCFP2025.csv, SCFP2022.csv) and the matching bootstrap replicate-weight files
(p25_rw1.dta, p22_rw1.dta), downloaded from
https://www.federalreserve.gov/econres/scfindex.htm into .cache/ on first run.

Definitions (variable names from the Fed's bulletin.macro.txt):
  owner       HOUSECL == 1 (owns the primary residence, including farm/ranch,
              mobile home, condo or co-op)
  non-owner   HOUSECL == 2 (the Fed's "renter or other": renters plus families
              living rent-free, e.g. with relatives or in employer housing)
  renter      HOUSECL == 2 and RENT > 0 (pays monthly rent)
  net worth   NETWORTH = ASSET - DEBT
  ex-home     NETWORTH - HOMEEQ (net worth less primary-residence equity)
  financial   FIN (financial assets: transaction accounts, CDs, bonds, stocks,
              funds, retirement accounts, cash-value life insurance, other)

Dollar amounts: the Fed distributes both extracts on the 2025 page already
inflation-adjusted to 2025 dollars, so no further conversion is applied. Check:
the 2022 extract's weighted median net worth comes out at $210,200, against
$211,100 (2025 dollars) in Table 2 of the Fed's October 2026 report and $192,900
(2022 dollars) in the 2023 Bulletin.

Estimation: shares and medians are computed on each of the five implicates
with WGT and averaged. Standard errors combine bootstrap sampling variance
(999 replicate weights wt1b{k} * mm{k}, first implicate, as in the Fed's
MEANIT macro and the scfcombo Stata module) with imputation variance across
implicates times (1 + 1/5). Cells with fewer than MIN_N sample families are
suppressed. The SCF excludes the Forbes 400 by design.

Run:  python3 scf_wealthy_renters.py   (needs pandas)
Writes output/scf-wealthy-renters.json and prints the tables quoted in the guide.
"""

from __future__ import annotations

import json
import sys
import urllib.request
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
CACHE = HERE / ".cache"
OUT = HERE / "output"
BASE = "https://www.federalreserve.gov/econres/files/"
FILES = {
    2025: ("scfp2025excel.zip", "SCFP2025.csv", "scf2025rw1s.zip", "p25_rw1.dta"),
    2022: ("scfp2022excel.zip", "SCFP2022.csv", "scf2022rw1s.zip", "p22_rw1.dta"),
}
ASSET_FACTOR = {2025: 1.0, 2022: 1.0}  # extracts already in 2025 dollars
THRESHOLDS = [1_000_000, 3_000_000, 5_000_000, 10_000_000]
MIN_N = 50
COLS = [
    "Y1", "YY1", "WGT", "AGE", "MARRIED", "KIDS", "HOUSECL", "RENT", "INCOME",
    "NETWORTH", "HOMEEQ", "HOUSES", "FIN", "EQUITY", "HBUS", "BUS",
    "HRETQLIQ", "ORESRE", "NNRESRE", "LF", "EDCL",
]  # fmt: skip


def fetch(name: str) -> Path:
    CACHE.mkdir(exist_ok=True)
    path = CACHE / name
    if not path.exists():
        req = urllib.request.Request(BASE + name, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req) as r:
            path.write_bytes(r.read())
    return path


def load(year: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    zext, csv, zrw, dta = FILES[year]
    with zipfile.ZipFile(fetch(zext)) as z, z.open(csv) as f:
        d = pd.read_csv(f, usecols=COLS)
    with zipfile.ZipFile(fetch(zrw)) as z, z.open(dta) as f:
        rw = pd.read_stata(f)
    rw.columns = [c.lower() for c in rw.columns]
    rw = rw.fillna(0.0)
    reps = np.column_stack(
        [rw[f"wt1b{k}"].to_numpy() * rw[f"mm{k}"].to_numpy() for k in range(1, 1000)]
    )
    rwdf = pd.DataFrame(reps, index=rw["y1"].astype(int).to_numpy())
    d["imp"] = d["Y1"] - 10 * d["YY1"]
    d["owner"] = d["HOUSECL"] == 1
    d["nonowner"] = d["HOUSECL"] == 2
    d["renter"] = d["nonowner"] & (d["RENT"] > 0)
    d["networth_ex_home"] = d["NETWORTH"] - d["HOMEEQ"]
    d["has_other_re"] = (d["ORESRE"] + d["NNRESRE"]) > 0
    d["equity_share"] = np.where(
        d["FIN"] > 0, d["EQUITY"] / d["FIN"].where(d["FIN"] > 0, 1), np.nan
    )
    return d, rwdf


def wshare(num: np.ndarray, den: np.ndarray, w: np.ndarray) -> float:
    tot = (w * den).sum()
    return float((w * num * den).sum() / tot) if tot > 0 else float("nan")


def wmedian(x: np.ndarray, w: np.ndarray) -> float:
    m = ~np.isnan(x) & (w > 0)
    x, w = x[m], w[m]
    if len(x) == 0:
        return float("nan")
    o = np.argsort(x)
    cw = np.cumsum(w[o])
    return float(x[o][np.searchsorted(cw, cw[-1] / 2)])


def share_with_se(d: pd.DataFrame, rw: pd.DataFrame, num: str, mask: pd.Series) -> dict:
    """Weighted share of `num` among rows in `mask`, with SCF standard errors."""
    ests, ns = [], []
    for i in range(1, 6):
        s = d[d["imp"] == i]
        m = mask[s.index].to_numpy()
        ests.append(wshare(s[num].to_numpy(), m, s["WGT"].to_numpy()))
        ns.append(int(m.sum()))
    point = float(np.mean(ests))
    s1 = d[d["imp"] == 1]
    m1 = mask[s1.index].to_numpy().astype(float)
    y1 = s1[num].to_numpy().astype(float)
    W = rw.loc[s1["Y1"].to_numpy()].to_numpy()  # families x 999
    den = (W * m1[:, None]).sum(axis=0)
    with np.errstate(invalid="ignore", divide="ignore"):
        reps = (W * (m1 * y1)[:, None]).sum(axis=0) / den
    reps = reps[np.isfinite(reps)]
    v_samp = float(np.mean((reps - ests[0]) ** 2))
    v_imp = float(np.var(ests, ddof=1))
    se = float(np.sqrt(v_samp + 1.2 * v_imp))
    n = int(round(np.mean(ns)))
    return {"share": point, "se": se, "n": n, "suppressed": n < MIN_N}


def median_by_imp(d: pd.DataFrame, col: str, mask: pd.Series) -> float:
    vals = []
    for i in range(1, 6):
        s = d[(d["imp"] == i) & mask]
        vals.append(wmedian(s[col].to_numpy(dtype=float), s["WGT"].to_numpy()))
    return float(np.mean(vals))


def mean_flag(d: pd.DataFrame, col: str, mask: pd.Series) -> float:
    vals = []
    for i in range(1, 6):
        s = d[(d["imp"] == i) & mask]
        vals.append(
            float(np.average(s[col].astype(float), weights=s["WGT"]))
            if len(s)
            else np.nan
        )
    return float(np.mean(vals))


def families(d: pd.DataFrame, mask: pd.Series) -> float:
    """Weighted family count (millions). WGT is already divided by 5, so the
    sum over all five implicates estimates the population total."""
    return float(d.loc[mask, "WGT"].sum() / 1e6)


def analyze(year: int) -> dict:
    d, rw = load(year)
    f = ASSET_FACTOR[year]
    every = pd.Series(True, index=d.index)
    res: dict = {
        "year": year,
        "families_m": families(d, every),
        "own_rate": share_with_se(d, rw, "owner", every),
        "renter_rate": share_with_se(d, rw, "renter", every),
        "median_networth": median_by_imp(d, "NETWORTH", every) * f,
        "by_threshold": {},
    }
    measures = {
        "networth": "NETWORTH",
        "networth_ex_home": "networth_ex_home",
        "financial": "FIN",
    }
    for key, col in measures.items():
        rows = []
        for t in THRESHOLDS:
            mask = d[col] >= t / f
            rows.append(
                {
                    "threshold": t,
                    "families_m": families(d, mask),
                    "nonowner": share_with_se(d, rw, "nonowner", mask),
                    "renter": share_with_se(d, rw, "renter", mask),
                }
            )
        res["by_threshold"][key] = rows
    for t in THRESHOLDS:
        d[f"nw_ge_{t}"] = d["NETWORTH"] >= t / f
    res["share_families_nw_ge_1m"] = share_with_se(
        d, rw, f"nw_ge_{THRESHOLDS[0]}", every
    )

    if year == 2025:
        # Profile at net worth >= $1M: renters vs owners.
        mill = d["NETWORTH"] >= 1_000_000
        prof = {}
        for grp in ["renter", "nonowner", "owner"]:
            m = mill & d[grp]
            prof[grp] = {
                "n": int(round(m.sum() / 5)),
                "families_m": families(d, m),
                "median_age": median_by_imp(d, "AGE", m),
                "median_income": median_by_imp(d, "INCOME", m),
                "median_networth": median_by_imp(d, "NETWORTH", m),
                "median_financial": median_by_imp(d, "FIN", m),
                "median_equity_share_of_financial": median_by_imp(d, "equity_share", m),
                "share_owns_business": mean_flag(d, "HBUS", m),
                "share_has_retirement_account": mean_flag(d, "HRETQLIQ", m),
                "share_owns_other_real_estate": mean_flag(d, "has_other_re", m),
                "share_married": mean_flag(d.assign(_m=(d["MARRIED"] == 1)), "_m", m),
                "share_with_kids": mean_flag(d.assign(_k=(d["KIDS"] > 0)), "_k", m),
                "share_under_45": mean_flag(d.assign(_a=(d["AGE"] < 45)), "_a", m),
                "share_65_plus": mean_flag(d.assign(_a=(d["AGE"] >= 65)), "_a", m),
            }
        res["profile_networth_ge_1m"] = prof

        # Renter share by age among $1M+ (net worth) and $1M+ (financial assets).
        ages = {
            "under_45": d["AGE"] < 45,
            "45_to_64": (d["AGE"] >= 45) & (d["AGE"] < 65),
            "65_plus": d["AGE"] >= 65,
        }
        res["by_age"] = {}
        for key, col in measures.items():
            res["by_age"][key] = {
                a: {
                    "nonowner": share_with_se(
                        d, rw, "nonowner", (d[col] >= 1_000_000) & am
                    ),
                    "renter": share_with_se(
                        d, rw, "renter", (d[col] >= 1_000_000) & am
                    ),
                }
                for a, am in ages.items()
            }

        # Married with children under the household, under 55, $3M+ financial assets.
        fam = (d["MARRIED"] == 1) & (d["KIDS"] > 0) & (d["AGE"] < 55)
        res["married_kids_under55_fin_ge_3m"] = {
            "nonowner": share_with_se(d, rw, "nonowner", fam & (d["FIN"] >= 3_000_000)),
            "renter": share_with_se(d, rw, "renter", fam & (d["FIN"] >= 3_000_000)),
        }
        res["married_kids_under55_fin_ge_1m"] = {
            "nonowner": share_with_se(d, rw, "nonowner", fam & (d["FIN"] >= 1_000_000)),
            "renter": share_with_se(d, rw, "renter", fam & (d["FIN"] >= 1_000_000)),
        }
        # Of all non-owners with net worth >= $1M, what share pay rent.
        res["renters_among_nonowners_nw_ge_1m"] = share_with_se(
            d, rw, "renter", mill & d["nonowner"]
        )
    return res


def pct(c: dict) -> str:
    if c["suppressed"]:
        return f"  (n={c['n']}, suppressed)"
    lo, hi = c["share"] - 1.96 * c["se"], c["share"] + 1.96 * c["se"]
    return f"{100 * c['share']:5.1f}%  [{100 * max(lo, 0):4.1f}, {100 * hi:4.1f}]  n={c['n']}"


def main() -> int:
    OUT.mkdir(exist_ok=True)
    results = {y: analyze(y) for y in (2025, 2022)}
    for y, r in results.items():
        print(f"\n=== SCF {y} ===  families {r['families_m']:.1f}M")
        print(f"own primary residence: {pct(r['own_rate'])}")
        print(f"pays rent: {pct(r['renter_rate'])}")
        print(f"median net worth (2025$): {r['median_networth']:,.0f}")
        print(
            f"share of families with net worth >= $1M (2025$): {pct(r['share_families_nw_ge_1m'])}"
        )
        for key, rows in r["by_threshold"].items():
            print(
                f"\n  {key} (2025$)   families    non-owner                        renter (pays rent)"
            )
            for row in rows:
                print(
                    f"  >= ${row['threshold'] / 1e6:>4.0f}M   {row['families_m']:6.2f}M   {pct(row['nonowner'])}   {pct(row['renter'])}"
                )
    r = results[2025]
    print("\n=== 2025 profile, net worth >= $1M ===")
    for grp, p in r["profile_networth_ge_1m"].items():
        print(
            f"  {grp}: "
            + ", ".join(
                f"{k}={v:,.3f}" if isinstance(v, float) else f"{k}={v}"
                for k, v in p.items()
            )
        )
    print("\n=== 2025 by age, >= $1M ===")
    for key, ages in r["by_age"].items():
        for a, c in ages.items():
            print(
                f"  {key:18s} {a:9s} non-owner {pct(c['nonowner'])}   renter {pct(c['renter'])}"
            )
    for k in ("married_kids_under55_fin_ge_1m", "married_kids_under55_fin_ge_3m"):
        c = r[k]
        print(f"\n  {k}: non-owner {pct(c['nonowner'])}   renter {pct(c['renter'])}")
    print(
        f"\n  renters among non-owners, nw >= $1M: {pct(r['renters_among_nonowners_nw_ge_1m'])}"
    )

    def clean(o):
        if isinstance(o, dict):
            return {str(k): clean(v) for k, v in o.items() if v is not None}
        if isinstance(o, list):
            return [clean(v) for v in o]
        if isinstance(o, float):
            return round(o, 6)
        return o

    path = OUT / "scf-wealthy-renters.json"
    path.write_text(json.dumps(clean(results), indent=2) + "\n")
    print(f"\nWrote {path.relative_to(HERE)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
