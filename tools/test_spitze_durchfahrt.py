#!/usr/bin/env python3
"""test_spitze_durchfahrt.py - feste synthetische Tests fuer tools/spitze_aus_umriss.py und tools/durchfahrt_pruefen.py (21.11.2026). Ohne Dateien, < 30 s.

A) Turm mit Zeltdach + offener Laterne + Zwiebelhaube + Nadel, 12 Kameras rundum, Himmelsmasken analytisch gerendert (konvexe Scheiben).
   Soll: Spitze (Nadelende) auf 0,25 m, Krempe (Unterkante der Haube) auf 0,4 m, Hals-Halbbreite ~ Laternenradius; Nadel 0,15 -> 0,2 m ist KEINE Krempe.
   Gegenprobe: Kamera direkt unter der Traufe (Traufe verdeckt die Spitze) wird verworfen, nicht als Spitze gezaehlt. Quadratischer Querschnitt wird als 'eckig' erkannt.
   bauteile.spitze_ab: Fotoblock ersetzt das Wolkendach erst ab dem Laternenhals; ungueltiger Block -> None.
B) Durchfahrt: Torweg (Laibungen durchgehend, Streupunkte im Inneren) -> ja; Nische 0,6 m mit Rueckwand -> nein; massive Wand mit Streupunkten -> nein."""
import sys, os, math, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cv2, spitze_aus_umriss as SU, durchfahrt_pruefen as DP, flaeche_ortho as FO

fehler = []
def pruef(ok, text):
    print(("    ok   " if ok else "FEHLER  ") + text)
    if not ok: fehler.append(text)

# ---- A: Turmspitze ----------------------------------------------------------------------------------------------------------------------------
AX = np.array([1.0, -2.0]); Z_TRAUFE, Z_HALS, Z_KREMPE, Z_HAUBE, Z_NADEL0, Z_SPITZE = 40.0, 46.0, 48.5, 50.5, 51.5, 53.0
def querschnitt(z, eckig_bis=None):
    """-> (halb, eckig) des Koerpers in Hoehe z."""
    if z < Z_TRAUFE: return 3.0, True
    if z < Z_HALS: return 3.6 - (3.6 - 0.8) * (z - Z_TRAUFE) / (Z_HALS - Z_TRAUFE), True      # Zeltdach mit Ueberstand, quadratisch
    if z < Z_KREMPE: return 0.8, False
    if z < Z_HAUBE: return 1.3, False
    if z < Z_NADEL0: return 1.3 - 1.1 * (z - Z_HAUBE) / (Z_NADEL0 - Z_HAUBE), False
    if z <= Z_SPITZE: return 0.15, False
    return None, False

def ring(z):
    h, e = querschnitt(z)
    if h is None: return None
    if e: return np.array([[AX[0] + sx * h, AX[1] + sy * h, z] for sx in (-1, 1) for sy in (-1, 1)])
    return np.array([[AX[0] + h * math.cos(w), AX[1] + h * math.sin(w), z] for w in np.linspace(0, 2 * math.pi, 32, endpoint=False)])

WI, HI, F = 1000, 1400, 900.0
def kamera(az, dist, h, ziel_z=40.0):
    C = np.array([AX[0] + dist * math.cos(az), AX[1] + dist * math.sin(az), h]); zv = np.array([AX[0], AX[1], ziel_z]) - C; zv /= np.linalg.norm(zv)
    xv = np.cross(zv, [0, 0, 1.0]); xv /= np.linalg.norm(xv); yv = np.cross(zv, xv); Rm = np.stack([xv, yv, zv])
    return dict(rvec=cv2.Rodrigues(Rm)[0].ravel().tolist(), t=(-Rm @ C).tolist(), f_px=F, cx=WI / 2, cy=HI / 2, k1=0.0), C

def maske(c):
    m = np.zeros((HI, WI), np.uint8); zs = np.arange(0.0, Z_SPITZE + 1e-9, 0.04)
    for a, b in zip(zs[:-1], zs[1:]):
        P = np.vstack([r for r in (ring(a), ring(min(b, Z_SPITZE))) if r is not None]); p, zc, _ = FO.projektion(P, c)
        if (zc > 0).all(): cv2.fillConvexPoly(m, cv2.convexHull(np.round(p).astype(np.int32)), 255)
    return m == 0                                                                  # True = Himmel

mess = []; zs = np.round(np.arange(43.0, 58.0, 0.1), 2)
for i in range(12):
    c, C = kamera(2 * math.pi * i / 12 + 0.2, 55 + 8 * (i % 3), 1.6 + (i % 2) * 6)
    proj = lambda X, c=c: FO.projektion(np.atleast_2d(X), c)
    z_sp, g, halb = SU.foto_messen(maske(c), proj, AX, zs, C)
    if z_sp is not None: mess.append((str(i), math.degrees(2 * math.pi * i / 12 + 0.2), z_sp, halb, (C[2], float(np.hypot(*(C[:2] - AX))))))
pruef(len(mess) >= 10, f"Spitze in {len(mess)} von 12 Fotos gemessen")
E = SU.auswerten(mess, zs, SU.SEKTOR_GRAD)
pruef(E.get("gueltig") and abs(E["spitze_z"] - Z_SPITZE) <= 0.25, f"Spitze {E.get('spitze_z')} (Soll {Z_SPITZE} +- 0,25)")
pruef(E.get("krempe_z") is not None and abs(E["krempe_z"] - Z_KREMPE) <= 0.4, f"Krempe {E.get('krempe_z')} (Soll {Z_KREMPE} +- 0,4; Nadel darf keine Krempe sein)")
pruef(E.get("hals_halb") is not None and abs(E["hals_halb"] - 0.8) <= 0.12, f"Hals-Halbbreite {E.get('hals_halb')} (Soll 0,8)")
pz = {p[0]: p for p in E.get("profil", [])}; z_d = min(pz, key=lambda z: abs(z - 43.5)) if pz else None
pruef(z_d is not None and pz[z_d][4] == "eckig", f"Zeltdach bei z {z_d} als eckig erkannt ({pz.get(z_d, [None] * 5)[4]})")
z_l = min(pz, key=lambda z: abs(z - 47.2)) if pz else None
pruef(z_l is not None and pz[z_l][4] == "rund" and abs(pz[z_l][6] - 0.8) <= 0.12, f"Laterne bei z {z_l} rund, r {pz.get(z_l, [None] * 7)[6]} (Soll 0,8)")
c, C = kamera(0.5, 4.5, 1.6, ziel_z=45.0)                                          # direkt unter der Traufe: Traufe verdeckt die Spitze
z_sp, g, _ = SU.foto_messen(maske(c), lambda X: FO.projektion(np.atleast_2d(X), c), AX, zs, C)
pruef(z_sp is None or abs(z_sp - Z_SPITZE) <= 0.3, f"Kamera unter der Traufe: {'verworfen (' + str(g) + ')' if z_sp is None else 'Spitze ' + str(z_sp)} - keine falsche Spitze")
pruef(SU.auswerten(mess[:3], zs, SU.SEKTOR_GRAD)["gueltig"] is False, "3 Fotos reichen nicht (MIN_FOTOS)")
# 23.11.2026 (Kettenlauf 1122o: 129 Fotos 'obere Bildkante unter der Suchhoehe', Laterne nie gebaut): Bildkante zwischen Spitze und Suchende -> trotzdem messen;
# Bildkante schneidet die Laterne -> verwerfen (keine falsche Spitze an der Bildkante)
def kamera_eng(az, dist, h, ziel_z, f=2500.0):
    c, C = kamera(az, dist, h, ziel_z); c["f_px"] = f; return c, C
for ziel, soll in ((32.0, "gemessen"), (28.0, "verworfen")):
    c, C = kamera_eng(1.0, 60.0, 1.6, ziel); oben = FO.projektion(np.array([[AX[0], AX[1], 58.0]]), c)[0][0, 1]
    z_sp, g, _ = SU.foto_messen(maske(c), lambda X, c=c: FO.projektion(np.atleast_2d(X), c), AX, zs, C)
    if soll == "gemessen": pruef(oben < 0 and z_sp is not None and abs(z_sp - Z_SPITZE) <= 0.3, f"Bildkante unter dem Suchende (z 58 bei y {oben:.0f} px), Spitze sichtbar: {z_sp} ({g})")
    else: pruef(z_sp is None, f"Bildkante schneidet die Laterne: {'verworfen (' + str(g) + ')' if z_sp is None else 'FALSCHE Spitze ' + str(z_sp)}")
# Offene Laterne: Himmel zwischen den Pfosten an der Achse (z 46,3..48,0, +-0,35 m) - das Achsenende dort ist KEINE Spitze (Probe 1122p: Einzelwerte 46,5..49,8 bei Median 52,6)
falsch = []
for i in range(6):
    c, C = kamera(2 * math.pi * i / 6 + 0.2, 60.0, 1.6); m = maske(c).copy(); b = np.array([AX[0] - C[0], AX[1] - C[1], 0.0]); b /= np.linalg.norm(b); q = np.array([-b[1], b[0], 0.0])
    for z in np.arange(46.3, 48.0, 0.02):
        P2 = np.array([[AX[0], AX[1], z]]) + np.outer(np.linspace(-0.35, 0.35, 15), q); p2 = np.round(FO.projektion(P2, c)[0]).astype(int)
        for (x_, y_) in p2:
            if 0 <= y_ < HI and 0 <= x_ < WI: m[max(0, y_ - 1):y_ + 2, max(0, x_ - 1):x_ + 2] = True
    z_sp, g, _ = SU.foto_messen(m, lambda X, c=c: FO.projektion(np.atleast_2d(X), c), AX, zs, C)
    if z_sp is not None and z_sp < Z_SPITZE - 1.0: falsch.append(round(z_sp, 2))
pruef(not falsch, f"offene Laterne: keine Spitze in der Pfostenluecke ({falsch or 'keine'})")
import bauteile as BT
ab = BT.spitze_ab(dict(E, achse=AX.tolist()))
pruef(ab is not None and Z_TRAUFE + 4 < ab <= Z_KREMPE, f"spitze_ab {ab}: Fotoblock ab Laternenhals (zwischen {Z_TRAUFE + 4} und {Z_KREMPE})")
pruef(BT.spitze_ab(dict(E, gueltig=False)) is None and BT.spitze_ab({}) is None, "spitze_ab ohne gueltigen Block = None")
# Generator: Wolkendach bis zum Hals + Fotolaterne + Spitze, Koerper reicht bis zur Spitze
from manifold3d import Manifold as M
o = AX; prof = [[round(z, 2), -h, h, -h, h, 500, []] for z in np.arange(Z_TRAUFE, 50.0, 0.5) for h in [querschnitt(z)[0]]]
import json, tempfile
with tempfile.TemporaryDirectory() as td:
    pj = os.path.join(td, "dach_profil.json"); json.dump(dict(o=o.tolist(), d=[1, 0], n=[0, 1], z0=Z_TRAUFE, schritt=0.5, wand_halb=[3, 3], scheiben=prof, spitze_foto=dict(E, achse=AX.tolist())), open(pj, "w"))
    k, bel = BT.dach_aus_profil(M.cube((6, 6, 40)).translate((AX[0] - 3, AX[1] - 3, 0)), pj)
    zt = k.bounding_box()[5]
    pruef(abs(zt - E["spitze_z"]) < 0.05 and k.num_vert() > 0 and k.genus() >= 0, f"Generator: Koerper bis z {zt:.2f} (Spitze {E['spitze_z']}), Beleg Laterne: {any('Foto-Silhouetten' in b['element'] for b in bel)}")

# ---- B: Durchfahrt ----------------------------------------------------------------------------------------------------------------------------
rng = np.random.default_rng(3); o = np.array([0.0, 0.0]); d = np.array([0.0, 1.0]); n = np.array([1.0, 0.0]); DICKE = 11.0
x = dict(u=0.0, breite=4.8, kaempfer=3.2, scheitel=6.2, unten=0.0)
stoer = np.c_[-rng.uniform(0, DICKE, 4000), rng.uniform(-6, 6, 4000), rng.uniform(0, 8, 4000)]          # Streupunkte im ganzen Turm (w = -x)
def laibung(tiefe, n_=6000):
    w = rng.uniform(0, tiefe, n_); s = rng.choice([-1, 1], n_); return np.c_[-w, s * 2.4 + rng.normal(0, 0.05, n_), rng.uniform(0.3, 3.2, n_)]
tor = np.vstack([stoer, laibung(DICKE)])
nische = np.vstack([stoer, laibung(0.6, 800), np.c_[-0.6 + rng.normal(0, 0.03, 6000), rng.uniform(-2.4, 2.4, 6000), rng.uniform(0, 3.2, 6000)]])
P1 = DP.pruefen(tor, o, d, n, x, DICKE); P2 = DP.pruefen(nische, o, d, n, x, DICKE); P3 = DP.pruefen(stoer, o, d, n, x, DICKE)
pruef(P1["ok"], f"Torweg durchgehend erkannt ({P1.get('gesehen_anteil')}, Deckung {P1.get('max_deckung')})")
pruef(not P2["ok"], f"Nische nicht als Durchfahrt ({P2.get('grund')})")
pruef(not P3["ok"], f"massive Wand mit Streupunkten nicht als Durchfahrt ({P3.get('grund')})")
lauter = np.vstack([tor, np.c_[-5.5 + rng.normal(0, 0.03, 8000), rng.uniform(-2.4, 2.4, 8000), rng.uniform(0, 3.2, 8000)]])     # Torweg mit Quermauer in der Mitte
pruef(not DP.pruefen(lauter, o, d, n, x, DICKE)["ok"], "Torweg mit Quermauer (Rueckwand bei 5,5 m) nicht als Durchfahrt")

print(f"{'FEHLER: ' + str(len(fehler)) if fehler else 'alle Tests bestanden'}")
sys.exit(1 if fehler else 0)
