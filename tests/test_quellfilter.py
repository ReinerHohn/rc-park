#!/usr/bin/env python3
"""Test tools/quellfilter.py (24.11.2026, Geisterblatt 1122z): synthetische Szene - Wand bei y = 10, 40 Kameras in einer Reihe (y = 0) blicken auf die Wand.
Ein 'Geisterblatt' bei y = 7 steht nur in den Tiefenkarten von 3 eng benachbarten Kameras (verschleppte Silhouettentiefe, wie die Videobilder);
alle anderen Kameras sehen dort die Wand dahinter (Freiraum). ROT-PROBE: Wandpunkte, ein echter Vorbau (Erker bei y = 8, in allen Karten) und
ein Wandpunkt am Bildrand mit wenigen Sichten bleiben. Dazu: Guard (> 10 %), vis-Kuerzung, Marke quellfilter_noetig."""
import os, sys, json, tempfile, numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
import quellfilter as QF

F = []
def pruef(b, txt):
    print(("    ok " if b else "    FEHLER ") + txt)
    if not b: F.append(txt)

W, H = 400, 300; K = (300.0, 300.0, 200.0, 150.0)
# Kamera bei (cx, 0, 2), Blick +y: Kamera-z = Welt-y, Kamera-x = Welt-x, Kamera-y = -Welt-z (Bild nach unten)
R = np.array([[1, 0, 0], [0, 0, -1], [0, 1, 0]], float)
kams = [np.array([cx, 0.0, 2.0]) for cx in np.linspace(-6, 6, 40)]
geist_kams = {20, 21, 22}

def tiefe(c, j):
    u, v = np.meshgrid(np.arange(W) + 0.0, np.arange(H) + 0.0)
    rx = (u - K[2]) / K[0]; ry = (v - K[3]) / K[1]          # Strahl in Kamera: (rx, ry, 1)
    d = np.full((H, W), 10.0 - c[1], np.float32)            # Wand y = 10 -> Tiefe = 10
    wx = c[0] + rx * 8.0; wz = c[2] - ry * 8.0              # Erker y = 8, x -1..1, z 3..5
    erker = (np.abs(wx) <= 1) & (wz >= 3) & (wz <= 5); d[erker] = 8.0
    if j in geist_kams:
        gx = c[0] + rx * 7.0; gz = c[2] - ry * 7.0          # Geisterblatt y = 7, x 2..4, z 1..4 (nur in diesen Karten)
        d[(gx >= 2) & (gx <= 4) & (gz >= 1) & (gz <= 4)] = 7.0
    return d

kameras = []
for j, c in enumerate(kams):
    t = -R @ c; dm = tiefe(c, j); kameras.append((K, R, t, W, H, (lambda dm=dm: dm)))
rng = np.random.default_rng(1)
wand = np.stack([rng.uniform(-4, 4, 3000), np.full(3000, 10.0), rng.uniform(0, 5, 3000)], 1)
wand = wand[~((np.abs(wand[:, 0]) <= 1.3) & (wand[:, 2] >= 2.5))]           # hinter dem Erker (verdeckt) nicht als Wand pruefen
erker = np.stack([rng.uniform(-1, 1, 500), np.full(500, 8.0), rng.uniform(3, 5, 500)], 1)
geist = np.stack([rng.uniform(2.1, 3.9, 500), np.full(500, 7.0), rng.uniform(1.1, 3.9, 500)], 1)
X = np.concatenate([wand, erker, geist]).astype(np.float32); lab = np.r_[np.zeros(len(wand)), np.ones(len(erker)), 2 * np.ones(len(geist))]
nq, nv = QF.zaehlen(X, kameras, threads=3); weg = QF.entscheiden(nq, nv)
pruef(weg[lab == 2].mean() > 0.8, f"Geisterblatt weg {100 * weg[lab == 2].mean():.0f} % (> 80 %)")
pruef(weg[lab == 0].mean() < 0.02, f"Rot-Probe Wand weg {100 * weg[lab == 0].mean():.1f} % (< 2 %)")
pruef(weg[lab == 1].mean() < 0.02, f"Rot-Probe Erker (echter Vorbau) weg {100 * weg[lab == 1].mean():.1f} % (< 2 %)")
nq1, nv1 = QF.zaehlen(X, kameras, threads=1); pruef(np.array_equal(nq, nq1) and np.array_equal(nv, nv1), "Threads aendern das Ergebnis nicht")
# wenige Kameras -> Mindestzahl Freiraum greift nicht (lieber nichts tun als raten)
nq2, nv2 = QF.zaehlen(X, kameras[18:26], threads=2); pruef(not QF.entscheiden(nq2, nv2).any(), "8 Kameras: Filter greift nicht (Mindestzahl Freiraum)")

# Datei-Ebene: PLY + vis kuerzen, Marke
with tempfile.TemporaryDirectory() as d:
    P = np.zeros(5, QF.DT); P["x"] = np.arange(5); p = os.path.join(d, "fused.ply"); QF.ply_schreiben(p, P)
    pruef(np.array_equal(QF.ply_lesen(p)["x"], P["x"]), "PLY schreiben/lesen")
    vis = [[1, 2], [3], [4, 5, 6], [7], [8, 9]]; b = [np.array([5], "<u8").tobytes()] + [np.array([len(r)] + r, "<u4").tobytes() for r in vis]
    open(p + ".vis", "wb").write(b"".join(b)); QF.vis_filtern(p + ".vis", np.array([True, False, True, False, True]))
    v = np.fromfile(p + ".vis", np.uint8); u = v[8:].view("<u4")
    pruef(int(v[:8].view("<u8")[0]) == 3 and u.tolist() == [2, 1, 2, 3, 4, 5, 6, 2, 8, 9], f"vis gekuerzt {u.tolist()}")
    pruef(QF.quellfilter_noetig(p), "ohne Marke -> noetig")
    json.dump(dict(stand=QF.stand(), punkte_nachher=5), open(p + ".quellfilter.json", "w")); pruef(not QF.quellfilter_noetig(p), "Marke aktuell -> nicht noetig")
    json.dump(dict(stand="alt", punkte_nachher=5), open(p + ".quellfilter.json", "w")); pruef(QF.quellfilter_noetig(p), "alter Stand -> noetig")
    os.environ["RCPARK_QUELLFILTER"] = "0"; pruef(not QF.quellfilter_noetig(p), "RCPARK_QUELLFILTER=0 -> aus"); del os.environ["RCPARK_QUELLFILTER"]
print("FEHLER" if F else "ALLE OK", len(F)); sys.exit(1 if F else 0)
