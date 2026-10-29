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


def pierced_railing(x0, y, z, length, h=1.0, proj=1.25):
    """Schwarzwald-Laube (Spec wm_hotel1): TIEF auskragender Laubenboden (~1,25 m) + Balustrade an der
    VORDERKANTE (durchbrochene weiße Baluster), dunkelbrauner Handlauf + Fußleiste. Echte Tiefe in der
    GEOMETRIE (nicht nur flaches Band). Gibt (holz_braun, baluster_weiss)."""
    yf = y - proj                                                     # Vorderkante der Laube
    holz = [box(x0, yf, z - 0.18, length, proj, 0.16),                # tief auskragender Boden
            box(x0, yf - 0.02, z + h - 0.16, length, 0.18, 0.18),     # Handlauf an der Vorderkante
            box(x0, yf - 0.02, z, length, 0.16, 0.14),                # Fußleiste vorn
            box(x0, y - 0.1, z - 0.18, length, 0.12, h + 0.1)]        # Rückwand-Anschluss (Tiefe sichtbar)
    slats = []
    for xi in np.arange(x0 + 0.12, x0 + length - 0.06, 0.135):        # Baluster an der Vorderkante
        slats.append(box(xi, yf + 0.01, z + 0.12, 0.045, 0.1, h - 0.28))
    return trimesh.util.concatenate(holz), trimesh.util.concatenate(slats)


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


def build_facade(Lf, E, FM, meas=None):
    """Schaufassade (Spec-getrieben): Naturstein-EG + 1 durchlaufende Laube (Mitte=Fresko-Wand, kein
    Balkon) + Fensterreihen + Walm-Gauben. Lokaler Frame: Front y=0, ragt -Y, X:0..Lf, Z:0..E.
    meas = facade_mass.json (Bauplan): gemessene Galerie-Höhe + Fensterachsen überschreiben die Schätzung."""
    meas = meas or {}
    # Galerie-Höhe aus Bauplan (geklammert gegen Mess-Rauschen), EG-Oberkante knapp darunter
    gal_z = float(np.clip(meas.get("gallery_m", E * 0.5), E * 0.40, E * 0.62))
    S = float(np.clip(meas.get("eg_top_m", gal_z * 0.72), E * 0.30, gal_z - 1.0))   # Naturstein-EG
    N = int(np.clip(meas.get("n_axes", 11), 7, 16))        # Fensterachsen aus Foto gemessen
    cx0, cx1 = Lf * 0.40, Lf * 0.60                          # Fresko-Mittelzone (ohne Balkon)
    eg_stein, galerie, baluster, blumen, fglass, fframe, dach_g = [], [], [], [], [], [], []
    # EG = Natursteinband (als proude Platte über die Front)
    eg_stein.append(box(0.2, -0.25, 0.0, Lf - 0.4, 0.3, S))
    eg_g, eg_fr = eg_wall_windows(Lf, S * 0.45, S * 0.45 + 1.4, N - 2, door_x=Lf * 0.5)
    fglass.append(eg_g); fframe.append(eg_fr)
    # 2 durchlaufende Lauben (hf_front zeigt 2 Balkonebenen), je in Segmenten um die Fresko-Mitte
    gal_levels = [S + 0.2, min(S + 0.2 + 2.6, E - 1.6)]               # untere + obere Galerie
    for li, zf in enumerate(gal_levels):
        segs = [(0.6, cx0 - 0.2), (cx1 + 0.2, Lf - 0.6)] if li == 1 else [(0.6, Lf - 0.6)]  # untere durchgehend
        for x0s, x1s in segs:
            L = x1s - x0s
            holz, slats = pierced_railing(x0s, -0.3, zf, L)
            galerie.append(holz); baluster.append(slats)
            blumen.append(flower_boxes(x0s, -1.5, zf, L))      # Geranien hängen an der Lauben-Vorderkante
        g, fr = window_row(Lf, zf + 0.35, zf + 1.6, N); fglass.append(g); fframe.append(fr)
    # Fresko mittig in der oberen Ebene (zwischen den Galerie-Segmenten)
    fresko = box(cx0, -0.06, gal_levels[1] + 0.2, cx1 - cx0, 0.06, (E - gal_levels[1]) - 0.4)
    # ~4 WALM-Gauben (hf_front: mehrere Gauben im Dach), walmgedeckt
    for x in np.array([0.22, 0.42, 0.60, 0.80]) * Lf:
        b, cp = hip_dormer(x, E, w=2.8, depth=1.8, h=1.4)
        fframe.append(b); dach_g.append(cp)
    parts = {
        "eg_stein": trimesh.util.concatenate(eg_stein),
        "balkone": trimesh.util.concatenate(galerie),
        "baluster": trimesh.util.concatenate(baluster),
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
    meas = json.load(open(f"{md}/facade_mass.json")) if os.path.exists(f"{md}/facade_mass.json") else {}
    if meas:
        print(f"[bauplan] gemessen: {meas.get('n_axes')} Achsen, Galerie {meas.get('gallery_m')} m, "
              f"EG {meas.get('eg_top_m')} m (aus freigestelltem Foto + LOD2-Massstab)")
    fac = build_facade(Lf, E, FM, meas)
    for m in fac.values():                                   # Fassade an die Hauptflügel-Front schieben
        m.apply_translation((front["x0"], front["y_front"], 0.0))

    # Kamine aus dem DOP-Luftbild (20 cm, schärfer als Laser) statt geraten
    R = front["ridge_m"] or 17.46
    kam_fr = [0.35, 0.68]
    if os.path.exists(f"{md}/dach_aufbauten.json"):
        kf = json.load(open(f"{md}/dach_aufbauten.json")).get("kamine_x_frac")
        if kf:
            kam_fr = kf; print(f"[dop] Kamine x-Anteil aus Luftbild: {kf}")
    kamine = trimesh.util.concatenate([box(front["x0"] + fx * Lf, front["y_front"] + 4, R - 1.2, 1.0, 1.0, 2.6)
                                       for fx in kam_fr])

    orn = FM.get("lueftlmalerei", [210, 205, 192])           # cremeweiße Lüftlmalerei/Baluster (Spec!)
    if isinstance(orn, dict):
        orn = orn.get("ornament_rgb", [210, 205, 192])
    COL = {"waende": FM["og_lauben"] + [255], "daecher": FM["dach"] + [255],
           "eg_stein": FM["eg"] + [255], "gauben_dach": FM["dach"] + [255], "kamine": [120, 108, 98, 255],
           "balkone": [int(c * 0.78) for c in FM["og_lauben"]] + [255],   # dunkelbraunes Holz (Boden/Handlauf/Fußleiste)
           "baluster": orn + [255],                           # WEISS gestrichene durchbrochene Baluster (Kontrast!)
           "blumen": [196, 70, 66, 255], "fenster": [38, 36, 42, 255],
           "fensterrahmen": [205, 178, 120, 255],             # helle ocker Fensterfaschen (Schauseite, Spec)
           "fresko": [172, 150, 118, 255]}
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
