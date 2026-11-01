#!/usr/bin/env python3
"""modell_pruefstand.py - Abnahme-Pruefstand Martinstor: feste Merkmale aus FOTOS und LASER, gemessen am STL.

Zweck: Verhindern, dass eine bereits behobene Abweichung (z. B. "Tuermchen zu gedrungen", "Mittelspitze zu dick")
durch eine spaetere Aenderung unbemerkt zurueckkommt. Gelaufen wird NACH JEDER Generatoraenderung, vor Commit/Viewer:

  /media/oem/scan/venv-seg/bin/python -I tools/modell_pruefstand.py [modelle/stl/martinstor_v4_1-87.stl]   (Exit 1 bei Fehlschlag)

Jede Pruefung hat Quelle + Toleranz. NEUE Nutzerbeobachtungen ("sieht zu ... aus") werden hier als Pruefung ergaenzt, bevor der
Generator geaendert wird (erst Test, der fehlschlaegt - dann Fix). Pruefwerte NICHT lockern, um Gruen zu bekommen; nur mit neuer Quelle.
"""
import sys, numpy as np, trimesh

STL = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("-") else "modelle/stl/martinstor_v4_1-87.stl"
m = trimesh.load(STL); m.apply_scale(87 / 1000.0)
c = m.bounds.mean(0); m.apply_translation([-c[0], -c[1], -m.bounds[0, 2]])

def polys(z):
    s = m.section(plane_origin=[0, 0, z], plane_normal=[0, 0, 1])
    if s is None: return []
    p, _ = s.to_2D()
    out = []
    for g in p.polygons_full:
        cen = np.array(g.centroid.coords[0]); out.append((cen, g))
    return out

def turret_polys(z):    # Eckturmchen: Schwerpunkt weit aus der Achse
    return [(c0, g) for c0, g in polys(z) if abs(c0[0]) > 2.5 and abs(c0[1]) > 2.5]

def spire_polys(z):
    return [(c0, g) for c0, g in polys(z) if abs(c0[0]) < 1.5 and abs(c0[1]) < 1.5]

def diam(g): return 2 * np.sqrt(g.area / np.pi)

def turret_tip():       # hoechster Punkt ausserhalb der Achse ueber 35 m
    v = m.vertices; k = (v[:, 2] > 35) & (np.abs(v[:, 0]) > 2.5) & (np.abs(v[:, 1]) > 2.5)
    return float(v[k, 2].max())

def spire_width(z):
    sp = spire_polys(z); return max([diam(g) for _, g in sp], default=0.0)

def turret_cone_diam_below_tip(d):
    tip = turret_tip(); tp = turret_polys(tip - d)
    return float(np.mean([diam(g) for _, g in tp])) if tp else float("nan"), len(tp)

checks = []   # (Name, Messwert, lo, hi, Quelle)
tip = turret_tip()
checks.append(("Tuermchen-Spitze Hoehe (m)", tip, 40.7, 41.8, "Laser DOM1: lokale Maxima 40,9 und 41,4 m (Mittel 41,15; Journal 12: 43,6 war OSM, nicht Laser)"))
dc, n = turret_cone_diam_below_tip(2.0)
checks.append(("Tuermchen-Kegel Durchmesser 2 m unter Spitze (m)", dc, 0.4, 1.2, "Foto 043/044 + Journal 10/6: Kegel schlank (>= ~2:1); Nutzer 'zu gedrungen'"))
dc4, _ = turret_cone_diam_below_tip(4.0)
checks.append(("Tuermchen-Kegel Durchmesser 4 m unter Spitze (m)", dc4, 0.8, 1.7, "Foto 043/044, Journal 6/10: Kegel ca. 3:1 (Hoehe:Fussbreite) -> bei 5,3 m Hoehe ~1,05 m; alt 4,5 m/r 1,42 gab 2,0 m"))
checks.append(("Tuermchen gefunden (Anzahl Querschnitte bei Spitze-2 m)", float(n), 4, 4, "Modell: 4 Ecktuermchen"))
checks.append(("Dachreiter Dicke bei 50 m (m)", spire_width(50.0), 0.08, 0.40, "Foto 049 Vollbild: Nadel 0,08-0,14 m, Mast 0,09-0,26 m (+Druck-Untergrenze); DOM1 verschmiert Nadel (Journal 12 war Artefakt); Nutzer 'Mittelspitze stimmt nicht'"))
checks.append(("Dachreiter Dicke bei 52 m (m)", spire_width(52.0), 0.08, 0.30, "wie oben"))
zs = np.arange(47.0, 52.0, 0.1); ws = [spire_width(z) for z in zs]; kz = float(zs[int(np.argmax(ws))]); kw = float(max(ws))
checks.append(("Dachreiter Knauf Durchmesser (m)", kw, 0.50, 0.90, "Foto 049: 44 px x 1,5 cm = ~0,67 m"))
TOPZ = float(m.extents[2])
checks.append(("Dachreiter Knauf Lage (Anteil der Laenge ueber First)", (kz - 46.2) / (TOPZ - 46.2), 0.12, 0.32, "Foto 049/000: Knauf bei ~20-28 % der Spitzenlaenge ueber dem First"))
checks.append(("Gesamthoehe (m)", TOPZ, 59.5, 66.0, "DOKUMENTIERT: Bauforschung BW (Landesdenkmalamt) 60 m nach 1901 / 65 m Objektbeschreibung; en.Wikipedia 60 m; Structurae ~65 m; de.Wikipedia 66 m (Plan Schaefer). Laser DOM1 54,8 m ist nur hoechste getroffene Flaeche (Nadel unsichtbar)"))
checks.append(("Spitzenlaenge ueber First (m)", TOPZ - 46.2, 12.0, 16.5, "Foto 049 Vollbild 16,6 / 014: 16,0 / 000: 12,4 m (Massstab aus Modellmassen, grob); Register J3"))
checks.append(("Wasserdicht (1=ja)", 1.0 if m.is_watertight else 0.0, 1, 1, "Druckfaehigkeit"))
checks.append(("Anzahl getrennte Koerper", float(len(m.split(only_watertight=False))), 1, 1, "Schwebende Teile (Journal: 14 gefunden)"))

def fenster_anzahl(face, z, half=4.6):
    """Zaehlt Fensternischen (Rueckversatz >= 0,2 m) entlang einer Fassade auf Hoehe z (Strahlen von aussen)."""
    sgn = 1.0 if face == "+x" else -1.0
    us = np.arange(-half, half + 1e-6, 0.05)
    org = np.array([[sgn * 30.0, u, z] for u in us]); dr = np.tile([-sgn, 0.0, 0.0], (len(us), 1))
    loc, ir, _ = m.ray.intersects_location(org, dr, multiple_hits=False)
    d = np.full(len(us), np.nan); d[ir] = np.abs(loc[:, 0])             # Abstand der getroffenen Flaeche von der Mitte
    wall = np.nanmedian(d); rec = (wall - d) >= 0.2; n = 0; run = 0
    for r in list(rec) + [False]:
        if r: run += 1
        else:
            if 6 <= run <= 40: n += 1                                   # Breite 0,3 - 2,0 m
            run = 0
    return float(n)
SUED, NORD = "+x", "-x"     # Konvention im Generator (Uhrseiten); Zuordnung zur echten Himmelsrichtung: Nutzer 'Uhr zeigt nach Sueden'
checks.append(("Fenster obere Reihe Suedseite (Anzahl, z 22,1 m)", fenster_anzahl(SUED, 22.07), 2, 2, "Fotos 041/030/042/001 (Suedseite, McDonald's links): zwei Schlitzfenster unter der Uhr"))
checks.append(("Fenster untere Reihe Suedseite (Anzahl, z 18,5 m)", fenster_anzahl(SUED, 18.5), 1, 1, "Fotos 041/030/001: ein Fenster tiefer"))
checks.append(("Fenster obere Reihe Nordseite (Anzahl, z 22,1 m)", fenster_anzahl(NORD, 22.07), 3, 3, "Foto 031 (Vollbild 2025): DREI Fenster in einer Reihe (u -2,6 / 0 / +2,5 m)"))
checks.append(("Fenster untere Reihe Nordseite (Anzahl, z 18,5 m)", fenster_anzahl(NORD, 18.5), 1, 1, "Foto 031: ein Schlitz tiefer bei u ~ 0"))

bad = 0
print(f"Pruefstand Martinstor  ({STL})")
for name, val, lo, hi, src in checks:
    ok = (lo <= val <= hi) if not np.isnan(val) else False
    bad += 0 if ok else 1
    print(f"  {'OK    ' if ok else 'FEHLER'}  {name:58s} {val:7.2f}  Soll {lo:g}..{hi:g}   [{src}]")
print("ERGEBNIS:", "alle Pruefungen bestanden" if not bad else f"{bad} Pruefung(en) FEHLGESCHLAGEN - Modell NICHT freigeben")
sys.exit(1 if bad else 0)
