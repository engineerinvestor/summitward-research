"""9:16 short: why R-squared is a poor quality score. All numbers computed live
from simulated data (demos follow Shalizi's CMU notes as summarized by UVA StatLab).
Usage: python r2_quality_render.py out.mp4 [start end]
       python r2_quality_render.py --stats-only"""
import subprocess, sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm

ARGS = [a for a in sys.argv[1:] if not a.startswith("--")]
OUT = ARGS[0] if ARGS else "r2_quality.mp4"
FPS = 30


def ols(x, y):
    b, a = np.polyfit(x, y, 1)
    r = y - (a + b * x)
    r2 = 1 - (r @ r) / ((y - y.mean()) @ (y - y.mean()))
    return a, b, r2, np.sqrt(np.mean(r ** 2)), r


# --- Demo A: same model, same noise, narrower x range
rngA = np.random.default_rng(1)
epsA = rngA.normal(0, 0.9, 100)
u = np.linspace(0, 1, 100)


def demoA(hi):
    x = 1 + (hi - 1) * u
    y = 2 + 1.2 * x + epsA
    return x, y, ols(x, y)


_, _, (_, _, R2_wide, E_wide, _) = demoA(10)
_, _, (_, _, R2_narrow, E_narrow, _) = demoA(2)
assert R2_wide > 0.9 and R2_narrow < 0.3 and abs(E_wide - E_narrow) < 1e-9  # residuals identical

# --- Demo B: model exactly right, more noise
rngB = np.random.default_rng(7)  # arbitrary; not tuned
epsB = rngB.normal(0, 1, 100)
xB = np.linspace(1, 10, 100)


def demoB(sig):
    y = 2 + 1.2 * xB + sig * epsB
    return y, ols(xB, y)


_, (_, bB_hi, R2_B_hi, _, _) = demoB(8.0)
_, (_, _, R2_B_lo, _, _) = demoB(0.5)
assert R2_B_lo > 0.95 and R2_B_hi < 0.35

# --- Demo C: wrong (straight) model on curved data, high R2
rngC = np.random.default_rng(3)
xC = np.sort(rngC.uniform(0, 10, 60))
yC = xC ** 2 * rngC.uniform(0.85, 1.15, 60)
aC, bC, R2_C, _, rC = ols(xC, yC)
assert R2_C > 0.85

# --- Demo D: regress y on x vs x on y
rngD = np.random.default_rng(5)
xD = np.linspace(1, 10, 80)
yD = 2 + 1.2 * xD + rngD.normal(0, 2, 80)
aD, bD, R2_yx, _, _ = ols(xD, yD)
cD, dD, R2_xy, _, _ = ols(yD, xD)
assert abs(R2_yx - R2_xy) < 1e-12
STATS = (f"A: {R2_wide:.3f}->{R2_narrow:.3f} rmse {E_wide:.3f}  B: {R2_B_lo:.2f}->{R2_B_hi:.2f} "
         f"slope {bB_hi:.2f}  C: {R2_C:.3f}  D: {R2_yx:.3f}")
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
CX = 0.47  # keep clear of right-side action buttons


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


def plot_ax(rect, a):
    ax = fig.add_axes(rect)
    ax.set_facecolor(BG)
    for s in ["top", "right"]:
        ax.spines[s].set_visible(False)
    for s in ["left", "bottom"]:
        ax.spines[s].set_color(MUTED); ax.spines[s].set_alpha(a)
    ax.set_xticks([]); ax.set_yticks([])
    return ax


def head(a, h, sub=None):
    txt(CX, 0.885, h, 52 if len(h) < 24 else 44, a)
    if sub:
        txt(CX, 0.85, sub, 28 if len(sub) < 52 else 25, a, MUTED, "regular")


# ---- 1. hook (0-4)
def s1(t):
    a = fade(t, 0, 4)
    txt(CX, 0.66, f"R² = {R2_wide:.2f}", 110, a, TEAL)
    txt(CX, 0.58, f"R² = {R2_narrow:.2f}", 110, fade(t, 0.9, 4), RED)
    txt(CX, 0.475, "Same underlying relationship.", 40, fade(t, 1.8, 4))
    txt(CX, 0.44, "Same residual error.", 40, fade(t, 1.8, 4))
    txt(CX, 0.395, "So what is R² actually telling you?", 34, fade(t, 2.4, 4), MUTED, "medium")


# ---- 2. demo A: range (4-15)
def s2(t):
    a = fade(t, 4, 15)
    if a <= 0:
        return
    hi = 10 - 8 * ease((t - 7.0) / 4.0)
    x, y, (a0, b0, r2, rmse, _) = demoA(hi)
    head(a, "Myth 1: R² = accuracy", "Same true relationship, same noise. Only the x-range shrinks.")
    ax = plot_ax([0.10, 0.42, 0.74, 0.36], a)
    ax.scatter(x, y, s=60, color=BLUE, alpha=0.8 * a, lw=0)
    xx = np.array([x.min(), x.max()])
    ax.plot(xx, a0 + b0 * xx, color=FG, lw=4, alpha=a)
    ax.set_xlim(0, 11); ax.set_ylim(0, 17)
    txt(0.28, 0.35, f"{r2:.2f}", 76, a, TEAL if r2 > 0.5 else RED)
    txt(0.28, 0.31, "R²", 30, a, MUTED, "medium")
    txt(0.66, 0.35, f"{rmse:.2f}", 76, a, FG)
    txt(0.66, 0.31, "residual RMSE (in-sample)", 28, a, MUTED, "medium")
    ca = min(a, appear(t, 11.6))
    txt(CX, 0.255, "R² collapsed. Residual RMSE didn't move.", 34, ca)


# ---- 3. demo B: noise (15-25)
def s3(t):
    a = fade(t, 15, 25)
    if a <= 0:
        return
    sig = 0.5 + 7.5 * ease((t - 16.5) / 5.0)
    y, (a0, b0, r2, _, _) = demoB(sig)
    head(a, "Myth 2: low R² = wrong model", "Same true line every frame. Only the noise grows.")
    ax = plot_ax([0.10, 0.42, 0.74, 0.36], a)
    ax.scatter(xB, y, s=60, color=BLUE, alpha=0.8 * a, lw=0)
    ax.plot([1, 10], [2 + 1.2, 2 + 12], color=GREEN, lw=4, alpha=a, ls="--")
    ax.plot([1, 10], [a0 + b0, a0 + 10 * b0], color=FG, lw=4, alpha=a)
    ax.set_xlim(0, 11); ax.set_ylim(-15, 32)
    txt(0.28, 0.35, f"{r2:.2f}", 76, a, TEAL if r2 > 0.5 else RED)
    txt(0.28, 0.31, "R²", 30, a, MUTED, "medium")
    txt(0.66, 0.35, f"{sig:.1f}", 76, a, FG)
    txt(0.66, 0.31, "noise σ", 30, a, MUTED, "medium")
    txt(0.30, 0.795, "— fitted", 26, a, FG, "medium")
    txt(0.62, 0.795, "- - true", 26, a, GREEN, "medium")
    ca = min(a, appear(t, 21.8))
    txt(CX, 0.255, "Correctly specified, and R² falls anyway.", 32, ca)


# ---- 4. demo C: curved data (25-35)
def s4(t):
    a = fade(t, 25, 35)
    if a <= 0:
        return
    head(a, "Myth 3: high R² = right model", "A straight line through curved data")
    ax = plot_ax([0.10, 0.52, 0.74, 0.27], a)
    ax.scatter(xC, yC, s=60, color=BLUE, alpha=0.8 * a, lw=0)
    ax.plot([0, 10], [aC, aC + 10 * bC], color=FG, lw=4, alpha=a)
    ax.set_xlim(-0.3, 10.5)
    txt(CX, 0.48, f"R² = {R2_C:.2f}", 64, a, TEAL)
    ra = min(a, appear(t, 28.5))
    if ra > 0:
        ax2 = plot_ax([0.10, 0.30, 0.74, 0.12], ra)
        ax2.axhline(0, color=MUTED, lw=1.5, alpha=ra)
        ax2.scatter(xC, rC, s=40, color=ORANGE, alpha=ra, lw=0)
        ax2.set_xlim(-0.3, 10.5)
        txt(CX, 0.435, "Residuals (misses): a clear U-shape", 28, ra, ORANGE, "medium")
    ca = min(a, appear(t, 30.5))
    txt(CX, 0.255, "The plot catches what R² hides.", 34, ca)


# ---- 5. demo D: direction (35-43)
def s5(t):
    a = fade(t, 35, 43)
    if a <= 0:
        return
    head(a, "Myth 4: R² says X drives Y", "Flip the regression around")
    ax = plot_ax([0.10, 0.44, 0.74, 0.34], a)
    ax.scatter(xD, yD, s=60, color=BLUE, alpha=0.8 * a, lw=0)
    ax.plot([0, 11], [aD, aD + 11 * bD], color=TEAL, lw=4, alpha=a)
    g = appear(t, 37.0)
    yy = np.array([yD.min() - 1, yD.max() + 1])
    ax.plot(cD + dD * yy, yy, color=ORANGE, lw=4, alpha=a * g)
    ax.set_xlim(0, 11)
    txt(0.28, 0.37, f"{R2_yx:.2f}", 64, a, TEAL)
    txt(0.28, 0.33, "Y on X", 28, a, MUTED, "medium")
    txt(0.66, 0.37, f"{R2_xy:.2f}", 64, a * g, ORANGE)
    txt(0.66, 0.33, "X on Y", 28, a * g, MUTED, "medium")
    ca = min(a, appear(t, 39.0))
    txt(CX, 0.28, "Different lines, identical R².", 34, ca)
    txt(CX, 0.248, "Simple OLS with an intercept: R² = r². No causal direction.", 26, ca, MUTED, "medium")


# ---- 6. instead (43-53)
def s6(t):
    a = fade(t, 43, 53.5)
    if a <= 0:
        return
    head(a, "Use R² as a description,", None)
    txt(CX, 0.845, "not a report card", 52, a, TEAL)
    items = [("Plot the data and residuals", "patterns R² can't see"),
             ("Report error in real units", "RMSE or MAE, out of sample"),
             ("Use a task-relevant metric", "prediction loss, or effect size + uncertainty")]
    for k, (l1, l2) in enumerate(items):
        ia = min(a, appear(t, 44.0 + 1.2 * k))
        y = 0.72 - k * 0.11
        txt(CX, y + 0.015, l1, 40, ia)
        txt(CX, y - 0.022, l2, 30, ia, MUTED, "regular")
    ca = min(a, appear(t, 48.5))
    txt(CX, 0.37, "Here, R² summarizes in-sample fit vs a", 32, ca, FG, "medium")
    txt(CX, 0.34, "mean-only baseline. It doesn't validate the model.", 28, ca, FG, "medium")
    txt(CX, 0.275, "Source: Shalizi, CMU regression notes;", 26, ca, MUTED, "regular")
    txt(CX, 0.252, "UVA StatLab, \"Is R-squared Useless?\"", 26, ca, MUTED, "regular")


def footer(t):
    txt(CX, 0.205, "Simulated data · every number computed", 26, 0.9, MUTED, "regular")


DUR = 53.5
proc = subprocess.Popen(
    ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", "1080x1920",
     "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18",
     "-preset", "medium", "-movflags", "+faststart", OUT], stdin=subprocess.PIPE)
start, stop = (float(v) for v in (ARGS[1:3] if len(ARGS) > 2 else (0, DUR)))
for f in range(int(start * FPS), int(stop * FPS)):
    t = f / FPS
    fig.clf()
    for scene in (s1, s2, s3, s4, s5, s6):
        scene(t)
    footer(t)
    fig.canvas.draw()
    proc.stdin.write(fig.canvas.buffer_rgba().tobytes())
proc.stdin.close(); proc.wait()
print("done", OUT, STATS)
