"""Reference implementation of the guide's Backtest Overfitting Lab.

Supports https://summitward.com/learn/does-technical-analysis-work. Needs
numpy. The browser component (backtest-overfitting-lab.tsx) runs the same
algorithm with the same random numbers; with the default settings its output
must match the `tool_check` block this script prints.

Each simulated market is 20 years of daily log returns (plus a 300-day
burn-in so the longest moving average has history), independent and normal
with 16% annual volatility. Cash earns a constant 3% a year. With no equity
premium the stock's expected daily log return equals cash's, so no timing rule
can be expected to beat buy and hold before costs: any rule's position on a
day depends only on earlier days, so its expected log growth equals buy and
hold's.

Rules are moving-average crossovers (short above long: in the market;
otherwise cash), on a 5 x 6 grid of lengths. A signal from the close of day t
is traded at the close of day t+1. The rule with the best after-cost edge over
buy and hold in the first ten years ("backtest") is then scored on the next
ten ("live").

    python3 overfitting_lab.py [--seed 42] [--rules 30] [--cost-bp 5] [--premium 0]
    python3 overfitting_lab.py --zero-edge-test
"""

import argparse
import math

import numpy as np

YEARS = 20
DPY = 252
BURN = 300
SIGMA = 0.16
RF = 0.03
MARKETS = 300
SHORTS = [1, 2, 5, 10, 20]
LONGS = [50, 100, 150, 200, 250, 300]
# Search order: the textbook 200-day rule first, then the rest of the grid.
GRID = [(1, 200)] + [(s, l_) for s in SHORTS for l_ in LONGS if (s, l_) != (1, 200)]
MASK = 0xFFFFFFFF


def imul(a, b):
    return (a * b) & MASK


def make_rng(seed):
    """Exact port of the JS mulberry32 used across Summitward simulators."""
    s = seed & MASK

    def nxt():
        nonlocal s
        s = (s + 0x6D2B79F5) & MASK
        t = imul(s ^ (s >> 15), 1 | s)
        t = ((t + imul(t ^ (t >> 7), 61 | t)) & MASK) ^ t
        return ((t ^ (t >> 14)) & MASK) / 4294967296

    return nxt


def randn(rng):
    u1 = 1.0 - rng()
    u2 = rng()
    return math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * u2)


def simulate_market(rng, premium):
    n = BURN + YEARS * DPY
    rf_log = math.log(1 + RF) / DPY
    mu = rf_log + math.log(1 + premium) / DPY
    sd = SIGMA / math.sqrt(DPY)
    return np.array([mu + sd * randn(rng) for _ in range(n)])


def sma_all(level, n):
    c = np.concatenate([[0.0], np.cumsum(level)])
    out = np.full(len(level), np.nan)
    out[n - 1 :] = (c[n:] - c[:-n]) / n
    return out


def score(x, rules, cost):
    """Edges (rule CAGR minus buy-and-hold CAGR) in the backtest and live
    halves for each rule, plus the winner's index."""
    level = np.exp(np.cumsum(x))
    stock = np.expm1(x)
    cash = math.exp(math.log(1 + RF) / DPY) - 1
    half = YEARS * DPY // 2
    a0, a1, b1 = BURN, BURN + half, BURN + 2 * half
    yrs = YEARS / 2
    bh_in = math.exp(np.sum(x[a0:a1]) / yrs) - 1
    bh_out = math.exp(np.sum(x[a1:b1]) / yrs) - 1
    cache = {}
    res = []
    for s, l_ in rules:
        for k in (s, l_):
            if k not in cache:
                cache[k] = sma_all(level, k)
        sig = (cache[s] > cache[l_]).astype(float)
        pos = np.ones(len(x))
        pos[2:] = sig[:-2]
        trade = np.abs(np.diff(pos, prepend=pos[0]))
        r = pos * stock + (1 - pos) * cash - cost * trade
        lr = np.log1p(r)
        e_in = math.exp(np.sum(lr[a0:a1]) / yrs) - 1 - bh_in
        e_out = math.exp(np.sum(lr[a1:b1]) / yrs) - 1 - bh_out
        res.append((e_in, e_out, float(pos[a0:b1].mean())))
    win = max(range(len(res)), key=lambda i: res[i][0])
    return res, win


def run(seed, n_rules, cost_bp, premium):
    rng = make_rng(seed)
    rules = GRID[:n_rules]
    cost = cost_bp / 1e4
    rows = []
    for _ in range(MARKETS):
        x = simulate_market(rng, premium)
        res, win = score(x, rules, cost)
        rows.append((rules[win], res[win][0], res[win][1]))
    first = rows[0]
    e_in = np.array([r[1] for r in rows])
    e_out = np.array([r[2] for r in rows])
    return {
        "featured_winner": f"{first[0][0]}-{first[0][1]}",
        "featured_edge_in": first[1],
        "featured_edge_out": first[2],
        "mean_edge_in": float(e_in.mean()),
        "mean_edge_out": float(e_out.mean()),
        "share_out_positive": float(np.mean(e_out > 0)),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--rules", type=int, default=30)
    ap.add_argument("--cost-bp", type=float, default=5)
    ap.add_argument("--premium", type=float, default=0.0)
    ap.add_argument("--zero-edge-test", action="store_true")
    a = ap.parse_args()
    if a.zero_edge_test:
        r = run(7, 1, 0, 0.0)
        print(
            f"1-200 alone, no cost, {MARKETS} markets: mean backtest edge {r['mean_edge_in'] * 100:+.2f}%/yr, mean live edge {r['mean_edge_out'] * 100:+.2f}%/yr"
        )
        return
    r = run(a.seed, a.rules, a.cost_bp, a.premium)
    print("tool_check")
    print(
        f"  seed {a.seed}, rules searched {a.rules}, cost {a.cost_bp:g} bp, premium {a.premium:.0%}"
    )
    print(
        f"  featured market winner {r['featured_winner']}: backtest edge {r['featured_edge_in'] * 100:+.2f}%/yr, live edge {r['featured_edge_out'] * 100:+.2f}%/yr"
    )
    print(
        f"  {MARKETS} markets: mean backtest edge of the winner {r['mean_edge_in'] * 100:+.2f}%/yr, mean live edge {r['mean_edge_out'] * 100:+.2f}%/yr, winner beat buy and hold live in {r['share_out_positive'] * 100:.0f}%"
    )


if __name__ == "__main__":
    main()
