"""9:16 educational short on tax-aware long-short (TALS), final.
All simulator numbers are read from talsim v0.5.0 pinned-CI result CSVs.
Usage: python tals_short_render.py <talsim/docs/results> <out.mp4> [start end]
       python tals_short_render.py <talsim/docs/results> --stats-only"""
import subprocess, sys
import numpy as np, pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm

ARGS = [a for a in sys.argv[1:] if not a.startswith("--")]
RES, OUT = ARGS[0], (ARGS[1] if len(ARGS) > 1 else "tals_short.mp4")
FPS = 30
BOOKS = ["100/0", "130/30", "150/50", "200/100", "250/150"]

sw = pd.read_csv(f"{RES}/leverage_sweep.csv").set_index("book")
sc = pd.read_csv(f"{RES}/scenario_comparison.csv")
L = sw.loc[BOOKS, "gross_losses_realized_median"].values
B = sw.loc[BOOKS, "tax_benefit_used_median"].values
LX, BX = L[-1] / L[0], B[-1] / B[0]
assert round(LX, 1) == 8.6 and round(BX, 1) == 2.1  # README v0.5 table


def scen(name):
    return sc[sc.scenario == name].set_index("book").loc[BOOKS[1:]]


base = scen("Annual $100k ST gains, zero alpha")
alph = scen("Annual $100k ST gains, +75 bps alpha")
D0 = base.wealth_diff_vs_baseline_median.values  # paired (common random numbers)
DA = alph.wealth_diff_vs_baseline_median.values
PA = alph.prob_beats_baseline.values
# guard against the v2 mistake: only 200/100 has a positive paired median with alpha
assert (D0 < 0).all() and DA[2] > 0 and (np.delete(DA, 2) < 0).all()
ST, LT = 0.408, 0.238  # talsim defaults: 37% + 3.8% NIIT; 20% + 3.8% NIIT

if "--stats-only" in sys.argv:
    print(f"losses {LX:.2f}x  tax benefit {BX:.2f}x  (250/150 vs 100/0)")
    for b, d0, da, pa in zip(BOOKS[1:], D0, DA, PA):
        print(f"{b:>8}  zero alpha {d0:>10,.0f}  +75bp alpha {da:>10,.0f}  P(beats 100/0) {pa:.2f}")
    sys.exit()

for f in fm.findSystemFonts():
    if "Inter" in f:
        fm.fontManager.addfont(f)
plt.rcParams["font.family"] = "Inter"
plt.rcParams["text.parse_math"] = False
BG, FG, MUTED = "#0b0f14", "#f2f5f7", "#9aa5b1"
TEAL, ORANGE, RED, GREEN, BLUE = "#3ccfc4", "#f2a541", "#ff5a5f", "#58d68d", "#6aa9ff"
fig = plt.figure(figsize=(10.8, 19.2), dpi=100)
fig.patch.set_facecolor(BG)

# Layout keeps everything above ~y=0.19 (Shorts/Reels bottom overlay) and
# inside x 0.06-0.86 for key content (right-side action buttons).
FOOT_Y = 0.205


def ease(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


def fade(t, a, b, d=0.4):
    return min(ease((t - a) / d), ease((b - t) / d))


def appear(t, s, d=0.4):
    return ease((t - s) / d)


def txt(x, y, s, size, a=1.0, color=FG, weight="bold", ha="center", **kw):
    if a > 0:
        fig.text(x, y, s, size=size, color=color, alpha=a, weight=weight, ha=ha, va="center", **kw)


def money(v):
    s = "−" if v < 0 else "+"
    v = abs(v)
    return s + (f"${v/1e6:.2f}M" if v >= 1e6 else f"${v/1e3:.0f}k")


def money_abs(v):
    return f"${v/1e6:.2f}M" if v >= 1e6 else f"${v/1e3:.0f}k"


def block_left(lines, size, cx, weight="bold"):
    """left x so a left-aligned block of lines is centered on cx"""
    r = fig.canvas.get_renderer()
    w = 0
    for s in lines:
        tt = fig.text(0, 0, s, size=size, weight=weight)
        w = max(w, tt.get_window_extent(r).width)
        tt.remove()
    return cx - w / 2 / fig.bbox.width

def blank_ax(rect):
    ax = fig.add_axes(rect)
    ax.set_facecolor(BG)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_xticks([]); ax.set_yticks([])
    return ax


def title(t, a, head, sub=None):
    txt(0.47, 0.885, head, 56 if len(head) < 24 else 42, a)
    if sub:
        txt(0.47, 0.85, sub, 28, a, MUTED, "regular")


# ---- 1. hook (0-4)
def s1(t):
    a = fade(t, 0, 4)
    txt(0.47, 0.64, "Can a portfolio realize", 56, a)
    txt(0.47, 0.60, "tax losses when the", 56, a)
    txt(0.47, 0.56, "market goes UP?", 56, a, TEAL)
    txt(0.47, 0.45, "A long-short one can.", 46, fade(t, 1.8, 4))
    txt(0.47, 0.41, "Tax-aware long-short (TALS) ↓", 34, fade(t, 1.8, 4), MUTED, "medium")


# ---- 2+3. structure + mechanism (4-20)
rng = np.random.default_rng(3)
N = 14
paths = np.cumsum(rng.normal(0, 0.035, (200, N)), axis=0)
paths -= paths[0]
paths += np.outer(np.linspace(0, 1, 200), np.linspace(-0.25, 0.25, N))
paths = paths[:, np.argsort(rng.normal(size=N))]
paths *= 0.6 / np.abs(paths).max()
short_mask = np.zeros(N, bool)
short_mask[[1, 6, 10, 12]] = True
T0, T1 = 4.0, 20.0
CAPS = [
    (4.0, 8.0, "$100 → $130 long + $30 short", "$160 gross · $100 net dollar exposure"),
    (8.0, 11.0, "Equity-like market exposure", "plus active long-short bets"),
    (11.0, 13.6, "Long stocks that fell?", "Sell → realized loss"),
    (13.6, 16.2, "Shorted stocks that ROSE?", "Cover → realized loss too"),
    (16.2, 18.4, "Shift exposure elsewhere", "avoid substantially identical securities"),
    (18.4, 20.0, "And just as important:", "deferring gains when possible"),
]


def s2(t):
    a = fade(t, T0, T1)
    if a <= 0:
        return
    ax = blank_ax([0.08, 0.36, 0.78, 0.36])
    i = int(np.clip((t - T0) / 12 * 199, 1, 199))
    ax.axhline(0, color=MUTED, lw=1.5, ls="--", alpha=0.6 * a)
    ax.text(N - 0.3, 0.0, "entry\nprice", color=MUTED, size=20, alpha=a, ha="left", va="center")
    show_short = t >= 4.8
    for j in range(N):
        y = paths[i, j]
        is_short = short_mask[j] and show_short
        col = ORANGE if is_short else TEAL
        lossy = (y < 0 and not is_short) or (y > 0 and is_short)
        hl = (t >= 11.0 and lossy and not is_short) or (t >= 13.6 and lossy and is_short)
        c = RED if hl else col
        ax.plot([j, j], [0, y], color=c, lw=10, alpha=a * (1 if hl else 0.85), solid_capstyle="round")
        ax.scatter([j], [y], s=260, color=c, alpha=a, zorder=3)
        if hl and t >= 16.2:
            ax.scatter([j], [y], s=900, facecolor="none", edgecolor=FG, lw=2.5, alpha=a, zorder=4)
    ax.set_xlim(-0.8, N + 1.0); ax.set_ylim(-0.75, 0.75)
    title(t, a, "Where the tax losses come from", "When the strategy trades, from BOTH sides")
    txt(0.30, 0.79, "● long", 30, a, TEAL)
    txt(0.64, 0.79, "● short", 30, a if show_short else 0, ORANGE)
    txt(0.47, 0.755, "price move since entry", 24, a, MUTED, "regular")
    for (s, e, l1, l2) in CAPS:
        ca = min(a, fade(t, s, e, 0.3))
        txt(0.47, 0.31, l1, 44 if len(l1) > 24 else 50, ca)
        hi = ("loss" in l2) or ("gains" in l2)
        txt(0.47, 0.268, l2, 32 if len(l2) > 34 else 40, ca, TEAL if hi else MUTED, "medium")
    txt(0.47, 0.232, "Wash-sale rules apply to shorts too", 22,
        min(a, fade(t, 16.2, 18.4, 0.3)), MUTED, "regular")


# ---- 4. mostly deferral (20-33)
def s3(t):
    a = fade(t, 20, 33)
    if a <= 0:
        return
    title(t, a, "Mostly deferral,", None)
    txt(0.47, 0.845, "not free money", 56, a, ORANGE)
    rows = [
        (20.5, 0.745, "TODAY", "$100 short-term capital loss offsets", "a $100 short-term capital gain",
         f"up to ${ST*100:.2f} less federal tax", GREEN),
        (23.0, 0.585, "LATER", "Harvesting can leave more embedded gain.", "If $100 is realized as long-term gain:",
         f"up to ${LT*100:.2f} federal tax", ORANGE),
    ]
    for s, y, tag, l1, l1b, l2, c in rows:
        ra = min(a, appear(t, s))
        txt(0.47, y + 0.035, tag, 30, ra, c)
        txt(0.47, y, l1, 32, ra, FG, "medium")
        txt(0.47, y - 0.028, l1b, 32, ra, FG, "medium")
        txt(0.47, y - 0.068, l2, 46, ra, c)
    ca = min(a, appear(t, 26.0))
    txt(0.47, 0.425, "Value can come from:", 34, ca, MUTED, "medium")
    lines = ["① paying later", "② possibly at a lower rate", "③ possibly never, via §1014 step-up*"]
    x0 = block_left(lines, 34, 0.47)
    for k, s in enumerate(lines):
        txt(x0, 0.38 - k * 0.04, s, 34, min(a, appear(t, 26.6 + 0.9 * k)), ha="left")
    txt(0.47, 0.25, "Illustrative top 2026 federal rates, assuming NIIT applies.", 23, a, MUTED, "regular")
    txt(0.47, 0.23, "*Eligible property: IRC §1014, current law.", 23, a, MUTED, "regular")


# ---- 5. in this simulation: losses vs tax used (33-42)
def s4(t):
    a = fade(t, 33, 42)
    if a <= 0:
        return
    txt(0.47, 0.895, "In this simulation:", 34, a, MUTED, "medium")
    txt(0.47, 0.86, "more leverage, more losses", 52, a)
    for vals, color, head, mult, gg, y0 in [
        (L, RED, "Gross losses realized", LX, ease((t - 33.5) / 2.2), 0.58),
        (B, GREEN, "Tax benefit actually used", BX, ease((t - 36.0) / 2.2), 0.32),
    ]:
        ax = blank_ax([0.08, y0, 0.78, 0.18])
        ax.bar(range(5), vals * gg, color=color, alpha=a, width=0.62)
        ax.set_ylim(0, vals.max() * 1.3)
        ax.set_xticks(range(5), BOOKS)
        ax.tick_params(colors=FG, labelsize=22, length=0)
        for lab in ax.get_xticklabels():
            lab.set_alpha(a)
        if gg > 0.95:
            for k, v in enumerate(vals):
                ax.text(k, v * 1.04, money_abs(v), ha="center", va="bottom", color=FG, size=21,
                        weight="bold", alpha=a)
        txt(0.47, y0 + 0.215, head, 38, a if gg > 0 else 0, color)
        txt(0.25, y0 + 0.12, f"{mult:.1f}×", 76, a * ease((gg - 0.9) / 0.1), color)
    ca = min(a, appear(t, 38.6))
    txt(0.47, 0.262, "Harvested losses ≠ tax savings", 34, ca)
    txt(0.47, 0.225, "talsim v0.5 · synthetic · zero alpha · $1M · 10 yrs · 200 paths", 22, a, MUTED, "regular")
    txt(0.47, 0.207, "$100k/yr outside short-term gains · medians", 22, a, MUTED, "regular")


# ---- 6. did leverage pay? paired differences (42-53)
def s5(t):
    a = fade(t, 42, 53)
    if a <= 0:
        return
    txt(0.47, 0.885, "Did leverage pay?", 56, a)
    txt(0.47, 0.85, "Median paired difference vs long-only,", 28, a, MUTED, "regular")
    txt(0.47, 0.826, "after-tax wealth after full liquidation", 28, a, MUTED, "regular")
    ax = fig.add_axes([0.16, 0.44, 0.70, 0.34])
    ax.set_facecolor(BG)
    for s in ["top", "right", "bottom"]:
        ax.spines[s].set_visible(False)
    ax.spines["left"].set_color(MUTED)
    ax.tick_params(colors=FG, labelsize=22, length=0)
    x = np.arange(4)
    g0, g1 = ease((t - 42.6) / 2.0), ease((t - 45.4) / 2.0)
    w = 0.36
    ax.bar(x - w / 2, D0 / 1e3 * g0, w, color=MUTED, alpha=a)
    ax.bar(x + w / 2, DA / 1e3 * g1, w, color=TEAL, alpha=a)
    ax.axhline(0, color=FG, lw=2, alpha=a)
    ax.set_ylim(-230, 60)
    ax.set_xlim(-0.6, 3.6)
    ax.set_xticks(x, BOOKS[1:])
    ax.xaxis.set_ticks_position("top")
    ax.set_yticks([-200, -100, 0], ["−$200k", "−$100k", "$0"])
    for lab in ax.get_xticklabels() + ax.get_yticklabels():
        lab.set_alpha(a)
    txt(0.30, 0.415, "■ zero alpha", 28, a * (g0 > 0), MUTED)
    txt(0.66, 0.415, "■ +0.75%/yr alpha", 28, a * (g1 > 0), TEAL)
    c1 = min(a, appear(t, 47.6))
    txt(0.47, 0.37, "Zero alpha: negative median edge", 32, c1)
    txt(0.47, 0.343, "after costs + liquidation", 26, c1, MUTED, "regular")
    c2 = min(a, appear(t, 49.4))
    txt(0.47, 0.305, "+0.75% alpha: roughly a wash", 32, c2, TEAL)
    txt(0.47, 0.276, f"beat long-only in {PA.min()*100:.0f}–{PA.max()*100:.0f}% of paths", 28, c2, MUTED, "regular")
    txt(0.47, 0.23, "talsim v0.5 · synthetic · $1M · 10 yrs · 100 paired paths", 22, a, MUTED, "regular")
    txt(0.47, 0.212, "$100k/yr outside short-term gains", 22, a, MUTED, "regular")


# ---- 7. close (53-58.5)
def s6(t):
    a = fade(t, 53, 58.6)
    if a <= 0:
        return
    txt(0.47, 0.66, "Harvested losses", 50, a)
    txt(0.47, 0.62, "measure activity.", 50, a)
    txt(0.47, 0.55, "After-tax wealth", 50, a, TEAL)
    txt(0.47, 0.51, "measures what you keep.", 50, a, TEAL)
    txt(0.47, 0.40, "Open-source simulator:", 30, a, MUTED, "medium")
    txt(0.47, 0.36, "pip install pytalsim", 38, a, FG, family="DejaVu Sans Mono")
    txt(0.47, 0.32, "github.com/engineerinvestor/talsim", 28, a, FG, "medium")


def footer(t):
    if 33 <= t < 53:
        return  # sim scenes carry their own footnotes in the same band
    txt(0.47, FOOT_Y, "Educational only · not tax or investment advice", 22, 0.85, MUTED, "regular")


DUR = 58.5
proc = subprocess.Popen(
    ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", "1080x1920",
     "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18",
     "-preset", "medium", "-movflags", "+faststart", OUT], stdin=subprocess.PIPE)
start, stop = (float(x) for x in (ARGS[2:4] if len(ARGS) > 3 else (0, DUR)))
for f in range(int(start * FPS), int(stop * FPS)):
    t = f / FPS
    fig.clf()
    for scene in (s1, s2, s3, s4, s5, s6):
        scene(t)
    footer(t)
    fig.canvas.draw()
    proc.stdin.write(fig.canvas.buffer_rgba().tobytes())
proc.stdin.close(); proc.wait()
print("done", OUT)
