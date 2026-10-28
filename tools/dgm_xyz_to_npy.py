#!/usr/bin/env python3
"""dgm_xyz_to_npy.py — LGL-DGM1 XYZ-Subkacheln -> ein north-up Höhenfeld (.npy).

LGL liefert DGM1 als 1 km-Subkacheln im ASCII-XYZ-Format (E N Z, 1 m-Raster).
Dieses Tool stitcht alle *.xyz eines Ordners zu EINEM Array + Origin, passend
für tools/bauwerk_szene.py / validate_modell.py (A[r,c], r=0 = Nord).

  python3 tools/dgm_xyz_to_npy.py daten/ravenna/dgm1_32_429_5306_2_bw \\
      --out daten/ravenna/ravenna_dgm1.npy
"""
import argparse, glob, os, sys, numpy as np

ap = argparse.ArgumentParser()
ap.add_argument("folder"); ap.add_argument("--out", required=True)
a = ap.parse_args()

files = sorted(glob.glob(os.path.join(a.folder, "*.xyz")))
if not files:
    sys.exit(f"keine .xyz in {a.folder}")
try:
    import pandas as pd
    def load(f): return pd.read_csv(f, sep=r"\s+", header=None).values
except ImportError:
    def load(f): return np.loadtxt(f)

pts = np.vstack([load(f) for f in files])
E, N, Z = pts[:, 0], pts[:, 1], pts[:, 2]
E0, N0 = int(np.floor(E.min())), int(np.floor(N.min()))
nx = int(round(E.max() - E.min())) + 1
ny = int(round(N.max() - N.min())) + 1
A = np.full((ny, nx), np.nan, float)
c = np.round(E - 0.5 - E0).astype(int)
rr = np.round(N - 0.5 - N0).astype(int)          # 0 = Süd
A[ny - 1 - rr, c] = Z                              # r=0 = Nord
np.save(a.out, A)
np.save(a.out.replace(".npy", "_origin.npy"), np.array([E0, N0]))
print(f"{len(files)} Kacheln -> {a.out}  shape {A.shape}  "
      f"origin E{E0} N{N0}  Höhe {np.nanmin(Z):.0f}..{np.nanmax(Z):.0f} m  "
      f"NaN {100*np.mean(np.isnan(A)):.1f}%")
