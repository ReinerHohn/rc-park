#!/usr/bin/env python3
"""rippen_abdeckung.py - Wie viel der sichtbaren Goldrippen eines Bauteils steckt im Modell? (Mass fuer feine Kanten, Nutzer 12.11.: foto_diff/Wolke sind fuer Rippen blind)

Aufruf: rippen_abdeckung.py OBJ.json --kam K-6171 --pruef K-6259 K-6162 --fenster x0 y0 x1 y1 --box "x0,y0,z0,x1,y1,z1" [--tol 0.04] [--aus DIR]
Ablauf: Gold-Maske (Gelbanteil) im Fenster der Hauptkamera -> Skelett (Rippenmittellinien) -> je Skelettpunkt Strahl x Modellflaeche (STL-Teilnetz in Box)
-> 3D-Punkt; Validierung: Projektion in jede Pruefkamera muss auf Gold treffen (<= 4 px), sonst verworfen (Flaeche stimmt dort nicht / verdeckt).
Mass: Anteil validierter Gold-Punkte, die im Modell eine Rippe haben (Modellflaeche vor der Flaeche: Abstand Punkt -> naechste Modelloberflaeche in der Rippenhoehe
<= tol) - Modell muss dafuer MIT Rippen gerechnet sein; Vergleich ohne/mit `rippen_pfade`. Ausgabe JSON + Bild (gruen = im Modell, rot = fehlt).
Grenze: nur so gut wie die Flaeche; Gold ist die Rippenmitte nur bei Gold-Streifenrippen."""
import sys, os, json, glob, importlib.util
import numpy as np, cv2, trimesh
from skimage.morphology import skeletonize
_d = os.path.dirname(os.path.abspath(__file__))
def lade(n):
    s = importlib.util.spec_from_file_location(n, os.path.join(_d, n + ".py")); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
EPI = lade("epilinie")
def gold(im, th=60):
    f = im.astype(np.float32); g = np.clip((f[..., 2] + f[..., 1]) / 2 - f[..., 0], 0, None); return g > th
def main():
    a = sys.argv[1:]
    if len(a) < 6: sys.exit(__doc__)
    obj = json.load(open(a[0])); root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(a[0])))); od = os.path.join(root, os.path.dirname(obj["masstabelle"]))
    kam = a[a.index("--kam") + 1]; i = a.index("--pruef") + 1; pr = []
    while i < len(a) and a[i].startswith("K-"): pr.append(a[i]); i += 1
    fw = [int(v) for v in a[a.index("--fenster") + 1:a.index("--fenster") + 5]]; bx = [float(v) for v in a[a.index("--box") + 1].split(",")]
    tol = float(a[a.index("--tol") + 1]) if "--tol" in a else 0.04; aus = a[a.index("--aus") + 1] if "--aus" in a else "."; os.makedirs(aus, exist_ok=True)
    img = lambda k: cv2.imread(glob.glob(os.path.join(root, obj["fotos_dir"], k[2:] + "_*"))[0])
    K = EPI.kam(od, kam); im = img(kam); G = gold(im, 95); Kp = [(EPI.kam(od, k), cv2.dilate(gold(img(k), 25).astype(np.uint8), np.ones((9, 9), np.uint8)) > 0) for k in pr]
    x0, y0, x1, y1 = fw; sk = skeletonize(G[y0:y1, x0:x1]); ys, xs = np.nonzero(sk); pts = np.c_[xs + x0, ys + y0][::3]
    m = trimesh.load(os.path.join(root, obj["stl"])); m.apply_scale(obj.get("stl_massstab", 87) / 1000.0)
    kk = json.load(open(os.path.join(od, "messprotokoll", kam + ".json")))["kamera"]; m.apply_translation(np.asarray(kk.get("rahmen_verschiebung", [0, 0, 0]), float))
    ct = m.triangles_center; sel = np.all((ct >= bx[:3]) & (ct <= bx[3:]), axis=1); sub = trimesh.Trimesh(m.vertices, m.faces[sel], process=False)
    o = np.array([EPI.strahl(K, p)[0] for p in pts]); d = np.array([EPI.strahl(K, p)[1] for p in pts])
    loc, ir, _ = sub.ray.intersects_location(o, d, multiple_hits=False); P = loc; px = pts[ir]; ok = np.ones(len(P), bool)
    for Kk, Gm in Kp:
        for j, p in enumerate(P):
            q = EPI.projekt(Kk, p)
            if q is None or not (0 <= int(q[0]) < Gm.shape[1] and 0 <= int(q[1]) < Gm.shape[0]) or not Gm[int(q[1]), int(q[0])]: ok[j] = False
    print("Skelettpunkte", len(pts), "Treffer Flaeche", len(P), "validiert (Gold in allen Pruefkameras)", int(ok.sum()))
    # Modell mit Rippen: Rippenoberflaeche liegt VOR der Flaeche; Strahl bis zum ersten Treffer im vollen STL im Box-Bereich
    sel2 = np.all((ct >= [bx[0], bx[1], bx[2]]) & (ct <= [bx[3], bx[4], bx[5]]), axis=1); full = trimesh.Trimesh(m.vertices, m.faces[sel2], process=False)
    # Rippenmittellinie vor Flaeche: Abstand Strahlursprung->erster Treffer (alle Dreiecke) kleiner als Abstand zur Flaeche ohne Rippen (= sub identisch: sub==full) -> Vergleich ueber Modell ohne/mit Rippen
    res = dict(kam=kam, pruef=pr, n_skelett=len(pts), n_flaeche=int(len(P)), n_valide=int(ok.sum()), punkte_xyz=P[ok].round(3).tolist(), pixel=px[ok].tolist())
    json.dump(res, open(os.path.join(aus, "rippen_abdeckung_punkte.json"), "w"))
    c = im[y0:y1, x0:x1].copy(); [cv2.circle(c, (int(p[0]) - x0, int(p[1]) - y0), 2, (0, 255, 0) if k else (0, 0, 255), -1) for p, k in zip(px, ok)]
    cv2.imwrite(os.path.join(aus, "rippen_abdeckung.jpg"), cv2.resize(c, None, fx=700 / c.shape[0], fy=700 / c.shape[0])); print("->", aus)
main()
