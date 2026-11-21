#!/usr/bin/env python3
"""Test dachflaeche_aus_umriss.py + bauteile.flaeche_aus_foto (synthetisch, Sekunden): Profil-Familie aus gerenderten Silhouetten zurueckgewinnen,
Formfamilie nur aus >= 3 einigen Fotos, Fuss des Aufsatzes am Knick, Generator baut bei 'gerade' Ebenen ohne Absatz."""
import sys, os, math, numpy as np
H_ = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, H_)
import dachflaeche_aus_umriss as DF

F = 0; o = np.zeros(2); d = np.array([1.0, 0]); n = np.array([0, 1.0]); A = np.zeros(2)
EAVE = (o, d, n, -7.0, 7.0, -7.0, 7.0); FUSS = (A, 0.8, None); ZT, ZF = 38.0, 47.0


def pr(ok, txt):
    global F; F += (not ok); print(("OK   " if ok else "FEHL ") + txt)


def kamera(az, dist, h=2.0, W=1600, Hh=1200, f=1500.0):
    C = np.array([dist * math.cos(math.radians(az)), dist * math.sin(math.radians(az)), h]); Z = np.array([*(A - C[:2]), 44.0 - h]); Z /= np.linalg.norm(Z)
    X = np.cross(Z, [0, 0, 1.0]); X /= np.linalg.norm(X); Y = np.cross(Z, X)
    def proj(P):
        P = np.atleast_2d(P) - C; zc = P @ Z; return np.c_[f * (P @ X) / zc + W / 2, f * (P @ Y) / zc + Hh / 2], zc
    return proj, C, (Hh, W)


def laterne(): return [np.array([[A[0] + sx * 0.8, A[1] + sy * 0.8, z] for sx in (-1, 1) for sy in (-1, 1) for z in (ZF, ZF + 3)])]


def szene(c, az, dist):
    proj, C, sh = kamera(az, dist); un = [np.array([[x, y, z] for x in (-7, 7) for y in (-7, 7) for z in (37.0, ZT)]), np.array([[x, y, z] for x in (-6, 6) for y in (-6, 6) for z in (0, 37.0)])]
    M = DF.hypothese_maske(sh, proj, DF.ringe(EAVE, FUSS, ZT, ZF, c), un + laterne()); return M, proj, C, un


# T1: gerade und geschweift aus der eigenen Silhouette zurueck (Analyse durch Synthese)
zs = np.round(np.arange(ZT, ZF + 3, DF.SCHRITT), 2)
for c_soll in (0.0, 2.0, -1.5):
    M, proj, C, un = szene(c_soll, 20, 45)
    r = DF.foto_form(M, proj, A, zs, C, EAVE, FUSS, ZT, np.arange(ZF - 1, ZF + 0.6, 0.5), un)
    pr(r is not None and abs(r[0] - c_soll) <= 0.25 and abs(r[1] - ZF) < 0.01 and r[2][(r[1], r[0])] < 0.05, f"T1 c {c_soll:+.1f} -> c {r[0] if r else None} Fuss {r[1] if r else None}")

# T2: Fuss am Knick (Breite nimmt ab, darueber Laterne senkrecht)
M, proj, C, un = szene(0.0, 30, 45); hz = DF.breite_messen(M, proj, A, zs, C); h = np.array([hz.get(round(float(z), 2), np.nan) for z in zs]); f = DF.fuss_finden(zs, h)
pr(f is not None and ZF - 0.2 <= f[0] <= ZF + 1.5, f"T2 Knick der Breite z {f[0] if f else None} (Fuss {ZF}; von unten hoeher - nur Startwert fuer die Synthese)")

# T3: Familie nur bei Konsens aus >= 3 guten Fotos
j = lambda c, fe=0.1, n=60: dict(foto="x", c=c, fehler=fe, fehler_gerade=0.2, hoehen=n)
E = DF.auswerten([j(0.0), j(0.25), j(-0.25), j(0.5)], 80); pr(E["gueltig"] and E["familie"] == "gerade", f"T3a gerade {E.get('familie')} {E.get('grund')}")
E = DF.auswerten([j(0.0), j(2.0)], 80); pr(not E["gueltig"], f"T3b 2 Fotos verworfen: {E.get('grund')}")
E = DF.auswerten([j(-2.5), j(-2.0), j(0.0), j(2.0), j(2.5), j(3.0)], 80); pr(not E["gueltig"], f"T3c uneins verworfen: {E.get('grund')}")
E = DF.auswerten([j(0.0, fe=0.8), j(0.0, n=10), j(0.0, fe=0.5), j(0.25)], 80); pr(not E["gueltig"], f"T3d schlechte Fotos zaehlen nicht: {E.get('grund')}")

# T4: Generator - gerade Ebenen von der Traufe bis zum Fuss, kein Absatz, Wolkenscheiben darueber entfallen; Guard
import bauteile as BT
D = dict(o=[0, 0], d=[1, 0], n=[0, 1], flaeche_foto=dict(gueltig=True, familie="gerade", c=0.5, z_traufe=ZT, z_fuss=ZF, achse=[0, 0], fuss=dict(halb=0.8, theta=None, quelle="t")))
P = [[37.0, -6.5, 6.5, -6.5, 6.5, 50, False], [38.0, -7, 7, -7, 7, 50, False], [40.0, -4, 4, -4, 4, 50, False], [44.0, -3.5, 3.5, -3.5, 3.5, 50, False]]
fl, bel = BT.flaeche_aus_foto(P, D)
ok = fl is not None and fl[0] == 1 and len(bel) == 1 and "gebaut c 0.0" in bel[0]["element"]
if ok:
    rs = fl[1]; zr = [r[0, 2] for r in rs]; hr = [abs(r[0, 0]) for r in rs]; ok = all(abs(abs(r[0, 0]) - abs(r[0, 1])) < 1e-6 for r in rs)   # Grat auf der Diagonale
    lin = np.allclose(np.diff(zr), np.diff(zr)[0]) and np.allclose(np.diff(hr), np.diff(hr)[0])
    ok = ok and lin and abs(zr[0] - ZT) < 1e-6 and abs(zr[-1] - ZF) < 1e-6 and abs(hr[-1] - 0.8) < 1e-6
pr(ok, "T4a gerade: Ebenen Traufe 38 -> Fuss 47 (halb 0.8), gleichmaessig, c 0 gebaut")
D["flaeche_foto"]["z_fuss"] = 38.5; fl, bel = BT.flaeche_aus_foto(P, D); pr(fl is None and "Guard" in bel[0]["element"], "T4b Guard Fuss zu tief")
D["flaeche_foto"]["gueltig"] = False; fl, bel = BT.flaeche_aus_foto(P, D); pr(fl is None and not bel, "T4c ungueltig -> Wolkenscheiben bleiben")

print("FEHLER", F); sys.exit(1 if F else 0)
