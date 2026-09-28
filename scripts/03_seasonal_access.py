"""Seasonal travel time to health facilities, schools, markets and towns, by month.

Model and assumptions: model.py. Destinations: facilities.py.

Usage: 03_seasonal_access.py [official|osm] [motorised|walking]
  (facility source and travel mode; default official motorised)

Outputs (../outputs, or a subfolder for non-default runs):
  access_national_monthly.csv   destination x scenario x period x population group
  access_districts.csv          hospital and HC IV-or-hospital access per district
  travel_time_<destination>.tif 14 bands: dry day, wet day, January-December
                                (2006-2025 rainfall)
Figures 2-3 (../figures); maps: 09_maps.py.
"""
import os
import numpy as np
import pandas as pd
import geopandas as gpd
import rasterio
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import model
from model import Grid, EARLY_LATE
from facilities import load_destinations, run_from_argv, output_dirs

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
SOURCE, MODE = run_from_argv()
OUT, FIG = output_dirs(os.path.join(HERE, ".."), SOURCE, MODE)
DISTRICT_TARGETS = ("hospital", "HC IV or hospital")

grid = Grid()
roads = model.load_roads()
fords = model.ford_cells(grid, roads)
v_dry, v_wet = model.build_speeds(grid, roads, fords, MODE)
f_share = {period: model.wet_share(grid, years) for period, years in EARLY_LATE.items()}
groups = model.population_groups(grid)
dest = load_destinations(SOURCE)
targets = {k: grid.rasterize(g.geometry).astype(bool) for k, g in dest.items()}

# --- Scenarios -----------------------------------------------------------------
results = {}
for tname, tmask in targets.items():
    results[(tname, "dry day", "")] = grid.travel_time(model.hours_per_km(v_dry, v_wet), tmask)
    results[(tname, "wet day", "")] = grid.travel_time(model.hours_per_km(v_dry, v_wet, 1.0), tmask)
    for period, fs in f_share.items():
        for m in range(12):
            results[(tname, m + 1, period)] = grid.travel_time(
                model.hours_per_km(v_dry, v_wet, fs[m]), tmask)

nat = pd.DataFrame([dict(target=k[0], scenario=k[1], period=k[2], group=gname,
                         **grid.pop_stats(v, w))
                    for k, v in results.items() for gname, w in groups.items()])
nat.to_csv(os.path.join(OUT, "access_national_monthly.csv"), index=False)

# --- Districts -------------------------------------------------------------------
# Population with no path to a facility (e.g. islands, as ferries are not modelled)
# counts as over 2 h and is excluded from mean hours.
dist = gpd.read_file(os.path.join(DATA, "uga_districts.geojson"))
dist_id = grid.zones(dist)
pop = grid.pop


def weighted_mean(tt, p):
    ok = np.isfinite(tt)
    return np.average(tt[ok], weights=p[ok]) if p[ok].sum() > 0 else np.nan


rows = []
for target in DISTRICT_TARGETS:
    tts = {m: results[(target, m, "late")] for m in range(1, 13)}
    dry_tt = results[(target, "dry day", "")]
    for i, name in enumerate(dist.adm2_name):
        sel = (dist_id == i + 1) & (pop > 0)
        if not sel.any():
            continue
        p = pop[sel]
        means = {m: weighted_mean(tts[m][sel], p) for m in tts}
        shares = {m: (p * ~(tts[m][sel] <= 2)).sum() / p.sum() for m in tts}
        best, worst = min(means, key=means.get), max(means, key=means.get)
        rows.append(dict(target=target, district=name, region=dist.adm1_name.iloc[i],
                         population=p.sum(),
                         unreachable_share=p[~np.isfinite(tts[1][sel])].sum() / p.sum(),
                         dry_day_mean_h=weighted_mean(dry_tt[sel], p),
                         best_month=best, worst_month=worst,
                         best_month_mean_h=means[best], worst_month_mean_h=means[worst],
                         seasonal_penalty_h=means[worst] - means[best],
                         best_month_share_over_2h=shares[best],
                         worst_month_share_over_2h=shares[worst]))
districts = (pd.DataFrame(rows)
             .sort_values(["target", "seasonal_penalty_h"], ascending=[True, False]))
districts.to_csv(os.path.join(OUT, "access_districts.csv"), index=False)

# --- Rasters ------------------------------------------------------------------------
TIF_BANDS = ["dry day", "wet day"] + list(range(1, 13))
profile = dict(driver="GTiff", height=grid.shape[0], width=grid.shape[1], count=len(TIF_BANDS),
               dtype="float32", crs=grid.crs, transform=grid.transform, nodata=np.nan,
               compress="deflate")
for tname in targets:
    slug = tname.lower().replace(" ", "_")
    with rasterio.open(os.path.join(OUT, f"travel_time_{slug}.tif"), "w", **profile) as dst:
        for b, sc in enumerate(TIF_BANDS, start=1):
            dst.write(results[(tname, sc, "" if isinstance(sc, str) else "late")]
                      .astype("float32"), b)
            dst.set_band_description(b, str(sc) if isinstance(sc, str) else f"month {sc}")

# --- Figures ----------------------------------------------------------------------
INK, INK2, GRID_C, SURF = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
BLUE, ORANGE = "#2a78d6", "#eb6834"
plt.rcParams.update({"font.size": 9, "axes.edgecolor": GRID_C, "axes.labelcolor": INK2,
                     "xtick.color": INK2, "ytick.color": INK2, "axes.spines.top": False,
                     "axes.spines.right": False, "axes.grid": True, "grid.color": GRID_C,
                     "grid.linewidth": 0.6, "figure.facecolor": SURF,
                     "axes.facecolor": SURF, "savefig.facecolor": SURF})
MONTHS = list("JFMAMJJASOND")
MODE_NOTE = "walking only" if MODE == "walking" else "motorised where there is a road"

# Maps are drawn by 09_maps.py.

# Fig 2: national share of population over 1 h from a hospital, by month, early vs late
fig, ax = plt.subplots(figsize=(7, 3.6))
m = nat[(nat.target == "hospital") & nat.period.isin(["early", "late"]) & (nat.group == "everyone")]
for (period, g), c in zip(m.groupby("period"), (BLUE, ORANGE)):
    years = EARLY_LATE[period]
    g = g.sort_values("scenario")
    ax.plot(g.scenario.astype(int), 100 * g.share_over_1h, color=c, lw=2, marker="o", ms=4,
            label=f"{years[0]}–{years[1]} rainfall")
dry = nat[(nat.target == "hospital") & (nat.scenario == "dry day")
          & (nat.group == "everyone")].share_over_1h.iloc[0]
ax.axhline(100 * dry, color=INK2, lw=0.8, ls="--")
ax.text(6.5, 100 * dry, "if every day were dry", ha="center", va="bottom", fontsize=8, color=INK2)
ax.set_xticks(range(1, 13), MONTHS)
ax.set_ylabel("% of population > 1 h from a hospital")
ax.legend(frameon=False, fontsize=8, loc="upper right")
ax.set_title(f"Share of Ugandans more than 1 hour from a hospital, by month\n{MODE_NOTE.capitalize()}",
             fontsize=10.5, color=INK, loc="left")
fig.tight_layout()
fig.savefig(os.path.join(FIG, "fig2_monthly_share_over_1h.png"), dpi=180)
plt.close(fig)

# Fig 3: districts with the largest seasonal penalty
top = districts[districts.target == "hospital"].head(15).iloc[::-1]
fig, ax = plt.subplots(figsize=(7, 4.6))
ax.barh(top.district, top.best_month_mean_h, color="#b7d3f6", height=0.6, label="best month")
ax.barh(top.district, top.seasonal_penalty_h, left=top.best_month_mean_h, color=BLUE,
        height=0.6, label="extra in worst month")
ax.set_xlabel("mean hours to nearest hospital (population-weighted)")
ax.grid(axis="y", visible=False)
ax.legend(frameon=False, fontsize=8, loc="lower right")
ax.set_title("Districts where the rains add most to hospital travel time",
             fontsize=10.5, color=INK, loc="left")
fig.tight_layout()
fig.savefig(os.path.join(FIG, "fig3_district_seasonal_penalty.png"), dpi=180)
plt.close(fig)

pd.set_option("display.width", 200, "display.max_rows", 200)
print(f"run: {SOURCE} facilities, {MODE}; ford cells: {int(fords.sum())}")
print("destinations:", {k: len(g) for k, g in dest.items()})
summary = nat[(nat.period != "early")]
summary = summary[summary.scenario.isin(["dry day", "wet day", 4, 8])]
print(summary.round(3).to_string(index=False))
