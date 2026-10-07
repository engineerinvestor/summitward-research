"""R-squared trap video: overlapping 10-yr windows + valuation regressions in pure-noise worlds.
Renders 1080x1920 @30fps MP4 via ffmpeg pipe.

Usage:
    python3 r2_trap_render.py --stats-only     # print the simulation results and exit
    python3 r2_trap_render.py --preview        # write six preview PNGs
    python3 r2_trap_render.py out.mp4          # render the video (needs ffmpeg)
"""
import sys, subprocess, json
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker
from matplotlib import font_manager as fm

ARGS = [a for a in sys.argv[1:] if not a.startswith("--")]
OUT = ARGS[0] if ARGS else "r2_trap.mp4"
PREVIEW = "--preview" in sys.argv
STATS_ONLY = "--stats-only" in sys.argv

# ---------- style ----------
BG = "#121212"; INK = "#F2F2F0"; INK2 = "#B4B4AE"; MUTED = "#6E6E69"; GRID = "#2A2A28"
BLUE = "#5B8DEF"; ORANGE = "#D9772E"
plt.rcParams.update({"font.family": "Inter", "text.color": INK, "axes.labelcolor": INK2,
                     "xtick.color": MUTED, "ytick.color": MUTED, "axes.edgecolor": GRID,
                     "font.size": 22})
W, H, DPI, FPS = 10.8, 19.2, 100, 30

# ---------- simulation ----------
# Null: monthly log price returns r_t i.i.d. normal (zero predictability by construction).
# log P/E_t = phi*log P/E_{t-1} + (r_t - mu) - e_t   (price shocks pass into P/E; earnings noise e_t)
# phi = 1  -> driftless random-walk log P/E (headline persistent-valuation null)
# phi < 1  -> mean-reverting log P/E sensitivity cases
T, HZ = 477, 120                 # Jan-1987 .. Sep-2026 monthly; 10-yr horizon
N = T - HZ                       # 357 full forward windows
MU, SIG = 0.0075, 0.045          # monthly log-return mean and s.d.
NSIM = 5000

def simulate(phi, n, seed):
    rng = np.random.default_rng(seed)
    r = rng.normal(MU, SIG, (n, T)); e = rng.normal(0, 0.01, (n, T))
    lpe = np.zeros((n, T))
    for t in range(1, T): lpe[:, t] = phi * lpe[:, t - 1] + (r[:, t] - MU) - e[:, t]
    cs = np.concatenate([np.zeros((n, 1)), np.cumsum(r, 1)], 1)
    fwd = np.exp((cs[:, 1 + HZ:1 + HZ + N] - cs[:, 1:1 + N]) * 12 / HZ) - 1   # returns AFTER month i
    x = np.exp(lpe[:, :N])
    xc = x - x.mean(1, keepdims=True); yc = fwd - fwd.mean(1, keepdims=True)
    c = (xc * yc).sum(1) / np.sqrt((xc**2).sum(1) * (yc**2).sum(1))
    return r, lpe, fwd, c

r_all, lpe_all, fwd_all, c_all = simulate(1.0, NSIM, 20261006)
r2s = c_all**2
stats = dict(median=float(np.median(r2s)), gt50=float((r2s > 0.5).mean()),
             ge81=float((r2s >= 0.81).mean()), n81=int((r2s >= 0.81).sum()),
             n81_neg=int(((r2s >= 0.81) & (c_all < 0)).sum()),
             neg_share=float((c_all < 0).mean()))
sens = {}
for phi in (0.997, 0.99):            # half-life ~19.2 yr and ~5.7 yr
    c = simulate(phi, NSIM, 7)[3]; q = c**2
    sens[phi] = dict(median=float(np.median(q)), ge81=float((q >= 0.81).mean()))
print(json.dumps(stats), json.dumps(sens))

# Demo world, predeclared rule: among worlds whose P/E range is history-like (max/min <= 3.5x),
# take the one whose R2 is closest to the 75th percentile of ALL null worlds. No slope screen.
target = np.percentile(r2s, 75)
ratio = np.exp(lpe_all.max(1) - lpe_all.min(1))
cand = np.where(ratio <= 3.5)[0]
dk = cand[np.argmin(np.abs(r2s[cand] - target))]
dr, dlpe, dfwd = r_all[dk], lpe_all[dk], fwd_all[dk]
pe_full = np.exp(dlpe); pe_full *= 13.0 / pe_full.min()       # scale only (R2 invariant)
pe = pe_full[:N]
demo_r2 = float(r2s[dk]); demo_pct = float((r2s < demo_r2).mean())
price = np.exp(np.concatenate([[0], np.cumsum(dr)]))[:T]
months = 1987 + np.arange(T) / 12
b1, b0 = np.polyfit(pe, dfwd, 1)
print("demo", dk, round(demo_r2, 3), round(demo_pct, 3), "slope", round(b1, 4), pe_full.max().round(1))
if STATS_ONLY:
    sys.exit()
IND = [0, 120, 240]

# ---------- helpers ----------
def ease(u): u = min(max(u, 0), 1); return 0.5 - 0.5 * np.cos(np.pi * u)
def fade(t, t0, d=0.4): return min(max((t - t0) / d, 0), 1)
def txt(fig, x, y, s, size, color=INK, weight="regular", a=1.0, ha="center", **kw):
    fig.text(x, y, s, fontsize=size, color=color, fontweight=weight, alpha=a, ha=ha, va="center", **kw)
def style_ax(ax):
    ax.set_facecolor(BG)
    for s in ("top", "right"): ax.spines[s].set_visible(False)
    ax.grid(True, color=GRID, lw=1); ax.set_axisbelow(True)
    ax.tick_params(labelsize=18, length=0, pad=8)
XL = (pe.min() - 1.5, pe.max() + 1.5)
YL = (min(dfwd.min(), b0 + b1 * XL[1]) - 0.02, max(dfwd.max(), b0 + b1 * XL[0]) + 0.02)
def scatter_ax(fig):
    ax = fig.add_axes([0.13, 0.27, 0.80, 0.30]); style_ax(ax)
    ax.set_xlim(*XL); ax.set_ylim(*YL)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0%}"))
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0f}x"))
    ax.set_xlabel("Valuation (P/E) at start of window", fontsize=20, labelpad=12)
    ax.set_ylabel("Next 10-yr return / yr", fontsize=20, labelpad=12)
    ax.axhline(0, color=MUTED, lw=1)
    return ax
def footer(fig, a=1):
    txt(fig, 0.5, 0.045, "@egr_investor  ·  Engineer Investor", 20, MUTED, a=a)

# ---------- scenes ----------
SC = [("hook", 4.0), ("slide", 13.0), ("collapse", 8.0), ("reveal", 7.0), ("hist", 14.0), ("end", 9.0)]
starts = np.cumsum([0] + [d for _, d in SC])
TOTAL = starts[-1]

def k_dots(u):
    if u < 0.3: return max(1, int(14 * u / 0.3) + 1)
    return int(15 + (N - 15) * ease((u - 0.3) / 0.65))

def frame(fig, t):
    i = int(np.searchsorted(starts, t, side="right") - 1); i = min(i, len(SC) - 1)
    name, dur = SC[i]; lt = t - starts[i]; u = lt / dur
    fig.patch.set_facecolor(BG)

    if name == "hook":
        txt(fig, 0.5, 0.66, "A widely shared chart says", 40, INK2, a=fade(lt, 0.0))
        txt(fig, 0.5, 0.585, "R² = 81%", 120, ORANGE, "bold", a=fade(lt, 0.4))
        txt(fig, 0.5, 0.50, "Valuation → next-10-year returns", 32, INK2, a=fade(lt, 0.9))
        txt(fig, 0.5, 0.40, "Here's a market where valuation", 40, INK, "semibold", a=fade(lt, 1.8))
        txt(fig, 0.5, 0.355, "predicts nothing. Watch.", 40, INK, "semibold", a=fade(lt, 1.8))
        footer(fig)

    elif name == "slide":
        k = k_dots(u); j = k - 1
        txt(fig, 0.5, 0.905, "Each dot = one 10-year window", 40, INK, "semibold")
        txt(fig, 0.5, 0.865, "The next dot slides forward just 1 month", 28, INK2)
        ax1 = fig.add_axes([0.13, 0.66, 0.80, 0.15]); style_ax(ax1)
        ax1.plot(months, price, color=INK2, lw=2)
        ax1.set_yscale("log"); ax1.yaxis.set_major_locator(matplotlib.ticker.NullLocator()); ax1.yaxis.set_minor_locator(matplotlib.ticker.NullLocator()); ax1.grid(False)
        ax1.set_xlim(1987, 2026.75); ax1.spines["left"].set_visible(False)
        ax1.axvspan(months[j], months[j] + 10, color=ORANGE, alpha=0.28, lw=0)
        ax1.set_title("Simulated market, 1987–2026", fontsize=20, color=MUTED, loc="left", pad=8)
        ax = scatter_ax(fig)
        ax.scatter(pe[:j], dfwd[:j], s=46, color=BLUE, alpha=0.75, lw=0)
        ax.scatter([pe[j]], [dfwd[j]], s=200, color=ORANGE, edgecolor=BG, lw=2, zorder=5)
        txt(fig, 0.5, 0.165, f"dot #{k}", 34, INK, "semibold")
        if k > 1:
            txt(fig, 0.5, 0.12, "shares 119 of its 120 months with the dot before it", 25, ORANGE)
        footer(fig)

    elif name == "collapse":
        f = ease(lt / 1.5)
        txt(fig, 0.5, 0.905, f"{N} dots…", 48, INK, "semibold")
        txt(fig, 0.5, 0.855, "but how many don't overlap at all?", 32, INK2, a=fade(lt, 0.8))
        ax = scatter_ax(fig)
        ax.scatter(pe, dfwd, s=46, color=BLUE, alpha=0.75 * (1 - 0.88 * f), lw=0)
        ax.scatter(pe[IND], dfwd[IND], s=60 + 340 * f, color=ORANGE, edgecolor=BG, lw=2, zorder=5)
        for n, idx in enumerate(IND):
            y0 = 1987 + idx // 12
            ox, oy, ha = [(0, -40, "center"), (0, 28, "center"), (0, -40, "center")][n]
            ax.annotate(f"{y0}–{y0 + 10}", (pe[idx], dfwd[idx]), xytext=(ox, oy), textcoords="offset points",
                        ha=ha, fontsize=20, color=INK, alpha=fade(lt, 1.6 + 0.3 * n))
        txt(fig, 0.5, 0.17, "3", 110, ORANGE, "bold", a=fade(lt, 2.6))
        txt(fig, 0.5, 0.095, "fully non-overlapping 10-year windows", 32, INK, a=fade(lt, 2.9))
        footer(fig)

    elif name == "reveal":
        txt(fig, 0.5, 0.905, "Plot twist:", 44, ORANGE, "bold")
        txt(fig, 0.5, 0.855, "returns here are pure random draws", 36, INK, "semibold")
        txt(fig, 0.5, 0.815, "Valuation has zero predictive power by construction", 24, INK2, a=fade(lt, 0.8))
        ax = scatter_ax(fig)
        ax.scatter(pe, dfwd, s=46, color=BLUE, alpha=0.75, lw=0)
        g = ease((lt - 1.5) / 1.5); xs = np.linspace(XL[0], XL[0] + (XL[1] - XL[0]) * g, 50)
        if g > 0: ax.plot(xs, b0 + b1 * xs, color=ORANGE, lw=4, zorder=4)
        txt(fig, 0.5, 0.17, f"R² = {demo_r2:.0%}", 80, ORANGE, "bold", a=fade(lt, 3.0))
        txt(fig, 0.5, 0.11, "Looks like a law of nature. It isn't.", 28, INK, a=fade(lt, 3.6))
        txt(fig, 0.5, 0.075, "Illustrative draw near the 75th percentile, restricted to a plausible P/E range", 18, MUTED, a=fade(lt, 3.6))
        footer(fig)

    elif name == "hist":
        txt(fig, 0.5, 0.905, f"{NSIM:,} worlds, zero predictability", 42, INK, "semibold")
        txt(fig, 0.5, 0.86, "Random (i.i.d.) returns · random-walk log P/E", 28, INK2)
        n = max(30, int(NSIM * ease(lt / 6.0)))
        ax = fig.add_axes([0.13, 0.43, 0.80, 0.33]); style_ax(ax)
        bins = np.linspace(0, 1, 41)
        ax.hist(r2s[:n], bins=bins, color=BLUE, edgecolor=BG, lw=2)
        ymax = np.histogram(r2s, bins=bins)[0].max() * 1.15
        ax.set_ylim(0, ymax); ax.set_xlim(0, 1); ax.set_yticks([])
        ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0%}"))
        ax.set_xlabel("In-sample R² from each world", fontsize=20, labelpad=12)
        txt(fig, 0.93, 0.78, f"worlds: {n:,}", 20, MUTED, ha="right")
        a1 = fade(lt, 6.5)
        if a1 > 0:
            ax.axvline(0.81, color=ORANGE, lw=4, alpha=a1)
            ax.text(0.83, ymax * 0.95, "the\nshared\nchart", ha="left", va="top", fontsize=20, color=INK, alpha=a1)
        rows = [(f"{stats['median']:.0%}", "median in-sample R²", 7.5),
                (f"{stats['gt50']:.0%}", "of worlds beat R² = 50%", 8.7),
                (f"{stats['ge81']:.1%}", "reach R² ≥ 81%", 9.9)]
        for m, (big, small, t0) in enumerate(rows):
            y = 0.335 - m * 0.065
            txt(fig, 0.37, y, big, 44, ORANGE, "bold", a=fade(lt, t0), ha="right")
            txt(fig, 0.41, y, small, 26, INK, a=fade(lt, t0), ha="left")
        lo_m, hi_m = sens[0.99]["median"], sens[0.997]["median"]
        hi81 = max(v["ge81"] for v in sens.values())
        txt(fig, 0.5, 0.15, f"If log P/E mean-reverts (half-life 6–19 yrs): median {lo_m:.0%}–{hi_m:.0%},",
            21, INK2, a=fade(lt, 11.0))
        txt(fig, 0.5, 0.125, f"and R² ≥ 81% drops to ≤{hi81:.1%}.", 21, INK2, a=fade(lt, 11.0))
        txt(fig, 0.5, 0.085, "Results depend on the assumed valuation process.", 27, INK, "semibold", a=fade(lt, 11.6))
        footer(fig)

    elif name == "end":
        txt(fig, 0.5, 0.76, "Valuations matter.", 50, INK, "bold", a=fade(lt, 0))
        txt(fig, 0.5, 0.69, f"But {N} overlapping dots aren't", 36, INK2, a=fade(lt, 0.8))
        txt(fig, 0.5, 0.65, f"{N} independent experiments.", 36, INK2, a=fade(lt, 0.8))
        txt(fig, 0.5, 0.56, "R² = 81% ≠ 81% predictable", 40, ORANGE, "bold", a=fade(lt, 1.8))
        txt(fig, 0.5, 0.50, "Even with zero predictability, persistent valuations", 26, INK, a=fade(lt, 2.8))
        txt(fig, 0.5, 0.47, "+ overlapping windows can produce high in-sample R².", 26, INK, a=fade(lt, 2.8))
        txt(fig, 0.5, 0.43, f"In these null simulations, median R² = {sens[0.99]['median']:.0%}–{stats['median']:.0%}.", 26, ORANGE, a=fade(lt, 3.2))
        txt(fig, 0.5, 0.385, "The evidence is far less precise than the picture.", 26, INK, "semibold", a=fade(lt, 3.8))
        txt(fig, 0.5, 0.33, "summitward.com/learn/r-squared-trap", 28, BLUE, "semibold", a=fade(lt, 4.2))
        m1 = fade(lt, 4.6)
        txt(fig, 0.5, 0.235, f"Method: {NSIM:,} simulated 1987–2026 monthly markets; i.i.d. price returns", 16, MUTED, a=m1)
        txt(fig, 0.5, 0.213, "(~9%/yr, ~16% vol), so valuation has zero population forecasting power.", 16, MUTED, a=m1)
        txt(fig, 0.5, 0.191, "P/E shares price shocks; earnings add noise. 10-yr forward windows, monthly steps.", 16, MUTED, a=m1)
        footer(fig)

# ---------- render ----------
fig = plt.figure(figsize=(W, H), dpi=DPI)
if PREVIEW:
    for name_t in [2.5, 15.0, 24.0, 30.5, 44.5, 53.5]:
        fig.clf(); frame(fig, name_t); fig.savefig(f"preview_{name_t:04.1f}.png", facecolor=BG)
    sys.exit()
nf = int(TOTAL * FPS)
ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgba",
                       "-s", f"{int(W*DPI)}x{int(H*DPI)}", "-r", str(FPS), "-i", "-",
                       "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-preset", "medium",
                       "-movflags", "+faststart", OUT], stdin=subprocess.PIPE)
for f in range(nf):
    fig.clf(); frame(fig, f / FPS); fig.canvas.draw()
    ff.stdin.write(fig.canvas.buffer_rgba().tobytes())
ff.stdin.close(); ff.wait()
print("done", nf, "frames")
