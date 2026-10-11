"""9:16 short: most stocks lose to T-bills, the market still wins.
Real numbers: Bessembinder (2026), "One Hundred Years in the U.S. Stock Markets", SSRN 6438198.
Simulation: computed live below.
Usage: python skew_short_render.py out.mp4 [start end]
       python skew_short_render.py --vo out.mp4    # timed to the published voiceover (67.6 s)
       python skew_short_render.py --stats-only"""
import subprocess, sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm

ARGS = [a for a in sys.argv[1:] if not a.startswith("--")]
OUT = ARGS[0] if ARGS else "skew_short.mp4"
VO = "--vo" in sys.argv
FPS = 30

# ---- real data (Bessembinder 2026, 1926-2025)
N_STOCKS, PCT_BELOW_TB, MEDIAN_LIFE = 29754, 59, -6.9
WEALTH_T, TOP_HALF, TOP_ALL, TOP_ALL_PCT = 91, 46, 1082, 3.7
TOP_HALF_PCT = TOP_HALF / 29081 * 100  # 29,081 firms

# ---- simulation: identical stocks, idiosyncratic risk only
N, YEARS = 1000, 20
M = YEARS * 12
VOL, EXP_RET, RF = 0.40, 0.10, 0.03
rng = np.random.default_rng(1)  # first seed tried; across seeds 1-100, 56% below T-bills on average
m = (1 + EXP_RET) ** (1 / 12) - 1
r = np.maximum(m + rng.normal(0, VOL / np.sqrt(12), (N, M)), -0.99)
W = np.concatenate([np.ones((N, 1)), np.cumprod(1 + r, axis=1)], axis=1)
END = W[:, -1]
TB = (1 + RF) ** (np.arange(M + 1) / 12)
TB_END = TB[-1]
PORT = W.mean(axis=0)  # equal dollars in every stock at the start, then hold
MED = np.median(END)
MED_IDX = int(np.argsort(END)[N // 2])
BELOW = np.mean(END < TB_END)
assert PORT[-1] > TB_END and MED < TB_END  # what the narration claims; true for all 100 seeds tested
STATS = (f"below {BELOW:.3f} median {MED:.2f} port {PORT[-1]:.2f} tb {TB_END:.2f} "
         f"max {END.max():.0f} med_idx_end {W[MED_IDX, -1]:.2f}")
if "--stats-only" in sys.argv:
    print(STATS)
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
CX = 0.5


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


def head(a, h, sub=None):
    txt(CX, 0.885, h, 52 if len(h) < 24 else 44, a)
    if sub:
        txt(CX, 0.85, sub, 28 if len(sub) < 50 else 25, a, MUTED, "regular")


def axes(rect, a, spines=("left", "bottom")):
    ax = fig.add_axes(rect)
    ax.set_facecolor(BG)
    for s in ["top", "right", "left", "bottom"]:
        ax.spines[s].set_visible(s in spines)
        ax.spines[s].set_color(MUTED); ax.spines[s].set_alpha(a)
    ax.tick_params(colors=FG, labelsize=22, length=0)
    return ax


def note(lines, a):
    for k, s in enumerate(lines):
        txt(CX, 0.245 - k * 0.021, s, 20, a * 0.95, MUTED, "regular")


REAL_NOTE = ["Bessembinder (2026), \"One Hundred Years in the U.S. Stock Markets\"",
             f"{N_STOCKS:,} U.S. stocks, 1926–2025 · wealth measured above 1-month T-bills"]
SIM_NOTE = [f"{N:,} made-up stocks: {EXP_RET:.0%}/yr expected vs {RF:.0%} cash, {VOL:.0%} vol, {YEARS} yrs",
            "Stock-specific risk only. Not calibrated to the historical data."]


# ---- 1. hook (0-5)
def s1(t):
    a = fade(t, 0, 5)
    txt(CX, 0.66, "Most stocks lost", 84, a)
    txt(CX, 0.608, "to Treasury bills.", 84, a, RED)
    txt(CX, 0.49, "The stock market still won.", 56, fade(t, 1.8, 5), TEAL)
    txt(CX, 0.445, "Here's how both are true.", 36, fade(t, 2.6, 5), MUTED, "medium")


# ---- 2. dot grid (5-15)
def s2(t):
    a = fade(t, 5, 15)
    if a <= 0:
        return
    head(a, "A century of U.S. stocks", "29,081 firms, 1926–2025 · each dot = 1% of firms")
    ax = axes([0.16, 0.44, 0.68, 0.38], a, spines=())
    k = np.arange(100)
    xs, ys = k % 10, 9 - k // 10
    lit = int(ease((t - 6.0) / 2.5) * PCT_BELOW_TB)
    cols = [RED if i < lit else TEAL for i in k]
    ax.scatter(xs, ys, s=1500, c=cols, alpha=a, marker="s", lw=0)
    ax.set_xlim(-0.7, 9.7); ax.set_ylim(-0.7, 9.7)
    ax.set_xticks([]); ax.set_yticks([])
    c = min(a, appear(t, 8.6))
    txt(CX, 0.39, f"{PCT_BELOW_TB}% did worse than T-bills", 44, c, RED)
    txt(CX, 0.355, "over their listed lifetime", 30, c, MUTED, "medium")
    c2 = min(a, appear(t, 11.0))
    txt(CX, 0.305, f"Median stock's lifetime return: {MEDIAN_LIFE}%", 36, c2)
    txt(CX, 0.272, "total over its listed life, not per year", 24, c2, MUTED, "regular")
    note(REAL_NOTE, a)


# ---- 3. concentration (15-25)
def s3(t):
    a = fade(t, 15, 25)
    if a <= 0:
        return
    head(a, "Yet the market made", None)
    txt(CX, 0.83, f"${WEALTH_T} trillion", 96, a, TEAL)
    txt(CX, 0.785, "above T-bills", 34, a, MUTED, "medium")
    rows = [(16.6, f"Top {TOP_HALF} firms", f"{TOP_HALF_PCT:.2f}%", 50, "50%"),
            (19.2, f"Top {TOP_ALL:,} firms", f"{TOP_ALL_PCT}%", 100, "100%")]
    for k, (s, name, pct, share, lab) in enumerate(rows):
        ra = min(a, appear(t, s))
        y0 = 0.62 - k * 0.17
        txt(CX, y0 + 0.055, f"{name} ({pct}) = {lab} of net wealth", 34, ra)
        g = ease((t - s - 0.3) / 1.4)
        ax = axes([0.12, y0 - 0.05, 0.76, 0.07], ra, spines=())
        ax.barh([1], [100], color=MUTED, alpha=0.18 * ra, height=0.7)
        ax.barh([1], [share * g], color=TEAL, alpha=ra, height=0.7)
        ax.set_xlim(0, 100); ax.set_ylim(0.4, 1.6)
        ax.set_xticks([]); ax.set_yticks([])
        txt(CX, y0 - 0.075, "share of the $91T net wealth above T-bills", 24, ra, MUTED, "regular")
    c = min(a, appear(t, 21.6))
    txt(CX, 0.29, "Everyone else netted out to about zero.", 32, c)
    note(REAL_NOTE, a)


# ---- 4. why: sorted outcomes (25-39)
ORDER = np.argsort(END)


def s4(t):
    a = fade(t, 25, 39)
    if a <= 0:
        return
    head(a, "Why? Skew from compounding", "SIMULATION · an illustration, not the historical data")
    ax = axes([0.12, 0.44, 0.76, 0.36], a)
    g = ease((t - 25.6) / 3.2)
    vals = END[ORDER]
    n = int(g * N)
    ax.bar(np.arange(n), vals[:n], width=1.0, color=np.where(vals[:n] < TB_END, RED, TEAL), alpha=a, lw=0)
    ax.axhline(TB_END, color=FG, lw=2, ls="--", alpha=a)
    z = ease((t - 33.0) / 2.2)
    top = 40 + z * (END.max() * 1.08 - 40)
    ax.set_xlim(0, N); ax.set_ylim(0, top)
    ax.set_xticks([0, N // 2, N], ["worst", "median", "best"])
    step = 10 if top < 70 else 50
    yt = np.arange(0, top, step)
    ax.set_yticks(yt, [f"{v:.0f}×" for v in yt])
    for lab in ax.get_xticklabels() + ax.get_yticklabels():
        lab.set_alpha(a)
    ax.text(30, TB_END + top * 0.025, f"T-bills: {TB_END:.2f}×", color=FG, size=22, weight="bold", alpha=a * (1 - z))
    if z > 0.9:
        ax.annotate(f"best: {END.max():.0f}×", (N - 1, END.max()), xytext=(N * 0.55, END.max() * 0.92), color=TEAL,
                    size=26, weight="bold", alpha=a, arrowprops=dict(arrowstyle="->", color=TEAL, lw=2))
    txt(CX, 0.825, "Each bar = one stock's ending value of $1", 26, a, MUTED, "medium")
    c = min(a, appear(t, 29.4))
    txt(CX, 0.39, "Same expected return. Wildly different luck.", 34, c)
    c2 = min(a, appear(t, 31.6))
    txt(CX, 0.35, f"{BELOW:.0%} finished below T-bills. Median: {MED:.2f}×", 30, c2, RED, "medium")
    c3 = min(a, appear(t, 35.2))
    txt(CX, 0.315, "Zoom out: a handful dwarf everything else.", 30, c3, TEAL, "medium")
    txt(CX, 0.278, "A stock can lose 100% at most. It can gain far more.", 26, min(a, appear(t, 36.4)), MUTED, "regular")
    note(SIM_NOTE, a)


# ---- 5. diversification (39-50)
def s5(t):
    a = fade(t, 39, 50)
    if a <= 0:
        return
    head(a, "Own them all", f"SIMULATION · $1 in each of the {N:,} stocks, then hold")
    ax = axes([0.15, 0.44, 0.70, 0.36], a)
    k = ease((t - 39.6) / 3.5) * M
    n = int(k) + 1
    x = np.arange(M + 1) / 12
    ax.plot(x[:n], PORT[:n], color=TEAL, lw=6, alpha=a)
    ax.plot(x[:n], TB[:n], color=FG, lw=3, ls="--", alpha=a)
    ax.plot(x[:n], W[MED_IDX, :n], color=RED, lw=3, alpha=a)
    ax.set_xlim(0, YEARS); ax.set_ylim(0, 7)
    ax.set_xticks([0, 5, 10, 15, 20], ["0", "5", "10", "15", "20 yrs"])
    ax.set_yticks([0, 2, 4, 6], ["0×", "2×", "4×", "6×"])
    for lab in ax.get_xticklabels() + ax.get_yticklabels():
        lab.set_alpha(a)
    c = min(a, appear(t, 43.4))
    for j, (lab, val, col) in enumerate([("all 1,000", PORT[-1], TEAL), ("T-bills", TB_END, FG),
                                         ("median stock", W[MED_IDX, -1], RED)]):
        txt(0.2 + 0.3 * j, 0.395, f"{val:.2f}×", 52, c, col)
        txt(0.2 + 0.3 * j, 0.36, lab, 26, c, MUTED, "medium")
    txt(CX, 0.305, "Holding everything included the rare winners.", 32, min(a, appear(t, 45.4)))
    txt(CX, 0.272, "Equal-weight buy-and-hold, no rebalancing", 24, min(a, appear(t, 45.4)), MUTED, "regular")
    note(SIM_NOTE, a)


# ---- 6. close (50-58)
def s6(t):
    a = fade(t, 50, 58.5)
    if a <= 0:
        return
    txt(CX, 0.70, "A broad-market index fund", 44, a)
    txt(CX, 0.664, "doesn't guarantee beating cash.", 44, a)
    c = min(a, appear(t, 51.8))
    txt(CX, 0.58, "But you don't have to find", 50, c, TEAL)
    txt(CX, 0.54, "the next giant to own it.", 50, c, TEAL)
    c2 = min(a, appear(t, 53.8))
    txt(CX, 0.45, "Real markets can still trail cash for a decade.", 30, c2, MUTED, "medium")
    txt(CX, 0.37, "Full explanation: summitward.com", 32, c2, FG, "medium")
    note(["Data: Bessembinder (2026), SSRN 6438198",
          "Simulation shows skew from compounding, not why stocks beat cash"], a)


def footer(t):
    txt(CX, 0.19, "Educational only · not investment advice", 22, 0.85, MUTED, "regular")


DUR = 58.5
A = V = None
if VO:
    # audio time -> scene time, anchored to sentence starts in the published voiceover
    A = [0, 3.0, 6.8, 7.1, 13.8, 20.03, 23.5, 30.25, 33.58, 34.0, 35.73, 40.98, 44.0, 46.4, 46.84,
         50.99, 55.0, 57.76, 63.0, 64.5, 66.35, 67.6]
    V = [0, 1.8, 4.6, 5.0, 8.6, 11.0, 15.0, 16.6, 24.0, 25.2, 25.6, 29.4, 33.0, 36.6, 39.0,
         43.4, 45.4, 50.0, 51.8, 53.8, 57.5, 58.5]
    assert all(np.diff(A) > 0) and all(np.diff(V) > 0)
    DUR = A[-1]
proc = subprocess.Popen(
    ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", "1080x1920",
     "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18",
     "-preset", "medium", "-movflags", "+faststart", OUT], stdin=subprocess.PIPE)
start, stop = (float(v) for v in (ARGS[1:3] if len(ARGS) > 2 else (0, DUR)))
for f in range(int(start * FPS), int(stop * FPS)):
    t = float(np.interp(f / FPS, A, V)) if VO else f / FPS
    fig.clf()
    for scene in (s1, s2, s3, s4, s5, s6):
        scene(t)
    footer(t)
    fig.canvas.draw()
    proc.stdin.write(fig.canvas.buffer_rgba().tobytes())
proc.stdin.close(); proc.wait()
print("done", OUT, DUR, STATS)
