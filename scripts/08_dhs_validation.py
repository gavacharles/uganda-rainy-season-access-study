"""Does modelled access line up with health outcomes? Uganda DHS 2016, by region.

Region-level indicators come from the DHS Program API (15 regions); regional
boundaries from the same API. For each region the script computes modelled access
(women 15-49 more than 2 h from emergency obstetric care, motorised and walking; all
people more than 1 h from a hospital) on a dry day and in April, plus mean Relative
Wealth Index, and reports Spearman correlations with the outcomes, raw and after
removing the (rank-linear) effect of wealth.

With 15 regions this is a consistency check, not causal evidence. The seasonal test
(do facility births dip in the months access worsens?) needs DHS birth-level
microdata, which require free registration at dhsprogram.com.

Outputs: ../outputs/dhs_regions.csv, ../outputs/dhs_correlations.csv,
../figures/fig10_dhs_validation.png. API responses are cached in ../data/dhs/.
"""
import os, json, urllib.request
import numpy as np
import pandas as pd
import geopandas as gpd
import rasterio
from shapely import wkt
from scipy import stats
from scipy.spatial import cKDTree
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import model

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
OUT = os.path.join(HERE, "..", "outputs")
FIG = os.path.join(HERE, "..", "figures")
CACHE = os.path.join(DATA, "dhs")
os.makedirs(CACHE, exist_ok=True)
API = "https://api.dhsprogram.com/rest/dhs"
SURVEY = "UG2016DHS"
# Region ids that exist only in the older 10-region scheme (East Central, Eastern,
# Northern, Western, South West).
OLD_10_ONLY = {"UGDHS2016452006", "UGDHS2016452007", "UGDHS2016452010",
               "UGDHS2016452014", "UGDHS2016452015"}
INDICATORS = {
    "RH_DELP_C_DHF": "Births in a health facility (%)",
    "RH_DELA_C_SKP": "Births assisted by a skilled provider (%)",
    "CH_VACC_C_BAS": "Children with all basic vaccinations (%)",
    "RH_PAHC_W_DIS": "Women citing distance as a problem accessing care (%)",
}


def get(name, url):
    path = os.path.join(CACHE, f"{name}.json")
    if not os.path.exists(path):
        with urllib.request.urlopen(url, timeout=120) as r, open(path, "wb") as f:
            f.write(r.read())
    return json.load(open(path))


# --- Outcomes --------------------------------------------------------------------------
rows = []
for ind in INDICATORS:
    d = get(ind, f"{API}/data?surveyIds={SURVEY}&indicatorIds={ind}&breakdown=subnational"
                 f"&f=json&perpage=1000&returnFields=RegionId,CharacteristicLabel,Value,IsPreferred")["Data"]
    for x in d:
        rows.append(dict(indicator=ind, region_id=x["RegionId"],
                         region=x["CharacteristicLabel"].lstrip(".").split("/")[0], value=x["Value"],
                         preferred=x["IsPreferred"]))
out = pd.DataFrame(rows)
missing = sorted(set(INDICATORS) - set(out.indicator))
out = (out.sort_values("preferred", ascending=False)
       .drop_duplicates(["indicator", "region_id"])
       .pivot(index=["region_id", "region"], columns="indicator", values="value").reset_index())

# --- Regions -----------------------------------------------------------------------------
g = get("geometry", f"{API}/geometry?surveyIds={SURVEY}&f=json&perpage=100"
                     f"&returnFields=RegionID,Coordinates")["Data"]
geo = gpd.GeoDataFrame([dict(region_id=x["RegionID"], geometry=wkt.loads(x["Coordinates"]))
                        for x in g if x["RegionID"] in set(out.region_id)], crs=4326)
# The API mixes the older 10-region scheme with the 15 regions used in 2016; keep the
# 15 (Karamoja appears in both, with a larger 10-region polygon: keep the smaller).
# Draw large regions first so Kampala is not overwritten by the Buganda polygons.
geo = geo[~geo.region_id.isin(OLD_10_ONLY)]
geo = geo.assign(area=geo.to_crs(32636).area).sort_values("area")
geo = geo.drop_duplicates("region_id").sort_values("area", ascending=False).drop(columns="area")
regions = geo.merge(out, on="region_id").reset_index(drop=True)

# --- Modelled access per region ------------------------------------------------------------
grid = model.Grid()
groups = model.population_groups(grid)
pop, women = groups["everyone"], groups["women 15-49"]
reg_id = grid.zones(regions)


def tt(run_dir, slug):
    with rasterio.open(os.path.join(OUT, run_dir, f"travel_time_{slug}.tif")) as src:
        a = src.read()
    return {"dry": a[0], "april": a[5]}


surf = {"motorised": {"hosp": tt("", "hospital"), "emoc": tt("", "hc_iv_or_hospital")}}
if os.path.exists(os.path.join(OUT, "walking", "travel_time_hc_iv_or_hospital.tif")):
    surf["walking"] = {"emoc": tt("walking", "hc_iv_or_hospital")}
rwi = pd.read_csv(os.path.join(DATA, "uga_relative_wealth_index.csv"))
lon, lat = np.meshgrid(grid.cols_lon, grid.rows_lat)
dd, j = cKDTree(np.c_[rwi.longitude, rwi.latitude]).query(np.c_[lon.ravel(), lat.ravel()])
cell_rwi = np.where(dd * 111 <= 3, rwi.rwi.values[j], np.nan).reshape(grid.shape)


def beyond(t, w, sel, h):
    return (w[sel] * ~(t[sel] <= h)).sum() / w[sel].sum()


for i in range(len(regions)):
    sel = (reg_id == i + 1) & (pop > 0)
    for when in ("dry", "april"):
        regions.loc[regions.index[i], f"emoc_women_2h_motorised_{when}"] = beyond(
            surf["motorised"]["emoc"][when], women, sel, 2)
        regions.loc[regions.index[i], f"hospital_1h_motorised_{when}"] = beyond(
            surf["motorised"]["hosp"][when], pop, sel, 1)
        if "walking" in surf:
            regions.loc[regions.index[i], f"emoc_women_2h_walking_{when}"] = beyond(
                surf["walking"]["emoc"][when], women, sel, 2)
    ok = sel & np.isfinite(cell_rwi)
    regions.loc[regions.index[i], "mean_rwi"] = np.average(cell_rwi[ok], weights=pop[ok])
regions.drop(columns="geometry").to_csv(os.path.join(OUT, "dhs_regions.csv"), index=False)

# --- Correlations -----------------------------------------------------------------------------
access_cols = [c for c in regions.columns if c.startswith(("emoc_", "hospital_"))]
outcome_cols = [c for c in INDICATORS if c in regions.columns]


def resid_rank(y, x):
    ry, rx = stats.rankdata(y), stats.rankdata(x)
    b = np.polyfit(rx, ry, 1)
    return ry - np.polyval(b, rx)


corr = []
for a in access_cols:
    for o in outcome_cols:
        d = regions[[a, o, "mean_rwi"]].dropna()
        rho, p = stats.spearmanr(d[a], d[o])
        prho, pp = stats.pearsonr(resid_rank(d[a], d.mean_rwi), resid_rank(d[o], d.mean_rwi))
        corr.append(dict(access=a, outcome=o, n=len(d), spearman=rho, p=p,
                         partial_given_wealth=prho, p_partial=pp))
corr = pd.DataFrame(corr)
corr.to_csv(os.path.join(OUT, "dhs_correlations.csv"), index=False)

# --- Figure ------------------------------------------------------------------------------------
INK, INK2, GRID_C, SURF = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
BLUE = "#2a78d6"
plt.rcParams.update({"font.size": 9, "axes.edgecolor": GRID_C, "axes.labelcolor": INK2,
                     "xtick.color": INK2, "ytick.color": INK2, "axes.spines.top": False,
                     "axes.spines.right": False, "axes.grid": True, "grid.color": GRID_C,
                     "grid.linewidth": 0.6, "figure.facecolor": SURF,
                     "axes.facecolor": SURF, "savefig.facecolor": SURF})
xcol = "emoc_women_2h_walking_april" if "walking" in surf else "emoc_women_2h_motorised_april"
panels = [o for o in ("RH_DELP_C_DHF", "RH_PAHC_W_DIS") if o in regions.columns]
fig, axes = plt.subplots(1, len(panels), figsize=(5.5 * len(panels), 4.2), squeeze=False)
for ax, o in zip(axes[0], panels):
    ax.scatter(100 * regions[xcol], regions[o], s=40, color=BLUE, edgecolor="white", zorder=3)
    for _, r in regions.iterrows():
        ax.annotate(r.region, (100 * r[xcol], r[o]), xytext=(4, 2), textcoords="offset points",
                    fontsize=6.8, color=INK2)
    c = corr[(corr.access == xcol) & (corr.outcome == o)].iloc[0]
    ax.set_title(f"{INDICATORS[o]}\nSpearman ρ = {c.spearman:.2f} (p = {c.p:.3f}); "
                 f"given wealth {c.partial_given_wealth:.2f}", fontsize=9, color=INK, loc="left")
    ax.set_xlabel("% of women 15–49 > 2 h on foot from HC IV/hospital, April"
                  if "walking" in xcol else "% of women 15–49 > 2 h from HC IV/hospital, April")
fig.suptitle("Modelled access vs DHS 2016 outcomes, by region (n = 15)",
             x=0.01, ha="left", color=INK, fontsize=11)
fig.tight_layout()
fig.savefig(os.path.join(FIG, "fig10_dhs_validation.png"), dpi=180)
plt.close(fig)

pd.set_option("display.width", 220, "display.max_rows", 100)
if missing:
    print("indicators not returned by the API:", missing)
print(regions.drop(columns="geometry").round(3).to_string(index=False))
print(corr.round(3).to_string(index=False))
