"""1080x1920 cover for the R² short. Uses the same Demo A data as the video.
Usage: python r2_quality_cover.py [out.png]"""
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm

import pathlib, sys
HERE = pathlib.Path(__file__).resolve().parent
src = (HERE / "r2_quality_render.py").read_text().split("for f in fm.findSystemFonts")[0]
ns = {"__name__": "cover"}
exec(src, ns)
demoA = ns["demoA"]

for f in fm.findSystemFonts():
    if "Inter" in f:
        fm.fontManager.addfont(f)
plt.rcParams["font.family"] = "Inter"
plt.rcParams["text.parse_math"] = False
BG, FG, MUTED = "#0b0f14", "#f2f5f7", "#9aa5b1"
TEAL, RED, BLUE = "#3ccfc4", "#ff5a5f", "#6aa9ff"

fig = plt.figure(figsize=(10.8, 19.2), dpi=100)
fig.patch.set_facecolor(BG)


def txt(x, y, s, size, color=FG, weight="bold"):
    fig.text(x, y, s, size=size, color=color, weight=weight, ha="center", va="center")


# Key content sits in the middle ~70% so 1:1 and 4:5 grid crops keep it.
txt(0.5, 0.78, "R² isn't a", 88)
txt(0.5, 0.728, "model-quality score", 72, TEAL)

for k, (hi, color) in enumerate([(10, TEAL), (2, RED)]):
    x, y, (a0, b0, r2, rmse, _) = demoA(hi)
    left = 0.07 + k * 0.47
    ax = fig.add_axes([left, 0.40, 0.40, 0.25])
    ax.set_facecolor(BG)
    for s in ["top", "right"]:
        ax.spines[s].set_visible(False)
    for s in ["left", "bottom"]:
        ax.spines[s].set_color(MUTED)
    ax.set_xticks([]); ax.set_yticks([])
    ax.scatter(x, y, s=40, color=BLUE, alpha=0.85, lw=0)
    xx = np.array([x.min(), x.max()])
    ax.plot(xx, a0 + b0 * xx, color=FG, lw=4)
    ax.set_xlim(0, 11); ax.set_ylim(0, 17)
    cx = left + 0.20
    txt(cx, 0.355, f"R² = {r2:.2f}", 66, color)
    txt(cx, 0.315, f"residual RMSE {rmse:.2f}", 32, MUTED, "medium")

txt(0.5, 0.255, "Same true relationship.", 48)
txt(0.5, 0.222, "Same residual error.", 48)
txt(0.5, 0.18, "4 R² myths, simulated", 38, MUTED, "medium")
txt(0.5, 0.12, "@egr_investor", 34, MUTED, "medium")

OUT = sys.argv[1] if len(sys.argv) > 1 else "r2_quality_cover.png"
fig.savefig(OUT, facecolor=BG)
print("wrote", OUT)
