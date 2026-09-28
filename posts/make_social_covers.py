"""Cover images for the Substack post and the LinkedIn post.

  images/00_cover_substack.png  2400x1260 (1.91:1, Substack header and link preview)
  images/00_cover_linkedin.png  2160x2700 (4:5 portrait, fills the LinkedIn feed)

Both show the same comparison: travel time to the nearest hospital on a dry day
and on a rainy day (every unpaved road wet), with the share of people more than
an hour away under each map. 00_cover.png (make_cover.py) is kept for X.
"""
import os, sys
import numpy as np
import rasterio
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.colors import LinearSegmentedColormap, BoundaryNorm
from matplotlib.patches import Rectangle

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import model  # noqa: E402

FONTS = os.path.join(HERE, "fonts")
for f in os.listdir(FONTS):
    font_manager.fontManager.addfont(os.path.join(FONTS, f))
COND = font_manager.FontProperties(fname=os.path.join(FONTS, "IBMPlexSansCondensed-SemiBold.ttf"))
SANS = font_manager.FontProperties(fname=os.path.join(FONTS, "IBMPlexSans-Variable.ttf"))
MONO = font_manager.FontProperties(fname=os.path.join(FONTS, "IBMPlexMono-Medium.ttf"))

PAPER, INK, MUTED, WARM = "#f5f6f4", "#17212b", "#5b6570", "#b8491c"
BLUES = ["#e3eefb", "#cde2fb", "#86b6ef", "#3987e5", "#1c5cab", "#0d366b", "#071f3f"]
H = [0, 0.25, 0.5, 1, 1.5, 2, 3, 1e9]
cmap = LinearSegmentedColormap.from_list("b", BLUES, N=len(H) - 1)
norm = BoundaryNorm(H, cmap.N)
URL = "gavacharles.github.io/uganda-rainy-season-access"

grid = model.Grid()
with rasterio.open(os.path.join(HERE, "..", "outputs", "travel_time_hospital.tif")) as src:
    dry, wet = src.read(1), src.read(2)
EXT = [grid.cols_lon[0], grid.cols_lon[-1], grid.rows_lat[-1], grid.rows_lat[0]]
ASPECT = 1 / np.cos(np.radians((EXT[2] + EXT[3]) / 2))


def draw_map(fig, rect, arr):
    ax = fig.add_axes(rect)
    ax.imshow(np.ma.masked_invalid(np.where(grid.land, arr, np.nan)), cmap=cmap, norm=norm,
              extent=EXT, interpolation="nearest", aspect=ASPECT)
    ax.set_axis_off()
    return ax


def key(fig, x, y, w, h, size):
    """Seven-step key, labelled only at its ends: close <-> far."""
    n = cmap.N
    for i in range(n):
        fig.patches.append(Rectangle((x + i * w / n, y), w / n, h, transform=fig.transFigure,
                                     facecolor=cmap(i), edgecolor=PAPER, linewidth=1.2))
    fig.text(x, y - 0.35 * h, "under 15 min", fontproperties=SANS, fontsize=size, color=MUTED,
             ha="left", va="top")
    fig.text(x + w, y - 0.35 * h, "over 3 hours", fontproperties=SANS, fontsize=size, color=MUTED,
             ha="right", va="top")
    fig.text(x + w / 2, y + h * 1.6, "Travel time to the nearest hospital", fontproperties=SANS,
             fontsize=size, color=INK, ha="center", va="bottom")


def label(fig, x, y, tag, stat, colour, s_tag, s_stat, s_line, line_gap):
    T = lambda yy, s, **k: fig.text(x, yy, s, ha="center", va="top", **k)
    T(y, tag, fontproperties=SANS, fontsize=s_tag, color=MUTED, fontweight="bold")
    T(y - line_gap[0], stat, fontproperties=MONO, fontsize=s_stat, color=colour)
    T(y - line_gap[1], "of people are more than\nan hour from a hospital", fontproperties=SANS,
      fontsize=s_line, color=INK, linespacing=1.25)


def substack():
    fig = plt.figure(figsize=(12, 6.3), dpi=200, facecolor=PAPER)
    T = lambda x, y, s, **k: fig.text(x, y, s, color=k.pop("color", INK), va="top", ha="left", **k)
    T(0.05, 0.89, "UGANDA  ·  RAINY-SEASON ACCESS", fontproperties=SANS, fontsize=11, color=MUTED)
    T(0.05, 0.82, "When the rains\ncome, the\nhospital moves\nfurther away", fontproperties=COND,
      fontsize=37, linespacing=1.02)
    T(0.05, 0.25, "Every April, 2.3 million more\nUgandans are pushed past the\none-hour mark.",
      fontproperties=SANS, fontsize=12.5, linespacing=1.35)
    T(0.05, 0.075, URL, fontproperties=SANS, fontsize=9, color=MUTED)

    w, hgt, y0 = 0.255, 0.60, 0.36
    draw_map(fig, [0.425, y0, w, hgt], dry)
    draw_map(fig, [0.715, y0, w, hgt], wet)
    fig.text(0.70, y0 + hgt * 0.55, "→", fontproperties=SANS, fontsize=30, color=MUTED,
             ha="center", va="center")
    label(fig, 0.5525, 0.35, "DRY DAY", "13%", INK, 11, 30, 10.5, (0.035, 0.115))
    label(fig, 0.8425, 0.35, "RAINY DAY", "31%", WARM, 11, 30, 10.5, (0.035, 0.115))
    key(fig, 0.5975, 0.055, 0.20, 0.02, 8.5)
    out = os.path.join(HERE, "images", "00_cover_substack.png")
    fig.savefig(out, dpi=200, facecolor=PAPER)
    print("wrote", out)


def linkedin():
    fig = plt.figure(figsize=(10.8, 13.5), dpi=200, facecolor=PAPER)
    T = lambda x, y, s, **k: fig.text(x, y, s, color=k.pop("color", INK), va="top", ha="left", **k)
    T(0.07, 0.945, "UGANDA  ·  RAINY-SEASON ACCESS", fontproperties=SANS, fontsize=17, color=MUTED)
    T(0.07, 0.915, "When the rains come,\nthe hospital moves\nfurther away", fontproperties=COND,
      fontsize=58, linespacing=1.02)

    w, hgt, y0 = 0.43, 0.36, 0.36
    draw_map(fig, [0.05, y0, 0.41, hgt], dry)
    draw_map(fig, [0.54, y0, 0.41, hgt], wet)
    fig.text(0.50, y0 + hgt * 0.55, "→", fontproperties=SANS, fontsize=40, color=MUTED,
             ha="center", va="center")
    label(fig, 0.255, 0.355, "DRY DAY", "13%", INK, 16, 48, 16, (0.025, 0.078))
    label(fig, 0.745, 0.355, "RAINY DAY", "31%", WARM, 16, 48, 16, (0.025, 0.078))
    key(fig, 0.30, 0.19, 0.40, 0.014, 13)

    fig.lines.append(plt.Line2D([0.07, 0.93], [0.125, 0.125], transform=fig.transFigure,
                                color="#d9dcd8", linewidth=1.5))
    T(0.07, 0.105, "Every April, 2.3 million more Ugandans are\npushed past the one-hour mark.",
      fontproperties=SANS, fontsize=19, linespacing=1.3)
    T(0.07, 0.035, "Explore the map: " + URL, fontproperties=SANS, fontsize=14, color=MUTED)
    out = os.path.join(HERE, "images", "00_cover_linkedin.png")
    fig.savefig(out, dpi=200, facecolor=PAPER)
    print("wrote", out)


substack()
linkedin()
