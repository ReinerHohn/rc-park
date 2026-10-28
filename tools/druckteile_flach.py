#!/usr/bin/env python3
"""druckteile_flach.py — Modell in FLACH druckbare, FARB-getrennte Teile zerlegen (Steck-Bausatz).

Ziel (User): jedes Panel liegend drucken (schnell, stützenfrei), je Teil eine FARBE, dann zusammenstecken.
Zuordnung je Segment → PANEL (Fassade/Dach/Wände/Erker/Zier) + FARBE. Fassade wird flach gelegt
(Relief nach oben). Ausgabe: je Panel+Farbe eine STL in modelle/kaufhaus_freiburg/flachteile/.

Lauf: python3 tools/druckteile_flach.py   (System-python3, trimesh)
"""
import os, glob
import numpy as np, trimesh

MDIR = "/home/md/git/rc-park/modelle/kaufhaus_freiburg"
OUT = f"{MDIR}/flachteile"; os.makedirs(OUT, exist_ok=True)

# Panel-Zuordnung je Segment (Name). Zier = aufsteckbare Goldteile.
PANEL = {
    "fassade": "front", "balken": "front", "cornice": "front", "konsolen": "front", "piers": "front",
    "lisenen": "front", "boegen": "front", "galerie": "front", "nische": "front", "first": "front",
    "krabben": "front", "firstkamm": "front", "laube": "front", "rahmen": "front",
    "statuen": "zier", "baldachin": "zier", "konsole": "zier", "balkon": "zier", "gitter": "zier",
    "wappen": "zier", "wappen_rot": "zier", "wappen_blau": "zier",
    "dach": "dach", "gauben": "dach", "gauben_dach": "dach", "gauben_rahmen": "dach",
    "waende": "waende", "giebel": "waende", "seitenglas": "waende",
    "erker": "erker", "helm": "erker", "helm_rot": "erker", "helm_hell": "erker",
    "helm_gruen": "erker", "fenster": "erker",
    # NUR-Textur/Bemalung → nicht als Teil:
    "sprossen": None, "dachmuster": None, "dachrauten": None,
}
# Farbname je Segment (fürs Datei-Label + Druckfarbe)
FARBE = {
    "fassade": "rot", "balken": "rot", "piers": "rot", "nische": "rot", "krabben": "rot", "giebel": "rot",
    "waende": "rot", "laube": "dunkel", "erker": "rot",
    "cornice": "gold", "konsolen": "gold", "lisenen": "gold", "boegen": "gold", "first": "gold",
    "rahmen": "gold", "konsole": "gold", "baldachin": "gold", "firstkamm": "gold",
    "dach": "gruen", "gauben": "dunkel", "gauben_dach": "gruen", "gauben_rahmen": "hell",
    "gauben_dach2": "gruen", "helm": "gold", "helm_gruen": "gruen", "helm_rot": "rot", "helm_hell": "creme",
    "statuen": "silber", "gitter": "dunkel", "balkon": "rot", "galerie": "rot",
    "wappen": "gold", "wappen_rot": "rot", "wappen_blau": "blau", "fenster": "dunkel", "seitenglas": "dunkel",
}
FLATTEN = {  # Rotation (Grad um X), um das Panel liegend mit Relief nach oben zu legen
    "front": -90, "waende": -90, "dach": 0, "erker": 0, "zier": -90,
}


def main():
    groups = {}  # (panel,farbe) -> list meshes
    for f in sorted(glob.glob(f"{MDIR}/khm_*.stl")):
        nm = os.path.basename(f).replace("khm_", "").replace(".stl", "")
        pan = PANEL.get(nm, "front")
        if pan is None:
            continue
        groups.setdefault((pan, FARBE.get(nm, "rot")), []).append((nm, trimesh.load(f, process=True)))
    print(f"{'Panel':<8}{'Farbe':<8}{'Segmente':<30}{'Datei'}")
    for (pan, far), items in sorted(groups.items()):
        m = trimesh.util.concatenate([mm for _, mm in items])
        ang = FLATTEN.get(pan, 0)
        if ang:
            m.apply_transform(trimesh.transformations.rotation_matrix(np.radians(ang), [1, 0, 0]))
        m.apply_translation(-m.bounds[0])                      # auf den Nullpunkt (auf die Bettebene)
        path = f"{OUT}/kh_{pan}_{far}.stl"; m.export(path)
        ext = (m.extents*1000).round(0)
        print(f"{pan:<8}{far:<8}{','.join(n for n,_ in items)[:28]:<30}{os.path.basename(path)}  {ext} mm@1:50? (roh m→mm)")
    print(f"\n→ {OUT}/  (je Panel+Farbe eine STL; Fassade/Wände/Zier liegen flach, Relief nach oben)")
    print("  TODO nächster Schritt: Steckzapfen/-schlitze an den Panel-Kanten + Dach-Schrägen einzeln flach.")


if __name__ == "__main__":
    main()
