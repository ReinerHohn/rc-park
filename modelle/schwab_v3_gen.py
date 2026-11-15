#!/usr/bin/env python3
"""schwab_v3_gen.py - Generator-Rumpf (manifold3d). Jedes sichtbare Element meldet sich mit beleg(); Bau + Abnahme: tools/bauen_abnehmen.sh schwab_v3"""
import os, sys, json, numpy as np
from manifold3d import Manifold as M
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
from dach_bauen import gebaeude_aus_lod2, seiten_aus_rahmen
SCALE = float(os.environ.get("SCALE", "87")); K = 1000.0 / SCALE
OUT = os.path.join(HERE, "stl", "schwab_v3_1-{SCALE:.0f}.stl".format(SCALE=SCALE))
ELEMENTE = []
def beleg(seite, element, quelle, **masse): ELEMENTE.append(dict(seite=seite, element=element, quelle=quelle, **masse))
OBJ = os.path.join(HERE, "schwab_v3", "objekt.json"); obj = json.load(open(OBJ))
SEITEN = seiten_aus_rahmen(obj)
if obj.get("lod2", {}).get("id"):                    # Standard: LoD2-Grundriss + DOM1-Dach (dach.json, Nullstart-Schritt 'dach') - tools/dach_bauen.py
    # 15.11.2026: Dach NICHT mehr aus dem Laser-Fit (kein Ueberstand, Traufe 2,5 m zu tief), sondern aus der Foto-Triangulation der Nordseite
    # (masstabelle.json, Protokolle M-113205-002..-007). LoD2 liefert nur noch den Grundriss und die Nebenteile.
    from manifold3d import CrossSection
    koerper, belege, haupt = gebaeude_aus_lod2(OBJ, dach_json=os.path.join(HERE, "schwab_v3", "KEIN_LASERDACH"))
    for b_ in belege:
        if b_["element"] == "Teil 0 (ohne Dachmessung)": continue           # Hauptteil bekommt das Fotodach unten
        beleg(**b_)
    ZT = 39.18                                # Traufe aussen oben: Ecken A 39,15 / C 39,20 (M-113205-002/-003)
    X1, Y0, Y1 = 4.88, 8.16, 22.51            # Traufkante Nord (x) und Ecken Ost/West (y), gleiche Protokolle
    MX = -2.15                                # Dachmitte x = Mitte zwischen Nordwand 3,69 (M-113205-006/-007) und Suedwand LoD2 -8,0
    X0 = 2 * MX - X1                          # ANNAHME: Suedtraufe spiegelbildlich (Turmkopf im SfM nur von Norden gesehen)
    NEIG = 55.1                               # Neigung Nordflaeche: Traufe -> Laternenfuss (-0,77 / 47,28), M-113205-004; Laser DOM1 56,1
    ZF = 47.28                                # Laternenfuss = Oberkante Pyramidenstumpf
    DICKE = 0.25                              # ANNAHME: Traufbrett/Sparrenkopf 0,25 m
    cx, cy = (X0 + X1) / 2, (Y0 + Y1) / 2; hx, hy = (X1 - X0) / 2, (Y1 - Y0) / 2
    zs = ZT + hx * np.tan(np.radians(NEIG)); f = (zs - ZF) / (zs - ZT)       # gedachte Spitze (~49,25 m; Laser max 49,62)
    ecken = lambda h_x, h_y, z: [[cx + a * h_x, cy + b * h_y, z] for a in (-1, 1) for b in (-1, 1)]
    dach = M.hull_points(ecken(hx, hy, ZT - DICKE) + ecken(hx, hy, ZT) + ecken(hx * f, hy * f, ZF))
    wand = M.extrude(CrossSection([np.asarray(haupt).tolist()]), ZT)        # ANNAHME: Wand laeuft bis unter die Dachhaut (Untersicht/Holzwerk nicht gemessen)
    beleg("dach", "Zeltdach mit Ueberstand", "Foto-Triangulation Nordseite (foto_mass.py --tri, M-113205-002/-003/-004)", traufe=ZT, neigung_grad=NEIG,
          trauflaenge_ost_west=round(Y1 - Y0, 2), ueberstand=round(X1 - 3.69, 2), spitze_gedacht=round(float(zs), 2),
          hinweis="ANNAHME: Sued-, Ost- und Westflaeche wie Nord (gleiche Spitzenhoehe), Traufdicke 0,25 m")
    beleg("wand", "Hauptteil Wand bis Traufe", "LoD2 DEBW_001000hPLcp GroundSurface 0; Nordwand am Foto bestaetigt (M-113205-006/-007)", hoehe=ZT,
          hinweis="ANNAHME: Wand bis Traufhoehe, Dachuntersicht nicht gemessen")
    # Laterne: nur der Knauf ist gemessen (-1,50 / 15,02 / 54,17, M-113205-005; x entlang der Blickrichtung unsicher) - Form = ANNAHME nach Foto 113205
    lat = M.cylinder(51.3 - (ZF - 0.3), 0.75, 0.75, 8).translate((cx, cy, ZF - 0.3))
    lat = lat + M.cylinder(0.35, 1.05, 0.80, 8).translate((cx, cy, 51.2))                                   # Krempe
    lat = lat + M.sphere(1.0, 24).scale((0.9, 0.9, 1.2)).translate((cx, cy, 52.5))                          # Zwiebelhaube
    lat = lat + M.cylinder(0.6, 0.14, 0.10, 12).translate((cx, cy, 53.5)) + M.sphere(0.22, 16).translate((cx, cy, 54.17))
    lat = lat + M.cylinder(1.0, 0.06, 0.05, 8).translate((cx, cy, 54.3))                                    # Spitze
    beleg("dach", "Laterne mit Zwiebelhaube", "Knauf-Hoehe 54,17 m aus Foto-Triangulation (M-113205-005)", hoehe=55.3,
          hinweis="ANNAHME: Form (geschlossener Achteckschaft statt 4 Pfosten, Krempe, Zwiebel, Spitze 1 m) nach Augenschein Foto 113205, nicht gemessen")
    koerper = koerper + wand + dach + lat
    cu, cv = haupt.mean(0); model = koerper.scale((K, K, K))   # 15.11.2026: NICHT zentrieren - STL bleibt im Rahmen (objekt.json rahmen); die Fotowerkzeuge (zentrierung 'achse') erwarten STL = Rahmen, sonst liegt das Modell um (cu, cv) neben Kameras/Wolke
else:
    H = 10.0                               # Gesamthoehe (m) - Quelle in masstabelle.json
    beleg("dach", "Grundkoerper", "ANNAHME: Rumpf ohne LoD2 (objekt.json lod2.id fehlt)", hoehe=H)
    model = M.cube((8.0, 8.0, H)).translate((-4.0, -4.0, 0.0)).scale((K, K, K))
mesh = model.to_mesh(); V = np.asarray(mesh.vert_properties)[:, :3]; F = np.asarray(mesh.tri_verts)
os.makedirs(os.path.dirname(OUT), exist_ok=True)
tri = V[F]; nrm = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]); nrm /= np.linalg.norm(nrm, axis=1, keepdims=True) + 1e-12
rec = np.zeros(len(F), dtype=[("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")]); rec["n"], rec["v"] = nrm, tri
with open(OUT, "wb") as f: f.write(b"schwab_v3".ljust(80, b" ")); f.write(np.uint32(len(F)).tobytes()); f.write(rec.tobytes())
json.dump([dict(e, seite_name=SEITEN.get(e["seite"], e["seite"])) for e in ELEMENTE], open(os.path.join(HERE, "schwab_v3", "elemente.json"), "w"), indent=1, ensure_ascii=False)
print("->", OUT)
