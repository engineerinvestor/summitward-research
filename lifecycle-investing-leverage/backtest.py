"""Re-test Ayres and Nalebuff's leveraged lifecycle strategy, 1871-2025.

Feeds the `lifecycle-investing-leverage` Learn guide on summitward.com. Reads
the monthly real series built by ``extract_data.py`` and the daily Ken French
market file (for intra-month margin calls), runs ``lifecycle_leverage.py``,
and writes ``results.json``.

Design (fixed before the results were read):

* Worker saves 4% of a Social Security "scaled medium earner" wage profile
  (Actuarial Note 2004.3, Table 6, ages 21-64) with the 2004 Trustees
  Report's 1.07% real wage growth, the profile the 2008 paper uses (peak wage
  $58,782 at age 51), for 44 years, pays a 0.30% annual fee, and starts each
  January.
* Leveraged strategy: 88% of lifetime wealth (the paper's CRRA-2 target),
  leverage capped at 2x, monthly rebalancing. Not re-optimized when costs
  change, as in the paper's robustness tables.
* Borrowing cost: T-bills plus a spread. Before July 1926 there is no bill
  series, so bills are proxied by call money minus its average 1926-1970 gap
  over bills.
* Benchmarks: 100% stocks; a 90%-to-50% linear glide path; and the same 88%
  lifetime-wealth target capped at 100% of savings (no borrowing), which
  splits the paper's gain into its de-risking part and its leverage part.

Sections: (1) replication of the 2008 paper's Table V on public data,
(2) cohorts through 2025 at several borrowing spreads, (3) breakeven spreads,
(4) equal-mean comparisons, (5) intra-month margin calls 1926-2026,
(6) a contribution pause after market crashes, (7) block bootstrap.

Usage:  python backtest.py
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import numpy as np

from lifecycle_leverage import (
    GAMMAS,
    Constant,
    Glide,
    Target,
    block_bootstrap_indices,
    effective_years,
    margin_call_months,
    optimal_share,
    simulate,
    summarize,
)

HERE = Path(__file__).resolve().parent
MONTHLY = HERE / "data" / "lifecycle_leverage_monthly.json"
DAILY = HERE / "data" / "us_market_daily.json"
OUTPUTS = [HERE / "results.json"]

# SSA Actuarial Note 2004.3, Table 6, medium earner, ages 21-64.
SSA_MEDIUM = [
    0.345, 0.411, 0.504, 0.590, 0.660, 0.719, 0.774, 0.819, 0.858, 0.889, 0.916,
    0.940, 0.960, 0.978, 0.997, 1.011, 1.028, 1.042, 1.054, 1.064, 1.075, 1.086,
    1.096, 1.106, 1.112, 1.115, 1.119, 1.120, 1.117, 1.108, 1.098, 1.085, 1.066,
    1.044, 1.017, 0.981, 0.948, 0.910, 0.872, 0.826, 0.774, 0.745, 0.717, 0.690,
]  # fmt: skip
# SSA indexes the factors to an average wage that grows faster than prices.
# The 2004 Trustees Report's ultimate assumptions (3.9% wage growth, 2.8% CPI)
# imply about 1.07% a year in real terms; Ayres and Nalebuff's profile carries
# that growth, which moves the wage peak from age 48 to age 51.
REAL_WAGE_GROWTH = 1.039 / 1.028 - 1.0
# Scale so the age-51 peak wage is $58,782, the paper's figure. Results are
# proportional to this, so it only sets the dollar units.
WAGE_SCALE = 58_782 / (1.098 * (1.0 + REAL_WAGE_GROWTH) ** 30)
SAVINGS_RATE = 0.04
FEE = 0.003
CAP = 2.0
TARGET = 0.88
YEARS = 44
T = YEARS * 12
SPREADS = [0.0, 0.003, 0.0075, 0.015, 0.025, 0.04, 0.06, 0.08]
MAIN_SPREAD = 0.015
# Real rate for the present value of future contributions in the target rule.
# The paper's text cites 2.63% (risk-free), but its Table IV footnote lists a
# 6.3% discount rate and Table V is reproduced only with the 6.35% blended
# return (88% stocks, 12% bonds). Discounting at 6.35% shrinks the
# lifetime-wealth estimate and so the leverage it calls for; the risk-free
# version runs as a sensitivity.
DISCOUNT = 0.0635
RF_DISCOUNT = 0.0263
CHEAP_SPREAD = 0.003
MAINTENANCE = (0.25, 0.30, 0.35)
PAUSE_DRAWDOWN = 0.30
PAUSE_MONTHS = 24
BOOT_PATHS = 10_000
BOOT_BLOCK = 60
BOOT_SEED = 20261017

# Ayres and Nalebuff (2008), Table V and Table VIII, for the replication check.
PAPER_TABLE_V = {
    "stock100": {"median": 354265, "mean": 410579, "std": 183500, "min": 142944,
                 "p10": 220593, "p90": 719062, "ce2": 343245, "ce4": 295626},
    "glide9050": {"median": 254854, "mean": 257316, "std": 69261, "min": 113536,
                  "p10": 163426, "p90": 346342, "ce2": 237082, "ce4": 215739},
    "lev": {"median": 450089, "mean": 489850, "std": 195643, "min": 153550,
            "p10": 272181, "p90": 812070, "ce2": 413666, "ce4": 344035},
    "lev_wins_vs_stock100": 89,
}  # fmt: skip


def monthly_rate(rate: float) -> float:
    return (1.0 + rate) ** (1.0 / 12.0) - 1.0


DISC_M = monthly_rate(DISCOUNT)


def geo(x: np.ndarray) -> float:
    return float(np.prod(1.0 + x) ** (12.0 / len(x)) - 1.0)


def monthly(rate: float) -> float:
    return (1.0 + rate) ** (1.0 / 12.0) - 1.0


def load():
    d = json.loads(MONTHLY.read_text())
    ym = np.asarray(d["ym"])
    call = np.array([np.nan if v is None else v for v in d["call"]])
    short = np.asarray(d["short"], dtype=float)
    overlap = (ym >= 192607) & ~np.isnan(call)
    gap = float(np.mean(call[overlap] - short[overlap]))
    bill = np.where(ym < 192607, call - gap, short)
    callmix = np.where(np.isnan(call), short + gap, call)
    return {
        "ym": ym,
        "stock": np.asarray(d["stock"], dtype=float),
        "bond": np.asarray(d["bond"], dtype=float),
        "bill": bill,
        "callmix": callmix,
        "gap": gap,
        "meta": d["_metadata"],
    }


def contributions() -> np.ndarray:
    growth = (1.0 + REAL_WAGE_GROWTH) ** np.arange(YEARS)
    annual = np.asarray(SSA_MEDIUM) * growth * WAGE_SCALE * SAVINGS_RATE
    return np.repeat(annual / 12.0, 12)


def cohort_index(ym: np.ndarray, first_year: int, last_year: int) -> np.ndarray:
    starts = [
        int(np.where(ym == y * 100 + 1)[0][0]) for y in range(first_year, last_year + 1)
    ]
    return np.array([np.arange(s, s + T) for s in starts])


def run_all(data, idx, borrow, planned, policies, r_lev, r_unlev, actual=None):
    out = {}
    for key, pol in policies.items():
        out[key] = simulate(
            data["stock"][idx],
            data["bond"][idx],
            borrow[idx],
            planned,
            pol,
            r_lev=r_lev,
            r_unlev=r_unlev,
            fee=FEE,
            actual=actual,
        )
    return out


def rel(a: dict, b: dict) -> dict:
    return {k: (a[k] / b[k] - 1.0) if b[k] else None for k in a if k in b}


def rounded(d, digits=4):
    if isinstance(d, dict):
        return {k: rounded(v, digits) for k, v in d.items()}
    if isinstance(d, list):
        return [rounded(v, digits) for v in d]
    if isinstance(d, float):
        return round(d, digits) if abs(d) < 1000 else round(d)
    return d


def solve_target_for_mean(data, idx, borrow, planned, r_lev, r_unlev, goal, cap=CAP):
    lo, hi = 0.2, 1.5
    for _ in range(40):
        mid = 0.5 * (lo + hi)
        w = simulate(
            data["stock"][idx],
            data["bond"][idx],
            borrow[idx],
            planned,
            Target(mid, cap=cap),
            r_lev=r_lev,
            r_unlev=r_unlev,
            fee=FEE,
        ).wealth
        if w.mean() < goal:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)  # fmt: skip


def solve_constant_for_mean(data, idx, borrow, planned, goal):
    lo, hi = 0.2, 1.0
    for _ in range(40):
        mid = 0.5 * (lo + hi)
        w = simulate(
            data["stock"][idx],
            data["bond"][idx],
            borrow[idx],
            planned,
            Constant(mid),
            fee=FEE,
        ).wealth
        if w.mean() < goal:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)  # fmt: skip


def replication(data, planned):
    ym = data["ym"]
    idx = cohort_index(ym, 1871, 1963)
    borrow = data["callmix"]
    r_lev = DISC_M
    r_unlev = DISC_M
    pols = {
        "stock100": Constant(1.0),
        "glide9050": Glide(0.9, 0.5),
        "lev": Target(TARGET, cap=CAP),
        "target_nolev": Target(TARGET, cap=1.0),
    }
    res = run_all(data, idx, borrow, planned, pols, r_lev, r_unlev)
    stats = {k: summarize(v.wealth) for k, v in res.items()}
    ratios_ours = {k: rel(stats[k], stats["stock100"]) for k in stats}
    paper = {k: v for k, v in PAPER_TABLE_V.items() if isinstance(v, dict)}
    ratios_paper = {k: rel(paper[k], paper["stock100"]) for k in paper}
    wins = int(np.sum(res["lev"].wealth > res["stock100"].wealth))
    print("\n(1) Replication of Ayres-Nalebuff (2008) Table V, 94 cohorts 1871-2007")
    for k in ("lev", "glide9050"):
        for m in ("mean", "median", "min", "p10", "std", "ce2", "ce4"):
            print(f"  {k:10s} {m:6s} vs 100%: ours {ratios_ours[k][m]:+.3f}"
                  f"  paper {ratios_paper[k][m]:+.3f}")  # fmt: skip
    print(
        f"  lev beats 100% in {wins}/94 cohorts (paper {PAPER_TABLE_V['lev_wins_vs_stock100']})"
    )
    print(f"  target capped at 100% vs 100% stock: mean {ratios_ours['target_nolev']['mean']:+.3f}"
          f" median {ratios_ours['target_nolev']['median']:+.3f}")  # fmt: skip
    return {
        "cohorts": 94,
        "stats": stats,
        "ratios_vs_stock100": ratios_ours,
        "paper_ratios_vs_stock100": ratios_paper,
        "paper_table_v": PAPER_TABLE_V,
        "lev_wins_vs_stock100": wins,
        "borrowing": "call money (NBER to 1970-11), then T-bills plus the 1926-1970 call-bill gap",
    }


def main_sweep(data, planned):
    ym = data["ym"]
    idx = cohort_index(ym, 1871, 1982)
    n = len(idx)
    r_unlev = DISC_M
    out = {
        "cohorts": n,
        "first_retirement": 1871 + YEARS,
        "last_retirement": 1982 + YEARS - 1,
    }
    base = None
    sweep = []
    for spread in SPREADS:
        borrow = data["bill"] + monthly(spread)
        r_lev = DISC_M
        pols = {"lev": Target(TARGET, cap=CAP)}
        if base is None:
            pols |= {
                "stock100": Constant(1.0),
                "glide9050": Glide(0.9, 0.5),
                "target_nolev": Target(TARGET, cap=1.0),
            }
        res = run_all(data, idx, borrow, planned, pols, r_lev, r_unlev)
        if base is None:
            base = res
        lev = res["lev"].wealth
        row = {
            "spread": spread,
            "lev": summarize(lev),
            "lev_vs_stock100": rel(summarize(lev), summarize(base["stock100"].wealth)),
            "lev_vs_nolev": rel(summarize(lev), summarize(base["target_nolev"].wealth)),
            "wins_vs_stock100": int(np.sum(lev > base["stock100"].wealth)),
            "wins_vs_nolev": int(np.sum(lev > base["target_nolev"].wealth)),
        }
        sweep.append(row)
        if spread == MAIN_SPREAD:
            main = res
        if spread == CHEAP_SPREAD:
            cheap = res
    out["sweep"] = sweep
    out["benchmarks"] = {
        k: summarize(base[k].wealth) for k in ("stock100", "glide9050", "target_nolev")
    }
    out["nolev_vs_stock100"] = rel(
        out["benchmarks"]["target_nolev"], out["benchmarks"]["stock100"]
    )

    retire = [1871 + YEARS + i for i in range(n)]
    out["cohort_wealth"] = {
        "retire_year": retire,
        "stock100": base["stock100"].wealth.tolist(),
        "glide9050": base["glide9050"].wealth.tolist(),
        "target_nolev": base["target_nolev"].wealth.tolist(),
        "lev_main": main["lev"].wealth.tolist(),
        "lev_cheap": cheap["lev"].wealth.tolist(),
    }

    # Real dollars in stock by career year, undiscounted: the paper's
    # effective-years figures (21.1 / 24.7 / 26.3 for 100% / 88% target /
    # 90-50) are reproduced on that basis, not on present values.
    expo = {"stock100": base["stock100"], "glide9050": base["glide9050"],
            "target_nolev": base["target_nolev"], "lev": main["lev"]}  # fmt: skip
    out["effective_years"] = {
        k: float(effective_years(v.exposure, 0.0).mean()) for k, v in expo.items()
    }
    out["exposure_by_age"] = {
        "age": list(range(21, 21 + YEARS)),
        **{
            k: (v.exposure.reshape(n, YEARS, 12).mean(axis=2)).mean(axis=0).tolist()
            for k, v in expo.items()
        },
    }
    share = main["lev"].share
    out["leverage_phase"] = {
        "median_age_max_leverage_ends": float(
            np.median(21 + np.argmax(share < CAP - 1e-9, axis=1) / 12)
        ),
        "median_age_leverage_ends": float(
            np.median(21 + np.argmax(share <= 1 + 1e-9, axis=1) / 12)
        ),
    }

    print(
        f"\n(2) {n} cohorts retiring {out['first_retirement']}-{out['last_retirement']}"
    )
    b = out["benchmarks"]
    print(
        f"  100% stock median {b['stock100']['median']:,.0f}  mean {b['stock100']['mean']:,.0f}"
    )
    print(
        "  target, no leverage vs 100%: "
        + ", ".join(
            f"{m} {out['nolev_vs_stock100'][m]:+.3f}"
            for m in ("mean", "median", "p10", "min", "ce2", "ce4")
        )
    )
    for row in sweep:
        r = row["lev_vs_stock100"]
        q = row["lev_vs_nolev"]
        print(f"  spread {row['spread']:.4f}: vs 100% mean {r['mean']:+.3f} median {r['median']:+.3f} "
              f"p10 {r['p10']:+.3f} min {r['min']:+.3f} ce2 {r['ce2']:+.3f} ce4 {r['ce4']:+.3f} wins {row['wins_vs_stock100']}/{n} | "
              f"vs no-lev mean {q['mean']:+.3f} median {q['median']:+.3f} min {q['min']:+.3f} ce4 {q['ce4']:+.3f} wins {row['wins_vs_nolev']}/{n}")  # fmt: skip
    print(f"  effective years: {rounded(out['effective_years'], 1)}")
    print(f"  leverage phases: {rounded(out['leverage_phase'], 1)}")
    return out, idx, main


def breakevens(data, planned, idx, bench):
    r_unlev = DISC_M

    def lev_stats(spread):
        borrow = data["bill"] + monthly(spread)
        w = simulate(
            data["stock"][idx],
            data["bond"][idx],
            borrow[idx],
            planned,
            Target(TARGET, cap=CAP),
            r_lev=DISC_M,
            r_unlev=r_unlev,
            fee=FEE,
        ).wealth
        return summarize(w)  # fmt: skip

    out = {}
    for ref in ("stock100", "target_nolev"):
        out[ref] = {}
        for metric in ("mean", "median", "p10", "min", "ce2", "ce4"):
            goal = bench[ref][metric]
            lo, hi = -0.02, 0.20
            if lev_stats(lo)[metric] <= goal:
                out[ref][metric] = None  # loses even with negative spread
                continue
            if lev_stats(hi)[metric] > goal:
                out[ref][metric] = hi
                continue
            for _ in range(30):
                mid = 0.5 * (lo + hi)
                if lev_stats(mid)[metric] > goal:
                    lo = mid
                else:
                    hi = mid
            out[ref][metric] = 0.5 * (lo + hi)
    print(
        "\n(3) Breakeven borrowing spread over T-bills (leveraged 88% target ties the benchmark)"
    )
    for ref, d in out.items():
        print(
            f"  vs {ref}: "
            + ", ".join(
                f"{m} {v if v is None else round(v * 100, 2)}" for m, v in d.items()
            )
        )
    return out


def equal_mean(data, planned, idx, bench):
    borrow = data["bill"] + monthly(MAIN_SPREAD)
    r_lev = DISC_M
    r_unlev = DISC_M
    lam = solve_target_for_mean(
        data, idx, borrow, planned, r_lev, r_unlev, bench["stock100"]["mean"]
    )
    w = simulate(data["stock"][idx], data["bond"][idx], borrow[idx], planned, Target(lam, cap=CAP),
                 r_lev=r_lev, r_unlev=r_unlev, fee=FEE).wealth  # fmt: skip
    a = {
        "target": lam,
        "stats": summarize(w),
        "vs_stock100": rel(summarize(w), bench["stock100"]),
    }
    # 2010 paper's framing: the constant share of savings that matches the
    # 200/50 strategy's mean. Here, the constant share matching the 88% target.
    lev = simulate(data["stock"][idx], data["bond"][idx], borrow[idx], planned, Target(TARGET, cap=CAP),
                   r_lev=r_lev, r_unlev=r_unlev, fee=FEE).wealth  # fmt: skip
    cshare = (
        solve_constant_for_mean(data, idx, borrow, planned, lev.mean())
        if lev.mean() < bench["stock100"]["mean"]
        else None
    )
    # Same idea without leverage: the lifetime-wealth target capped at 100%
    # that matches 100% stock's mean is impossible (cap binds), so compare the
    # unleveraged target to the constant share with its mean.
    nolev_mean = bench["target_nolev"]["mean"]
    c2 = solve_constant_for_mean(data, idx, borrow, planned, nolev_mean)
    wc2 = simulate(
        data["stock"][idx],
        data["bond"][idx],
        borrow[idx],
        planned,
        Constant(c2),
        fee=FEE,
    ).wealth
    b = {"constant_share": c2, "stats": summarize(wc2),
         "nolev_vs_constant": rel(bench["target_nolev"], summarize(wc2))}  # fmt: skip
    print(f"\n(4) Equal-mean: leveraged target {lam:.3f} matches 100% stock's mean; "
          f"std {a['vs_stock100']['std']:+.3f}, p10 {a['vs_stock100']['p10']:+.3f}, min {a['vs_stock100']['min']:+.3f}, "
          f"ce4 {a['vs_stock100']['ce4']:+.3f}")  # fmt: skip
    print(f"  no-leverage target vs constant {c2:.3f} (same mean): std {b['nolev_vs_constant']['std']:+.3f}, "
          f"p10 {b['nolev_vs_constant']['p10']:+.3f}, min {b['nolev_vs_constant']['min']:+.3f}")  # fmt: skip
    return {
        "leveraged_matching_stock100": a,
        "nolev_vs_equal_mean_constant": b,
        "constant_matching_lev": cshare,
    }


def margin_calls(data, idx, main):
    raw = json.loads(DAILY.read_text())
    dates = np.asarray(raw["dates"])
    r = np.asarray(raw["returns_bp"], dtype=float) / 10000.0
    ymd = dates // 100
    mins = {}
    for key in np.unique(ymd):
        mask = ymd == key
        mins[int(key)] = float(np.min(np.cumprod(1.0 + r[mask])))
    ym = data["ym"]
    rel_min = np.array([[mins.get(int(ym[j]), 1.0) for j in row] for row in idx])
    covered = np.array([[int(ym[j]) in mins for j in row] for row in idx])
    share = main["lev"].share
    lev_months = int(np.sum((share > 1.0) & covered))
    out = {"levered_cohort_months_1926_on": lev_months, "by_maintenance": {}}
    print("\n(5) Intra-month margin calls, daily French market data 1926-07 to 2026-05")
    for m in MAINTENANCE:
        calls = margin_call_months(share, rel_min, m) & covered
        months = sorted(
            {
                int(ym[j])
                for row, crow in zip(idx, calls)
                for j, c in zip(row, crow)
                if c
            }
        )
        out["by_maintenance"][str(m)] = {
            "cohort_months": int(calls.sum()),
            "cohorts_hit": int(calls.any(axis=1).sum()),
            "calendar_months": months,
        }
        print(f"  maintenance {m:.0%}: {int(calls.sum())} of {lev_months} levered cohort-months, "
              f"{int(calls.any(axis=1).sum())} cohorts, months {months}")  # fmt: skip
    return out


def pause_stress(data, planned, idx, r_lev_spread=MAIN_SPREAD):
    ym = data["ym"]
    level = np.cumprod(1.0 + data["stock"])
    dd = level / np.maximum.accumulate(level) - 1.0
    cross = np.zeros(len(dd), bool)
    cross[1:] = (dd[1:] < -PAUSE_DRAWDOWN) & (dd[:-1] >= -PAUSE_DRAWDOWN)
    paused = np.zeros(len(dd), bool)
    for t in np.where(cross)[0]:
        paused[t + 1 : t + 1 + PAUSE_MONTHS] = True
    actual = np.where(paused[idx], 0.0, planned[None, :])
    borrow = data["bill"] + monthly(r_lev_spread)
    pols = {
        "stock100": Constant(1.0),
        "target_nolev": Target(TARGET, cap=1.0),
        "lev": Target(TARGET, cap=CAP),
    }
    res = run_all(data, idx, borrow, planned, pols, DISC_M, DISC_M, actual=actual)
    stats = {k: summarize(v.wealth) for k, v in res.items()}
    out = {
        "trigger_months": [int(ym[t]) for t in np.where(cross)[0]],
        "stats": stats,
        "lev_vs_stock100": rel(stats["lev"], stats["stock100"]),
        "lev_vs_nolev": rel(stats["lev"], stats["target_nolev"]),
        "wins_vs_stock100": int(np.sum(res["lev"].wealth > res["stock100"].wealth)),
        "cohorts_with_pause": int((actual == 0).any(axis=1).sum()),
    }
    print(
        f"\n(6) Contribution pause ({PAUSE_MONTHS} months after a {PAUSE_DRAWDOWN:.0%} real drawdown), spread {r_lev_spread:.3f}"
    )
    print(f"  triggers: {out['trigger_months']}")
    r = out["lev_vs_stock100"]
    print(f"  lev vs 100%: mean {r['mean']:+.3f} median {r['median']:+.3f} p10 {r['p10']:+.3f} min {r['min']:+.3f} "
          f"ce4 {r['ce4']:+.3f} wins {out['wins_vs_stock100']}/{len(idx)}")  # fmt: skip
    return out


def bootstrap(
    data,
    planned,
    block=BOOT_BLOCK,
    paths=BOOT_PATHS,
    spreads=(CHEAP_SPREAD, MAIN_SPREAD),
):
    ym = data["ym"]
    end = int(np.where(ym == 202512)[0][0]) + 1
    idx = block_bootstrap_indices(end, T, paths, block, BOOT_SEED)
    r_unlev = DISC_M
    out = {"paths": paths, "block_months": block, "seed": BOOT_SEED, "by_spread": {}}
    base = None
    for spread in spreads:
        borrow = data["bill"] + monthly(spread)
        pols = {"lev": Target(TARGET, cap=CAP)}
        if base is None:
            pols |= {
                "stock100": Constant(1.0),
                "target_nolev": Target(TARGET, cap=1.0),
                "glide9050": Glide(0.9, 0.5),
            }
        res = run_all(data, idx, borrow, planned, pols, DISC_M, r_unlev)
        if base is None:
            base = {k: summarize(v.wealth) for k, v in res.items()}
            base_w = {k: v.wealth for k, v in res.items()}
        s = summarize(res["lev"].wealth)
        out["by_spread"][str(spread)] = {
            "lev": s,
            "lev_vs_stock100": rel(s, base["stock100"]),
            "lev_vs_nolev": rel(s, base["target_nolev"]),
            "share_paths_lev_beats_stock100": float(
                np.mean(res["lev"].wealth > base_w["stock100"])
            ),
            "share_paths_lev_beats_nolev": float(
                np.mean(res["lev"].wealth > base_w["target_nolev"])
            ),
        }
    out["benchmarks"] = base
    out["nolev_vs_stock100"] = rel(base["target_nolev"], base["stock100"])
    print(f"\n(7) Block bootstrap: {paths:,} paths, {block}-month blocks, 1871-2025")
    print(
        "  no-lev vs 100%: "
        + ", ".join(
            f"{m} {out['nolev_vs_stock100'][m]:+.3f}"
            for m in ("mean", "median", "p5", "p1", "ce2", "ce4", "ce8")
        )
    )
    for spread, d in out["by_spread"].items():
        r = d["lev_vs_stock100"]
        q = d["lev_vs_nolev"]
        print(f"  spread {float(spread):.3f}: vs 100% mean {r['mean']:+.3f} median {r['median']:+.3f} p5 {r['p5']:+.3f} "
              f"p1 {r['p1']:+.3f} ce2 {r['ce2']:+.3f} ce4 {r['ce4']:+.3f} ce8 {r['ce8']:+.3f} beats {d['share_paths_lev_beats_stock100']:.2f} | "
              f"vs no-lev median {q['median']:+.3f} p1 {q['p1']:+.3f} ce4 {q['ce4']:+.3f}")  # fmt: skip
    return out


def rf_discount_sensitivity(data, planned, idx, bench):
    """Main comparison with future contributions discounted at the risk-free rate."""
    rd = monthly(RF_DISCOUNT)
    out = {}
    for spread in (CHEAP_SPREAD, MAIN_SPREAD, 0.04):
        borrow = data["bill"] + monthly(spread)
        lev = simulate(data["stock"][idx], data["bond"][idx], borrow[idx], planned,
                       Target(TARGET, cap=CAP), r_lev=rd, r_unlev=rd, fee=FEE).wealth  # fmt: skip
        s = summarize(lev)
        out[str(spread)] = {"lev": s, "lev_vs_stock100": rel(s, bench["stock100"]),
                            "wins_vs_stock100": int(np.sum(lev > np.array(bench["_stock100_w"])))}  # fmt: skip
    nolev = simulate(data["stock"][idx], data["bond"][idx], data["bill"][idx], planned,
                     Target(TARGET, cap=1.0), r_lev=rd, r_unlev=rd, fee=FEE).wealth  # fmt: skip
    out["nolev_vs_stock100"] = rel(summarize(nolev), bench["stock100"])
    print(
        f"\nSensitivity: contributions discounted at {RF_DISCOUNT:.2%} instead of {DISCOUNT:.2%}"
    )
    for k, v in out.items():
        r = v.get("lev_vs_stock100", v)
        print(
            f"  {k}: mean {r['mean']:+.3f} median {r['median']:+.3f} min {r['min']:+.3f} ce4 {r['ce4']:+.3f}"
        )
    return out


def crra_targets(data):
    ym = data["ym"]
    jan = np.where(ym % 100 == 1)[0]
    jan = jan[jan + 12 <= len(ym)]
    z = np.array([np.prod(1 + data["stock"][j : j + 12]) for j in jan])
    rb = np.array([np.prod(1 + data["bond"][j : j + 12]) for j in jan])
    out = {}
    for spread in (CHEAP_SPREAD, MAIN_SPREAD):
        rm = np.array(
            [np.prod(1 + data["bill"][j : j + 12] + monthly(spread)) for j in jan]
        )
        out[str(spread)] = {
            str(g): {"lev": optimal_share(z, rm, g), "unlev": optimal_share(z, rb, g)}
            for g in GAMMAS
        }
    print(
        f"\nCRRA targets (annual real returns {int(ym[jan[0]])}-{int(ym[jan[-1]])}): {out}"
    )
    return out


def main() -> None:
    data = load()
    planned = contributions()
    print(f"Data {data['meta']['first_month']}-{data['meta']['last_month']}; call money ran "
          f"{data['gap'] * 1200:.2f}%/yr above T-bills, 1926-07 to 1970-11")  # fmt: skip
    rep = replication(data, planned)
    main_out, idx, main_res = main_sweep(data, planned)
    be = breakevens(data, planned, idx, main_out["benchmarks"])
    em = equal_mean(data, planned, idx, main_out["benchmarks"])
    mc = margin_calls(data, idx, main_res)
    ps = pause_stress(data, planned, idx)
    bs = bootstrap(data, planned)
    bs12 = bootstrap(data, planned, block=12, paths=BOOT_PATHS, spreads=(MAIN_SPREAD,))
    targets = crra_targets(data)
    bench = dict(main_out["benchmarks"])
    bench["_stock100_w"] = main_out["cohort_wealth"]["stock100"]
    rfs = rf_discount_sensitivity(data, planned, idx, bench)

    payload = {
        "_metadata": {
            "generated": date.today().isoformat(),
            "script": "backtest.py",
            "data": data["meta"],
            "design": {
                "savings_rate": SAVINGS_RATE,
                "wage_profile": "SSA Actuarial Note 2004.3, Table 6, medium earner, ages 21-64",
                "real_wage_growth": REAL_WAGE_GROWTH,
                "wage_scale": WAGE_SCALE,
                "years": YEARS,
                "fee": FEE,
                "cap": CAP,
                "target": TARGET,
                "discount": DISCOUNT,
                "borrowing": "T-bills plus spread; pre-1926 bills proxied by call money minus the 1926-1970 call-bill gap",
                "call_bill_gap": data["gap"] * 12,
                "main_spread": MAIN_SPREAD,
                "cheap_spread": CHEAP_SPREAD,
                "pause": {"drawdown": PAUSE_DRAWDOWN, "months": PAUSE_MONTHS},
            },
        },
        "replication_2008": rep,
        "main": main_out,
        "breakeven_spread": be,
        "equal_mean": em,
        "margin_calls": mc,
        "pause": ps,
        "bootstrap": bs,
        "bootstrap_12m_blocks": bs12,
        "crra_targets": targets,
        "rf_discount_sensitivity": rfs,
        "contributions_monthly": planned.tolist(),
    }
    text = json.dumps(rounded(payload, 6), separators=(",", ":")) + "\n"
    for out in OUTPUTS:
        out.write_text(text)
        print(f"wrote {out.relative_to(HERE)}")


if __name__ == "__main__":
    main()
