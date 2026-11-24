#!/usr/bin/env python3
"""test_ortsteine.py - Rot-Probe Ortsteine/Eckverzahnung aus dem Wandbild (tools/ortsteine.py, 24.11.2026).
Anlass: Schwabentor-1122 (Lauf 1122u/v) - Foto Sued/Nord zeigt an allen Turmkanten versetzte rote Sandstein-Eckquader, Modell: Kanten glatt.
Synthetische Wand 12 x 18 m (Wandbild 1 cm): weisser Putz, an beiden Kanten Ortsteine abwechselnd 1,0 / 0,6 m lang, Lagen 0,5 m (z 3..15), darunter volles
Quadermauerwerk (darf KEINE Ortsteinzone sein), LoD2-Kante 0,2 m neben der Fotokante, Einzelbilder: 3 deckungsgleich + 1 versetztes (stimmt nicht mit).
  1. Erkennung: beide Kanten, Zone z 3..15 (+-0,3), Lagen 24 +-3, lang 1,0 / kurz 0,6 (+-0,12), Zahnung >= 0,8, Fotokante erkannt, 3 Fotos bestaetigen.
  2. Vorsprung aus dem Ebenen-Sweep (Stein +5 cm) gemessen; ohne Sweep -> None (ANNAHME im Bau).
  3. Bau: Bloecke vor der echten Flaeche, Vorsprung im Modell, ein Koerper, lang/kurz im Modell; Druckmass (Lage, Breite >= MINMM).
  4. Gegenproben: Putzwand ohne Steine -> nichts; nur 2 bestaetigende Fotos -> nicht gebaut; fassaden_kette.anbauen ruft ortsteine_anbauen (Generator ruft nur auf).
"""
import os, sys, json, numpy as np
HIER = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HIER)
from pfade import temp_ordner
from PIL import Image
import ortsteine as O
n_ok = 0


def ok(b, t):
    global n_ok
    if not b: print("FEHLER:", t); sys.exit(1)
    n_ok += 1; print("    ok", t)


C = 0.01; UW, ZW = 12.0, 18.0; MARGE = 0.5; LOD2_VERSATZ = 0.2; Z_A, Z_E, LAGE, LANG, KURZ = 3.0, 15.0, 0.5, 1.0, 0.6
rng = np.random.default_rng(3)


def wandbild(ortsteine=True):
    """RGB-Wandbild im fassade_fein-Raster (Zeile 0 = z1 = ZW + MARGE). Wand u 0..UW (Fotokante = LoD2 + LOD2_VERSATZ)."""
    nu, nz = int((UW + 2 * MARGE) / C), int((ZW + 2 * MARGE) / C)
    uu = -MARGE + (np.arange(nu) + 0.5) * C; zz = ZW + MARGE - (np.arange(nz) + 0.5) * C; U, Z = np.meshgrid(uu, zz)
    img = np.zeros((nz, nu, 3), np.float32); wand = (U >= LOD2_VERSATZ) & (U <= UW - LOD2_VERSATZ) & (Z >= 0) & (Z <= ZW)
    img[wand] = (232, 230, 226)
    stein = np.zeros(U.shape, bool)
    if ortsteine:
        k = np.floor((Z - Z_A) / LAGE).astype(int); lang = (k % 2 == 0); b = np.where(lang, LANG, KURZ)
        zone = (Z >= Z_A) & (Z < Z_E)
        stein |= zone & (U >= LOD2_VERSATZ) & (U < LOD2_VERSATZ + b)
        stein |= zone & (U <= UW - LOD2_VERSATZ) & (U > UW - LOD2_VERSATZ - np.where(lang, KURZ, LANG))
        stein |= (Z < Z_A) & wand                                             # volles Quadermauerwerk unten
    stein &= wand
    fuge = stein & ((((Z - Z_A) % LAGE) < 0.02) | (((Z % 0.4) < 0.02) & (Z < Z_A)))
    img[stein] = (150, 80, 60); img[fuge] = (70, 60, 55)
    img[wand] += rng.normal(0, 6, (int(wand.sum()), 3))
    return np.clip(img, 0, 255).astype(np.uint8), stein


def ordner(ortsteine=True, n_gut=3, sweep=True):
    d = temp_ordner("test_ortsteine_"); fein = os.path.join(d, "fassade_fein"); fa = os.path.join(d, "fassade"); os.makedirs(os.path.join(fein, "ortho_f00_einzeln")); os.makedirs(fa)
    img, stein = wandbild(ortsteine)
    F = dict(id="f00", o=[0.0, 0.0], d=[1.0, 0.0], n=[0.0, -1.0], u=[0.0, UW], z=[0.0, ZW], raster=dict(u0=-MARGE, z1=ZW + MARGE, nu=img.shape[1], nz=img.shape[0], zelle=C))
    json.dump(dict(fassaden=[F]), open(os.path.join(fein, "fassaden.json"), "w"))
    json.dump(dict(f00=dict(fotos=[dict(foto="a", rolle="bezug")] + [dict(foto=f"b{i}", rolle="ausgerichtet") for i in range(n_gut - 1)])), open(os.path.join(fein, "fein.json"), "w"))
    Image.fromarray(img).save(os.path.join(fein, "ortho_f00_fein.png"))
    for i in range(n_gut): Image.fromarray(img).save(os.path.join(fein, "ortho_f00_einzeln", f"gut{i}.png"))
    Image.fromarray(np.roll(img, 70, axis=1)).save(os.path.join(fein, "ortho_f00_einzeln", "versetzt.png"))     # 0,7 m seitlich versetzt: darf nicht mitstimmen
    if sweep:
        c4 = 0.04; nu4, nz4 = int(UW / c4), int(ZW / c4); jj = ((np.arange(nu4) + 0.5) * c4 + MARGE) / C; ii = (MARGE + (np.arange(nz4) + 0.5) * c4) / C
        st4 = stein[np.ix_(ii.astype(int), jj.astype(int))]; w = np.where(st4, 0.05, 0.0) + rng.normal(0, 0.005, st4.shape)
        np.savez(os.path.join(fa, "tiefe_f00.npz"), w=w.astype(np.float32), gut=np.ones_like(st4), sicher=np.ones(st4.shape, np.float32), u0=0.0, z1=ZW, zelle=c4)
    return fein


# 1 Erkennung
fein = ordner()
J = O.ortsteine_erkennen(fein); Fa = J["fassaden"][0]; K = {k["ende"]: k for k in Fa["kanten"]}
print("   ", [(k["ende"], k["z0"], k["z1"], k["lagen"], k["lang_m"], k["kurz_m"], k["zahnung"], k["vorsprung_m"], k["fotos_bestaetigt"], k["u_stein"]) for k in Fa["kanten"]])
ok(set(K) == {"anfang", "ende"} and len(Fa["kanten"]) == 2, f"beide Kanten je eine Zone ({len(Fa['kanten'])} Zonen)")
ok(all(abs(k["z0"] - Z_A) <= 0.3 and abs(k["z1"] - Z_E) <= 0.3 for k in K.values()), "Zone z 3..15 (volles Mauerwerk darunter ist keine Ortsteinzone)")
ok(all(abs(k["lagen"] - (Z_E - Z_A) / LAGE) <= 3 for k in K.values()), f"Lagen {[k['lagen'] for k in K.values()]} ~ 24")
ok(all(abs(k["lang_m"] - LANG) <= 0.12 and abs(k["kurz_m"] - KURZ) <= 0.12 for k in K.values()), f"lang/kurz {[(k['lang_m'], k['kurz_m']) for k in K.values()]} ~ 1,0/0,6")
ok(all(k["zahnung"] >= 0.8 for k in K.values()), "Zahnung lang/kurz im Wechsel")
ok(abs(K["anfang"]["u_stein"] - LOD2_VERSATZ) <= 0.06 and abs(K["ende"]["u_stein"] - (UW - LOD2_VERSATZ)) <= 0.06, "Fotokante neben der LoD2-Kante erkannt")
ok(all(k["fotos_bestaetigt"] == 3 for k in K.values()), "Formfamilie aus 3 Fotos bestaetigt, versetztes Foto stimmt nicht mit")
# 2 Vorsprung
ok(all(k["vorsprung_m"] is not None and abs(k["vorsprung_m"] - 0.05) <= 0.015 for k in K.values()), "Vorsprung aus dem Ebenen-Sweep 5 cm")
J2 = O.ortsteine_erkennen(ordner(sweep=False)); ok(all(k["vorsprung_m"] is None for k in J2["fassaden"][0]["kanten"]), "ohne Sweep: Vorsprung None (Bau: ANNAHME Druckmass)")
# 3 Bau
from manifold3d import Manifold as M
koerper = M.cube((UW, 8.0, 20.0)).translate((0.0, 0.0, 0.0))                 # Wand bei y = 0, aussen = -y (n)
k2, bel = O.ortsteine_bauen(koerper, J)
me = k2.to_mesh(); V = np.asarray(me.vert_properties)[:, :3]
ok(k2.volume() > koerper.volume() + 0.5 and len(k2.decompose()) == 1, f"Bloecke angebaut, ein Koerper (+{k2.volume() - koerper.volume():.2f} m3)")
ok(abs(-V[:, 1].min() - 0.05) <= 0.01, f"Vorsprung im Modell {-V[:, 1].min():.3f} m")
gb = [g for b in bel if "ortsteine" in b for g in b["ortsteine"]]
ok(len(gb) >= 40 and min(g["z1"] - g["z0"] for g in gb) >= O.druck_m(1.0) - 1e-6 and min(g["b"] for g in gb) >= O.druck_m(1.0) - 1e-6, f"{len(gb)} Steine, Lage/Breite >= Druckmass")
sl = k2.slice(9.25); sl2 = k2.slice(9.75)                                    # zwei Nachbarlagen: links lang/kurz wechselt
def vorn_bis(s):
    P = np.vstack([np.asarray(p) for p in s.to_polygons()]); v = P[P[:, 1] < -0.02]; return float(v[:, 0][v[:, 0] < UW / 2].max())
ok(abs(abs(vorn_bis(sl) - vorn_bis(sl2)) - (LANG - KURZ)) <= 0.12, f"lang/kurz im Modell (Kante links {vorn_bis(sl):.2f} / {vorn_bis(sl2):.2f} m)")
ok(V[:, 0].min() < -0.03, "Block um die Ecke gefuehrt (Vorsprung auch an der Nachbarseite)")
# 4 Gegenproben
J3 = O.ortsteine_erkennen(ordner(ortsteine=False)); ok(not J3["fassaden"][0]["kanten"], "Putzwand ohne Steine: keine Ortsteine")
J4 = O.ortsteine_erkennen(ordner(n_gut=2)); k4, b4 = O.ortsteine_bauen(koerper, J4)
ok(not J4["fassaden"][0]["kanten"] and abs(k4.volume() - koerper.volume()) < 1e-6, "nur 2 bestaetigende Fotos: Formfamilie nicht belegt, nichts gebaut")
src = open(os.path.join(HIER, "fassaden_kette.py")).read(); ok("ortsteine_anbauen(koerper, objekt_json)" in src, "fassaden_kette.anbauen ruft ortsteine_anbauen (Generator ruft nur auf)")
print(f"alle {n_ok} Ortstein-Pruefungen bestanden")
