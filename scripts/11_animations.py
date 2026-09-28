"""Animated maps through the year (../figures/animations/), one frame per month.

  a1_hospital_monthly.gif         1 km travel time to the nearest hospital (motorised)
  a2_subcounty_hospital.gif       sub-counties: share of people > 1 h from a hospital
  a3_subcounty_walking_any.gif    sub-counties: share > 1 h on foot from any facility

Every frame has a title with the month and the national figure, a key, a scale bar
and a north arrow.
"""
import os
import numpy as np
import geopandas as gpd
import rasterio
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation, PillowWriter

import model
import cartography as C
from zonal import Zones

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
OUT = os.path.join(HERE, "..", "outputs")
FIG = os.path.join(HERE, "..", "figures", "animations")
os.makedirs(FIG, exist_ok=True)
C.setup()
FPS = 1.2

grid = model.Grid()
pop = grid.pop
EXT = [grid.cols_lon[0] - 0.02, grid.cols_lon[-1] + 0.02, grid.rows_lat[-1] - 0.02, grid.rows_lat[0] + 0.02]
IMG_EXT = [grid.cols_lon[0], grid.cols_lon[-1], grid.rows_lat[-1], grid.rows_lat[0]]
districts = gpd.read_file(os.path.join(DATA, "uga_districts.geojson")).to_crs(4326)
subs = gpd.read_file(os.path.join(DATA, "uga_subcounties.geojson")).to_crs(4326)
land_poly = C.land_polygon(grid)
districts = C.clip_to_land(districts, land_poly)
subs = C.clip_to_land(subs, land_poly)


def read(run, slug):
    with rasterio.open(os.path.join(OUT, run, f"travel_time_{slug}.tif")) as src:
        return src.read()


def month_title(fig, heading, m, value_text):
    t1 = fig.text(0.02, 0.965, heading, fontsize=12, color=C.INK, ha="left", va="top")
    t2 = fig.text(0.02, 0.925, "", fontsize=20, color=C.BLUES[3], ha="left", va="top", fontweight="bold")
    t3 = fig.text(0.02, 0.875, "", fontsize=9.5, color=C.INK2, ha="left", va="top")
    return t1, t2, t3


# --- a1: raster --------------------------------------------------------------------------------
H = [0, 0.25, 0.5, 1, 1.5, 2, 3, 1e9]
H_LAB = ["< 15 min", "15–30 min", "30–60 min", "1–1.5 h", "1.5–2 h", "2–3 h", "> 3 h"]
h_cmap, h_norm = C.scale(H, C.BLUES)
hosp = read("", "hospital")
fig, ax = plt.subplots(figsize=(7.2, 8))
fig.subplots_adjust(top=0.84, bottom=0.04, left=0.02, right=0.86)
C.frame(ax, EXT)
im = ax.imshow(np.ma.masked_invalid(np.where(grid.land, hosp[2], np.nan)), cmap=h_cmap, norm=h_norm,
               extent=IMG_EXT, interpolation="nearest", zorder=1)
districts.boundary.plot(ax=ax, color="white", linewidth=0.2, zorder=2)
C.furniture(ax)
C.key(fig, ax, h_cmap, h_norm, H, "travel time to the nearest hospital", H_LAB)
_, big, small = month_title(fig, "Travel time to the nearest hospital through the year", 1, "")
fig.text(0.02, 0.01, "Motorised; CHIRPS 2006–2025 wet-day frequency; OSM roads; official hospitals.",
         fontsize=7, color=C.INK2)


def frame_a1(m):
    im.set_data(np.ma.masked_invalid(np.where(grid.land, hosp[m + 2], np.nan)))
    big.set_text(C.MONTH_NAMES[m])
    small.set_text(f"{100 * grid.pop_stats(hosp[m + 2])['share_over_1h']:.1f}% of Ugandans more than 1 hour "
                   f"from a hospital\n(dry day: {100 * grid.pop_stats(hosp[0])['share_over_1h']:.1f}%)")
    return im, big, small


FuncAnimation(fig, frame_a1, frames=12).save(os.path.join(FIG, "a1_hospital_monthly.gif"),
                                             writer=PillowWriter(fps=FPS), dpi=110)
plt.close(fig)

# --- a2, a3: sub-county choropleths ---------------------------------------------------------------
S = [0, 0.05, 0.1, 0.25, 0.5, 0.75, 0.9, 1.0001]
S_LAB = ["< 5%", "5–10%", "10–25%", "25–50%", "50–75%", "75–90%", "> 90%"]
s_cmap, s_norm = C.scale(S, C.BLUES)
Z = Zones(grid, subs)
P = Z.total(pop)


def subcounty_anim(stack, hours, heading, what, fname, note):
    shares = Z.monthly(stack, lambda b: Z.share_beyond(b, hours, pop))
    dry = Z.share_beyond(stack[0], hours, pop)
    fig, ax = plt.subplots(figsize=(7.2, 8))
    fig.subplots_adjust(top=0.84, bottom=0.04, left=0.02, right=0.86)
    C.frame(ax, EXT)
    land_poly.plot(ax=ax, color=C.LAND, zorder=0)
    g = subs.assign(v=shares[0])
    g.plot(ax=ax, column="v", cmap=s_cmap, norm=s_norm, edgecolor="white", linewidth=0.08,
           missing_kwds=dict(color=C.LAND), zorder=1)
    coll = ax.collections[-1]
    districts.boundary.plot(ax=ax, color=C.INK2, linewidth=0.15, zorder=2)
    C.furniture(ax)
    C.key(fig, ax, s_cmap, s_norm, S, what, S_LAB)
    _, big, small = month_title(fig, heading, 1, "")
    fig.text(0.02, 0.01, note, fontsize=7, color=C.INK2)
    # geopandas draws polygons in row order, one path per polygon part
    parts = np.repeat(np.arange(len(subs)), [len(getattr(geom, "geoms", [geom])) for geom in subs.geometry])

    def frame(m):
        v = shares[m]
        cols = s_cmap(s_norm(np.nan_to_num(v, nan=0)))
        cols[~np.isfinite(v)] = matplotlib.colors.to_rgba(C.LAND)
        coll.set_facecolor(cols[parts] if len(parts) == len(coll.get_paths()) else cols)
        nat = np.nansum(v * P) / P.sum()
        big.set_text(C.MONTH_NAMES[m])
        small.set_text(f"{100 * nat:.1f}% of Ugandans {note_short} (dry day: "
                       f"{100 * np.nansum(dry * P) / P.sum():.1f}%)")
        return coll, big, small

    note_short = what.split("share of people ")[-1]
    FuncAnimation(fig, frame, frames=12).save(os.path.join(FIG, fname), writer=PillowWriter(fps=FPS), dpi=110)
    plt.close(fig)


subcounty_anim(hosp, 1, "Sub-counties: people more than 1 hour from a hospital",
               "share of people more than 1 h from a hospital", "a2_subcounty_hospital.gif",
               "Motorised; 1,520 sub-counties; CHIRPS 2006–2025.")
subcounty_anim(read("walking", "any_facility"), 1,
               "Sub-counties: more than 1 hour on foot from any health facility",
               "share of people more than 1 h on foot from any facility", "a3_subcounty_walking_any.gif",
               "Walking only; nearest facility of any level; CHIRPS 2006–2025.")
print("animations written to", os.path.abspath(FIG))
