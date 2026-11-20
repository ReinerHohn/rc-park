#!/usr/bin/env python3
"""modell_neben_foto.py <objekt.json> FOTO AUS.jpg [--stl a.stl,b.stl] [--box x0 y0 x1 y1] [--breite 900] - schattiertes Modell aus der Fotokamera NEBEN dem Foto.

Pflichtbild nach jedem Bau (CLAUDE.md: "Teil neben Referenzfoto ansehen"). Kamera = messprotokoll/K-<FOTO>.json (k1 wird im Foto entzerrt), STL im Rahmen
(zentrierung 'achse', 1:87). --box = Bildausschnitt in Originalpixeln. Entstanden 15.11.2026 (Nachbarhaus Schwabentor), nutzt den GPU-Renderkern.
  /media/oem/scan/venv-seg/bin/python -I tools/modell_neben_foto.py modelle/schwab_nachbar/objekt.json eigen__IMG_20261106_113033 /tmp/x.jpg --box 600 500 2100 3400
Ausgabe: AUS.jpg (links Foto, rechts Render; Standard-STL modelle/stl/<objektordner>_1-87.stl). Braucht messprotokoll/K-<FOTO>.json
(tools/kameras_aus_buendel.py). Automatisch je objekt.json "neben_fotos" -> audit/neben_<foto>.jpg. Umgebung: cv2/trimesh -> venv-seg (`tools/py ...`).
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
x0, y0, x1, y1 = [int(v) for v in a[a.index("--box") + 1:a.index("--box") + 5]] if "--box" in a else (0, 0, W, H)
x0, y0, x1, y1 = max(x0, 0), max(y0, 0), min(x1, W), min(y1, H)        # Ausschnitt auf das Bild begrenzen (sonst passten Foto- und Renderhaelfte nicht zusammen)
ms = [trimesh.load(s_) for s_ in stls]; mm = trimesh.util.concatenate(ms) if len(ms) > 1 else ms[0]; mm.apply_scale(87.0 / 1000.0)
res = rk.dreiecke_rastern(mm, R, t, f, cx - x0, cy - y0, x1 - x0, y1 - y0); fid = np.asarray(res[1]); tr = fid >= 0          # Dreiecks-Raster (GPU) nur im Ausschnitt - der Punkt-Renderer rauschte zu stark fuer Steine/Details
li = R.T @ np.array([-0.45, -0.75, -1.0]); li = li / np.linalg.norm(li)      # Licht von der Kamera her, schraeg von links oben
r = np.full((y1 - y0, x1 - x0), 235, np.uint8); r[tr] = (60 + 190 * np.clip(mm.face_normals[fid[tr]] @ li, 0, 1)).astype(np.uint8); r = cv2.cvtColor(r, cv2.COLOR_GRAY2BGR)
im = im[y0:y1, x0:x1]; x0 = y0 = 0; y1, x1 = r.shape[:2]
o = np.hstack([im[y0:y1, x0:x1], r[y0:y1, x0:x1].astype(np.uint8)]); B = int(a[a.index("--breite") + 1]) if "--breite" in a else 900
s = 2 * B / o.shape[1]; cv2.imwrite(a[3], cv2.resize(o, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)); print("->", a[3])
