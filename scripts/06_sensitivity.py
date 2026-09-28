"""Sensitivity of the hospital-access results to the model's assumptions.

Each variant changes one assumption from model.PARAMS (or the facility source) and
recomputes motorised travel time to the nearest hospital for a dry day and every month
of 2006-2025 rainfall. Reported per variant:
  dry_over_1h, april_over_1h   national share of people more than 1 h away
  april_minus_dry_pp           the seasonal increase, percentage points
  district_rank_corr           Spearman correlation of district seasonal penalties
                               (worst month minus best month, mean hours) with baseline
  top15_overlap                districts shared with the baseline's top 15

Outputs: ../outputs/sensitivity.csv, ../figures/fig8_sensitivity.png
"""
import os
import numpy as np
import pandas as pd
import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import model
from model import params
from facilities import load_destinations

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
OUT = os.path.join(HERE, "..", "outputs")
FIG = os.path.join(HERE, "..", "figures")

VARIANTS = [
    ("Baseline", {}, "official"),
    ("Earth roads keep 25% when wet", dict(wet_factor={"earth": 0.25}), "official"),
    ("Earth roads keep 60% when wet", dict(wet_factor={"earth": 0.6}), "official"),
    ("Gravel roads keep 50% when wet", dict(wet_factor={"gravel": 0.5}), "official"),
    ("Gravel roads keep 90% when wet", dict(wet_factor={"gravel": 0.9}), "official"),
    ("Fords 0.2 km/h when wet", dict(ford_wet_kmh=0.2), "official"),
    ("Fords 2 km/h when wet", dict(ford_wet_kmh=2.0), "official"),
    ("Ford blocks its whole 1 km cell", dict(ford_blocks_cell=True), "official"),
    ("Untagged secondary/tertiary = earth",
     dict(default_surface={"secondary": "earth", "tertiary": "earth"}), "official"),
    ("Road speeds ×0.75", dict(speed_scale=0.75), "official"),
    ("Road speeds ×1.25", dict(speed_scale=1.25), "official"),
    ("Walking 4 km/h", dict(walk_kmh=4.0), "official"),
    ("Off-road keeps 40% when wet", dict(offroad_wet_factor=0.4), "official"),
    ("Wet day = rain ≥5 mm", dict(wet_mm=5.0, drying_mm=12.5), "official"),
    ("Wet day = rain ≥20 mm", dict(wet_mm=20.0, drying_mm=50.0), "official"),
    ("OSM facilities", {}, "osm"),
]

grid = model.Grid()
roads = model.load_roads()
fords = model.ford_cells(grid, roads)
pop = grid.pop
districts = gpd.read_file(os.path.join(DATA, "uga_districts.geojson"))
dist_id = grid.zones(districts)
targets = {src: grid.rasterize(load_destinations(src)["hospital"].geometry).astype(bool)
           for src in ("official", "osm")}
share_cache = {}


def district_penalty(tts):
    out = {}
    for i, name in enumerate(districts.adm2_name):
        sel = (dist_id == i + 1) & (pop > 0)
        if not sel.any():
            continue
        p = pop[sel]
        means = []
        for tt in tts:
            ok = np.isfinite(tt[sel])
            means.append(np.average(tt[sel][ok], weights=p[ok]) if p[ok].sum() > 0 else np.nan)
        out[name] = np.nanmax(means) - np.nanmin(means)
    return pd.Series(out)


rows, penalties = [], {}
for name, overrides, source in VARIANTS:
    p = params(**overrides)
    v_dry, v_wet = model.build_speeds(grid, roads, fords, "motorised", p)
    key = (p["wet_mm"], p["drying_mm"])
    if key not in share_cache:
        share_cache[key] = model.wet_share(grid, model.EARLY_LATE["late"], p)
    fs = share_cache[key]
    t = targets[source]
    dry = grid.travel_time(model.hours_per_km(v_dry, v_wet), t)
    months = [grid.travel_time(model.hours_per_km(v_dry, v_wet, fs[m]), t) for m in range(12)]
    penalties[name] = district_penalty(months)
    rows.append(dict(variant=name, dry_over_1h=grid.pop_stats(dry)["share_over_1h"],
                     april_over_1h=grid.pop_stats(months[3])["share_over_1h"]))
    print(name, "done", flush=True)

sens = pd.DataFrame(rows)
sens["april_minus_dry_pp"] = 100 * (sens.april_over_1h - sens.dry_over_1h)
base = penalties["Baseline"]
top_base = set(base.nlargest(15).index)
sens["district_rank_corr"] = [base.corr(penalties[v], method="spearman") for v in sens.variant]
sens["top15_overlap"] = [len(top_base & set(penalties[v].nlargest(15).index)) for v in sens.variant]
sens.to_csv(os.path.join(OUT, "sensitivity.csv"), index=False)

# --- Figure -------------------------------------------------------------------------
INK, INK2, GRID_C, SURF = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
BLUE, MUTED = "#2a78d6", "#b8b7b2"
plt.rcParams.update({"font.size": 9, "axes.edgecolor": GRID_C, "axes.labelcolor": INK2,
                     "xtick.color": INK2, "ytick.color": INK2, "axes.spines.top": False,
                     "axes.spines.right": False, "axes.grid": True, "grid.color": GRID_C,
                     "grid.linewidth": 0.6, "figure.facecolor": SURF,
                     "axes.facecolor": SURF, "savefig.facecolor": SURF})
fig, axes = plt.subplots(1, 3, figsize=(12, 4.6), sharey=True)
y = np.arange(len(sens))[::-1]
cols = [BLUE if v == "Baseline" else MUTED for v in sens.variant]
for ax, (col, title, fmt) in zip(axes, (
        ("dry_over_1h", "Over 1 h from a hospital: dry day vs April", None),
        ("april_minus_dry_pp", "Seasonal increase (percentage points)", "{:.1f}"),
        ("district_rank_corr", "District ranking vs baseline (Spearman)", "{:.2f}"))):
    if col == "dry_over_1h":
        for yi, (_, r) in zip(y, sens.iterrows()):
            ax.plot([100 * r.dry_over_1h, 100 * r.april_over_1h], [yi, yi], color=GRID_C, lw=2, zorder=1)
        ax.scatter(100 * sens.dry_over_1h, y, s=28, color="#86b6ef", zorder=2, label="dry day")
        ax.scatter(100 * sens.april_over_1h, y, s=28, color=BLUE, zorder=3, label="April")
        ax.set_xlabel("% of population")
        ax.legend(frameon=False, fontsize=8, loc="lower right")
    else:
        ax.barh(y, sens[col], color=cols, height=0.6)
        for yi, v in zip(y, sens[col]):
            ax.text(v, yi, " " + fmt.format(v), va="center", fontsize=7.5, color=INK2)
    ax.set_title(title, fontsize=9.5, color=INK, loc="left")
    ax.grid(axis="y", visible=False)
axes[0].set_yticks(y, sens.variant)
fig.suptitle("How much do the hospital-access results depend on the assumptions?",
             x=0.01, ha="left", color=INK, fontsize=11)
fig.tight_layout()
fig.savefig(os.path.join(FIG, "fig8_sensitivity.png"), dpi=180)
plt.close(fig)

pd.set_option("display.width", 200)
print(sens.round(3).to_string(index=False))
