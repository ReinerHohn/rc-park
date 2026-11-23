#!/usr/bin/env python3
"""Test seiten_eck_koppeln REPROJ (23.11.2026): Kopplungsweg pycolmap.align_reconstructions_via_reprojections, dieselben Tore wie der Punkt-Weg.
(1) Synthetisch (pycolmap.synthesize_dataset, Rauschen): Teil 0, Teil 1 (bekannte Sim3) und ein Eckmodell (andere Sim3), die sich nur WENIGE Bilder teilen ->
    beide Kopplungen stimmig, Kante Teil1 -> Teil0 = bekannte Sim3 wiedergefunden; Keim fest = gleiche Eingabe gleiches Ergebnis.
(2) Falsches Teil (andere Szene unter denselben Bildnamen) -> nicht gekoppelt. Gespiegelter flacher Teil mit vorgegebener Sim3 aus den Kameras -> Tore lehnen ab.
(3) Variantenwahl: Reproj gewinnt nur mit MEHR stimmigen Teilen, bei Gleichstand der Punkt-Weg; wahl_grund nennt es. Grenzen unveraendert. CPU, Sekunden."""
import os, sys, numpy as np, pycolmap
T = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, T)
import seiten_eck_koppeln as EK
from sim3_robust import matrix, anwenden, umeyama
fehler = []
def pruef(ok, text): print(("ok   " if ok else "FEHL ") + text); ok or fehler.append(text)
d = __import__("pfade").temp_ordner("test_eck_reproj_")

def szene(keim, n_bilder=30):
    pycolmap.set_random_seed(keim); o = pycolmap.SyntheticDatasetOptions(); o.num_rigs = 1; o.num_cameras_per_rig = 1; o.num_frames_per_rig = n_bilder; o.num_points3D = 1500
    r = pycolmap.synthesize_dataset(o); no = pycolmap.SyntheticNoiseOptions(); no.point2D_stddev = 0.5; pycolmap.synthesize_noise(no, r); return r

def nur(r, behalten, sim=None, rauschen=True):
    """Kopie mit nur den Bildern 'behalten' (Index in Bild-ID-Reihenfolge), eigenes Rauschen (Punkte/Kamerazentren 2 mm bei ~2 m Szene, 0,02 Grad), optional mit Sim3 transformiert."""
    q = pycolmap.Reconstruction(r); ids = sorted(q.images)
    for i, b in enumerate(ids):
        if i not in behalten and q.images[b].has_pose: q.deregister_frame(q.images[b].frame_id)
    if rauschen:
        no = pycolmap.SyntheticNoiseOptions(); no.point3D_stddev = 0.002; no.rig_from_world_translation_stddev = 0.002; no.rig_from_world_rotation_stddev = 0.02; pycolmap.synthesize_noise(no, q)
    if sim is not None: q.transform(sim)
    return q

def sim3(s, achse, grad, t):
    a = np.asarray(achse, float); a /= np.linalg.norm(a); h = np.radians(grad) / 2
    return pycolmap.Sim3d(s, pycolmap.Rotation3d(np.r_[a * np.sin(h), np.cos(h)]), np.asarray(t, float))

def M4(s): M = np.eye(4); M[:3] = np.asarray(s.matrix()); return M

r = szene(1)
S1 = sim3(0.37, [0.2, 1, 0.3], 41, [3, -1, 2]); SE = sim3(2.5, [1, 0, 0.4], -23, [-4, 5, 1])
R = {0: nur(r, set(range(0, 16))), 1: nur(r, set(range(12, 30)), S1)}
eck = nur(r, set(range(10, 18)), SE); pe = os.path.join(d, "eck"); os.makedirs(pe, exist_ok=True); eck.write(pe)
for t in R: EK.NAMEN[t] = {im.name for im in R[t].images.values() if im.has_pose}
at = {t: EK.ausdehnung([p.xyz for p in R[t].points3D.values()]) for t in R}
info, gut, alle = EK.koppeln(pe, [0, 1], R, None, at, weg="reproj")
pruef(sorted(gut) == [0, 1], f"8 Eckbilder, je 6 mit einem Teil gemeinsam: beide Kopplungen stimmig ({ {t: v.get('grund') for t, v in alle.items()} })")
if sorted(gut) == [0, 1]:
    Mk = gut[0][0] @ np.linalg.inv(gut[1][0]); W = np.linalg.inv(M4(S1)); D = Mk @ np.linalg.inv(W); s, Rr, _ = EK.zerlegen(D)
    P0 = np.array([p.xyz for p in R[0].points3D.values()]); vs = float(np.median(np.linalg.norm(anwenden(D, P0) - P0, axis=1))) / at[0]   # Lagefehler auf den Punkten von Teil 0
    pruef(EK.winkel(Rr) < 0.5 and abs(s - 1) < 0.01 and vs < 0.01, f"Kante Teil1 -> Teil0 = bekannte Sim3 (Drehung {EK.winkel(Rr):.4f} Grad, Massstab {abs(s - 1):.2e}, Lage {vs:.2e} der Ausdehnung; Rauschen 0,1 % der Szene)")
    pr = alle[1]; pruef(pr.get("weg") == "reproj" and pr["reproj"]["bilder_stimmig"] >= 5 and pr["reproj"]["beobachtungen_stimmig"] > 0.5 and "keim_streuung" in pr["reproj"],
                        f"JSON: Weg, Inlier-Bilder/Beobachtungen, Keim-Streuung ({ {k: pr['reproj'].get(k) for k in ('bilder_stimmig', 'beobachtungen_stimmig', 'keim_streuung')} })")
a1, _ = EK.reproj_sim3(eck, R[1]); a2, _ = EK.reproj_sim3(eck, R[1])
pruef(a1 is not None and np.array_equal(a1, a2), "fester RANSAC-Keim: zwei Aufrufe liefern dieselbe Sim3")

# (2) falsches Teil: andere Szene, dieselben Bildnamen
R2 = {0: R[0], 1: nur(szene(7), set(range(12, 30)), S1)}; EK.NAMEN[1] = {im.name for im in R2[1].images.values() if im.has_pose}
at2 = {0: at[0], 1: EK.ausdehnung([p.xyz for p in R2[1].points3D.values()])}
_, gut2, alle2 = EK.koppeln(pe, [0, 1], R2, None, at2, weg="reproj")
pruef(0 in gut2 and 1 not in gut2, f"falsches Teil (andere Szene, gleiche Namen) nicht gekoppelt ({alle2.get(1, {}).get('grund')})")
rng = np.random.default_rng(5); n = 3000
P = np.c_[rng.uniform(-8, 8, n), rng.uniform(0, 12, n), rng.normal(0, 0.03, n)]; C = np.c_[rng.uniform(-6, 6, 12), rng.uniform(1, 3, 12), np.full(12, 10.0)]
c_, s_ = np.cos(0.7), np.sin(0.7); M = matrix(0.4, np.array([[c_, -s_, 0], [s_, c_, 0], [0, 0, 1]]), [1, -2, 3]); Mi = np.linalg.inv(M)
tf = np.linalg.norm(P - C[rng.integers(0, 12, n)], axis=1); X = anwenden(Mi, P + rng.normal(0, 1, P.shape) * (0.002 * tf)[:, None]); CX = anwenden(Mi, C); td = tf / 0.4
sp = lambda Y: Y * np.array([1, 1, -1])
_, prr, okr, gr = EK.kopplung_pruefen(X, P, EK.ausdehnung(X), EK.ausdehnung(P), tiefe=td, kameras=(CX, C), M_fest=M)
pruef(okr and prr["rest_rel"] < 0.005, f"vorgegebene richtige Sim3: Tore bestanden ({gr})")
Msp = matrix(*umeyama(CX, sp(C)))                                                     # Sim3, die die Kameras des gespiegelten Teils trifft (wie ein Kamerazentren-Fit)
_, prs, oks, gs = EK.kopplung_pruefen(X, sp(P), EK.ausdehnung(X), EK.ausdehnung(P), tiefe=td, kameras=(CX, sp(C)), M_fest=Msp)
pruef(not oks and ("Anteil" in gs or "Rest" in gs or "trifft nur" in gs), f"gespiegelter flacher Teil mit Kamera-Sim3: Punkt-Tore lehnen ab ({gs})")
_, _, okb, gb = EK.kopplung_pruefen(X, P, EK.ausdehnung(X), None, tiefe=td, M_fest=M @ matrix(1.0, np.eye(3), [0.3, 0, 0]))
pruef(not okb, f"verschobene vorgegebene Sim3 (0,3 m im Eckrahmen) abgelehnt, kein Nachpassen ({gb})")

# (3) Variantenwahl
g = lambda *t: {x: None for x in t}
pruef(EK.variante_waehlen(dict(sift=g(0, 1), teilkameras=g(0, 1), reproj_teilkameras=g(0, 1), reproj_sift=g(0, 1))) == "teilkameras", "Gleichstand -> Punkt-Weg vor Reproj")
pruef(EK.variante_waehlen(dict(sift=g(0), teilkameras=g(1), reproj_teilkameras=g(0, 1), reproj_sift=g())) == "reproj_teilkameras", "Reproj koppelt als einzige beide Teile -> Reproj")
pruef(EK.variante_waehlen(dict(sift=g(0, 1), reproj_sift=g(1))) == "sift", "Reproj mit einem Teil zaehlt nicht")
wg = EK.wahl_grund(dict(sift=g(0), teilkameras=g(1), reproj_teilkameras=g(0, 1)), "reproj_teilkameras")
pruef("reproj_teilkameras: 2" in wg and "meiste" in wg, f"wahl_grund nennt Zahl und Regel ({wg})")
pruef("Gleichstand" in EK.wahl_grund(dict(sift=g(0, 1), reproj_sift=g(0, 1)), "sift"), "wahl_grund bei Gleichstand")
pruef(EK.MASS_REL == 0.02 and EK.REST_REL == 0.005 and EK.MIN_ANTEIL == 0.8 and EK.KAM_REL == 0.2 and EK.SCHWELLE_REL == 0.02, "Kopplungsgrenzen unveraendert")
src = open(os.path.join(T, "seiten_eck_koppeln.py")).read()
pruef("RCPARK_ECK_REPROJ" in src and 'vs["reproj_" + b] = reproj_variante(' in src and "set_random_seed" in src and "M_fest=Mf" in src, "Verdrahtung: Schalter, Variante je Basis, fester Keim, Tore mit M_fest")
print("FEHLER:" if fehler else "alle ok", len(fehler)); sys.exit(1 if fehler else 0)
