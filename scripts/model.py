"""Friction-surface travel-time model on the WorldPop 1 km grid.

  1. Each cell gets the speed of the fastest OSM road through it, for a dry day and a
     wet day (unpaved roads slow down on wet days; roads crossing a ford become
     near-impassable, unless another road runs through the same cell).
     Cells with no road are crossed on foot.
  2. The chance that a day in a given month is wet at that location comes from CHIRPS:
     the share of days that are "lost earthworks days" (rain >=10 mm, or the day after
     >=25 mm), the same rule as the main paper.
  3. Expected time to cross a cell in month m is (1-f)/v_dry + f/v_wet, where f is that
     wet-day share.
  4. Travel time to the nearest destination is the least-cost path over the
     8-connected grid (Dijkstra from all destinations at once).

Two travel modes: "motorised" (road speeds by class; motorcycle taxis on paths) and
"walking" (walking pace on every road, slower on wet earth). Cells outside WorldPop's
land mask (outside Uganda, and open water) are impassable; ferries are not modelled.

All assumptions are in PARAMS; pass overrides to build_speeds() for sensitivity tests.
"""
import os, sys
import numpy as np
import pandas as pd
import geopandas as gpd
import rasterio
from rasterio import features
from scipy import sparse
from scipy.sparse.csgraph import dijkstra

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
sys.path.insert(0, HERE)
from rain import EARTHWORKS_MM, DRYING_MM, EARLY, LATE, load_precip  # noqa: E402

EARLY_LATE = {"early": EARLY, "late": LATE}

PARAMS = dict(
    # Dry-day speed (km/h) by OSM highway class, motorised.
    speed={"motorway": 100, "trunk": 80, "primary": 60, "secondary": 50, "tertiary": 40,
           "unclassified": 30, "residential": 20, "living_street": 20, "service": 20,
           "road": 20, "track": 15,
           "path": 10, "bridleway": 10, "cycleway": 10,   # motorcycle taxis use these
           "footway": 5, "pedestrian": 5, "steps": 5},
    speed_scale=1.0,          # multiplies every motorised road speed
    walk_kmh=5.0,             # walking pace, off-road and (walking mode) on roads
    # Share of dry speed kept on a wet day, by surface group.
    wet_factor={"paved": 1.0, "gravel": 0.7, "earth": 0.4, "foot": 0.6},
    walk_wet_factor={"paved": 1.0, "gravel": 0.9, "earth": 0.7, "foot": 0.6},
    offroad_wet_factor=0.6,
    unpaved_cap={"gravel": 50, "earth": 30},   # max dry speed on unpaved surfaces
    ford_wet_kmh=0.5,         # a ford cell on a wet day: wading or waiting
    ford_blocks_cell=False,   # True: a ford slows the whole 1 km cell, even other roads
    # When surface is not tagged: assumed surface by class (others: earth).
    default_surface={"motorway": "paved", "trunk": "paved", "primary": "paved",
                     "secondary": "gravel", "tertiary": "gravel"},
    # Wet-day rule for the monthly wet-day share.
    wet_mm=EARTHWORKS_MM, drying_mm=DRYING_MM,
)
PAVED = {"paved", "asphalt", "concrete", "concrete:plates", "paving_stones", "sett",
         "chipseal", "cobblestone", "metal", "concrete:lanes"}
GRAVEL = {"gravel", "fine_gravel", "compacted", "murram", "pebblestone", "laterite"}
EARTH = {"unpaved", "dirt", "earth", "ground", "mud", "sand", "grass", "soil"}
FOOT = {"path", "bridleway", "cycleway", "footway", "pedestrian", "steps"}
STEPS = [(0, 1), (1, 0), (1, 1), (1, -1)]   # forward neighbours; graph made symmetric


def params(**overrides):
    p = {k: (dict(v) if isinstance(v, dict) else v) for k, v in PARAMS.items()}
    for k, v in overrides.items():
        if isinstance(v, dict):
            p[k].update(v)
        else:
            p[k] = v
    return p


class Grid:
    """WorldPop 1 km grid, population, land mask and the graph's edge geometry."""

    def __init__(self):
        with rasterio.open(os.path.join(DATA, "uga_ppp_2020_1km.tif")) as src:
            pop = src.read(1).astype(float)
            self.transform, self.crs, self.shape = src.transform, src.crs, src.shape
            nodata = src.nodata
        self.land = (pop != nodata) & np.isfinite(pop)
        self.pop = np.where(self.land, np.maximum(pop, 0), 0.0)
        R, C = self.shape
        t = self.transform
        self.rows_lat = t.f + t.e * (np.arange(R) + 0.5)
        self.cols_lon = t.c + t.a * (np.arange(C) + 0.5)
        self.idx = -np.ones(self.shape, dtype=np.int64)
        self.idx[self.land] = np.arange(self.land.sum())
        self.n = int(self.land.sum())
        dy_km = abs(t.e) * 110.57
        dx_km = t.a * 111.32 * np.cos(np.radians(self.rows_lat))
        self.edges = []
        for dr, dc in STEPS:
            s0 = (slice(0, R - dr), slice(max(0, -dc), C - max(0, dc)))
            s1 = (slice(dr, R), slice(max(0, dc), C - max(0, -dc)))
            a, b = self.idx[s0], self.idx[s1]
            ok = (a >= 0) & (b >= 0)
            rows = np.broadcast_to(np.arange(R - dr)[:, None], a.shape)
            dist = np.sqrt((dx_km[rows] * abs(dc)) ** 2 + (dy_km * dr) ** 2)
            self.edges.append((a[ok], b[ok], dist[ok], s0, s1, ok))

    def rasterize(self, geoms, value=1, dtype="uint8", all_touched=False):
        return features.rasterize(((g, value) for g in geoms), out_shape=self.shape,
                                  transform=self.transform, fill=0, dtype=dtype,
                                  all_touched=all_touched)

    def zones(self, gdf):
        """Zone number (1-based row position in gdf) for every cell, 0 outside."""
        return features.rasterize(((g, i + 1) for i, g in enumerate(gdf.to_crs(self.crs).geometry)),
                                  out_shape=self.shape, transform=self.transform, fill=0,
                                  dtype="int32")

    def graph(self, hours_per_km):
        src, dst, w = [], [], []
        for a, b, dist, s0, s1, ok in self.edges:
            cost = dist * 0.5 * (hours_per_km[s0][ok] + hours_per_km[s1][ok])
            src += [a, b]
            dst += [b, a]
            w += [cost, cost]
        return sparse.csr_matrix((np.concatenate(w), (np.concatenate(src), np.concatenate(dst))),
                                 shape=(self.n, self.n))

    def travel_time(self, hours_per_km, targets, sources=False, graph=None):
        """Hours from every land cell to the nearest target cell. With sources=True,
        also returns the grid index (row*cols+col) of that nearest target."""
        g = self.graph(hours_per_km) if graph is None else graph
        t_idx = np.unique(self.idx[targets & self.land])
        d, _, src = dijkstra(g, directed=False, indices=t_idx, min_only=True,
                             return_predecessors=True)
        out = np.full(self.shape, np.nan)
        out[self.land] = np.where(np.isinf(d), np.nan, d)
        if not sources:
            return out
        land_flat = np.flatnonzero(self.land.ravel())
        nearest = np.full(self.shape, -1, dtype=np.int64)
        nearest[self.land] = np.where(src >= 0, land_flat[np.maximum(src, 0)], -1)
        return out, nearest

    def pop_stats(self, tt, weights=None):
        """Share of people beyond 1 h and 2 h (unreachable counts as beyond), and mean
        hours among the reachable."""
        w = self.pop if weights is None else weights
        ok = np.isfinite(tt) & (w > 0)
        P = w[w > 0].sum()
        out_1 = w[(w > 0) & ~(tt <= 1)].sum()
        out_2 = w[(w > 0) & ~(tt <= 2)].sum()
        return dict(mean_hours=np.average(tt[ok], weights=w[ok]),
                    share_over_1h=out_1 / P, share_over_2h=out_2 / P)


def load_fords():
    return gpd.read_file(os.path.join(DATA, "osm_features.gpkg"), layer="fords")


def load_roads():
    """Roads with a `crosses_ford` flag: tagged ford=*, or passing through a ford node."""
    roads = gpd.read_file(os.path.join(DATA, "osm_features.gpkg"), layer="roads")
    roads["base"] = roads.highway.str.replace("_link", "", regex=False)
    roads = roads[roads.base.isin(PARAMS["speed"])].copy()
    pts = load_fords()
    hit = gpd.sjoin(roads[["geometry"]], pts[["geometry"]], predicate="dwithin",
                    distance=1e-6).index.unique()
    roads["crosses_ford"] = roads.ford | roads.index.isin(hit)
    return roads


def surface_group(roads, p):
    s = roads.surface.fillna("").str.lower()
    group = roads.base.map(lambda b: p["default_surface"].get(b, "earth"))
    group = np.where(roads.tracktype.isin(["grade1", "grade2"]), "gravel", group)
    group = np.where(s.isin(EARTH), "earth", group)
    group = np.where(s.isin(GRAVEL), "gravel", group)
    group = np.where(s.isin(PAVED), "paved", group)
    return np.where(roads.base.isin(FOOT), "foot", group)


def ford_cells(grid, roads):
    geoms = list(load_fords().geometry) + list(roads[roads.ford].geometry)
    return grid.rasterize(geoms, all_touched=True).astype(bool)


def build_speeds(grid, roads, fords, mode="motorised", p=None):
    """Dry-day and wet-day speed (km/h) per cell.

    In a cell containing a ford, on a wet day the river blocks the roads that cross it
    and off-road walking (both drop to ford_wet_kmh), but other roads through the same
    cell keep their wet-day speed: a ford only isolates a cell when it is the only way
    through."""
    p = p or params()
    group = pd.Series(surface_group(roads, p))
    if mode == "walking":
        v_dry = np.full(len(roads), float(p["walk_kmh"]))
        v_wet = v_dry * group.map(p["walk_wet_factor"]).values
    else:
        v_dry = roads.base.map(p["speed"]).values.astype(float) * p["speed_scale"]
        v_dry = np.minimum(v_dry, group.map(p["unpaved_cap"]).fillna(np.inf).values)
        v_wet = v_dry * group.map(p["wet_factor"]).values
    v_wet = np.where(roads.bridge.values, v_dry, v_wet)   # bridges keep dry speed

    def burn(v, base):
        order = np.argsort(v)            # slow first so fast roads overwrite
        burned = features.rasterize(zip(roads.geometry.values[order], v[order]),
                                    out_shape=grid.shape, transform=grid.transform, fill=0,
                                    all_touched=True, dtype="float32")
        return np.maximum(burned, base)

    dry = burn(v_dry, p["walk_kmh"])
    wet = burn(v_wet, p["walk_kmh"] * p["offroad_wet_factor"])
    if p["ford_blocks_cell"]:
        wet = np.where(fords, np.minimum(wet, p["ford_wet_kmh"]), wet)
    else:
        other_roads = burn(np.where(roads.crosses_ford.values, 0.0, v_wet), 0.0)
        wet = np.where(fords, np.maximum(other_roads, p["ford_wet_kmh"]), wet)
    return dry, wet


def wet_share(grid, period, p=None):
    """Share of days that are wet, per month (12, rows, cols), from CHIRPS."""
    p = p or params()
    pr = load_precip("chirps").sel(time=slice(str(period[0]), str(period[1])))
    wet = (pr >= p["wet_mm"]) | (pr >= p["drying_mm"]).shift(time=1, fill_value=False)
    m = wet.where(pr.notnull()).groupby("time.month").mean().fillna(0.0)
    ilat = np.abs(m.latitude.values[None, :] - grid.rows_lat[:, None]).argmin(axis=1)
    ilon = np.abs(m.longitude.values[None, :] - grid.cols_lon[:, None]).argmin(axis=1)
    return m.values[:, ilat][:, :, ilon]


def hours_per_km(v_dry, v_wet, f=None):
    """Expected hours per km: all-dry (f=None), all-wet (f=1) or a month's share f."""
    if f is None:
        return 1.0 / v_dry
    return (1 - f) / v_dry + f / v_wet


def population_groups(grid):
    """Population weights: everyone, women 15-49 and children under 5. WorldPop's
    age/sex layers give each cell's shares, applied to the UN-adjusted total."""
    d = os.path.join(DATA, "agesex")
    read = lambda s, a: np.nan_to_num(np.maximum(rasterio.open(
        os.path.join(d, f"uga_{s}_{a}_2020_1km.tif")).read(1).astype(float), 0))
    ages = [0, 1] + list(range(5, 85, 5))
    total = sum(read(s, a) for s in "fm" for a in ages)
    share = lambda arr: np.where(total > 0, arr / np.where(total > 0, total, 1), 0)
    women = sum(read("f", a) for a in (15, 20, 25, 30, 35, 40, 45))
    under5 = sum(read(s, a) for s in "fm" for a in (0, 1))
    return {"everyone": grid.pop, "women 15-49": grid.pop * share(women),
            "children under 5": grid.pop * share(under5)}
