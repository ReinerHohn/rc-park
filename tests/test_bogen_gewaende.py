#!/usr/bin/env python3
"""test_bogen_gewaende.py - fester synthetischer Test fuer den Befund 'Torboegen ohne Gewaende' aus Kettenlauf 1122w (24.11.2026), < 30 s, nur CPU.

Befund (modelle/schwabentor-1122/audit/neben_detail_oeffnung_bogen_f00/_f01.jpg): beide Torboegen im Foto mit Sandstein-Gewaende aus Bogensteinen (Ring ~0,35-0,45 m),
im Modell nur ein glattes Loch. Teile:
  1 ERKENNEN   Bruchsteinwand (Lagen mit Stossfugen) + Spitzbogen-Tor, Bogensteine radial 0,45 m breit -> tools/bogen_gewaende.py misst das Band 0,45 +- 0,06 m
               (Kettenaufruf main(): oeffnungen_auto.json bekommt 'gewaende_band', rc 0, Kontrollbild da). Vorsprung aus der Tiefe je Zelle (+0,08 m).
  2 ROT-PROBE  dieselbe Wand OHNE Bogensteine (Bruchstein bis ans Loch) -> kein Band (rc 3), Eintrag ohne 'gewaende_band'; altes Band eines frueheren Laufs wird entfernt.
  3 BAUEN      bauteile.bogen_gewaende_spaet: Band vor der echten Oberflaeche (Reliefplatte 0,1 m vor der Ebene), Loch bleibt offen, ausserhalb des Bands unveraendert,
               ein Koerper; Vorsprung nie unter Druckmindestmass (MINMM x SCALE); ohne 'gewaende_band' unveraendert.
"""
import sys, os, json, numpy as np
HIER = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(os.path.dirname(HIER), "tools"))
from pfade import temp_ordner
import bogen_gewaende as BG

U0, U1, Z0, Z1, C = -5.0, 5.0, -0.2, 8.5, 0.01
TOR = dict(art="bogen", form="spitz", u=0.0, breite=4.0, kaempfer=3.5, scheitel=6.2, unten=0.0, tiefe_m=0.6, gebaut=True)
BAND = 0.45
F = 0


def pruef(ok, text):
    global F
    print(("  ok     " if ok else "  FEHLER ") + text)
    if not ok: F += 1


def bild(mit_band, seed=5):
    """Synthetisches feines Wandbild (BGR, 1 cm): Bruchstein in Lagen, Spitzbogen-Tor dunkel, optional Bogensteine (radiale Fugen) im Band."""
    import cv2
    from bauteile import bogen_querschnitt
    rng = np.random.default_rng(seed); H, W = int(round((Z1 - Z0) / C)), int(round((U1 - U0) / C))
    im = np.zeros((H, W, 3), np.float64) + np.array([150, 160, 170])                 # Moertel
    z = Z0
    while z < Z1:                                                                     # Lagen 0,25-0,40 m, Steine 0,3-0,8 m, Fugen 1,5 cm
        h = rng.uniform(0.25, 0.40); u = U0 - rng.uniform(0, 0.5)
        while u < U1:
            l = rng.uniform(0.3, 0.8); f = np.array([70, 85, 120]) + rng.normal(0, 18, 3)
            i0, i1 = int((Z1 - (z + h - 0.015)) / C), int((Z1 - z) / C); j0, j1 = int((u - U0) / C), int((u + l - 0.015 - U0) / C)
            im[max(0, i0):max(0, i1), max(0, j0):max(0, j1)] = f; u += l
        z += h
    im += rng.normal(0, 6, (H, W, 1))
    P = np.array(bogen_querschnitt(TOR["form"], TOR["breite"], TOR["kaempfer"], TOR["scheitel"], TOR["unten"]).to_polygons()[0])
    pts = np.stack([(TOR["u"] + P[:, 0] - U0) / C, (Z1 - P[:, 1]) / C], 1).round().astype(np.int32)
    loch = np.zeros((H, W), np.uint8); cv2.fillPoly(loch, [pts], 1)
    if mit_band:
        Q, N, teil = BG.umriss_pfad(TOR)                                              # Bogensteine: Stossfugen radial alle 0,35 m entlang des Umrisses
        rand = np.ones((H, W), np.uint8); idx = np.zeros((H, W), np.int32)
        for k, q in enumerate(Q):
            i, j = int(round((Z1 - q[1]) / C)), int(round((TOR["u"] + q[0] - U0) / C))
            if 0 <= i < H and 0 <= j < W: rand[i, j] = 0; idx[i, j] = k
        dist, lab = cv2.distanceTransformWithLabels(rand, cv2.DIST_L2, 5, labelType=cv2.DIST_LABEL_PIXEL)
        nl = np.zeros(lab.max() + 1, np.int32); nl[lab[rand == 0]] = idx[rand == 0]; s = nl[lab] * 0.01; d = dist * C
        im_b = (d <= BAND) & (loch == 0)
        farben = np.array([105, 120, 175]) + rng.normal(0, 10, (400, 3)); stein = (s / 0.35).astype(int) % 400
        im[im_b] = farben[stein[im_b]] + rng.normal(0, 4, (int(im_b.sum()), 3))
        fuge = im_b & (((s % 0.35) < 0.015) | (d > BAND - 0.015))
        im[fuge] = [150, 160, 170]
    im[loch > 0] = [25, 25, 30]
    return np.clip(im, 0, 255).astype(np.uint8)


def tiefe_npz(pfad, vorsprung):
    """Tiefe je Zelle (4 cm): Wand 0, Band +vorsprung, Loch -0,6."""
    import cv2
    from bauteile import bogen_querschnitt
    c = 0.04; H, W = int((Z1 - Z0) / c), int((U1 - U0) / c)
    P = np.array(bogen_querschnitt(TOR["form"], TOR["breite"], TOR["kaempfer"], TOR["scheitel"], TOR["unten"]).to_polygons()[0])
    pts = np.stack([(TOR["u"] + P[:, 0] - U0) / c, (Z1 - P[:, 1]) / c], 1).round().astype(np.int32)
    m = np.zeros((H, W), np.uint8); cv2.fillPoly(m, [pts], 1); d = cv2.distanceTransform((1 - m).astype(np.uint8), cv2.DIST_L2, 5) * c
    w = np.zeros((H, W)); w[(d > 0) & (d <= BAND)] = vorsprung; w[m > 0] = -0.6
    np.savez(pfad, w=w, gut=np.ones((H, W), bool), sicher=np.ones((H, W), bool), u0=U0, z1=Z1, zelle=c)


def ordner(mit_band, d):
    import cv2
    fo, ff, au = (os.path.join(d, n) for n in ("fassade", "fassade_fein", "audit"))
    for p in (fo, ff, au): os.makedirs(p, exist_ok=True)
    rast = dict(u0=U0, z1=Z1, zelle=C, nu=int((U1 - U0) / C), nz=int((Z1 - Z0) / C))
    json.dump(dict(fassaden=[dict(id="f00", o=[0.0, 0.0], d=[1.0, 0.0], n=[0.0, -1.0], raster=rast)]), open(os.path.join(ff, "fassaden.json"), "w"))
    cv2.imwrite(os.path.join(ff, "ortho_f00_fein.png"), bild(mit_band))
    tiefe_npz(os.path.join(fo, "tiefe_f00.npz"), 0.08 if mit_band else 0.0)
    oa = os.path.join(au, "oeffnungen_auto.json")
    alt = dict(TOR, gewaende_band=dict(aussen=0.9, vorsprung=0.1)) if not mit_band else dict(TOR)   # Rot-Probe: Band eines frueheren Laufs muss weg
    json.dump({"f00": dict(o=[0.0, 0.0], d=[1.0, 0.0], n=[0.0, -1.0], oeffnungen=[alt, dict(TOR, u=3.0, gebaut=False)])}, open(oa, "w"))
    return oa, ff, fo, au


def teil_erkennen():
    print("1 Erkennen: Bogensteine radial 0,45 m")
    d = temp_ordner("test_bogen_gew_"); oa, ff, fo, au = ordner(True, d)
    rc = BG.main([oa, ff, "--fassade", fo, "--aus", au])
    J = json.load(open(oa)); x = J["f00"]["oeffnungen"][0]; G = x.get("gewaende_band")
    pruef(rc == 0 and G is not None, f"Band erkannt (rc {rc})")
    if G:
        pruef(abs(G["aussen"] - BAND) <= 0.06, f"Bandbreite {G['aussen']:.2f} m (soll {BAND} +- 0,06)")
        pruef(G["kontrast"] >= 0.25, f"Kontrast {G['kontrast']:.2f}")
        pruef(abs(G["vorsprung"] - 0.08) <= 0.03 and "Tiefe je Zelle" in G["vorsprung_quelle"], f"Vorsprung {G['vorsprung']:.3f} m aus der Tiefe je Zelle (soll 0,08)")
        pruef("ANNAHME" in G["pfosten_quelle"], "Pfostenbreite als ANNAHME benannt")
    pruef("gewaende_band" not in J["f00"]["oeffnungen"][1], "nicht gebaute Oeffnung bleibt ohne Band")
    pruef(os.path.exists(os.path.join(au, "bogen_gewaende_f00.jpg")) and os.path.exists(os.path.join(au, "bogen_gewaende.json")), "Kontrollbild + Bericht geschrieben")
    return oa


def teil_rot():
    print("2 Rot-Probe: Bruchstein bis ans Loch (kein Gewaende)")
    d = temp_ordner("test_bogen_gew_rot_"); oa, ff, fo, au = ordner(False, d)
    rc = BG.main([oa, ff, "--fassade", fo, "--aus", au])
    J = json.load(open(oa)); x = J["f00"]["oeffnungen"][0]
    pruef(rc == 3 and "gewaende_band" not in x, f"kein Band erfunden (rc {rc}), altes Band entfernt")
    ber = json.load(open(os.path.join(au, "bogen_gewaende.json")))["f00"][0]
    pruef("fehler" in ber, f"Grund im Bericht: {ber.get('fehler', '-')[:70]}")


def teil_bauen(oa):
    print("3 Bauen: bauteile.bogen_gewaende_spaet auf der echten Oberflaeche")
    import bauteile as B
    from manifold3d import Manifold as M
    J = json.load(open(oa)); F0 = J["f00"]; o = np.array(F0["o"]); W = B.Wand(o, o + np.array(F0["d"]), aussen=o + np.array(F0["n"]))
    k = W.kasten(-5, 5, 0, 9, -2.0, 0.0) + W.kasten(-5, 5, 0, 9, -0.1, 0.1)          # Wand + Reliefplatte 0,1 m vor der Ebene
    d = temp_ordner("test_bogen_gew_bau_"); p = os.path.join(d, "oa.json"); json.dump(J, open(p, "w"))
    k, _, _ = B.oeffnungen_aus_json(k, p)
    v0 = k.volume(); n0 = len(k.decompose())
    k2, bel = B.bogen_gewaende_spaet(k, p)
    G = J["f00"]["oeffnungen"][0]["gewaende_band"]; dm = float(os.environ.get("MINMM", "0.8")) * float(os.environ.get("SCALE", "87")) / 1000.0
    h = max(G["vorsprung"], dm)
    pruef(k2.volume() > v0 and len(k2.decompose()) == n0, f"Band angebaut, ein Koerper (Volumen +{k2.volume() - v0:.3f} m3)")
    mitte_band = (TOR["breite"] / 2 + G["aussen"] / 2, 2.0)                       # Pfosten rechts, Mitte des Bands (u, z)
    w = B._oberflaeche_w(k2, W, [mitte_band, (TOR["breite"] / 2 + G["aussen"] + 0.4, 2.0), (0.0, 2.0), (0.0, TOR["scheitel"] + G["aussen"] / 2)])
    pruef(w[0] is not None and abs(w[0] - (0.1 + h)) < 0.01, f"Bandflaeche bei w {w[0]} (soll Oberflaeche 0,1 + Vorsprung {h:.3f})")
    pruef(w[1] is not None and abs(w[1] - 0.1) < 0.01, f"ausserhalb des Bands unveraendert (w {w[1]})")
    pruef(w[2] is None or w[2] < -0.5, f"Loch bleibt offen (w {w[2]})")
    pruef(w[3] is not None and abs(w[3] - (0.1 + h)) < 0.01, f"Band auch ueber dem Scheitel (w {w[3]})")
    pruef(bel and bel[0]["masse"] and bel[0]["masse"][0]["vorsprung"] >= dm - 1e-9, "Beleg mit Massen, Vorsprung >= Druckmindestmass")
    J2 = json.load(open(p)); J2["f00"]["oeffnungen"][0]["gewaende_band"] = dict(G, vorsprung=0.001); json.dump(J2, open(p, "w"))
    k3, bel3 = B.bogen_gewaende_spaet(k, p); w3 = B._oberflaeche_w(k3, W, [mitte_band])[0]
    pruef(w3 is not None and abs(w3 - (0.1 + dm)) < 0.01, f"Vorsprung 1 mm -> Druckmindestmass {dm:.3f} m (w {w3})")
    J2["f00"]["oeffnungen"][0].pop("gewaende_band"); json.dump(J2, open(p, "w"))
    k4, bel4 = B.bogen_gewaende_spaet(k, p)
    pruef(abs(k4.volume() - v0) < 1e-9 and not bel4, "ohne gewaende_band unveraendert")


def main():
    os.environ.setdefault("MINMM", "0.8"); os.environ.setdefault("SCALE", "87")
    oa = teil_erkennen(); teil_rot(); teil_bauen(oa)
    print("FEHLER gesamt:", F)
    return 1 if F else 0


if __name__ == "__main__": sys.exit(main())
