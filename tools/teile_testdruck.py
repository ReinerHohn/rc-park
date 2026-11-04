#!/usr/bin/env python3
"""teile_testdruck.py - Generator-STL in DRUCKBARE, STECKBARE Einzelteile zerlegen (Bambu u.a.). Boolesche Schnitte mit manifold3d (wasserdicht), Zapfen/Bohrung mit Spiel.
Teile (Schnitte in Modellmetern, +x Sued, aus Schnittbildern des STL v4 - ANNAHME, nicht aus masse.json):
  basis        Zinnenkranz-Stumpf z 32..39 m, UMGEDREHT gedruckt (breiter Kranz auf dem Bett, kein Ueberhang); Bohrungen: 4 Tuermchen, Dach, 2 Front-Zapfen
  ecke         NO-Ecke z>=33 m: Eckblock + Arkade (Boegen) + Tuermchen als EIN Teil, ohne Bohrung, steht auf ebener Schnittflaeche
  tuermchen    NO-Eck-Tuermchen z>=39 (4x drucken), Bohrung unten (ebene Auflageflaeche!)
  dach         Helm z 39..55 m, Bohrung unten; oben Stossfuge zur Nadel (kleben)
  nadel        z>=55 m, flach geschnitten (kleben)
  stift        loser Passstift (je Verbindung 1; 3-mm-Filament/Draht geht auch). NIE Zapfen unter eine breitere Flaeche setzen (Luftdruck, Fehler 2026-11-03)
  front_sued   Suedplatte x>=3 m, z 0..32, LIEGEND (Rueckseite auf dem Bett), 2 Bohrungen oben (Stifte)
Zapfen d=ZAPFEN_MM, Spiel SPIEL_MM je Seite. Nadel-Duenne: bei kleinen Massstaeben < 0,4 mm Linie -> Warnung.
  /media/oem/scan/venv-seg/bin/python -I tools/teile_testdruck.py [--stl ...] [--massstab 160] [--aus modelle/export/testdruck]
"""
import argparse, os, numpy as np, trimesh
ZAPFEN_MM = 3.0; LAENGE_MM = 3.5; SPIEL_MM = 0.15
Z_BASIS_U, Z_PLATTE, Z_DACH_O = 32.0, 39.0, 55.0
TUERM_XY = (3.9, 4.4)            # Mitte NO-Tuermchen (Schnitt z=40: x 3,1..4,9 / y 3,5..5,3)
FRONT_ZAPFEN = [(3.85, -2.5), (3.85, 2.5)]

def box(lo, hi):
    lo = np.array([-1e4 if v is None else v for v in lo], float); hi = np.array([1e4 if v is None else v for v in hi], float)
    b = trimesh.creation.box(hi - lo); b.apply_translation((hi + lo) / 2); return b

def zyl(x, y, z0, r, h):
    c = trimesh.creation.cylinder(radius=r, height=h, sections=48); c.apply_translation([x, y, z0 + h / 2]); return c

def bool_(op, a, b):
    return trimesh.boolean.boolean_manifold([a, b], op)

def scheiben(a, m0):
    """Waagerechte Scheiben mit ebener Unter- und Oberseite (nichts haengt in der Luft), Passbohrungen beidseitig wo die Wand es erlaubt."""
    from shapely.geometry import Point
    k = 1000 / 87; f = 87 / a.massstab; r_z = ZAPFEN_MM / 2 / f; h_z = LAENGE_MM / f; sp = SPIEL_MM / f; os.makedirs(a.aus, exist_ok=True)
    kand = [(0, 0), (2, 0), (-2, 0), (0, 2), (0, -2), (3, 3), (-3, 3), (3, -3), (-3, -3), (2.5, 2.5), (-2.5, -2.5), (2.5, -2.5), (-2.5, 2.5)]
    def frei(z):
        s_ = m0.section(plane_origin=[0, 0, z * k], plane_normal=[0, 0, 1])
        if s_ is None: return []
        from shapely.ops import unary_union
        pg = unary_union(s_.to_2D()[0].polygons_full)
        return [(x, y) for x, y in kand if pg.buffer(0).buffer(-(r_z + sp + 1.2) / k * 1.0 * 0 - (r_z + sp + 1.2)).buffer(0).contains(Point(x * k - (s_.to_2D()[1][0, 3]), y * k - s_.to_2D()[1][1, 3]))]
    namen = []
    for i, bereich in enumerate(a.scheiben.split(";")):
        z0, z1 = (float(v) for v in bereich.split(","))
        t = bool_("intersection", m0, box([None, None, z0 * k], [None, None, z1 * k]))
        for z in (z0 + 0.3, z1 - 0.3):
            pass
        loecher = []
        ok = set(frei(z0 + 0.05)) & set(frei(z1 - 0.05))
        for x, y in list(ok)[:2]: loecher.append((x, y))
        for x, y in loecher:
            t = bool_("difference", t, zyl(x * k, y * k, z0 * k - 1, r_z + sp, h_z + 1)); t = bool_("difference", t, zyl(x * k, y * k, z1 * k - h_z, r_z + sp, h_z + 1))
        kp = t.split(only_watertight=False); gross = max(b.volume for b in kp); t = trimesh.util.concatenate([b for b in kp if b.volume >= 0.05 * gross])
        t.apply_scale(f); t.apply_translation(-np.array([t.bounds[:, 0].mean(), t.bounds[:, 1].mean(), t.bounds[0, 2]]))
        nm = f"scheibe_{i + 1}_z{z0:g}-{z1:g}_1-{int(a.massstab)}.stl"; t.export(os.path.join(a.aus, nm)); namen.append(nm)
        print(f"{nm:40s} mm {t.extents.round(1).tolist()} wasserdicht {t.is_watertight} Bohrungen {len(loecher)} Volumen cm3 {t.volume / 1000:.0f}")
    st = trimesh.creation.cylinder(radius=r_z, height=2 * h_z - 0.2 / f, sections=48); st.apply_scale(f); st.apply_translation([0, 0, st.extents[2] / 2]); st.export(os.path.join(a.aus, f"stift_1-{int(a.massstab)}.stl"))

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--stl", default="modelle/stl/martinstor_v4_1-87.stl"); ap.add_argument("--massstab", type=float, default=160)
    ap.add_argument("--zapfen", type=float, default=None, help="Stift/Bohrung d in Ziel-mm (Standard 3 bei 1:160, sonst 5)"); ap.add_argument("--scheiben", default=None, help="Steckbausatz OHNE Ueberhang: z-Bereiche in m, z. B. \"9,18;18,27;44.5,55;55,66\" - je Scheibe plan, Bohrungen beidseitig (wo der Querschnitt es zulaesst), dazu ein Stift"); ap.add_argument("--aus", default="modelle/export/testdruck"); a = ap.parse_args(); os.makedirs(a.aus, exist_ok=True)
    global ZAPFEN_MM, LAENGE_MM
    ZAPFEN_MM = a.zapfen or (3.0 if a.massstab >= 130 else 5.0); LAENGE_MM = 3.5 if a.massstab >= 130 else 6.0
    m0 = trimesh.load(a.stl)
    if a.scheiben: return scheiben(a, m0)
    k = 1000 / 87; f = 87 / a.massstab; mm = 1 / (k * f)      # mm im Ziel -> Modell-STL-mm (1:87) -> Meter
    # Alles im STL-Raum (1:87-mm) rechnen: Meter*k. Zapfenmasse sind Ziel-mm -> in 1:87-mm umrechnen (/f)
    r_z = ZAPFEN_MM / 2 / f; h_z = LAENGE_MM / f; sp = SPIEL_MM / f
    S = lambda *v: [None if x is None else x * k for x in v]
    def teil(lo, hi): return bool_("intersection", m0, box(S(*lo), S(*hi)))
    out = {}
    # Basis
    t = teil((None, None, Z_BASIS_U), (None, None, Z_PLATTE))
    for sx in (1, -1):
        for sy in (1, -1): t = bool_("difference", t, zyl(sx * TUERM_XY[0] * k, sy * TUERM_XY[1] * k, Z_PLATTE * k - h_z - 0.3, r_z + sp, h_z + 0.3 + 1))
    t = bool_("difference", t, zyl(0, 0, Z_PLATTE * k - h_z - 0.3, r_z + sp, h_z + 1.3))
    for x, y in FRONT_ZAPFEN: t = bool_("difference", t, zyl(x * k, y * k, Z_BASIS_U * k - 1, r_z + sp, h_z + 1))
    t.apply_transform(trimesh.transformations.rotation_matrix(np.pi, [1, 0, 0])); out["basis"] = t
    # Ecke NO: Tuermchen MIT Bogenfries (Arkade z 34..35 m) und Eckblock ab z=33 (ebene Schnittflaeche = Standflaeche), ohne den Rest des Blocks
    out["ecke"] = teil((2.9, 3.3, 33.0), (None, None, None))
    # Tuermchen NO
    t = teil((2.9, 3.3, Z_PLATTE), (None, None, None)); t = bool_("difference", t, zyl(TUERM_XY[0] * k, TUERM_XY[1] * k, Z_PLATTE * k - 1, r_z + sp, h_z + 1)); out["tuermchen"] = t
    # Dach (Schaft 3,6 x 3,5 m um die Mitte) + Zapfen unten + Bohrung oben
    t = teil((-3.6, -3.5, Z_PLATTE), (3.6, 3.5, Z_DACH_O)); t = bool_("difference", t, zyl(0, 0, Z_PLATTE * k - 1, r_z + sp, h_z + 1))
    t = bool_("difference", t, zyl(0, 0, Z_DACH_O * k - h_z, r_z + sp, h_z + 1)); out["dach"] = t
    # Nadel
    t = teil((-3.6, -3.5, Z_DACH_O), (3.6, 3.5, None)); out["nadel"] = t       # Nadel an der Stossfuge kleben (Querschnitt bei 1:160 nur ~1,5 mm: keine Bohrung moeglich)
    # Front
    t = teil((3.0, None, 0.0), (None, None, Z_BASIS_U))
    for x, y in FRONT_ZAPFEN: t = bool_("difference", t, zyl(x * k, y * k, Z_BASIS_U * k - h_z - 0.3, r_z + sp, h_z + 1.3))
    t.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [0, 1, 0])); out["front_sued"] = t
    out["stift"] = trimesh.creation.cylinder(radius=r_z - 0.0, height=2 * h_z - 0.2 / f, sections=48); out["stift"].apply_translation([0, 0, out["stift"].extents[2] / 2])
    for name, t in out.items():
        kp = t.split(only_watertight=False)          # schwebende Kleinstteile (Generator-Einzelkoerper < 5 % des groessten) verwerfen
        gross = max(b.volume for b in kp); t = trimesh.util.concatenate([b for b in kp if b.volume >= 0.05 * gross]); out[name] = t
        t.apply_scale(f); t.apply_translation(-np.array([t.bounds[:, 0].mean(), t.bounds[:, 1].mean(), t.bounds[0, 2]]))
        p = os.path.join(a.aus, f"{name}_1-{int(a.massstab)}.stl"); t.export(p)
        print(f"{name:11s} mm {t.extents.round(1).tolist()} wasserdicht {t.is_watertight} Koerper {len(t.split(only_watertight=False))} -> {p}")

if __name__ == "__main__":
    main()
