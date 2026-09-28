# When the Rains Come: Seasonal Access to Health Care, Schools and Markets in Uganda

## Paper summary

**Question.** How much do Uganda's rainy seasons lengthen journeys to hospitals, health centres, schools, markets and towns; where; in which months; and for whom?

**Data.** OpenStreetMap roads (about 690,000 segments, with class, surface and fords), the Ministry of Health public and not-for-profit facility list (Maina et al. 2019), WorldPop 2020 population and age/sex structure on a 1 km grid, HDX district and sub-county boundaries, Meta's Relative Wealth Index, 45 years of CHIRPS daily rainfall, and DHS 2016 regional indicators for validation. All public; no surveys.

**Approach.** A 1 km friction surface: each cell takes the speed of its fastest road, and on a wet day unpaved roads slow down and fords become close to impassable. CHIRPS gives each cell's share of wet days in each month, so a month's expected crossing time mixes dry and wet speeds. Least-cost travel time to the nearest destination is then computed for every month, by road and on foot, and broken down by district, sub-county, wealth, women of reproductive age and refugee-hosting areas. Every assumption is varied in 16 sensitivity runs, and the results are checked against DHS 2016.

**Main findings.**
- 13% of Ugandans are more than an hour from a hospital by road in dry weather; in April, the peak of the long rains, 18% (about 2.3 million more people); on a fully wet day, 31%.
- The burden is unequal: 23% of the poorest fifth are more than an hour from a hospital in dry weather and 32% in April; the richest fifth stay near 1%.
- On foot, 44% of women aged 15–49 are more than two hours from emergency obstetric care in April. Walking, not road distance, is the barrier.
- A handful of river crossings matter a great deal: a bridge at the top-ranked ford (Riwo, Bukwo) would bring about 7,000 people within an hour of emergency obstetric care on wet days.
- Modelled access tracks the share of women who cite distance as a barrier to care (Spearman ρ ≈ 0.8 across 15 regions). The seasonal cycle, not the long-term rainfall trend, is what matters.

**Status.** Analysis complete; public interactive map live; write-up drafted as a Substack post (`posts/`).

**Related repositories.** Companion papers by the same author: `uganda-seasons-construction-delay` (climate and construction delay; source of the wet-day rule) and `uganda-trade-corridors` (bottlenecks on the main trade corridors).

## Interactive map

**Interactive map:** https://gavacharles.github.io/uganda-rainy-season-access/ is public and needs no account. It is served by GitHub Pages from the `site/` folder, a separate public repo that holds only the page.

- **Offline copy:** `web/index.html` is a single self-contained file that works offline, so it can be emailed or opened from a USB stick.
- **Claude copy:** https://claude.ai/artifact/GHZ1dpps68W2NCLjEfykdG, which is private unless shared from its Share menu.
- **Updating:** after any change, run `10_interactive_map.py`, then `12_publish_site.sh`.

## Pipeline

Install the packages in `requirements.txt` (Python 3.9), then run each script from `scripts/` with that Python (locally, `../.venv/bin/python`). CHIRPS rainfall is downloaded by `00_download_chirps.py 1981 2025` into `data/chirps_uganda/`. Scripts that take `[official|osm] [motorised|walking]` default to `official motorised`. Other runs write to subfolders of `outputs/` and `figures/`: `walking/` and `facilities_osm/`.

| Step | Script | What it does |
|---|---|---|
| 0 | `00_download_chirps.py 1981 2025` | Downloads CHIRPS daily rainfall and clips it to Uganda. |
| 1 | `01_download.sh` | Downloads the inputs: the Geofabrik OSM extract; WorldPop 2020 population (1 km) and age/sex structure; HDX COD-AB district and sub-county boundaries; the public facility list (Maina et al. 2019); Meta's Relative Wealth Index. |
| 2 | `02_extract_osm.py` | Extracts roads (class, surface, bridge, ford), fords, health facilities, schools, markets, towns and refugee sites. |
| 3 | `03_seasonal_access.py [src] [mode]` | Computes travel time to six destinations for a dry day, a wet day, and each month under 1981–2000 and 2006–2025 rainfall. Writes national tables for everyone, women 15–49 and children under 5; district tables; and 14-band GeoTIFFs. |
| 4 | `04_district_breakdown.py [src] [mode]` | Writes the sub-county table, the district × month heatmap and six district profiles. |
| 5 | `05_equity_breakdown.py` | Covers emergency obstetric care for women, the wealth quintile gradient, refugee-site sub-counties and hospital catchments. |
| 6 | `06_sensitivity.py` | Runs 16 variants of the assumptions and of the facility source. |
| 7 | `07_crossings.py` | Ranks river crossings by wet-day time saved to emergency obstetric care. |
| 8 | `08_dhs_validation.py` | Compares modelled access with DHS 2016 outcomes across 15 regions. |
| 9 | `09_maps.py` | Draws the GIS map series: 8 national and 8 sub-county maps. |
| 10 | `10_interactive_map.py` | Builds the interactive map from `interactive_map_template.html`. |
| 11 | `11_animations.py` | Renders month-by-month animated GIFs. |
| 12 | `12_publish_site.sh` | Pushes the rebuilt `web/index.html` to the public site. |

Shared modules:
- `model.py`: the travel-time model and all its assumptions, in `PARAMS`.
- `facilities.py`: destinations and run settings.
- `zonal.py`: sub-county statistics.
- `cartography.py`: map furniture.
- `rain.py`: the wet-day thresholds and the CHIRPS loader.

Every static map has a title, a key, a scale bar and a north arrow, and its labels are placed so they do not overlap. Admin boundaries are clipped to land so lake areas are not drawn.

## Method

The model uses a friction surface on WorldPop's 1 km grid.

**Speeds.** Each cell takes the speed of the fastest road through it:
- Dry-day speed comes from the road class.
- On wet days, unpaved roads keep 70% (gravel) or 40% (earth) of their speed, and footpaths keep 60%.
- Roads that cross a ford drop to 0.5 km/h on a wet day. Other roads through the same 1 km cell keep their speed, so a ford only cuts off a cell when it is the only way through.

**Monthly travel time.** The chance that a day is wet comes from CHIRPS: the companion paper's lost-earthworks rule, which is rain of 10 mm or more, or the day after rain of 25 mm or more. A month's expected time to cross a cell is `(1−f)/v_dry + f/v_wet`, where `f` is that wet-day share. Travel time is then the least-cost path to the nearest destination.

**Modes.**
- *Motorised:* road speeds, with motorcycle taxis on paths.
- *Walking:* 5 km/h, slower on wet earth.

**Destinations.**
- *Hospitals, HC IVs and other facilities:* from the Ministry of Health public and not-for-profit list, which records levels. 22 hospitals and HC IVs with clearly wrong coordinates were moved to their OSM location; see `data/facility_relocations.csv`.
- *Secondary schools, markets and towns:* from OSM.

## Results (2006–2025 rainfall, official facilities)

**Seasonal access**
- **Hospitals, by road:** 13.1% of people are more than 1 hour from a hospital in dry weather. That rises to 18.1% in April, the worst month in 79 of 135 districts (about 2.3 million more people), and to 30.5% on a fully wet day.
- **On foot:**
  - 16.8% are more than 1 hour from any facility in dry weather, rising to 20.2% in April.
  - 41% of women aged 15–49 are more than 2 hours from emergency obstetric care (HC IV or hospital) in dry weather, rising to 44% in April.
  - By road, the same figure for women is 0.9% rising to 1.3%. Walking, not distance by road, is the barrier.
- **Other destinations, by road, dry weather to April:**
  - more than 1 hour from a market: 17.0% to 21.4%
  - from a town: 6.2% to 9.4%
  - from a secondary school: 2.4% to 2.9% (27% to 30% on foot)

**Who is affected**
- **Wealth:** by road, 23% of the poorest fifth are more than 1 hour from a hospital in dry weather and 32% in April; for the richest fifth, 0.8% and 1.0%. On foot to any facility, the poorest fifth go from 31% to 37%; the richest fifth are at 1%.
- **Refugee-site sub-counties:** 22% of people are more than 1 hour from a hospital in dry weather and 33% in April, against 13% and 18% elsewhere. This covers only the 14 sub-counties with an OSM refugee site, mostly in West Nile.
- **Sub-counties:** the largest April jumps are Malongo (Mayuge), 59% to 93%; Kagulu (Buyende), 33% to 66%; Butoloogo (Mubende), 26% to 84%; and Kyangwali (Kikuube, refugee settlement), 54% to 77%.
- **Hospital catchments:** the rains push most people beyond 1 hour in the catchments of Mubende RRH (155,000 people in April), Lira RRH (141,000), Kamuli (127,000), Kagadi (118,000) and Pallisa (108,000).

**Crossings to bridge.** 72 distinct crossings were ranked. Bridging the top one, on a secondary road in Riwo (Bukwo), would bring about 7,000 people within 1 hour of emergency obstetric care on wet days, including 1,500 women of reproductive age. The next are Karita (Amudat) and Panyangara (Kotido).

**Check against DHS 2016 (15 regions).** Modelled access matches the share of women who cite distance as a barrier to care:
- Spearman ρ = 0.81–0.85 (p < 0.001).
- ρ = 0.55–0.60 after controlling for wealth (p = 0.02–0.035).

Modelled access does **not** predict facility births or vaccination at regional level; Karamoja, for example, has poor access but 80% facility births. A seasonal test, whether facility births dip in the months access worsens, needs DHS birth-level microdata. These require a free registration at dhsprogram.com.

**Sensitivity** (`outputs/sensitivity.csv`, `figures/fig8_sensitivity.png`). The April increase is positive in all 16 variants. District rankings agree with the baseline (Spearman 0.88–1.00). The size of the increase depends most on how a wet day is defined: +0.8 points at 20 mm, +5.0 at 10 mm (baseline) and +10.5 at 5 mm. Report that range.

**Change since 1981–2000.** The national seasonal pattern is almost unchanged. For access, the seasonal cycle matters much more than the long-term trend.

## Outputs

**Tables** (`outputs/`):
- `access_*`: national, district, sub-county, EmOC, wealth and refugee tables
- `hospital_catchments.csv`
- `crossings_priority.csv`
- `sensitivity.csv`
- `dhs_*`
- `subcounty_map_data.csv`
- `travel_time_*.tif`: bands are dry, wet, then January to December

**Charts** (`figures/`):
- `fig2`: monthly curve
- `fig3`: district penalties
- `fig4`: heatmap
- `fig6`: wealth gradient
- `fig8`: sensitivity
- `fig10`: DHS check

**Maps** (`figures/maps/`): `m01`–`m08` national; `subcounty/s01`–`s08`.

**District profiles** (`figures/districts/`): Kotido, Nakapiripirit, Agago, Kasese, Kikuube, Mayuge.

**Animations** (`figures/animations/`): `a1` monthly hospital travel time; `a2` sub-counties by road; `a3` sub-counties on foot.

## Caveats

- **OSM completeness varies.** Most roads have no `surface` tag, so class-based defaults decide wet-day speeds. Treating untagged secondary and tertiary roads as earth is the variant that most changes district rankings (Spearman 0.90).
- **The facility list dates from about 2018** and excludes private for-profit facilities. The relocations need a manual check.
- **Refugee sites in OSM are incomplete.** Settlement boundaries from UNHCR would allow a full breakdown.
- **Ferries are not modelled.** Kalangala and Buvuma have population with no road link, counted as beyond every threshold.
- **Northern rainfall is uncertain.** CHIRPS and TAMSAT disagree on long-term change there (see the construction-delay paper). The seasonal cycle used here is less affected than the trend.
