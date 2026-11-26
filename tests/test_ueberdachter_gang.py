#!/usr/bin/env python3
"""test_ueberdachter_gang.py - fester synthetischer Test fuer bauteile.ueberdachter_gang (26.11.2026, SPEC_SCHWABENTOR_DEMONSTRATOR Anforderung 4), < 10 s, nur CPU.

Baustein: ueberdachter Gang mit Treppe (Bruecke ueber eine Strasse zwischen zwei Baukoerpern), alle Masse aus einem JSON-dict, keine festen Objektmasse.
Geprueft wird nur der PARAMETRISCHE Baustein (Kopplung an den Fotokanten-Sweep ist nicht Teil davon). Die Masse unten sind frei gewaehlte Testzahlen.
Teile:
  1 GANG       ein Koerper, wasserdicht, hohl (Laufraum frei), Wand/Boden/Dach voll, Ausdehnung = Spannweite + Einbinden, Breite + Ueberstand.
  2 TREPPE     innen: Stufenzahl, Steigung und Auftritt am Koerper nachgemessen (Oberkante je Auftritt); aussen: Treppe vor dem Gangende abwaerts.
  3 PARAMETER  andere Stufenzahl / Spannweite -> anderer Koerper (kein Hardcoding); Achse a->b im Modellrahmen legt Lage, Richtung und Spannweite fest.
  4 DACH       flach / pult / sattel: First bzw. hohe Seite dort, wo die Form es verlangt.
  5 DRUCK      Wandstaerke unter 0,8 mm (1:87) -> auf das Mindestmass angehoben (im Beleg), am Koerper nachgemessen.
  6 GUARD      widerspruechliche Treppe, Treppe laenger als der Gang, Treppe durchs Dach, zu flache Stufen (Rampe), unbekannte Dachform (flach),
               zu schmaler Gang (massiver Steg), Spannweite fehlt / widerspricht der Achse (nicht gebaut) - nie ein degenerierter Koerper.
"""
import sys, os, copy, math
import numpy as np
HIER = os.path.dirname(os.path.abspath(__file__)); WURZEL = os.path.dirname(HIER); sys.path.insert(0, os.path.join(WURZEL, "tools"))
from manifold3d import Manifold as M
F = 0


def pruef(ok, text):
    global F
    print(("  ok     " if ok else "  FEHLER ") + text)
    if not ok: F += 1


def drin(m, p, e=0.01):
    """Punkt p liegt im Koerper (Wuerfel mit Kante e ganz im Koerper)."""
    return (m ^ M.cube([e, e, e], center=True).translate(tuple(p))).volume() > 0.9 * e ** 3


def frei(m, p, e=0.01):
    return (m ^ M.cube([e, e, e], center=True).translate(tuple(p))).volume() < 0.1 * e ** 3


def oberkante(m, x, y, z_lo, z_hi, e=0.01):
    """Hoechste Koerperflaeche im senkrechten Stab bei (x, y) zwischen z_lo und z_hi (Stufenoberkante)."""
    s = m ^ M.cube([e, e, z_hi - z_lo]).translate((x - e / 2, y - e / 2, z_lo))
    return None if s.is_empty() else float(s.bounding_box()[5])


GRUND = dict(spannweite=6.4, breite=2.6, z_boden=5.5, hoehe=2.3, boden_dicke=0.25, wand_dicke=0.18, einbinden=0.3,
             dach=dict(form="sattel", neigung_grad=30.0, ueberstand=0.25, dicke=0.12),
             seiten=dict(art="geschlossen"),
             treppe=dict(lage="innen", ende="a", stufen=5, steigung=0.16, auftritt=0.30))


def main():
    try:
        from bauteile import ueberdachter_gang as _ug, als_trimesh
    except ImportError as ex:
        pruef(False, f"bauteile.ueberdachter_gang fehlt ({ex})"); return
    gebaut = []
    def ueberdachter_gang(*a, **k):
        r = _ug(*a, **k)
        if r[0] is not None: gebaut.append(r[0])
        return r
    # ---- 1 GANG
    P = copy.deepcopy(GRUND); g, bel, ms = ueberdachter_gang(P, massstab=87.0, min_mm=0.8)
    pruef(g is not None and not g.is_empty(), "Gang gebaut")
    if g is None or g.is_empty(): return
    pruef(len(g.decompose()) == 1 and g.genus() >= 0 and str(g.status()).endswith("NoError"), f"ein wasserdichter Koerper (Teile {len(g.decompose())}, genus {g.genus()})")
    bb = g.bounding_box(); L, B, e, u = 6.4, 2.6, 0.3, 0.25
    pruef(abs(bb[0] + e) < 1e-6 and abs(bb[3] - (L + e)) < 1e-6, f"Laenge = Spannweite + 2 x Einbinden: x {bb[0]:.3f}..{bb[3]:.3f}")
    pruef(abs(bb[1] + B / 2 + u) < 1e-6 and abs(bb[4] - B / 2 - u) < 1e-6, f"Breite + Dachueberstand: y {bb[1]:.3f}..{bb[4]:.3f}")
    zt = 5.5 + 2.3; t = 0.18; yi = B / 2 - t; a30 = math.radians(30.0)
    z_first = zt + yi * math.tan(a30) + 0.12 / math.cos(a30)
    pruef(abs(bb[5] - z_first) < 1e-6, f"Firsthoehe aus Neigung/Dicke: {bb[5]:.3f} (soll {z_first:.3f})")
    pruef(abs(bb[2] - (5.5 - 0.25)) < 1e-6, f"Unterkante Boden {bb[2]:.3f} (soll {5.5 - 0.25:.3f})")
    xm = 4.5                                                     # hinter der Treppe
    pruef(frei(g, (xm, 0.0, 5.5 + 0.8 + 1.0)), "Laufraum frei (hohl)")
    pruef(drin(g, (xm, B / 2 - t / 2, zt - 0.3)) and drin(g, (xm, -B / 2 + t / 2, zt - 0.3)), "beide Seitenwaende voll")
    pruef(frei(g, (xm, B / 2 + 0.05, zt - 0.3)), "vor der Wand frei (Wand nicht zu dick)")
    pruef(drin(g, (xm, 0.0, 5.5 - 0.12)), "Boden voll")
    pruef(drin(g, (xm, 0.0, zt + yi * math.tan(a30) + 0.05)) and frei(g, (xm, 0.0, zt + yi * math.tan(a30) - 0.05)), "Dach am First voll, darunter frei")
    pruef(frei(g, (-e - 0.05, 0.0, 6.5)) and frei(g, (L + e + 0.05, 0.0, 6.5)), "Gangenden offen (Einbinden endet)")
    # ---- 2 TREPPE innen (Ende a, steigt Richtung b)
    ok_st = True
    for i in range(5):
        z = oberkante(g, (i + 0.5) * 0.30, 0.0, 5.5 - 0.1, zt - 0.5)
        ok_st &= z is not None and abs(z - (5.5 + (i + 1) * 0.16)) < 1e-6
    pruef(ok_st, "5 Stufen: Oberkante je Auftritt = z_boden + (i+1) x Steigung")
    z_ob = oberkante(g, 3.0, 0.0, 5.5 - 0.1, zt - 0.5)
    pruef(z_ob is not None and abs(z_ob - (5.5 + 5 * 0.16)) < 1e-6, f"oberer Boden nach der Treppe {z_ob}")
    stufen_gez = len({round(oberkante(g, x, 0.0, 5.5 - 0.1, zt - 0.5), 3) for x in np.arange(0.005, 1.6, 0.02)})
    pruef(stufen_gez == 5,f"Hoehenstufen im Treppenbereich gezaehlt: {stufen_gez} (soll 5)")
    pruef(ms.get("treppe") == "gebaut" and ms.get("stufen") == 5, "Masse melden Treppe gebaut, 5 Stufen")
    # ---- 2b TREPPE aussen an Ende b (abwaerts weg vom Gang)
    P2 = copy.deepcopy(GRUND); P2["treppe"] = dict(lage="aussen", ende="b", stufen=8, steigung=0.17, lauflaenge=8 * 0.28, platte=0.12)
    g2, _, ms2 = ueberdachter_gang(P2)
    bb2 = g2.bounding_box()
    pruef(abs(bb2[3] - (L + e + 8 * 0.28)) < 1e-6, f"Aussentreppe haengt hinter Ende b: x bis {bb2[3]:.3f} (soll {L + e + 8 * 0.28:.3f})")
    pruef(abs(bb2[2] - (5.5 - 8 * 0.17 - max(0.12, 0.0696) / math.cos(math.atan(0.17 / 0.28)))) < 1e-3, f"Fuss der Aussentreppe z {bb2[2]:.3f}")
    z_unten = oberkante(g2, L + e + 8 * 0.28 - 0.14, 0.0, 0.0, 9.0)
    pruef(z_unten is not None and abs(z_unten - (5.5 - 7 * 0.17)) < 1e-6, f"unterste Stufe aussen z {z_unten}")
    pruef(len(g2.decompose()) == 1, "Gang + Aussentreppe ein Koerper")
    # ---- 3 PARAMETER: andere Werte -> anderer Koerper
    P3 = copy.deepcopy(GRUND); P3["treppe"]["stufen"] = 8; P3["spannweite"] = 9.1
    g3, _, ms3 = ueberdachter_gang(P3)
    pruef(abs(g3.bounding_box()[3] - (9.1 + e)) < 1e-6 and ms3.get("stufen") == 8, "Spannweite 9,1 / 8 Stufen uebernommen")
    z8 = oberkante(g3, 7.5 * 0.30, 0.0, 5.5 - 0.1, zt - 0.5)
    pruef(z8 is not None and abs(z8 - (5.5 + 8 * 0.16)) < 1e-6, "8. Stufe auf 8 x Steigung")
    P4 = copy.deepcopy(GRUND); del P4["spannweite"]; P4["achse"] = dict(a=[10.0, 20.0], b=[10.0, 26.4])     # Achse in +y
    g4, _, ms4 = ueberdachter_gang(P4); bb4 = g4.bounding_box()
    pruef(abs(ms4.get("spannweite", 0) - 6.4) < 1e-9, "Spannweite aus der Achse")
    pruef(abs(bb4[1] - (20.0 - e)) < 1e-6 and abs(bb4[4] - (26.4 + e)) < 1e-6 and abs(bb4[0] - (10.0 - B / 2 - u)) < 1e-6, f"Lage/Richtung aus der Achse: {np.round(bb4, 3).tolist()}")
    # ---- 4 DACH
    for form, pr in (("flach", lambda b: abs(b[5] - (zt + 0.12)) < 1e-6), ("pult", lambda b: abs(b[5] - (zt + (2 * yi + u + t) * math.tan(a30) + 0.12 / math.cos(a30))) < 1e-6)):
        Pd = copy.deepcopy(GRUND); Pd["dach"]["form"] = form; gd, _, msd = ueberdachter_gang(Pd)
        pruef(gd is not None and pr(gd.bounding_box()) and msd.get("dach") == form, f"Dach {form}: Oberkante {gd.bounding_box()[5]:.3f}")
    Pd = copy.deepcopy(GRUND); Pd["dach"]["form"] = "pult"; gd, _, _ = ueberdachter_gang(Pd)
    pruef(drin(gd, (xm, B / 2 + 0.1, zt + (2 * yi + t + 0.1) * math.tan(a30) + 0.03)) and frei(gd, (xm, -B / 2 - 0.1, zt + 0.3)), "Pultdach hoch auf +y, niedrig auf -y")
    # ---- 5 DRUCK: Wand zu duenn
    P5 = copy.deepcopy(GRUND); P5["wand_dicke"] = 0.02; g5, bel5, ms5 = ueberdachter_gang(P5, massstab=87.0, min_mm=0.8)
    dmin = 0.8 * 87.0 / 1000.0
    pruef(abs(ms5.get("wand_dicke") - dmin) < 1e-9, f"Wandstaerke auf 0,8 mm x 87 angehoben: {ms5.get('wand_dicke')}")
    pruef(drin(g5, (xm, B / 2 - dmin + 0.006, zt - 0.3)) and frei(g5, (xm, B / 2 - dmin - 0.006, zt - 0.3)), "Wand am Koerper so dick wie das Mindestmass")
    pruef(any("angehoben" in str(b.get("hinweis", "")) for b in bel5), "Anhebung im Beleg")
    # ---- 6 GUARD
    def bau(**aend):
        Pg = copy.deepcopy(GRUND)
        for k, v in aend.items():
            if isinstance(v, dict) and isinstance(Pg.get(k), dict): Pg[k].update(v)
            else: Pg[k] = v
        return ueberdachter_gang(Pg)
    gw, bw, mw = bau(treppe=dict(lauflaenge=2.0))                                 # 5 x 0,30 = 1,5 != 2,0
    pruef(gw is not None and mw.get("treppe") == "nicht gebaut" and len(gw.decompose()) == 1, "widerspruechliche Lauflaenge -> Gang ohne Treppe")
    pruef(any("widerspr" in str(b.get("hinweis", "")).lower() for b in bw), "Grund im Beleg (widerspruechlich)")
    gw, _, mw = bau(treppe=dict(stufen=30))                                       # 9 m Lauf > 6,4 m Gang
    pruef(gw is not None and mw.get("treppe") == "nicht gebaut", "Treppe laenger als Gang -> nicht gebaut")
    gw, _, mw = bau(treppe=dict(stufen=5, steigung=0.45))                         # 2,25 m Hub, Dach bei 2,3 m
    pruef(gw is not None and mw.get("treppe") == "nicht gebaut", "Treppe stoesst ans Dach -> nicht gebaut")
    gw, bw, mw = bau(treppe=dict(steigung=0.05))                                  # 0,57 mm Stufe im Druck
    pruef(gw is not None and mw.get("treppe") == "rampe" and abs(oberkante(gw, 0.75, 0.0, 5.4, 7.0) - (5.5 + 0.125)) < 2e-3, "zu flache Stufen -> Rampe (Mitte auf halber Hoehe)")
    gw, _, mw = bau(dach=dict(form="zwiebel"))
    pruef(gw is not None and mw.get("dach") == "flach", "unbekannte Dachform -> Flachdach")
    gw, _, mw = bau(dach=dict(neigung_grad=89.0))
    pruef(gw is not None and mw.get("dach") == "flach", "Neigung 89 Grad -> Flachdach")
    gw, bw, mw = bau(breite=0.3)                                                  # kein Laufraum zwischen den Waenden
    pruef(gw is not None and mw.get("art") == "massiver Steg" and len(gw.decompose()) == 1, "zu schmal -> massiver Steg")
    Pn = copy.deepcopy(GRUND); del Pn["spannweite"]; gn, bn, mn = ueberdachter_gang(Pn)
    pruef(gn is None and bn and "nicht gebaut" in bn[0]["element"], "Spannweite fehlt -> nicht gebaut")
    Pn = copy.deepcopy(GRUND); Pn["achse"] = dict(a=[0.0, 0.0], b=[7.5, 0.0]); gn, bn, _ = ueberdachter_gang(Pn)
    pruef(gn is None and "widerspr" in bn[0]["hinweis"].lower(), "Spannweite widerspricht Achse -> nicht gebaut (Quellen nicht mitteln)")
    gn, _, _ = bau(hoehe=float("nan")); pruef(gn is None, "NaN-Hoehe -> nicht gebaut")
    # ---- seitlich offen (Bruestung + Pfosten)
    gs, bs, mss = bau(seiten=dict(art="offen", bruestung=1.0, pfosten=4, pfosten_breite=0.2, riegel=0.25), treppe=dict(lage="aussen", ende="a"))
    pruef(gs is not None and len(gs.decompose()) == 1 and mss.get("oeffnungen") == 3, f"offene Seiten: 3 Felder zwischen 4 Pfosten ({mss.get('oeffnungen')})")
    pruef(frei(gs, (L / 2, B / 2 - t / 2, 5.5 + 1.5)) and drin(gs, (L / 2, B / 2 - t / 2, 5.5 + 0.5)) and drin(gs, (0.1, B / 2 - t / 2, 5.5 + 1.5)),
          "Feld offen ueber der Bruestung, Bruestung und Endpfosten voll")
    nw = [i for i, m in enumerate(gebaut) if not als_trimesh(m).is_watertight]
    pruef(not nw, f"alle {len(gebaut)} gebauten Varianten als trimesh wasserdicht (nicht: {nw})")
    from bauteile import ueberdachter_gang_aus_json
    import json
    from pfade import temp_ordner
    d = temp_ordner("gang_"); pf = os.path.join(d, "gang.json"); json.dump(dict(gang=GRUND), open(pf, "w"))
    k, bj = ueberdachter_gang_aus_json(None, pf); tm = als_trimesh(k)
    pruef(tm.is_watertight and abs(tm.volume - g.volume()) < 1e-4, f"JSON-Weg + trimesh: wasserdicht, Volumen {tm.volume:.3f} m3")
    # ---- 7 ZUFALLSPROBE (fester Keim): beliebige, auch unsinnige Parameter -> entweder None oder EIN wasserdichter Koerper (nie degeneriert).
    #      Fand am 26.11. Antritt/Austritt flaechengleich mit dem Gangende (einbinden 0) -> doppelte Eckpunkte.
    import random
    R = random.Random(1); schlecht = []; n_gebaut = 0
    for k_ in range(150):
        Pz = dict(spannweite=R.uniform(2, 15), breite=R.uniform(0.2, 4), z_boden=R.uniform(0, 10), hoehe=R.uniform(0.05, 3.5), boden_dicke=R.uniform(0.01, 0.4),
                  wand_dicke=R.uniform(0.01, 0.4), einbinden=R.choice([0, 0.05, 0.3]),
                  dach=dict(form=R.choice(["flach", "pult", "sattel", "x"]), neigung_grad=R.uniform(0, 80), ueberstand=R.uniform(0, 0.6), dicke=R.uniform(0.01, 0.3)),
                  seiten=dict(art=R.choice(["offen", "geschlossen"]), bruestung=R.uniform(0, 1.5), pfosten=R.randint(1, 8), pfosten_breite=R.uniform(0.01, 0.4), riegel=R.uniform(0.01, 0.5)),
                  treppe=dict(lage=R.choice(["innen", "aussen"]), ende=R.choice("ab"), stufen=R.randint(1, 20), steigung=R.uniform(0.02, 0.25), auftritt=R.uniform(0.03, 0.4)))
        gz, _, _ = _ug(Pz)
        if gz is None: continue
        n_gebaut += 1
        if len(gz.decompose()) != 1 or not als_trimesh(gz).is_watertight: schlecht.append(k_)
    pruef(not schlecht and n_gebaut > 100, f"Zufallsprobe: {n_gebaut} von 150 gebaut, alle ein wasserdichter Koerper (schlecht: {schlecht[:10]})")


if __name__ == "__main__":
    main()
    print("ERGEBNIS:", "alle Pruefungen bestanden" if F == 0 else f"{F} FEHLER"); sys.exit(1 if F else 0)
