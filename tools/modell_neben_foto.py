#!/usr/bin/env python3
"""modell_neben_foto.py <objekt.json> FOTO AUS.jpg [--stl a.stl,b.stl] [--box x0 y0 x1 y1] [--breite 900] - schattiertes Modell aus der Fotokamera NEBEN dem Foto.

Pflichtbild nach jedem Bau (CLAUDE.md: "Teil neben Referenzfoto ansehen"). Kamera = messprotokoll/K-<FOTO>.json (k1 wird im Foto entzerrt), STL im Rahmen
(zentrierung 'achse', 1:87). --box = Bildausschnitt in Originalpixeln. Entstanden 15.11.2026 (Nachbarhaus Schwabentor), nutzt den GPU-Renderkern.
  /media/oem/scan/venv-seg/bin/python -I tools/modell_neben_foto.py modelle/schwab_nachbar/objekt.json eigen__IMG_20261106_113033 /tmp/x.jpg --box 600 500 2100 3400
"""
import sys, os, json, glob, cv2, numpy as np, trimesh
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import render_kern as rk
a = sys.argv; objp = os.path.abspath(a[1]); od = os.path.dirname(objp); root = os.path.dirname(os.path.dirname(od)); obj = json.load(open(objp)); foto = a[2]
stls = a[a.index("--stl") + 1].split(",") if "--stl" in a else [os.path.join(root, "modelle", "stl", os.path.basename(od) + "_1-87.stl")]
K = json.load(open(os.path.join(od, "messprotokoll", "K-" + foto + ".json")))["kamera"]; R = cv2.Rodrigues(np.array(K["rvec"]))[0]; t = np.array(K["t"]); f, cx, cy = K["f_px"], K["cx"], K["cy"]
im = cv2.imread((glob.glob(os.path.join(root, obj["fotos_dir"], foto + ".*")) or glob.glob(os.path.join(root, obj["fotos_dir"], foto + "_*")))[0]); H, W = im.shape[:2]
k1 = float(K.get("k1") or 0.0)
if k1: im = cv2.undistort(im, np.array([[f, 0, cx], [0, f, cy], [0, 0, 1.0]]), np.array([k1, 0, 0, 0.0]))
P = []; N = []
for s in stls:
    m = trimesh.load(s); p, fi = trimesh.sample.sample_surface(m, 6000000); P.append(p * 87.0 / 1000.0); N.append(m.face_normals[fi])
P = np.vstack(P); N = np.vstack(N)
x0, y0, x1, y1 = [int(v) for v in a[a.index("--box") + 1:a.index("--box") + 5]] if "--box" in a else (0, 0, W, H)
q = 3                                                                # Punkt-Renderer: mit 1/3 Aufloesung rechnen, sonst Loecher zwischen den Abtastpunkten
r = rk.schattiert(P, N, R, t, f / q, cx / q, cy / q, W // q, H // q)[0]; r = cv2.cvtColor(cv2.resize(np.asarray(r).astype(np.uint8), (W, H), interpolation=cv2.INTER_LINEAR), cv2.COLOR_GRAY2BGR)
o = np.hstack([im[y0:y1, x0:x1], r[y0:y1, x0:x1].astype(np.uint8)]); B = int(a[a.index("--breite") + 1]) if "--breite" in a else 900
s = 2 * B / o.shape[1]; cv2.imwrite(a[3], cv2.resize(o, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)); print("->", a[3])
