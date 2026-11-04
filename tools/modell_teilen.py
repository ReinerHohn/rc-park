#!/usr/bin/env python3
"""modell_teilen.py - AUTOMATISCH ein zu hohes Modell in druckbare Segmente teilen (Steckzapfen + Bohrung) und die Nadel durch eine Stabbohrung ersetzen (Plan: Druckvorbereitung).

Schritte (alles generisch, Werte als Argument, Voreinstellungen = ANNAHME):
  1. Zahl der Segmente N = ceil(Hoehe_Koerper / --max-hoehe); Zieltrennhoehen gleichmaessig.
  2. Je Trennstelle im Fenster +-FENSTER mm die Hoehe mit EINEM zusammenhaengenden Querschnitt und kleinster Flaechenaenderung (keine Gesimse/Absaetze) waehlen.
  3. Schnitt per Boolean (manifold3d). Zapfen (Durchmesser = min(--zapfen-d, 0,6 x groesster Kreis im Querschnitt)) am unteren Segment, Bohrung mit --spiel am oberen,
     Mittelpunkt = groesster einbeschriebener Kreis (Pol der Unzugaenglichkeit), damit der Zapfen sicher im Material steht.
  4. Nadel: ab der Hoehe, an der der Querschnittsdurchmesser unter --stab-d + 2 x --stab-wand faellt, wird abgeschnitten und eine Stabbohrung (Stabdurchmesser + --spiel,
     --stab-tiefe) gebohrt; Bericht nennt die Stablaenge (ANNAHME: Messing/Stahl, im Slicer nicht druckbar).
  /media/oem/scan/venv-seg/bin/python -I tools/modell_teilen.py <modell.stl> [--ausgabe PRAEFIX] [--max-hoehe 200] [--stab-d 0.8] [--kein-stab] [--bericht datei.json]
Ausgabe: <PRAEFIX>_teil_1..N.stl (unten = Teil 1; jedes Teil steht mit seiner ebenen Schnittflaeche unten auf dem Druckbett) und <PRAEFIX>_teilen.json.
GRENZEN: Passung (--spiel 0,2 mm) und Wandstaerken sind Voreinstellungen fuer FDM; erst am Testdruck pruefen. Stuetzen/Ausrichtung entscheidet der Slicer.
Es prueft: jedes Teil wasserdicht, 1 Koerper, Volumenbilanz (Summe der Teile = Original + Zapfen - Bohrungen +- 0,5 %).
"""
import sys, os, json, math, argparse, numpy as np, trimesh
from shapely.ops import polylabel

def schnitt(m, z):
    s = m.section(plane_origin=[0, 0, z], plane_normal=[0, 0, 1])
    if s is None: return None
    p2, T = s.to_2D(); return p2.polygons_full, T

def flaeche_und_kreis(m, z):
    r = schnitt(m, z)
    if r is None or len(r[0]) != 1: return None                       # genau EIN Querschnittsteil (kein Gesims, keine zwei Tuermchen)
    poly, T = r[0][0], r[1]; p = polylabel(poly, tolerance=0.05); rad = poly.exterior.distance(p) if poly.interior_distance(p) is None else min(poly.exterior.distance(p), *[i.distance(p) for i in poly.interiors]) if len(poly.interiors) else poly.exterior.distance(p)
    c3 = T @ np.array([p.x, p.y, 0.0, 1.0]); return poly.area, float(rad), c3[:2]

def box(x0, x1, y0, y1, z0, z1): return trimesh.creation.box(extents=[x1 - x0, y1 - y0, z1 - z0], transform=trimesh.transformations.translation_matrix([(x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2]))
def zyl(xy, z0, z1, d): c = trimesh.creation.cylinder(radius=d / 2, height=z1 - z0, sections=48); c.apply_translation([xy[0], xy[1], (z0 + z1) / 2]); return c
def bool_(a, b, art): return trimesh.boolean.difference([a, b], engine="manifold") if art == "diff" else trimesh.boolean.union([a, b], engine="manifold") if art == "union" else trimesh.boolean.intersection([a, b], engine="manifold")

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("stl"); ap.add_argument("--ausgabe"); ap.add_argument("--max-hoehe", type=float, default=200.0); ap.add_argument("--fenster", type=float, default=15.0)
    ap.add_argument("--zapfen-d", type=float, default=6.0); ap.add_argument("--zapfen-h", type=float, default=6.0); ap.add_argument("--spiel", type=float, default=0.2)
    ap.add_argument("--stab-d", type=float, default=0.8); ap.add_argument("--stab-wand", type=float, default=0.6); ap.add_argument("--stab-tiefe", type=float, default=15.0); ap.add_argument("--kein-stab", action="store_true")
    ap.add_argument("--min-querschnitt", type=float, default=30.0, help="mm2: oberhalb dieser Flaeche darf geschnitten werden (kein Schnitt durch die Nadel)"); ap.add_argument("--bericht")
    a = ap.parse_args(); m = trimesh.load(a.stl); z0, z1 = float(m.bounds[0, 2]); z1 = float(m.bounds[1, 2]); pre = a.ausgabe or os.path.splitext(a.stl)[0]; B = m.bounds; X0, X1, Y0, Y1 = B[0, 0] - 5, B[1, 0] + 5, B[0, 1] - 5, B[1, 1] + 5
    bericht = dict(stl=a.stl, hoehe_mm=round(z1 - z0, 2), volumen_cm3=round(m.volume / 1000, 2), parameter={k: v for k, v in vars(a).items() if k not in ("stl",)}, annahmen=["Passung/Wandstaerken sind FDM-Voreinstellungen, am Testdruck pruefen", "Stab aus Metall (Messing/Stahl), Durchmesser --stab-d"])
    # Nadel: Hoehe, ab der der Querschnitt (Aequivalentdurchmesser) kleiner als der Stab + 2 Wand wird
    stab_z = None
    if not a.kein_stab:
        dmin = a.stab_d + 2 * a.stab_wand; zz = np.arange(z1 - 1.0, z0, -1.0)
        for z in zz:                                                         # von oben nach unten: erster Schnitt, der dick genug ist
            r = schnitt(m, z)
            if r and r[0] and 2 * math.sqrt(sum(p.area for p in r[0]) / math.pi) >= dmin: stab_z = float(z); break
        if stab_z: bericht["stab"] = dict(abschneiden_bei_mm=round(stab_z - z0, 2), stab_d_mm=a.stab_d, bohrung_d_mm=round(a.stab_d + a.spiel, 2), tiefe_mm=a.stab_tiefe)
    zk = (stab_z if stab_z else z1)                                          # Koerperhoehe ohne Nadel
    # Trennstellen
    N = max(1, math.ceil((zk - z0) / a.max_hoehe)); ziele = [z0 + (zk - z0) * i / N for i in range(1, N)]; trenn = []
    for zt in ziele:
        best = None
        for z in np.arange(zt - a.fenster, zt + a.fenster + 1e-6, 1.0):
            f0 = flaeche_und_kreis(m, z - 2.0); f1 = flaeche_und_kreis(m, z); f2 = flaeche_und_kreis(m, z + 2.0)
            if not (f0 and f1 and f2) or f1[0] < a.min_querschnitt: continue
            sprung = abs(f2[0] - f0[0]) / max(f1[0], 1.0); sc = sprung + 0.002 * abs(z - zt)
            if best is None or sc < best[0]: best = (sc, float(z), f1)
        if best is None: sys.exit(f"keine geeignete Trennstelle bei {zt - z0:.0f} mm (kein einteiliger Querschnitt) - --fenster vergroessern")
        trenn.append(dict(ziel_mm=round(zt - z0, 1), gewaehlt_mm=round(best[1] - z0, 1), flaeche_mm2=round(best[2][0], 0), einbeschriebener_radius_mm=round(best[2][1], 2), mitte_xy=[round(float(x), 2) for x in best[2][2]], flaechenaenderung=round(best[0], 4)))
    bericht["trennstellen"] = trenn; zs = [t["gewaehlt_mm"] + z0 for t in trenn]
    # Stuecke
    grenzen = [z0 - 1.0] + zs + [z1 + 1.0]; teile = []
    full = m
    if stab_z: full = bool_(m, box(X0, X1, Y0, Y1, z0 - 1, stab_z), "inter")
    for i in range(len(grenzen) - 1):
        lo, hi = grenzen[i], grenzen[i + 1]; t = bool_(full, box(X0, X1, Y0, Y1, lo, hi), "inter")
        if i < len(trenn):                                                   # Zapfen oben
            tr = trenn[i]; d = min(a.zapfen_d, 1.2 * tr["einbeschriebener_radius_mm"] * 0.6 * 2 / 2) if False else min(a.zapfen_d, 0.6 * 2 * tr["einbeschriebener_radius_mm"]); tr["zapfen_d_mm"] = round(d, 2)
            t = bool_(t, zyl(tr["mitte_xy"], zs[i] - 0.5, zs[i] + a.zapfen_h, d), "union")
        if i > 0:                                                            # Bohrung unten
            tr = trenn[i - 1]; d = tr["zapfen_d_mm"] + a.spiel; t = bool_(t, zyl(tr["mitte_xy"], zs[i - 1] - 0.01, zs[i - 1] + a.zapfen_h + a.spiel, d), "diff")
        if i == len(grenzen) - 2 and stab_z and True:                        # Stabbohrung von oben im obersten Teil
            c = flaeche_und_kreis(m, stab_z - 1.0); xy = c[2] if c else [0.0, 0.0]; t = bool_(t, zyl(xy, stab_z - a.stab_tiefe, stab_z + 1.0, a.stab_d + a.spiel), "diff"); bericht["stab"]["mitte_xy"] = [round(float(x), 2) for x in xy]
        t.apply_translation([0, 0, -t.bounds[0, 2]]); teile.append(t)
    res = []; vsum = 0.0
    for i, t in enumerate(teile, 1):
        p = f"{pre}_teil_{i}.stl"; t.export(p); vsum += t.volume
        res.append(dict(teil=i, datei=p, hoehe_mm=round(float(t.bounds[1, 2]), 2), breite_mm=round(float(t.extents[0]), 1), tiefe_mm=round(float(t.extents[1]), 1), volumen_cm3=round(t.volume / 1000, 2), wasserdicht=bool(t.is_watertight), koerper=len(t.split(only_watertight=False))))
    bericht["teile"] = res; bericht["volumen_summe_cm3"] = round(vsum / 1000, 2)
    orig = (full.volume if stab_z else m.volume); bericht["volumenbilanz_abweichung_prozent"] = round(100 * (vsum - orig) / orig, 3)
    ok = all(r["wasserdicht"] and r["koerper"] == 1 for r in res) and abs(bericht["volumenbilanz_abweichung_prozent"]) < 0.5; bericht["bestanden"] = bool(ok)
    json.dump(bericht, open(a.bericht or pre + "_teilen.json", "w"), indent=1, ensure_ascii=False)
    print(f"{len(teile)} Teile, Hoehe {bericht['hoehe_mm']} mm; Trennstellen {[t['gewaehlt_mm'] for t in trenn]} mm; Stab: {bericht.get('stab')}")
    for r in res: print(f"  Teil {r['teil']}: {r['hoehe_mm']} mm hoch, {r['breite_mm']} x {r['tiefe_mm']} mm, {r['volumen_cm3']} cm3, wasserdicht {r['wasserdicht']}, Koerper {r['koerper']}")
    print(f"Volumenbilanz {bericht['volumenbilanz_abweichung_prozent']:+.3f} %  ->", "BESTANDEN" if ok else "FEHLER"); sys.exit(0 if ok else 1)

if __name__ == "__main__": main()
