#!/usr/bin/env python3
"""knoten_pruefen.py - 3D-Kandidatenpunkte (u n z im Fassadenrahmen) in mehrere Kameras projizieren und die Bildausschnitte als Kontaktbogen zeigen (Gegenprobe der Zuordnung).
Aufruf: /media/oem/scan/venv-seg/bin/python -W ignore -I tools/knoten_pruefen.py modelle/<objekt>/objekt.json --kams K-n11_06,K-6130,K-e04,K-6124,K-i08 --punkte "name:u,n,z;name:u,n,z" --aus FILE.jpg [--r 70] [--nx 0.3338 --ny 0.9426]
Je Zeile ein Kandidat, je Spalte eine Kamera; Fadenkreuz in der Bildmitte = projizierter Punkt. Ein echter Knoten liegt in ALLEN Kameras auf derselben Rippenkreuzung. Reine Geometrie + Bildausschnitt.
Anlass 13.11.2026: Handpunkt-Zuordnung zweier Fotos bleibt auch bei 70 Grad Schnittwinkel mehrdeutig (regelmaessiges Rautennetz)."""
import sys, os, json, glob, numpy as np, cv2
a = sys.argv[1:]
if len(a) < 5: sys.exit(__doc__)
opt = lambda n, d: a[a.index(n) + 1] if n in a else d
od = os.path.dirname(os.path.abspath(a[0])); root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(a[0])))); obj = json.load(open(a[0]))
nx, ny, r = float(opt("--nx", 0.3338)), float(opt("--ny", 0.9426)), int(opt("--r", 70)); kams = opt("--kams", "").split(","); pts = [(s.split(":")[0], [float(v) for v in s.split(":")[1].split(",")]) for s in opt("--punkte", "").split(";") if s]
def cam(kid):
    k = json.load(open(os.path.join(od, "messprotokoll", kid + ".json")))["kamera"]; R, _ = cv2.Rodrigues(np.array(k["rvec"], float)); sh = np.asarray(k.get("rahmen_verschiebung", [0, 0, 0]), float)
    return dict(R=R, t=np.array(k["t"], float), sh=sh, f=k["f_px"], cx=k["cx"], cy=k["cy"], k1=float(k.get("k1") or 0), f_px=k["f_px"])
ims, Ks = {}, {}
for kid in kams: Ks[kid] = cam(kid); ims[kid] = cv2.imread(glob.glob(os.path.join(root, obj["fotos_dir"], kid[2:] + "_*"))[0])
rows = []
for nm, (u, n, z) in pts:
    P = np.array([u * ny + n * nx, -u * nx + n * ny, z]); cells = []
    for kid in kams:
        K = Ks[kid]; x = K["R"] @ (P + K["sh"]) + K["t"]; c = np.full((2 * r, 2 * r, 3), 40, np.uint8)
        if x[2] > 0:
            xn, yn = x[0] / x[2], x[1] / x[2]; r2 = xn * xn + yn * yn; px, py = int(K["f"] * xn * (1 + K["k1"] * r2) + K["cx"]), int(K["f"] * yn * (1 + K["k1"] * r2) + K["cy"]); scale = K["f"] / x[2]
            R2 = int(r * max(1.0, scale / 300.0)); im = ims[kid]; x0, y0 = px - R2, py - R2
            if 0 <= x0 and 0 <= y0 and x0 + 2 * R2 <= im.shape[1] and y0 + 2 * R2 <= im.shape[0]:
                c = cv2.resize(im[y0:y0 + 2 * R2, x0:x0 + 2 * R2], (2 * r * 3, 2 * r * 3)); m = c.shape[0] // 2; cv2.drawMarker(c, (m, m), (255, 0, 255), cv2.MARKER_CROSS, 40, 2)
            else: c = cv2.resize(c, (2 * r * 3, 2 * r * 3))
        else: c = cv2.resize(c, (2 * r * 3, 2 * r * 3))
        cv2.putText(c, kid[2:], (6, 22), 0, 0.7, (0, 255, 255), 2); cells.append(c)
    row = np.hstack(cells); cv2.putText(row, f"{nm} u{u} n{n} z{z}", (6, row.shape[0] - 10), 0, 0.8, (255, 255, 255), 2); rows.append(row)
cv2.imwrite(opt("--aus", "knoten.jpg"), np.vstack(rows), [cv2.IMWRITE_JPEG_QUALITY, 85]); print("->", opt("--aus", "knoten.jpg"))
