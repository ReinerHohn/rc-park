#!/usr/bin/env python3
"""wolke_farbmerkmal.py - GENERISCH: Lage eines FARBIGEN Fassadenmerkmals (Zifferblatt, Tafel, Relief) aus der dichten Fotowolke.

Die Wolke traegt Fotofarben; ein Merkmal mit eigener Farbe (goldene Stundenmarken/Zeiger der Uhr, gruene Kupferteile) laesst sich
ohne Kamera und ohne Modell lokalisieren: Punkte der Wandfront (|tief - Front(z)| < 0,8) im Fenster (|quer| < halb, z0..z1) nach
HSV-Klasse filtern -> Schwerpunkt (z, quer), Radius (p90 des Abstands), Anzahl. Ergebnis ist ein MASS mit Quelle (Wolke, Farbklasse).

  wolke_farbmerkmal.py modelle/<objekt>/objekt.json nord --farbe gold --z 20 32 --halb 3 \
      --pruefung "Uhr: Mitte z (m)" --messung '{"typ":"relief_mitte","seite":"-x","z0":20,"z1":27.5,"halb":3.0,"schwelle":0.08}' --feld z --toleranz 0.4
Farbklassen (OpenCV-HSV, H 0-180): gold = H 15-35 S>80, gruen = H 60-100 S>60, rot = H<8|>170 S>90, weiss = S<30 V>200.
Mit --pruefung wird die Zeile in der Masstabelle angelegt/aktualisiert (quelltyp sfm_bodenanker, Soll = Schwerpunkt +- Toleranz) -
die Modellmessung muss der Pruefstand kennen (z. B. relief_mitte: Schwerpunkt der aus der Wandflaeche heraustretenden Zellen).
"""
import sys, os, json, argparse, numpy as np

KLASSEN = {"gold": lambda h, s, v: (h >= 15) & (h <= 35) & (s > 80), "gruen": lambda h, s, v: (h >= 60) & (h <= 100) & (s > 60),
           "rot": lambda h, s, v: ((h < 8) | (h > 170)) & (s > 90), "weiss": lambda h, s, v: (s < 30) & (v > 200)}

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("seite"); ap.add_argument("--farbe", default="gold"); ap.add_argument("--z", nargs=2, type=float, required=True)
    ap.add_argument("--halb", type=float, default=3.0); ap.add_argument("--dicht"); ap.add_argument("--pruefung"); ap.add_argument("--messung", help="JSON der Modellmessung fuer den Pruefstand")
    ap.add_argument("--feld", default="z", help="welche Groesse geprueft wird: z | quer | radius"); ap.add_argument("--merkmal", default="absolut_hoehe", help="Merkmal fuer die Quellen-Blindheit des Pruefstands (Hoehe eines Merkmals = absolut_hoehe)"); ap.add_argument("--toleranz", type=float, default=0.4)
    a = ap.parse_args(); import cv2
    od = os.path.dirname(os.path.abspath(a.objekt)); s = a.seite.lower()
    pf = os.path.join(od, a.dicht or f"sfm/dicht_{s}_entzerrt.npy"); P = np.load(pf).astype(float)
    cf = pf.replace("_entzerrt.npy", "_modell.npy").replace("_modell.npy", "_farben.npy"); C = np.load(cf)
    tief, sgn, quer = {"nord": ("x", -1.0, "y"), "sued": ("x", 1.0, "y"), "ost": ("y", 1.0, "x"), "west": ("y", -1.0, "x")}[s]; it = 0 if tief == "x" else 1; iq = 1 - it
    hsv = cv2.cvtColor(C.reshape(-1, 1, 3).astype(np.uint8), cv2.COLOR_RGB2HSV).reshape(-1, 3).astype(float)
    # Front je 0,5-m-Schicht (Median der Tiefe im Fenster), Frontpunkte = |tief - Front| < 0,8
    fenster = (P[:, 2] >= a.z[0]) & (P[:, 2] < a.z[1]) & (np.abs(P[:, iq]) < a.halb) & (sgn * P[:, it] > 0.5)
    front = np.zeros(len(P), bool)
    for z in np.arange(a.z[0], a.z[1], 0.5):
        k = fenster & (P[:, 2] >= z) & (P[:, 2] < z + 0.5)
        if k.sum() < 10: continue
        xf = np.median(sgn * P[k, it]); front |= k & (np.abs(sgn * P[:, it] - xf) < 0.8)
    kl = KLASSEN[a.farbe](hsv[:, 0], hsv[:, 1], hsv[:, 2]) & front
    n = int(kl.sum()); print(f"Seite {s}: {int(front.sum())} Frontpunkte im Fenster z {a.z[0]}-{a.z[1]}, |{quer}| < {a.halb}; Farbklasse '{a.farbe}': {n} Punkte ({100 * n / max(front.sum(), 1):.1f} %)")
    if n < 20: sys.exit("zu wenige Punkte der Farbklasse - Fenster/Farbe pruefen")
    Q = P[kl]; zc, qc = float(np.median(Q[:, 2])), float(np.median(Q[:, iq]))
    # Ausreisser (einzelne Farbpunkte weitab) abwerfen: 2 Runden, Abstand <= 1,5 x p75
    for _ in range(2):
        r = np.hypot(Q[:, 2] - zc, Q[:, iq] - qc); Q = Q[r <= 1.5 * np.percentile(r, 75)]; zc, qc = float(np.median(Q[:, 2])), float(np.median(Q[:, iq]))
    r = np.hypot(Q[:, 2] - zc, Q[:, iq] - qc); rad = float(np.percentile(r, 90))
    hist = np.histogram(P[kl][:, 2], bins=np.arange(a.z[0], a.z[1] + 0.01, 0.5))[0]
    print("  z-Verteilung (0,5 m ab %.1f): %s" % (a.z[0], " ".join(str(int(x)) for x in hist)))
    print(f"  Schwerpunkt z {zc:.2f} m, {quer} {qc:.2f} m, Radius (p90) {rad:.2f} m, {len(Q)} Punkte nach Ausreisserfilter")
    erg = dict(seite=s, farbe=a.farbe, fenster=dict(z=a.z, halb=a.halb), punkte=n, z=round(zc, 2), quer=round(qc, 2), radius_p90=round(rad, 2), wolke=os.path.basename(pf))
    if a.pruefung:
        tp = os.path.join(od, "masstabelle.json"); T = json.load(open(tp)); wert = "farb_" + "".join(ch if ch.isalnum() else "_" for ch in a.pruefung.lower()).strip("_")
        soll_w = {"z": zc, "quer": qc, "radius": rad}[a.feld]; soll = [round(soll_w - a.toleranz, 2), round(soll_w + a.toleranz, 2)]
        if a.messung: T["messungen"][wert] = json.loads(a.messung)
        quelle = f"wolke_farbmerkmal.py: dichte Wolke {s} (entzerrt), Farbklasse {a.farbe} an der Wandfront: {n} Punkte, Schwerpunkt z {zc:.2f} / {quer} {qc:.2f}, Radius p90 {rad:.2f}"
        name_wert = f"{wert}_{a.feld}" if a.messung and json.loads(a.messung).get("typ") in ("relief_mitte",) else wert
        for pr in T["pruefungen"]:
            if pr["name"] == a.pruefung:
                if pr["soll"] != soll: pr.setdefault("historie", []).append({"datum": "auto", "alt_soll": pr["soll"], "grund": "wolke_farbmerkmal.py neu gerechnet"}); pr["soll"] = soll; pr["quelle"] = quelle
                pr["wert"] = name_wert; break
        else:
            T["pruefungen"].append(dict(name=a.pruefung, wert=name_wert, soll=soll, quelle=quelle, quelltyp="sfm_bodenanker", merkmal=a.merkmal, massstab="LoD2-Eckkanten + Wandebene", protokoll=f"wolke_farbmerkmal {s} {a.farbe}"))
        json.dump(T, open(tp, "w"), indent=1, ensure_ascii=False); print(f"  Masstabelle: Pruefung '{a.pruefung}' Soll {soll} (Messung {name_wert})")
    print(json.dumps(erg, ensure_ascii=False))

if __name__ == "__main__":
    main()
