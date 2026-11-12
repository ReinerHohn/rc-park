#!/usr/bin/env python3
"""rundum_kanten.py - Modell als KANTENBILD aus mehreren Blickrichtungen um ein Objekt (Kontaktbogen), damit Koerper (Erker, Tuerme) nie nur von vorn bewertet werden.
Anlass 12./13.11.: Der Erker war nur von vorn gegen Fotos geprueft; fehlende Achteckseiten/Fenster fielen nie auf (Nutzer sah sie im Kanten-Viewer).
Aufruf: /media/oem/scan/venv-seg/bin/python -W ignore -I tools/rundum_kanten.py modelle/<objekt>/objekt.json --u 15.52 --n 13.3 --z 11.2 [--abstand 8] [--hoehe 11] [--winkel -90,-60,-30,0,30,60,90] [--aus datei.jpg]
Koordinaten (u, n, z) im Fassadenrahmen: u laengs, n zur Strasse (grosse n = Strasse); Winkel 0 = Blick von der Strasse (n+) auf das Objekt, +-90 = von der Seite (Gasse).
Kanten = Knick zwischen Dreiecksnormalen > 25 Grad oder Tiefensprung > 0,25 m. Pro Ansicht Titel mit Winkel. Reine Geometrie."""
import sys, json, math, numpy as np, cv2, trimesh, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import render_kern as RK
a = sys.argv[1:]
if not a or a[0].startswith("-"): sys.exit(__doc__)
opt = lambda n, d: a[a.index(n) + 1] if n in a else d
obj = json.load(open(a[0])); root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(a[0]))))
u0, n0, z0 = float(opt("--u", 0)), float(opt("--n", 0)), float(opt("--z", 0)); d = float(opt("--abstand", 8)); h = float(opt("--hoehe", z0))
winkel = [float(v) for v in opt("--winkel", "-90,-60,-30,0,30,60,90").split(",")]
nx, ny = float(opt("--nx", 0.3338)), float(opt("--ny", 0.9426))
W = lambda u, n, z: np.array([u * ny + n * nx, -u * nx + n * ny, z])
m = trimesh.load(os.path.join(root, obj["stl"])); m.apply_scale(obj.get("stl_massstab", 87) / 1000.0)
# Modell liegt im Rahmen der K-Protokolle (Verschiebung 0 fuer Zusatzkameras); Standard hier: ohne Verschiebung
T = W(u0, n0, z0); bilder = []; Wd, Hd, fp = 600, 800, float(opt("--brennweite", 850))
for w in winkel:
    th = math.radians(w); C = W(u0 + d * math.sin(th), n0 + d * math.cos(th), h)
    f = T - C; f /= np.linalg.norm(f); r = np.cross(f, [0, 0, 1.0]); r /= np.linalg.norm(r); dn = np.cross(f, r)
    R = np.array([r, dn, f]); t = -R @ C
    res = RK.dreiecke_rastern(m, R, t, fp, Wd / 2, Hd / 2, Wd, Hd); depth, fid = np.asarray(res[0], np.float32), np.asarray(res[1]); tr = fid >= 0
    N = np.asarray(m.face_normals); nn = np.zeros((Hd, Wd, 3), np.float32); nn[tr] = N[fid[tr]]
    dp = np.where(tr, depth, 1e3).astype(np.float32); kan = np.zeros((Hd, Wd), bool)
    for dy, dx in ((0, 1), (1, 0)):
        s1, s2 = (slice(None), slice(0, -1)) if dx else (slice(0, -1), slice(None)); t1, t2 = (slice(None), slice(1, None)) if dx else (slice(1, None), slice(None))
        cosw = (nn[s1, s2] * nn[t1, t2]).sum(-1); dd = np.abs(dp[s1, s2] - dp[t1, t2])
        e = (cosw < math.cos(math.radians(25))) | (dd > 0.25) | (tr[s1, s2] != tr[t1, t2]); kan[s1, s2] |= e
    img = np.full((Hd, Wd, 3), 255, np.uint8); img[tr] = (235, 235, 235); img[kan] = (60, 30, 40)
    cv2.putText(img, f"{w:+.0f} Grad", (10, 30), 0, 0.9, (0, 0, 200), 2); bilder.append(img)
cols = min(4, len(bilder)); rows = (len(bilder) + cols - 1) // cols
bogen = np.full((rows * Hd, cols * Wd, 3), 255, np.uint8)
for i, b in enumerate(bilder): bogen[(i // cols) * Hd:(i // cols + 1) * Hd, (i % cols) * Wd:(i % cols + 1) * Wd] = b
cv2.imwrite(opt("--aus", "rundum.jpg"), cv2.resize(bogen, None, fx=0.6, fy=0.6, interpolation=cv2.INTER_AREA), [cv2.IMWRITE_JPEG_QUALITY, 90]); print("->", opt("--aus", "rundum.jpg"))
