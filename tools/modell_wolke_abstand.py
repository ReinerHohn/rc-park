#!/usr/bin/env python3
"""modell_wolke_abstand.py - Gesamtmodell (STL mm, Massstab) gegen die Wolke: Median/P90 Abstand Wolkenpunkt -> Modellflaeche (Punkte < --rand m), plus Anteil > 0,3 m und die
Rueckrichtung (Modell -> Wolke, 'gestuetzt'). Zum Vergleich zweier Staende: Nur gleiche Wolke/gleiche --rand vergleichen (Regel: gleicher Schaetzer).
  /media/oem/scan/venv-seg/bin/python -I tools/modell_wolke_abstand.py a.stl [b.stl ...]"""
import sys, os, numpy as np, trimesh
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from gpu_knn import min_abstand
P = np.load("/media/oem/scan/rc-park_null/wolke_netzrahmen.npy")[:, :3].astype(np.float32)
for f in sys.argv[1:]:
    m = trimesh.load(f, process=False); m.apply_scale(0.087); Q, _ = trimesh.sample.sample_surface(m, 200000, seed=1); d = min_abstand(P, Q); r = d[d < 1.0]
    print(f"{f.split('/')[-1]:34s} Median {np.median(r):.3f}  P90 {np.percentile(r, 90):.3f}  >0,3 m {100 * (r > 0.3).mean():.1f} %  n {len(r)}  gestuetzt {100 * (min_abstand(Q, P) < 0.3).mean():.1f} %")
