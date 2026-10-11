"""9:16 short: dividends aren't free money. All numbers are worked examples.
Usage: python div_short_render.py out.mp4 [start end]
       python div_short_render.py --vo hank out.mp4      # timed to one voiceover read (69.5 s)
       python div_short_render.py --vo jessica out.mp4   # timed to another read (67.0 s)
       python div_short_render.py --stats-only"""
import subprocess, sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm

VOICE = sys.argv[sys.argv.index("--vo") + 1] if "--vo" in sys.argv else None
ARGS = [a for a in sys.argv[1:] if not a.startswith("--") and a != VOICE]
OUT = ARGS[0] if ARGS else "div_short.mp4"
FPS = 30

# ---- worked examples
P0, DIV = 100.0, 2.0
SHARES = 50
A_STOCK, A_CASH = SHARES * (P0 - DIV), SHARES * DIV        # dividend investor
SELL = A_CASH / P0                                          # shares B sells for the same cash
B_STOCK, B_CASH = (SHARES - SELL) * P0, SELL * P0           # no-dividend investor
assert A_STOCK == B_STOCK == 4900 and A_CASH == B_CASH == 100
RATE, BASIS = 0.15, 60.0
TAX_A = A_CASH * RATE                                       # whole dividend is income
TAX_B = SELL * (P0 - BASIS) * RATE                          # only the gain on shares sold
assert round(TAX_A, 2) == 15.0 and round(TAX_B, 2) == 6.0
LATER_A = SHARES * (P0 - DIV - BASIS) * RATE                # sell the rest at $98
LATER_B = (SHARES - SELL) * (P0 - BASIS) * RATE              # sell the rest at $100
TOTAL_TAX = TAX_A + LATER_A
assert round(TAX_A + LATER_A, 2) == round(TAX_B + LATER_B, 2) == 300.0  # timing differs, total doesn't
if "--stats-only" in sys.argv:
    print(f"after the dividend: A stock {A_STOCK:,.0f} + cash {A_CASH:,.0f}; B stock {B_STOCK:,.0f} + cash {B_CASH:,.0f}")
    print(f"tax now: A {TAX_A:.2f}, B {TAX_B:.2f}; tax on selling the rest: A {LATER_A:.2f}, B {LATER_B:.2f}; "
          f"total {TAX_A + LATER_A:.2f} vs {TAX_B + LATER_B:.2f}")
    sys.exit()

for f in fm.findSystemFonts():
    if "Inter" in f:
        fm.fontManager.addfont(f)
plt.rcParams["font.family"] = "Inter"
plt.rcParams["text.parse_math"] = False
BG, FG, MUTED = "#0b0f14", "#f2f5f7", "#9aa5b1"
TEAL, ORANGE, RED, GREEN, BLUE = "#3ccfc4", "#f2a541", "#ff5a5f", "#58d68d", "#6aa9ff"
STOCK_C, CASH_C = BLUE, GREEN
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


def stack(x0, w, y0, h, stock, cash, total, a, labels=True, cash_word="cash"):
    """Vertical stacked bar in figure coords: stock (bottom) + cash (top), scaled to `total`."""
    ax = fig.add_axes([x0, y0, w, h])
    ax.set_facecolor(BG)
    ax.axis("off")
    ax.bar([0], [stock], color=STOCK_C, alpha=a, width=0.8)
    ax.bar([0], [cash], bottom=[stock], color=CASH_C, alpha=a, width=0.8)
    ax.set_xlim(-0.5, 0.5); ax.set_ylim(0, total * 1.02)
    if labels:
        if stock > 0:
            ax.text(0, stock / 2, f"${stock:,.0f}\nstock", ha="center", va="center", color=BG,
                    size=30, weight="bold", alpha=a)
        if cash > 0:
            txt(x0 + w / 2, y0 + h + 0.016, f"+${cash:,.0f} {cash_word}", 30, a, CASH_C)


def note(lines, a):
    for k, s in enumerate(lines):
        txt(CX, 0.245 - k * 0.021, s, 20, a * 0.95, MUTED, "regular")


# ---- 1. hook (0-5)
def s1(t):
    a = fade(t, 0, 5)
    txt(CX, 0.66, f"A ${P0:.0f} stock pays", 72, a)
    txt(CX, 0.61, f"a ${DIV:.0f} dividend.", 72, a, CASH_C)
    txt(CX, 0.50, f"Did you just make ${DIV:.0f}?", 56, fade(t, 1.8, 5), ORANGE)


# ---- 2. the adjustment (5-17)
def s2(t):
    a = fade(t, 5, 17)
    if a <= 0:
        return
    head(a, "What actually happens", "1 share, in theory, all else equal")
    g = ease((t - 7.0) / 1.6)  # dividend leaves the stock
    stack(0.17, 0.26, 0.47, 0.30, P0, 0, P0, a)
    stack(0.57, 0.26, 0.47, 0.30, P0 - DIV * g, DIV * g, P0, a, cash_word="owed to you")
    txt(0.30, 0.445, "Before", 32, a, MUTED, "medium")
    txt(0.70, 0.445, "Ex-dividend date", 32, a, MUTED, "medium")
    c = min(a, appear(t, 9.0))
    txt(CX, 0.39, f"~${P0 - DIV:.0f} stock + ${DIV:.0f} owed = ${P0:.0f}", 44, c)
    txt(CX, 0.355, "cash arrives on the payment date · before taxes", 26, c, MUTED, "medium")
    c2 = min(a, appear(t, 11.8))
    txt(CX, 0.30, "The company pays you its own cash.", 34, c2, TEAL)
    txt(CX, 0.265, "Value moved. It wasn't created.", 34, c2, TEAL)


# ---- 3. two investors (17-32)
def s3(t):
    a = fade(t, 17, 32)
    if a <= 0:
        return
    head(a, "Two investors, 50 shares each", "Hypothetical companies, identical except payout")
    g = ease((t - 19.0) / 1.6)
    h = ease((t - 22.4) / 1.6)
    total = SHARES * P0
    stack(0.14, 0.26, 0.44, 0.26, total - A_CASH * g, A_CASH * g, total, a)
    stack(0.60, 0.26, 0.44, 0.26, total - B_CASH * h, B_CASH * h, total, a * appear(t, 21.6))
    txt(0.27, 0.81, "Gets a dividend", 32, a, CASH_C)
    txt(0.27, 0.783, f"${DIV:.0f}/share × {SHARES}", 26, a, MUTED, "medium")
    b = appear(t, 21.6)
    txt(0.73, 0.81, "No dividend", 32, a * b, ORANGE)
    txt(0.73, 0.783, f"sells {SELL:.0f} share for cash", 26, a * b, MUTED, "medium")
    c = min(a, appear(t, 25.0))
    txt(CX, 0.41, "Same value. Same cash.", 50, c)
    txt(CX, 0.37, f"${A_STOCK:,.0f} + ${A_CASH:,.0f} either way, before tax", 32, c, MUTED, "medium")
    c2 = min(a, appear(t, 27.4))
    txt(CX, 0.31, "A dividend is similar to cashing out", 34, c2, TEAL)
    txt(CX, 0.275, "part of your investment.", 34, c2, TEAL)


# ---- 4. taxes (32-43)
def s4(t):
    a = fade(t, 32, 43)
    if a <= 0:
        return
    head(a, "Where they differ: taxes", f"Taxable account · {RATE:.0%} rate · ${BASIS:.0f} basis · long-term")
    rows = [(33.0, "Dividend", f"All ${A_CASH:,.0f} is taxable now", TAX_A, CASH_C),
            (34.8, f"Sell {SELL:.0f} share", f"Only the ${SELL * (P0 - BASIS):,.0f} gain is taxed", TAX_B, ORANGE)]
    for k, (s_, name, how, tax, col) in enumerate(rows):
        ra = min(a, appear(t, s_))
        y = 0.77 - k * 0.15
        txt(CX, y + 0.035, name, 38, ra, col)
        txt(CX, y - 0.002, how, 30, ra, FG, "medium")
        txt(CX, y - 0.045, f"${tax:,.0f} tax this year", 50, ra, col)
    c = min(a, appear(t, 37.0))
    txt(CX, 0.47, "Sell everything later?", 36, c)
    txt(CX, 0.43, f"Same eventual tax here: ${TOTAL_TAX:,.0f}", 42, c, TEAL)
    txt(CX, 0.395, "assumes unchanged prices and tax rates", 24, c, MUTED, "regular")
    txt(CX, 0.365, "The edge is mostly timing and control.", 30, c, MUTED, "medium")
    c2 = min(a, appear(t, 39.4))
    txt(CX, 0.312, "In an IRA, 401(k) or Roth,", 28, c2)
    txt(CX, 0.285, "the difference mostly disappears.", 28, c2)
    note(["Illustration assumes qualified dividends and long-term gains taxed at 15%.",
          "Your rates, basis and holding periods will differ."], a)


# ---- 5. real markets (43-50): good news hides the adjustment
NEWS = 3.0
xs = np.linspace(0, 20, 121)
ramp = NEWS * (xs >= 10)  # news and the dividend adjustment land at the same moment
wig = 0.25 * np.sin(xs * 2.1) + 0.15 * np.sin(xs * 5.3)
NO_DIV = P0 + ramp + wig
ACTUAL = NO_DIV - DIV * (xs >= 10)
assert round(ACTUAL[-1] - wig[-1]) == P0 - DIV + NEWS


def s5(t):
    a = fade(t, 43, 50)
    if a <= 0:
        return
    head(a, "Why you might not see it", f"Hypothetical ex-dividend day with good news (+${NEWS:.0f})")
    ax = fig.add_axes([0.16, 0.47, 0.56, 0.30])
    ax.set_facecolor(BG)
    for s_ in ["top", "right"]:
        ax.spines[s_].set_visible(False)
    for s_ in ["left", "bottom"]:
        ax.spines[s_].set_color(MUTED)
    ax.set_xticks([]); ax.set_yticks([])
    n = min(len(xs), int(ease((t - 43.4) / 2.4) * len(xs)) + 1)
    ax.plot(xs[:n], NO_DIV[:n], color=MUTED, lw=3, ls="--", alpha=a)
    ax.plot(xs[:n], ACTUAL[:n], color=STOCK_C, lw=5, alpha=a)
    ax.axhline(P0, color=FG, lw=1, ls=":", alpha=0.5 * a)
    ax.axvline(10, color=CASH_C, lw=2, ls="--", alpha=a)
    ax.text(10.3, P0 + NEWS + 0.9, f"ex-dividend: −${DIV:.0f}", color=CASH_C, size=22, weight="bold", alpha=a)
    ax.set_xlim(0, 20); ax.set_ylim(P0 - DIV - 1.5, P0 + NEWS + 1.6)
    if n == len(xs):
        txt(0.80, 0.47 + 0.30 * (NO_DIV[-1] - (P0 - DIV - 1.5)) / (NEWS + DIV + 3.1), f"${P0 + NEWS:.0f}", 30, a, MUTED)
        txt(0.80, 0.47 + 0.30 * (ACTUAL[-1] - (P0 - DIV - 1.5)) / (NEWS + DIV + 3.1), f"${P0 - DIV + NEWS:.0f}", 30, a, STOCK_C)
    c = min(a, appear(t, 45.6))
    txt(CX, 0.415, f"Stock finished ${NEWS - DIV:.0f} higher", 38, c)
    txt(CX, 0.378, f"despite a ${DIV:.0f} dividend adjustment.", 32, c)
    txt(CX, 0.338, f"Without the dividend it would be ${P0 + NEWS:.0f}.", 28, c, MUTED, "medium")


# ---- 6. close (50-58.5)
def s6(t):
    a = fade(t, 50, 58.5)
    if a <= 0:
        return
    txt(CX, 0.70, "Dividends aren't bad.", 54, a)
    txt(CX, 0.655, "They aren't free money.", 54, a, ORANGE)
    c = min(a, appear(t, 52.2))
    txt(CX, 0.57, "Judge total return:", 44, c, TEAL)
    txt(CX, 0.53, "price change + dividends", 44, c, TEAL)
    c2 = min(a, appear(t, 54.4))
    txt(CX, 0.455, "Full explanation:", 30, c2, MUTED, "medium")
    txt(CX, 0.415, "Summitward.com", 44, c2, FG)
    txt(CX, 0.38, "link in description", 24, c2, MUTED, "regular")


def footer(t):
    txt(CX, 0.19, "Educational only · not investment or tax advice", 22, 0.85, MUTED, "regular")


DUR = 58.5
# audio time -> scene time, anchored to sentence starts in each voiceover read
ANCHORS = {
    "hank": ([0, 3.47, 5.43, 7.52, 15.85, 18.33, 21.0, 21.36, 24.37, 25.79, 34.58, 37.74, 40.9, 41.2, 43.35,
              47.85, 52.13, 54.5, 56.9, 57.2, 59.5, 61.7, 62.0, 65.28, 67.16, 69.5],
             [0, 1.8, 5.0, 7.0, 9.0, 11.8, 16.6, 17.2, 19.0, 21.6, 22.4, 25.0, 31.8, 32.4, 33.0,
              34.8, 37.0, 39.4, 42.6, 43.2, 45.6, 49.8, 50.2, 52.2, 54.4, 58.5]),
    "jessica": ([0, 3.29, 5.41, 7.46, 15.12, 17.55, 20.3, 20.6, 23.45, 24.9, 33.0, 36.16, 39.0, 39.4, 41.63,
                 45.76, 49.81, 52.0, 54.5, 54.75, 57.0, 59.1, 59.35, 62.71, 64.52, 67.0],
                [0, 1.8, 5.0, 7.0, 9.0, 11.8, 16.6, 17.2, 19.0, 21.6, 22.4, 25.0, 31.8, 32.4, 33.0,
                 34.8, 37.0, 39.4, 42.6, 43.2, 45.6, 49.8, 50.2, 52.2, 54.4, 58.5]),
}
# without a voiceover, stretch the scene timeline to the final pacing
NEW_B = [0, 5, 19, 35, 48, 53, 58.5]   # opening 5, mechanics 14, investors 16, taxes 13, price 5, close 5.5
OLD_B = [0, 5, 17, 32, 43, 50, 58.5]
A, V = ANCHORS[VOICE] if VOICE else (NEW_B, OLD_B)
assert len(A) == len(V) and all(np.diff(A) > 0) and all(np.diff(V) > 0)
DUR = A[-1]
proc = subprocess.Popen(
    ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", "1080x1920",
     "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18",
     "-preset", "medium", "-movflags", "+faststart", OUT], stdin=subprocess.PIPE)
start, stop = (float(v) for v in (ARGS[1:3] if len(ARGS) > 2 else (0, DUR)))
for f in range(int(start * FPS), int(stop * FPS)):
    t = float(np.interp(f / FPS, A, V))
    fig.clf()
    for scene in (s1, s2, s3, s4, s5, s6):
        scene(t)
    footer(t)
    fig.canvas.draw()
    proc.stdin.write(fig.canvas.buffer_rgba().tobytes())
proc.stdin.close(); proc.wait()
print("done", OUT, DUR)
