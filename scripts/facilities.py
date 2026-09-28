"""Destinations (health facilities, schools, markets, towns) and run settings, shared
by the analysis scripts.

Two sources, both reduced to three levels (hospital, hc4, other):
  official  Public and not-for-profit facilities from the Ministry of Health list,
            geocoded by Maina et al. (2019), "A spatial database of health facilities
            managed by the public health sector in sub-Saharan Africa". Levels are
            recorded, but private for-profit facilities are not included. Default.
  osm       OpenStreetMap. Includes private facilities, but tagging over-uses
            amenity=hospital (most such features are Health Centre II/III) and some
            public facilities are missing, so the level is read from the name.
"""
import os, re, sys
import pandas as pd
import geopandas as gpd

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")

TARGET_LEVELS = {"hospital": {"hospital"},
                 "HC IV or hospital": {"hospital", "hc4"},
                 "any facility": {"hospital", "hc4", "other"}}
OFFICIAL_LEVEL = {"Hospital": "hospital", "Regional Referral Hospital": "hospital",
                  "National Referral Hospital": "hospital", "Health Centre IV": "hc4"}


def run_from_argv():
    """Facility source and travel mode from the command line:
    script.py [official|osm] [motorised|walking]  (defaults: official motorised)."""
    src = sys.argv[1] if len(sys.argv) > 1 else "official"
    mode = sys.argv[2] if len(sys.argv) > 2 else "motorised"
    if src not in ("official", "osm") or mode not in ("motorised", "walking"):
        sys.exit("usage: script.py [official|osm] [motorised|walking]")
    return src, mode


def output_dirs(root, source, mode="motorised"):
    """The default run (official facilities, motorised) writes to the top-level
    outputs/ and figures/; other runs write to a subfolder named after what differs,
    e.g. facilities_osm/ or walking/."""
    sub = "_".join(x for x in ("facilities_osm" if source == "osm" else "",
                               "walking" if mode == "walking" else "") if x)
    out, fig = os.path.join(root, "outputs", sub), os.path.join(root, "figures", sub)
    os.makedirs(out, exist_ok=True)
    os.makedirs(fig, exist_ok=True)
    return out, fig


GENERIC = {"hospital", "health", "centre", "center", "hc", "h/c", "iv", "iii", "ii", "4",
           "referral", "regional", "national", "general", "district", "the", "of", "and", "st"}
# Names made only of these words are too common to match safely across sources.
COMMON = {"family", "care", "mission", "memorial", "community", "medical", "mercy", "holy",
          "cross", "mary", "joseph", "saint", "good", "samaritan", "hope", "life", "christ",
          "international", "city", "kampala", "military", "police", "prison", "church"}
RELOCATE_KM = 10.0
DUPLICATE_KM = 2.0     # OSM points this close with the same name are one facility


def core_name(name):
    """Distinctive words of a facility name, e.g. 'Adjumani Hospital' -> {'adjumani'}."""
    words = re.sub(r"[^a-z0-9 ]", " ", str(name).lower().replace("'s", "")).split()
    return frozenset(w for w in words if w not in GENERIC and len(w) > 1)


def stated_level(name):
    """Level stated in a facility name, or None if the name does not say."""
    n = str(name).lower()
    if "hospital" in n:
        return "hospital"
    m = re.search(r"(?:hc|h/c|health ?cent(?:re|er))[\s\-]*(iv|iii|ii|4|3|2)\b", n)
    if m:
        return {"iv": "hc4", "4": "hc4", "iii": "hc3", "3": "hc3", "ii": "hc2", "2": "hc2"}[m.group(1)]
    return None


def load_osm():
    health = gpd.read_file(os.path.join(DATA, "osm_features.gpkg"), layer="health")
    lvl = health.name.map(stated_level)
    health["level"] = lvl.where(lvl.isin(["hospital", "hc4"]), "other")
    return health


def load_official():
    """Official list, with hospitals and HC IVs moved to their OSM location where the
    official coordinates look wrong: exactly one OSM facility has the same distinctive
    name and does not state a different level (names shared by several facilities are
    narrowed to those stating the same level, and points within DUPLICATE_KM of each
    other count as one), the name is not made only of COMMON words, the OSM point is
    more than RELOCATE_KM away, and it is inside Uganda. Each move is logged in data/facility_relocations.csv."""
    x = pd.read_excel(os.path.join(DATA, "ssa_health_facilities.xlsx"))
    x = x[x.Country == "Uganda"]
    off = gpd.GeoDataFrame(
        dict(name=x.Facility_n.values, facility_type=x.Facility_t.values,
             level=x.Facility_t.map(OFFICIAL_LEVEL).fillna("other").values),
        geometry=gpd.points_from_xy(x.Long, x.Lat), crs="EPSG:4326")
    osm = load_osm()
    osm = osm[osm.name.notna()].assign(core=lambda d: d.name.map(core_name),
                                       stated=lambda d: d.name.map(stated_level))
    by_core = osm.groupby("core")
    uganda = gpd.read_file(os.path.join(DATA, "uga_districts.geojson")).union_all()
    off_m, osm_m = off.to_crs(32636), osm.to_crs(32636)
    moves = []
    for i, r in off[off.level != "other"].iterrows():
        core = core_name(r["name"])
        if not core or core <= COMMON or core not in by_core.groups:
            continue
        cand = by_core.get_group(core)
        cand = cand[cand.stated.isna() | (cand.stated == r.level)]
        if len(cand) > 1:
            cand = cand[cand.stated == r.level]
        if len(cand) > 1:
            pts = osm_m.geometry[cand.index]
            if pts.apply(lambda g: pts.distance(g).max()).max() / 1000 <= DUPLICATE_KM:
                cand = cand.iloc[:1]
        if len(cand) != 1:
            continue
        j = cand.index[0]
        km = off_m.geometry[i].distance(osm_m.geometry[j]) / 1000
        target = cand.geometry.iloc[0]
        if km > RELOCATE_KM and uganda.contains(target):
            moves.append(dict(name=r["name"], level=r.level, km_moved=round(km, 1),
                              osm_name=cand.name.iloc[0], from_lon=r.geometry.x,
                              from_lat=r.geometry.y, to_lon=target.x, to_lat=target.y))
            off.loc[i, "geometry"] = target
    pd.DataFrame(moves).to_csv(os.path.join(DATA, "facility_relocations.csv"), index=False)
    return off


def load_health(source="official"):
    return load_official() if source == "official" else load_osm()


SECONDARY = r"secondary|high school|\bs\.?\s?s\.?\b|college|seminary"


def load_places():
    return gpd.read_file(os.path.join(DATA, "osm_features.gpkg"), layer="places")


def load_destinations(source="official"):
    """Point sets travel time is measured to. Health levels come from `source`; the
    others from OSM. Secondary schools: ISCED level 2 or 3, or a secondary-type name."""
    health = load_health(source)
    places = load_places()
    schools = places[places.kind == "school"]
    name = schools.name.fillna("").str.lower()
    secondary = schools[schools.isced.fillna("").str.contains("2|3")
                        | (name.str.contains(SECONDARY) & ~name.str.contains("primary"))]
    dest = {k: health[health.level.isin(v)] for k, v in TARGET_LEVELS.items()}
    dest.update({"secondary school": secondary,
                 "market": places[places.kind == "market"],
                 "town": places[places.kind == "town"]})
    return dest
