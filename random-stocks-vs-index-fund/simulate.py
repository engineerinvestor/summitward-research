"""Simulate random-stock portfolios against an index fund.

Supports https://summitward.com/learn/random-stocks-vs-index-fund.

Model (monthly, arithmetic returns):
    r_m      ~ Normal(mu_m, sigma_m^2)             the index
    r_i      = r_f + beta_i (r_m - r_f) + e_i      a constituent
    e_i      ~ Normal(0, s_i^2), independent of r_m and of other stocks
The index is the fully diversified portfolio of the universe, so it carries
no idiosyncratic noise. A random portfolio's ending wealth is compared with
the index fund's ending wealth on the same contributions and the same market
path. Results describe the model, not history.

Cases
    baseline   beta = 1 for every stock; s = RMS idiosyncratic vol measured on
               current S&P 500 members (calibrate.py). Random portfolios then
               have the same expected return as the index, so any spread is
               uncompensated noise.
    measured   each of the 500 universe stocks gets a (beta, idio vol) pair
               drawn from the measured cross-section; expected returns follow
               CAPM.
    fat_tails  baseline with Student-t (4 df) shocks scaled to the same
               variance.

Rules
    fixed_n    buy N distinct random stocks in equal dollars at the start,
               never trade again.
    monthly    each month put the same dollar amount into one stock drawn at
               random (with replacement) from the universe; never sell.

Reads output/calibration.json and output/per_stock.csv; writes
output/simulation.json. Needs numpy.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
OUT = HERE / "output"

M = 500  # companies in the universe
RF = 0.03  # annual risk-free rate (assumption)
MKT_EXCESS = 0.06  # annual expected market excess return (assumption)
FUND_FEE = 0.0003  # index fund expense ratio used for scale (VTI/VOO class)
EW_FUND_FEE = 0.0020  # equal-weight S&P 500 ETF (RSP) expense ratio
SEED = 20261118


def load_calibration() -> tuple[dict, np.ndarray]:
    cal = json.loads((OUT / "calibration.json").read_text())
    with open(OUT / "per_stock.csv") as f:
        rows = list(csv.DictReader(f))
    pairs = np.array([[float(r["beta"]), float(r["idio_vol"])] for r in rows])
    return cal, pairs


def shocks(rng, shape, s, tails: bool):
    if not tails:
        return rng.normal(0.0, 1.0, shape) * s
    nu = 4.0
    z = rng.standard_t(nu, shape) / np.sqrt(nu / (nu - 2.0))
    return z * s


class Universe:
    def __init__(self, rng, case: str, s_rms: float, pairs: np.ndarray):
        if case == "measured":
            idx = rng.integers(0, len(pairs), M)
            self.beta = pairs[idx, 0]
            self.s = pairs[idx, 1] / np.sqrt(12)
        else:
            self.beta = np.ones(M)
            self.s = np.full(M, s_rms / np.sqrt(12))
        self.tails = case == "fat_tails"


def market_path(rng, T, sigma_m):
    mu = (RF + MKT_EXCESS) / 12
    return rng.normal(mu, sigma_m / np.sqrt(12), T)


def stock_returns(rng, uni: Universe, ids: np.ndarray, rm: np.ndarray):
    T, K = len(rm), len(ids)
    rf = RF / 12
    e = shocks(rng, (T, K), uni.s[ids], uni.tails)
    r = rf + uni.beta[ids] * (rm[:, None] - rf) + e
    return np.maximum(r, -0.99)


def growth_to_end(r: np.ndarray) -> np.ndarray:
    """G[t] = product of (1 + r[s]) for s >= t (value at T of $1 put in at t)."""
    return np.cumprod((1 + r)[::-1], axis=0)[::-1]


def pct(a, qs=(5, 25, 50, 75, 95)):
    return {f"p{q}": round(float(np.percentile(a, q)), 4) for q in qs}


def summarize(rel: np.ndarray) -> dict:
    return {
        **pct(rel),
        "mean": round(float(rel.mean()), 4),
        "p_trail_10": round(float((rel < 0.90).mean()), 4),
        "p_trail_25": round(float((rel < 0.75).mean()), 4),
        "p_trail_any": round(float((rel < 1.0).mean()), 4),
        "p_lead_10": round(float((rel > 1.10).mean()), 4),
    }


def run_fixed_n(rng, uni, sigma_m, N, years, paths):
    T = 12 * years
    rel = np.empty(paths)
    for p in range(paths):
        rm = market_path(rng, T, sigma_m)
        ids = rng.choice(M, N, replace=False)
        r = stock_returns(rng, uni, ids, rm)
        rel[p] = np.prod(1 + r, axis=0).mean() / np.prod(1 + rm)
    return summarize(rel)


def run_monthly(rng, uni, sigma_m, years, paths, per_buy=1, snapshots=True):
    T = 12 * years
    rel = np.empty(paths)
    distinct = np.empty(paths)
    neff = np.empty(paths)
    fee_drag = np.empty(paths)
    fee_drag_ew = np.empty(paths)
    snap_years = list(range(1, years + 1))
    neff_path = np.empty((paths, len(snap_years)))
    dist_path = np.empty((paths, len(snap_years)))
    for p in range(paths):
        rm = market_path(rng, T, sigma_m)
        picks = rng.integers(0, M, (T, per_buy))
        uniq, inv = np.unique(picks, return_inverse=True)
        inv = inv.reshape(T, per_buy)
        r = stock_returns(rng, uni, uniq, rm)
        G = growth_to_end(r)  # (T, K)
        Gm = growth_to_end(rm)  # (T,)
        t_idx = np.repeat(np.arange(T), per_buy)
        k_idx = inv.ravel()
        contrib = G[t_idx, k_idx] / per_buy  # each month invests $1 in total
        W = contrib.sum()
        Wm = Gm.sum()
        rel[p] = W / Wm
        v = np.bincount(k_idx, weights=contrib, minlength=len(uniq))
        distinct[p] = (v > 0).sum()
        neff[p] = v.sum() ** 2 / (v**2).sum()
        months_held = T - np.arange(T)
        fee_drag[p] = 1 - (Gm * (1 - FUND_FEE / 12) ** months_held).sum() / Wm
        fee_drag_ew[p] = 1 - (Gm * (1 - EW_FUND_FEE / 12) ** months_held).sum() / Wm
        if snapshots:
            C = np.vstack([np.ones(len(uniq)), np.cumprod(1 + r, axis=0)])
            for j, y in enumerate(snap_years):
                tau = 12 * y
                m = t_idx < tau
                val = C[tau, k_idx[m]] / C[t_idx[m], k_idx[m]] / per_buy
                vv = np.bincount(k_idx[m], weights=val, minlength=len(uniq))
                neff_path[p, j] = vv.sum() ** 2 / (vv**2).sum()
                dist_path[p, j] = (vv > 0).sum()
    out = {
        **summarize(rel),
        "distinct_mean": round(float(distinct.mean()), 1),
        "neff_median": round(float(np.median(neff)), 1),
        "neff_p5": round(float(np.percentile(neff, 5)), 1),
        "neff_p95": round(float(np.percentile(neff, 95)), 1),
        "fund_fee_drag_median": round(float(np.median(fee_drag)), 5),
        "ew_fund_fee_drag_median": round(float(np.median(fee_drag_ew)), 5),
    }
    if snapshots:
        out["by_year"] = [
            {
                "year": y,
                "distinct_mean": round(float(dist_path[:, j].mean()), 1),
                "neff_median": round(float(np.median(neff_path[:, j])), 1),
            }
            for j, y in enumerate(snap_years)
        ]
    return out


def closed_form(s_e, sigma_m, N, years):
    """Rebalanced equal weight, beta 1: tracking error and lognormal bands."""
    te = s_e / np.sqrt(N)
    vol = float(np.sqrt(sigma_m**2 + s_e**2 / N))
    mu, sd = -0.5 * te**2 * years, te * np.sqrt(years)
    z = 1.6448536269514722
    return {
        "vol": round(vol, 4),
        "tracking_error": round(float(te), 4),
        "p5": round(float(np.exp(mu - z * sd)), 4),
        "p50": round(float(np.exp(mu)), 4),
        "p95": round(float(np.exp(mu + z * sd)), 4),
    }


def expected_distinct(M_, T):
    return M_ * (1 - (1 - 1 / M_) ** T)


def main() -> None:
    cal, pairs = load_calibration()
    s_rms = cal["idiosyncratic_vol"]["rms"]
    sigma_m = cal["spy_annualized_vol"]
    rng = np.random.default_rng(SEED)
    res: dict = {
        "assumptions": {
            "universe_companies": M,
            "idio_vol_rms": s_rms,
            "market_vol": sigma_m,
            "risk_free": RF,
            "market_excess_return": MKT_EXCESS,
            "fund_fee_for_scale": FUND_FEE,
            "seed": SEED,
            "calibration_window": cal["window"],
        },
        "closed_form_rebalanced_ew_10y": {
            str(N): closed_form(s_rms, sigma_m, N, 10)
            for N in (1, 5, 10, 20, 30, 50, 100, 500)
        },
        "expected_distinct_holdings": {
            str(T): round(expected_distinct(M, T), 1) for T in (10, 12, 60, 120, 240, 360)
        },
    }
    for case in ("baseline", "measured", "fat_tails"):
        uni = Universe(rng, case, s_rms, pairs)
        paths = 10000 if case == "baseline" else 4000
        block = {"fixed_n_10y": {}, "monthly": {}}
        for N in (1, 5, 10, 20, 30, 50, 100):
            block["fixed_n_10y"][str(N)] = run_fixed_n(rng, uni, sigma_m, N, 10, paths)
        for years in (10, 20, 30):
            n_paths = paths if years == 10 else paths // 2
            block["monthly"][f"{years}y"] = run_monthly(
                rng, uni, sigma_m, years, n_paths, snapshots=(case == "baseline")
            )
        res[case] = block
        print(case, "done")
    # Fixed N = 10 held 20 and 30 years, baseline, for the horizon comparison.
    uni = Universe(rng, "baseline", s_rms, pairs)
    res["baseline"]["fixed_n_long"] = {
        f"10_{y}y": run_fixed_n(rng, uni, sigma_m, 10, y, 5000) for y in (20, 30)
    }
    (OUT / "simulation.json").write_text(json.dumps(res, indent=2) + "\n")
    b = res["baseline"]
    print(json.dumps({k: res[k] for k in ("closed_form_rebalanced_ew_10y", "expected_distinct_holdings")}, indent=1))
    print(json.dumps(b["fixed_n_10y"], indent=1))
    print(json.dumps({k: {kk: vv for kk, vv in v.items() if kk != "by_year"} for k, v in b["monthly"].items()}, indent=1))
    print(json.dumps(b["fixed_n_long"], indent=1))
    for case in ("measured", "fat_tails"):
        print(case, json.dumps({"N10": res[case]["fixed_n_10y"]["10"], "monthly10": res[case]["monthly"]["10y"]}, indent=1))


if __name__ == "__main__":
    main()
