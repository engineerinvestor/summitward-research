"""9:16 short: what a mega backdoor Roth is worth.
Limits: IRS Notice 2025-67 (2026). All results come from mbr_model.py.
Usage: python3 render_mbr.py out.mp4 [start end]
       python3 render_mbr.py --stats-only"""
import subprocess, sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from matplotlib.patches import FancyBboxPatch
import mbr_model as M

FPS = 30
B = M.run()
IRA_ADV = M.run(c=M.IRA)["adv"]
ROTH_S, TAX_S = M.series()
PRE_S = [0.0]                                  # taxable account value before selling, by year
_v = 0.0
for _ in range(M.YEARS):
    _d = _v * M.YLD
    _v = _v * (1 + M.R - M.YLD) + _d * (1 - M.TAX) + M.MEGA
    PRE_S.append(_v)
assert abs(PRE_S[-1] - M.run()["pre_sale"]) < 1e-6
assert M.EMPLOYER == 8_000 and M.MEGA == 39_500
assert round(B["adv"], -3) == 254_000 and round(IRA_ADV, -3) == 48_000
assert round(B["roth"] / 1e4) == 250 and round(B["taxable"] / 1e4) == 224

for f in fm.findSystemFonts():
    if "Inter" in f:
        fm.fontManager.addfont(f)
plt.rcParams["font.family"] = "Inter"
plt.rcParams["text.parse_math"] = False
BG, FG, MUTED = "#0b0f14", "#f2f5f7", "#9aa5b1"
C_IRA, C_MEGA, C_YOU, C_EMP, C_TAXA = "#9ea9c9", "#3ccfc4", "#f2b33d", "#6aa9ff", "#9ea9c9"
CARD, EDGE = "#141b23", "#2a3440"
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
    txt(CX, 0.885, h, 50 if len(h) < 26 else 44, a)
    if sub:
        txt(CX, 0.85, sub, 28, a, MUTED, "regular")


def note(lines, a, y0=0.245):
    for k, s in enumerate(lines):
        txt(CX, y0 - k * 0.022, s, 21, a * 0.95, MUTED, "regular")


def card(rect, a, color=CARD, edge=EDGE):
    ax = fig.add_axes(rect)
    ax.axis("off")
    ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    ax.add_patch(FancyBboxPatch((0.01, 0.02), 0.98, 0.96, boxstyle="round,pad=0,rounding_size=0.06",
                                fc=color, ec=edge, lw=3, alpha=a))
    return ax


def d(v):
    return f"${v:,.0f}"


def kk(v):
    return f"${v / 1e3:,.0f}K"


def mm(v):
    return f"${v / 1e6:.2f}M"


# ---- 1. hook (0-6.1)
def s1(t):
    a = fade(t, 0, 6.1)
    txt(CX, 0.74, "Same savings. Same investments.", 44, min(a, appear(t, 0.1)))
    n = B["adv"] * ease((t - 0.3) / 1.4)
    txt(CX, 0.645, f"+${round(n, -3):,.0f}", 118, min(a, appear(t, 0.3)), C_MEGA)
    txt(CX, 0.56, "Mega backdoor Roth vs. a taxable account", 32, min(a, appear(t, 2.0)), FG, "medium")
    txt(CX, 0.525, "25-year example", 28, min(a, appear(t, 2.0)), MUTED, "regular")


# ---- 2. where the room comes from (6.1-22.4)
SEGS = [(M.DEFERRAL, "your regular 401(k)", C_YOU, 11.6),
        (M.EMPLOYER, "employer", C_EMP, 14.2),
        (M.MEGA, "after-tax room", C_MEGA, 16.6)]


def s2(t):
    a = fade(t, 6.1, 22.4)
    if a <= 0:
        return
    head(a, f"2026 401(k) limit: {d(M.TOTAL_415C)}", "from all sources, before catch-ups")
    txt(CX, 0.805, f"{kk(M.SALARY)} salary \u00d7 {M.EMPLOYER_RATE:.0%} = {d(M.EMPLOYER)} employer",
        30, min(a, appear(t, 13.8)), C_EMP, "medium")
    ax = fig.add_axes([0.22, 0.31, 0.56, 0.46])
    ax.axis("off")
    ax.set_xlim(0, 1); ax.set_ylim(0, M.TOTAL_415C * 1.02)
    # the whole limit appears at once, then gets carved into its three parts
    full = ease((t - 6.4) / 0.9)
    ax.add_patch(FancyBboxPatch((0.05, 0), 0.9, M.TOTAL_415C * full, boxstyle="square,pad=0",
                                fc=EDGE, ec=BG, lw=3, alpha=a))
    ax.text(0.5, M.TOTAL_415C * 0.62, d(M.TOTAL_415C), color=FG, size=56, weight="bold", ha="center", va="center",
            alpha=min(a, appear(t, 7.0), 1 - appear(t, 16.4)))
    base = 0
    for amt, label, col, s_ in SEGS:
        e = ease((t - s_) / 0.9)
        if e > 0:
            ax.add_patch(FancyBboxPatch((0.05, base), 0.9, amt * e, boxstyle="square,pad=0", fc=col, ec=BG, lw=3, alpha=a))
            la = min(a, appear(t, s_ + 0.5))
            mid = base + amt / 2
            if amt > 15_000:
                ax.text(0.5, mid + 1300, d(amt), color=BG, size=46, weight="bold", ha="center", va="center", alpha=la)
                ax.text(0.5, mid - 3300, label, color=BG, size=28, weight="bold", ha="center", va="center", alpha=la)
            else:
                ax.text(0.5, mid, f"{d(amt)} {label}", color=BG, size=28, weight="bold", ha="center", va="center", alpha=la)
        base += amt
    c = min(a, appear(t, 17.6))
    txt(CX, 0.275, f"{d(M.TOTAL_415C)} \u2212 {d(M.DEFERRAL)} \u2212 {d(M.EMPLOYER)} = {d(M.MEGA)}", 32, c)
    txt(CX, 0.24, "Convert it to Roth, if your plan allows the full amount.", 26, min(a, appear(t, 19.4)), C_MEGA, "medium")


# ---- 3. 25 years, Roth vs. taxable (22.4-42.9)
# The taxable bar follows its real path (dividend taxes drag it from the start), then loses
# the capital gains tax when it is sold in year 25.
DRAG = B["roth"] - B["pre_sale"]          # dividend taxes plus the growth they would have earned
SALE = B["gain_tax"]                      # capital gains tax when the account is sold
assert abs(B["roth"] - (B["taxable"] + DRAG + SALE)) < 1e-6
C_RED, C_RED2 = "#ff5a5f", "#b8434a"


def s3(t):
    a = fade(t, 22.4, 42.9)
    if a <= 0:
        return
    head(a, f"{d(M.MEGA)} a year for {M.YEARS} years", f"{M.R:.0%} return, same investments in both")
    ax = fig.add_axes([0.14, 0.50, 0.72, 0.31])
    ax.axis("off")
    ax.set_xlim(-0.75, 1.75); ax.set_ylim(0, 2.95e6)
    yr = ease((t - 22.8) / 4.4) * M.YEARS
    grown = np.interp(yr, np.arange(M.YEARS + 1), ROTH_S)
    pre = np.interp(yr, np.arange(M.YEARS + 1), PRE_S)
    drag = grown - pre
    sale = SALE * ease((t - 34.2) / 0.8)
    if grown > 0:
        ax.bar(0, grown, 0.6, color=C_MEGA, alpha=a)
        ax.bar(1, pre - sale, 0.6, color=C_TAXA, alpha=a)
        if sale > 0:
            ax.bar(1, sale, 0.6, bottom=pre - sale, color=C_RED, alpha=a)
        ax.bar(1, drag, 0.6, bottom=pre, color=C_RED2, alpha=a * min(1, appear(t, 31.6) + 0.55))
        ax.text(0, grown + 50_000, mm(grown), color=C_MEGA, size=44, weight="bold", ha="center", va="bottom", alpha=a)
        ax.text(1, grown + 50_000, mm(pre - sale), color=C_TAXA, size=44, weight="bold",
                ha="center", va="bottom", alpha=a)
    txt(CX, 0.805, f"year {int(round(yr))}", 26, min(a, fade(t, 22.8, 27.6)), MUTED, "regular")
    for j, (l1, l2, col) in enumerate([("Roth", "if withdrawals qualify", C_MEGA), ("Taxable", "sold in year 25", C_TAXA)]):
        x = 0.14 + 0.72 * (j + 0.75) / 2.5
        txt(x, 0.482, l1, 34, a, col)
        txt(x, 0.457, l2, 22, a, MUTED, "regular")
    txt(CX, 0.415, f"\u2212{kk(DRAG)}  dividend taxes and the growth they cost", 28, min(a, appear(t, 31.6)), C_RED2)
    txt(CX, 0.385, f"\u2212{kk(SALE)}  capital gains tax when sold", 28, min(a, appear(t, 34.2)), C_RED)
    g = min(a, appear(t, 37.2))
    txt(CX, 0.33, f"+${round(B['adv'], -3):,.0f} for the Roth", 56, g, C_MEGA)
    txt(CX, 0.29, "Same investments. Only the taxes differ.", 30, min(a, appear(t, 38.4)), FG, "medium")
    txt(CX, 0.248, "Hypothetical \u00b7 7% return \u00b7 15% tax \u00b7 future dollars",
        26, min(a, appear(t, 23.0)), MUTED, "medium")


# ---- 4. vs. the backdoor Roth IRA (42.9-49.7)
def s4(t):
    a = fade(t, 42.9, 49.7)
    if a <= 0:
        return
    head(a, "Same math, smaller account", f"{d(M.IRA)} a year in a backdoor Roth IRA")
    ax = fig.add_axes([0.16, 0.40, 0.68, 0.36])
    ax.axis("off")
    ax.set_xlim(-0.75, 1.75); ax.set_ylim(0, 300_000)
    for j, (v, col, s_, l1, l2) in enumerate([(IRA_ADV, C_IRA, 43.4, "Backdoor", "Roth IRA"),
                                               (B["adv"], C_MEGA, 43.0, "Mega backdoor", "Roth 401(k)")]):
        h = v * ease((t - s_) / 0.8)
        if h > 0:
            ax.bar(j, h, 0.62, color=col, alpha=a)
            ax.text(j, h + 6000, f"+{kk(h)}", color=col, size=48, weight="bold", ha="center", va="bottom", alpha=a)
        x = 0.16 + 0.68 * (j + 0.75) / 2.5
        la = min(a, appear(t, s_))
        txt(x, 0.375, l1, 32, la, col)
        txt(x, 0.35, l2, 32, la, col)
    txt(CX, 0.28, "You can do both.", 48, min(a, appear(t, 46.8)), FG)


# ---- 5. personal (49.7-53.5)
def s5(t):
    a = fade(t, 49.7, 53.5)
    if a <= 0:
        return
    txt(CX, 0.70, "I've maxed mine out", 60, a)
    txt(CX, 0.65, "for the last six years.", 60, a, C_MEGA)
    for i in range(6):
        txt(0.5 + (i - 2.5) * 0.12, 0.55, "\u2713", 80, min(a, appear(t, 50.0 + 0.3 * i, 0.25)), C_MEGA)


# ---- 6. the catch and close (53.5-64.5)
def s6(t):
    a = fade(t, 53.5, 64.6)
    if a <= 0:
        return
    head(a, "The catch", "your plan has to allow both")
    items = [(54.4, "After-tax contributions", "above the regular $24,500"),
             (56.0, "Roth conversion", "in-plan, or an in-service rollover")]
    for i, (s_, l1, l2) in enumerate(items):
        ia = min(a, appear(t, s_))
        y = 0.76 - i * 0.12
        card([0.10, y - 0.048, 0.80, 0.096], ia)
        txt(0.17, y, "\u2713", 56, ia, C_MEGA)
        txt(0.25, y + 0.013, l1, 34, ia, FG, ha="left")
        txt(0.25, y - 0.018, l2, 26, ia, MUTED, "medium", ha="left")
    txt(CX, 0.555, "After-tax isn't Roth until you convert it.", 30, min(a, appear(t, 56.8)), C_YOU, "medium")
    txt(CX, 0.48, "Check whether yours does.", 50, min(a, appear(t, 58.4)))
    c = min(a, appear(t, 60.4))
    txt(CX, 0.39, "Full math and assumptions:", 28, c, MUTED, "medium")
    txt(CX, 0.355, "Summitward.com", 42, c)


def footer(t):
    txt(CX, 0.19, "Educational only · not tax or investment advice", 22, 0.85, MUTED, "regular")


# ---- pacing: scenes are designed on a fixed timeline (V); A says when each moment happens in
# the final video, anchored to sentence starts in the Skylar (Cartesia sonic-3.6) read, 58.2 s.
# For a new read, find its pauses and edit A:
#   ffmpeg -i VO.wav -af silencedetect=noise=-38dB:d=0.1 -f null -
V = [0, 2.0, 6.1, 6.4, 11.6, 13.8, 14.2, 16.6, 17.6, 19.4, 22.4, 22.8, 31.6, 34.2, 37.2, 38.4,
     42.9, 43.0, 46.8, 49.7, 53.5, 54.4, 56.0, 56.8, 58.4, 60.4, 64.5]
A = [0, 5.4, 7.9, 8.2, 14.4, 17.3, 17.7, 20.2, 21.5, 23.0, 24.7, 25.0, 33.7, 37.0, 39.8, 40.2,
     43.0, 43.15, 46.85, 47.9, 50.3, 51.3, 53.8, 54.6, 55.4, 56.6, 61.0]
assert len(V) == len(A) and all(np.diff(V) > 0) and all(np.diff(A) > 0)
DUR = A[-1]
SCENES = (s1, s2, s3, s4, s5, s6)
if __name__ == "__main__" and "--stats-only" in sys.argv:
    print(f"room {M.MEGA:,}  roth {mm(B['roth'])}  taxable {mm(B['taxable'])}  adv {B['adv']:,.0f}"
          f"  drag {kk(DRAG)}  sale {kk(SALE)}  IRA adv {IRA_ADV:,.0f}")
elif __name__ == "__main__":
    OUT = sys.argv[1]
    proc = subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", "1080x1920",
         "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18",
         "-preset", "medium", "-movflags", "+faststart", OUT], stdin=subprocess.PIPE)
    start, stop = (float(v) for v in (sys.argv[2:4] if len(sys.argv) > 3 else (0, DUR)))
    for f in range(int(start * FPS), int(stop * FPS)):
        t = float(np.interp(f / FPS, A, V))
        fig.clf()
        for scene in SCENES:
            scene(t)
        footer(t)
        fig.canvas.draw()
        proc.stdin.write(fig.canvas.buffer_rgba().tobytes())
    proc.stdin.close(); proc.wait()
    print(f"done {OUT}  adv {B['adv']:,.0f}  IRA adv {IRA_ADV:,.0f}")
