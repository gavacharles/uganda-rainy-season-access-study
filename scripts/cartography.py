"""Map furniture shared by every static map: title, key, scale bar, north arrow and
non-overlapping labels. Maps are drawn in longitude/latitude; the scale bar is
computed for the map's central latitude.
"""
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, BoundaryNorm
from matplotlib.patches import Rectangle, FancyArrow
from adjustText import adjust_text

INK, INK2, SURF, LAND, WATER = "#0b0b0b", "#52514e", "#fcfcfb", "#f0efec", "#d3d6d9"
BLUES = ["#cde2fb", "#86b6ef", "#3987e5", "#1c5cab", "#0d366b"]
ORANGES = ["#fde6da", "#f6b596", "#eb6834", "#b8491c", "#7c2e0f"]
DIVERGING = ["#b8491c", "#f6b596", "#e9e6df", "#86b6ef", "#1c5cab"]
MONTH_NAMES = ["January", "February", "March", "April", "May", "June", "July", "August",
               "September", "October", "November", "December"]


def land_polygon(grid):
    """Uganda's land (WorldPop land mask) as one polygon: lakes excluded."""
    import geopandas as gpd
    from rasterio import features
    from shapely.geometry import shape
    geoms = [shape(g) for g, v in features.shapes(grid.land.astype("uint8"), mask=grid.land,
                                                   transform=grid.transform) if v == 1]
    return gpd.GeoDataFrame(geometry=[gpd.GeoSeries(geoms).union_all()], crs=4326)


def clip_to_land(gdf, land):
    """Clip admin polygons to land, so lake portions (Lake Victoria etc.) are not drawn."""
    import geopandas as gpd
    out = gpd.clip(gdf.to_crs(4326), land, keep_geom_type=True)
    return out.loc[gdf.index.intersection(out.index)].reindex(gdf.index)


def setup():
    plt.rcParams.update({"font.size": 9, "figure.facecolor": SURF, "savefig.facecolor": SURF,
                         "axes.facecolor": SURF})


def scale(bounds, colors):
    cmap = LinearSegmentedColormap.from_list("s", colors, N=len(bounds) - 1)
    return cmap, BoundaryNorm(bounds, cmap.N)


def frame(ax, extent):
    """Fix the map extent and aspect (cos-latitude), hide axes, water background."""
    x0, x1, y0, y1 = extent
    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)
    ax.set_aspect(1 / np.cos(np.radians((y0 + y1) / 2)))
    ax.set_facecolor(WATER)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_xticks([])
    ax.set_yticks([])


def scalebar(ax, km=None, loc="lower right"):
    """Alternating black/white scale bar in km, sized to ~20% of the map width."""
    x0, x1 = ax.get_xlim()
    y0, y1 = ax.get_ylim()
    kmdeg = 111.32 * np.cos(np.radians((y0 + y1) / 2))
    if km is None:
        target = 0.2 * (x1 - x0) * kmdeg
        km = min((1, 2, 5, 10, 20, 25, 50, 100, 200), key=lambda k: abs(k - target))
    w = km / kmdeg
    h = 0.012 * (y1 - y0)
    bx = x1 - 0.04 * (x1 - x0) - w if "right" in loc else x0 + 0.04 * (x1 - x0)
    by = y0 + 0.045 * (y1 - y0)
    for k in range(2):
        ax.add_patch(Rectangle((bx + k * w / 2, by), w / 2, h, facecolor=INK if k == 0 else "white",
                               edgecolor=INK, linewidth=0.6, zorder=20))
    ax.apply_aspect()
    px = ax.transData.transform((bx + w, by))[0] - ax.transData.transform((bx, by))[0]
    ticks = ((0, "0"), (0.5, f"{km / 2:g}"), (1, f"{km:g} km")) if px > 60 else ((0, "0"), (1, f"{km:g} km"))
    for frac, lab in ticks:
        ax.text(bx + frac * w, by + 1.8 * h, lab, ha="center", va="bottom", fontsize=6.8,
                color=INK, zorder=20,
                bbox=dict(boxstyle="square,pad=0.1", fc=SURF, ec="none", alpha=0.7))


def north_arrow(ax, loc="upper right"):
    x0, x1 = ax.get_xlim()
    y0, y1 = ax.get_ylim()
    x = x1 - 0.06 * (x1 - x0) if "right" in loc else x0 + 0.06 * (x1 - x0)
    y = y1 - 0.14 * (y1 - y0)
    L = 0.07 * (y1 - y0)
    ax.add_patch(FancyArrow(x, y, 0, L, width=0.012 * (x1 - x0), head_width=0.035 * (x1 - x0),
                            head_length=0.03 * (y1 - y0), length_includes_head=True,
                            color=INK, zorder=20))
    ax.text(x, y - 0.02 * (y1 - y0), "N", ha="center", va="top", fontsize=8, fontweight="bold",
            color=INK, zorder=20)


def furniture(ax, km=None, arrow=True):
    scalebar(ax, km)
    if arrow:
        north_arrow(ax)


def key(fig, axes, cmap, norm, bounds, label, labels=None, orientation="vertical"):
    """Stepped colour key: one equal-sized block per class, labelled at its centre
    (labels) or at the class boundaries (from bounds, open ends left blank)."""
    from matplotlib.colors import BoundaryNorm, ListedColormap
    n = len(bounds) - 1
    steps = ListedColormap([cmap(i) for i in range(cmap.N)][:n])
    kw = dict(fraction=0.03, pad=0.02) if orientation == "vertical" else dict(fraction=0.05, pad=0.03)
    cb = fig.colorbar(plt.cm.ScalarMappable(norm=BoundaryNorm(np.arange(n + 1), n), cmap=steps),
                      ax=axes, orientation=orientation, **kw)
    if labels is not None:
        cb.set_ticks(np.arange(n) + 0.5)
        cb.set_ticklabels(labels)
    else:
        idx = [i for i, b in enumerate(bounds) if abs(b) < 1e8]
        cb.set_ticks(idx)
        cb.set_ticklabels([f"{bounds[i]:g}" for i in idx])
    cb.set_label(label, fontsize=8)
    cb.ax.tick_params(labelsize=7, length=0)
    cb.outline.set_visible(False)
    return cb


def outside_legend(ax, handles, labels, title, **kw):
    """Legend to the right of the map frame, clear of the data."""
    return ax.legend(handles, labels, title=title, frameon=False, fontsize=7.5, title_fontsize=8,
                     loc="upper left", bbox_to_anchor=(1.02, 0.35), borderaxespad=0, **kw)


def labels(ax, xs, ys, texts, fontsize=7, color=INK, **kw):
    """Place point labels and move them apart so none overlap, with leader lines."""
    ts = [ax.text(x, y, t, fontsize=fontsize, color=color, zorder=15,
                  bbox=dict(boxstyle="round,pad=0.15", fc=SURF, ec="none", alpha=0.8))
          for x, y, t in zip(xs, ys, texts)]
    if ts:
        adjust_text(ts, x=list(xs), y=list(ys), ax=ax, expand=(1.3, 1.5),
                    arrowprops=dict(arrowstyle="-", color=INK2, lw=0.5), **kw)
    return ts


def title(fig, text, subtitle=None):
    fig.suptitle(text, x=0.01, ha="left", color=INK, fontsize=12, y=0.995)
    if subtitle:
        fig.text(0.01, 0.955, subtitle, ha="left", va="top", fontsize=8.5, color=INK2)


def source(fig, text):
    fig.text(0.01, 0.003, text, fontsize=7, color=INK2, va="bottom")
