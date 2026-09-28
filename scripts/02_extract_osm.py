"""Extract roads, fords and health facilities from the Uganda OSM extract.

Writes ../data/osm_features.gpkg with layers:
  roads    one line per highway way: highway, surface, tracktype, bridge, ford
  fords    ford nodes (ford=yes etc.), where a road crosses water without a bridge
  health   health facilities as points (nodes, or the centroid of mapped buildings/areas)
  places   other destinations as points: kind = school, market, town or refugee_site
           (school keeps isced:level and name so primary/secondary can be told apart)
"""
import os
import osmium
import geopandas as gpd
from shapely.geometry import LineString, Point, Polygon

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
PBF = os.path.join(DATA, "uganda-latest.osm.pbf")

ROAD_CLASSES = {
    "motorway", "motorway_link", "trunk", "trunk_link", "primary", "primary_link",
    "secondary", "secondary_link", "tertiary", "tertiary_link", "unclassified",
    "residential", "living_street", "service", "road", "track",
    "path", "footway", "bridleway", "pedestrian", "cycleway", "steps"}
HEALTH_AMENITY = {"hospital", "clinic", "doctors", "health_post"}
HEALTH_CARE = {"hospital", "clinic", "centre", "doctor", "health_post"}


def place_type(tags):
    a, pl = tags.get("amenity"), tags.get("place")
    if a == "school":
        return "school"
    if a == "marketplace":
        return "market"
    if pl in ("city", "town"):
        return "town"
    if a == "refugee_site" or pl == "refugee_camp" or tags.get("refugee") == "yes":
        return "refugee_site"
    return None


def health_type(tags):
    a, h = tags.get("amenity"), tags.get("healthcare")
    if a in HEALTH_AMENITY or h in HEALTH_CARE:
        return "hospital" if "hospital" in (a, h) else "other"
    return None


roads, fords, health, places = [], [], [], []


def add_place(o, tags, geom):
    kind = place_type(tags)
    if kind:
        places.append(dict(osm_id=f"{o.type_str()}{o.id}", kind=kind, name=tags.get("name"),
                           isced=tags.get("isced:level"), geometry=geom))


fp = (osmium.FileProcessor(PBF)
      .with_locations()
      .with_filter(osmium.filter.KeyFilter("highway", "ford", "amenity", "healthcare",
                                           "place", "refugee")))
for o in fp:
    tags = o.tags
    if o.is_node():
        if tags.get("ford") not in (None, "no"):
            fords.append(dict(osm_id=o.id, geometry=Point(o.location.lon, o.location.lat)))
        kind = health_type(tags)
        if kind:
            health.append(dict(osm_id=f"n{o.id}", kind=kind, name=tags.get("name"),
                               geometry=Point(o.location.lon, o.location.lat)))
        add_place(o, tags, Point(o.location.lon, o.location.lat))
    elif o.is_way():
        try:
            coords = [(n.lon, n.lat) for n in o.nodes]
        except osmium.InvalidLocationError:
            continue
        if len(coords) < 2:
            continue
        hw = tags.get("highway")
        if hw in ROAD_CLASSES:
            roads.append(dict(osm_id=o.id, highway=hw, surface=tags.get("surface"),
                              tracktype=tags.get("tracktype"),
                              bridge=tags.get("bridge") not in (None, "no"),
                              ford=tags.get("ford") not in (None, "no"),
                              geometry=LineString(coords)))
        kind = health_type(tags)
        if kind and len(coords) >= 4 and coords[0] == coords[-1]:
            health.append(dict(osm_id=f"w{o.id}", kind=kind, name=tags.get("name"),
                               geometry=Polygon(coords).centroid))
        if len(coords) >= 4 and coords[0] == coords[-1]:
            add_place(o, tags, Polygon(coords).centroid)

out = os.path.join(DATA, "osm_features.gpkg")
if os.path.exists(out):
    os.remove(out)
for layer, rows in (("roads", roads), ("fords", fords), ("health", health), ("places", places)):
    gdf = gpd.GeoDataFrame(rows, geometry="geometry", crs="EPSG:4326")
    gdf.to_file(out, layer=layer, engine="pyogrio")
    print(layer, len(gdf))
