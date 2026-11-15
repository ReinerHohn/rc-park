#!/usr/bin/env python3
"""schwab_nachbar_gen.py - Generator-Rumpf (manifold3d). Jedes sichtbare Element meldet sich mit beleg(); Bau + Abnahme: tools/bauen_abnehmen.sh schwab_nachbar"""
import os, sys, json, numpy as np
from manifold3d import Manifold as M
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
from dach_bauen import gebaeude_aus_lod2, seiten_aus_rahmen
SCALE = float(os.environ.get("SCALE", "87")); K = 1000.0 / SCALE
OUT = os.path.join(HERE, "stl", "schwab_nachbar_1-{SCALE:.0f}.stl".format(SCALE=SCALE))
ELEMENTE = []
def beleg(seite, element, quelle, **masse): ELEMENTE.append(dict(seite=seite, element=element, quelle=quelle, **masse))
OBJ = os.path.join(HERE, "schwab_nachbar", "objekt.json"); obj = json.load(open(OBJ))
SEITEN = seiten_aus_rahmen(obj)
if obj.get("lod2", {}).get("id"):                    # Standard: LoD2-Grundriss + DOM1-Dach (dach.json, Nullstart-Schritt 'dach') - tools/dach_bauen.py
    koerper, belege, haupt = gebaeude_aus_lod2(OBJ)
    for b_ in belege: beleg(**b_)
    # ---- 15.11.2026 Nachbarhaus Teil 1 (direkt am Turm): Fassaden Nord (Fachwerkgiebel) und Sued als Relief aus dem neuen OpenMVS-Netz, Durchfahrt aus Fotomassen ----
    from bauteile import Wand, spitzbogen
    from relief_einsatz import koerper as relief_koerper
    WN = Wand((3.56, 2.85), (3.53, 9.45), aussen=(20.0, 6.0)); WS = Wand((-6.80, 1.00), (-7.02, 9.35), aussen=(-30.0, 5.0))      # Wandgeraden im Erdgeschoss aus der dichten Wolke (Rest 0,7 cm)
    huelle_n = koerper + koerper.translate((0.8, 0, 0)) + koerper.translate((1.6, 0, 0)); huelle_s = koerper + koerper.translate((-0.8, 0, 0)) + koerper.translate((-1.6, 0, 0)) + koerper.translate((-2.3, 0, 0))
    for nm_, W_, hu_, tf_ in (("nord", WN, huelle_n, 0.4), ("sued", WS, huelle_s, 0.4)):
        rp = os.path.join(HERE, "schwab_nachbar", "relief", nm_ + ".npz")
        if os.path.exists(rp) and os.environ.get("OHNE_RELIEF") != "1":
            koerper = koerper + (relief_koerper(rp, tiefe=tf_, trend=True) ^ hu_)        # nur innerhalb des Gebaeudeumrisses (sonst stuende die Platte im Himmel neben dem Giebel)
            beleg("wand", f"Relief Fassade {nm_} (Teil 1) mit Auskragungen", "OpenMVS-Netz der neuen dichten Wolke (rc-park_daten/schwab_v3/sfm_neu/openmvs), Hoehenbild 5 cm",
                  hinweis="Scan-Relief, kein Mass: Geschosse kragen bis 0,6 m (Nord) bzw. 1,2 m (Sued, Erker) vor; Fenster, Fachwerk und Gesimse nur als weiches Relief - scharf nachbauen")
    WNO = Wand((3.5, 2.8), (12.0, -1.5), aussen=(9.0, 12.0)); rp = os.path.join(HERE, "schwab_nachbar", "relief", "nordost.npz")       # Nordost-Fassade (Teile 0 und 2): LoD2-Kante, Lage/Schraege kommen aus dem Relief (trend)
    if os.path.exists(rp) and os.environ.get("OHNE_RELIEF") != "1":
        hu_ = koerper + koerper.translate(tuple(0.8 * WNO.n) + (0.0,)) + koerper.translate(tuple(1.6 * WNO.n) + (0.0,))
        koerper = koerper + (relief_koerper(rp, tiefe=0.9, trend=True) ^ hu_)
        beleg("wand", "Relief Nordost-Fassade (Teile 0/2) z 0,5-11,3 m", "OpenMVS-Netz der neuen dichten Wolke, Hoehenbild 5 cm", hinweis="Scan-Relief, kein Mass; der dritte Bogen (Laube am Nordostfluegel) ist darin ein Loch = geschlossene Wand (ANNAHME), Rundfenster und Fenster nur weich; LoD2-Kante liegt ~5 Grad schraeg zur Fassade")
    WL = Wand((5.15, 2.08), (11.89, -1.43), aussen=(9.0, 12.0))                 # Nordost-Fassade im Erdgeschoss: Wandgerade aus der dichten Wolke (23 952 Punkte, Rest 0,8 cm)
    koerper = koerper - WL.prisma(spitzbogen(5.41 / 2, 3.5, 5.83), u=4.535, w0=-4.0, w1=2.2)       # Laube (dritter Bogen): Masse M-113529-001..-004; Tiefe 4 m = ANNAHME (offene Halle, Rueckwand im Foto sichtbar)
    beleg("wand", "Laube Nordost (dritter Bogen)", "foto_mass.py auf der Fassadenebene, Foto 113529 (M-113529-001..-004), Gegenprobe Foto 113452 (gleiche Kanten aus anderem Winkel)", lichte_breite=5.41, scheitel=5.83, kaempfer=3.5,
          hinweis="ANNAHME: Tiefe der Halle 4 m, Kreisboegen; Masswerkbruestung darueber (z 7-8 m), Holzstreben in der Laube und Treppe dahinter fehlen")
    koerper = koerper - WN.prisma(spitzbogen(3.20, 3.90, 6.35), u=3.30, w0=-7.0, w1=1.7) - WS.prisma(spitzbogen(3.15, 4.05, 6.39), u=5.25, w0=-7.0, w1=2.4)
    beleg("wand", "Durchfahrt (zweiter Torbogen) Nord und Sued", "foto_mass.py auf den Fassadenebenen, Fotos 113310 (Nord) und commons 217 (Sued): M-113310-001..-004, M-commons217-001..-003", nord_halbe_breite=3.20,
          nord_scheitel=6.35, nord_kaempfer=3.90, sued_halbe_breite=3.15, sued_scheitel=6.39, sued_kaempfer=4.05,
          hinweis="ANNAHME: Boegen symmetrisch (in den Fotos ist nur die turmseitige Haelfte zu sehen; Spannweite passt zum Netz), Kreisboegen, Durchfahrt gerade von Nord nach Sued")
    cu, cv = haupt.mean(0); model = koerper.scale((K, K, K))   # 15.11.2026: NICHT zentrieren - STL bleibt im Rahmen (objekt.json rahmen); die Fotowerkzeuge (zentrierung 'achse') erwarten STL = Rahmen, sonst liegt das Modell um (cu, cv) neben Kameras/Wolke
else:
    H = 10.0                               # Gesamthoehe (m) - Quelle in masstabelle.json
    beleg("dach", "Grundkoerper", "ANNAHME: Rumpf ohne LoD2 (objekt.json lod2.id fehlt)", hoehe=H)
    model = M.cube((8.0, 8.0, H)).translate((-4.0, -4.0, 0.0)).scale((K, K, K))
from bauteile import stl_schreiben
stl_schreiben(model, OUT, b"schwab_nachbar")          # verschweisst Ecken, entfernt entartete Dreiecke (sonst Splitter als Einzelkoerper)
json.dump([dict(e, seite_name=SEITEN.get(e["seite"], e["seite"])) for e in ELEMENTE], open(os.path.join(HERE, "schwab_nachbar", "elemente.json"), "w"), indent=1, ensure_ascii=False)
print("->", OUT)
