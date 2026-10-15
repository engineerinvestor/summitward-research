"""Mean-variance optimization out of sample: simulation and walk-forward retest.

Supports https://summitward.com/learn/mean-variance-optimization-out-of-sample.
Needs numpy and scipy. Reads data/ and writes results.json. The design is
pre-registered in README.md; this script implements it without changes unless
README.md lists a deviation.

Part A  Known-parameter simulation: how much does estimating mu and Sigma from
        T years of monthly data cost, measured at the true parameters?
Part B1 Walk-forward on Kenneth French's 10 value-weighted US industry
        portfolios, July 1926 to August 2026, M = 120 (and 60) months.
Part B2 Walk-forward on Damodaran's annual asset-class returns, 1928 to 2025.

Conventions: weights for period t+1 use data through period t only. Returns
are in excess of the T-bill. Turnover is the sum of |target - drifted| weights
(buys plus sells). Sharpe ratios are annualized from monthly data by sqrt(12).
CE = mean - (gamma/2) var of excess returns, annualized.

Usage:
    python3 mvo_retest.py            # full run, writes results.json
    python3 mvo_retest.py --quick    # 200 simulated histories, 500 bootstraps
"""

import argparse
import json
import math
from pathlib import Path

import numpy as np
from scipy.optimize import minimize

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
SEED = 20261015

# --------------------------------------------------------------------------
# Estimators
# --------------------------------------------------------------------------


def sample_moments(x):
    """Sample mean and unbiased covariance of a T x N array."""
    return x.mean(axis=0), np.cov(x, rowvar=False, ddof=1)


def ledoit_wolf_cc(x):
    """Ledoit and Wolf (2004) shrinkage toward the constant-correlation target.

    Follows the authors' covCor.m: sample covariance with 1/T, shrinkage
    intensity kappa / T clipped to [0, 1]. Returns (Sigma_shrunk, delta).
    """
    t, n = x.shape
    xc = x - x.mean(axis=0)
    s = xc.T @ xc / t
    var = np.diag(s)
    sd = np.sqrt(var)
    corr = s / np.outer(sd, sd)
    rbar = (corr.sum() - n) / (n * (n - 1))
    f = rbar * np.outer(sd, sd)
    np.fill_diagonal(f, var)
    y = xc**2
    phi_mat = y.T @ y / t - s**2
    phi = phi_mat.sum()
    term1 = (xc**3).T @ xc / t
    term4 = var[:, None] * s
    theta = term1 - term4
    np.fill_diagonal(theta, 0.0)
    rho = np.diag(phi_mat).sum() + rbar * (np.outer(1 / sd, sd) * theta).sum()
    gamma = np.linalg.norm(s - f, "fro") ** 2
    kappa = (phi - rho) / gamma
    delta = max(0.0, min(1.0, kappa / t))
    return delta * f + (1 - delta) * s, delta


def bayes_stein_mean(x):
    """Jorion (1986) Bayes-Stein shrinkage of the mean toward the min-var mean."""
    t, n = x.shape
    mu, s = sample_moments(x)
    sig = s * (t - 1) / (t - n - 2)
    inv = np.linalg.inv(sig)
    ones = np.ones(n)
    w0 = inv @ ones / (ones @ inv @ ones)
    mu0 = w0 @ mu
    d = mu - mu0
    phi = (n + 2) / ((n + 2) + t * d @ inv @ d)
    return (1 - phi) * mu + phi * mu0


# --------------------------------------------------------------------------
# Optimizers
# --------------------------------------------------------------------------


def long_only_min_var(sig):
    n = len(sig)
    res = minimize(
        lambda w: w @ sig @ w,
        np.full(n, 1 / n),
        jac=lambda w: 2 * sig @ w,
        bounds=[(0, 1)] * n,
        constraints=[{"type": "eq", "fun": lambda w: w.sum() - 1, "jac": lambda w: np.ones(n)}],
        method="SLSQP",
        options={"ftol": 1e-12, "maxiter": 500},
    )
    w = np.clip(res.x, 0, None)
    return w / w.sum()


def long_only_tangency(mu, sig):
    """Max Sharpe, w >= 0, sum w = 1. Solved as min y'Sy s.t. mu'y = 1, y >= 0.

    If no asset has a positive expected excess return the tangency portfolio is
    undefined; fall back to long-only minimum variance (counted in results).
    """
    n = len(mu)
    if mu.max() <= 0:
        return long_only_min_var(sig), True
    y0 = np.where(mu > 0, 1 / (mu.clip(min=0).sum()), 0.0)
    res = minimize(
        lambda y: y @ sig @ y,
        y0,
        jac=lambda y: 2 * sig @ y,
        bounds=[(0, None)] * n,
        constraints=[{"type": "eq", "fun": lambda y: mu @ y - 1, "jac": lambda y: mu}],
        method="SLSQP",
        options={"ftol": 1e-14, "maxiter": 500},
    )
    y = np.clip(res.x, 0, None)
    return y / y.sum(), False


def simplex_grid(n, step_pct):
    k = 100 // step_pct
    pts = []

    def rec(prefix, remaining, slots):
        if slots == 1:
            pts.append(prefix + [remaining])
            return
        for i in range(remaining + 1):
            rec(prefix + [i], remaining - i, slots - 1)

    rec([], k, n)
    return np.array(pts, dtype=float) / k


def grid_ce(grid, mu, sig, gamma):
    return grid @ mu - 0.5 * gamma * np.einsum("gi,ij,gj->g", grid, sig, grid)


def grid_var(grid, sig):
    return np.einsum("gi,ij,gj->g", grid, sig, grid)


# --------------------------------------------------------------------------
# Part A: known-parameter simulation
# --------------------------------------------------------------------------


def calibration(with_gold):
    names = ["US stocks", "International stocks", "Bonds"]
    mu = [0.05, 0.05, 0.015]
    vol = [0.16, 0.17, 0.06]
    corr = np.array([[1.0, 0.8, 0.1], [0.8, 1.0, 0.1], [0.1, 0.1, 1.0]])
    if with_gold:
        names.append("Gold")
        mu.append(0.01)
        vol.append(0.16)
        c = np.eye(4)
        c[:3, :3] = corr
        corr = c
    mu = np.array(mu)
    vol = np.array(vol)
    return names, mu, np.outer(vol, vol) * corr


def calibrate_gamma(mu, sig, grid):
    """Smallest gamma on a 0.5 grid whose true optimum holds about 60% stocks."""
    best = None
    for g in np.arange(0.5, 20.01, 0.5):
        w = grid[np.argmax(grid_ce(grid, mu, sig, g))]
        stocks = w[0] + w[1]
        if best is None or abs(stocks - 0.60) < abs(best[1] - 0.60) - 1e-12:
            best = (float(g), float(stocks))
    return best[0]


def continuous_optimum(mu, sig, gamma):
    n = len(mu)
    res = minimize(
        lambda w: -(w @ mu - 0.5 * gamma * w @ sig @ w),
        np.full(n, 1 / n),
        bounds=[(0, 1)] * n,
        constraints=[{"type": "eq", "fun": lambda w: w.sum() - 1}],
        method="SLSQP",
        options={"ftol": 1e-14},
    )
    return res.x


def simulate_part_a(n_hist, rng, gamma=None, with_gold=False):
    names, mu, sig = calibration(with_gold)
    n = len(mu)
    grid = simplex_grid(n, 1 if n == 3 else 2)
    if gamma is None:
        gamma = calibrate_gamma(mu, sig, grid)
    true_ce_grid = grid_ce(grid, mu, sig, gamma)
    w_true = grid[np.argmax(true_ce_grid)]
    ce_true = true_ce_grid.max()
    w_cont = continuous_optimum(mu, sig, gamma)
    w_eq = np.full(n, 1 / n)
    ce_eq = w_eq @ mu - 0.5 * gamma * w_eq @ sig @ w_eq

    mu_m, sig_m = mu / 12, sig / 12
    chol = np.linalg.cholesky(sig_m)
    out = {
        "assets": names,
        "mu": mu.tolist(),
        "vol": np.sqrt(np.diag(sig)).tolist(),
        "corr": (sig / np.outer(np.sqrt(np.diag(sig)), np.sqrt(np.diag(sig)))).round(4).tolist(),
        "gamma": gamma,
        "grid_step_pct": 1 if n == 3 else 2,
        "true_optimum_weights": w_true.round(4).tolist(),
        "continuous_optimum_weights": w_cont.round(4).tolist(),
        "control_max_abs_diff": float(np.abs(w_true - w_cont).max()),
        "true_optimum_ce_pct": round(100 * ce_true, 4),
        "equal_weight_ce_pct": round(100 * ce_eq, 4),
        "equal_weight_loss_bp": round(1e4 * (ce_true - ce_eq), 2),
        "by_years": {},
    }
    strategies = ["mv_sample", "mv_bayes_stein", "mv_lw_cov", "min_variance"]
    for years in (5, 10, 20, 40, 100):
        t = 12 * years
        ws = {s: np.empty((n_hist, n)) for s in strategies}
        for h in range(n_hist):
            x = mu_m + rng.standard_normal((t, n)) @ chol.T
            m_hat, s_hat = sample_moments(x)
            lw, _ = ledoit_wolf_cc(x)
            bs = bayes_stein_mean(x)
            ests = {
                "mv_sample": (m_hat, s_hat),
                "mv_bayes_stein": (bs, s_hat),
                "mv_lw_cov": (m_hat, lw),
            }
            for s, (m_e, s_e) in ests.items():
                ws[s][h] = grid[np.argmax(grid_ce(grid, 12 * m_e, 12 * s_e, gamma))]
            ws["min_variance"][h] = grid[np.argmin(grid_var(grid, s_hat))]
        row = {}
        for s in strategies:
            w = ws[s]
            ce = w @ mu - 0.5 * gamma * np.einsum("hi,ij,hj->h", w, sig, w)
            loss = 1e4 * (ce_true - ce)
            stock_share = w[:, 0] + w[:, 1]
            row[s] = {
                "mean_loss_bp": round(float(loss.mean()), 2),
                "median_loss_bp": round(float(np.median(loss)), 2),
                "p95_loss_bp": round(float(np.percentile(loss, 95)), 2),
                "share_beats_equal_weight": round(float((ce > ce_eq).mean()), 4),
                "stock_share_p5_p50_p95": [
                    round(float(np.percentile(stock_share, q)), 3) for q in (5, 50, 95)
                ],
                "weight_p5_p95_by_asset": [
                    [round(float(np.percentile(w[:, i], 5)), 3), round(float(np.percentile(w[:, i], 95)), 3)]
                    for i in range(n)
                ],
            }
        out["by_years"][str(years)] = row
    return out


# --------------------------------------------------------------------------
# Tool cross-check: same PRNG as the browser tool (mulberry32 + Box-Muller)
# --------------------------------------------------------------------------


def mulberry32(seed):
    a = seed & 0xFFFFFFFF

    def nxt():
        nonlocal a
        a = (a + 0x6D2B79F5) & 0xFFFFFFFF
        t = a
        t = ((t ^ (t >> 15)) * (t | 1)) & 0xFFFFFFFF
        t ^= (t + (((t ^ (t >> 7)) * (t | 61)) & 0xFFFFFFFF)) & 0xFFFFFFFF
        return ((t ^ (t >> 14)) & 0xFFFFFFFF) / 4294967296

    return nxt


def tool_check(years=20, n_hist=300, seed=42):
    """Reproduces the browser tool's default run exactly (calibration 1)."""
    names, mu, sig = calibration(False)
    grid = simplex_grid(3, 1)
    gamma = calibrate_gamma(mu, sig, grid)
    chol = np.linalg.cholesky(sig / 12)
    rnd = mulberry32(seed)
    t = 12 * years

    def normal():
        u1 = rnd()
        u2 = rnd()
        return math.sqrt(-2 * math.log(1 - u1)) * math.cos(2 * math.pi * u2)

    ce_true = grid_ce(grid, mu, sig, gamma).max()
    w_eq = np.full(3, 1 / 3)
    ce_eq = w_eq @ mu - 0.5 * gamma * w_eq @ sig @ w_eq
    losses, beats, stocks, promised, delivered = [], 0, [], [], []
    for _ in range(n_hist):
        z = np.array([[normal() for _ in range(3)] for _ in range(t)])
        x = mu / 12 + z @ chol.T
        m_hat, s_hat = sample_moments(x)
        w = grid[np.argmax(grid_ce(grid, 12 * m_hat, 12 * s_hat, gamma))]
        ce = w @ mu - 0.5 * gamma * w @ sig @ w
        losses.append(1e4 * (ce_true - ce))
        beats += ce > ce_eq
        stocks.append(w[0] + w[1])
        promised.append(12 * w @ m_hat)
        delivered.append(w @ mu)
    return {
        "mean_promised_excess_return_pct": round(100 * float(np.mean(promised)), 3),
        "mean_true_excess_return_pct": round(100 * float(np.mean(delivered)), 3),
        "years": years,
        "histories": n_hist,
        "seed": seed,
        "gamma": gamma,
        "mean_loss_bp": round(float(np.mean(losses)), 4),
        "share_beats_equal_weight": round(beats / n_hist, 4),
        "first_five_stock_shares": [round(float(s), 2) for s in stocks[:5]],
    }


# --------------------------------------------------------------------------
# Data loading
# --------------------------------------------------------------------------


def read_french_block(path, header_contains):
    lines = path.read_text(errors="replace").splitlines()
    start = next(i for i, ln in enumerate(lines) if header_contains in ln)
    i = start
    while not lines[i].strip().startswith(","):
        i += 1
    cols = [c.strip() for c in lines[i].split(",")[1:]]
    dates, rows = [], []
    for ln in lines[i + 1 :]:
        parts = [p.strip() for p in ln.split(",")]
        if not parts[0].isdigit() or len(parts[0]) != 6:
            break
        dates.append(int(parts[0]))
        rows.append([float(p) for p in parts[1:]])
    return cols, np.array(dates), np.array(rows)


def load_industries():
    path = DATA / "10_Industry_Portfolios.csv"
    cols, dates, vw = read_french_block(path, "Average Value Weighted Returns -- Monthly")
    _, d2, nfirms = read_french_block(path, "Number of Firms in Portfolios")
    _, d3, size = read_french_block(path, "Average Firm Size")
    assert (dates == d2).all() and (dates == d3).all()
    _, df, ff = read_french_block(DATA / "F-F_Research_Data_Factors.csv", "Mkt-RF")
    rf_map = dict(zip(df.tolist(), (ff[:, 3] / 100).tolist(), strict=True))
    rf = np.array([rf_map[d] for d in dates])
    if (vw <= -99).any() or (size <= -99).any():
        raise ValueError("missing values in industry file")
    total = vw / 100
    cap = nfirms * size  # market cap at the start of each month
    return cols, dates, total - rf[:, None], rf, cap


def load_damodaran(keys):
    raw = json.loads((DATA / "damodaran_returns.json").read_text())
    years = list(range(raw["_metadata"]["first_year"], raw["_metadata"]["last_year"] + 1))
    tb = np.array([raw["assets"]["tbill"]["nominal"][str(y)] for y in years])
    tot = np.array([[raw["assets"][k]["nominal"][str(y)] for k in keys] for y in years])
    labels = [raw["assets"][k]["label"] for k in keys]
    return labels, np.array(years), tot - tb[:, None], tb


# --------------------------------------------------------------------------
# Walk-forward engine
# --------------------------------------------------------------------------


def make_rules(n, extra=None):
    """Weight rules: f(window_excess, expanding_excess, t_index) -> (w, fallback)."""

    def eq(_x, _e, _t):
        return np.full(n, 1 / n), False

    def max_sharpe_sample(x, _e, _t):
        m, s = sample_moments(x)
        return long_only_tangency(m, s)

    def mv_unconstrained(x, _e, _t):
        m, s = sample_moments(x)
        z = np.linalg.solve(s, m)
        return z / abs(z.sum()), False

    def min_var_unc(x, _e, _t):
        _, s = sample_moments(x)
        z = np.linalg.solve(s, np.ones(n))
        return z / z.sum(), False

    def min_var_lo(x, _e, _t):
        _, s = sample_moments(x)
        return long_only_min_var(s), False

    def min_var_lw(x, _e, _t):
        lw, _ = ledoit_wolf_cc(x)
        return long_only_min_var(lw), False

    def max_sharpe_bs_lw(x, _e, _t):
        lw, _ = ledoit_wolf_cc(x)
        return long_only_tangency(bayes_stein_mean(x), lw)

    def max_sharpe_const_sharpe(x, _e, _t):
        lw, _ = ledoit_wolf_cc(x)
        return long_only_tangency(np.sqrt(np.diag(lw)), lw)

    def max_sharpe_expanding(_x, e, _t):
        m, s = sample_moments(e)
        return long_only_tangency(m, s)

    def blend_half(x, e, t):
        w, fb = max_sharpe_sample(x, e, t)
        return 0.5 * w + 0.5 / n, fb

    rules = {
        "equal_weight": eq,
        "max_sharpe_sample": max_sharpe_sample,
        "mv_unconstrained": mv_unconstrained,
        "min_var_unconstrained": min_var_unc,
        "min_var_long_only": min_var_lo,
        "min_var_lw": min_var_lw,
        "max_sharpe_bs_lw": max_sharpe_bs_lw,
        "max_sharpe_const_sharpe": max_sharpe_const_sharpe,
        "max_sharpe_expanding": max_sharpe_expanding,
        "blend_half": blend_half,
    }
    if extra:
        rules.update(extra)
    return rules


def walk_forward(ex, rf, window, rules, rolling=True):
    """Returns dict name -> (excess_returns, turnover, weights) for periods window..T-1."""
    t_total, n = ex.shape
    out = {}
    for name, rule in rules.items():
        rets, turns, wts, fallbacks = [], [], [], 0
        w_drift = None
        for t in range(window, t_total):
            x = ex[t - window : t] if rolling else ex[:t]
            w, fb = rule(x, ex[:t], t)
            fallbacks += fb
            r = ex[t]
            turns.append(np.abs(w - w_drift).sum() if w_drift is not None else 0.0)
            port = w @ r
            rets.append(port)
            wts.append(w)
            gross = 1 + rf[t] + r  # total returns of each asset
            denom = 1 + rf[t] + port
            w_drift = w * gross / denom if denom > 0 else w
        out[name] = (np.array(rets), np.array(turns), np.array(wts), fallbacks)
    return out


# --------------------------------------------------------------------------
# Metrics and inference
# --------------------------------------------------------------------------


def sharpe(r):
    return r.mean() / r.std(ddof=1)


def memmel_p(a, b):
    """Jobson-Korkie test of equal Sharpe ratios with Memmel's (2003) correction."""
    t = len(a)
    sa, sb = sharpe(a), sharpe(b)
    rho = np.corrcoef(a, b)[0, 1]
    v = (2 - 2 * rho + 0.5 * (sa**2 + sb**2 - 2 * sa * sb * rho**2)) / t
    z = (sa - sb) / math.sqrt(v)
    return float(math.erfc(abs(z) / math.sqrt(2)))


def block_bootstrap_ci(a, b, block, reps, rng, scale):
    t = len(a)
    nblocks = math.ceil(t / block)
    starts = rng.integers(0, t, size=(reps, nblocks))
    idx = (starts[:, :, None] + np.arange(block)[None, None, :]).reshape(reps, -1)[:, :t] % t
    ra, rb = a[idx], b[idx]
    d = ra.mean(1) / ra.std(1, ddof=1) - rb.mean(1) / rb.std(1, ddof=1)
    lo, hi = np.percentile(d * scale, [2.5, 97.5])
    return [round(float(lo), 3), round(float(hi), 3)]


def max_drawdown(r):
    if (r <= -1).any():
        return -1.0
    wealth = np.cumprod(1 + r)
    peak = np.maximum.accumulate(wealth)
    return float((wealth / peak - 1).min())


def summarize(res, mask, periods_per_year, cost_bp, gammas, block, reps, rng, bench="equal_weight"):
    scale = math.sqrt(periods_per_year)
    out = {}
    b_r = res[bench][0][mask]
    for name, (r_all, turn_all, w_all, fb) in res.items():
        r, turn, w = r_all[mask], turn_all[mask], w_all[mask]
        net = r - cost_bp / 1e4 * turn
        row = {
            "sharpe": round(float(sharpe(r) * scale), 3),
            "sharpe_net_10bp": round(float(sharpe(net) * scale), 3),
            "mean_excess_pct": round(float(100 * r.mean() * periods_per_year), 2),
            "vol_pct": round(float(100 * r.std(ddof=1) * scale), 2),
            "turnover_per_period": round(float(turn.mean()), 4),
            "max_drawdown_pct": round(100 * max_drawdown(r), 1),
            "avg_max_weight": round(float(np.abs(w).max(axis=1).mean()), 3),
            "avg_gross_leverage": round(float(np.abs(w).sum(axis=1).mean()), 2),
            "tangency_fallbacks": int(fb),
        }
        for g in gammas:
            ce = periods_per_year * (r.mean() - 0.5 * g * r.var(ddof=1))
            ce_net = periods_per_year * (net.mean() - 0.5 * g * net.var(ddof=1))
            row[f"ce_gamma{g}_pct"] = round(float(100 * ce), 2)
            row[f"ce_gamma{g}_net_pct"] = round(float(100 * ce_net), 2)
        if name != bench:
            row["sharpe_diff_vs_" + bench] = round(float((sharpe(r) - sharpe(b_r)) * scale), 3)
            row["memmel_p_vs_" + bench] = round(memmel_p(r, b_r), 4)
            row["bootstrap_ci95_sharpe_diff_vs_" + bench] = block_bootstrap_ci(r, b_r, block, reps, rng, scale)
        out[name] = row
    return out


# --------------------------------------------------------------------------
# Part B1 and B2
# --------------------------------------------------------------------------


def part_b1(reps, rng):
    cols, dates, ex, rf, cap = load_industries()
    n = ex.shape[1]

    def market_cap(_x, _e, t):
        c = cap[t]
        return c / c.sum(), False

    periods = {
        "dgu_window": (197307, 200411),
        "post_publication": (200412, 202608),
        "pre_1963": (193607, 196306),
        "full": (193607, 202608),
    }
    result = {
        "assets": cols,
        "first_month": int(dates[0]),
        "last_month": int(dates[-1]),
        "periods": {k: list(v) for k, v in periods.items()},
        "by_window": {},
    }
    for window in (120, 60):
        rules = make_rules(n, {"market_cap": market_cap})
        res = walk_forward(ex, rf, window, rules)
        oos_dates = dates[window:]
        wres = {}
        for pname, (a, b) in periods.items():
            mask = (oos_dates >= a) & (oos_dates <= b)
            # DGU's industry sample starts estimation in July 1963
            if pname == "dgu_window" and window == 60:
                mask = (oos_dates >= 196807) & (oos_dates <= b)
            wres[pname] = {
                "first": int(oos_dates[mask][0]),
                "last": int(oos_dates[mask][-1]),
                "months": int(mask.sum()),
                "strategies": summarize(res, mask, 12, 10, (1,), 12, reps, rng),
            }
        result["by_window"][str(window)] = wres
        if window == 120:
            last = {k: v[2][-1].round(3).tolist() for k, v in res.items()}
            result["latest_weights_m120"] = {"month": int(dates[-1]), "weights": last}
            # in-sample illustration: max Sharpe fit on 1995-2004, held 2005-2026
            fit = (dates >= 199501) & (dates <= 200412)
            hold = dates >= 200501
            m, s = sample_moments(ex[fit])
            w_is, _ = long_only_tangency(m, s)
            w_eq = np.full(n, 1 / n)
            buy_hold = _buy_and_hold(ex[hold], rf[hold], w_is)
            result["in_sample_illustration"] = {
                "fit_months": [199501, 200412],
                "weights": dict(zip(cols, w_is.round(3).tolist(), strict=True)),
                "in_sample_sharpe": round(float(sharpe(ex[fit] @ w_is) * math.sqrt(12)), 3),
                "in_sample_sharpe_equal_weight": round(float(sharpe(ex[fit] @ w_eq) * math.sqrt(12)), 3),
                "next_period_months": [int(dates[hold][0]), int(dates[hold][-1])],
                "next_sharpe_rebalanced": round(float(sharpe(ex[hold] @ w_is) * math.sqrt(12)), 3),
                "next_sharpe_buy_and_hold": round(float(sharpe(buy_hold) * math.sqrt(12)), 3),
                "next_sharpe_equal_weight": round(float(sharpe(ex[hold] @ w_eq) * math.sqrt(12)), 3),
            }
    return result


def _buy_and_hold(ex, rf, w0):
    w = w0.copy()
    out = []
    for t in range(len(ex)):
        port = w @ ex[t]
        out.append(port)
        w = w * (1 + rf[t] + ex[t]) / (1 + rf[t] + port)
    return np.array(out)


def part_b2(reps, rng, keys):
    labels, years, ex, tb = load_damodaran(keys)
    n = ex.shape[1]

    def sixty_forty(_x, _e, _t):
        w = np.zeros(n)
        w[0], w[2] = 0.6, 0.4
        return w, False

    keep = [
        "equal_weight",
        "sixty_forty",
        "max_sharpe_sample",
        "min_var_long_only",
        "min_var_lw",
        "max_sharpe_bs_lw",
        "max_sharpe_const_sharpe",
        "max_sharpe_expanding",
        "blend_half",
    ]
    rules = {k: v for k, v in make_rules(n, {"sixty_forty": sixty_forty}).items() if k in keep}
    periods = {"full": (1948, 2025), "first_half": (1948, 1986), "second_half": (1987, 2025)}
    out = {"assets": labels, "periods": {k: list(v) for k, v in periods.items()}, "by_window": {}}
    window = 20
    for mode, rolling in (("rolling_20y", True), ("expanding", False)):
        res = walk_forward(ex, tb, window, rules, rolling=rolling)
        oos = years[window:]
        if rolling:
            out["weight_paths_rolling_20y"] = {
                "years": oos.tolist(),
                **{k: res[k][2].round(3).tolist() for k in ("max_sharpe_sample", "min_var_long_only")},
            }
        out["by_window"][mode] = {
            p: {
                "years": int(((oos >= a) & (oos <= b)).sum()),
                "strategies": summarize(res, (oos >= a) & (oos <= b), 1, 10, (1, 5), 3, reps, rng),
            }
            for p, (a, b) in periods.items()
        }
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    args = ap.parse_args()
    n_hist = 200 if args.quick else 2000
    reps = 500 if args.quick else 5000
    rng = np.random.default_rng(SEED)
    a3 = simulate_part_a(n_hist, rng)
    a4 = simulate_part_a(n_hist, rng, gamma=a3["gamma"], with_gold=True)
    results = {
        "generated": "see git log",
        "quick": args.quick,
        "part_a": {"three_assets": a3, "four_assets_with_gold": a4},
        "tool_check": tool_check(),
        "part_b1_industries": part_b1(reps, np.random.default_rng(SEED)),
        # gold before 1972 is an administered price; see README deviation 1
        "part_b2_asset_classes": {
            "with_gold": part_b2(
                reps, np.random.default_rng(SEED), ["sp500", "smallcap", "tbond", "baa", "gold"]
            ),
            "ex_gold": part_b2(reps, np.random.default_rng(SEED), ["sp500", "smallcap", "tbond", "baa"]),
        },
    }
    name = "results_quick.json" if args.quick else "results.json"
    (HERE / name).write_text(json.dumps(results, indent=1))
    print(f"wrote {name}")


if __name__ == "__main__":
    main()
