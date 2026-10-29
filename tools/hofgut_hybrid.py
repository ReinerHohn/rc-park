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


def hip_dormer(x, E, w=3.0, depth=2.2, h=1.5):
    """WALM-Gaube (Spec: walmgedeckt, KEINE Spitzgiebel): Körper + allseitig geneigtes Walmdach.
    Front bei y=0, ragt nach -Y. Gibt (körper, dach)."""
    xl, yf = x - w / 2, -depth
    body = box(xl, yf, E, w, depth, h)
    # Walmdach: 4 Schrägen zu einem kurzen First
    zt = E + h; zr = zt + 0.8; ins = w * 0.3
    V = [(xl, yf, zt), (xl + w, yf, zt), (xl + w, 0, zt), (xl, 0, zt),
         (xl + ins, (yf) / 2, zr), (xl + w - ins, (yf) / 2, zr)]
    F = [(0, 1, 5), (0, 5, 4), (2, 3, 4), (2, 4, 5), (0, 4, 3), (1, 2, 5)]
    cap = trimesh.Trimesh(vertices=np.array(V, float), faces=np.array(F), process=True)
    return body, cap


def build_facade(Lf, E, FM):
    """Schaufassade (Spec-getrieben): Naturstein-EG + 1 durchlaufende Laube (Mitte=Fresko-Wand, kein
    Balkon) + Fensterreihen + Walm-Gauben. Lokaler Frame: Front y=0, ragt -Y, X:0..Lf, Z:0..E."""
    S = E * 0.46                                            # hoher Naturstein-Sockel (EG)
    N = 11
    cx0, cx1 = Lf * 0.40, Lf * 0.60                          # Fresko-Mittelzone (ohne Balkon)
    eg_stein, galerie, blumen, fglass, fframe, dach_g = [], [], [], [], [], []
    # EG = Natursteinband (als proude Platte über die Front)
    eg_stein.append(box(0.2, -0.25, 0.0, Lf - 0.4, 0.3, S))
    eg_g, eg_fr = eg_wall_windows(Lf, S * 0.45, S * 0.45 + 1.4, N - 2, door_x=Lf * 0.5)
    fglass.append(eg_g); fframe.append(eg_fr)
    # 1 durchlaufende Laube im 1.OG — in zwei Segmenten links/rechts der Fresko-Mitte
    zf = S
    for x0s, x1s in [(0.6, cx0 - 0.2), (cx1 + 0.2, Lf - 0.6)]:
        L = x1s - x0s
        galerie.append(box(x0s, -1.25, zf - 0.18, L, 1.35, 0.18))     # auskragender Boden
        galerie.append(gaden(x0s, -1.25, zf, L))                      # durchbrochene Baluster
        blumen.append(flower_boxes(x0s, -1.25, zf, L))                # Blumentröge
    # Fensterreihe im Laubengeschoss (hinter der Laube)
    g, fr = window_row(Lf, zf + 0.5, zf + 1.9, N); fglass.append(g); fframe.append(fr)
    # Fresko mittig über der Laube
    fresko = box(cx0, -0.06, zf + 0.4, cx1 - cx0, 0.06, (E - zf) - 0.6)
    # 2-3 WALM-Gauben, walmgedeckt (Spec), brechen die Front-Dachlinie
    for x in np.array([0.30, 0.70]) * Lf:
        b, cp = hip_dormer(x, E, w=3.2, depth=2.0, h=1.5)
        fframe.append(b); dach_g.append(cp)
    parts = {
        "eg_stein": trimesh.util.concatenate(eg_stein),
        "balkone": trimesh.util.concatenate(galerie),
        "blumen": trimesh.util.concatenate(blumen),
        "fenster": trimesh.util.concatenate(fglass),
        "fensterrahmen": trimesh.util.concatenate(fframe),
        "gauben_dach": trimesh.util.concatenate(dach_g),
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

    # 2 Kamine (Spec) auf dem Hauptflügel-First
    R = front["ridge_m"] or 17.46
    kamine = trimesh.util.concatenate([box(front["x0"] + fx * Lf, front["y_front"] + 4, R - 1.2, 1.0, 1.0, 2.6)
                                       for fx in (0.35, 0.68)])

    fr_rgb = FM.get("fensterrahmen", [82, 45, 20])
    COL = {"waende": FM["og_lauben"] + [255], "daecher": FM["dach"] + [255],
           "eg_stein": FM["eg"] + [255], "gauben_dach": FM["dach"] + [255], "kamine": [120, 108, 98, 255],
           "balkone": [int(c * 0.82) for c in FM["og_lauben"]] + [255],
           "blumen": [196, 70, 66, 255], "fenster": [40, 38, 44, 255],
           "fensterrahmen": fr_rgb + [255], "fresko": [168, 150, 120, 255]}
    sc = trimesh.Scene()
    walls.visual.face_colors = COL["waende"]; roofs.visual.face_colors = COL["daecher"]
    kamine.visual.face_colors = COL["kamine"]
    sc.add_geometry(walls, geom_name="waende"); sc.add_geometry(roofs, geom_name="daecher")
    sc.add_geometry(kamine, geom_name="kamine")
    for nm, m in fac.items():
        m.visual.face_colors = COL[nm]; sc.add_geometry(m, geom_name=nm)
    sc.export(f"{md}/hofgut_hybrid.glb")
    ext = sc.bounds[1] - sc.bounds[0]
    print(f"HYBRID: LOD2-Massing + Fassade auf Hauptflügel (B {Lf:.1f} m, Traufe {E} m)")
    print(f"  L×B×H = {ext[0]:.1f}×{ext[1]:.1f}×{ext[2]:.1f} m -> {md}/hofgut_hybrid.glb")


if __name__ == "__main__":
    main()
