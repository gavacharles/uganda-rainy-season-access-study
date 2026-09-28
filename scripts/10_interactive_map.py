"""Build the interactive map (../web/rainy_season_access.html) from the outputs of 03-09.

Self-contained Leaflet page: travel-time surfaces as image overlays (including one per
month, animated by a slider), sub-counties as clickable polygons with their
statistics, and hospitals, HC IVs, priority crossings and hospital catchments as
toggleable points. No external map tiles; only the Leaflet script loads from cdnjs.
Template: interactive_map_template.html.
"""
import os, io, json, base64
import numpy as np
import pandas as pd
import geopandas as gpd
import rasterio
from scipy.spatial import cKDTree
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, BoundaryNorm, to_hex

import model
import cartography as C
from facilities import load_destinations
from zonal import Zones

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
DATA, OUT, WEB = (os.path.join(ROOT, d) for d in ("data", "outputs", "web"))

grid = model.Grid()
groups = model.population_groups(grid)
pop, women = groups["everyone"], groups["women 15-49"]
t = grid.transform
south, north = float(t.f + t.e * grid.shape[0]), float(t.f)
west, east = float(t.c), float(t.c + t.a * grid.shape[1])


def read(run, slug):
    with rasterio.open(os.path.join(OUT, run, f"travel_time_{slug}.tif")) as src:
        return src.read()


def classes(bounds, colors):
    cmap = LinearSegmentedColormap.from_list("c", colors, N=len(bounds) - 1)
    return cmap, BoundaryNorm(bounds, cmap.N), [to_hex(cmap(i)) for i in range(cmap.N)]


def png(arr, bounds, colors):
    cmap, norm, _ = classes(bounds, colors)
    rgba = cmap(norm(np.nan_to_num(arr, nan=bounds[0])))
    rgba[..., 3] = np.where(np.isfinite(arr) & grid.land, 1.0, 0.0)
    buf = io.BytesIO()
    plt.imsave(buf, rgba, format="png")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


H = [0, 0.25, 0.5, 1, 1.5, 2, 3, 1e9]
H_LAB = ["< 15 min", "15–30 min", "30–60 min", "1–1.5 h", "1.5–2 h", "2–3 h", "> 3 h"]
W = [0, 0.5, 1, 2, 3, 4, 6, 1e9]
W_LAB = ["< 30 min", "30–60 min", "1–2 h", "2–3 h", "3–4 h", "4–6 h", "> 6 h"]
E = [0, 2, 5, 10, 20, 30, 60, 1e9]
E_LAB = ["< 2 min", "2–5 min", "5–10 min", "10–20 min", "20–30 min", "30–60 min", "> 60 min"]
R = [-1e9, -0.6, -0.4, -0.2, 0, 0.3, 0.8, 1e9]
R_LAB = ["poorest", "", "", "", "", "", "richest"]
S = [0, 0.05, 0.1, 0.25, 0.5, 0.75, 0.9, 1.0001]
S_LAB = ["< 5%", "5–10%", "10–25%", "25–50%", "50–75%", "75–90%", "> 90%"]
I = [-1, 0.02, 0.05, 0.1, 0.2, 0.3, 0.5, 1.0001]
I_LAB = ["< 2 pts", "2–5 pts", "5–10 pts", "10–20 pts", "20–30 pts", "30–50 pts", "> 50 pts"]
SW = {k: classes(b, c)[2] for k, b, c in (("H", H, C.BLUES), ("W", W, C.BLUES), ("E", E, C.ORANGES),
                                          ("R", R, C.DIVERGING), ("S", S, C.BLUES), ("I", I, C.ORANGES))}

hosp = read("", "hospital")
walk_emoc, walk_any = read("walking", "hc_iv_or_hospital"), read("walking", "any_facility")
rwi = pd.read_csv(os.path.join(DATA, "uga_relative_wealth_index.csv"))
lon, lat = np.meshgrid(grid.cols_lon, grid.rows_lat)
dd, j = cKDTree(np.c_[rwi.longitude, rwi.latitude]).query(np.c_[lon.ravel(), lat.ravel()])
cell_rwi = np.where(dd * 111 <= 3, rwi.rwi.values[j], np.nan).reshape(grid.shape)

# --- Surfaces (1 km rasters) -----------------------------------------------------------------
monthly_png = [png(hosp[m + 1], H, C.BLUES) for m in range(1, 13)]
surfaces = {
    "hosp_dry": png(hosp[0], H, C.BLUES), "hosp_wet": png(hosp[1], H, C.BLUES),
    "hosp_extra": png(np.where(pop > 0, (hosp[5] - hosp[0]) * 60, np.nan), E, C.ORANGES),
    "emoc_walk": png(walk_emoc[5], W, C.BLUES), "any_walk": png(walk_any[5], W, C.BLUES),
    "sec_apr": png(read("", "secondary_school")[5], H, C.BLUES),
    "mkt_apr": png(read("", "market")[5], H, C.BLUES),
    "rwi": png(np.where(pop > 0, cell_rwi, np.nan), R, C.DIVERGING),
}
land_png = png(np.where(grid.land, 0.0, np.nan), [0, 1, 2], ["#ffffff", "#ffffff"])

# --- Sub-counties --------------------------------------------------------------------------------
subs = gpd.read_file(os.path.join(DATA, "uga_subcounties.geojson")).to_crs(4326)
Z = Zones(grid, subs)
monthly_share = Z.monthly(hosp, lambda b: Z.share_beyond(b, 1, pop))            # (12, n)
md = pd.read_csv(os.path.join(OUT, "subcounty_map_data.csv"))
md["hosp_wet"] = Z.share_beyond(hosp[1], 1, pop)
md["emoc_car_dry"] = Z.share_beyond(read("", "hc_iv_or_hospital")[0], 2, women)
SEASON = {3: "Mar–May", 4: "Mar–May", 5: "Mar–May", 6: "Jun–Aug", 7: "Jun–Aug", 8: "Jun–Aug",
          9: "Sep–Nov", 10: "Sep–Nov", 11: "Sep–Nov", 12: "Dec–Feb", 1: "Dec–Feb", 2: "Dec–Feb"}
md["season"] = md.worst_month.map(SEASON)
md.loc[md.mean_increase_h * 60 < 3, "season"] = "Little change"
md.loc[~np.isfinite(md.mean_increase_h), "season"] = "No road link"

land = C.land_polygon(grid)
shapes = C.clip_to_land(subs, land)
shapes["geometry"] = shapes.geometry.simplify(0.003, preserve_topology=True)
r4 = lambda v: None if v is None or not np.isfinite(v) else round(float(v), 3)
feats = []
for i, (_, r) in enumerate(shapes.iterrows()):
    if r.geometry is None or r.geometry.is_empty:
        continue
    d = md.iloc[i]
    props = dict(n=d.adm4_name, d=d.adm2_name, p=int(round(d["pop"])), wm=int(d.worst_month),
                 s=d.season, m=[r4(v) for v in monthly_share[:, i]],
                 **{k: r4(d[k]) for k in ("hosp_dry", "hosp_worst", "hosp_wet", "hosp_increase",
                                          "walk_any_dry", "walk_any_worst", "walk_any_increase",
                                          "emoc_walk_dry", "emoc_walk_worst", "emoc_car_dry",
                                          "school_apr", "market_apr", "rwi")})
    props["pushed"] = int(max(0, round(d.pushed))) if np.isfinite(d.pushed) else 0
    feats.append(dict(type="Feature", properties=props,
                      geometry=json.loads(gpd.GeoSeries([r.geometry]).to_json())["features"][0]["geometry"]))


def round_coords(o):
    if isinstance(o, list):
        return [round_coords(x) for x in o] if o and isinstance(o[0], list) else [round(v, 4) for v in o]
    return o


for f in feats:
    f["geometry"]["coordinates"] = round_coords(f["geometry"]["coordinates"])
dist = C.clip_to_land(gpd.read_file(os.path.join(DATA, "uga_districts.geojson")), land)
dist["geometry"] = dist.geometry.simplify(0.005, preserve_topology=True).boundary
dist_geo = json.loads(dist[["adm2_name", "geometry"]].to_json())
for f in dist_geo["features"]:
    f["geometry"]["coordinates"] = round_coords(f["geometry"]["coordinates"])
    f["properties"] = {}

# --- Points ----------------------------------------------------------------------------------------
dest = load_destinations("official")
pts = lambda g: [[round(p.y, 4), round(p.x, 4), nm] for p, nm in zip(g.geometry, g.name)]
hc = dest["HC IV or hospital"]
cr = pd.read_csv(os.path.join(OUT, "crossings_priority.csv")).head(30)
ca = pd.read_csv(os.path.join(OUT, "hospital_catchments.csv"))
ca = ca[ca.extra_over_1h_april > 0].head(40)

# --- National figures ----------------------------------------------------------------------------------
def nat(path, target, scen, group, col):
    n = pd.read_csv(path)
    n = n[(n.target == target) & (n.scenario.astype(str) == scen) & (n.group == group)
          & (n.period.fillna("").isin(["", "late"]))]
    return float(n[col].iloc[0])


NM = os.path.join(OUT, "access_national_monthly.csv")
NW = os.path.join(OUT, "walking", "access_national_monthly.csv")
monthly_nat = [nat(NM, "hospital", str(m), "everyone", "share_over_1h") for m in range(1, 13)]
headline = dict(hosp_dry=nat(NM, "hospital", "dry day", "everyone", "share_over_1h"),
                hosp_apr=nat(NM, "hospital", "4", "everyone", "share_over_1h"),
                hosp_wet=nat(NM, "hospital", "wet day", "everyone", "share_over_1h"),
                emoc_walk_dry=nat(NW, "HC IV or hospital", "dry day", "women 15-49", "share_over_2h"),
                emoc_walk_apr=nat(NW, "HC IV or hospital", "4", "women 15-49", "share_over_2h"),
                any_walk_dry=nat(NW, "any facility", "dry day", "everyone", "share_over_1h"),
                any_walk_apr=nat(NW, "any facility", "4", "everyone", "share_over_1h"),
                monthly=monthly_nat, pop=float(pop.sum()))

payload = dict(
    bounds=[[south, west], [north, east]], land=land_png, monthly=monthly_png, surfaces=surfaces,
    swatches=SW, labels=dict(H=H_LAB, W=W_LAB, E=E_LAB, R=R_LAB, S=S_LAB, I=I_LAB),
    bins=dict(S=S[:-1], I=I[:-1]), subs=dict(type="FeatureCollection", features=feats),
    districts=dist_geo, hospitals=pts(dest["hospital"]), hc4=pts(hc[hc.level == "hc4"]),
    crossings=[dict(rank=int(r["rank"]), lat=round(r.lat, 4), lon=round(r.lon, 4),
                    sub=str(r.subcounty), dist=str(r.district), road=str(r.nearest_road_class),
                    hours=int(r.person_hours_per_year), within1=int(r.people_within_1h),
                    women2=int(r.women_within_2h), wet=round(float(r.wet_days_per_year)))
               for _, r in cr.iterrows()],
    catchments=[dict(name=r.hospital, lat=round(r.lat, 4), lon=round(r.lon, 4),
                     pop=int(r.catchment_population), dry=int(r.over_1h_dry),
                     apr=int(r.over_1h_april), extra=int(r.extra_over_1h_april))
                for _, r in ca.iterrows()],
    headline=headline)
leaflet_css = open(os.path.join(WEB, "leaflet.css")).read()
template = open(os.path.join(HERE, "interactive_map_template.html")).read()
html = (template.replace("/*LEAFLET_CSS*/", leaflet_css)
        .replace("/*DATA*/", "const DATA = " + json.dumps(payload, separators=(",", ":")) + ";"))
out = os.path.join(WEB, "rainy_season_access.html")
open(out, "w").write(html)
print(f"wrote {out} ({os.path.getsize(out) / 1e6:.1f} MB), {len(feats)} sub-counties")

# Standalone copy for hosting anywhere or opening offline: a complete document with
# the Leaflet script inlined (no CDN needed; web fonts fall back to system fonts).
CDN = '<script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js"></script>'
leaflet_js = open(os.path.join(WEB, "leaflet.js")).read()
assert CDN in html and "</script" not in leaflet_js
standalone = ("<!doctype html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
              "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1, viewport-fit=cover\">\n"
              "<meta name=\"description\" content=\"Travel time to hospitals, health centres, schools and "
              "markets in Uganda, month by month, and how much the rains lengthen it.\">\n"
              "<style>*,*::before,*::after{box-sizing:border-box}body{margin:0}[hidden]{display:none!important}</style>\n"
              "</head>\n<body>\n"
              + html.replace(CDN, "<script>" + leaflet_js + "</script>")
              + "\n</body>\n</html>\n")
out2 = os.path.join(WEB, "index.html")
open(out2, "w").write(standalone)
print(f"wrote {out2} ({os.path.getsize(out2) / 1e6:.1f} MB), standalone")
