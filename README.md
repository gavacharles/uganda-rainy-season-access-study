# uganda-rainy-season-access-study

Python pipeline, outputs, figures and presentation for modelling travel time to hospitals, health centres, schools and markets in Uganda month by month, and how much the rainy seasons lengthen it (OpenStreetMap, WorldPop, CHIRPS).

The interactive map built from this repository is published at https://gavacharles.github.io/uganda-rainy-season-access/ from a separate public repository that holds only the page. `web/index.html` is a self-contained offline copy.

## Setup

Install the packages in `requirements.txt` (Python 3.9), then run each script from `scripts/`. Downloaded data goes to `data/` (not tracked).

## Pipeline

| Step | Script | What it does |
|---|---|---|
| 0 | `00_download_chirps.py 1981 2025` | Downloads CHIRPS daily rainfall and clips it to Uganda |
| 1 | `01_download.sh` | Downloads the other inputs: OSM extract, WorldPop population and age/sex structure, HDX COD-AB boundaries, public facility list, wealth index and others |
| 2 | `02_extract_osm.py` | Extracts roads, fords, health facilities, schools, markets, towns and refugee sites |
| 3 | `03_seasonal_access.py [src] [mode]` | Travel time to six destinations for a dry day, a wet day and each month, under two rainfall periods |
| 4 | `04_district_breakdown.py [src] [mode]` | Sub-county table, district × month heatmap and district profiles |
| 5 | `05_equity_breakdown.py` | Emergency obstetric care, wealth gradient, refugee-site sub-counties, hospital catchments |
| 6 | `06_sensitivity.py` | Variants of the assumptions and of the facility source |
| 7 | `07_crossings.py` | Ranks river crossings by wet-day time saved |
| 8 | `08_dhs_validation.py` | Compares modelled access with DHS 2016 outcomes |
| 9 | `09_maps.py` | National and sub-county map series |
| 10 | `10_interactive_map.py` | Builds the interactive map from `interactive_map_template.html` |
| 11 | `11_animations.py` | Month-by-month animated GIFs |
| 12 | `12_publish_site.sh` | Pushes the rebuilt `web/index.html` to the public site |

Shared modules in `scripts/`: `model.py` (travel-time model and its parameters in `PARAMS`), `facilities.py` (destinations and run settings), `zonal.py` (sub-county statistics), `cartography.py` (map furniture), `rain.py` (wet-day thresholds and CHIRPS loader).

## Outputs

- `outputs/`: access tables (national, district, sub-county, obstetric care, wealth, refugee), hospital catchments, crossing priorities, sensitivity, DHS checks, sub-county map data, travel-time rasters (`travel_time_*.tif`, bands: dry, wet, then January to December)
- `figures/`: charts, `maps/` (national and `subcounty/`), `districts/` profiles, `animations/`
- `web/`: the map page and its Leaflet files
- `presentation/`: slide deck and its builder
- `posts/`: post drafts, images and the preview builder
