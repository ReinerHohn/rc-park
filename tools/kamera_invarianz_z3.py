#!/usr/bin/env python3
"""kamera_invarianz_z3.py - Z3: Beweis, dass eine Kameraaenderung einen Modellfehler nicht verschluckt.
Kopie eines Bauteil-STL (Scratch, Generator unberuehrt) um DX verschoben (synthetischer Modellfehler). Je Foto: Projektionsversatz des verschobenen Teils gegen das Original
(a) mit alter Kamera (kam_lot2), (b) mit Vorschlagskamera. Invarianz: (a)==(b) +-Rauschen. Zusaetzlich Verschluckungsanteil = Kameraverschiebung des Originalteils (px) / Fehlerversatz (px).
  python -I tools/kamera_invarianz_z3.py KOPIE.stl VORSCHLAG.json [dx dy dz]"""
import sys, os, json, numpy as np, trimesh
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
D = "/media/oem/scan/rc-park_daten/kaufhaus_alle"
if sys.argv[1] == "ersatz":      # Ersatzteil: dichteste 3x3x3-m-Zelle der Gitterpunkte (z 4..10) - modellfrei, lot2-Rahmen
    from kamera_linienfein import segment_punkte
    G = segment_punkte(schritt=0.1)[0]; G = G[(G[:, 2] > 4) & (G[:, 2] < 10)]; c = np.floor(G / 3.0).astype(int); u, inv, cnt = np.unique(c, axis=0, return_inverse=True, return_counts=True); V = G[inv.ravel() == cnt.argmax()]
    print("Ersatzteil: Zelle", u[cnt.argmax()] * 3, "n", len(V))
else:
    m = trimesh.load(sys.argv[1]); V = np.asarray(m.vertices)
vor = json.load(open(sys.argv[2])); alt = json.load(open(D + "/sfm/kam_lot2.json")); dx = np.array([float(x) for x in sys.argv[3:6]] or [1, 0, 0]) if len(sys.argv) > 5 else np.array([0., 1., 0.])
def pr(k, X, R=None, t=None):
    R = np.array(k["Rn"]) if R is None else R; t = np.array(k["tn"]) if t is None else t; Xc = X @ R.T + t; u = Xc[:, :2] / Xc[:, 2:3]; k1 = k["params"][3]
    return k["f"] * u * (1 + k1 * (u * u).sum(1)[:, None]) + [k["cx"], k["cy"]], Xc[:, 2]
rows = []
for n, kn in vor.items():
    ka = alt[n]; pa0, z = pr(ka, V); ok = (z > 1) & (pa0[:, 0] > 0) & (pa0[:, 0] < ka["W"]) & (pa0[:, 1] > 0) & (pa0[:, 1] < ka["H"])
    if ok.sum() < 20: continue
    pa1, _ = pr(ka, V + dx); pb0, _ = pr(kn, V); pb1, _ = pr(kn, V + dx)
    fa = np.linalg.norm(pa1[ok] - pa0[ok], axis=1).mean(); fb = np.linalg.norm(pb1[ok] - pb0[ok], axis=1).mean(); cam = np.linalg.norm(pb0[ok] - pa0[ok], axis=1).mean()
    rows.append(dict(foto=n, n_pkt=int(ok.sum()), fehler_px_alte_kamera=round(float(fa), 2), fehler_px_neue_kamera=round(float(fb), 2), differenz_px=round(float(fb - fa), 3), kamera_verschiebt_teil_px=round(float(cam), 2),
                     verschluckt_anteil=round(float(cam / fa), 3), tiefe_m=round(float(np.median(z[ok])), 1)))
json.dump(rows, open(D + "/agent_scratch_kam/z3/z3_ergebnis.json", "w"), indent=0)
for r in rows: print(r)
d = np.array([r["differenz_px"] for r in rows]); v = np.array([r["verschluckt_anteil"] for r in rows]); print("n", len(rows), "Fehlerversatz-Differenz px med/max", np.median(np.abs(d)).round(3), np.abs(d).max().round(3), "| verschluckt Anteil med/max", np.median(v).round(3), v.max().round(3))
