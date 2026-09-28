"""Population-weighted zonal statistics on the 1 km grid (sub-counties, districts)."""
import numpy as np


class Zones:
    def __init__(self, grid, gdf):
        self.id = grid.zones(gdf).ravel()
        self.n = len(gdf) + 1

    def _sum(self, v):
        return np.bincount(self.id, weights=np.asarray(v, float).ravel(), minlength=self.n)[1:]

    def total(self, w):
        return self._sum(w)

    def share_beyond(self, tt, hours, w):
        """Share of weight w more than `hours` away (unreachable counts as beyond)."""
        tot = self._sum(w)
        s = self._sum(w * ~(tt <= hours))
        return np.where(tot > 0, s / np.where(tot > 0, tot, 1), np.nan)

    def mean(self, v, w):
        ok = np.isfinite(v)
        tot = self._sum(w * ok)
        s = self._sum(np.where(ok, v * w, 0))
        return np.where(tot > 0, s / np.where(tot > 0, tot, 1), np.nan)

    def monthly(self, stack, fn):
        """fn(band) for months 1-12 of a 14-band travel-time stack -> (12, zones)."""
        return np.stack([fn(stack[m + 1]) for m in range(1, 13)])
