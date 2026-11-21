#!/usr/bin/env python3
"""test_oeffnungen_aus_kanten.py - fester Test (ohne GPU, ohne Daten) fuer tools/oeffnungen_aus_kanten.py.

Synthetische Wand 12 x 14 m mit drei Oeffnungen: Spitzbogentor (steht auf dem Boden), Rundbogenfenster, Rechteckfenster.
 Teil 1 'nur kanten': Kantenpunkte auf den Umrissen (vordere Kante in Wandtiefe, hintere Laibungskante 0,3 m dahinter), Rauschen 1,5 cm,
                      je Oeffnung fehlende Kantenstuecke, dazu Fugenstriche in der Wand (duerfen keine Oeffnung ergeben).
 Teil 2 'wolke'     : dichte Wolke (Wand rau 1,5 cm; Fenster mit Grund 0,3 m hinten; Tor leer = Durchblick) + dieselben Kantenpunkte.
 Teil 3 'wandbild'  : Tor mit Fase (0,25 m breit, Innenkante 0,3 m tief), synthetisches entzerrtes Wandbild (Quaderwand mit Fugen, dunkle Fase, helle Durchgangswand,
                      hinteres Portal als Durchblick) + 4 Einzelfotos mit Parallaxe: Spitzbogen aus dem Bild, lichte Weite, Aussenmass, Fase, Fasentiefe; Fenster ohne Gewaende;
                      ohne Einzelfotos nur eine Kante und Gewaende offen.
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


def versatz(s, g):
    """Umriss s um g nach aussen versetzt (gleiche Bogenmittelpunkte, Radius + g) = Aussenkante der Fase."""
    b = s["uR"] - s["uL"]; h = s["h"]
    if h <= 0: h2 = g
    elif h > b / 2 + 1e-9: ex = (h * h - b * b / 4) / b; h2 = np.sqrt((b / 2 + ex + g) ** 2 - ex ** 2)
    else: r = (b * b / 4 + h * h) / (2 * h); zc = s["zk"] + h - r; h2 = zc + r + g - s["zk"]
    return dict(s, uL=s["uL"] - g, uR=s["uR"] + g, h=h2, zs=s["zs"])


FASE, FASE_L = 0.25, 0.30                        # Tor: Fase 0,25 m breit in der Wandebene, Innenkante 0,3 m hinter der Wand
HINTEN = dict(name="hinteres_portal", uL=-0.9, uR=0.9, zs=0.0, zk=2.0, h=1.4)      # Durchblick: kleineres Portal 3 m tiefer (darf die Form nicht stoeren)


def wandbild(zr, ru, rausch=6.0):
    """Synthetisches entzerrtes Wandbild (1 cm) aus Blickrichtung ru: Quaderwand mit Fugen, Tor mit dunkler Fase (Aussenkante in der Wandebene, Innenkante FASE_L tief ->
    um FASE_L * ru verschoben), heller Durchgangswand und dunklem hinterem Portal (3 m tief). Fenster bleiben dunkel (Glas)."""
    zl = 0.01; uu = -6 + (np.arange(1200) + 0.5) * zl; zz = 14 - (np.arange(1400) + 0.5) * zl; U, Z = np.meshgrid(uu, zz); rs = np.random.default_rng(5)
    lage = np.floor(Z / 0.35).astype(int); vers = (lage % 2) * 0.3; stein = np.floor((U + 6 + vers) / 0.6).astype(int); A = 140 + rs.normal(0, 18, (60, 30))[lage % 60, stein % 30]
    A[((Z % 0.35) < 0.02) | (((U + 6 + vers) % 0.6) < 0.02)] = 200                        # Fugen hell
    tor = SOLL[0]; tor_i = dict(tor, uL=tor["uL"] + FASE_L * ru, uR=tor["uR"] + FASE_L * ru)
    A[innen(U, Z, versatz(tor, FASE))] = 70; A[innen(U, Z, tor_i)] = 215; A[innen(U, Z, dict(HINTEN, uL=HINTEN["uL"] + 3 * ru, uR=HINTEN["uR"] + 3 * ru))] = 40
    for s in SOLL[1:]: A[innen(U, Z, s)] = 45
    import cv2
    A = cv2.GaussianBlur(A.astype(np.float32), (0, 0), 1.0) + zr.normal(0, rausch, A.shape); return np.clip(A, 1, 255).astype(np.float32)


def teil_wandbild(zr, P, fehler):
    """Teil 3: Wolkenrand auf der Fase (Fase in der Wolke schraeg 0 -> FASE_L), Wandbild + 4 Einzelfotos -> Spitzbogen, lichte Weite, Aussenmass, Fase, Fasentiefe;
    Fenster ohne Gewaende duerfen keins bekommen (Fugen sind keine). Danach dieselbe Oeffnung NUR mit dem Wandbild: eine Kante, Gewaende offen."""
    import copy
    F = dict(id="t00", o=[0.0, 0.0], d=[1.0, 0.0], n=[0.0, 1.0], raster=dict(u0=-6.0, z1=14.0, zelle=0.01, nu=1200, nz=1400))
    E = [(f"foto{k}", np.clip(wandbild(zr, ru), 1, 255).astype(np.uint8), np.array([ru * 100.0, 100.0, 2.5])) for k, ru in enumerate((-0.3, -0.12, 0.1, 0.3))]
    bild = wandbild(zr, 0.0); W = O.wandbild_aus(F, bild, EBENE, E, quelle="synthetisch")
    u, z, w = wolke(zr, 200000); tor = SOLL[0]; sa = versatz(tor, FASE); fase = innen(u, z, sa) & ~innen(u, z, tor)               # Fase in der Wolke: schraeg von 0 (aussen) bis FASE_L (innen)
    if fase.any():                                                                                             # Abstand nach innen = Abstand zum Aussenumriss (Kreisboegen: exakt)
        from scipy.spatial import cKDTree
        M, _ = O.umriss(sa["uL"], sa["uR"], sa["zk"], sa["h"], sa["zs"], schritt=0.005); dd = cKDTree(M).query(np.c_[u[fase], z[fase]])[0]
        w[fase] = -FASE_L * np.clip(dd / FASE, 0, 1) + zr.normal(0, 0.015, int(fase.sum()))
    alt = {}
    orig = O.wandbild_vermessen
    def merke(o, *a):                                                                                          # Zustand vor der Wandbild-Stufe aufheben (fuer den Lauf ohne Einzelfotos)
        alt[id(o)] = copy.deepcopy(o); return orig(o, *a)
    O.wandbild_vermessen = merke
    try: e = O.ebene_auswerten(EBENE, P, (u, z, w), wandbild=W)
    finally: O.wandbild_vermessen = orig
    tag = "wandbild+einzeln"; kand = [o for o in e["oeffnungen"] if abs(o["mitte_u"]) < 0.3 and o["zone"][2] < 0.5]
    for s_ in SOLL[1:]:                                                                                        # Fenster: Form bleibt, KEIN Gewaende (Fugen in der Wandebene)
        f_ = [o for o in e["oeffnungen"] if abs(o["mitte_u"] - 0.5 * (s_["uL"] + s_["uR"])) < 0.3 and abs(o["zone"][2] - s_["zs"]) < 0.5]
        if not f_: fehler.append(f"{tag}: {s_['name']} nicht gefunden"); continue
        if f_[0]["form"] != s_["form"]: fehler.append(f"{tag}: {s_['name']} Form {f_[0]['form']} statt {s_['form']}")
        if (f_[0].get("gewaende") or {}).get("breite") is not None: fehler.append(f"{tag}: {s_['name']} Gewaende {f_[0]['gewaende']['breite']} erfunden")
    if not kand: fehler.append(f"{tag}: Tor nicht gefunden"); return
    o = kand[0]; wb = o.get("wandbild", {}); sa = versatz(tor, FASE)
    if o["form"] != "spitzbogen" or o["form_quelle"] != "wandbild": fehler.append(f"{tag}: Form {o['form']} ({o['form_quelle']}, {o.get('form_grund')}; wandbild {wb.get('form')} {wb.get('hinweis', '')})"); return
    ist = dict(licht=o["breite"]["wert"], aussen=o["aussenmass"]["breite"], fase_l=o["gewaende"]["links"], fase_r=o["gewaende"]["rechts"], scheitel=o["scheitel"]["wert"], kaempfer=o["kaempfer"]["wert"], scheitel_aussen=o["aussenmass"]["scheitel"])
    soll = dict(licht=tor["uR"] - tor["uL"], aussen=sa["uR"] - sa["uL"], fase_l=FASE, fase_r=FASE, scheitel=tor["zk"] + tor["h"], kaempfer=tor["zk"], scheitel_aussen=sa["zk"] + sa["h"])
    tol = dict(licht=0.05, aussen=0.05, fase_l=0.05, fase_r=0.05, scheitel=0.06, kaempfer=0.2, scheitel_aussen=0.08)          # Kaempfer: Bogen laeuft tangential in die Laibung
    for k in soll:
        if ist[k] is None or abs(ist[k] - soll[k]) > tol[k]: fehler.append(f"{tag}: {k} {ist[k]} statt {soll[k]:.2f} (Toleranz {tol[k]})")
    L = [o["gewaende"]["tiefe_innenkante_links"], o["gewaende"]["tiefe_innenkante_rechts"]]
    if any(x is None or abs(x - FASE_L) > 0.1 for x in L): fehler.append(f"{tag}: Fasentiefe {L} statt {FASE_L} (Parallaxe der Einzelfotos)")
    print(f"  {tag:16s} tor {o['form']} ({o['form_quelle']}) " + " ".join(f"{k} {ist[k]}/{soll[k]:.2f}" for k in soll) + f" tiefe {L[0]}/{L[1]}")
    # ohne Einzelfotos: zweite Kante nicht bestaetigbar -> EINE Kante (innen ODER aussen), Gewaende offen
    tag = "nur wandbild"; o2 = O.wandbild_vermessen(alt[id(o)], O.wandbild_aus(F, bild, EBENE, [], quelle="synthetisch"), o["zelle"], O.DRUCK_MIN_M)
    if o2["form"] != "spitzbogen" or o2["form_quelle"] != "wandbild": fehler.append(f"{tag}: Form {o2['form']} ({o2['form_quelle']})"); return
    b2, a2 = o2["breite"]["wert"], o2["aussenmass"]["breite"]
    if o2["gewaende"]["breite"] is not None: fehler.append(f"{tag}: Gewaende {o2['gewaende']['breite']} ohne Einzelfotos behauptet")
    if b2 != a2: fehler.append(f"{tag}: Innen {b2} != Aussen {a2} trotz nur einer Kante")
    if min(abs(b2 - soll["licht"]), abs(b2 - soll["aussen"])) > tol["licht"]: fehler.append(f"{tag}: Breite {b2} weder Innen- noch Aussenkante")
    print(f"  {tag:16s} tor {o2['form']} ({o2['form_quelle']}) eine Kante: Breite {b2} (innen {soll['licht']:.2f} / aussen {soll['aussen']:.2f}) Scheitel {o2['scheitel']['wert']}")


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
    teil_wandbild(zr, P, fehler)
    for f in fehler: print("FEHLER", f)
    print("test_oeffnungen_aus_kanten:", "bestanden" if not fehler else f"{len(fehler)} Fehler"); return 0 if not fehler else 1


if __name__ == "__main__": sys.exit(main())
