#!/usr/bin/env python3
"""test_oeffnungen_aus_kanten.py - fester Test (ohne GPU, ohne Daten) fuer tools/oeffnungen_aus_kanten.py.

Synthetische Wand 12 x 14 m mit drei Oeffnungen: Spitzbogentor (steht auf dem Boden), Rundbogenfenster, Rechteckfenster.
 Teil 1 'nur kanten': Kantenpunkte auf den Umrissen (vordere Kante in Wandtiefe, hintere Laibungskante 0,3 m dahinter), Rauschen 1,5 cm,
                      je Oeffnung fehlende Kantenstuecke, dazu Fugenstriche in der Wand (duerfen keine Oeffnung ergeben).
 Teil 2 'wolke'     : dichte Wolke (Wand rau 1,5 cm; Fenster mit Grund 0,3 m hinten; Tor leer = Durchblick) + dieselben Kantenpunkte.
Geprueft: Zahl der Oeffnungen, Form je Oeffnung, Breite / Kaempfer / Scheitel / Sohlbank gegen die Vorgabe.
rc 0 = bestanden.
"""
import sys, os, numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import oeffnungen_aus_kanten as O

SOLL = [dict(name="tor", form="spitzbogen", uL=-1.5, uR=1.5, zs=0.0, zk=2.5, h=2.4),
        dict(name="rundbogenfenster", form="rundbogen", uL=-4.0, uR=-2.4, zs=7.0, zk=8.6, h=0.8),
        dict(name="rechteckfenster", form="sturz", uL=2.5, uR=3.7, zs=7.2, zk=9.0, h=0.0)]
EBENE = dict(id="t00_wand", art="wand", o=[0.0, 0.0], d=[1.0, 0.0], n=[0.0, 1.0], w=0.0, zone=[-6.0, 6.0, 0.0, 14.0], band=0.5)


def innen(u, z, s):
    """Punkt im Loch der Oeffnung s?"""
    M, _ = O.umriss(s["uL"], s["uR"], s["zk"], s["h"], s["zs"], schritt=0.01); top = M[M[:, 1] >= s["zk"] - 1e-9]
    zo = np.interp(u, np.sort(top[:, 0]), top[np.argsort(top[:, 0]), 1], left=-1e9, right=-1e9) if s["h"] > 0 else np.where((u >= s["uL"]) & (u <= s["uR"]), s["zk"], -1e9)
    return (u > s["uL"]) & (u < s["uR"]) & (z > s["zs"]) & (z < np.maximum(zo, s["zk"]))


def kanten(zr):
    P = []
    for s in SOLL:
        M, _ = O.umriss(s["uL"], s["uR"], s["zk"], s["h"], s["zs"], schritt=0.004)
        if s["zs"] > 0: t = np.arange(s["uL"], s["uR"], 0.004); M = np.vstack([M, np.c_[t, np.full(len(t), s["zs"])]])      # Sohlbank (das Tor hat keine)
        for l_ in range(3):                                                      # drei fehlende Stuecke von 0,2 m je Oeffnung
            c = M[zr.integers(len(M))]; M = M[np.hypot(M[:, 0] - c[0], M[:, 1] - c[1]) > 0.1]
        for tiefe, anteil in ((0.0, 1.0), (-0.3, 0.5)):                          # vordere Kante voll, hintere Laibungskante halb so dicht
            Q = M[zr.random(len(M)) < anteil]; Q = Q + zr.normal(0, 0.015, Q.shape); P.append(np.c_[Q[:, 0], tiefe + zr.normal(0, 0.05, len(Q)), Q[:, 1]])
    for _ in range(60):                                                          # Fugenstriche 0,3-0,9 m, nicht in den Oeffnungen
        u0, z0, l_ = zr.uniform(-5.8, 5.0), zr.uniform(0.2, 13.8), zr.uniform(0.3, 0.9); t = np.arange(u0, u0 + l_, 0.01); zz = np.full(len(t), z0)
        if any(innen(t, zz, s).any() for s in SOLL): continue
        P.append(np.c_[t, zr.normal(0, 0.05, len(t)), zz + zr.normal(0, 0.01, len(t))])
    for uu in (-5.95, 5.95): z = np.arange(0, 14, 0.01); P.append(np.c_[np.full(len(z), uu), zr.normal(0, 0.05, len(z)), z])      # Wandkanten
    return np.vstack(P)                                                          # Spalten x, y, z: u = x, Tiefe = y


def wolke(zr, n=400000):
    u, z = zr.uniform(-6, 6, n), zr.uniform(0, 14, n); w = zr.normal(0, 0.015, n); weg = np.zeros(n, bool)
    for s in SOLL:
        i = innen(u, z, s)
        if s["name"] == "tor": weg |= i
        else: w[i] = -0.3 + zr.normal(0, 0.015, int(i.sum()))
    return u[~weg], z[~weg], w[~weg]


def pruefe(erg, tol, name):
    fehler = []; oe = erg["oeffnungen"]
    if len(oe) != len(SOLL): fehler.append(f"{len(oe)} Oeffnungen statt {len(SOLL)}: {[(o['form'], o['zone']) for o in oe]}")
    for s in SOLL:
        kand = [o for o in oe if abs(o["mitte_u"] - 0.5 * (s["uL"] + s["uR"])) < 0.3 and abs(o["zone"][2] - s["zs"]) < 0.5]
        if not kand: fehler.append(f"{s['name']}: nicht gefunden"); continue
        o = kand[0]
        if o["form"] != s["form"]: fehler.append(f"{s['name']}: Form {o['form']} statt {s['form']} ({o['form_grund']})")
        ist = dict(breite=o["breite"]["wert"], scheitel=o["scheitel"]["wert"], sohlbank=o["sohlbank"]["wert"]); soll = dict(breite=s["uR"] - s["uL"], scheitel=s["zk"] + s["h"], sohlbank=s["zs"])
        if s["h"] > 0: ist["kaempfer"] = o["kaempfer"]["wert"]; soll["kaempfer"] = s["zk"]
        for k in soll:
            t = tol * (2.5 if k == "kaempfer" else 1.0)                           # der Kaempfer ist die unschaerfste Hoehe (Bogen laeuft tangential in die Laibung)
            if ist[k] is None or abs(ist[k] - soll[k]) > t: fehler.append(f"{s['name']}: {k} {ist[k]} statt {soll[k]:.2f} (Toleranz {t:.2f})")
        print(f"  {name} {s['name']:17s} {o['form']:10s} ({o['form_quelle']}) " + " ".join(f"{k} {ist[k]:.2f}/{soll[k]:.2f}" for k in soll))
    return fehler


def main():
    zr = np.random.default_rng(11); P = kanten(zr); fehler = []
    e1 = O.ebene_auswerten(EBENE, P); fehler += ["nur kanten: " + f for f in pruefe(e1, 0.08, "kanten")]
    e2 = O.ebene_auswerten(EBENE, P, wolke(zr)); fehler += ["wolke: " + f for f in pruefe(e2, 0.10, "wolke ")]
    if not all(o["sicher"] for o in e2["oeffnungen"] if o["laibung_tiefe"]["wolke"] is not None): fehler.append("wolke: Oeffnung mit Tiefe als unsicher gemeldet")
    # Formwahl: bei reinem Rauschen ohne klaren Unterschied muss 'unbestimmt' kommen
    f, _ = O.form_waehlen(dict(sturz=dict(rest=0.05, uL=0, uR=1, h=0), rundbogen=dict(rest=0.045, uL=0, uR=1, h=0.5)), 0.05)
    if f != "unbestimmt": fehler.append(f"Formwahl ohne klaren Sieger ergab {f}")
    # leere Wand: keine Oeffnung
    u, z = zr.uniform(-6, 6, 200000), zr.uniform(0, 14, 200000); e3 = O.ebene_auswerten(EBENE, P[:0].reshape(0, 3), (u, z, zr.normal(0, 0.015, len(u))))
    if e3["oeffnungen"]: fehler.append(f"leere Wand: {len(e3['oeffnungen'])} Oeffnungen erfunden")
    for f in fehler: print("FEHLER", f)
    print("test_oeffnungen_aus_kanten:", "bestanden" if not fehler else f"{len(fehler)} Fehler"); return 0 if not fehler else 1


if __name__ == "__main__": sys.exit(main())
