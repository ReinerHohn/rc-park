#!/usr/bin/env python3
"""seiten_anhang_pruefen_1119.py <modell_mit_anhang> <seitenmodell_vorher> <kontrolle.txt> [--aus json] - VERSUCH 19.11.2026: welche an ein Seitenmodell angehaengten Bilder
gehoeren wirklich dorthin? Mass je Bild: Anteil der Bildflaeche (6x6-Raster, Zellen mit >= 20 Merkmalen), in der Merkmale Modellpunkte tragen (>= 3 je Zelle), und Anteil der
Merkmale mit Modellpunkt. Gruppen: 'vorher' (Seitenmodell selbst = richtig), 'kontrolle' (Bilder der ANDEREN Seite, absichtlich mit angehaengt = falsch), 'kandidat'."""
import sys, json, argparse, collections
import numpy as np, pycolmap
ap = argparse.ArgumentParser(); ap.add_argument("modell"); ap.add_argument("vorher"); ap.add_argument("kontrolle"); ap.add_argument("--aus"); a = ap.parse_args()
r = pycolmap.Reconstruction(a.modell); alt = {im.name for im in pycolmap.Reconstruction(a.vorher).images.values() if im.has_pose}; ko = set(l.strip() for l in open(a.kontrolle) if l.strip())
alt_p = set(pycolmap.Reconstruction(a.vorher).points3D.keys()); E = {}
for im in r.images.values():
    if not im.has_pose: continue
    cam = r.cameras[im.camera_id]; xy = np.array([p.xy for p in im.points2D]); has = np.array([p.has_point3D() for p in im.points2D])
    if len(xy) < 100: continue
    z = np.clip((xy[:, 1] / cam.height * 6).astype(int), 0, 5) * 6 + np.clip((xy[:, 0] / cam.width * 6).astype(int), 0, 5)
    alle = np.bincount(z, minlength=36); mit = np.bincount(z[has], minlength=36); voll = alle >= 20
    E[im.name] = dict(gruppe="vorher" if im.name in alt else ("kontrolle" if im.name in ko else "kandidat"), flaeche=float(((mit >= 3) & voll).sum() / max(1, voll.sum())), anteil=float(has.mean()), punkte=int(has.sum()))
print("Bilder im Modell", len(E), collections.Counter(v["gruppe"] for v in E.values()))
for g in ("vorher", "kontrolle", "kandidat"):
    v = [x for x in E.values() if x["gruppe"] == g]
    if v: print(f"  {g:10s} {len(v):4d}: Bildflaeche mit Modellpunkten p10/25/50/75/90 {np.percentile([x['flaeche'] for x in v], [10, 25, 50, 75, 90]).round(2)} | Merkmale mit Punkt p10/50/90 {np.percentile([x['anteil'] for x in v], [10, 50, 90]).round(3)} | Punkte p50 {int(np.median([x['punkte'] for x in v]))}")
if a.aus: json.dump(E, open(a.aus, "w"))
