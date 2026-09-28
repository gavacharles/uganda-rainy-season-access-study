"""GIS map series from the outputs of 03-07. Every map has a title, a key, a scale bar
and a north arrow; point labels are placed so they do not overlap.

National maps (../figures/maps/):
  m01_hospital_dry_wet.png        travel time to a hospital, dry day vs wet day
  m02_hospital_by_month.png       the same for each month (2006-2025 rainfall)
  m03_destinations.png            five destination types, dry day vs April
  m04_emoc_motorised_walking.png  emergency obstetric care, motorised vs on foot
  m05_emoc_women_districts.png    women 15-49 > 2 h from EmOC by district, worst month
  m06_wealth_and_penalty.png      relative wealth vs minutes added in April
  m07_hospital_catchments.png     hospitals whose catchments lose most in April
  m08_crossings.png               priority river crossings over the wet-day surface
Sub-county maps (../figures/maps/subcounty/):
  s01_hospital_share.png          > 1 h from a hospital: dry, worst month, increase
  s02_worst_season.png            the season in which access is worst
  s03_people_pushed_over_1h.png   people pushed beyond 1 h in the worst month
  s04_walking_any_facility.png    on foot to any facility: dry, worst month, increase
  s05_emoc_women_walking.png      women 15-49 > 2 h on foot from EmOC: dry, worst
  s06_school_market.png           > 1 h from a secondary school / a market, April
  s07_wealth.png                  mean Relative Wealth Index
  s08_regional_zooms.png          increase by region, top sub-counties labelled
"""
import os
import numpy as np
import pandas as pd
import geopandas as gpd
import rasterio
from scipy.spatial import cKDTree
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from matplotlib.lines import Line2D

import model
import cartography as C
from zonal import Zones

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
OUT = os.path.join(HERE, "..", "outputs")
FIG = os.path.join(HERE, "..", "figures", "maps")
FIG_SC = os.path.join(FIG, "subcounty")
os.makedirs(FIG_SC, exist_ok=True)
C.setup()
SRC = "Sources: OSM roads; official public/PNFP facilities (Maina et al. 2019); WorldPop 2020; CHIRPS rainfall 2006–2025."

grid = model.Grid()
groups = model.population_groups(grid)
pop, women = groups["everyone"], groups["women 15-49"]
EXT = [grid.cols_lon[0] - 0.02, grid.cols_lon[-1] + 0.02, grid.rows_lat[-1] - 0.02, grid.rows_lat[0] + 0.02]
IMG_EXT = [grid.cols_lon[0], grid.cols_lon[-1], grid.rows_lat[-1], grid.rows_lat[0]]
districts = gpd.read_file(os.path.join(DATA, "uga_districts.geojson")).to_crs(4326)
subs = gpd.read_file(os.path.join(DATA, "uga_subcounties.geojson")).to_crs(4326)
land_poly = C.land_polygon(grid)
districts = C.clip_to_land(districts, land_poly)
subs = C.clip_to_land(subs, land_poly)


def read(run, slug):
    with rasterio.open(os.path.join(OUT, run, f"travel_time_{slug}.tif")) as src:
        return src.read()


def raster_panel(ax, arr, cmap, norm, title, km=100):
    C.frame(ax, EXT)
    ax.imshow(np.ma.masked_invalid(np.where(grid.land, arr, np.nan)), cmap=cmap, norm=norm,
              extent=IMG_EXT, interpolation="nearest", zorder=1)
    districts.boundary.plot(ax=ax, color="white", linewidth=0.2, zorder=2)
    ax.set_title(title, fontsize=9, color=C.INK, loc="left")
    C.furniture(ax, km)


def choropleth_panel(ax, gdf, col, cmap, norm, title, extent=EXT, km=100, edge=0.08):
    C.frame(ax, extent)
    land_poly.plot(ax=ax, color=C.LAND, zorder=0)
    gdf.plot(ax=ax, column=col, cmap=cmap, norm=norm, edgecolor="white", linewidth=edge,
             missing_kwds=dict(color=C.LAND), zorder=1)
    districts.boundary.plot(ax=ax, color=C.INK2, linewidth=0.15, zorder=2)
    ax.set_title(title, fontsize=9, color=C.INK, loc="left")
    C.furniture(ax, km)


def save(fig, path):
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)


H = [0, 0.25, 0.5, 1, 1.5, 2, 3, 1e9]
H_LAB = ["< 15 min", "15–30 min", "30–60 min", "1–1.5 h", "1.5–2 h", "2–3 h", "> 3 h"]
h_cmap, h_norm = C.scale(H, C.BLUES)
W = [0, 0.5, 1, 2, 3, 4, 6, 1e9]
W_LAB = ["< 30 min", "30–60 min", "1–2 h", "2–3 h", "3–4 h", "4–6 h", "> 6 h"]
w_cmap, w_norm = C.scale(W, C.BLUES)
S = [0, 0.05, 0.1, 0.25, 0.5, 0.75, 0.9, 1.0001]
S_LAB = ["< 5%", "5–10%", "10–25%", "25–50%", "50–75%", "75–90%", "> 90%"]
s_cmap, s_norm = C.scale(S, C.BLUES)
I = [-1, 0.02, 0.05, 0.1, 0.2, 0.3, 0.5, 1.0001]
I_LAB = ["< 2 pts", "2–5", "5–10", "10–20", "20–30", "30–50", "> 50 pts"]
i_cmap, i_norm = C.scale(I, C.ORANGES)

hosp = read("", "hospital")
emoc = read("", "hc_iv_or_hospital")
walk_emoc = read("walking", "hc_iv_or_hospital")
walk_any = read("walking", "any_facility")

# --- m01: hospital dry vs wet -------------------------------------------------------------
fig, axes = plt.subplots(1, 2, figsize=(11, 5.6))
for ax, (b, t) in zip(axes, ((0, "Every day dry"), (1, "Every day wet"))):
    raster_panel(ax, hosp[b], h_cmap, h_norm,
                 f"{t}: {100 * grid.pop_stats(hosp[b])['share_over_1h']:.1f}% of people > 1 h")
C.key(fig, axes, h_cmap, h_norm, H, "travel time to the nearest hospital", H_LAB)
C.title(fig, "Travel time to the nearest hospital, dry vs wet conditions",
        "Motorised where there is a road. Wet day: unpaved roads slowed, fords near-impassable.")
C.source(fig, SRC)
save(fig, os.path.join(FIG, "m01_hospital_dry_wet.png"))

# --- m02: hospital by month ------------------------------------------------------------------
fig, axes = plt.subplots(3, 4, figsize=(13, 11.5))
for m, ax in enumerate(axes.flat):
    raster_panel(ax, hosp[m + 2], h_cmap, h_norm,
                 f"{C.MONTH_NAMES[m]}: {100 * grid.pop_stats(hosp[m + 2])['share_over_1h']:.1f}% > 1 h")
C.key(fig, axes, h_cmap, h_norm, H, "expected travel time to the nearest hospital", H_LAB)
C.title(fig, "Travel time to the nearest hospital through the year",
        "Expected time in each month given how often it rains there (CHIRPS 2006–2025), motorised.")
C.source(fig, SRC)
save(fig, os.path.join(FIG, "m02_hospital_by_month.png"))

# --- m03: destinations -------------------------------------------------------------------------
DESTS = [("any_facility", "Any health facility"), ("hc_iv_or_hospital", "HC IV or hospital"),
         ("secondary_school", "Secondary school"), ("market", "Market"), ("town", "Town")]
fig, axes = plt.subplots(2, len(DESTS), figsize=(3.3 * len(DESTS), 7.8))
for j, (slug, label) in enumerate(DESTS):
    a = read("", slug)
    for i, (b, when) in enumerate(((0, "dry day"), (5, "April"))):
        raster_panel(axes[i, j], a[b], h_cmap, h_norm,
                     f"{label}, {when}\n{100 * grid.pop_stats(a[b])['share_over_1h']:.1f}% of people > 1 h")
C.key(fig, axes, h_cmap, h_norm, H, "travel time to the nearest", H_LAB)
C.title(fig, "Travel time to five kinds of destination, dry day vs April",
        "Motorised. Schools, markets and towns from OpenStreetMap; secondary schools are ISCED 2–3 or secondary-type names.")
C.source(fig, SRC)
save(fig, os.path.join(FIG, "m03_destinations.png"))

# --- m04: EmOC motorised vs walking ----------------------------------------------------------------
fig, axes = plt.subplots(1, 3, figsize=(15, 5.6))
for ax, (arr, t) in zip(axes, ((emoc[5], "By road, April"), (walk_emoc[0], "On foot, dry day"),
                               (walk_emoc[5], "On foot, April"))):
    raster_panel(ax, arr, w_cmap, w_norm,
                 f"{t}: {100 * grid.pop_stats(arr, women)['share_over_2h']:.0f}% of women 15–49 > 2 h")
C.key(fig, axes, w_cmap, w_norm, W, "travel time to the nearest HC IV or hospital", W_LAB)
C.title(fig, "Emergency obstetric care: travel time to the nearest HC IV or hospital",
        "The WHO/Lancet benchmark is surgical and obstetric care within 2 hours.")
C.source(fig, SRC)
save(fig, os.path.join(FIG, "m04_emoc_motorised_walking.png"))

# --- m05: EmOC women by district ------------------------------------------------------------------------
em = pd.read_csv(os.path.join(OUT, "access_emoc_districts.csv"))
fig, axes = plt.subplots(1, 2, figsize=(11, 5.6))
for ax, mode in zip(axes, ("motorised", "walking")):
    g = districts.merge(em[em["mode"] == mode], left_on="adm2_name", right_on="district", how="left")
    choropleth_panel(ax, g, "worst_month_share_over_2h", s_cmap, s_norm,
                     "By road" if mode == "motorised" else "On foot", edge=0.3)
C.key(fig, axes, s_cmap, s_norm, S, "women 15–49 more than 2 h away, worst month", S_LAB)
C.title(fig, "Women of reproductive age more than 2 hours from emergency obstetric care, by district",
        "Share in each district's worst month (HC IV or hospital).")
C.source(fig, SRC)
save(fig, os.path.join(FIG, "m05_emoc_women_districts.png"))

# --- m06: wealth vs penalty --------------------------------------------------------------------------------
rwi = pd.read_csv(os.path.join(DATA, "uga_relative_wealth_index.csv"))
lon, lat = np.meshgrid(grid.cols_lon, grid.rows_lat)
dd, j = cKDTree(np.c_[rwi.longitude, rwi.latitude]).query(np.c_[lon.ravel(), lat.ravel()])
cell_rwi = np.where(dd * 111 <= 3, rwi.rwi.values[j], np.nan).reshape(grid.shape)
R = [-1e9, -0.6, -0.4, -0.2, 0, 0.3, 0.8, 1e9]
R_LAB = ["poorest", "", "", "", "", "", "richest"]
r_cmap, r_norm = C.scale(R, C.DIVERGING)
E = [0, 2, 5, 10, 20, 30, 60, 1e9]
E_LAB = ["< 2 min", "2–5", "5–10", "10–20", "20–30", "30–60", "> 60 min"]
e_cmap, e_norm = C.scale(E, C.ORANGES)
fig, axes = plt.subplots(1, 2, figsize=(12, 5.8))
raster_panel(axes[0], np.where(pop > 0, cell_rwi, np.nan), r_cmap, r_norm, "Relative Wealth Index")
C.key(fig, axes[0], r_cmap, r_norm, R, "relative wealth (Meta)", R_LAB)
raster_panel(axes[1], np.where(pop > 0, (hosp[5] - hosp[0]) * 60, np.nan), e_cmap, e_norm,
             "Minutes the April rains add to the hospital trip")
C.key(fig, axes[1], e_cmap, e_norm, E, "extra minutes in April vs a dry day", E_LAB)
C.title(fig, "Where people are poorer, the April rains add more to the trip to hospital",
        "Populated 1 km cells only. Quintile breakdown: access_by_wealth.csv.")
C.source(fig, SRC)
save(fig, os.path.join(FIG, "m06_wealth_and_penalty.png"))

# --- m07: hospital catchments -------------------------------------------------------------------------------
ca = pd.read_csv(os.path.join(OUT, "hospital_catchments.csv"))
ca = ca[ca.extra_over_1h_april > 0]
fig, ax = plt.subplots(figsize=(8, 8))
C.frame(ax, EXT)
land_poly.plot(ax=ax, color=C.LAND, zorder=0)
districts.boundary.plot(ax=ax, color="white", linewidth=0.4, zorder=1)
size = lambda v: v / 300
ax.scatter(ca.lon, ca.lat, s=size(ca.extra_over_1h_april), color=C.BLUES[2], alpha=0.75,
           edgecolor="white", linewidth=0.6, zorder=3)
top = ca.head(10)
C.labels(ax, top.lon, top.lat, [h.replace(" Regional Referral Hospital", " RRH") for h in top.hospital])
handles = [plt.scatter([], [], s=size(v), color=C.BLUES[2], alpha=0.75, edgecolor="white")
           for v in (10000, 50000, 150000)]
C.outside_legend(ax, handles, ["10,000", "50,000", "150,000"],
                 "people pushed beyond 1 h\nin April (catchment)", labelspacing=2.2, borderpad=1.0)
C.furniture(ax)
C.title(fig, "Hospital catchments cut off most by the April rains",
        "Each circle is a hospital; its catchment is everyone for whom it is the nearest hospital on a dry day.")
C.source(fig, SRC)
save(fig, os.path.join(FIG, "m07_hospital_catchments.png"))

# --- m08: crossings ---------------------------------------------------------------------------------------------
cr = pd.read_csv(os.path.join(OUT, "crossings_priority.csv")).head(30)
fig, ax = plt.subplots(figsize=(8.5, 8.5))
raster_panel(ax, emoc[1], w_cmap, w_norm, "")
s = 30 + 400 * cr.person_hours_per_year / cr.person_hours_per_year.max()
ax.scatter(cr.lon, cr.lat, s=s, facecolor="none", edgecolor=C.ORANGES[3], linewidth=1.8, zorder=4)
top = cr.head(10)
C.labels(ax, top.lon, top.lat, [f"{int(r['rank'])}. {r.subcounty} ({r.district})" for _, r in top.iterrows()])
C.key(fig, ax, w_cmap, w_norm, W, "wet-day travel time to HC IV or hospital", W_LAB)
ax.legend([Line2D([], [], marker="o", ls="", mfc="none", mec=C.ORANGES[3], mew=1.8, ms=10)],
          ["priority crossing (size: person-hours saved a year)"], frameon=False, fontsize=7.5,
          loc="upper left", bbox_to_anchor=(0, -0.01))
C.title(fig, "The 30 river crossings where a bridge would most shorten wet-day trips to emergency obstetric care",
        "Crossings within 2 km of a higher-ranked one are merged.")
C.source(fig, SRC)
save(fig, os.path.join(FIG, "m08_crossings.png"))

# ===================== Sub-county maps ===========================================================================
Z = Zones(grid, subs)
P = Z.total(pop)
hosp_m = Z.monthly(hosp, lambda b: Z.share_beyond(b, 1, pop))
hosp_mean = Z.monthly(hosp, lambda b: Z.mean(b, pop))
sc = subs[["adm4_name", "adm2_name", "adm1_name", "geometry"]].copy()
sc["pop"] = P
sc["hosp_dry"] = Z.share_beyond(hosp[0], 1, pop)
sc["hosp_worst"] = np.nanmax(hosp_m, axis=0)
sc["hosp_increase"] = sc.hosp_worst - sc.hosp_dry
sc["worst_month"] = np.nanargmax(np.nan_to_num(hosp_mean, nan=-1), axis=0) + 1
sc["mean_increase_h"] = np.nanmax(hosp_mean, axis=0) - Z.mean(hosp[0], pop)
sc["pushed"] = sc["pop"] * sc.hosp_increase
any_m = Z.monthly(walk_any, lambda b: Z.share_beyond(b, 1, pop))
sc["walk_any_dry"] = Z.share_beyond(walk_any[0], 1, pop)
sc["walk_any_worst"] = np.nanmax(any_m, axis=0)
sc["walk_any_increase"] = sc.walk_any_worst - sc.walk_any_dry
em_m = Z.monthly(walk_emoc, lambda b: Z.share_beyond(b, 2, women))
sc["emoc_walk_dry"] = Z.share_beyond(walk_emoc[0], 2, women)
sc["emoc_walk_worst"] = np.nanmax(em_m, axis=0)
sc["school_apr"] = Z.share_beyond(read("", "secondary_school")[5], 1, pop)
sc["market_apr"] = Z.share_beyond(read("", "market")[5], 1, pop)
sc["rwi"] = Z.mean(np.where(np.isfinite(cell_rwi), cell_rwi, np.nan), pop)
sc.drop(columns="geometry").to_csv(os.path.join(OUT, "subcounty_map_data.csv"), index=False)

# s01
fig, axes = plt.subplots(1, 3, figsize=(16, 6))
choropleth_panel(axes[0], sc, "hosp_dry", s_cmap, s_norm, "Dry day")
choropleth_panel(axes[1], sc, "hosp_worst", s_cmap, s_norm, "Worst month")
choropleth_panel(axes[2], sc, "hosp_increase", i_cmap, i_norm, "Increase in the worst month")
C.key(fig, axes[:2].tolist(), s_cmap, s_norm, S, "share of people > 1 h from a hospital", S_LAB,
      orientation="horizontal")
C.key(fig, axes[2], i_cmap, i_norm, I, "increase (percentage points)", I_LAB, orientation="horizontal")
C.title(fig, "Sub-counties: share of people more than 1 hour from a hospital",
        "1,520 sub-counties; motorised; worst month = the month with the longest average trip.")
C.source(fig, SRC)
save(fig, os.path.join(FIG_SC, "s01_hospital_share.png"))

# s02 worst season
SEASONS = {"Mar–May (long rains)": (3, 4, 5), "Jun–Aug": (6, 7, 8),
           "Sep–Nov (short rains)": (9, 10, 11), "Dec–Feb": (12, 1, 2)}
SEASON_COL = {"Mar–May (long rains)": "#2a78d6", "Jun–Aug": "#1baf7a",
              "Sep–Nov (short rains)": "#eb6834", "Dec–Feb": "#4a3aa7",
              "Little seasonal change (< 3 min)": "#d8d4cb", "No road link (islands)": "#8f8c85"}
sc["season"] = [next(k for k, v in SEASONS.items() if m in v) for m in sc.worst_month]
sc.loc[sc.mean_increase_h * 60 < 3, "season"] = "Little seasonal change (< 3 min)"
sc.loc[~np.isfinite(sc.mean_increase_h), "season"] = "No road link (islands)"
fig, ax = plt.subplots(figsize=(8, 8))
C.frame(ax, EXT)
land_poly.plot(ax=ax, color=C.LAND, zorder=0)
sc.plot(ax=ax, color=sc.season.map(SEASON_COL), edgecolor="white", linewidth=0.08, zorder=1)
districts.boundary.plot(ax=ax, color=C.INK2, linewidth=0.15, zorder=2)
counts = sc.season.value_counts()
C.outside_legend(ax, [Patch(color=c) for c in SEASON_COL.values()],
                 [f"{k} ({counts.get(k, 0)})" for k in SEASON_COL], "worst season\n(number of sub-counties)")
C.furniture(ax)
C.title(fig, "When is the trip to hospital longest? Worst season by sub-county",
        "Season of the month with the longest average motorised trip to the nearest hospital.")
C.source(fig, SRC)
save(fig, os.path.join(FIG_SC, "s02_worst_season.png"))

# s03 people pushed
fig, ax = plt.subplots(figsize=(8, 8))
C.frame(ax, EXT)
land_poly.plot(ax=ax, color=C.LAND, zorder=0)
subs.boundary.plot(ax=ax, color="white", linewidth=0.1, zorder=1)
districts.boundary.plot(ax=ax, color=C.INK2, linewidth=0.15, zorder=2)
cen = sc.to_crs(32636).representative_point().to_crs(4326)
pz = sc.pushed.clip(lower=0).fillna(0)
ax.scatter(cen.x, cen.y, s=pz / 150, color=C.ORANGES[2], alpha=0.7, edgecolor="white", linewidth=0.4, zorder=3)
top = sc.assign(x=cen.x, y=cen.y).nlargest(12, "pushed")
C.labels(ax, top.x, top.y, [f"{r.adm4_name} ({r.adm2_name})" for _, r in top.iterrows()])
handles = [plt.scatter([], [], s=v / 150, color=C.ORANGES[2], alpha=0.7, edgecolor="white")
           for v in (2000, 10000, 40000)]
C.outside_legend(ax, handles, ["2,000", "10,000", "40,000"],
                 "people pushed beyond 1 h\nin the worst month", labelspacing=2.2, borderpad=1.0)
C.furniture(ax)
C.title(fig, "Sub-counties where the rains push most people beyond 1 hour from a hospital",
        f"{sc.pushed.clip(lower=0).sum() / 1e6:.1f} million people in total, each counted in their own sub-county's worst month.")
C.source(fig, SRC)
save(fig, os.path.join(FIG_SC, "s03_people_pushed_over_1h.png"))

# s04 walking any facility
fig, axes = plt.subplots(1, 3, figsize=(16, 6))
choropleth_panel(axes[0], sc, "walk_any_dry", s_cmap, s_norm, "Dry day")
choropleth_panel(axes[1], sc, "walk_any_worst", s_cmap, s_norm, "Worst month")
choropleth_panel(axes[2], sc, "walk_any_increase", i_cmap, i_norm, "Increase in the worst month")
C.key(fig, axes[:2].tolist(), s_cmap, s_norm, S, "share of people > 1 h on foot from any facility", S_LAB,
      orientation="horizontal")
C.key(fig, axes[2], i_cmap, i_norm, I, "increase (percentage points)", I_LAB, orientation="horizontal")
C.title(fig, "On foot: share of people more than 1 hour from any health facility",
        "Walking only; nearest facility of any level (the first point of care).")
C.source(fig, SRC)
save(fig, os.path.join(FIG_SC, "s04_walking_any_facility.png"))

# s05 EmOC women walking
fig, axes = plt.subplots(1, 2, figsize=(11.5, 6))
choropleth_panel(axes[0], sc, "emoc_walk_dry", s_cmap, s_norm, "Dry day")
choropleth_panel(axes[1], sc, "emoc_walk_worst", s_cmap, s_norm, "Worst month")
C.key(fig, axes, s_cmap, s_norm, S, "women 15–49 more than 2 h on foot from HC IV or hospital", S_LAB,
      orientation="horizontal")
C.title(fig, "On foot: women of reproductive age more than 2 hours from emergency obstetric care",
        "Sub-counties; HC IV or hospital; walking only.")
C.source(fig, SRC)
save(fig, os.path.join(FIG_SC, "s05_emoc_women_walking.png"))

# s06 school and market
fig, axes = plt.subplots(1, 2, figsize=(11.5, 6))
choropleth_panel(axes[0], sc, "school_apr", s_cmap, s_norm, "Secondary school, April")
choropleth_panel(axes[1], sc, "market_apr", s_cmap, s_norm, "Market, April")
C.key(fig, axes, s_cmap, s_norm, S, "share of people more than 1 h away by road", S_LAB, orientation="horizontal")
C.title(fig, "Beyond health: sub-counties more than 1 hour from a secondary school or a market in April",
        "Schools and markets from OpenStreetMap; completeness varies by area.")
C.source(fig, SRC)
save(fig, os.path.join(FIG_SC, "s06_school_market.png"))

# s07 wealth
fig, ax = plt.subplots(figsize=(8, 8))
choropleth_panel(ax, sc, "rwi", r_cmap, r_norm, "")
C.key(fig, ax, r_cmap, r_norm, R, "mean Relative Wealth Index (population-weighted)", R_LAB)
C.title(fig, "Relative wealth by sub-county", "Meta Relative Wealth Index, 2.4 km tiles averaged over each sub-county's population.")
C.source(fig, "Source: Meta Data for Good, Relative Wealth Index; WorldPop 2020.")
save(fig, os.path.join(FIG_SC, "s07_wealth.png"))

# s08 regional zooms
fig, axes = plt.subplots(2, 2, figsize=(13, 13))
for ax, region in zip(axes.flat, ["Northern", "Eastern", "Western", "Central"]):
    r = sc[sc.adm1_name.str.startswith(region)]
    x0, y0, x1, y1 = r.total_bounds
    pad = 0.05
    choropleth_panel(ax, sc, "hosp_increase", i_cmap, i_norm, f"{region} region",
                     extent=[x0 - pad, x1 + pad, y0 - pad, y1 + pad], km=None, edge=0.2)
    rc = r.to_crs(32636).representative_point().to_crs(4326)
    top = r.assign(x=rc.x, y=rc.y).nlargest(6, "pushed")
    C.labels(ax, top.x, top.y, [f"{t.adm4_name} ({t.adm2_name})" for _, t in top.iterrows()], fontsize=7)
C.key(fig, axes, i_cmap, i_norm, I, "increase in share > 1 h from a hospital, worst month (percentage points)",
      I_LAB, orientation="horizontal")
C.title(fig, "Regional zooms: where the rains lengthen the trip to hospital most",
        "Labels: the six sub-counties per region with most people pushed beyond 1 hour.")
C.source(fig, SRC)
save(fig, os.path.join(FIG_SC, "s08_regional_zooms.png"))

print("maps written to", os.path.abspath(FIG))
