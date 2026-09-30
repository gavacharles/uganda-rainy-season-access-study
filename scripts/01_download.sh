#!/bin/sh
# Download inputs: OpenStreetMap Uganda extract, WorldPop 2020 population (1 km,
# UN-adjusted) and official district (admin 2) and sub-county (admin 4) boundaries
# from HDX (COD-AB), WorldPop age/sex structure, Meta's Relative Wealth Index, and the public-sector health facility list for sub-Saharan Africa
# (Maina et al. 2019, via HDX), which records Ministry of Health facility levels.
# Skips files already present.
set -e
cd "$(dirname "$0")/../data"
get() { [ -s "$2" ] || curl -sSfL --retry 3 -o "$2" "$1"; echo "$2 ok"; }
get https://download.geofabrik.de/africa/uganda-latest.osm.pbf uganda-latest.osm.pbf
get https://data.humdata.org/dataset/eb1ba830-9464-43c8-9370-28cee0c99f5d/resource/758d5c17-88f4-42b2-9d4b-4bfe32d4acf7/download/sub-saharan_health_facilities.xlsx ssa_health_facilities.xlsx
get https://data.worldpop.org/GIS/Population/Global_2000_2020_1km_UNadj/2020/UGA/uga_ppp_2020_1km_Aggregated_UNadj.tif uga_ppp_2020_1km.tif
if [ ! -s uga_districts.geojson ] || [ ! -s uga_subcounties.geojson ]; then
  get https://data.humdata.org/dataset/6d6d1495-196b-49d0-86b9-dc9022cde8e7/resource/4a409743-e1b7-40d7-ad05-e08920f4b099/download/uga_admin_boundaries.geojson.zip admin.zip
  unzip -o -q -j admin.zip uga_admin2.geojson uga_admin4.geojson
  mv uga_admin2.geojson uga_districts.geojson && mv uga_admin4.geojson uga_subcounties.geojson && rm admin.zip
fi

# WorldPop 2020 age/sex structure (1 km, unconstrained): 5-year bands 0,1,5,...,80 for
# each sex, used to weight results for women 15-49 and children under 5.
mkdir -p agesex
for s in f m; do for a in 0 1 5 10 15 20 25 30 35 40 45 50 55 60 65 70 75 80; do
  f=uga_${s}_${a}_2020_1km.tif
  [ -s agesex/$f ] || curl -sSfL --retry 3 -o agesex/$f https://data.worldpop.org/GIS/AgeSex_structures/Global_2000_2020_1km/unconstrained/2020/UGA/$f
done; done; echo "agesex ok"
# Meta Relative Wealth Index (2.4 km tiles), for breakdowns by relative wealth.
get https://data.humdata.org/dataset/76f2a2ea-ba50-40f5-b79c-db95d668b843/resource/ae47ca7e-de1b-40f5-8b30-81ba30bed89b/download/uga_relative_wealth_index.csv uga_relative_wealth_index.csv

# UBOS 2016 parish boundaries, used by facilities.py to check facility coordinates against
# the places facilities are named after. The UBOS GeoNode needs an access token, so this
# one is downloaded by hand: layer geonode:uganda_parishes_cleaned_attached as SHAPE-ZIP from
# http://ubos.geo-solutions.it/geoserver/wfs, unpacked into data/uga_parishes/.
[ -s uga_parishes/uganda_parishes_cleaned_attached.shp ] && echo "uga_parishes ok" || echo "uga_parishes missing (manual download; facility checks will be skipped)"
