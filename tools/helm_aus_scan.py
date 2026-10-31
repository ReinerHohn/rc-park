#!/usr/bin/env python3
"""helm_aus_scan.py — Hybrid: Schaft/Tor aus dem Generator-Modell (H0, mm), Helm aus den gemessenen Scan-Breiten.

Der Generator (bauwerk_generator.py) liefert saubere Wand-/Torgeometrie, macht den Helm aber nur nach Parametern.
Der Scan-Koerper (scan_zu_koerper.py, Meter) kennt die tatsaechliche Helmmasse. Dieses Tool schneidet das Generator-Modell
bei --ab-m ab und setzt darauf einen Helm, dessen Querschnitte (quadratisch, auf Generator-Achse zentriert) die Scan-Breite
je Hoehe haben, abzueglich --schrumpf-m (das Luecken-Schliessen im Scan blaeht die Kontur auf).

Nutzung:
  helm_aus_scan.py generator.stl scan_koerper.stl ausgabe.stl --hoehe-m 45.9 --ab-m 36 [--schrumpf-m 0.6] [--massstab 87]
Beide Modelle: generator.stl in mm (1:massstab), scan_koerper.stl in Metern (unskaliert, Hoehe wird auf --hoehe-m gestreckt).
"""
import argparse, json
import numpy as np
import trimesh


def quader_profil(mitte, breiten, zs):
    """Loft aus quadratischen Querschnitten (Breite je z) -> geschlossener Koerper (Pyramidenstumpf-Folge)."""
    n = len(zs)
    v = []
    for (cx, cy), w, z in zip([mitte] * n, breiten, zs):
        h = max(w, 0.05) / 2
        v += [[cx - h, cy - h, z], [cx + h, cy - h, z], [cx + h, cy + h, z], [cx - h, cy + h, z]]
    f = []
    for i in range(n - 1):
        a, b = 4 * i, 4 * (i + 1)
        for k in range(4):
            k2 = (k + 1) % 4
            f += [[a + k, a + k2, b + k2], [a + k, b + k2, b + k]]
    f += [[0, 2, 1], [0, 3, 2]]                                       # Boden
    t = 4 * (n - 1); f += [[t, t + 1, t + 2], [t, t + 2, t + 3]]      # Deckel
    m = trimesh.Trimesh(np.array(v, float), np.array(f), process=True)
    trimesh.repair.fix_normals(m)
    return m


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("generator"); ap.add_argument("scan"); ap.add_argument("ausgabe")
    ap.add_argument("--hoehe-m", type=float, required=True)
    ap.add_argument("--ab-m", type=float, required=True, help="ab dieser Hoehe kommt der Helm aus dem Scan")
    ap.add_argument("--schrumpf-m", type=float, default=0.6)
    ap.add_argument("--massstab", type=float, default=87.0)
    ap.add_argument("--schritt-m", type=float, default=1.0)
    a = ap.parse_args()
    k = 1000.0 / a.massstab                                           # Meter -> mm

    g = trimesh.load(a.generator)
    s = trimesh.load(a.scan)
    s.apply_scale(a.hoehe_m / s.extents[2]); s.apply_translation([0, 0, -s.bounds[0, 2]])

    # Scan-Breite je Hoehe (Mittel aus beiden Achsen, Sicherheitsabstand zu Kanten der Schichtstapelung)
    zs = np.arange(a.ab_m, a.hoehe_m - 0.2, a.schritt_m)
    breiten = []
    for z in zs:
        sec = s.section(plane_origin=[0, 0, z + 0.1], plane_normal=[0, 0, 1])
        w = (sec.bounds[1] - sec.bounds[0])[:2].mean() if sec is not None else 0.0
        breiten.append(max(w - a.schrumpf_m, 0.4))
    breiten = np.minimum.accumulate(np.array(breiten))                 # Helm wird nach oben nie breiter
    zs = np.append(zs, a.hoehe_m); breiten = np.append(breiten, 0.05)  # Spitze
    print("Helmprofil [m]:", [(round(float(z), 1), round(float(b), 1)) for z, b in zip(zs, breiten)])

    # Generator unterhalb ab-m behalten
    cut = g.slice_plane([0, 0, a.ab_m * k], [0, 0, -1], cap=True)
    achse = (cut.bounds[0, :2] + cut.bounds[1, :2]) / 2
    helm = quader_profil(achse, breiten * k, zs * k)
    ergebnis = trimesh.boolean.union([cut, helm], engine="manifold")
    ergebnis.export(a.ausgabe)
    bericht = {"ausdehnung_mm": [round(float(x), 1) for x in ergebnis.extents], "wasserdicht": bool(ergebnis.is_watertight),
               "flaechen": int(len(ergebnis.faces)), "ab_m": a.ab_m, "schrumpf_m": a.schrumpf_m,
               "helm_breiten_m": [round(float(b), 2) for b in breiten]}
    json.dump(bericht, open(a.ausgabe.rsplit(".", 1)[0] + ".bericht.json", "w"), indent=1)
    print(json.dumps({k_: v for k_, v in bericht.items() if k_ != "helm_breiten_m"}))


if __name__ == "__main__":
    main()
