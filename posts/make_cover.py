"""Cover image for the Substack post and its X post (posts/images/00_cover.png, 1600x900).

Left: title and the headline numbers. Right: expected travel time to the nearest
hospital in April, from the model outputs.
"""
import os, sys
import numpy as np
import rasterio
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.colors import LinearSegmentedColormap, BoundaryNorm

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import model  # noqa: E402

FONTS = os.path.join(HERE, "fonts")
for f in os.listdir(FONTS):
    font_manager.fontManager.addfont(os.path.join(FONTS, f))
COND = font_manager.FontProperties(fname=os.path.join(FONTS, "IBMPlexSansCondensed-SemiBold.ttf"))
SANS = font_manager.FontProperties(fname=os.path.join(FONTS, "IBMPlexSans-Variable.ttf"))
MONO = font_manager.FontProperties(fname=os.path.join(FONTS, "IBMPlexMono-Medium.ttf"))

PAPER, INK, MUTED, WARM, WATER = "#f5f6f4", "#17212b", "#5b6570", "#b8491c", "#d3d6d9"
BLUES = ["#cde2fb", "#86b6ef", "#3987e5", "#1c5cab", "#0d366b"]
H = [0, 0.25, 0.5, 1, 1.5, 2, 3, 1e9]
cmap = LinearSegmentedColormap.from_list("b", BLUES, N=len(H) - 1)
norm = BoundaryNorm(H, cmap.N)

grid = model.Grid()
with rasterio.open(os.path.join(HERE, "..", "outputs", "travel_time_hospital.tif")) as src:
    april = src.read(6)
arr = np.ma.masked_invalid(np.where(grid.land, april, np.nan))
ext = [grid.cols_lon[0], grid.cols_lon[-1], grid.rows_lat[-1], grid.rows_lat[0]]

fig = plt.figure(figsize=(16, 9), dpi=100, facecolor=PAPER)
ax = fig.add_axes([0.50, 0.17, 0.48, 0.80])
ax.set_facecolor(PAPER)
ax.imshow(arr, cmap=cmap, norm=norm, extent=ext, interpolation="nearest",
          aspect=1 / np.cos(np.radians(1.3)))
ax.set_axis_off()

T = lambda x, y, s, **k: fig.text(x, y, s, color=k.pop("color", INK), va="top", ha="left", **k)
T(0.055, 0.88, "UGANDA  ·  RAINY-SEASON ACCESS", fontproperties=SANS, fontsize=15, color=MUTED)
T(0.055, 0.82, "When the rains come,\nthe hospital moves\nfurther away", fontproperties=COND,
  fontsize=58, linespacing=1.05)
T(0.055, 0.40, "13%", fontproperties=MONO, fontsize=52, color=MUTED)
T(0.165, 0.395, "→", fontproperties=SANS, fontsize=44, color=MUTED)
T(0.215, 0.40, "18%", fontproperties=MONO, fontsize=52, color=WARM)
T(0.055, 0.29, "of Ugandans more than an hour from a hospital:\ndry weather → April, the peak of the long rains",
  fontproperties=SANS, fontsize=16.5, color=INK, linespacing=1.4)
T(0.055, 0.175, "Poorest fifth: 23% → 32%.  Richest fifth: under 1%.",
  fontproperties=SANS, fontsize=16.5, color=INK)
T(0.055, 0.075, "Modelled from OpenStreetMap roads, WorldPop and 45 years of CHIRPS rainfall",
  fontproperties=SANS, fontsize=12.5, color=MUTED)
# Key and scale bar for the map
import cartography as C  # noqa: E402
C.scalebar(ax, km=100)
LAB = ["< 15 min", "15–30", "30–60", "1–1.5 h", "1.5–2", "2–3", "> 3 h"]
kx, ky, kw, kh = 0.555, 0.105, 0.052, 0.022
fig.text(kx, ky + kh + 0.012, "Travel time to the nearest hospital, April", fontproperties=SANS,
         fontsize=12, color=INK, va="bottom")
for i, lab in enumerate(LAB):
    fig.patches.append(matplotlib.patches.Rectangle((kx + i * kw, ky), kw, kh, transform=fig.transFigure,
                                                    facecolor=cmap(i), edgecolor=PAPER, linewidth=1.5))
    fig.text(kx + (i + 0.5) * kw, ky - 0.008, lab, fontproperties=SANS, fontsize=10.5, color=MUTED,
             ha="center", va="top")
out = os.path.join(HERE, "images", "00_cover.png")
fig.savefig(out, dpi=100, facecolor=PAPER)
print("wrote", out)
