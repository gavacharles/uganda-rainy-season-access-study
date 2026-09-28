"""Who loses access in the rains: women, the poor, refugee-hosting areas, and which
hospitals' catchments are cut off. Uses the official facility runs of 03
(motorised, and walking if it has been run).

Outputs (../outputs):
  access_emoc_districts.csv      women 15-49 more than 2 h from emergency obstetric care
                                 (HC IV or hospital), dry day vs worst month, per district
  access_by_wealth.csv           access by national quintile of Meta's Relative Wealth
                                 Index (population-weighted)
  access_refugee_subcounties.csv sub-counties with an OSM refugee site vs the rest
  hospital_catchments.csv        per hospital: catchment population, and people in it
                                 more than 1 h away on a dry day vs in April
Figure (../figures): fig6_wealth_gradient.png. Maps of these results: 09_maps.py.
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

import model
from facilities import load_health, load_places

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
OUT = os.path.join(HERE, "..", "outputs")
FIG = os.path.join(HERE, "..", "figures")
RUNS = {"motorised": OUT, "walking": os.path.join(OUT, "walking")}
RUNS = {k: v for k, v in RUNS.items() if os.path.exists(os.path.join(v, "travel_time_hospital.tif"))}
CATCHMENT_MONTH = 4       # April, the worst month nationally
# Headline destination per mode: on foot almost everyone is over 1 h from a hospital,
# so walking results use the nearest facility of any level (first point of care).
HEADLINE = {"motorised": ("hospital", "a hospital"), "walking": ("any_facility", "any health facility")}

grid = model.Grid()
groups = model.population_groups(grid)
pop, women = groups["everyone"], groups["women 15-49"]
districts = gpd.read_file(os.path.join(DATA, "uga_districts.geojson"))
subs = gpd.read_file(os.path.join(DATA, "uga_subcounties.geojson"))
dist_id, sub_id = grid.zones(districts), grid.zones(subs)


def read_tt(run, slug):
    with rasterio.open(os.path.join(RUNS[run], f"travel_time_{slug}.tif")) as src:
        a = src.read()
    return {"dry": a[0], "wet": a[1], **{m: a[m + 1] for m in range(1, 13)}}


def share_beyond(tt, w, sel, hours):
    P = w[sel].sum()
    return (w[sel] * ~(tt[sel] <= hours)).sum() / P if P > 0 else np.nan


# --- Emergency obstetric care: women 15-49 within 2 h of an HC IV or hospital --------
rows = []
for run in RUNS:
    tt = read_tt(run, "hc_iv_or_hospital")
    for i, r in districts.reset_index(drop=True).iterrows():
        sel = (dist_id == i + 1) & (women > 0)
        if not sel.any():
            continue
        by_month = {m: share_beyond(tt[m], women, sel, 2) for m in range(1, 13)}
        worst = max(by_month, key=by_month.get)
        rows.append(dict(mode=run, district=r.adm2_name, region=r.adm1_name,
                         women_15_49=women[sel].sum(),
                         dry_share_over_2h=share_beyond(tt["dry"], women, sel, 2),
                         worst_month=worst, worst_month_share_over_2h=by_month[worst],
                         wet_day_share_over_2h=share_beyond(tt["wet"], women, sel, 2)))
emoc = pd.DataFrame(rows)
emoc["extra_women_over_2h"] = emoc.women_15_49 * (emoc.worst_month_share_over_2h
                                                  - emoc.dry_share_over_2h)
emoc.sort_values(["mode", "worst_month_share_over_2h"], ascending=[True, False]).to_csv(
    os.path.join(OUT, "access_emoc_districts.csv"), index=False)

# --- Wealth: Meta Relative Wealth Index, nearest tile within 3 km -------------------
rwi = pd.read_csv(os.path.join(DATA, "uga_relative_wealth_index.csv"))
lon, lat = np.meshgrid(grid.cols_lon, grid.rows_lat)
coslat = np.cos(np.radians(1.3))
tree = cKDTree(np.c_[rwi.longitude * coslat, rwi.latitude])
d, j = tree.query(np.c_[lon.ravel() * coslat, lat.ravel()])
cell_rwi = np.where(d * 111 <= 3, rwi.rwi.values[j], np.nan).reshape(grid.shape)
has = np.isfinite(cell_rwi) & (pop > 0)
order = np.argsort(cell_rwi[has])
cum = np.cumsum(pop[has][order]) / pop[has].sum()
quint = np.full(grid.shape, 0)
q = np.empty(has.sum(), int)
q[order] = np.minimum((cum * 5).astype(int), 4) + 1
quint[has] = q
wealth_rows = []
for run in RUNS:
    for dest, hours in (("hospital", 1), ("any_facility", 1), ("hc_iv_or_hospital", 2),
                        ("market", 1), ("secondary_school", 1)):
        tt = read_tt(run, dest)
        for k in range(1, 6):
            sel = quint == k
            wealth_rows.append(dict(mode=run, destination=dest, threshold_h=hours, quintile=k,
                                    population=pop[sel].sum(),
                                    dry=share_beyond(tt["dry"], pop, sel, hours),
                                    april=share_beyond(tt[4], pop, sel, hours),
                                    august=share_beyond(tt[8], pop, sel, hours),
                                    wet_day=share_beyond(tt["wet"], pop, sel, hours)))
wealth = pd.DataFrame(wealth_rows)
wealth.to_csv(os.path.join(OUT, "access_by_wealth.csv"), index=False)
coverage = pop[has].sum() / pop.sum()

# --- Refugee-hosting sub-counties (OSM refugee sites; incomplete outside West Nile) ---
ref = load_places()
ref = ref[ref.kind == "refugee_site"]
host = gpd.sjoin(subs, ref[["geometry"]].to_crs(subs.crs), predicate="contains").index.unique()
is_host = np.isin(sub_id, np.asarray(host) + 1) & (pop > 0)
ref_rows = []
for run in RUNS:
    tt = read_tt(run, HEADLINE[run][0])
    for label, sel in (("with OSM refugee site", is_host), ("other", ~is_host & (pop > 0))):
        ref_rows.append(dict(mode=run, destination=HEADLINE[run][0], subcounties=label,
                             population=pop[sel].sum(),
                             **{f"{k}_share_over_1h": share_beyond(tt[k], pop, sel, 1)
                                for k in ("dry", 4, 8, "wet")}))
pd.DataFrame(ref_rows).to_csv(os.path.join(OUT, "access_refugee_subcounties.csv"), index=False)

# --- Hospital catchments: nearest hospital on a dry day vs in April -----------------
roads = model.load_roads()
fords = model.ford_cells(grid, roads)
v_dry, v_wet = model.build_speeds(grid, roads, fords, "motorised")
f_apr = model.wet_share(grid, model.EARLY_LATE["late"])[CATCHMENT_MONTH - 1]
hosp = load_health("official")
hosp = hosp[hosp.level == "hospital"].reset_index(drop=True)
hosp_cell = grid.rasterize([], dtype="int32")
rr, cc = rasterio.transform.rowcol(grid.transform, hosp.geometry.x, hosp.geometry.y)
hosp["cell"] = np.ravel_multi_index((np.clip(rr, 0, grid.shape[0] - 1),
                                     np.clip(cc, 0, grid.shape[1] - 1)), grid.shape)
cell_to_h = hosp.groupby("cell").name.first()
target = np.zeros(grid.shape, bool)
target.ravel()[hosp.cell.values] = True
cat = {}
for label, f in (("dry", None), ("april", f_apr)):
    tt, nearest = grid.travel_time(model.hours_per_km(v_dry, v_wet, f), target, sources=True)
    cat[label] = (tt, nearest)
tt_d, near_d = cat["dry"]
tt_a, _ = cat["april"]
ok = (near_d >= 0) & (pop > 0)
df = pd.DataFrame(dict(cell=near_d[ok], pop=pop[ok], over_dry=pop[ok] * ~(tt_d[ok] <= 1),
                       over_apr=pop[ok] * ~(tt_a[ok] <= 1)))
catch = df.groupby("cell").sum().drop(columns=[], errors="ignore")
catch["hospital"] = cell_to_h.reindex(catch.index).values
catch["extra_over_1h_april"] = catch.over_apr - catch.over_dry
pts = hosp.drop_duplicates("cell").set_index("cell").geometry
catch["lon"], catch["lat"] = pts.reindex(catch.index).x.values, pts.reindex(catch.index).y.values
catch = catch.rename(columns={"pop": "catchment_population",
                              "over_dry": "over_1h_dry", "over_apr": "over_1h_april"})
catch = catch.sort_values("extra_over_1h_april", ascending=False)
catch.to_csv(os.path.join(OUT, "hospital_catchments.csv"), index_label="cell")

# --- Figures --------------------------------------------------------------------------
INK, INK2, GRID_C, SURF = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
BLUE, ORANGE = "#2a78d6", "#eb6834"
plt.rcParams.update({"font.size": 9, "axes.edgecolor": GRID_C, "axes.labelcolor": INK2,
                     "xtick.color": INK2, "ytick.color": INK2, "axes.spines.top": False,
                     "axes.spines.right": False, "axes.grid": True, "grid.color": GRID_C,
                     "grid.linewidth": 0.6, "figure.facecolor": SURF,
                     "axes.facecolor": SURF, "savefig.facecolor": SURF})
BLUES = ["#cde2fb", "#86b6ef", "#3987e5", "#1c5cab", "#0d366b"]

# Fig 6: wealth gradient, > 1 h from the mode's headline destination, dry vs April
fig, axes = plt.subplots(1, len(RUNS), figsize=(5.2 * len(RUNS), 3.6), squeeze=False, sharey=False)
for ax, run in zip(axes[0], RUNS):
    w = wealth[(wealth["mode"] == run) & (wealth.destination == HEADLINE[run][0])]
    x = np.arange(1, 6)
    ax.bar(x - 0.18, 100 * w.dry, width=0.34, color="#86b6ef", label="dry day")
    ax.bar(x + 0.18, 100 * w.april, width=0.34, color=BLUE, label="April")
    ax.set_xticks(x, ["poorest", "2", "3", "4", "richest"])
    ax.set_ylabel("% of people more than 1 h away")
    ax.set_title(f"{run.capitalize()}: to {HEADLINE[run][1]}", fontsize=9.5, color=INK, loc="left")
    ax.grid(axis="x", visible=False)
axes[0][0].legend(frameon=False, fontsize=8)
fig.suptitle("Access by relative wealth quintile (population-weighted)",
             x=0.01, ha="left", color=INK, fontsize=11)
fig.text(0.01, -0.02, f"Meta Relative Wealth Index, nearest 2.4 km tile within 3 km; "
         f"covers {100 * coverage:.0f}% of the population.", fontsize=7.5, color=INK2)
fig.tight_layout()
fig.savefig(os.path.join(FIG, "fig6_wealth_gradient.png"), dpi=180, bbox_inches="tight")
plt.close(fig)

pd.set_option("display.width", 200, "display.max_rows", 100)
print("runs:", list(RUNS), f"| RWI covers {100 * coverage:.0f}% of population | "
      f"refugee-site sub-counties: {len(host)}")
print(emoc.groupby("mode")[["dry_share_over_2h", "worst_month_share_over_2h", "women_15_49"]].apply(lambda g: pd.Series(dict(
    dry=(g.dry_share_over_2h * g.women_15_49).sum() / g.women_15_49.sum(),
    worst=(g.worst_month_share_over_2h * g.women_15_49).sum() / g.women_15_49.sum()))).round(3))
print(wealth[wealth.destination.isin(["hospital", "any_facility"])].round(3).to_string(index=False))
print(pd.DataFrame(ref_rows).round(3).to_string(index=False))
print(catch.head(10)[["hospital", "catchment_population", "over_1h_dry", "over_1h_april",
                      "extra_over_1h_april"]].round(0).to_string())
