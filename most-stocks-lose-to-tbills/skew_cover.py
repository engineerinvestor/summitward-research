"""1080x1920 cover for the 'most stocks lose to T-bills' short. Real data only (Bessembinder 2026).
Usage: python skew_cover.py [out.png]"""
import sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm

for f in fm.findSystemFonts():
    if "Inter" in f:
        fm.fontManager.addfont(f)
plt.rcParams["font.family"] = "Inter"
plt.rcParams["text.parse_math"] = False
BG, FG, MUTED = "#0b0f14", "#f2f5f7", "#9aa5b1"
TEAL, RED = "#3ccfc4", "#ff5a5f"

fig = plt.figure(figsize=(10.8, 19.2), dpi=100)
fig.patch.set_facecolor(BG)


def txt(y, s, size, color=FG, weight="bold"):
    fig.text(0.5, y, s, size=size, color=color, weight=weight, ha="center", va="center")


# Key content sits in the middle so 1:1 and 4:5 grid crops keep it.
txt(0.81, "Most stocks lose", 84)
txt(0.748, "to T-bills.", 84, RED)

ax = fig.add_axes([0.22, 0.39, 0.56, 0.315])
ax.set_facecolor(BG)
ax.axis("off")
k = np.arange(100)
ax.scatter(k % 10, 9 - k // 10, s=1050, c=[RED if i < 59 else TEAL for i in k], marker="s", lw=0)
ax.set_xlim(-0.7, 9.7); ax.set_ylim(-0.7, 9.7)

txt(0.355, "59% of firms trailed T-bills", 40, RED)
txt(0.295, "The market still made", 50)
txt(0.243, "$91 trillion", 78, TEAL)
txt(0.198, "above T-bills · U.S. stocks 1926–2025 · Bessembinder (2026)", 24, MUTED, "regular")
txt(0.12, "@egr_investor", 34, MUTED, "medium")

OUT = sys.argv[1] if len(sys.argv) > 1 else "skew_cover.png"
fig.savefig(OUT, facecolor=BG)
print("wrote", OUT)
