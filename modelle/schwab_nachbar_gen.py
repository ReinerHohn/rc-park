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
    # 16.11.2026 FLUEGEL (LoD2-Teil 0): die angepasste Sattelform (First 21,7, RMS 1,1 m) stand als hohe Wand vor dem halben Fachwerkgiebel -> Dach als Hoehenfeld direkt aus dem Laser
    from laserdach import laserdach_koerper, prisma as _prisma
    _T0 = json.load(open(os.path.join(HERE, "schwab_nachbar", "dach.json")))["teile"][0]["grundriss_uv"]
    koerper = (koerper - _prisma(_T0, 60.0)) + laserdach_koerper(OBJ, _T0, px=0.5)
    beleg("dach", "Fluegel (Teil 0): Dach als Hoehenfeld aus dem DOM1-Laser", "DOM1-Laser 1 m (LGL), bilinear auf 0,5 m; Grundriss LoD2", hinweis="grob (1-m-Pixel), keine Traufkanten/Gauben als Form; vom Boden nicht einsehbar - Fotos/Wolke blind; am Giebelanschluss misst der Laser den Giebel mit")
    # ---- 15.11.2026 Nachbarhaus Teil 1 (direkt am Turm): Fassaden Nord (Fachwerkgiebel) und Sued als Relief aus dem neuen OpenMVS-Netz, Durchfahrt aus Fotomassen ----
    from bauteile import Wand, spitzbogen
    from relief_einsatz import koerper as relief_koerper
    WN = Wand((3.56, 2.85), (3.53, 9.45), aussen=(20.0, 6.0)); WS = Wand((-6.80, 1.00), (-7.02, 9.35), aussen=(-30.0, 5.0))      # Wandgeraden im Erdgeschoss aus der dichten Wolke (Rest 0,7 cm)
    huelle_n = koerper + koerper.translate((0.8, 0, 0)) + koerper.translate((1.6, 0, 0)); huelle_s = koerper + koerper.translate((-0.8, 0, 0)) + koerper.translate((-1.6, 0, 0)) + koerper.translate((-2.3, 0, 0))
    for nm_, W_, hu_, tf_ in ():                                         # Nord und Sued seit 15.11. scharf gebaut (unten), kein Netz-Relief mehr
        rp = os.path.join(HERE, "schwab_nachbar", "relief", nm_ + ".npz")
        if os.path.exists(rp) and os.environ.get("OHNE_RELIEF") != "1":
            koerper = koerper + (relief_koerper(rp, tiefe=tf_, trend=True) ^ hu_)        # nur innerhalb des Gebaeudeumrisses (sonst stuende die Platte im Himmel neben dem Giebel)
            beleg("wand", f"Relief Fassade {nm_} (Teil 1) mit Auskragungen", "OpenMVS-Netz der neuen dichten Wolke (rc-park_daten/schwab_v3/sfm_neu/openmvs), Hoehenbild 5 cm",
                  hinweis="Scan-Relief, kein Mass: Geschosse kragen bis 0,6 m (Nord) bzw. 1,2 m (Sued, Erker) vor; Fenster, Fachwerk und Gesimse nur als weiches Relief - scharf nachbauen")
    WNO = Wand((3.5, 2.8), (12.0, -1.5), aussen=(9.0, 12.0)); rp = os.path.join(HERE, "schwab_nachbar", "relief", "nordost.npz")       # Nordost-Fassade (Teile 0 und 2): LoD2-Kante, Lage/Schraege kommen aus dem Relief (trend)
    if os.path.exists(rp) and os.environ.get("MIT_RELIEF_NO") == "1":      # 16.11.: Nordost-Fassade ist jetzt scharf gebaut (unten), Netz-Relief nur noch auf Wunsch
        hu_ = koerper + koerper.translate(tuple(0.8 * WNO.n) + (0.0,)) + koerper.translate(tuple(1.6 * WNO.n) + (0.0,))
        koerper = koerper + (relief_koerper(rp, tiefe=0.9, trend=True) ^ hu_)
        beleg("wand", "Relief Nordost-Fassade (Teile 0/2) z 0,5-11,3 m", "OpenMVS-Netz der neuen dichten Wolke, Hoehenbild 5 cm", hinweis="Scan-Relief, kein Mass; der dritte Bogen (Laube am Nordostfluegel) ist darin ein Loch = geschlossene Wand (ANNAHME), Rundfenster und Fenster nur weich; LoD2-Kante liegt ~5 Grad schraeg zur Fassade")
    # ---- 15.11.2026 NORDGIEBEL SCHARF (Fachwerk-Steilgiebel): Ortgang/First M-113033-001..-003, Geschossebenen aus der dichten Wolke, Fenster M-113210-001..-007, M-113144-001/-002, M-113033-004..-007 ----
    koerper = koerper - WN.kasten(-7.5, 0.0, 11.0, 30.0, 0.0, 3.4)       # 16.11.: vor der linken Giebelhaelfte misst der Laser (1-m-Pixel) den Giebel mit -> Fluegeldach dort bis 2,6 m vor der Wand auf 11 m begrenzt (ANNAHME; Traufe am Foto ~10-11 m)
    UA, ZA, ST, UR = -0.13, 25.35, 1.66, 6.99                          # Firstlage u (= y 2,72), Firsthoehe, Ortgangneigung, Hausende am Turm (u 6,99 = y 9,84)
    def dreieck(ab, w0, w1): return WN.huelle([(UA, ZA - ab, w_) for w_ in (w0, w1)] + [(UA + s_ * 20.0, ZA - ab - 20.0 * ST, w_) for s_ in (-1, 1) for w_ in (w0, w1)])
    koerper = koerper + WN.kasten(0.0, UR, 0.0, 10.14, -0.6, 0.0)       # Erdgeschoss + 1. OG (Putz) bis in die Wandebene und bis zur Turmkante
    himmel = WN.kasten(UA, UR + 0.3, 12.0, 40.0, -13.5, 1.7) + WN.kasten(-2.45, UA + 0.01, 18.5, 40.0, -13.5, 1.7) + WN.kasten(-3.96, -2.44, 18.5, 40.0, -13.5, -4.55)   # Ostflaeche: nur wo kein Fluegeldach (Teil 0) ueber der Ebene liegt
    koerper = koerper - (himmel - dreieck(0.0, -14.0, 2.0))             # Laserdach lag 0,4-0,9 m ueber dem gemessenen Ortgang (DOM1-Pixel am Turm verfaelscht)
    dach = dreieck(0.0, -10.55, 1.57) ^ (WN.kasten(UA - 0.01, UR, 12.0, 26.0, -10.55, 1.57) + WN.kasten(-3.96, UA, 18.5, 26.0, -10.55, 1.57))
    koerper = koerper + (dach - dreieck(0.35, 0.0, 1.6))                # vor der Wandebene bleibt nur die Dachplatte (Ortgang-Ueberstand), darunter die Geschosse
    koerper = koerper + WN.kasten(-1.67, UR, 9.96, 10.14, -0.3, 0.40)   # Balkenlage unter dem ersten Fachwerkgeschoss (Balkenkoepfe fehlen)
    for z0_, z1_, w_, ul_ in ((10.14, 13.41, 0.54, -1.67), (13.41, 16.75, 0.73, -1.9), (16.75, 19.75, 0.93, -3.96), (19.75, 22.2, 1.11, -3.96), (22.2, 26.0, 1.38, -3.96)):
        koerper = koerper + (WN.kasten(ul_, UR, z0_ - 0.01, z1_, -0.3, w_) ^ dreieck(0.34, -1.0, 2.0))
    # 16.11.2026 FACHWERKBALKEN: 3,5 cm vor dem Putz, Lage aus dem Mehrfoto-Fassadenbild (tools/fachwerk_aus_ortho.py; 10-12 Fotos gemittelt, Schwelle dunkel/hell), je Geschoss auf dessen Flaeche
    for id_, z0_, z1_, w_, ul_ in (("e17", 10.14, 13.41, 0.54, -1.67), ("e18", 13.41, 16.75, 0.73, -1.9), ("e20", 16.75, 19.75, 0.93, -3.96), ("e21", 19.75, 22.2, 1.11, -3.96)):
        fw_ = os.path.join(HERE, "schwab_nachbar", "relief", f"fachwerk_{id_}.npz")
        if os.path.exists(fw_) and os.environ.get("OHNE_FACHWERK") != "1": koerper = koerper + (relief_koerper(fw_, tiefe=0.05, rand_auslauf=False) ^ (WN.kasten(ul_, UR, z0_, z1_, w_ - 0.1, w_ + 0.1) ^ dreieck(0.34, -1.0, 2.0)))
    beleg("wand", "Fachwerkbalken Nordgiebel, Geschosse A-D (flaches Relief 3,5 cm)", "Mehrfoto-Fassadenbild (fassade_ortho.py, 12 Fotos, Median) -> tools/fachwerk_aus_ortho.py (Helligkeitsschwelle)", hinweis="ANNAHME: Balkenstaerke vor dem Putz 3,5 cm; Lage aus Farbschwelle auf dem Mehrfoto-Median statt Kanten-Sweep; linke Giebelhaelfte (im Fassadenbild verdeckt) und oberstes Giebelfeld ohne Balken; Schnitzwerk fehlt")
    FEN = [(-1.50, -0.85, 11.43, 12.99, 0.54, (), 12.53), (0.67, 2.11, 11.43, 12.99, 0.54, (1.39,), 12.53), (3.62, 5.85, 11.43, 12.99, 0.54, (4.35, 5.12), 12.53),
           (-1.50, -0.85, 14.69, 16.33, 0.73, (), 15.78), (0.67, 2.11, 14.69, 16.33, 0.73, (1.39,), 15.78), (3.57, 4.23, 14.69, 16.33, 0.73, (), 15.78),
           (-2.31, -0.89, 18.02, 19.27, 0.93, (-1.60,), 18.72), (0.69, 2.11, 18.02, 19.27, 0.93, (1.40,), 18.72), (-0.89, 0.61, 20.97, 21.80, 1.11, (-0.14,), None)]
    VERDECKT = []
    if os.environ.get("AUTO_FENSTER") == "1":            # Gegenprobe der Automatik (tools/fenster_aus_parsing.py) gegen die Handmasse: gleiche Pruefungen muessen bestehen
        from bauteile import fenster_aus_json
        koerper, _b = fenster_aus_json(koerper, os.path.join(HERE, "schwab_nachbar", "audit", "fenster_auto.json")); FEN = []
        for b_ in _b: beleg(**b_)
    for u0_, u1_, z0_, z1_, w_, tl_, kz_ in FEN:
        sonde = WN.kasten(u0_, u1_, z0_, z1_, w_ + 0.03, w_ + 0.08)
        if (koerper ^ sonde).volume() > 0.2 * sonde.volume(): VERDECKT.append((u0_, z0_)); continue          # Fluegeldach (Teil 0, Laser) steht im Modell davor -> kein Hohlraum im Inneren bauen
        ab_, zu_ = WN.fenster(u0_, u1_, z0_, z1_, w_, teiler=tl_, kaempfer=kz_); koerper = koerper - ab_ - WN.kasten(u0_ - 0.03, u1_ + 0.03, z0_ - 0.03, z1_ + 0.03, w_ + 0.001, w_ + 0.12) + zu_   # auch die Balkenplatte vor dem Fenster weg (sonst 2 cm Lippe / Splitter)
    koerper = koerper + WN.kasten(1.83, 4.80, 7.85, 9.98, -0.1, 0.06) - WN.kasten(2.09, 4.45, 8.0, 9.575, -0.2, 0.1)     # Steinfenster 1. OG: Gewaende 6 cm vor dem Putz (ANNAHME), Nische 20 cm (ANNAHME)
    koerper = koerper + WN.kasten(2.80, 2.93, 7.99, 9.585, -0.21, 0.03) + WN.kasten(3.65, 3.78, 7.99, 9.585, -0.21, 0.03)
    beleg("wand", "Nordgiebel: fuenf Fachwerkgeschosse mit Auskragungen, Ortgang, 9 Fenster, Steinfenster 1. OG", "foto_mass.py (M-113033-001..-007, M-113210-001..-007, M-113144-001/-002), Picks ueber wand_ortho.py; Geschossebenen aus der dichten Wolke",
          first=ZA, ortgang_neigung=ST, fenster_verdeckt=len(VERDECKT), hinweis="Fenster links (u < 0), die im Modell vom Fluegeldach (Teil 0, Laserform) verdeckt sind, wurden nicht geoeffnet - am Foto sind sie frei, das Fluegeldach ist also zu hoch/zu weit vorn; ANNAHME: Nischentiefe 12 cm, Rahmenbreiten 5-7 cm, Dachplatte 18 cm, Dach laeuft gerade bis zur Suedfassade; Fachwerkbalken, Balkenkoepfe, Eckquader, Firstspitze und Kamin fehlen; links unter z 18,5 verdeckt der Fluegel den Giebel (nicht gemessen)")
    # ---- 15.11.2026 SUEDFASSADE SCHARF (Nutzer: "Fenster zu weiche Kanten, alles schaerfer"): Masse M-113857-001..-011, M-113855-001..-003, Ebenen aus der dichten Wolke ----
    from bauteile import rundbogen
    SA, SZ, SS = 1.72, 25.35, 1.66                                       # First (u = y - 1; gleiche Firstlinie und Neigung wie am Nordgiebel), Ortgangfuss bei z 16,8
    def dr_s(ab, w0, w1): return WS.huelle([(SA, SZ - ab, w_) for w_ in (w0, w1)] + [(SA + s_ * 20.0, SZ - ab - 20.0 * SS, w_) for s_ in (-1, 1) for w_ in (w0, w1)])
    def saeule(poly, z0, z1): return WS.huelle([(u_, z_, w_) for u_, w_ in poly for z_ in (z0, z1)])
    koerper = koerper - WS.kasten(-6.5, 9.5, 0.0, 30.0, 0.0, 3.5)        # alles VOR der Wandebene weg (Reste von LoD2/Laserdach), dann neu aufbauen
    koerper = koerper + WS.kasten(-5.2, 8.45, 0.0, 14.4, -0.6, 0.0)      # Wand bis in die Ebene, von der Ostecke bis zum Turm
    koerper = koerper + (WS.kasten(-3.45, 6.75, 14.3, 26.0, -0.5, 0.0) ^ dr_s(0.35, -1.0, 0.5))                       # Giebelwand
    koerper = koerper + ((dr_s(0.0, -3.0, 0.3) - dr_s(0.35, -3.1, 0.4)) ^ WS.kasten(-3.52, 6.78, 16.8, 26.0, -3.0, 0.3))   # Ortgang/Dachplatte am Suedgiebel (Ueberstand 0,3 m, Tiefe 3 m: ANNAHME)
    VB = [(-3.8, -0.05), (-3.8, 1.15), (7.6, 1.15), (8.45, -0.05)]            # Vorbau 2. OG im Grundriss (u, w); Westende schraeg zum Turm
    koerper = koerper + saeule(VB, 10.17, 13.3) + saeule([(u_ - 0.1 * np.sign(u_ - 2.0), w_ + (0.1 if w_ > 0 else 0.0)) for u_, w_ in VB], 10.04, 10.17) + saeule([(u_ - 0.1 * np.sign(u_ - 2.0), w_ + (0.1 if w_ > 0 else 0.0)) for u_, w_ in VB], 13.3, 13.4)
    koerper = koerper + WS.huelle([(u_, z_, w_) for u_ in (-3.95, 8.45) for z_, w_ in ((13.4, -0.05), (13.4, 1.65), (13.5, 1.65), (14.4, -0.05))])     # Pultdach ueber dem Vorbau
    EK = [(-0.17, -0.05), (0.3, 1.05), (3.55, 1.05), (3.95, -0.05)]           # Erker 1. OG
    koerper = koerper + saeule(EK, 6.85, 10.1) + WS.huelle([(u_, 6.85, w_) for u_, w_ in EK] + [(u_, 5.5, w_) for u_, w_ in ((1.0, -0.05), (1.4, 0.3), (2.4, 0.3), (2.8, -0.05))])
    koerper = koerper + WS.kasten(0.25, 3.6, 7.95, 8.05, -0.05, 1.12)     # Bruestungsgesims des Erkers
    for u0_, u1_ in ((7.0, 7.9), (-3.75, -2.9)): koerper = koerper + WS.huelle([(u_, z_, w_) for u_ in (u0_, u1_) for z_, w_ in ((8.1, -0.05), (10.1, -0.05), (10.1, 1.1))])   # Konsolen unter dem Vorbau (Form ANNAHME)
    SF = [(u1_, u0_, 11.42, 12.79, 1.15, (), 12.42) for u0_, u1_ in ((7.11, 6.50), (5.63, 5.03), (4.54, 4.0), (3.44, 2.92), (2.63, 2.04), (1.76, 1.25), (0.96, 0.45), (-0.12, -0.66), (-1.2, -1.69), (-2.65, -3.08))]
    SF += [(2.92, 3.46, 8.03, 9.4, 1.05, (), 9.0), (2.09, 2.63, 8.03, 9.4, 1.05, (), 9.0), (1.25, 1.79, 8.03, 9.4, 1.05, (), 9.0), (0.47, 0.96, 8.03, 9.4, 1.05, (), 9.0)]      # Erker
    SF += [(4.02, 6.33, 8.03, 9.44, 0.0, (4.73, 5.57), 9.0), (-2.28, -1.79, 8.05, 9.47, 0.0, (), 9.0), (-4.02, -1.05, 5.09, 6.33, 0.0, (-1.74, -2.57, -3.35), None), (0.17, 0.62, 2.66, 3.74, 0.0, (), None)]
    SF += [(3.80, 5.49, 14.95, 16.3, 0.0, (4.65,), None), (0.57, 3.07, 14.95, 16.3, 0.0, (1.40, 2.24), None), (-1.88, -0.17, 14.95, 16.3, 0.0, (-1.03,), None),
           (2.14, 3.90, 17.91, 19.24, 0.0, (3.02,), None), (-0.32, 1.35, 17.91, 19.24, 0.0, (0.52,), None), (1.65, 1.89, 20.8, 22.08, 0.0, (), None)]
    for u0_, u1_, z0_, z1_, w_, tl_, kz_ in SF:
        if w_ == 0.0: koerper = koerper + WS.kasten(u0_ - 0.15, u1_ + 0.15, z0_ - 0.15, z1_ + 0.15, -0.1, 0.05)        # Steingewaende 5 cm vor dem Putz (ANNAHME)
        ab_, zu_ = WS.fenster(u0_, u1_, z0_, z1_, w_ + (0.05 if w_ == 0.0 else 0.0), tiefe=0.17, teiler=tl_, kaempfer=kz_, b=(0.30 if u0_ == -4.02 else 0.12) if (w_ == 0.0 and tl_) else 0.07); koerper = koerper - ab_ + zu_   # Zwischengeschoss: Steinpfosten ~0,3 m breit (entzerrtes Foto: Lichter je ~0,5 m)
    koerper = koerper - WS.prisma(rundbogen(2.89, -0.6, 3.83), u=-2.65, w0=-4.0, w1=0.5)                               # kleiner Rundbogen (Laube, Suedseite): Tiefe 4 m ANNAHME
    beleg("wand", "Suedfassade scharf: Giebel, Vorbau 2. OG mit 10 Fenstern, Erker 1. OG, Pultdach, 10 Wand-/Giebelfenster, kleiner Rundbogen", "foto_mass.py (M-113857-001..-011, M-113855-001..-003), Picks ueber wand_ortho.py; Ebenen aus der dichten Wolke",
          vorbau_breite=11.4, vorbau_tiefe=1.15, erker_breite=4.12, hinweis="ANNAHME: Nischentiefen 17 cm, Gewaende 5 cm, Konsolen- und Erkerfussform, Dachplatte, Fensterlagen der uebrigen 2.-OG-Fenster am entzerrten Bild abgelesen (nicht einzeln protokolliert); Masswerk der Erkerbruestung, Stufenquader am Ortgang, Eckquader fehlen")
    # ---- 16.11.2026 QUERDACH zum Turm (Nutzer: "Warum fehlt dieses Dach?"): Sattel mit First Ost-West in der Turmachse; Form aus der dichten Wolke (17 000 Punkte ueber dem Hauptdach) ----
    QX, QZ, QS, QN = -2.0, 22.5, 1.55, 1.44                              # Firstlage x, Firsthoehe, Neigung Sued-/Nordflaeche
    koerper = koerper + M.hull_points([[x_, y_, z_] for y_ in (4.2, 9.7) for x_, z_ in ((QX, QZ), (QX - (QZ - 15.5) / QS, 15.5), (QX + (QZ - 15.5) / QN, 15.5))])
    beleg("dach", "Querdach zum Turm (Sattel, First z 22,5 in der Turmachse)", "dichte Wolke sfm_neu (Median je 0,5-m-Streifen); Augenschein Nord-Fernfoto 113033", first=QZ, neigung_sued=QS, neigung_nord=QN,
          hinweis="Form aus der Wolke, nicht aus Fotokanten (kein Foto zeigt es frei); Anschluss an Hauptdach und Turmwand ANNAHME, Traufen nicht gemessen")
    WL = Wand((5.15, 2.08), (11.89, -1.43), aussen=(9.0, 12.0))                 # Nordost-Fassade im Erdgeschoss: Wandgerade aus der dichten Wolke (23 952 Punkte, Rest 0,8 cm)
    # ---- 16.11.2026 NORDOST-FASSADE SCHARF (Fluegel mit Laube): M-113529-005..-011 auf der Fassadenebene ----
    koerper = koerper - WL.kasten(-1.7, 7.7, 0.0, 10.0, 0.0, 2.5) + WL.kasten(-1.7, 7.6, 0.0, 10.0, -0.6, 0.0)       # vor der Ebene frei, Wand bis in die Ebene
    koerper = koerper - WL.kasten(0.63, 7.5, 8.01, 9.83, -1.5, 0.3)                                                # Loggia: offen ueber der Bruestung, 1,5 m tief (ANNAHME)
    for u_ in (2.84, 5.25): koerper = koerper + WL.kasten(u_ - 0.11, u_ + 0.11, 7.95, 9.9, -0.3, -0.05)            # zwei Saeulen (als Vierkant 22 cm; Form ANNAHME)
    koerper = koerper + WL.kasten(0.5, 7.6, 6.9, 7.0, -0.05, 0.08) + WL.kasten(0.5, 7.6, 7.93, 8.01, -0.05, 0.06)   # Gesims unter und Handlauf auf der Bruestung
    for u0_, u1_, z0_, z1_, tl_ in ((-1.51, -0.11, 8.08, 9.54, (-0.80,)), (-1.49, -0.02, 5.02, 6.39, (-0.75,))):
        koerper = koerper + WL.kasten(u0_ - 0.15, u1_ + 0.15, z0_ - 0.15, z1_ + 0.15, -0.1, 0.05); ab_, zu_ = WL.fenster(u0_, u1_, z0_, z1_, 0.05, tiefe=0.17, teiler=tl_, b=0.12); koerper = koerper - ab_ + zu_
    koerper = koerper + WL.scheibe(-0.06, 2.85, 1.42, -0.05, 0.05) - WL.scheibe(-0.06, 2.85, 0.80, -0.15, 0.1)     # Rundfenster: Steinring 5 cm vor dem Putz, Nische 15 cm (ANNAHME)
    beleg("wand", "Nordost-Fassade scharf: Loggia mit Bruestung und zwei Saeulen, 2 Doppelfenster, Rundfenster", "foto_mass.py auf der Fassadenebene, Foto 113529 (M-113529-005..-011), Picks ueber wand_ortho.py",
          loggia_breite=7.05, loggia_hoehe=1.82, bruestung=1.10, hinweis="ANNAHME: Loggiatiefe 1,5 m, Saeulen als Vierkant, Bruestung geschlossen (Masswerk fehlt), Gewaende 5 cm; Walmdach, Dachgelaender, Eckquader, Schriftzug fehlen")
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
