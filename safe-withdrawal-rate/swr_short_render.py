"""9:16 short: what the 4% rule is and isn't.
Backtest numbers are computed from Shiller's U.S. data (swr_data.py).
Trinity numbers are copied from Cooley, Hubbard & Walz (1999), Table 2.
Usage: python swr_short_render.py out.mp4 [start end]
       python swr_short_render.py --vo out.mp4    # timed to the published voiceover (75 s)
       python swr_short_render.py --stats-only"""
import subprocess, sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from swr_data import years, run, starts, success, portfolio_real

ARGS = [a for a in sys.argv[1:] if not a.startswith("--")]
OUT = ARGS[0] if ARGS else "swr_short.mp4"
VO = "--vo" in sys.argv
FPS = 30

# ---- data
H, WR, EQ = 30, 0.04, 0.6
S30 = starts(H)
PATHS = np.array([run(i, WR, H, EQ) for i in S30])  # real, start = 1.0
FAIL = PATHS[:, -1] <= 0
P30, N30 = success(WR, 30, EQ)
P50, N50 = success(WR, 50, EQ)
MED_END = np.median(PATHS[:, -1])
FAIL_YEARS = [int(years[i]) for i, f in zip(S30, FAIL) if f]
i66 = list(years).index(1966)
seq = portfolio_real(EQ)[i66:i66 + H]
FWD = run(i66, WR, H, EQ)
REV = run(0, WR, H, EQ, rets=seq[::-1])
GEO = np.prod(1 + seq) ** (1 / H) - 1
RUNOUT = int(np.argmax(FWD <= 0))
assert round(P30, 2) == 0.96 and FAIL_YEARS == [1965, 1966, 1967, 1968, 1969]
assert RUNOUT == 26 and REV[-1] > 1.5 and round(P50, 2) == 0.80
STATS = (f"30y {P30:.3f} 50y {P50:.3f} median end {MED_END:.2f} fails {FAIL_YEARS} "
         f"geo66 {GEO:.4f} runout {RUNOUT} rev {REV[-1]:.2f}")
if "--stats-only" in sys.argv:
    print(STATS)
    sys.exit()

# Cooley, Hubbard & Walz (1999), Financial Counseling and Planning 10(1), Table 2:
# inflation-adjusted withdrawals, 1926-1997, 4% rate, 30-year payout.
TRINITY = [("100% stocks", 98), ("75 / 25", 100), ("50 / 50", 95), ("25 / 75", 74), ("100% bonds", 19)]

for f in fm.findSystemFonts():
    if "Inter" in f:
        fm.fontManager.addfont(f)
plt.rcParams["font.family"] = "Inter"
plt.rcParams["text.parse_math"] = False
BG, FG, MUTED = "#0b0f14", "#f2f5f7", "#9aa5b1"
TEAL, ORANGE, RED, GREEN, BLUE = "#3ccfc4", "#f2a541", "#ff5a5f", "#58d68d", "#6aa9ff"
fig = plt.figure(figsize=(10.8, 19.2), dpi=100)
fig.patch.set_facecolor(BG)
CX = 0.47


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


def chart_ax(rect, a):
    ax = fig.add_axes(rect)
    ax.set_facecolor(BG)
    for s in ["top", "right"]:
        ax.spines[s].set_visible(False)
    for s in ["left", "bottom"]:
        ax.spines[s].set_color(MUTED); ax.spines[s].set_alpha(a)
    ax.tick_params(colors=FG, labelsize=22, length=0)
    return ax


def note(lines, a):
    for k, s in enumerate(lines):
        txt(CX, 0.245 - k * 0.021, s, 20, a * 0.95, MUTED, "regular")


BACKTEST_NOTE = ["Backtest: Shiller U.S. data 1871–2022 · 60% stocks / 40% 10-yr Treasuries",
                 "Annual rebalance · real dollars · no fees or taxes"]


# ---- 1. hook (0-4)
def s1(t):
    a = fade(t, 0, 4)
    txt(CX, 0.64, "The 4% rule", 110, a)
    txt(CX, 0.575, "isn't a rule.", 110, a, ORANGE)
    txt(CX, 0.47, "It's a result from historical backtests.", 36, fade(t, 1.6, 4))
    txt(CX, 0.435, "Here's what it actually says.", 36, fade(t, 1.6, 4), MUTED, "medium")


# ---- 2. mechanics (4-13)
def s2(t):
    a = fade(t, 4, 13)
    if a <= 0:
        return
    head(a, "What it actually is", "$1M portfolio, 3% inflation for illustration")
    rows = [(4.6, "Year 1", "4% × $1,000,000", "$40,000", ""),
            (6.0, "Year 2", "$40,000 + 3%", "$41,200", "market up 20%"),
            (7.4, "Year 3", "$41,200 + 3%", "$42,436", "market down 20%")]
    for k, (s, yr, how, amt, mkt) in enumerate(rows):
        ra = min(a, appear(t, s))
        y = 0.75 - k * 0.115
        txt(0.10, y + 0.02, yr, 32, ra, MUTED, "medium", ha="left")
        txt(0.10, y - 0.018, how, 30, ra, FG, "medium", ha="left")
        txt(0.84, y + 0.002, amt, 50, ra, TEAL, ha="right")
        if mkt:
            txt(0.10, y - 0.052, mkt, 26, ra, GREEN if "up" in mkt else RED, "medium", ha="left")
    ca = min(a, appear(t, 9.0))
    txt(CX, 0.39, "4% of your STARTING balance,", 38, ca)
    txt(CX, 0.355, "then raised with inflation,", 38, ca)
    txt(CX, 0.32, "whatever the market does.", 38, ca, ORANGE)
    txt(CX, 0.255, "Not 4% of whatever you have each year.", 30, min(a, appear(t, 10.6)), MUTED, "medium")


# ---- 3. origins (13-24)
def s3(t):
    a = fade(t, 13, 24)
    if a <= 0:
        return
    head(a, "Where it came from")
    b1 = min(a, appear(t, 13.4))
    txt(CX, 0.83, "Bengen, 1994", 36, b1, TEAL)
    txt(CX, 0.80, "Highest starting rate that lasted every", 30, b1, FG, "medium")
    txt(CX, 0.777, "30-year U.S. retirement he tested: about 4%", 30, b1, FG, "medium")
    b2 = min(a, appear(t, 16.0))
    txt(CX, 0.725, "Trinity study (Cooley, Hubbard & Walz)", 36, b2, TEAL)
    txt(CX, 0.695, "4%, inflation-adjusted, 30 years, 1926–1997:", 28, b2, MUTED, "medium")
    txt(CX, 0.672, "share of periods that never hit $0", 28, b2, MUTED, "medium")
    ax = fig.add_axes([0.30, 0.38, 0.52, 0.27])
    ax.set_facecolor(BG)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_xticks([])
    g = ease((t - 16.6) / 2.0)
    ys = np.arange(len(TRINITY))[::-1]
    vals = np.array([v for _, v in TRINITY])
    cols = [TEAL if v >= 95 else (ORANGE if v >= 70 else RED) for v in vals]
    ax.barh(ys, vals * g, color=cols, alpha=b2, height=0.62)
    ax.set_xlim(0, 125)
    ax.set_yticks(ys, [n for n, _ in TRINITY])
    ax.tick_params(colors=FG, labelsize=26, length=0)
    for lab in ax.get_yticklabels():
        lab.set_alpha(b2)
    if g > 0.95:
        for yv, v in zip(ys, vals):
            ax.text(v + 2, yv, f"{v}%", va="center", color=FG, size=26, weight="bold", alpha=b2)
    c = min(a, appear(t, 19.8))
    txt(CX, 0.33, "\"Success\" only means not running out.", 32, c)
    txt(CX, 0.295, "Stock-heavy mixes did best. All-bond mixes failed.", 28, c, MUTED, "medium")
    note(["Cooley, Hubbard & Walz (1999), Fin. Counseling & Planning, Table 2",
          "Bengen: Journal of Financial Planning (1994)"], a)


# ---- 4. every retirement since 1871 (24-35)
def s4(t):
    a = fade(t, 24, 35)
    if a <= 0:
        return
    head(a, "Every 30-yr retirement since 1871", f"$1M start, $40K/yr real, {len(S30)} start years")
    ax = chart_ax([0.15, 0.42, 0.70, 0.36], a)
    k = ease((t - 24.6) / 4.0) * H
    n = int(k) + 1
    xs = np.arange(H + 1)
    for p, f in zip(PATHS, FAIL):
        if not f:
            ax.plot(xs[:n], np.minimum(p[:n], 4.2), color=BLUE, lw=1.4, alpha=0.28 * a)
    for p, f in zip(PATHS, FAIL):
        if f:
            ax.plot(xs[:n], p[:n], color=RED, lw=3, alpha=a)
    ax.axhline(1.0, color=FG, lw=1.2, ls=":", alpha=0.6 * a)
    ax.set_xlim(0, 30); ax.set_ylim(0, 4.2)
    ax.set_xticks([0, 10, 20, 30], ["0", "10", "20", "30 yrs"])
    ax.set_yticks([0, 1, 2, 3, 4], ["$0", "$1M", "$2M", "$3M", "$4M+"])
    for lab in ax.get_xticklabels() + ax.get_yticklabels():
        lab.set_alpha(a)
    c = min(a, appear(t, 29.0))
    txt(0.28, 0.36, f"{P30*100:.0f}%", 70, c, TEAL)
    txt(0.28, 0.325, "lasted 30 years", 26, c, MUTED, "medium")
    txt(0.66, 0.36, f"{MED_END:.1f}×", 70, c, FG)
    txt(0.66, 0.325, "median ending balance", 26, c, MUTED, "medium")
    c2 = min(a, appear(t, 31.0))
    txt(CX, 0.28, f"Red: retirements starting {FAIL_YEARS[0]}–{FAIL_YEARS[-1]} ran out", 30, c2, RED, "medium")
    note(BACKTEST_NOTE, a)


# ---- 5. sequence risk (35-46)
def s5(t):
    a = fade(t, 35, 46)
    if a <= 0:
        return
    head(a, "Why 1966 failed: order", f"Same 30 yearly returns, {GEO*100:.1f}%/yr real average")
    ax = chart_ax([0.15, 0.44, 0.70, 0.34], a)
    k = ease((t - 35.6) / 4.0) * H
    n = int(k) + 1
    xs = np.arange(H + 1)
    ax.plot(xs[:n], FWD[:n], color=RED, lw=5, alpha=a)
    g = appear(t, 37.0)
    ax.plot(xs[:n], REV[:n], color=TEAL, lw=5, alpha=a * g)
    ax.axhline(1.0, color=FG, lw=1.2, ls=":", alpha=0.6 * a)
    ax.set_xlim(0, 30); ax.set_ylim(0, 3.0)
    ax.set_xticks([0, 10, 20, 30], ["0", "10", "20", "30 yrs"])
    ax.set_yticks([0, 1, 2, 3], ["$0", "$1M", "$2M", "$3M"])
    for lab in ax.get_xticklabels() + ax.get_yticklabels():
        lab.set_alpha(a)
    txt(0.30, 0.405, "■ actual order (1966–95)", 26, a, RED, "medium")
    txt(0.70, 0.405, "■ reversed order", 26, a * g, TEAL, "medium")
    c = min(a, appear(t, 40.6))
    txt(CX, 0.355, f"Actual: ran out in year {RUNOUT}", 34, c, RED)
    txt(CX, 0.315, f"Reversed: ended with ${REV[-1]:.2f}M", 34, c, TEAL)
    txt(CX, 0.278, "Bad years early hurt most. That's sequence risk.", 28, min(a, appear(t, 42.4)), MUTED, "medium")
    note(BACKTEST_NOTE, a)


# ---- 6. what it isn't + my take (46-58.5)
P35_30, _ = success(0.035, 30, EQ)
P35_50, _ = success(0.035, 50, EQ)
assert P35_30 == 1.0 and round(P35_50, 2) == 0.96


def s6(t):
    a = fade(t, 46, 58.5)
    if a <= 0:
        return
    head(a, "What it isn't")
    items = [
        ("Not a guarantee", "a historical result, mostly U.S. data"),
        ("Not built for 50-year retirements", f"4% lasted 50 yrs in {P50*100:.0f}% of this backtest"),
        ("Not a forecast", "Morningstar's 2026 estimate: 3.9% (30 yrs, 90%)"),
    ]
    for k, (l1, l2) in enumerate(items):
        ia = min(a, appear(t, 46.5 + 1.2 * k))
        y = 0.79 - k * 0.095
        txt(CX, y + 0.016, l1, 40, ia)
        txt(CX, y - 0.02, l2, 28, ia, MUTED, "regular")
    c = min(a, appear(t, 50.8))
    txt(CX, 0.5, "My take", 34, c, MUTED, "medium")
    txt(CX, 0.46, "3.5% is a good back-of-the-envelope number", 32, c, TEAL)
    txt(CX, 0.428, f"Backtest: lasted 30 yrs in {P35_30*100:.0f}% and 50 yrs in {P35_50*100:.0f}% of start years", 23, c, MUTED, "regular")
    c2 = min(a, appear(t, 53.0))
    txt(CX, 0.375, "But nobody should spend on autopilot.", 34, c2)
    txt(CX, 0.343, "Use a dynamic plan: trim after bad years, raise after good ones", 23, c2, MUTED, "regular")
    txt(CX, 0.29, "Try your numbers: summitward.com/learn/fire-calculator", 24, c2, FG, "medium")
    note(["Morningstar, \"The State of Retirement Income\" (2025 research)",
          "Backtest as earlier: Shiller U.S. data, 60/40, no fees or taxes"], a)


def footer(t):
    txt(CX, 0.19, "Educational only · not investment advice", 22, 0.85, MUTED, "regular")


DUR = 58.5
A = V = None
if VO:
    # audio time -> scene time, anchored to sentence starts in the published voiceover
    GAP_AT, GAP = 58.95, 3.0   # silence inserted before "My take" so the list can be read
    A = [0, 5.35, 15.58, 23.05, 33.83, 39.67, 44.6, 49.2, 51.09, 56.15, 58.95,
         58.95 + GAP, 63.5 + GAP, 71.4 + GAP, 72.0 + GAP]
    V = [0, 4.0, 13.0, 15.9, 24.0, 28.9, 30.9, 35.0, 36.9, 42.3, 46.0,
         50.6, 52.9, 58.2, 58.5]
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
