#!/usr/bin/env python3
"""hofgut_hybrid.py — der gewählte Weg: LOD2-Grundriss-MASSING (8 Teile) + parametrische DETAIL-
FASSADE (Lauben/Fenster/Fresko) auf dem HAUPTFLÜGEL + gemessene Farben. (DOP-Dachtextur = Schritt B.)
Nutzt ALLE relevanten Quellen: LOD2 (Massing/Front), nDOM (Firsthöhe-Quercheck), Foto (Farben).

Lauf: /tmp/rv/bin/python tools/hofgut_hybrid.py  → modelle/hofgut_sternen/hofgut_hybrid.glb
"""
import json, os
import numpy as np
import trimesh
import hofgut_massing as HM
from hofgut_sternen import box, gaden, window_row, flower_boxes, eg_wall_windows, zwerchhaus


def build_facade(Lf, E, FM, S=3.0):
    """Detailfassade im LOKALEN Frame: Front bei y=0, projiziert nach -Y, X:0..Lf, Z:0..E.
    Gibt dict{name:mesh}. Geschosse: EG 0..S, 2 OG S..E (Lauben)."""
    Fl = (E - S) / 2.0
    N = 11
    balkone, blumen, fglass, fframe = [], [], [], []
    for zf in (S, S + Fl):
        balkone.append(box(0.6, -1.3, zf - 0.18, Lf - 1.2, 1.4, 0.18))
        balkone.append(gaden(0.6, -1.3, zf, Lf - 1.2))
        blumen.append(flower_boxes(0.6, -1.3, zf, Lf - 1.2))
    eg_g, eg_fr = eg_wall_windows(Lf, S * 0.55, S * 0.55 + 1.5, N - 2, door_x=Lf * 0.5)
    fglass.append(eg_g); fframe.append(eg_fr)
    for z0, z1 in [(S + 0.5, S + 1.9), (S + Fl + 0.5, S + Fl + 1.9)]:
        g, fr = window_row(Lf, z0, z1, N); fglass.append(g); fframe.append(fr)
    for x in np.array([0.24, 0.55, 0.82]) * Lf:              # Zwerchhäuser brechen die Front-Dachlinie
        b, w_ = zwerchhaus(x, E, E + 8, 13, 5, w=4.0, body_h=1.7, gh=1.3)
        balkone.append(b) if False else None
        fglass.append(w_); fframe.append(b)                  # Giebelkörper als Rahmen-Gruppe (Holzfarbe)
    fresko = box(Lf * 0.5 - 2.6, -0.06, S + Fl + 0.3, 5.2, 0.06, Fl - 0.7)
    parts = {
        "balkone": trimesh.util.concatenate(balkone),
        "blumen": trimesh.util.concatenate(blumen),
        "fenster": trimesh.util.concatenate(fglass),
        "fensterrahmen": trimesh.util.concatenate(fframe),
        "fresko": fresko,
    }
    return parts


def main():
    md = "modelle/hofgut_sternen"
    walls, roofs, front = HM.build()                         # LOD2-Massing + Hauptflügel-Front
    FM = {"dach": [173, 155, 136], "og_lauben": [105, 85, 62], "eg": [197, 176, 148]}
    if os.path.exists(f"{md}/farben.json"):
        FM.update(json.load(open(f"{md}/farben.json")))

    Lf = front["x1"] - front["x0"]; E = front["eave_m"] or 9.37
    fac = build_facade(Lf, E, FM)
    for m in fac.values():                                   # Fassade an die Hauptflügel-Front schieben
        m.apply_translation((front["x0"], front["y_front"], 0.0))

    COL = {"waende": FM["og_lauben"] + [255], "daecher": FM["dach"] + [255],
           "balkone": [int(c * 0.8) for c in FM["og_lauben"]] + [255],
           "blumen": [196, 60, 66, 255], "fenster": [44, 42, 48, 255],
           "fensterrahmen": FM["og_lauben"] + [255], "fresko": [182, 150, 112, 255]}
    sc = trimesh.Scene()
    walls.visual.face_colors = COL["waende"]; roofs.visual.face_colors = COL["daecher"]
    sc.add_geometry(walls, geom_name="waende"); sc.add_geometry(roofs, geom_name="daecher")
    for nm, m in fac.items():
        m.visual.face_colors = COL[nm]; sc.add_geometry(m, geom_name=nm)
    sc.export(f"{md}/hofgut_hybrid.glb")
    ext = sc.bounds[1] - sc.bounds[0]
    print(f"HYBRID: LOD2-Massing + Fassade auf Hauptflügel (B {Lf:.1f} m, Traufe {E} m)")
    print(f"  L×B×H = {ext[0]:.1f}×{ext[1]:.1f}×{ext[2]:.1f} m -> {md}/hofgut_hybrid.glb")


if __name__ == "__main__":
    main()
