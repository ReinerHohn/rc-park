#!/usr/bin/env python3
"""dom_full_prep.py — baut dom025_full.npy EXAKT auf dem Raster von dgm025_full.npy (4000x4000,
0.25 m), aus den georeferenzierten DOM1-Kacheln (bilinear resampled). Damit kann terrain_eggcrate
das DOM mit DEMSELBEN --r0/r1/c0/c1-Fenster nutzen wie das DGM (Galerie-Dach ins Relief).

Raster (verifiziert, Diff 0.000 m zur DGM-Kachel): E=426000+c*0.25, N=5310000-r*0.25.
"""
import numpy as np, glob, rasterio
from rasterio.merge import merge
from rasterio.warp import reproject, Resampling
from rasterio.transform import from_origin

N = 4000; RES = 0.25
E0, Ntop = 426000.0, 5310000.0
dst_tr = from_origin(E0, Ntop, RES, RES)        # top-left, Nord oben

doms = glob.glob("daten/hoellental/eo/dom1/*/dom1_*_bw*.tif")
srcs = [rasterio.open(f) for f in doms]
mos, mos_tr = merge(srcs)                        # DOM-Mosaik
dst = np.full((N, N), np.nan, np.float32)
reproject(source=mos[0], destination=dst,
          src_transform=mos_tr, src_crs=srcs[0].crs,
          dst_transform=dst_tr, dst_crs=srcs[0].crs,
          resampling=Resampling.bilinear)
dst = np.where(dst < -1000, np.nan, dst)
np.save("daten/hoellental/dom025_full.npy", dst)
# Gegencheck gegen DGM: DOM >= DGM fast ueberall (Oberflaeche >= Grund)
dgm = np.load("daten/hoellental/dgm025_full.npy")
nd = dst - dgm
print("dom025_full.npy %s  Hoehe %.0f..%.0f  nDOM(DOM-DGM) median %.2f  >2m: %.1f%%"
      % (dst.shape, np.nanmin(dst), np.nanmax(dst), np.nanmedian(nd), 100*np.nanmean(nd > 2)))
