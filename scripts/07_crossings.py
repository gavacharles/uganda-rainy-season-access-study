"""Which river crossings to bridge first.

A ford (OSM ford node, or a road way tagged ford) is near-impassable on a wet day in
the model. For each ford cell, "bridging" it gives the cell its wet-day road speed
without the ford penalty; the benefit is measured on a wet day, for motorised travel
to the nearest emergency obstetric care (HC IV or hospital):
  person_hours_per_wet_day   hours saved, summed over everyone
  people_within_1h           people brought from over 1 h to within 1 h
  women_within_2h            women 15-49 brought from over 2 h to within 2 h
  wet_days_per_year          wet days at the crossing (CHIRPS, 2006-2025)
  person_hours_per_year      person_hours_per_wet_day x wet_days_per_year

Screening: bridging all fords at once shows which cells gain; each ford is scored by
the population-weighted gain within SCREEN_KM of it, and the top N_EXACT are
recomputed one at a time.

Output: ../outputs/crossings_priority.csv (mapped by 09_maps.py)
"""
import os
import numpy as np
import pandas as pd
import geopandas as gpd
from scipy.spatial import cKDTree

import model
from facilities import load_destinations

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
OUT = os.path.join(HERE, "..", "outputs")
FIG = os.path.join(HERE, "..", "figures")
TARGET = "HC IV or hospital"
SCREEN_KM = 25
N_EXACT = 150
MERGE_KM = 2.0

grid = model.Grid()
pop = grid.pop
women = model.population_groups(grid)["women 15-49"]
roads = model.load_roads()
fords = model.ford_cells(grid, roads)
v_dry, v_wet = model.build_speeds(grid, roads, fords, "motorised")
_, v_wet_bridged = model.build_speeds(grid, roads, np.zeros_like(fords), "motorised")
target = grid.rasterize(load_destinations("official")[TARGET].geometry).astype(bool)
wet_days = model.wet_share(grid, model.EARLY_LATE["late"]).sum(axis=0) * 365.25 / 12

base = grid.travel_time(1.0 / v_wet, target)
all_bridged = grid.travel_time(1.0 / v_wet_bridged, target)
gain = np.nan_to_num(base - all_bridged) * pop          # person-hours per wet day

# --- Screening ------------------------------------------------------------------------
fr, fc = np.where(fords & grid.land)
lat, lon = grid.rows_lat[fr], grid.cols_lon[fc]
gr, gc = np.where(gain > 0)
tree = cKDTree(np.c_[grid.cols_lon[gc] * 111.0, grid.rows_lat[gr] * 111.0])
near = tree.query_ball_point(np.c_[lon * 111.0, lat * 111.0], SCREEN_KM)
score = np.array([gain[gr[i], gc[i]].sum() for i in near])
cand = np.argsort(score)[::-1][:N_EXACT]


def within(tt, h):
    return tt <= h


rows = []
for k, i in enumerate(cand):
    r, c = fr[i], fc[i]
    vw = v_wet.copy()
    vw[r, c] = v_wet_bridged[r, c]
    tt = grid.travel_time(1.0 / vw, target)
    saved = np.nan_to_num(base - tt)
    rows.append(dict(lon=lon[i], lat=lat[i], screen_score=score[i],
                     person_hours_per_wet_day=(saved * pop).sum(),
                     people_within_1h=pop[within(tt, 1) & ~within(base, 1)].sum(),
                     women_within_2h=women[within(tt, 2) & ~within(base, 2)].sum(),
                     wet_days_per_year=wet_days[r, c]))
    if k % 25 == 0:
        print(f"{k}/{len(cand)}", flush=True)
cr = pd.DataFrame(rows)
cr["person_hours_per_year"] = cr.person_hours_per_wet_day * cr.wet_days_per_year
cr = cr.sort_values("person_hours_per_year", ascending=False).reset_index(drop=True)
# Neighbouring ford cells are usually the same crossing: keep the best-ranked cell and
# drop any other within MERGE_KM of it.
keep, xy = [], np.c_[cr.lon * 111.0 * np.cos(np.radians(1.3)), cr.lat * 111.0]
for i in range(len(cr)):
    if all(np.hypot(*(xy[i] - xy[k])) > MERGE_KM for k in keep):
        keep.append(i)
cr = cr.iloc[keep].reset_index(drop=True)
cr.index += 1
pts = gpd.GeoDataFrame(cr, geometry=gpd.points_from_xy(cr.lon, cr.lat), crs=4326)
subs = gpd.read_file(os.path.join(DATA, "uga_subcounties.geojson"))
pts = gpd.sjoin(pts, subs[["adm4_name", "adm2_name", "geometry"]].to_crs(4326), how="left",
                predicate="within").rename(columns={"adm4_name": "subcounty", "adm2_name": "district"})
# Road class nearest the crossing point
road_near = gpd.sjoin_nearest(pts[["geometry"]].to_crs(32636),
                              roads[["highway", "geometry"]].to_crs(32636), max_distance=1500,
                              how="left")
pts["nearest_road_class"] = road_near.groupby(level=0).highway.first()
pts = pts.drop(columns=["index_right", "geometry"])
pts.to_csv(os.path.join(OUT, "crossings_priority.csv"), index_label="rank")

pd.set_option("display.width", 220)
print(f"ford cells: {len(fr)}; screened: {len(cand)}; distinct sites: {len(cr)}; "
      f"all fords bridged would save {gain.sum():,.0f} person-hours per wet day")
print(pts.head(15).round(1).to_string())
