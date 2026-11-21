#!/usr/bin/env python3
"""seiten_blick_tor.py <sparse-modell> <seiten.json> [--min 5] [--winkel 60] [--aus bericht.json]

HARTES TOR nach dem Mapper gegen SEITENVERKLEBUNG, ohne Vorwissen (21.11.2026, Martinstor: 8,4-h-Mapperlauf legte 51 Sued-Bilder auf die Nordwand, tools/modell_zerlegen.py
meldete "ein Stueck", das GPS-Tor hatte keine GPS-Fotos).
Eingang: seiten.json aus tools/seiten_erkennen.py (Bildgruppen + Verbindungen mit Urteil des Paar-Pruefers). Zwei Gruppen mit Urteil 'verwechselt' zeigen AEHNLICHE, aber
VERSCHIEDENE Waende. Stehen beide im selben Modell und blicken ihre Kameras im Mittel in dieselbe Richtung (Winkel < --winkel Grad), dann hat der Mapper die eine Wand auf
die andere gelegt. Richtig getrennte Gegenseiten blicken > 120 Grad gegeneinander; Nachbarseiten ~90 Grad.
Je Gruppenpaar: Zahl der registrierten Bilder, Winkel der mittleren Blickrichtungen, Abstand der Standorte in Einheiten der Szenengroesse.
rc 0 = keine Verklebung (oder kein pruefbares Paar - wird gemeldet), rc 3 = mindestens ein verklebtes Gruppenpaar (Modell NICHT weiterverwenden).
GRENZE: prueft nur Gruppenpaare, die die Seitenerkennung als 'verwechselt' kennt; ohne seiten.json kein Urteil.
"""
import sys, os, json, argparse
import numpy as np


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("modell"); ap.add_argument("seiten"); ap.add_argument("--min", type=int, default=5); ap.add_argument("--winkel", type=float, default=60.0); ap.add_argument("--aus"); a = ap.parse_args()
    import pycolmap
    r = pycolmap.Reconstruction(a.modell); d = json.load(open(a.seiten)); g = {os.path.basename(k): v for k, v in d["gemeinschaft"].items()}; C = {}
    for im in r.images.values():
        w = im.cam_from_world() if callable(im.cam_from_world) else im.cam_from_world; R = w.rotation.matrix(); C[os.path.basename(im.name)] = (-R.T @ w.translation, R[2])
    G = {}
    for n, (c, v) in C.items():
        if n in g: G.setdefault(g[n], []).append((c, v))
    alle = np.array([c for c, _ in C.values()]); gr = float(np.linalg.norm(np.percentile(alle, 95, 0) - np.percentile(alle, 5, 0))) or 1.0; B = []
    for V in d.get("verbindungen", []):
        if V.get("urteil") != "verwechselt" or len(G.get(V["a"], [])) < a.min or len(G.get(V["b"], [])) < a.min: continue
        va = np.mean([v for _, v in G[V["a"]]], 0); vb = np.mean([v for _, v in G[V["b"]]], 0); w = float(np.degrees(np.arccos(np.clip(va @ vb / np.linalg.norm(va) / np.linalg.norm(vb), -1, 1))))
        ab = float(np.linalg.norm(np.median([c for c, _ in G[V["a"]]], 0) - np.median([c for c, _ in G[V["b"]]], 0)) / gr)
        B.append(dict(a=V["a"], b=V["b"], bilder_a=len(G[V["a"]]), bilder_b=len(G[V["b"]]), paare=V.get("paare"), winkel_grad=round(w, 1), abstand_rel=round(ab, 3), verklebt=bool(w < a.winkel)))
    B.sort(key=lambda b: b["winkel_grad"]); kl = [b for b in B if b["verklebt"]]
    print(f"{len(C)} Kameras, {len(G)} Bildgruppen im Modell; {len(B)} pruefbare 'verwechselt'-Gruppenpaare, davon VERKLEBT (Blickwinkel < {a.winkel:.0f} Grad): {len(kl)}")
    for b in B[:8]: print(f"  Gruppe {b['a']} ({b['bilder_a']} Bilder) <-> {b['b']} ({b['bilder_b']}): Blickwinkel {b['winkel_grad']} Grad, Standorte {b['abstand_rel']} der Szene auseinander" + ("  VERKLEBT" if b["verklebt"] else ""))
    if not B: print("HINWEIS: kein pruefbares Gruppenpaar (jede verwechselte Gruppe steht hoechstens einseitig im Modell) - keine Verklebung moeglich, aber auch nur EINE Seite im Modell")
    if a.aus: json.dump(dict(modell=a.modell, seiten=a.seiten, paare=B, verklebt=len(kl)), open(a.aus, "w"), indent=1)
    print("SEITEN-BLICK-TOR:", "DURCHGEFALLEN - Seiten aufeinander geklebt" if kl else "bestanden"); return 3 if kl else 0


if __name__ == "__main__": sys.exit(main())
