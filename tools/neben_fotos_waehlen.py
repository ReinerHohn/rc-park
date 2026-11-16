#!/usr/bin/env python3
"""neben_fotos_waehlen.py <objekt.json> [--eintragen] [--je 1] - je Gebaeudeseite das beste Vergleichsfoto fuer 'Modell neben Foto' und das Umriss-Tor waehlen.

Anlass 16.11.2026: Kettenobjekte hatten kein 'neben_fotos' in objekt.json. Folge: bauen_abnehmen zeigte "0 Foto-Paare", umriss_tor.py lief LEER mit rc 0 durch -
die Pflicht "nach jedem Bau Modell neben Foto, je Seite mindestens ein Foto" war fuer jedes automatisch gebaute Objekt unerfuellt, ohne dass es jemand merkte.
Wahl je Seite (+x, -x, +y, -y des Rahmens): Messkamera K-*.json (nicht 'tiefe_unsicher', Standort -3 .. 60 m ueber Gelaende, Foto im fotos_dir vorhanden),
die auf diese Seite schaut (Winkel Standort-Richtung gegen Seitennormale < 40 Grad), den Modellquader (aus dem STL) oben und seitlich ganz im Bild hat
und ihn moeglichst gross zeigt; gibt es fuer eine Seite keins, das beste seitlich angeschnittene (Oberkante im Bild, so gemeldet). Wertung = Bildanteil des Quaders x Kosinus des Winkels.
Ausgabe: Liste je Seite; --eintragen schreibt objekt.json 'neben_fotos' NUR, wenn dort noch keine stehen (Geprueftes wird nie ueberschrieben).
rc 3, wenn eine Seite kein Foto bekommt (= Fotoauftrag fuer diese Seite, kein Fehler der Rechnung).
Grenze: waehlt nach Geometrie, nicht nach Bildguete (Gegenlicht, Baum davor sieht dieses Werkzeug nicht) - die Bilder audit/neben_<foto>.jpg ansehen.
"""
import sys, os, json, glob, numpy as np, cv2, trimesh
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dach_bauen import seiten_aus_rahmen


def main():
    arg = [x for x in sys.argv[1:] if not x.startswith("--")]
    if not arg: sys.exit(__doc__)
    je = int(sys.argv[sys.argv.index("--je") + 1]) if "--je" in sys.argv else 1
    if "--je" in sys.argv: arg = [x for x in arg if x != str(je)]
    op = os.path.abspath(arg[0]); od = os.path.dirname(op); root = os.path.dirname(os.path.dirname(od)); obj = json.load(open(op)); fd = os.path.join(root, obj["fotos_dir"])
    m = trimesh.load(os.path.join(root, obj["stl"])); lo, hi = [np.asarray(v, float) * (float(obj.get("stl_massstab", 87)) / 1000.0 if obj.get("stl_einheit_mm", True) else 1.0) for v in m.bounds]
    E = np.array([[x, y, z] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (max(lo[2], 0.0), hi[2])]); mitte = (lo + hi) / 2
    normale = {"+x": (1, 0), "-x": (-1, 0), "+y": (0, 1), "-y": (0, -1)}; name = seiten_aus_rahmen(obj) if obj.get("rahmen") else {k: k for k in normale}; kand = {k: [] for k in normale}; n_k = 0
    for kf in sorted(glob.glob(os.path.join(od, "messprotokoll", "K-*.json"))):
        try: k = json.load(open(kf)).get("kamera")
        except Exception: continue
        nm = os.path.basename(kf)[2:-5]
        if not isinstance(k, dict) or "rvec" not in k or k.get("tiefe_unsicher") or not glob.glob(os.path.join(fd, glob.escape(nm) + ".*")): continue
        R = cv2.Rodrigues(np.array(k["rvec"], float))[0]; t = np.array(k["t"], float).ravel(); C = -R.T @ t; W, H = k.get("bild") or (2 * k["cx"], 2 * k["cy"]); n_k += 1
        if not (-3.0 <= C[2] <= 60.0): continue
        X = E @ R.T + t
        if (X[:, 2] <= 1.0).any(): continue
        u = k["f_px"] * X[:, 0] / X[:, 2] + k["cx"]; v = k["f_px"] * X[:, 1] / X[:, 2] + k["cy"]
        if v.min() < 0.02 * H or v.min() > 0.9 * H or u.max() < 0.2 * W or u.min() > 0.8 * W: continue  # Oberkante im Bild (unten darf abgeschnitten sein)
        ganz = u.min() >= 0.01 * W and u.max() <= 0.99 * W                                             # seitlich ganz im Bild = Stufe 1; sonst Stufe 2 (angeschnitten), nur wenn Stufe 1 leer bleibt
        anteil = (min(u.max(), W) - max(u.min(), 0)) * (min(v.max(), H) - v.min()) / (W * H) * (1.0 if ganz else 0.001); r = (C - mitte)[:2]; r /= max(np.linalg.norm(r), 1e-9)
        for s, nv in normale.items():
            c = float(r @ np.array(nv, float))
            if c > np.cos(np.radians(40)) and anteil * (1 if ganz else 1000) > 0.04: kand[s].append((anteil * c, nm, round(float(anteil if ganz else anteil * 1000), 2), ganz, round(float(np.degrees(np.arccos(min(c, 1.0))))), round(float(np.linalg.norm((C - mitte)[:2])))))
    wahl = []; leer = []
    print(f"{n_k} Messkameras mit Foto geprueft")
    for s in normale:
        best = sorted(kand[s], reverse=True)[:je]
        if not best: leer.append(name[s]); print(f"  Seite {name[s]:5s} ({s}): KEIN Foto zeigt das Gebaeude von dieser Seite ganz"); continue
        for w, nm, ant, gz, wi, dist in best: wahl.append(nm); print(f"  Seite {name[s]:5s} ({s}): {nm[-44:]}  Bildanteil {ant}, {wi} Grad schraeg, {dist} m entfernt ({len(kand[s])} Kandidaten)" + ("" if gz else "  SEITLICH ANGESCHNITTEN (kein Foto zeigt die Seite ganz)"))
    wahl = list(dict.fromkeys(wahl))
    if "--eintragen" in sys.argv and wahl:
        if obj.get("neben_fotos"): print("objekt.json hat schon neben_fotos - nichts ueberschrieben")
        else: obj["neben_fotos"] = wahl; json.dump(obj, open(op, "w"), indent=1, ensure_ascii=False); print(f"-> {len(wahl)} neben_fotos in objekt.json eingetragen")
    if leer: print("OHNE Vergleichsfoto: " + ", ".join(leer) + " (Fotoauftrag)")
    return 3 if leer else 0


if __name__ == "__main__":
    sys.exit(main())
