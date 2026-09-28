"""Sub-county and district breakdown of seasonal hospital access.

Usage: 04_district_breakdown.py [official|osm] [motorised|walking]  (same as the 03 run)

Reads the travel-time surfaces written by 03_seasonal_access.py (bands: dry day,
wet day, January-December under 2006-2025 rainfall) and produces:
  ../outputs/access_subcounties.csv     every sub-county x target: dry vs worst month
  ../figures/fig4_district_month_heatmap.png
                                        share of people > 1 h from a hospital by month,
                                        for the districts where the rains add most
  ../figures/districts/<district>.png   profile of each district in PROFILE_DISTRICTS:
                                        dry-day map, worst-month map, extra minutes,
                                        and the monthly curve
"""
import os
import numpy as np
import pandas as pd
import geopandas as gpd
import rasterio
from rasterio import features
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, BoundaryNorm

from facilities import load_health, run_from_argv, output_dirs
import cartography as C
import model

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
SOURCE, MODE = run_from_argv()
OUT, FIG = output_dirs(os.path.join(HERE, ".."), SOURCE, MODE)
os.makedirs(os.path.join(FIG, "districts"), exist_ok=True)

# Districts profiled, chosen to show different mechanisms:
PROFILE_DISTRICTS = [
    "Kotido",         # Karamoja: remote all year, few facilities
    "Nakapiripirit",  # Karamoja: among the largest seasonal penalties (May)
    "Agago",          # Acholi: large August jump on unpaved roads
    "Kasese",         # Rwenzori: mountain rivers, several priority crossings
    "Kikuube",        # Albertine: Kyangwali refugee settlement
    "Mayuge",         # Lake Victoria shore: Malongo tips from 59% to 93% in April
]
HEATMAP_ROWS = 30
MONTHS = list("JFMAMJJASOND")

# --- Inputs -----------------------------------------------------------------------
with rasterio.open(os.path.join(DATA, "uga_ppp_2020_1km.tif")) as src:
    pop = src.read(1).astype(float)
    pop = np.where((pop != src.nodata) & np.isfinite(pop), np.maximum(pop, 0), 0.0)
    transform, crs, shape = src.transform, src.crs, src.shape


def read_tt(slug):
    with rasterio.open(os.path.join(OUT, f"travel_time_{slug}.tif")) as src:
        a = src.read()
    return {"dry": a[0], "wet": a[1], **{m: a[m + 1] for m in range(1, 13)}}


TT = {"hospital": read_tt("hospital"), "HC IV or hospital": read_tt("hc_iv_or_hospital")}
districts = gpd.read_file(os.path.join(DATA, "uga_districts.geojson")).to_crs(crs)
subs = gpd.read_file(os.path.join(DATA, "uga_subcounties.geojson")).to_crs(crs)
# Draw boundaries clipped to land (admin polygons extend into the lakes); statistics use
# the 1 km land grid either way.
_land = C.land_polygon(model.Grid())
districts, subs = C.clip_to_land(districts, _land), C.clip_to_land(subs, _land)
health = load_health(SOURCE)
roads = gpd.read_file(os.path.join(DATA, "osm_features.gpkg"), layer="roads", engine="pyogrio",
                      where="highway IN ('trunk','primary','secondary','trunk_link','primary_link')")


def zone_ids(gdf):
    return features.rasterize(((g, i + 1) for i, g in enumerate(gdf.geometry)),
                              out_shape=shape, transform=transform, fill=0, dtype="int32")


def worst_month(st):
    """Month with the longest population-weighted mean travel time."""
    return max(range(1, 13), key=lambda m: st[m]["mean_h"])


def zone_stats(tt, sel):
    """Population-weighted access in one zone. Unreachable cells count as > 1 h / > 2 h
    and are left out of mean hours."""
    p = pop[sel]
    P = p.sum()
    out = {}
    for m in list(range(1, 13)) + ["dry", "wet"]:
        t = tt[m][sel]
        ok = np.isfinite(t)
        out[m] = dict(mean_h=np.average(t[ok], weights=p[ok]) if p[ok].sum() > 0 else np.nan,
                      over_1h=(p * ~(t <= 1)).sum() / P, over_2h=(p * ~(t <= 2)).sum() / P)
    return P, out


# --- Sub-county table ---------------------------------------------------------------
sub_id = zone_ids(subs)
rows, missing = [], 0
for target, tt in TT.items():
    for i, r in subs.reset_index(drop=True).iterrows():
        sel = (sub_id == i + 1) & (pop > 0)
        if not sel.any():
            missing += target == "hospital"
            continue
        P, st = zone_stats(tt, sel)
        worst = worst_month(st)
        rows.append(dict(target=target, district=r.adm2_name, county=r.adm3_name,
                         subcounty=r.adm4_name, population=P,
                         dry_mean_h=st["dry"]["mean_h"], worst_month=worst,
                         worst_month_mean_h=st[worst]["mean_h"],
                         dry_share_over_1h=st["dry"]["over_1h"],
                         worst_month_share_over_1h=st[worst]["over_1h"],
                         extra_people_over_1h=P * (st[worst]["over_1h"] - st["dry"]["over_1h"]),
                         wet_day_share_over_1h=st["wet"]["over_1h"]))
subtab = pd.DataFrame(rows).sort_values(["target", "extra_people_over_1h"], ascending=[True, False])
subtab.to_csv(os.path.join(OUT, "access_subcounties.csv"), index=False)

# --- District x month -----------------------------------------------------------------
dist_id = zone_ids(districts)
dist_rows = {}
for i, r in districts.reset_index(drop=True).iterrows():
    sel = (dist_id == i + 1) & (pop > 0)
    if sel.any():
        P, st = zone_stats(TT["hospital"], sel)
        unreachable = pop[sel & ~np.isfinite(TT["hospital"]["dry"])].sum() / P
        dist_rows[r.adm2_name] = dict(region=r.adm1_name, population=P, stats=st,
                                      unreachable=unreachable)
month_share = pd.DataFrame({d: {m: v["stats"][m]["over_1h"] for m in range(1, 13)}
                            for d, v in dist_rows.items()}).T
month_share.insert(0, "dry", [v["stats"]["dry"]["over_1h"] for v in dist_rows.values()])

# --- Figures ----------------------------------------------------------------------------
INK, INK2, GRID, SURF = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
BLUE, ORANGE = "#2a78d6", "#eb6834"
plt.rcParams.update({"font.size": 9, "axes.edgecolor": GRID, "axes.labelcolor": INK2,
                     "xtick.color": INK2, "ytick.color": INK2, "axes.spines.top": False,
                     "axes.spines.right": False, "axes.grid": True, "grid.color": GRID,
                     "grid.linewidth": 0.6, "figure.facecolor": SURF,
                     "axes.facecolor": SURF, "savefig.facecolor": SURF})
BLUES = ["#cde2fb", "#86b6ef", "#3987e5", "#1c5cab", "#0d366b"]
ORANGES = ["#fde6da", "#f6b596", "#eb6834", "#b8491c", "#7c2e0f"]

# Fig 4: heatmap of the districts where the rains add most (peak month minus dry day),
# grouped by region. Districts with >20% of people unreachable (islands; ferries are
# not modelled) are left out.
mainland = [d for d, v in dist_rows.items() if v["unreachable"] <= 0.2]
swing = (month_share.loc[mainland].iloc[:, 1:].max(axis=1) - month_share.loc[mainland, "dry"])
top = month_share.loc[swing.nlargest(HEATMAP_ROWS).index]
top = top.assign(region=[dist_rows[d]["region"] for d in top.index],
                 swing=swing).sort_values(["region", "swing"], ascending=[True, False])
vals = 100 * top.drop(columns=["region", "swing"]).values
fig, ax = plt.subplots(figsize=(8.2, 0.26 * len(top) + 1.4))
cmap = LinearSegmentedColormap.from_list("b", BLUES)
ax.imshow(vals, cmap=cmap, vmin=0, vmax=100, aspect="auto")
for i in range(vals.shape[0]):
    for j in range(vals.shape[1]):
        ax.text(j, i, f"{vals[i, j]:.0f}", ha="center", va="center", fontsize=6.5,
                color="white" if vals[i, j] > 55 else INK)
ax.set_xticks(range(13), ["dry"] + MONTHS)
ax.set_yticks(range(len(top)), [f"{d}  ({top.region[d].split()[0]})" for d in top.index])
ax.axvline(0.5, color=SURF, lw=3)
ax.grid(False)
for s in ax.spines.values():
    s.set_visible(False)
ax.set_title(f"% of people more than 1 hour from a hospital, by month\n"
             f"The {HEATMAP_ROWS} districts where the rains add most (island districts excluded)",
             fontsize=10, color=INK, loc="left")
fig.tight_layout()
fig.savefig(os.path.join(FIG, "fig4_district_month_heatmap.png"), dpi=180)
plt.close(fig)

# District profiles
bounds = [0, 0.5, 1, 2, 3, 4, 6, 100] if MODE == "motorised" else [0, 1, 2, 3, 4, 6, 8, 100]
tt_cmap = LinearSegmentedColormap.from_list("b", BLUES, N=len(bounds) - 1)
tt_norm = BoundaryNorm(bounds, tt_cmap.N)
d_bounds = [0, 5, 15, 30, 60, 120, 1e4]
d_cmap = LinearSegmentedColormap.from_list("o", ORANGES, N=len(d_bounds) - 1)
d_norm = BoundaryNorm(d_bounds, d_cmap.N)
hosp = health[health.level == "hospital"]
hc4 = health[health.level == "hc4"]

for name in PROFILE_DISTRICTS:
    idx = districts.index[districts.adm2_name == name]
    if len(idx) == 0:
        print("not found:", name)
        continue
    i = districts.index.get_loc(idx[0])
    geom = districts.geometry.iloc[i]
    mask = dist_id == i + 1
    rr, cc = np.where(mask)
    r0, r1, c0, c1 = rr.min() - 3, rr.max() + 4, cc.min() - 3, cc.max() + 4
    win = (slice(max(r0, 0), r1), slice(max(c0, 0), c1))
    west, north = transform * (win[1].start, win[0].start)
    east, south = transform * (win[1].stop, win[0].stop)
    extent = [west, east, south, north]
    st = dist_rows[name]["stats"]
    worst = worst_month(st)
    tt = TT["hospital"]
    clip = lambda a: np.where(mask[win], a[win], np.nan)
    dry, wm = clip(tt["dry"]), clip(tt[worst])
    extra = (wm - dry) * 60
    sub_in = subs[subs.adm2_name == name]
    near = lambda g: g.cx[west - 0.2:east + 0.2, south - 0.2:north + 0.2]

    fig = plt.figure(figsize=(13, 4.6))
    gs = fig.add_gridspec(2, 5, height_ratios=[1, 0.045], width_ratios=[1, 1, 1, 0.12, 1.1],
                          wspace=0.06, hspace=0.08)
    maps = [(dry, tt_cmap, tt_norm, "Dry day"),
            (wm, tt_cmap, tt_norm, f"{pd.Timestamp(2000, worst, 1):%B} (worst month)"),
            (extra, d_cmap, d_norm, "Extra minutes in worst month")]
    for k, (arr, cm, nm, title) in enumerate(maps):
        ax = fig.add_subplot(gs[0, k])
        ax.imshow(np.ma.masked_invalid(arr), cmap=cm, norm=nm, extent=extent,
                  interpolation="nearest")
        sub_in.boundary.plot(ax=ax, color="white", lw=0.4)
        gpd.GeoSeries([geom]).boundary.plot(ax=ax, color=INK, lw=0.8)
        near(roads).plot(ax=ax, color=INK2, lw=0.6)
        near(hc4).plot(ax=ax, marker="o", markersize=16, facecolor="white",
                       edgecolor=INK, lw=0.8, zorder=4)
        near(hosp).plot(ax=ax, marker="P", markersize=40, color=INK, edgecolor="white",
                        lw=0.6, zorder=5)
        ax.set_xlim(west, east)
        ax.set_ylim(south, north)
        ax.set_axis_off()
        ax.set_title(title, fontsize=9, color=INK, loc="left")
        C.scalebar(ax)
        C.north_arrow(ax)
    for cax_slot, nm, cm, ticks, label in ((gs[1, 0:2], tt_norm, tt_cmap, bounds, "hours to nearest hospital"),
                                           (gs[1, 2], d_norm, d_cmap, d_bounds, "extra minutes")):
        cb = fig.colorbar(plt.cm.ScalarMappable(norm=nm, cmap=cm), cax=fig.add_subplot(cax_slot),
                          orientation="horizontal", ticks=ticks[:-1])
        cb.set_label(label, fontsize=7.5)
        cb.ax.tick_params(labelsize=7)
        cb.outline.set_visible(False)
    ax = fig.add_subplot(gs[0, 4])
    for key, c, lab in (("over_1h", BLUE, "> 1 h"), ("over_2h", ORANGE, "> 2 h")):
        y = [100 * st[m][key] for m in range(1, 13)]
        ax.plot(range(1, 13), y, color=c, lw=2, marker="o", ms=3.5, label=lab)
        ax.axhline(100 * st["dry"][key], color=c, lw=0.8, ls="--")
    ax.set_xticks(range(1, 13), MONTHS)
    ax.set_ylim(0, 100)
    ax.set_ylabel("% of district population")
    ax.legend(frameon=False, fontsize=8, loc="upper left")
    ax.set_title("From a hospital, by month (dashed: dry day)", fontsize=9, color=INK, loc="left")
    n_h, n_4 = len(near(hosp).clip(geom)), len(near(hc4).clip(geom))
    fig.suptitle(f"{name} district: {dist_rows[name]['population'] / 1e3:,.0f}k people, "
                 f"{n_h} hospital{'s' * (n_h != 1)} and {n_4} HC IV{'s' * (n_4 != 1)} inside",
                 x=0.01, ha="left", color=INK, fontsize=11)
    fig.text(0.01, -0.04, "✚ hospital   ○ HC IV   lines: trunk and primary roads   white: sub-counties. "
             "Facilities outside the district are shown; people may use them.",
             fontsize=7.5, color=INK2)
    fig.savefig(os.path.join(FIG, "districts", f"{name}.png"), dpi=170, bbox_inches="tight")
    plt.close(fig)

pd.set_option("display.width", 220, "display.max_rows", 100)
print(f"sub-counties without a populated 1 km cell (too small for the grid): {missing}")
h = subtab[subtab.target == "hospital"]
print(h.head(20).round(2).to_string(index=False))
for name in PROFILE_DISTRICTS:
    if name in dist_rows:
        st = dist_rows[name]["stats"]
        worst = max(range(1, 13), key=lambda m: st[m]["over_1h"])
        print(f"{name:11s} >1h dry {100 * st['dry']['over_1h']:4.0f}%  worst ({worst:2d}) "
              f"{100 * st[worst]['over_1h']:4.0f}%  wet day {100 * st['wet']['over_1h']:4.0f}%")
