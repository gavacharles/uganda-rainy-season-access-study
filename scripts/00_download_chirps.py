"""Download CHIRPS v2.0 daily rainfall (0.25 deg), clip to Uganda, save one file per year.

Global yearly files (~83 MB) are streamed to a temp file, clipped, and deleted,
so disk use stays small. Re-running skips years already downloaded.
"""
import os, sys, subprocess, tempfile
import xarray as xr

BASE = "https://data.chc.ucsb.edu/products/CHIRPS-2.0/global_daily/netcdf/p25"
OUT = os.path.join(os.path.dirname(__file__), "..", "data", "chirps_uganda")
# Uganda bounding box with a small margin
LON = slice(29.4, 35.1)
LAT = slice(-1.6, 4.4)

years = range(int(sys.argv[1]), int(sys.argv[2]) + 1)
for y in years:
    out = os.path.join(OUT, f"chirps_uganda_{y}.nc")
    if os.path.exists(out):
        continue
    with tempfile.NamedTemporaryFile(suffix=".nc", delete=False) as tmp:
        path = tmp.name
    try:
        subprocess.run(["curl", "-sSf", "--retry", "3", "-o", path,
                        f"{BASE}/chirps-v2.0.{y}.days_p25.nc"], check=True)
        with xr.open_dataset(path) as ds:
            ds.sel(longitude=LON, latitude=LAT).load().to_netcdf(out)
        print(y, "ok", flush=True)
    finally:
        os.remove(path)
