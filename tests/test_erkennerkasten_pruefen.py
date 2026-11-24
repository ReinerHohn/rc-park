#!/usr/bin/env python3
"""test_erkennerkasten_pruefen.py - Erkennerkaesten vor der Verwendung pruefen (Befund Kettenlauf 1122zb, 24.11.2026), synthetisch, < 15 s, nur CPU.

Befund: Schwabentor f04 (Sehne des runden Treppenturms) - im Foto drei Schlitze, gebaut einer. Zwei FALSCHE 'tuer'-Kaesten 1,6 x 5,9 m auf weissem Putz
sperrten in schlitze_wandbild alle drei Schlitze; loch_gewaende machte aus dem einen eine zweite Tuer (Doppelung) und aus dem anderen den einen Schlitz.
Faelle:
  1 f04-Nachbau: weisser Putz, echte Tuer unten im Sandsteinportal, drei Schlitze 0,12 x 0,65 m. Kaesten: echte Tuer GILT (dunkel + Boden);
    falsche Tuer z 2,1-8,0 VERWORFEN (Loch fuellt die Box nicht, kein Rahmen, kein Tiefensprung); falsche Tuer z 6,6-12 VERWORFEN (ohne Boden/Schwelle).
  2 Rot-Proben: Schlitz im Sandsteinfeld (rahmen) GILT; dunkles Fenster mit HELLEM Ring hoch oben (f00 z 33) GILT; helles Feld zwischen dunklen Konsolen
    (f00 z 8,8 'fenster', PERFORMANCE_BREMSEN 20.11.) VERWORFEN; offene Durchfahrt ohne Dunkel, aber Tiefensprung GILT; Tuer im OG ueber Schwelle GILT.
  3 schlitze_wandbild.bekannte_kaesten: verworfene Tuerkaesten sperren nichts (Grund in der Liste), echte Tuer bleibt bekannt; ohne Pruefung Altverhalten.
  4 loch_gewaende: aus echter + zwei falschen Tuerzonen genau EINE Tuer (keine Doppelung), Bericht 'Erkennerkasten verworfen'; zwei gueltige Zonen um
    dieselbe Tuer -> 'Doppelung', eine Tuer.
"""
import sys, os, json
import numpy as np
HIER = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HIER, "..", "tools"))
from pfade import temp_ordner
import erkennerkasten_pruefen as EK

F = 0
WAND, SAND, DUNKEL, TUER, HELL = (225, 225, 222), (120, 85, 70), (25, 25, 30), (40, 32, 25), (240, 240, 238)


def pruef(ok, text):
    global F
    print(("    ok     " if ok else "    FEHLER ") + text)
    if not ok: F += 1


def bild(U0, U1, Z0, Z1, C, felder, grund=WAND, seed=1):
    rng = np.random.default_rng(seed); H, W = int(round((Z1 - Z0) / C)), int(round((U1 - U0) / C))
    im = np.zeros((H, W, 3)) + np.array(grund) + rng.normal(0, 3.0, (H, W, 1))
    uu = U0 + C * (np.arange(W) + 0.5); zz = Z1 - C * (np.arange(H) + 0.5); UU, ZZ = np.meshgrid(uu, zz)
    for (a0, a1, b0, b1, farbe) in felder: im[(UU >= a0) & (UU <= a1) & (ZZ >= b0) & (ZZ <= b1)] = farbe
    return np.clip(im, 0, 255).astype(np.uint8)


def npz_flach(U0, U1, Z0, Z1, tief=()):
    c = 0.04; H, W = int((Z1 - Z0) / c), int((U1 - U0) / c); uu = U0 + c * (np.arange(W) + 0.5); zz = Z1 - c * (np.arange(H) + 0.5); UU, ZZ = np.meshgrid(uu, zz)
    w = np.zeros((H, W))
    for (a0, a1, b0, b1, t) in tief: w[(UU >= a0) & (UU <= a1) & (ZZ >= b0) & (ZZ <= b1)] = -t
    return dict(w=w, gut=np.ones_like(w, bool), u0=U0, z1=Z1, zelle=c)


# f04-Nachbau: Sehne 1,6 m (Bild etwas breiter: Rand), 0..12 m
U0, U1, Z0, Z1, C = -1.3, 1.3, -0.5, 12.5, 0.01
F04 = [(0.15, 0.95, 0.0, 2.6, SAND), (0.33, 0.79, 0.3, 2.3, TUER),                        # Portal + Tuerblatt
       (0.45, 0.57, 4.61, 5.27, DUNKEL), (0.50, 0.64, 7.62, 8.21, DUNKEL), (0.55, 0.66, 9.81, 10.48, DUNKEL),   # drei Schlitze
       (0.1, 0.9, 3.3, 3.6, (60, 50, 40))]                                                 # Schild 'Zinnfiguren'
FAS04 = dict(id="f04", u=[-0.8, 0.8], z=[-0.03, 12.05], polys_uz=[[[-0.8, -0.03], [0.8, -0.03], [0.8, 12.05], [-0.8, 12.05]]])
ECHT, FALSCH_A, FALSCH_B = (0.34, 0.79, 0.32, 2.31), (-0.82, 0.79, 2.09, 8.01), (-0.81, 0.79, 6.58, 12.04)
ECHT_OA = (-0.163, 0.792, 0.315, 2.78)    # Tuerzone aus oeffnungen_aussen 1122zb (Erkennerkasten tuer + Bogen vereint)


def fall1():
    print("  Fall 1: f04 - echte Tuer gilt, falsche Tuerkaesten auf Putz verworfen")
    rgb = bild(U0, U1, Z0, Z1, C, F04); bel = np.ones(rgb.shape[:2], bool)
    bel[:, : int(0.5 / C)] = False; bel[:, -int(0.5 / C):] = False                    # ausserhalb der Sehne keine Fotozellen (runder Turm)
    npz = npz_flach(U0, U1, Z0, Z1, [(0.33, 0.79, 0.3, 2.3, 0.25)])
    r = EK.pruefen(rgb, bel, U0, Z1, C, ECHT, "tuer", npz, FAS04)
    pruef(r["gilt"] and any(b.startswith("dunkel") for b in r["belege"]), f"echte Tuer gilt: {r['grund'][:110]}")
    r = EK.pruefen(rgb, bel, U0, Z1, C, FALSCH_A, "tuer", npz, FAS04)
    pruef(not r["gilt"], f"falsche Tuer z 2,1-8,0 verworfen: {r['grund'][:120]}")
    r = EK.pruefen(rgb, bel, U0, Z1, C, FALSCH_B, "tuer", npz, FAS04)
    pruef(not r["gilt"] and "Boden" in r["grund"], f"falsche Tuer z 6,6-12 verworfen: {r['grund'][:120]}")
    return rgb, bel, npz


def fall2():
    print("  Fall 2: Rot-Proben - echte Oeffnungen bleiben, helles Feld verworfen")
    u0, u1, z0, z1, c = -4.0, 4.0, 0.0, 36.0, 0.02
    fel = [(-3.0, -1.6, 10.6, 12.4, SAND), (-2.35, -2.23, 10.9, 11.9, DUNKEL),            # Schlitz im Sandsteinfeld
           (1.0, 1.4, 33.0, 34.0, DUNKEL),                                                  # dunkles Fenster, heller Ring (f00 z 33)
           (-1.0, 3.0, 8.6, 11.0, SAND), (-0.6, 0.6, 8.8, 10.7, HELL), (-0.7, -0.6, 8.8, 10.7, DUNKEL), (0.6, 0.7, 8.8, 10.7, DUNKEL),   # Konsolenfeld
           (2.0, 3.2, 20.0, 20.15, SAND), (2.2, 3.0, 20.15, 22.4, DUNKEL)]                 # Tuer im OG ueber Schwelle (Balkon)
    rgb = bild(u0, u1, z0, z1, c, fel); bel = np.ones(rgb.shape[:2], bool)
    Fx = dict(id="f00", u=[u0, u1], z=[z0, z1], polys_uz=[[[u0, z0], [u1, z0], [u1, z1], [u0, z1]]])
    npz = npz_flach(u0, u1, z0, z1, [(-3.5, -2.5, 0.0, 5.0, 1.0)])
    r = EK.pruefen(rgb, bel, u0, z1, c, (-3.0, -1.6, 10.6, 12.4), "fenster", npz, Fx)
    pruef(r["gilt"] and any(b.startswith("rahmen") for b in r["belege"]), f"Schlitz im Sandsteinfeld gilt (rahmen): {r['grund'][:100]}")
    r = EK.pruefen(rgb, bel, u0, z1, c, (0.95, 1.45, 32.95, 34.05), "fenster", npz, Fx)
    pruef(r["gilt"], f"dunkles Fenster mit hellem Ring (f00 z 33) gilt: {r['grund'][:100]}")
    r = EK.pruefen(rgb, bel, u0, z1, c, (-0.65, 0.65, 8.8, 10.7), "fenster", npz, Fx)
    pruef(not r["gilt"], f"helles Feld zwischen dunklen Konsolen verworfen: {r['grund'][:110]}")
    r = EK.pruefen(rgb, bel, u0, z1, c, (-3.5, -2.5, 0.0, 5.0), "tuer", npz, Fx)
    pruef(r["gilt"] and any(b.startswith("tiefe") for b in r["belege"]), f"Durchfahrt ohne Dunkel, Tiefensprung 1,0 m gilt: {r['grund'][:100]}")
    r = EK.pruefen(rgb, bel, u0, z1, c, (2.1, 3.1, 20.1, 22.5), "tuer", npz, Fx)
    pruef(r["gilt"] and r["werte"].get("schwelle"), f"Tuer im OG ueber Schwelle gilt: {r['grund'][:100]}")
    r = EK.pruefen(rgb, np.zeros_like(bel), u0, z1, c, (-0.65, 0.65, 8.8, 10.7), "fenster", npz, Fx)
    pruef(r["gilt"] and r["grund"].startswith("keine Aussage"), "Box ohne Fotozellen: keine Aussage, bleibt")


def fall3(rgb, bel, npz):
    print("  Fall 3: schlitze_wandbild.bekannte_kaesten gibt die Flaeche falscher Tuerkaesten frei")
    import schlitze_wandbild as SW
    E = {"f04": dict(elemente=[dict(klasse="tuer", u0=a[0], u1=a[1], z0=a[2], z1=a[3], stimmen=8) for a in (ECHT, FALSCH_A, FALSCH_B)])}
    alt = SW.bekannte_kaesten({}, E, "f04")
    pruef(len(alt) == 3, f"ohne Pruefung (Altverhalten) 3 bekannte Kaesten ({len(alt)})")
    weg = []
    neu = SW.bekannte_kaesten({}, E, "f04", lambda x: EK.pruefen(rgb, bel, U0, Z1, C, (x["u0"], x["u1"], x["z0"], x["z1"]), x["klasse"], npz, FAS04), weg)
    pruef(len(neu) == 1 and abs(neu[0][2] - 0.32) < 1e-6, f"mit Pruefung nur die echte Tuer bekannt ({[tuple(round(v, 2) for v in k) for k in neu]})")
    pruef(len(weg) == 2 and all(x.get("grund") for x in weg), f"2 verworfene Kaesten mit Grund in der Liste ({len(weg)})")
    frei = [s for s in ((0.45, 0.57, 4.61, 5.27), (0.50, 0.64, 7.62, 8.21), (0.55, 0.66, 9.81, 10.48))
            if not any(min(s[1], k[1]) > max(s[0], k[0]) and min(s[3], k[3]) > max(s[2], k[2]) for k in neu)]
    pruef(len(frei) == 3, f"alle 3 Schlitze liegen ausserhalb bekannter Kaesten ({len(frei)})")


def fall4(rgb):
    print("  Fall 4: loch_gewaende - genau eine Tuer aus echter + falschen Tuerzonen, Doppelung erkannt")
    import cv2, loch_gewaende as LG
    d = temp_ordner("test_ekasten_"); fo = os.path.join(d, "fassade"); ff = os.path.join(d, "fassade_fein"); au = os.path.join(d, "audit")
    for p in (fo, ff, au): os.makedirs(p)
    rast = dict(u0=U0, z1=Z1, zelle=C, nu=rgb.shape[1], nz=rgb.shape[0])
    fas = dict(fassaden=[dict(FAS04, o=[0.0, 0.0], d=[1.0, 0.0], n=[0.0, 1.0], raster=rast)])
    json.dump(fas, open(os.path.join(ff, "fassaden.json"), "w")); json.dump(fas, open(os.path.join(fo, "fassaden.json"), "w"))
    im = rgb[..., ::-1].copy(); im[:, : int(0.5 / C)] = 0; im[:, -int(0.5 / C):] = 0; cv2.imwrite(os.path.join(ff, "ortho_f04_fein.png"), im)
    json.dump(dict(fassaden={"f04": dict(elemente=[])}), open(os.path.join(fo, "elemente.json"), "w"))
    n = npz_flach(U0, U1, Z0, Z1, [(0.33, 0.79, 0.3, 2.3, 0.25)]); np.savez(os.path.join(fo, "tiefe_f04.npz"), **n)
    ob = os.path.join(au, "oeffnungen_auto.json"); json.dump({}, open(ob, "w"))
    for name, zonen, soll_tueren, soll_text in (("falsche Zonen", [ECHT_OA, FALSCH_A, FALSCH_B], 1, "Erkennerkasten verworfen"),
                                               ("Doppelung", [ECHT_OA, (0.1, 0.95, 0.2, 2.65)], 1, "Doppelung")):
        fa = os.path.join(au, "fenster_auto.json"); json.dump({"f04": dict(o=[0.0, 0.0], d=[1.0, 0.0], n=[0.0, 1.0], fenster=[])}, open(fa, "w"))
        oa = os.path.join(au, "oeffnungen_aussen.json")
        json.dump({"f04": dict(o=[0.0, 0.0], d=[1.0, 0.0], n=[0.0, 1.0], oeffnungen=[dict(klasse="tuer", zone=list(z), tiefe=0.0, flach=True) for z in zonen])}, open(oa, "w"))
        rc = LG.main([fa, fo, ff, "--oeffnungen", oa, "--oeffnungen_auto", ob])
        J = json.load(open(fa))["f04"]["fenster"]; tu = [e for e in J if e.get("art") == "tuer"]
        B = json.load(open(os.path.join(au, "loch_gewaende.json")))["f04"]
        pruef(rc == 0 and len(tu) == soll_tueren and abs(tu[0]["u0"] - 0.33) < 0.05 and tu[0]["z0"] < 0.4,
              f"{name}: {len(tu)} Tuer(en) (Soll {soll_tueren}), Loch u {tu[0]['u0'] if tu else None}")
        pruef(any(soll_text in r.get("urteil", "") for r in B), f"{name}: Bericht nennt '{soll_text}'")
        if name == "falsche Zonen":
            pruef(not any(e for e in J if e.get("art") != "tuer"), "falsche Zonen geben keinen Schlitz als 'Loch' der Tuerzone (Schlitze kommen ueber schlitze_wandbild)")


def main():
    rgb, bel, npz = fall1(); fall2(); fall3(rgb, bel, npz); fall4(rgb)
    print("ERGEBNIS: " + ("alle Proben bestanden" if F == 0 else f"{F} FEHLER")); return 1 if F else 0


if __name__ == "__main__": sys.exit(main())
