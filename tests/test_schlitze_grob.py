#!/usr/bin/env python3
"""test_schlitze_grob.py - Rot-Probe Befund 1122w West (24.11.2026): Schlitz/Luke oben fehlen, Eckquader oben fehlen.
Ursache: das feine Wandbild (1 cm, fassade_ortho --max-mpp 0,02) ist ueber ~27,5 m leer (Strassenfotos 2,4-3 cm/px), OWLv2 liefert fuer einen 2-3 Zellen breiten
Schlitz keinen Kasten; ortsteine zaehlte nur feine Einzelfotos (ueber 30 m: 1 Foto) - das grobe Wandbild (5 cm) zeigt die Zone in 15 Fotos.
Synthetische Wand 8 x 14 m: Putz, Ortsteine an beiden Kanten z 2..14, Schlitz 0,15 x 1,0 m (z 11-12), Luke 0,4 x 0,6 m, bekanntes Fenster (Fensterliste),
lichtabhaengiger dunkler Fleck (nur Mosaik + 1 Foto), dunkler Stein im Eckquaderwerk. Feines Wandbild nur bis z 9, grobes (5 cm) ganz.
  1. schlitze_wandbild: Schlitz + Luke gefunden (Lage/Mass aus Mehrfoto-Kanten), Fleck (Mehrheit), bekanntes Fenster (keine Dublette) nicht; Eintrag mit 'loch' + Tiefe.
  2. Rot: ohne grobes Wandbild nichts (Ursache 2); nur 2 grobe Fotos mit Schlitz -> Formfamilie verworfen.
  3. ortsteine: mit grobem Wandbild Zone bis z ~14 und Fotos aus dem groben Bild bestaetigt; ohne (alter Weg) endet die Zone unter z 9,5.
  4. Kettenstufe bauplan_schlitze in gesamtkette (nach nischen_fenster, vor loch_gewaende).
"""
import sys, os, json, numpy as np
HIER = os.path.dirname(os.path.abspath(__file__)); T = os.path.join(os.path.dirname(HIER), "tools"); sys.path.insert(0, T)
from pfade import temp_ordner
from PIL import Image
import schlitze_wandbild as SW, ortsteine as O
n_ok = 0


def ok(b, t):
    global n_ok
    if not b: print("FEHLER:", t); sys.exit(1)
    n_ok += 1; print("    ok", t)


UW, ZW, M = 8.0, 14.0, 0.5
U0, Z1 = -M, ZW + M
SCHLITZ = (3.95, 4.10, 11.0, 12.0); LUKE = (5.4, 5.8, 12.7, 13.3); FENSTER = (1.6, 2.4, 5.0, 6.4); FLECK = (5.9, 6.25, 9.9, 10.3); STEIN_DUNKEL = (0.1, 0.5, 12.05, 12.45)


def malen(c, zmax=None, schlitz=True, fleck=False, seed=0, versatz=(0.0, 0.0)):
    """RGB im Raster (u0 = -M, z1 = ZW + M, Zelle c). zmax: darueber keine Daten (feines Bild an der Aufloesungsgrenze). versatz (du, dz) = Kamera-/Ebenenfehler."""
    rng = np.random.default_rng(seed)
    nu, nz = int(round((UW + 2 * M) / c)), int(round((ZW + 2 * M) / c))
    U, Z = np.meshgrid(U0 + (np.arange(nu) + 0.5) * c - versatz[0], Z1 - (np.arange(nz) + 0.5) * c - versatz[1])
    a = np.zeros((nz, nu, 3), np.float32); a[:] = (150, 190, 235)                                   # Himmel
    wand = (U >= 0) & (U <= UW) & (Z >= 0) & (Z <= ZW); a[wand] = (232, 232, 226)
    for u_k, r_ in ((0.0, 1), (UW, -1)):                                                          # Ortsteine lang/kurz, Lagen 0,5 m, Lagerfuge dunkel
        for q, z in enumerate(np.arange(2.0, ZW, 0.5)):
            L = 1.0 if q % 2 == 0 else 0.6; uu = (U - u_k) * r_
            m = wand & (uu >= 0) & (uu <= L) & (Z >= z) & (Z < z + 0.5); a[m] = (165, 85, 68)
            a[wand & (uu >= 0) & (uu <= L) & (np.abs(Z - z) < 0.015)] = (120, 70, 60)
    a[(U >= 0) & (U < 2.5) & (Z < 2.0) & wand] = (160, 82, 66)                                     # Sockelquader
    box = lambda b: (U >= b[0]) & (U <= b[1]) & (Z >= b[2]) & (Z <= b[3])
    a[box(FENSTER)] = (30, 30, 34)
    if schlitz: a[box(SCHLITZ)] = (24, 24, 28); a[box(LUKE)] = (28, 26, 30)
    if fleck: a[box(FLECK)] = (70, 70, 72)
    a[box(STEIN_DUNKEL)] = (60, 45, 42)
    a += rng.normal(0, 4, a.shape)
    a = np.clip(a, 0, 255).astype(np.uint8)
    if zmax is not None: a[Z > zmax] = 0
    return a


def ordner_anlegen(wurzel, fein_fotos=4, grob_fotos=4, grob_mit_schlitz=None, grob=True):
    fe, gr = os.path.join(wurzel, "fassade_fein"), os.path.join(wurzel, "fassade"); os.makedirs(os.path.join(fe, "ortho_f00_einzeln")); os.makedirs(os.path.join(gr, "ortho_f00_einzeln"))
    F = dict(id="f00", o=[0.0, 0.0], d=[1.0, 0.0], n=[0.0, -1.0], u=[0.0, UW], z=[0.0, ZW], polys_uz=[[[0, 0], [UW, 0], [UW, ZW], [0, ZW]]])
    for d_, c in ((fe, 0.01), (gr, 0.05)):
        nu, nz = int(round((UW + 2 * M) / c)), int(round((ZW + 2 * M) / c))
        json.dump(dict(fassaden=[dict(F, raster=dict(u0=U0, z1=Z1, nu=nu, nz=nz, zelle=c))]), open(os.path.join(d_, "fassaden.json"), "w"))
    json.dump({"f00": dict(fotos=[dict(foto=f"p{i}", rolle="ausgerichtet") for i in range(fein_fotos)])}, open(os.path.join(fe, "fein.json"), "w"))
    Image.fromarray(malen(0.01, zmax=9.0)).save(os.path.join(fe, "ortho_f00_fein.png"))
    for i in range(fein_fotos): Image.fromarray(malen(0.01, zmax=9.0, seed=10 + i, versatz=(0.02 * i, 0.0))).save(os.path.join(fe, "ortho_f00_einzeln", f"p{i}.png"))
    if grob:
        Image.fromarray(malen(0.05, fleck=True, seed=5)).save(os.path.join(gr, "ortho_f00.png"))
        gm = grob_fotos if grob_mit_schlitz is None else grob_mit_schlitz
        for i in range(grob_fotos): Image.fromarray(malen(0.05, schlitz=i < gm, fleck=(i == 0), seed=20 + i, versatz=(0.0, 0.05 * (i % 2)))).save(os.path.join(gr, "ortho_f00_einzeln", f"p{i}.png"))
    fa = os.path.join(wurzel, "fenster_auto.json")
    json.dump({"f00": dict(o=F["o"], d=F["d"], n=F["n"], fenster=[dict(u0=FENSTER[0], u1=FENSTER[1], z0=FENSTER[2], z1=FENSTER[3], teiler=[], kaempfer=None, scheiben=1, stimmen_min=5, sprossen=[])])},
              open(fa, "w"))
    return fa, gr, fe


def neue(fa):
    return [e for e in json.load(open(fa))["f00"]["fenster"] if "schlitze_wandbild" in e.get("quelle", "")]


def nahe(e, b, tol):
    return all(abs(e[k] - b[i]) <= tol for i, k in enumerate(("u0", "u1", "z0", "z1")))


# 1. Erkennung
w = temp_ordner("schlitze_"); fa, gr, fe = ordner_anlegen(w)
rc = SW.main([fa, gr, fe]); N = neue(fa)
ok(rc == 0, f"rc 0 (eingetragen), rc {rc}")
s = [e for e in N if nahe(e, SCHLITZ, 0.1)]; l_ = [e for e in N if nahe(e, LUKE, 0.1)]
ok(len(s) == 1, f"Schlitz 0,15 x 1,0 m ueber der Grenze des feinen Bilds gefunden (Kanten +-0,1 m): {[(e['u0'], e['u1'], e['z0'], e['z1']) for e in N]}")
ok(len(l_) == 1, "Luke 0,4 x 0,6 m gefunden")
ok(len(N) == 2, f"sonst nichts (Fleck nur in 1 Foto, dunkler Stein im Eckquaderwerk, bekanntes Fenster): {len(N)} Eintraege")
e = s[0]
ok(e["stimmen_min"] >= 3 and "von" in e["form_quelle"] and e.get("loch") and e["bogen"]["form"] == "gerade", "Eintrag: Fotozahl, form_quelle, loch, Rechteck")
ok(e["tiefe"] > 0 and "ANNAHME" in e["tiefe_quelle"], "Tiefe ohne Sweep = ANNAHME (benannt)")
ok(abs(e["aufloesung_m"] - 0.05) < 1e-6, "Aufloesung des groben Bilds im Eintrag")
ok(os.path.exists(os.path.join(w, "schlitze_f00.jpg")) and os.path.exists(os.path.join(w, "fenster_auto_vor_schlitze.json")), "Beleg-Bild + Eingang gesichert")
B = json.load(open(os.path.join(w, "schlitze_wandbild.json")))["f00"]
ok(any("sehenden Fotos" in x.get("grund", "") or "Formfamilie" in x.get("grund", "") for x in B["verworfen"] if nahe(x, FLECK, 0.15)), "Fleck verworfen: lichtabhaengig (Mehrheit/Formfamilie)")
ok(SW.main([fa, gr, fe]) == 3 and len(neue(fa)) == 2, "zweiter Lauf: keine Dubletten (bekannte Oeffnung)")

# 2. Rot-Proben
w2 = temp_ordner("schlitze_"); fa2, gr2, fe2 = ordner_anlegen(w2, grob=False)
ok(SW.main([fa2, gr2, fe2]) == 3 and not neue(fa2), "ohne grobes Wandbild: Schlitz/Luke nicht sichtbar (feines Bild endet bei z 9) - Ursache des Befunds")
w3 = temp_ordner("schlitze_"); fa3, gr3, fe3 = ordner_anlegen(w3, grob_mit_schlitz=2)
SW.main([fa3, gr3, fe3])
ok(not [e for e in neue(fa3) if nahe(e, SCHLITZ, 0.1)], "nur 2 grobe Fotos zeigen den Schlitz: Formfamilie < 3 -> nicht eingetragen")

# 3. Ortsteine mit grobem Wandbild
FF = json.load(open(os.path.join(fe, "fassaden.json")))["fassaden"][0]
alt = O.fassade_ortsteine(FF, fe, gr, grob_dir="")
neu = O.fassade_ortsteine(FF, fe, gr)
z_alt = max([K["z1"] for K in alt["kanten"]] + [0.0]); z_neu = max([K["z1"] for K in neu["kanten"]] + [0.0])
ok(z_alt < 9.5, f"alter Weg (nur feine Einzelfotos): Ortsteinzone endet an der Aufloesungsgrenze (z {z_alt:.1f})")
ok(z_neu >= 13.0, f"mit grobem Wandbild: Zone bis z {z_neu:.1f} (>= 13)")
ok(neu.get("einzeln_grob", {}).get("fotos_mit_grob", 0) == 4 and all(K["fotos_bestaetigt"] >= 3 for K in neu["kanten"]), "grobe Fotos je Foto einmal vereint, Formfamilie >= 3 bestaetigt")
ok(len({K["ende"] for K in neu["kanten"] if K["z1"] >= 13.0}) == 2, "beide Kanten bis oben")

# 4. Kettenstufe
g = open(os.path.join(T, "gesamtkette.py")).read()
ok("bauplan_schlitze" in g and g.index("bauplan_nischen_fenster") < g.index("bauplan_schlitze") < g.index("bauplan_loch_gewaende"), "Kettenstufe bauplan_schlitze nach nischen_fenster, vor loch_gewaende")
print(f"ALLE {n_ok} PROBEN BESTANDEN")
