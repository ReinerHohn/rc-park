#!/usr/bin/env python3
"""aufloesung_karte.py - wo reichen die vorhandenen Fotos aufloesungsmaessig, wo fehlen bessere Ansichten? (Auswahl fuer gezielte Nachbeschaffung je Ausschnitt)
Je Oberflaechenpunkt des Netzes: Zahl der Kameras, die ihn vorderseitig im Bild sehen (Normale zur Kamera >0,3, im Bild, Tiefe 3-120 m; OHNE Verdeckungstest -> obere Schranke)
und beste Bodenaufloesung GSD = Tiefe/f (m/px, auf Bildebene senkrecht; nicht korrigiert fuer Schraegsicht) + schlechteste Blickwinkelvielfalt (Spreizung der Blickrichtungen in Grad).
Ausgabe: JSON + Tabelle nach Hoehenband x Richtung (Himmelsrichtung der Normale). Rahmen der K-Dateien (rahmen_verschiebung auf das Netz).
  venv-seg/bin/python -I tools/aufloesung_karte.py modelle/<obj>/objekt.json --stl netz.stl --aus x.json [--n 400000]"""
import os, sys, json, glob, argparse, numpy as np, cv2, trimesh
ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--stl", required=True); ap.add_argument("--aus", required=True); ap.add_argument("--n", type=int, default=400000)
a = ap.parse_args(); od = os.path.dirname(os.path.abspath(a.objekt)); obj = json.load(open(a.objekt))
m = trimesh.load(a.stl, force="mesh"); m.apply_scale(obj.get("stl_massstab", 87) / 1000.0)
P, fi = trimesh.sample.sample_surface(m, a.n, seed=0); P = np.asarray(P); N = m.face_normals[fi]
cams = []
for p in sorted(glob.glob(os.path.join(od, "messprotokoll", "K-*.json"))):
    k = json.load(open(p)).get("kamera", {})
    if "rvec" not in k or "bild" not in k: continue
    R = cv2.Rodrigues(np.array(k["rvec"], float))[0]; t = np.array(k["t"], float); rv = np.array(k.get("rahmen_verschiebung", [0, 0, 0]), float); cams.append((os.path.basename(p)[2:-5], R, t, rv, k["f_px"], k.get("cx", k["bild"][0] / 2), k.get("cy", k["bild"][1] / 2), k["bild"]))
# STL -> Kamerarahmen: Netz traegt rahmen_verschiebung der Kameras (alle gleich); je Kamera addieren
nviews = np.zeros(len(P), int); best = np.full(len(P), np.inf); az_min = np.full(len(P), 1e9); az_max = np.full(len(P), -1e9); bestcam = np.empty(len(P), dtype=object)
for nr, R, t, rv, f, cx, cy, (W, H) in cams:
    X = P + rv; Xc = X @ R.T + t; z = Xc[:, 2]; u = f * Xc[:, 0] / np.where(z > 0.1, z, 1) + cx; v = f * Xc[:, 1] / np.where(z > 0.1, z, 1) + cy
    C = -R.T @ t; d = C - X; dn = np.linalg.norm(d, axis=1); cosw = (N * d).sum(1) / np.maximum(dn, 1e-9)
    ok = (z > 3) & (z < 120) & (u > 30) & (u < W - 30) & (v > 30) & (v < H - 30) & (cosw > 0.3)
    g = z / f; nviews += ok; better = ok & (g < best); best[better] = g[better]; bestcam[better] = nr
    az = np.degrees(np.arctan2(d[:, 1], d[:, 0])); az_min[ok] = np.minimum(az_min[ok], az[ok]); az_max[ok] = np.maximum(az_max[ok], az[ok])
spread = np.where(nviews > 1, az_max - az_min, 0); best[~np.isfinite(best)] = np.nan
zb = P[:, 2] + 0.0; rich = (np.degrees(np.arctan2(N[:, 1], N[:, 0])) + 360) % 360
rows = []
bands = [(0, 4), (4, 8), (8, 12), (12, 16), (16, 22)]; sect = [("N", 315, 45), ("O", 45, 135), ("S", 135, 225), ("W", 225, 315)]
print(f"{'Hoehe m':>8s} {'Richtung':>8s} {'Flaeche%':>8s} {'Pkt mit 0 Kam':>13s} {'median Kam':>10s} {'beste GSD mm/px (med)':>22s} {'p90 GSD':>8s}")
for z0, z1 in bands:
    for nm, a0, a1 in sect:
        k = (zb >= z0) & (zb < z1) & ((rich >= a0) & (rich < a1) if a0 < a1 else (rich >= a0) | (rich < a1)) & (N[:, 2] < 0.7 if z0 < 14 else np.ones(len(P), bool))
        if k.sum() < 200: continue
        g = best[k] * 1000; r = dict(z0=z0, z1=z1, richtung=nm, anteil_flaeche=round(k.sum() / len(P) * 100, 1), ohne_kamera=round(float((nviews[k] == 0).mean()), 3), kam_median=float(np.median(nviews[k])), gsd_mm_median=round(float(np.nanmedian(g)), 1) if np.isfinite(g).any() else None, gsd_mm_p90=round(float(np.nanpercentile(g, 90)), 1) if np.isfinite(g).any() else None, spreizung_med_grad=round(float(np.median(spread[k])), 0))
        rows.append(r); print(f"{z0:3d}-{z1:<4d} {nm:>8s} {r['anteil_flaeche']:8.1f} {r['ohne_kamera']:13.2f} {r['kam_median']:10.0f} {str(r['gsd_mm_median']):>22s} {str(r['gsd_mm_p90']):>8s}  Spreizung {r['spreizung_med_grad']:.0f}")
json.dump(dict(zeilen=rows, kameras=len(cams), n=a.n), open(a.aus, "w"), indent=1)
E_ = 0
