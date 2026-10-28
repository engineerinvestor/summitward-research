"""Wealth of employee-headed vs self-employed-headed families, 2025 and 2022 SCF.

Supports https://summitward.com/learn/are-w2-jobs-a-scam.

Data: Federal Reserve Survey of Consumer Finances public summary extract
(SCFP2025.csv, SCFP2022.csv) and the matching bootstrap replicate-weight files
(p25_rw1.dta, p22_rw1.dta), downloaded from
https://www.federalreserve.gov/econres/scfindex.htm into .cache/ on first run.
Both extracts on the 2025 page are in 2025 dollars.

Definitions (variable names from the Fed's bulletin.macro.txt):
  work status  OCCAT1 of the family's reference person: 1 works for someone
               else, 2 self-employed or partnership, 3 retired / disabled /
               student / homemaker / not in labor force, 4 other not working.
               Spouses are not classified, so a family headed by an employee
               can still own a business run by the spouse.
  net worth    NETWORTH = ASSET - DEBT
  ex-business  NETWORTH - BUS (net worth less the value of privately held
               businesses, actively and non-actively managed)
  financial    FIN (transaction accounts, CDs, bonds, stocks, funds,
               retirement accounts, cash-value life insurance, other)
  stock owner  EQUITY > 0 (publicly traded stock held directly, in funds or in
               retirement accounts)
  income pct   INCCAT: 1 = below 20th percentile ... 5 = 80th-89.9th,
               6 = 90th-100th

Estimation: statistics are computed on each of the five implicates with WGT
and averaged. Standard errors combine bootstrap sampling variance (999
replicate weights wt1b{k} * mm{k}, first implicate, as in the Fed's MEANIT
macro) with imputation variance across implicates times (1 + 1/5). Cells
with fewer than MIN_N sample families are suppressed. The SCF excludes the
Forbes 400 by design.

This is a cross-section. It describes who holds wealth today; it does not
measure what choosing self-employment does to a given person's wealth.
People who start businesses and fail mostly go back to working for someone
else, so they are counted with the employees.

Run:  python3 scf_wealth_by_work_status.py   (needs numpy, pandas)
Writes output/scf-wealth-by-work-status.json and prints the tables quoted in
the guide.
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
MIN_N = 50
COLS = [
    "Y1", "YY1", "WGT", "AGE", "OCCAT1", "INCOME", "INCCAT", "NETWORTH",
    "FIN", "EQUITY", "HBUS", "BUS",
]  # fmt: skip
GROUPS = {"employee": 1, "self_employed": 2, "retired_or_nilf": 3, "other": 4}
AGE_BANDS = [(25, 34), (35, 44), (45, 54), (55, 64)]
THRESHOLDS = [1_000_000, 3_000_000, 10_000_000]
# Published checks: Fed historical tables (scf2025_tables_internal_real_historical
# .xlsx), median net worth and income by work status, thousands of 2025 dollars.
FED_CHECK = {
    2025: {
        "employee": {"nw": 156.0, "inc": 95.7},
        "self_employed": {"nw": 574.6, "inc": 93.5},
    },
    2022: {
        "employee": {"nw": 170.4, "inc": 94.6},
        "self_employed": {"nw": 488.5, "inc": 88.7},
    },
}


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
    d["nw_ex_bus"] = d["NETWORTH"] - d["BUS"]
    d["owns_stock"] = d["EQUITY"] > 0
    d["owns_bus"] = d["HBUS"] == 1
    for t in THRESHOLDS:
        d[f"nw_ge_{t}"] = d["NETWORTH"] >= t
    for name, code in GROUPS.items():
        d[f"is_{name}"] = d["OCCAT1"] == code
    return d, rwdf


def wmedian(x: np.ndarray, w: np.ndarray) -> float:
    m = ~np.isnan(x) & (w > 0)
    x, w = x[m], w[m]
    if len(x) == 0:
        return float("nan")
    o = np.argsort(x)
    cw = np.cumsum(w[o])
    return float(x[o][np.searchsorted(cw, cw[-1] / 2)])


def rep_medians(x: np.ndarray, W: np.ndarray) -> np.ndarray:
    """Weighted median of x under each replicate weight column of W."""
    o = np.argsort(x)
    xs, cw = x[o], np.cumsum(W[o], axis=0)
    idx = (cw < cw[-1] / 2).sum(axis=0)
    return xs[np.minimum(idx, len(xs) - 1)]


def combine(ests: list[float], reps: np.ndarray, ns: list[int]) -> dict:
    reps = reps[np.isfinite(reps)]
    v_samp = float(np.mean((reps - ests[0]) ** 2))
    v_imp = float(np.var(ests, ddof=1))
    n = int(round(np.mean(ns)))
    return {
        "est": float(np.mean(ests)),
        "se": float(np.sqrt(v_samp + 1.2 * v_imp)),
        "n": n,
        "suppressed": n < MIN_N,
    }


def share(d: pd.DataFrame, rw: pd.DataFrame, num: str, mask: pd.Series) -> dict:
    """Weighted share of boolean `num` among families in `mask`."""
    ests, ns = [], []
    for i in range(1, 6):
        s = d[(d["imp"] == i) & mask]
        w = s["WGT"].to_numpy()
        ests.append(float((w * s[num].to_numpy()).sum() / w.sum()))
        ns.append(len(s))
    s1 = d[(d["imp"] == 1) & mask]
    W = rw.loc[s1["Y1"].to_numpy()].to_numpy()
    y = s1[num].to_numpy().astype(float)
    with np.errstate(invalid="ignore", divide="ignore"):
        reps = (W * y[:, None]).sum(axis=0) / W.sum(axis=0)
    return combine(ests, reps, ns)


def median(d: pd.DataFrame, rw: pd.DataFrame, col: str, mask: pd.Series) -> dict:
    ests, ns = [], []
    for i in range(1, 6):
        s = d[(d["imp"] == i) & mask]
        ests.append(wmedian(s[col].to_numpy(dtype=float), s["WGT"].to_numpy()))
        ns.append(len(s))
    s1 = d[(d["imp"] == 1) & mask]
    W = rw.loc[s1["Y1"].to_numpy()].to_numpy()
    reps = rep_medians(s1[col].to_numpy(dtype=float), W)
    return combine(ests, reps, ns)


def composition(d: pd.DataFrame, rw: pd.DataFrame, mask: pd.Series) -> dict:
    """Share of families in `mask` headed by each work-status group, plus the
    weighted family count (millions; WGT sums to the population over the five
    implicates)."""
    out = {g: share(d, rw, f"is_{g}", mask) for g in GROUPS}
    out["families_millions"] = float(d.loc[mask, "WGT"].sum() / 1e6)
    return out


def analyze(year: int) -> dict:
    d, rw = load(year)
    every = pd.Series(True, index=d.index)
    res: dict = {"year": year, "all": {}, "by_age": {}, "rich": {}, "emp_income": {}}

    res["all"]["composition"] = composition(d, rw, every)
    for g in ("employee", "self_employed"):
        m = d[f"is_{g}"]
        res["all"][g] = {
            "median_networth": median(d, rw, "NETWORTH", m),
            "median_nw_ex_business": median(d, rw, "nw_ex_bus", m),
            "median_financial": median(d, rw, "FIN", m),
            "median_income": median(d, rw, "INCOME", m),
            "median_age": median(d, rw, "AGE", m),
            "owns_business": share(d, rw, "owns_bus", m),
            "owns_stock": share(d, rw, "owns_stock", m),
            **{f"nw_ge_{t}": share(d, rw, f"nw_ge_{t}", m) for t in THRESHOLDS},
        }

    for lo, hi in AGE_BANDS:
        band = (d["AGE"] >= lo) & (d["AGE"] <= hi)
        key = f"{lo}-{hi}"
        res["by_age"][key] = {}
        for g in ("employee", "self_employed"):
            m = band & d[f"is_{g}"]
            res["by_age"][key][g] = {
                "median_networth": median(d, rw, "NETWORTH", m),
                "median_nw_ex_business": median(d, rw, "nw_ex_bus", m),
                "median_financial": median(d, rw, "FIN", m),
                "median_income": median(d, rw, "INCOME", m),
                "nw_ge_1000000": share(d, rw, "nw_ge_1000000", m),
            }

    for t in THRESHOLDS:
        res["rich"][f"nw_ge_{t}"] = composition(d, rw, d[f"nw_ge_{t}"])

    emp = d["is_employee"]
    for cat, label in [(4, "p60-80"), (5, "p80-90"), (6, "p90-100")]:
        m = emp & (d["INCCAT"] == cat)
        res["emp_income"][label] = {
            "nw_ge_1000000": share(d, rw, "nw_ge_1000000", m),
            "median_networth": median(d, rw, "NETWORTH", m),
        }
    return res


def k(c: dict) -> str:
    if c["suppressed"]:
        return "   (n<50)"
    return f"{c['est'] / 1e3:8,.1f}k ±{1.96 * c['se'] / 1e3:,.1f}"


def pct(c: dict) -> str:
    if c["suppressed"]:
        return "(n<50)"
    return f"{100 * c['est']:5.1f}% ±{196 * c['se']:.1f} (n={c['n']})"


def report(r: dict) -> None:
    y = r["year"]
    print(f"\n===== {y} SCF (2025 dollars; ± is a 95% interval) =====")
    comp = r["all"]["composition"]
    print("Share of all families by head's work status:")
    for g in GROUPS:
        print(f"  {g:16s} {pct(comp[g])}")
    print("\nAll ages            employee                  self-employed")
    rows = [
        ("median net worth", "median_networth"),
        ("median NW ex-bus", "median_nw_ex_business"),
        ("median financial", "median_financial"),
        ("median income", "median_income"),
    ]
    e, s = r["all"]["employee"], r["all"]["self_employed"]
    for label, key in rows:
        print(f"  {label:17s} {k(e[key]):24s} {k(s[key])}")
    print(
        f"  median age        {e['median_age']['est']:.0f}  {s['median_age']['est']:>24.0f}"
    )
    for key, label in [
        ("owns_business", "owns a business"),
        ("owns_stock", "owns stock"),
    ]:
        print(f"  {label:17s} {pct(e[key]):24s} {pct(s[key])}")
    for t in THRESHOLDS:
        key = f"nw_ge_{t}"
        print(f"  NW >= ${t / 1e6:.0f}M       {pct(e[key]):24s} {pct(s[key])}")
    chk = FED_CHECK[y]
    print(
        f"  Fed check: employee NW {chk['employee']['nw']}k inc {chk['employee']['inc']}k;"
        f" self-employed NW {chk['self_employed']['nw']}k inc {chk['self_employed']['inc']}k"
    )

    print("\nBy age band")
    for band, v in r["by_age"].items():
        print(f"  {band}")
        for label, key in rows:
            print(
                f"    {label:17s} {k(v['employee'][key]):24s} {k(v['self_employed'][key])}"
            )
        print(
            f"    {'NW >= $1M':17s} {pct(v['employee']['nw_ge_1000000']):24s}"
            f" {pct(v['self_employed']['nw_ge_1000000'])}"
        )

    print("\nWho heads wealthy families")
    for key, comp in r["rich"].items():
        print(f"  {key} ({comp['families_millions']:.1f}M families)")
        for g in GROUPS:
            mill = comp["families_millions"] * comp[g]["est"]
            print(f"    {g:16s} {pct(comp[g])}  ~{mill:.1f}M families")

    print("\nEmployee-headed families by income percentile")
    for label, v in r["emp_income"].items():
        print(
            f"  {label:8s} NW>=$1M {pct(v['nw_ge_1000000'])}"
            f"  median NW {k(v['median_networth'])}"
        )


def main() -> int:
    OUT.mkdir(exist_ok=True)
    results = [analyze(2025), analyze(2022)]
    for r in results:
        report(r)
    (OUT / "scf-wealth-by-work-status.json").write_text(json.dumps(results, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
