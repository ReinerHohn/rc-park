#!/usr/bin/env python3
"""Test DOM1-Veto der Foto-Dachflaeche (23.11.2026, Schwabentor-1122p HOEHEN-TOR +1,73 m / k 0,958): dachflaeche_aus_umriss.laser_isolinien / ringe_dom1_veto /
veto_block + bauteile.flaeche_aus_foto. Synthetischer Laser: 56-Grad-Zeltdach (Spitze der Ebenen 45,5 m) mit flachem Aufschiebling bis zur Traufkante 7,0 m,
darueber eine Laterne (Laser dort blind). Die Foto-Ebene Traufkante 7,0 @ 37,5 -> Fuss 0,8 @ 45,9 steht wie am Schwabentor 1-1,7 m zu weit draussen."""
import sys, os, numpy as np
H_ = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, H_)
import dachflaeche_aus_umriss as DF

F = 0


def pr(ok, txt):
    global F; F += (not ok); print(("OK   " if ok else "FEHL ") + txt)


def laser(x, y):
    r = np.maximum(np.abs(np.asarray(x, float)), np.abs(np.asarray(y, float)))
    z = np.where(r <= 5.3, 45.5 - 1.48 * r, 37.65 - 0.15 * (r - 5.3) / 1.7)       # Ebene 56 Grad, Aufschiebling 5,3 -> 7,0 m
    z = np.where(r < 0.7, 49.0, z)                                                 # Laterne
    return np.where(r > 7.0, 0.5, z)                                               # Strasse vor der Traufkante (Klippe)


def flaeche_hoehe(rs, u, v):
    """Oberseite der Ringflaeche (hoechster Ring, der (u, v) noch umschliesst), Achse im Ursprung."""
    zt = np.nan
    for r in rs:
        if r[:, 0].min() <= u <= r[:, 0].max() and r[:, 1].min() <= v <= r[:, 1].max(): zt = r[0, 2]
    return zt


D = dict(o=[0.0, 0.0], d=[1.0, 0.0], n=[0.0, 1.0])
ZT, ZF = 37.5, 45.9
zs = np.round(np.arange(ZT, ZF + 0.5 + 1e-9, 0.1), 2)
iso = DF.laser_isolinien(D, laser, zs)

# T1 Isolinien: auf der Dachflaeche = Laser-Ebene (+-0,15 m, 0,1-m-Raster), nach oben nicht breiter; ganz oben (Sektor < 2 m2 Laserflaeche) blind = None
soll = lambda z: (45.5 - z) / 1.48
ok1 = all(iso[z][j] is not None and abs(iso[z][j] - soll(z)) <= 0.15 for z in (39.0, 40.0, 41.0, 42.0) for j in range(4))
top = iso[45.0] == [None] * 4
mono = all(iso[a][j] is None or iso[b][j] is None or iso[b][j] <= iso[a][j] + 1e-9 for a, b in zip(sorted(iso)[:-1], sorted(iso)[1:]) for j in range(4))
pr(ok1 and mono and top, f"T1 Isolinien = Laser-Ebene (z 40: {iso[40.0]}, soll {soll(40.0):.2f}), monoton nach oben")

# T2 Veto der zu breiten Foto-Ebene: Traufring bleibt, alle anderen Seiten <= Isolinie + tol, Flaechenhoehe ueber den Laser-Pixeln ~ Laser
eave = (np.zeros(2), np.array([1.0, 0]), np.array([0, 1.0]), -7.0, 7.0, -7.0, 7.0); fuss = (np.zeros(2), 0.8, None)
rA = DF.ringe(eave, fuss, ZT, ZF, 0.0, n=28); rB, ein = DF.ringe_dom1_veto(rA, D["o"], D["d"], D["n"], iso)
tr_ok = np.allclose(rB[0], rA[0])
inn = all(np.abs(r[:, :2]).max() <= (iso[min(iso, key=lambda z: abs(z - r[0, 2]))][0] or 99) + DF.VETO_TOL + 1e-6 for r in rB[1:])
px = [(u, 0.3) for u in np.arange(2.0, 5.01, 0.5)]
dA = np.median([flaeche_hoehe(rA, u, v) - float(laser(u, v)) for u, v in px]); dB = np.median([flaeche_hoehe(rB, u, v) - float(laser(u, v)) for u, v in px])
pr(tr_ok and inn and len(ein) > 0 and dA > 1.0 and abs(dB) <= 0.5, f"T2 Veto: {len(ein)} Eingriffe, Traufring unveraendert, Flaeche - Laser r 2..5: ohne Veto {dA:+.2f}, mit {dB:+.2f} m (Tor tol 0,5)")

# T3 passende Foto-Flaeche (innerhalb der Isolinie): kein Eingriff
rC = DF.ringe((np.zeros(2), np.array([1.0, 0]), np.array([0, 1.0]), -5.3, 5.3, -5.3, 5.3), (np.zeros(2), 0.8, None), 37.65, 44.3, 0.0, n=20)
_, ein_c = DF.ringe_dom1_veto(rC, D["o"], D["d"], D["n"], iso)
pr(len(ein_c) == 0, f"T3 Foto-Flaeche passt zum Laser: {len(ein_c)} Eingriffe")

# T4 Laser blind (keine Kachel / None) -> kein Veto
rD, ein_d = DF.ringe_dom1_veto(rA, D["o"], D["d"], D["n"], {z: [None] * 4 for z in zs})
pr(len(ein_d) == 0 and all(np.allclose(a, b) for a, b in zip(rA, rD)), "T4 Laser blind: Flaeche unveraendert")

# T5 Stufe -> Block -> Generator: veto_block schreibt Isolinien, bauteile.flaeche_aus_foto setzt sie um und nennt es im Beleg; ohne Block wie bisher
import bauteile as BT
FF = dict(gueltig=True, familie="gerade", c=0.5, z_traufe=ZT, z_fuss=ZF, achse=[0, 0], fuss=dict(halb=0.8, theta=None, quelle="t"))
V = DF.veto_block(D, {}, eave, fuss, ZT, FF, hoehe=laser)["dom1_veto"]
P = [[37.0, -6.5, 6.5, -6.5, 6.5, 50, []], [ZT, -7.0, 7.0, -7.0, 7.0, 50, []], [40.0, -4, 4, -4, 4, 50, []]]
D0 = dict(D, flaeche_foto=dict(FF)); D1 = dict(D, flaeche_foto=dict(FF, dom1_veto=V))
f0, b0 = BT.flaeche_aus_foto([list(p) for p in P], D0); f1, b1 = BT.flaeche_aus_foto([list(p) for p in P], D1)
d0 = np.median([flaeche_hoehe(f0[1], u, v) - float(laser(u, v)) for u, v in px]); d1 = np.median([flaeche_hoehe(f1[1], u, v) - float(laser(u, v)) for u, v in px])
pr(V["aktiv"] and V["eingriffe"] > 0 and "DOM1-VETO" in b1[0]["hinweis"] and "DOM1-VETO" not in b0[0]["hinweis"].upper() and len(f0[1]) == 13 and d0 > 1.0 and abs(d1) <= 0.5,
   f"T5 Generator: ohne Block {len(f0[1])} Ringe {d0:+.2f} m, mit Block {len(f1[1])} Ringe {d1:+.2f} m ueber dem Laser")

print("FEHLER:", F); sys.exit(1 if F else 0)
