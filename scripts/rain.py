"""Rainfall settings and loader (shared with the companion paper "Shifting Seasons, Slipping
Schedules", which defines the same thresholds). CHIRPS files are in ../data/chirps_uganda/,
made by 00_download_chirps.py."""
import glob, os
import xarray as xr

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")

EARTHWORKS_MM = 10.0      # a wet day: rainfall at or above this
DRYING_MM = 25.0          # ...and the next day also counts as wet at or above this
EARLY = (1981, 2000)
LATE = (2006, 2025)


def load_precip(dataset="chirps"):
    """Daily CHIRPS rainfall for Uganda (0.25 deg), 1981 onwards."""
    files = sorted(glob.glob(os.path.join(ROOT, "data", f"{dataset}_uganda", "*.nc")))
    pr = xr.concat([xr.open_dataset(f).precip.load() for f in files], dim="time")
    return pr.where(pr >= 0)  # CHIRPS uses -9999 for missing
