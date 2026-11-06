"""Render the guide's hero image: chart-pattern lines drawn on a random walk.

Supports https://summitward.com/learn/does-technical-analysis-work. Needs
numpy and matplotlib.

The prices are simulated: 250 trading days, each built from 26 fifteen-minute
steps of a geometric random walk with 16% annual volatility and 7% annual
drift, so every bar's open, high, low and close come from one consistent path.
The lines are then fitted to that path the way a chart reader would, after the
fact: Fibonacci retracements and extensions between the biggest swing low and
high, trendlines through pivot lows and highs, fan lines from pivots, and
horizontal support and resistance at pivot levels.

    python3 render_random_walk_chart.py [output.png]
"""

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

SEED = 11
DAYS = 250
STEPS = 26
VOL = 0.16
DRIFT = 0.07
START = 100.0
FIB = [0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0, 1.272, 1.618]


def simulate():
    rng = np.random.default_rng(SEED)
    dt = 1 / (252 * STEPS)
    z = rng.standard_normal(DAYS * STEPS)
    logp = np.log(START) + np.cumsum((DRIFT - VOL**2 / 2) * dt + VOL * np.sqrt(dt) * z)
    path = np.exp(np.concatenate([[np.log(START)], logp])).reshape(-1)
    o = np.empty(DAYS)
    h = np.empty(DAYS)
    lo = np.empty(DAYS)
    c = np.empty(DAYS)
    for d in range(DAYS):
        seg = path[d * STEPS : (d + 1) * STEPS + 1]
        o[d], c[d], h[d], lo[d] = seg[0], seg[-1], seg.max(), seg.min()
    return o, h, lo, c


def pivots(h, lo, width=8):
    highs, lows = [], []
    for i in range(width, len(h) - width):
        if h[i] == h[i - width : i + width + 1].max():
            highs.append(i)
        if lo[i] == lo[i - width : i + width + 1].min():
            lows.append(i)
    return highs, lows


def main():
    out = (
        Path(sys.argv[1])
        if len(sys.argv) > 1
        else Path(__file__).resolve().parent
        / "out"
        / "technical-analysis-random-walk.png"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    o, h, lo, c = simulate()
    x = np.arange(DAYS)
    highs, lows = pivots(h, lo)

    fig, ax = plt.subplots(figsize=(12, 6.75), dpi=150)
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")

    up = c >= o
    ax.vlines(
        x, lo, h, color=np.where(up, "#1a7f37", "#b42318"), linewidth=0.7, zorder=3
    )
    ax.bar(
        x,
        np.abs(c - o) + 0.02,
        bottom=np.minimum(o, c),
        width=0.7,
        color=np.where(up, "#1a7f37", "#b42318"),
        zorder=4,
    )

    lo_i = int(np.argmin(lo))
    hi_i = int(np.argmax(h))
    a, b = (lo_i, hi_i) if lo_i < hi_i else (hi_i, lo_i)
    p_low, p_high = lo[lo_i], h[hi_i]
    span = p_high - p_low
    uptrend = lo_i < hi_i
    for f in FIB:
        if f <= 1:
            level = p_high - f * span if uptrend else p_low + f * span
        else:
            level = p_low + f * span if uptrend else p_high - f * span
        ax.axhline(level, color="#1f4fd1", linewidth=0.8, alpha=0.75, zorder=2)
        ax.text(
            DAYS + 1, level, f"{f * 100:.1f}%", fontsize=7, color="#1f4fd1", va="center"
        )

    rng = np.random.default_rng(SEED + 1)
    for i in range(len(lows) - 1):
        for j in range(i + 1, min(i + 4, len(lows))):
            p, q = lows[i], lows[j]
            slope = (lo[q] - lo[p]) / (q - p)
            xs = np.array([p, min(DAYS - 1, q + 60)])
            ax.plot(
                xs,
                lo[p] + slope * (xs - p),
                color="#16a34a",
                linewidth=1.4,
                alpha=0.8,
                zorder=2,
            )
    for i in range(len(highs) - 1):
        for j in range(i + 1, min(i + 4, len(highs))):
            p, q = highs[i], highs[j]
            slope = (h[q] - h[p]) / (q - p)
            xs = np.array([p, min(DAYS - 1, q + 60)])
            ax.plot(
                xs,
                h[p] + slope * (xs - p),
                color="#dc2626",
                linewidth=1.0,
                alpha=0.7,
                zorder=2,
            )

    for p in rng.choice(highs + lows, size=min(6, len(highs + lows)), replace=False):
        base = h[p] if p in highs else lo[p]
        sign = -1 if p in highs else 1
        for k in (0.125, 0.25, 0.5, 1, 2, 4, 8):
            slope = sign * k * span / 120
            xs = np.array([p, DAYS - 1])
            ax.plot(
                xs,
                base + slope * (xs - p),
                color="#ef4444",
                linewidth=0.5,
                alpha=0.6,
                zorder=1,
            )

    for p in highs[::2] + lows[::2]:
        level = h[p] if p in highs else lo[p]
        ax.axhline(
            level, color="#7c3aed", linewidth=0.6, alpha=0.5, linestyle="--", zorder=1
        )

    for p in highs + lows:
        ax.axvline(p, color="#0f766e", linewidth=0.4, alpha=0.4, zorder=1)

    pad = 0.15 * span
    ax.set_ylim(p_low - pad, p_low + 1.7 * span)
    ax.set_xlim(-3, DAYS + 10)
    ax.set_xticks([])
    ax.tick_params(axis="y", labelsize=8)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.text(
        0.01,
        0.98,
        "Simulated random walk. Every line was fitted after the fact.",
        transform=ax.transAxes,
        fontsize=10,
        va="top",
        color="#111827",
        bbox={
            "facecolor": "white",
            "edgecolor": "#9ca3af",
            "boxstyle": "round,pad=0.3",
        },
    )
    fig.tight_layout()
    fig.savefig(out, facecolor="white")
    rets = np.diff(np.log(c))
    print(
        f"wrote {out.name}: {DAYS} days, seed {SEED}, close {c[-1]:.2f}, realized vol {rets.std(ddof=1) * np.sqrt(252) * 100:.1f}%"
    )
    print(
        f"swing low day {lo_i} at {p_low:.2f}, swing high day {hi_i} at {p_high:.2f}; {len(highs)} pivot highs, {len(lows)} pivot lows"
    )


if __name__ == "__main__":
    main()
