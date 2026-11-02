#!/usr/bin/env python3
"""abdeckung.py - Wo fehlen Fotos? Aufnahme-Assistent aus den vorhandenen Netzen (Register BI).

Liest je Seitennetz (modelle/<objekt>/sfm/sparse_modell_<seite>, Modellsystem in Metern) die Kamerapositionen und die dichte Wolke
(sfm/dicht_<seite>_modell.npy) und meldet, WAS ZU FOTOGRAFIEREN IST: Richtungssektoren ohne Kameras, zu geringe Abstaende (steiler Blick
nach oben -> Perspektivverzerrung, kaum Basis), fehlende Kamerahoehen, duenne Wolke in den oberen Schichten.
  /media/oem/scan/venv-colmap/bin/python -I tools/abdeckung.py modelle/<objekt>/objekt.json [--hoehe 65] [--schreiben]
Schwellen sind Faustwerte (ANNAHME, Quelle: Register BI: Suednetz Martinstor 8-17 m Abstand -> verbogene Wolke; Nordnetz 27-150 m ok):
  Sektor ok >= 2 Kameras je 45 Grad; Abstand ok >= 1,0 x Turmhoehe nicht noetig, aber Hoehenwinkel zur Spitze <= 55 Grad (atan(H/d));
  Kamerahoehe: mind. eine Kamera >= 8 m (erhoehter Standort) fuer die obere Haelfte; Wolke: Punkte je 5-m-Schicht >= 20 % des Medians der unteren Schichten.
"""
import sys, os, json, argparse, numpy as np
import pycolmap

def kameras(d):
    r = pycolmap.Reconstruction(d); return np.array([np.array(im.projection_center()) for im in r.images.values()])

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--hoehe", type=float); ap.add_argument("--schreiben", action="store_true")
    ap.add_argument("--max-winkel", type=float, default=55.0); ap.add_argument("--min-hoehe", type=float, default=8.0)
    a = ap.parse_args(); od = os.path.dirname(os.path.abspath(a.objekt)); sd = os.path.join(od, "sfm"); obj = json.load(open(a.objekt))
    H = a.hoehe
    if H is None:
        try: H = float(json.load(open(os.path.join(od, "masse.json")))["masse"]["H_TOTAL"]["wert"])
        except Exception: H = 60.0
    L = [f"# Abdeckung {obj.get('name', os.path.basename(od))} (automatisch, Turmhoehe {H:.0f} m)", ""]; fehlt = []
    seiten = sorted(d[len("sparse_modell_"):] for d in os.listdir(sd) if d.startswith("sparse_modell_") and os.path.isdir(os.path.join(sd, d)))
    for s in seiten:
        P = kameras(os.path.join(sd, f"sparse_modell_{s}")); az = np.degrees(np.arctan2(P[:, 1], P[:, 0])) % 360; dist = np.hypot(P[:, 0], P[:, 1]); ang = np.degrees(np.arctan2(H - P[:, 2], dist))
        sek, _ = np.histogram(az, bins=range(0, 361, 45)); leer = [f"{i * 45}-{i * 45 + 45}" for i, n in enumerate(sek) if n < 2]
        L += [f"## Netz {s}: {len(P)} Kameras", f"- Abstand zur Achse {dist.min():.0f}..{dist.max():.0f} m (Median {np.median(dist):.0f}); Hoehe {P[:, 2].min():.0f}..{P[:, 2].max():.0f} m (Median {np.median(P[:, 2]):.0f})",
              f"- Blickwinkel zur Spitze {ang.min():.0f}..{ang.max():.0f} Grad (Median {np.median(ang):.0f}); steiler als {a.max_winkel:.0f} Grad: {int((ang > a.max_winkel).sum())} von {len(P)}",
              f"- Richtung (Grad, 45er-Sektoren 0..360): {sek.tolist()}"]
        if (ang > a.max_winkel).mean() > 0.5: fehlt.append(f"Netz {s}: {int((ang > a.max_winkel).sum())} von {len(P)} Fotos schauen steiler als {a.max_winkel:.0f} Grad zur Spitze (Abstand Median {np.median(dist):.0f} m) -> weiter weg stellen: mind. {H / np.tan(np.radians(a.max_winkel)):.0f} m, besser 1-1,5 x Turmhoehe")
        if len(leer) >= 6: fehlt.append(f"Netz {s}: Kameras nur in {8 - len(leer)} von 8 Richtungssektoren; ein Bogen von ca. 90-120 Grad um den Turm in 10-15-Grad-Schritten fehlt (leer: {', '.join(leer)})")
        elif leer: fehlt.append(f"Netz {s}: wenige Kameras in den Sektoren {', '.join(leer)} Grad")
        if P[:, 2].max() < a.min_hoehe: fehlt.append(f"Netz {s}: keine Kamera ueber {a.min_hoehe:.0f} m Hoehe (hoechste {P[:, 2].max():.0f} m) -> erhoehter Standort (Fenster, Parkhaus, Hang) fuer die obere Haelfte")
        pf = os.path.join(sd, f"dicht_{s}_modell.npy")
        if os.path.exists(pf):
            X = np.load(pf); edges = np.arange(0, np.ceil(H / 5) * 5 + 5, 5); h, _ = np.histogram(X[:, 2], bins=edges); ref = np.median(h[1:max(2, len(h) // 2)]) if len(h) > 2 else h.max()
            duenn = [f"{int(edges[i])}-{int(edges[i + 1])}" for i in range(len(h)) if h[i] < 0.2 * ref and edges[i] > 5]
            L += [f"- Wolkenpunkte je 5-m-Schicht: {h.tolist()} (Referenz Median untere Haelfte {ref:.0f})"]
            if duenn: fehlt.append(f"Netz {s}: Wolke duenn (< 20 % des Medians) in {', '.join(duenn)} m -> Tele/erhoehter Standort fuer diese Hoehen")
        L.append("")
    L += ["## Was fotografieren" if fehlt else "## Abdeckung ausreichend nach diesen Faustwerten", ""] + [f"- {f}" for f in fehlt]
    L += ["", "Hinweis: Originalbilder ohne Zuschnitt/Filter, fester Zoom (Tele getrennt), bedeckter Himmel, Boden-/Gebaeudeecken im Bild lassen (amtliche Anker), mind. 70 % Ueberlappung."]
    txt = "\n".join(L); print(txt)
    if a.schreiben: open(os.path.join(od, "ABDECKUNG.md"), "w").write(txt + "\n"); print("\ngeschrieben:", os.path.join(od, "ABDECKUNG.md"))

if __name__ == "__main__":
    main()
