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


# UBOS 2016 parish boundaries, used to check facility coordinates against the places
# facilities are named after. Downloaded by hand from the UBOS GeoNode (WFS layer
# geonode:uganda_parishes_cleaned_attached); the checks are skipped if it is missing.
PARISHES = os.path.join(DATA, "uga_parishes", "uganda_parishes_cleaned_attached.shp")
NAME_KM = 2.0          # a facility this close to a unit bearing its name is where its name says
SAME_PLACE_KM = 5.0    # units bearing one name this close together are one place
# The facility list records only the region; these are its UBOS sub-regions.
REGIONS = {"Central": {"GREATER KAMPALA", "CENTRAL I", "CENTRAL II"},
           "Eastern": {"BUSOGA", "BUKEDI", "BUGISU_SEBEI", "TESO"},
           "Northern": {"WEST NILE", "LANGO", "ACHOLI", "KARAMOJA"},
           "Western": {"ANKOLE", "KIGEZI", "BUNYORO", "TORO"}}
# Words of a unit name that do not say which place it is, e.g. 'KISENYI II', 'KAZO TOWN COUNCIL'.
ADMIN_WORDS = {"ward", "town", "council", "tc", "division", "cell", "municipality", "municipal",
               "central", "north", "south", "east", "west", "upper", "lower", "rural", "urban",
               "i", "ii", "iii", "iv", "v"}


def admin_key(name):
    words = re.sub(r"[^a-z0-9 ]", " ", str(name).lower()).split()
    return frozenset(w for w in words if w not in ADMIN_WORDS)


def load_named_units():
    """Parishes, sub-counties and districts (EPSG:32636) keyed by the words of their
    name, or None if the parish file is missing."""
    if not os.path.exists(PARISHES):
        print(f"warning: {PARISHES} not found; facility coordinates not checked against place names")
        return None
    par = gpd.read_file(PARISHES).to_crs(32636)
    par["geometry"] = par.buffer(0)
    parts = []
    for level, col, by in (("parish", "p", None), ("sub-county", "s", ["F15Regions", "d", "s"]),
                           ("district", "d", ["F15Regions", "d"])):
        g = par if by is None else par.dissolve(by=by).reset_index()
        parts.append(gpd.GeoDataFrame(
            dict(region=g.F15Regions.values, level=level, unit=g[col].values,
                 district=g.d.values, key=g[col].map(admin_key).values),
            geometry=g.geometry.values, crs=par.crs))
    units = pd.concat(parts, ignore_index=True)
    return units[units.key.map(len) > 0]


def one_place(units):
    """Representative point (EPSG:32636) of units that are all one place, else None."""
    if units.empty:
        return None
    pts = units.geometry.representative_point()
    if pts.apply(lambda g: pts.distance(g).max()).max() / 1000 > SAME_PLACE_KM:
        return None
    return pts.iloc[0]


def load_official():
    """Official list, with hospitals and HC IVs moved to their OSM location where the
    official coordinates look wrong: exactly one OSM facility has the same distinctive
    name and does not state a different level (names shared by several facilities are
    narrowed to those stating the same level, and points within DUPLICATE_KM of each
    other count as one), the name is not made only of COMMON words, the OSM point is
    more than RELOCATE_KM away, and it is inside Uganda.

    The UBOS parish boundaries then check these against the place each facility is named
    after (a parish, sub-county or district of that name in its region):
      - an OSM move is dropped if it takes a facility away from a place of its name;
      - a hospital or HC IV more than RELOCATE_KM from every place of its name, and
        outside its recorded region, is moved to the sub-county of that name, if the
        name means one sub-county (inside its region, the place may simply be missing
        from the 2016 boundaries, e.g. Kinoni in Rwampara);
      - a facility without coordinates is placed in the parish (else sub-county) of its
        name, if the name means one place, and dropped otherwise;
      - other facilities more than RELOCATE_KM from every place of their name are kept
        but listed for review, since parish names repeat across the country.
    Moves are logged in data/facility_relocations.csv; dropped facilities, rejected OSM
    moves and facilities to review in outputs/facility_location_review.csv."""
    x = pd.read_excel(os.path.join(DATA, "ssa_health_facilities.xlsx"))
    x = x[x.Country == "Uganda"]
    off = gpd.GeoDataFrame(
        dict(name=x.Facility_n.values, facility_type=x.Facility_t.values,
             level=x.Facility_t.map(OFFICIAL_LEVEL).fillna("other").values,
             region=x.Admin1.values),
        geometry=gpd.points_from_xy(x.Long, x.Lat), crs="EPSG:4326")
    no_coords = ((x.Lat.fillna(0) == 0) & (x.Long.fillna(0) == 0)).values
    units = load_named_units()
    by_key = units.groupby("key") if units is not None else None

    def named(name, region):
        """Units in the region bearing the facility's distinctive name."""
        core = core_name(name)
        if units is None or not core or core <= COMMON or core not in by_key.groups:
            return None
        u = by_key.get_group(core)
        u = u[u.region.isin(REGIONS.get(region, ()))]
        return u if len(u) else None

    def near(point_m, u):
        return u.geometry.distance(point_m).min() / 1000 <= NAME_KM

    in_region = {}
    if units is not None:
        admin1 = {sub: reg for reg, subs in REGIONS.items() for sub in subs}
        districts = units[units.level == "district"].rename(columns={"region": "sub_region"})
        hit = gpd.sjoin(off.to_crs(32636)[~no_coords], districts[["sub_region", "geometry"]],
                        predicate="within")
        in_region = {i: admin1.get(sub) == off.region[i]
                     for i, sub in hit.groupby(level=0).sub_region.first().items()}

    osm = load_osm()
    osm = osm[osm.name.notna()].assign(core=lambda d: d.name.map(core_name),
                                       stated=lambda d: d.name.map(stated_level))
    by_core = osm.groupby("core")
    uganda = gpd.read_file(os.path.join(DATA, "uga_districts.geojson")).union_all()
    off_m, osm_m = off.to_crs(32636), osm.to_crs(32636)
    moves, review, moved = [], [], {}
    to_lonlat = lambda g: gpd.GeoSeries([g], crs=32636).to_crs(4326).iloc[0]

    def move(i, target, method, km, osm_name=""):
        r = off.loc[i]
        moved[i] = method
        moves.append(dict(name=r["name"], level=r.level, method=method, km_moved=km,
                          osm_name=osm_name, from_lon=r.geometry.x, from_lat=r.geometry.y,
                          to_lon=target.x, to_lat=target.y))
        off.loc[i, "geometry"] = target

    def flag(i, issue, km=None, u=None):
        r = off.loc[i]
        review.append(dict(name=r["name"], facility_type=r.facility_type, issue=issue,
                           km_from_named_place=km,
                           named_place="" if u is None else f"{u.unit.iloc[0]} ({u.level.iloc[0]})",
                           named_district="" if u is None else u.district.iloc[0],
                           lon=r.geometry.x, lat=r.geometry.y))

    for i, r in off[(off.level != "other") & ~no_coords].iterrows():
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
            u = named(r["name"], r.region)
            if u is not None and near(off_m.geometry[i], u) and not near(osm_m.geometry[j], u):
                flag(i, f"OSM move of {km:.0f} km rejected: already at a place of its name", 0.0, u)
                continue
            move(i, target, "OSM name", round(km, 1), cand.name.iloc[0])
            off_m.loc[i, "geometry"] = osm_m.geometry[j]

    for i, r in off.iterrows():
        u = named(r["name"], r.region)
        if u is None or i in moved:
            continue
        if no_coords[i]:
            for level in ("parish", "sub-county"):
                target = one_place(u[u.level == level])
                if target is not None:
                    move(i, to_lonlat(target), f"{level} name (no coordinates)", None)
                    break
            continue
        km = round(u.geometry.distance(off_m.geometry[i]).min() / 1000, 1)
        if km <= RELOCATE_KM:
            continue
        outside = not in_region.get(i, False)
        target = one_place(u[u.level == "sub-county"]) if r.level != "other" and outside else None
        if target is not None:
            move(i, to_lonlat(target), "sub-county name", round(target.distance(off_m.geometry[i]) / 1000, 1))
            continue
        flag(i, "far from every place of its name" + ("; outside its recorded region" if outside else ""), km, u)

    placed = off.index.isin(list(moved)) & no_coords
    for i in off.index[no_coords & ~placed]:
        flag(i, "no coordinates; dropped")
    pd.DataFrame(moves).to_csv(os.path.join(DATA, "facility_relocations.csv"), index=False)
    pd.DataFrame(review).to_csv(os.path.join(DATA, "..", "outputs", "facility_location_review.csv"),
                                index=False)
    return off[~no_coords | placed].drop(columns="region")


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
