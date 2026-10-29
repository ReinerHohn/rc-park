#!/usr/bin/env python3
"""hofgut_massing.py — MASSING aus dem ECHTEN LOD2-Grundriss (nichts geraten): liest
modelle/hofgut_sternen/footprint.json (8 Teile, je Ring + Traufe + First), extrudiert JEDEN Teil
zu seiner Traufe und setzt ein Krüppelwalm-/Walmdach bis zum First. Richtet den Hauptflügel
(größter Teil) mit der Längsachse nach X, Fassade nach -Y aus (konsistent mit den Renders).

Gibt modelle/hofgut_sternen/hofgut_massing.glb + gibt die Transform + Hauptflügel-Frontkante zurück
(für die Fassaden-Detaillierung im nächsten Schritt).
"""
import json, os
import numpy as np
import trimesh
from shapely.geometry import Polygon
from shapely.ops import unary_union


def pca_angle(pts):
    """Hauptachsen-Winkel (rad) der Punktwolke → zum Ausrichten der Längsachse auf X."""
    c = pts.mean(0); u, s, vt = np.linalg.svd(pts - c)
    return np.arctan2(vt[0, 1], vt[0, 0])


def rot2(a):
    return np.array([[np.cos(a), -np.sin(a)], [np.sin(a), np.cos(a)]])


def hip_over_bbox(x0, x1, y0, y1, E, R, inset_frac=0.28, overh=1.5, t=0.4):
    """Krüppelwalm über einem achsenparallelen Rechteck (Teil-Bbox), First entlang der langen Seite."""
    o = overh
    long_x = (x1 - x0) >= (y1 - y0)
    if long_x:
        ins = inset_frac * (x1 - x0); ridge = [((x0 + ins), (y0 + y1) / 2, R), ((x1 - ins), (y0 + y1) / 2, R)]
    else:
        ins = inset_frac * (y1 - y0); ridge = [((x0 + x1) / 2, (y0 + ins), R), ((x0 + x1) / 2, (y1 - ins), R)]
    A = (x0 - o, y0 - o, E); B = (x1 + o, y0 - o, E); C = (x1 + o, y1 + o, E); Dd = (x0 - o, y1 + o, E)
    top = [A, B, C, Dd, ridge[0], ridge[1]]
    if long_x:
        Ft = [(0, 1, 5), (0, 5, 4), (2, 3, 4), (2, 4, 5), (0, 4, 3), (1, 2, 5)]
    else:
        Ft = [(1, 2, 4), (1, 4, 5), (3, 0, 5), (3, 5, 4), (0, 1, 5), (2, 3, 4)]
    bot = [(p[0], p[1], p[2] - t) for p in top]
    V = top + bot; F = list(Ft) + [(a + 6, c + 6, b + 6) for (a, b, c) in Ft]
    for i, j in [(0, 1), (1, 2), (2, 3), (3, 0)]:
        F += [(i, j, j + 6), (i, j + 6, i + 6)]
    return trimesh.Trimesh(vertices=np.array(V, float), faces=np.array(F), process=True)


def cross_gable(cx, y_front, y_back, E_roof, R, w):
    """ZENTRALES QUERSCHIFF / Zwerchgiebel (DOP: Kreuz-First, springt mittig zur Talseite vor).
    Gegiebelter Flügel: First in Y bei x=cx, Giebel-Front bei y_front, Rückkante im Hauptdach."""
    xl, xr = cx - w / 2, cx + w / 2
    V = [(xl, y_front, E_roof), (xr, y_front, E_roof), (cx, y_front, R),      # Front-Giebel 0-2
         (xl, y_back, E_roof), (xr, y_back, E_roof), (cx, y_back, R)]         # Rück 3-5
    F = [(0, 1, 2),                     # Front-Giebeldreieck
         (3, 5, 4),                     # Rück
         (0, 2, 5), (0, 5, 3),          # linke Dachschräge
         (1, 4, 5), (1, 5, 2),          # rechte Dachschräge
         (0, 3, 4), (0, 4, 1)]          # Boden
    return trimesh.Trimesh(vertices=np.array(V, float), faces=np.array(F), process=True)


def build(footprint="modelle/hofgut_sternen/footprint.json",
          out="modelle/hofgut_sternen/hofgut_massing.glb",
          colors="modelle/hofgut_sternen/farben.json"):
    fp = json.load(open(footprint))
    teile = fp["teile"]
    FM = {"dach": [173, 155, 136], "og_lauben": [105, 85, 62], "eg": [197, 176, 148]}
    if os.path.exists(colors):
        FM.update(json.load(open(colors)))

    rings = [np.array(t["ring_xy_m"]) for t in teile]
    areas = [Polygon(r).area for r in rings]
    main = int(np.argmax(areas))                                  # Hauptflügel = größter Teil
    # Ausrichtung: Hauptflügel-Längsachse → X; Drehung um dessen Schwerpunkt
    ang = pca_angle(rings[main]); Rm = rot2(-ang)
    ctr = rings[main].mean(0)
    rings_r = [((r - ctr) @ Rm.T) for r in rings]
    # FASSADE = unverdeckte Längsseite des Hauptflügels. Welche der beiden langen Seiten (−y/+y)
    # hat WENIGER andere Bauteile davor? Diese zeigt zur offenen Talseite = echte Schaufassade.
    my = Polygon(rings_r[main]).centroid.y
    front_occ = sum(Polygon(rings_r[i]).area for i in range(len(rings_r))
                    if i != main and Polygon(rings_r[i]).centroid.y < my)
    back_occ = sum(Polygon(rings_r[i]).area for i in range(len(rings_r))
                   if i != main and Polygon(rings_r[i]).centroid.y >= my)
    flip = front_occ > back_occ
    if flip:                                                      # −y-Seite verdeckt → Fassade ist +y → 180° drehen
        rings_r = [r * np.array([1.0, -1.0]) for r in rings_r]
    allp = np.vstack(rings_r); shift = allp.min(0)
    rings_r = [r - shift for r in rings_r]                        # alles in +Quadranten

    # Fassade soll nach -Y zeigen: Hauptflügel-Front = Kante mit kleinstem y → ok nach shift.
    # DOP/Luftbild zeigt EIN zusammenhängendes Dach → Hauptkörper VERSCHMELZEN, EIN Dach drüber
    # (statt getrennter Teildächer = falsches „zweites Gebäude"). Mini-Anbauten raus.
    polys = [(i, Polygon(r).buffer(0)) for i, r in enumerate(rings_r)]
    polys = [(i, p) for i, p in polys if not p.is_empty and p.area > 40]   # nur Hauptkörper
    merged = unary_union([p.buffer(0.6) for _, p in polys]).buffer(-0.6)   # berührende Teile verschmelzen
    if merged.geom_type == "MultiPolygon":
        merged = max(merged.geoms, key=lambda g: g.area)
    E = teile[main]["eave_m"] or 9.0; R = teile[main]["ridge_m"] or (E + 8)
    wall_meshes = [trimesh.creation.extrude_polygon(merged.simplify(0.3), E)]   # EIN Wandkörper
    x0, y0, x1, y1 = merged.bounds
    # DACH-FORM aus dem LASER (nDOM) — beste Datenquelle: First-Höhe, Dach-Unterkante, First-Länge/Inset
    rp = os.path.join(os.path.dirname(out), "roof_params.json")
    if os.path.exists(rp):
        pr = json.load(open(rp))
        R = pr.get("ridge_m", R); E_roof = pr.get("roof_eave_m", E * 0.6); inset = pr.get("inset_frac", 0.2)
        print(f"  [Dach aus Laser-nDOM: First {R} m, Dach-Unterkante {E_roof} m, inset {inset} (langer First={1-2*inset:.0%})]")
    else:
        E_roof = max(E * float(os.environ.get("ROOF_SWEEP", "0.45")), E - 3.5)
        inset = float(os.environ.get("ROOF_INSET", "0.28"))
    overh = float(np.clip(0.12 * min(x1 - x0, y1 - y0), 0.4, 1.0))
    # DACH zentral aus dem LUFTBILD (dach_aus_luftbild.py: Firststruktur inkl. Querschiff aus DOP).
    # Fallback: OBB-Hüftdach aus Laser-Parametern, wenn das Luftbild-Dach (noch) nicht erzeugt wurde.
    lb = os.path.join(os.path.dirname(out), "dach_luftbild.obj")
    if os.path.exists(lb):
        roof_meshes = [trimesh.load(lb)]
        print(f"  [Dach aus LUFTBILD: {lb} (Firststruktur inkl. Querschiff aus DOP)]")
    else:
        roof_meshes = [hip_over_bbox(x0, x1, y0, y1, E_roof, R, overh=overh, inset_frac=inset)]
        cx = (x0 + x1) / 2.0
        roof_meshes.append(cross_gable(cx, y0 - overh - 1.2, (y0 + y1) / 2.0, E_roof, R, (x1 - x0) * 0.24))

    walls = trimesh.util.concatenate(wall_meshes)
    try:                                                          # Teildächer SAUBER verschmelzen (statt Überschneidungs-Hütchen)
        roofs = trimesh.boolean.union(roof_meshes)
        if roofs.is_empty or len(roofs.faces) < 10:
            raise ValueError("leer")
    except Exception as e:
        print(f"  [roof-union Fallback: {e}]"); roofs = trimesh.util.concatenate(roof_meshes)
    walls.visual.face_colors = FM["og_lauben"] + [255]
    roofs.visual.face_colors = FM["dach"] + [255]
    sc = trimesh.Scene()
    sc.add_geometry(walls, geom_name="waende"); sc.add_geometry(roofs, geom_name="daecher")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    sc.export(out)
    ext = sc.bounds[1] - sc.bounds[0]
    # Hauptflügel-Frontkante (für Fassadendetail): lange Kante mit kleinstem y
    mr = rings_r[main]; x0, y0, x1, y1 = Polygon(mr).bounds
    front = {"main_idx": main, "x0": float(x0), "x1": float(x1), "y_front": float(y0),
             "eave_m": teile[main]["eave_m"], "ridge_m": teile[main]["ridge_m"]}
    # vollständiger Transform (local-from-origin → Modell-Frame): p' = ((p-ctr)@Rm.T){,y*=-1} - shift
    json.dump({"rot_angle": float(ang), "ctr": [float(v) for v in ctr], "flip": bool(flip),
               "shift": [float(v) for v in shift], "front": front},
              open("modelle/hofgut_sternen/massing_frame.json", "w"), indent=1)
    print(f"Massing aus LOD2-Grundriss: {len(wall_meshes)} Teile, L×B×H = {ext[0]:.1f}×{ext[1]:.1f}×{ext[2]:.1f} m")
    print(f"  Hauptflügel Teil{main}: Front x {x0:.1f}..{x1:.1f} (B {x1-x0:.1f} m), Traufe {front['eave_m']}, First {front['ridge_m']}")
    print(f"-> {out} (+ massing_frame.json)")
    return walls, roofs, front


if __name__ == "__main__":
    build()
