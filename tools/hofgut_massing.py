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

    # Fassade soll nach -Y zeigen: Hauptflügel-Front = Kante mit kleinstem y → ok nach shift
    wall_meshes, roof_meshes = [], []
    for i, (t, r) in enumerate(zip(teile, rings_r)):
        E = t["eave_m"] or 9.0; R = t["ridge_m"] or (E + 5)
        poly = Polygon(r).buffer(0)
        if poly.is_empty or poly.area < 2:
            continue
        w = trimesh.creation.extrude_polygon(poly, E)             # Wände 0..Traufe
        wall_meshes.append(w)
        x0, y0, x1, y1 = poly.bounds
        # Schwarzwald: Dach tief heruntergezogen, ABER Überstand GRÖSSENABHÄNGIG (sonst stechen kleine
        # Teile dreieklig heraus = „Vorgebäude"-Artefakt). Niedrige Anbauten (kleiner R) flacher.
        side = min(x1 - x0, y1 - y0)
        overh = float(np.clip(0.12 * side, 0.3, 1.1))
        E_roof = max(E * 0.45, E - 3.5) if R > 7 else E * 0.8   # nur Hauptbauten tief ziehen
        roof_meshes.append(hip_over_bbox(x0, x1, y0, y1, E_roof, R, overh=overh))

    walls = trimesh.util.concatenate(wall_meshes)
    roofs = trimesh.util.concatenate(roof_meshes)
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
