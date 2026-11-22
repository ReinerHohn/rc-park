#!/usr/bin/env python3
"""Fester Test tools/sfm_gps_ausgleich.py (synthetisch, < 30 s, < 1 GB): Turm 10 x 10 x 30 m, zwei Seitenteile (Nord 60 Kameras, Sued 50) OHNE gemeinsame 3D-Punkte
(wie das vereinte Modell aus tools/sfm_seiten_modelle.py). Teil B ist um 3 Grad (um das Lot) verdreht und 9 % zu gross an A gelegt, das Ganze steht in einem beliebigen
Modellsystem (gedreht, Massstab 0,13). Foto-GPS: 4 m Rauschen, 8 falsche Geotags (60-90 m daneben), eine Serie von 5 Bildern mit DEMSELBEN eingefrorenen Geotag.
  1. Ausgleich bringt B zurueck: Drehung B gegen A < 1 Grad, Massstab B/A < 2 % daneben, GPS-Rest sinkt, Bildfehler nicht schlechter, Ergebnis im Eingangssystem (A bleibt).
  2. Gegenprobe wenig GPS (17 Geotags wie Martinstor): rc 2, nichts geaendert.
  3. Gegenprobe Teil ohne genug GPS: dessen Lagen bleiben fest (Stueck festgehalten), kein Absturz.
  4. Eingefrorene Geotags zaehlen einmal (gruppen).
  5. Waechter: wird der Bildfehler schlechter, bleibt das Modell unveraendert (rc-3-Weg).
Aufruf: /media/oem/scan/venv-colmap/bin/python -I tools/test_sfm_gps_ausgleich.py"""
import os, sys, io, contextlib
import numpy as np
T = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, T)
import pycolmap
import sfm_gps_ausgleich as GA

rng = np.random.default_rng(1)
F, W_, H_ = 1500.0, 1600, 1200


def blick(c, ziel):
    """cam_from_world fuer eine aufrechte Kamera in c, die auf ziel blickt (Welt z = oben)."""
    z = ziel - c; z /= np.linalg.norm(z); x = np.cross(z, [0, 0, 1.0]); x /= np.linalg.norm(x); y = np.cross(z, x)   # Bild-y zeigt nach unten
    R = np.array([x, y, z]); return pycolmap.Rigid3d(pycolmap.Rotation3d(R), -R @ c)


def flaeche(y0, n=500):
    """Punkte auf der Wand y = y0 (x -5..5, z 0..30) plus etwas Relief."""
    return np.c_[rng.uniform(-5, 5, n), np.full(n, y0) + rng.normal(0, 0.3, n), rng.uniform(0, 30, n)]


def teil(az_von, az_bis, n, P, start_id, rng_):
    ks = []
    for k in range(n):
        a = np.radians(rng_.uniform(az_von, az_bis)); r = rng_.uniform(20, 60); c = np.array([r * np.cos(a), r * np.sin(a), 1.6 + rng_.normal(0, 0.3)])
        ks.append((start_id + k, c, blick(c, np.array([0, 0, rng_.uniform(5, 20)]))))
    return ks, P


def szene():
    """-> (Reconstruction im WAHREN ENU-System, {Name: Teil})."""
    rec = pycolmap.Reconstruction(); rec.add_camera_with_trivial_rig(pycolmap.Camera(model="SIMPLE_PINHOLE", width=W_, height=H_, params=[F, W_ / 2, H_ / 2], camera_id=1))
    teile = {}; spuren = []
    for t, (a0, a1, n, y0, sid) in enumerate([(50, 130, 60, 5.0, 1), (230, 310, 50, -5.0, 1001)]):
        ks, P = teil(a0, a1, n, flaeche(y0), sid, rng); obs = {i: [] for i, _, _ in ks}; tr = [[] for _ in P]
        for i, c, cw in ks:
            Xc = P @ cw.rotation.matrix().T + cw.translation; u = F * Xc[:, 0] / Xc[:, 2] + W_ / 2; v = F * Xc[:, 1] / Xc[:, 2] + H_ / 2
            ok = (Xc[:, 2] > 1) & (u > 0) & (u < W_) & (v > 0) & (v < H_)
            for j in np.flatnonzero(ok): tr[j].append((i, len(obs[i]))); obs[i].append([u[j] + rng.normal(0, 0.5), v[j] + rng.normal(0, 0.5)])
        for i, c, cw in ks:
            nm = f"t{t}_{i:04d}.jpg"; teile[nm] = t; rec.add_image_with_trivial_frame(pycolmap.Image(name=nm, keypoints=np.array(obs[i], float).reshape(-1, 2), camera_id=1, image_id=i), cw)
        for j, el in enumerate(tr):
            if len(el) < 2: continue
            tk = pycolmap.Track()
            for i, k in el: tk.add_element(i, k)
            rec.add_point3D(P[j], tk, np.zeros(3, np.uint8))
    return rec, teile


def sim(s, grad, t, achse=(0, 0, 1)):
    a = np.radians(grad); k = np.asarray(achse, float) / np.linalg.norm(achse); K = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
    R = np.eye(3) + np.sin(a) * K + (1 - np.cos(a)) * K @ K; M = np.eye(4); M[:3, :3] = s * R; M[:3, 3] = t; return M


def teil_bewegen(rec, teile, t, M):
    """Bilder und Punkte von Teil t mit M (4x4) bewegen (Teile ohne gemeinsame Punkte)."""
    s, R, tt = GA.zerlege(M); ids = {i for i, im in rec.images.items() if teile[im.name] == t}
    for i in ids:
        cw = rec.images[i].cam_from_world(); C = cw.rotation.matrix().T @ -cw.translation; Rn = cw.rotation.matrix() @ R.T; Cn = s * R @ C + tt
        rec.frames[rec.images[i].frame_id].rig_from_world = pycolmap.Rigid3d(pycolmap.Rotation3d(Rn), -Rn @ Cn)
    for p in rec.points3D.values():
        if p.track.elements[0].image_id in ids: p.xyz = s * R @ p.xyz + tt


def gps(rec, n=None, falsch=8, frier=5):
    """{Name: (ost, nord)} aus den WAHREN Zentren + 4 m Rauschen, einige falsche Geotags, eine eingefrorene Serie."""
    ns = sorted(im.name for im in rec.images.values()); rng_ = np.random.default_rng(7); wahl = ns if n is None else list(rng_.choice(ns, n, replace=False))
    C = {im.name: im.projection_center() for im in rec.images.values()}; G = {m: C[m][:2] + rng_.normal(0, 4.0 / np.sqrt(2), 2) for m in wahl}
    for m in list(G)[:falsch]: G[m] = G[m] + rng_.uniform(60, 90) * np.array([1.0, 0.0])
    for m in list(G)[falsch:falsch + frier]: G[m] = G[list(G)[falsch]].copy()
    return G


def lage_b_gegen_a(rec, wahr, teile):
    """Drehung (Grad) und Massstab von Teil B relativ zu Teil A gegen die Wahrheit: Sim3 alt->wahr je Teil, dann B relativ zu A."""
    def m(t):
        ns = [im.name for im in rec.images.values() if teile[im.name] == t]; X = np.array([rec.find_image_with_name(n).projection_center() for n in ns])
        return GA.sim3_fit(X, np.array([wahr.find_image_with_name(n).projection_center() for n in ns]))
    D = np.linalg.inv(m(0)) @ m(1); s, R, _ = GA.zerlege(D); return GA.drehwinkel(R), 1.0 / s   # Massstab B/A (1,09 = B zu gross)


wahr, teile = szene(); G = gps(wahr)
roh = pycolmap.Reconstruction(wahr)
teil_bewegen(roh, teile, 1, sim(1.09, 3.0, [0, 0, 0]) @ np.eye(4))     # B um 3 Grad um das Lot (Turmmitte) verdreht, 9 % zu gross
X0 = sim(0.13, 37.0, [4.0, -2.0, 1.0], achse=(0.3, 0.2, 1.0)); roh.transform(GA.zu_sim3d(X0))   # beliebiges Modellsystem
d0, s0 = lage_b_gegen_a(roh, wahr, teile); assert abs(d0 - 3.0) < 0.2 and abs(s0 - 1.09) < 0.01, f"Testaufbau: {d0} {s0}"

# 4 eingefrorene Geotags
gr, n_u = GA.gruppen(G, list(G)); assert max(gr.values()) == 5 and n_u == len(G) - 4, f"Gruppen {max(gr.values())} {n_u}"
print(f"ok 4: eingefrorene Serie (5 gleiche Geotags) zaehlt einmal: {n_u} unabhaengige von {len(G)}")

# 1 Ausgleich
with contextlib.redirect_stdout(io.StringIO()): erg, neu = GA.ausgleich(roh, G, teile)
assert erg["ok"] and neu is not None, f"nicht uebernommen: {erg['urteil']}"
d1, s1 = lage_b_gegen_a(neu, wahr, teile)
assert d1 < 1.0 and abs(s1 - 1) < 0.02, f"B nicht zurueck: Drehung {d1:.2f} Grad, Massstab {s1:.4f} (vorher {d0:.2f} / {s0:.3f})"
assert erg["gps_rest_nachher_m"] < erg["gps_rest_vorher_m"] and erg["reproj_nachher_px"] <= erg["reproj_vorher_px"] * 1.02 + 0.02, erg["urteil"]
tA = erg["teile"]["0"]; assert tA["drehung_grad"] < 1.0 and abs(tA["massstab"] - 1) < 0.02, f"Teil A wurde verschoben statt B: {tA}"
assert erg["stuecke"]["anzahl"] == 2 and not erg["stuecke"]["festgehalten"], erg["stuecke"]
print(f"ok 1: B zurueck (Drehung {d0:.1f} -> {d1:.2f} Grad, Massstab {s0:.3f} -> {s1:.4f}); {erg['urteil']}; delta B {erg['teile']['1']['drehung_grad']:.2f} Grad x{erg['teile']['1']['massstab']:.3f}")

# 2 Gegenprobe wenig GPS (Martinstor 15-17)
G2 = gps(wahr, n=17, falsch=0, frier=0)
erg2, neu2 = GA.ausgleich(roh, G2, teile); assert not erg2["ok"] and erg2.get("zu_wenig") and neu2 is None, erg2["urteil"]
print(f"ok 2: wenig GPS -> nichts getan ({erg2['urteil']})")

# 3 Teil B ohne genug GPS: festgehalten
G3 = {k: v for k, v in G.items() if teile[k] == 0 or int(k[3:7]) < 1008}
with contextlib.redirect_stdout(io.StringIO()): erg3, neu3 = GA.ausgleich(roh, G3, teile)
assert erg3["stuecke"]["festgehalten"] == [1], erg3["stuecke"]
if neu3 is not None:
    d3, s3 = lage_b_gegen_a(neu3, wahr, teile); assert erg3["teile"]["1"]["drehung_grad"] < 0.05 and abs(erg3["teile"]["1"]["massstab"] - 1) < 1e-3, f"festgehaltener Teil bewegt: {erg3['teile']['1']}"
print(f"ok 3: Teil ohne genug GPS festgehalten ({erg3['urteil'][:90]})")
# 5 Waechter Bildfehler: Toleranz kuenstlich negativ -> abgelehnt, nichts uebernommen
alt_tol = GA.REPROJ_TOL_REL; GA.REPROJ_TOL_REL = -0.5
try:
    with contextlib.redirect_stdout(io.StringIO()): erg5, neu5 = GA.ausgleich(roh, G, teile)
finally: GA.REPROJ_TOL_REL = alt_tol
assert not erg5["ok"] and not erg5.get("zu_wenig") and neu5 is None and "Bildfehler schlechter" in erg5["urteil"], erg5["urteil"]
print(f"ok 5: Waechter Bildfehler lehnt ab ({erg5['urteil'][:80]})")
print("ALLE TESTS BESTANDEN")
