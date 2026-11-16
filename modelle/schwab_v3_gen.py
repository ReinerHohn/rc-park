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
    # MASSSTAB (15.11.2026): Alle Fotomasse unten sind ROHMASSE im SfM-Rahmen VOR der Massstabskorrektur. Der DOM1-Laser zeigt, dass dieser Rahmen 5,3 % zu gross
    # war (Dachtraufe 37,2 statt 39,26 m, Vordach 16,4 statt 17,3 m, Dachflaeche 169 statt 199,5 m2; Foto-GPS 0,97). Die Ausrichtung ist korrigiert
    # (tools/ausrichtung_massstab_korrigieren.py, Faktor 0,947 um die Turmmitte am Boden). Hier: amtliche LoD2-Teile in den Rohrahmen zurueckrechnen, alles
    # wie gemessen bauen, am Ende den ganzen Koerper mit MK skalieren -> LoD2-Teile bleiben amtlich, Fototeile bekommen den Lasermassstab.
    MK, MC = 0.933, (-2.15, 15.28, 0.0)                    # 0,947 (Laser Traufpixel/Vordach) x 0,985 (Hoehen-Tor: 61 ebene Dachpixel)
    def massstab(k_, f): return k_.translate((-MC[0], -MC[1], -MC[2])).scale((f, f, f)).translate(MC)
    # 15.11.2026 (Nutzerbild 14:36, Koerper stand als glatter Streifen ueber Relief und Wolke hinaus): der LoD2-GRUNDRISS wird MIT skaliert. Im Rohrahmen lag er
    # auf den Wolkenwaenden (+-0,2 m); im Lasermassstab sind die Wolkenwaende aller vier Seiten 0,2-0,6 m schmaler als LoD2 (LoD2 = Sockelumring, Schaft 11,3 m).
    # Waagerecht gilt also Wolke/Foto (Lage-Veto), nur die amtlichen HOEHEN der LoD2-Nebenteile bleiben (z vorab durch MK geteilt).
    koerper = koerper.scale((1.0, 1.0, 1.0 / MK))
    beleg("wand", "Grundriss Schaft = LoD2-Umriss x 0,933", "Wolkenwaende aller vier Seiten im Lasermassstab (tools/..., Stand 15.11.): LoD2 unskaliert 0,2-0,6 m zu breit, skaliert +-0,2 m",
          hinweis="ANNAHME fuer Sued/Ost/West: Wandlage aus der Wolke (nur Nordwand am Foto gepeilt); Anzug/Sockel nicht gebaut")
    N_BELEGE_LOD2 = len(ELEMENTE)
    ZT = 39.26                                # Traufe aussen oben: Ecken A 39,20 / C 39,32 (M-113205-008/-009, nach Lotkorrektur)
    X1, Y0, Y1 = 4.80, 8.20, 22.55            # Traufkante Nord (x) und Ecken Ost/West (y), gleiche Protokolle
    MX = -2.15                                # Dachmitte x = Mitte zwischen Nordwand 3,69 (M-113205-006/-007) und Suedwand LoD2 -8,0
    X0 = 2 * MX - X1                          # ANNAHME: Suedtraufe spiegelbildlich (Turmkopf im SfM nur von Norden gesehen)
    NEIG = 54.4                               # Neigung Nordflaeche: Traufe -> Laternenfuss (-0,96 / 47,30), M-113205-010; Laser DOM1 56,1
    ZF = 47.30                                # Laternenfuss = Oberkante Pyramidenstumpf
    DICKE = 0.25                              # ANNAHME: Traufbrett/Sparrenkopf 0,25 m
    cx, cy = (X0 + X1) / 2, (Y0 + Y1) / 2; hx, hy = (X1 - X0) / 2, (Y1 - Y0) / 2
    zs = ZT + hx * np.tan(np.radians(NEIG)); f = (zs - ZF) / (zs - ZT)       # gedachte Spitze (~49,25 m; Laser max 49,62)
    ecken = lambda h_x, h_y, z: [[cx + a * h_x, cy + b * h_y, z] for a in (-1, 1) for b in (-1, 1)]
    # Dachprofil GESCHWEIFT (15.11.2026, Hoehen-Tor tools/hoehe_gegen_dom1.py: gerade Pyramide lag in der Flaechenmitte +1,34 m ueber dem Laser, an der Traufe richtig).
    # Stuetzpunkte (Abstand von der Dachmitte r, Hoehe z) im KORRIGIERTEN Rahmen: Traufe und Laternenfuss aus Fotos, dazwischen DOM1-Laser (Mittel N/S/W/O):
    PROFIL = [(6.0, 37.5), (5.0, 38.5), (4.0, 40.0), (3.0, 41.5)]            # laser_dom1, hoehe_flaeche; unten flacher (Aufschiebling), oben steiler
    ringe = [(1.0, ZT)] + [(r_ / (hx * MK), z_ / MK) for r_, z_ in PROFIL] + [(f, ZF)]
    dach = M.hull_points(ecken(hx, hy, ZT - DICKE) + ecken(hx, hy, ZT))
    for (f0, z0_), (f1, z1_) in zip(ringe[:-1], ringe[1:]): dach = dach + M.hull_points(ecken(hx * f0, hy * f0, z0_ - DICKE) + ecken(hx * f0, hy * f0, z0_) + ecken(hx * f1, hy * f1, z1_ - DICKE) + ecken(hx * f1, hy * f1, z1_))
    dach = dach + M.hull_points(ecken(hx * 0.9, hy * 0.9, ZT - DICKE) + ecken(hx * f, hy * f, ZF - DICKE))        # Kern unter der Dachhaut (innen voll)
    wand = M.extrude(CrossSection([np.asarray(haupt).tolist()]), ZT)        # ANNAHME: Wand laeuft bis unter die Dachhaut (Untersicht/Holzwerk nicht gemessen)
    beleg("dach", "Zeltdach mit Ueberstand", "Foto-Triangulation Nordseite (foto_mass.py --tri, M-113205-008/-009/-010, Rahmen lotrecht aus Foto-Vertikalen)", traufe=ZT, neigung_grad=NEIG,
          trauflaenge_ost_west=round(Y1 - Y0, 2), ueberstand=round(X1 - 3.63, 2), spitze_gedacht=round(float(zs), 2),
          hinweis="Dachflaeche geschweift: Zwischenpunkte r 3-6 m aus DOM1-Laser (41,5 / 40,0 / 38,5 / 37,5 m); ANNAHME: Sued-, Ost- und Westflaeche wie Nord, Traufdicke 0,25 m")
    beleg("wand", "Hauptteil Wand bis Traufe", "LoD2 DEBW_001000hPLcp GroundSurface 0; Nordwand am Foto bestaetigt (M-113205-006/-007)", hoehe=ZT,
          hinweis="ANNAHME: Wand bis Traufhoehe, Dachuntersicht nicht gemessen")
    # Laterne: nur der Knauf ist gemessen (-1,50 / 15,02 / 54,17, M-113205-005; x entlang der Blickrichtung unsicher) - Form = ANNAHME nach Foto 113205
    lat = M.cylinder(51.3 - (ZF - 0.3), 0.75, 0.75, 8).translate((cx, cy, ZF - 0.3))
    lat = lat + M.cylinder(0.35, 1.05, 0.80, 8).translate((cx, cy, 51.2))                                   # Krempe
    lat = lat + M.sphere(1.0, 24).scale((0.9, 0.9, 1.2)).translate((cx, cy, 52.5))                          # Zwiebelhaube
    lat = lat + M.cylinder(0.6, 0.14, 0.10, 12).translate((cx, cy, 53.5)) + M.sphere(0.22, 16).translate((cx, cy, 54.18))
    lat = lat + M.cylinder(1.0, 0.06, 0.05, 8).translate((cx, cy, 54.3))                                    # Spitze
    beleg("dach", "Laterne mit Zwiebelhaube", "Knauf-Hoehe 54,17 m aus Foto-Triangulation (M-113205-005)", hoehe=55.3,
          hinweis="ANNAHME: Form (geschlossener Achteckschaft statt 4 Pfosten, Krempe, Zwiebel, Spitze 1 m) nach Augenschein Foto 113205, nicht gemessen")
    # Nordwand: LoD2 liegt am Uhrgeschoss bis 0,2 m zu weit aussen (3,92 statt 3,72 bei y 9,2). Am Foto gepeilte Wandecken C' (3,72 / 9,22) und A' (3,54 / 21,38),
    # M-113205-012/-013 -> Wandkoerper an dieser senkrechten Ebene abschneiden (Dach und Laterne bleiben)
    ca, cb = np.array([3.72, 9.22]), np.array([3.54, 21.38]); tn = (cb - ca) / np.linalg.norm(cb - ca); nn = np.array([tn[1], -tn[0]]); nn = nn if nn[0] > 0 else -nn
    # 15.11.2026 (Nutzerbilder 14:39): die Wolke/das Netz stehen 0,15-0,3 m VOR dieser gepeilten Ebene (Peilung +-0,19..0,35 m unsicher; Netzflaeche bei z 29,6: +0,17 m,
    # nach unten zunehmend = Wandanzug 0,6 cm/m). Lage-Veto der Wolke: Wandebene um 0,17 m nach aussen; der Anzug darunter kommt mit dem Relief (trend=True).
    WV = 0.17; ca, cb = ca + WV * nn, cb + WV * nn
    _L = float(np.linalg.norm(cb - ca)); fuell = M.hull_points([[ca[0] + u_ * tn[0] + w_ * nn[0], ca[1] + u_ * tn[1] + w_ * nn[1], z_] for u_ in (0.0, _L) for w_ in (-1.0, 0.0) for z_ in (0.0, ZT)])
    rumpf = (koerper + wand + fuell).trim_by_plane((-nn[0], -nn[1], 0.0), float(-(nn @ ca)))      # Fuellkoerper: Wand reicht ueberall BIS zur Ebene (skaliertes LoD2 lag bis 0,14 m dahinter -> Uhr schwebte)
    beleg("wand", "Nordwand (Ebene)", "Foto-Peilung foto_mass.py --tri2d der Wandecken am Uhrgeschoss (M-113205-012/-013)", x_bei_y9=3.72, x_bei_y21=3.54,
          hinweis="ANNAHME: Wand ueber die ganze Hoehe in dieser Ebene (Anzug/Sockel noch nicht gemessen)")
    # Relief-Einsatz Nordwand (Nutzerentscheidung 15.11.2026): Hoehenbild aus dem OpenMVS-Netz als Platte vor der gepeilten Wandebene; Wand, Kanten und
    # Oeffnungen bleiben Sache des Generators. Erzeugt mit tools/relief_einsatz.py (modelle/schwab_v3/relief/nord.npz), geprueft mit tools/relief_test.py.
    from relief_einsatz import koerper as relief_koerper
    rel_n = os.path.join(HERE, "schwab_v3", "relief", "nord.npz")
    if os.path.exists(rel_n.replace(".npz", "_voll.npz")):          # 15.11.2026 Nutzer: "Rest der Steine notfalls generieren" - Loecher des Scan-Reliefs mit generierten Quadern gefuellt (tools/steine_generieren.py)
        rel_n = rel_n.replace(".npz", "_voll.npz"); beleg("wand", "Generierte Quader Nord (Loecher des Scan-Reliefs, Sockelstreifen z 0-0,6 m)", "ANNAHME: tools/steine_generieren.py - Verband gewuerfelt, Schichthoehe und Hub aus dem echten Relief daneben", anteil=float(np.load(rel_n)["generiert_anteil"]), hinweis="ERFUNDEN, kein Mass: einzelne Steine entsprechen nicht dem Original")
    if os.path.exists(rel_n.replace("_voll.npz", "_eben.npz")) and rel_n.endswith("_voll.npz"): rel_n = rel_n.replace("_voll.npz", "_eben.npz")      # 16.11.2026 Nutzer (Beulen neben der Uhr): glatt behauene Eckquader ueber dem Gesims eben, Kontur aus der Fotofarbe (tools/relief_quader_eben.py); Fugen fehlen
    _fo_nord = os.path.join(HERE, "schwab_v3", "relief", "nord_foto.npz"); _ft_nord = [(0.0, 12.2, 14.8, 27.8)] if os.path.exists(_fo_nord) and os.environ.get("OHNE_FOTOSTEINE") != "1" else []      # 16.11.2026 Nutzer: 'Steine nach oben noch nicht korrekt' -> Quader mit Fugen aus dem feinen Fassadenbild (tools/steine_aus_foto.py)
    if os.path.exists(rel_n) and os.environ.get("OHNE_RELIEF") != "1":
        rel_nm = os.path.join(HERE, "schwab_v3", "relief", "nord_misch.npz"); fein_n = os.path.exists(rel_nm) and os.environ.get("OHNE_FEIN") != "1"   # 15.11. spaet: lokale Feinrechnung der Tiefe (tools/tiefe_lokal.py -> relief_mischen.py), Nordwand unten 2 cm statt 5 cm
        rumpf = rumpf + relief_koerper(rel_n, tiefe=0.12 + WV, trend=True, versatz=0.0, null_felder=[(2.6, 5.4, 23.9, 27.1), (6.9, 9.7, 23.9, 27.1), (1.6, 11.1, 9.7, 21.1)], tief_felder=([(0.0, 12.2, 0.0, 10.4)] if fein_n else []) + _ft_nord)
        if _ft_nord: rumpf = rumpf + relief_koerper(_fo_nord, tiefe=0.12 + WV, trend=True, rand_auslauf=False, null_felder=[(2.6, 5.4, 23.9, 27.1), (6.9, 9.7, 23.9, 27.1), (1.6, 11.1, 9.7, 21.1)]); beleg("wand", "Quader mit Fugen nord (mittlere Zone)", "feines Fassadenbild 1 cm (fassade_fein.py) -> tools/steine_aus_foto.py: Lagerfugen aus dem Zeilenprofil, Stossfugen je Schicht", steine=int(np.load(_fo_nord)["steine"]), hinweis="Fugenlage aus dem Foto (Schichtmodell: nicht jede einzelne Fuge stimmt), Fugentiefe 3 cm und ebene Steinflaeche ANNAHME; Bossen fehlen")
        if fein_n:
            rumpf = rumpf + relief_koerper(rel_nm, tiefe=0.12 + WV, trend=True, null_felder=[(1.6, 11.1, 9.7, 21.1)], rand_auslauf=False)
            beleg("wand", "Feines Relief Nordwand z 0-10,5 m (2 cm)", "lokale Feinrechnung: 13 Nahfotos in 3200 px, COLMAP PatchMatch nur fuer dieses Feld (tools/tiefe_lokal.py), gemischt mit dem groben Relief (tools/relief_mischen.py)",
                  fein_anteil=float(np.load(rel_nm)["fein"].mean()), hinweis="Scan-Relief, kein Mass; wo die Feinrechnung keine Daten hat (56 %), steht das grobe bzw. generierte Relief")   # Fensterfelder baut der Generator scharf (unten)
        beleg("wand", "Relief Nordwand z 0,6-29,6 m", "OpenMVS-Netz der Fotowolke (rc-park_daten/schwab_v3/openmvs/mesh.ply), Hoehenbild 5 cm, geklemmt -0,10..+0,15 m; Fugen gegen 3 Fotos korreliert (audit/relief_test.json)",
              hinweis="Scan-Relief, kein Mass: Torbogen, Holzgalerie und Vordach sind darin Loecher (glatte Wand) und fehlen noch; Wandanzug (~0,6 cm/m) abgezogen")
    # Tordurchfahrt Nord als ECHTE Oeffnung aus Fotokanten (Nutzer 13:30: Relief mit dem Generator schaerfen). Masse M-113602-001..-006 auf der Sockelebene.
    def spitzbogen(halb, kaempfer, scheitel, unten=-0.6, nseg=24):
        h = scheitel - kaempfer; r = (halb * halb + h * h) / (2 * halb); w0 = np.arcsin(h / r)          # Kreisbogen: Mitte auf der Kaempferlinie, r - halb jenseits der Achse
        re = [[-(r - halb) + r * np.cos(w), kaempfer + r * np.sin(w)] for w in np.linspace(0, w0, nseg)]  # rechter Bogen vom Kaempfer zum Scheitel
        li = [[-x, z] for x, z in re[::-1]]
        return CrossSection([[[-halb, unten], [halb, unten]] + re[:-1] + li])
    T_UM, T_PF = 6.135, 0.05                                   # Tormitte ab Wandecke Ost (u), Pflasterhoehe
    ac = ca + T_UM * tn; M_tor = [[tn[0], 0.0, nn[0], ac[0]], [tn[1], 0.0, nn[1], ac[1]], [0.0, 1.0, 0.0, 0.0]]     # lokal (quer, hoch, tief nach aussen) -> Welt
    innen = M.extrude(spitzbogen(4.63 / 2, T_PF + 4.25, T_PF + 6.88), 16.0).translate((0, 0, -15.0)).transform(M_tor)   # ANNAHME: Durchfahrt mit gleichem Querschnitt bis zur Suedseite
    aussen = M.extrude(spitzbogen(5.47 / 2, T_PF + 4.25, T_PF + 7.20, unten=T_PF + 4.25), 1.0).translate((0, 0, -0.08)).transform(M_tor)  # Bogenring: ANNAHME Stufe 0,25 m statt Fase
    rumpf = rumpf - innen - aussen
    beleg("wand", "Tordurchfahrt Nord (Spitzbogen)", "foto_mass.py auf der Sockelebene, Frontalfoto 113602 + Schraegfoto 113310 (M-113602-001..-006, M-113310-001)", lichte_breite=4.63,
          kaempfer=4.25, lichte_hoehe=6.88, scheitel_aussen=7.20, hinweis="ANNAHME: Kreisboegen; Bogenring als Stufe 0,25 m; Durchfahrt mit gleichem Querschnitt bis Sued (Suedbogen nicht gemessen); Kaempfersteine fehlen")
    # Zwei Rundbogenfenster Nord (Blendnische mit Sohlbank, darin schmale Oeffnung mit Laden), Masse M-113029-001..-007 (Foto 113029, Wandebene)
    def rundbogen(breite, unten, scheitel, nseg=20):
        r = breite / 2; return CrossSection([[[-r, unten], [r, unten]] + [[r * np.cos(w), scheitel - r + r * np.sin(w)] for w in np.linspace(0, np.pi, nseg)]])
    M_w = [[tn[0], 0.0, nn[0], ca[0]], [tn[1], 0.0, nn[1], ca[1]], [0.0, 1.0, 0.0, 0.0]]            # lokal (u ab Wandecke Ost, z, nach aussen) -> Welt
    F_SOHL, F_NB, F_NH, F_OB, F_OH, F_NT, F_OT = 24.21, 2.09, 2.52, 0.68, 1.89, 0.15, 0.45          # Sohlbank z; Nische Breite/Hoehe; Oeffnung Breite/Hoehe; Tiefen = ANNAHME
    for um in (2.96 + F_NB / 2, 7.25 + F_NB / 2):
        nische = M.extrude(rundbogen(F_NB, F_SOHL, F_SOHL + F_NH), F_NT + 0.6).translate((um, 0, -F_NT)).transform(M_w)
        oeffn = M.extrude(rundbogen(F_OB, F_SOHL, F_SOHL + F_OH), F_OT + 0.6).translate((um, 0, -F_OT)).transform(M_w)
        bank = M.cube((F_NB + 0.1, 0.10, 0.12 + F_NT)).translate((um - F_NB / 2 - 0.05, F_SOHL - 0.10, -F_NT)).transform(M_w)   # Sohlbank: ANNAHME 10 cm stark, 12 cm Ausladung
        rumpf = rumpf - nische - oeffn + bank
    beleg("wand", "2 Rundbogenfenster Nord (Blendnische + Oeffnung + Sohlbank)", "foto_mass.py auf der Wandebene, Foto 113029 (M-113029-001..-007)", nische_breite=F_NB, nische_hoehe=F_NH,
          oeffnung_breite=F_OB, oeffnung_hoehe=F_OH, sohlbank_z=F_SOHL, hinweis="ANNAHME: Nischentiefe 0,15 m, Laden 0,45 m hinter der Wand, Sohlbank 10 x 12 cm; rechtes Fenster = Masse des linken, nur Lage gemessen")
    # Holzgalerie und geschweiftes Vordach Nord aus Foto-Triangulation (M-113231-001..-004, M-113128-001..-004); lokal (u, z, w nach aussen) ueber M_w
    def kasten(u0, u1, z0, z1, w0, w1): return M.cube((u1 - u0, z1 - z0, w1 - w0)).translate((u0, z0, w0)).transform(M_w)
    def huelle(pts): return M.hull_points([[ca[0] + u * tn[0] + w * nn[0], ca[1] + u * tn[1] + w * nn[1], z] for u, z, w in pts])
    G_U0, G_U1, G_W, G_ZU, G_ZO = 1.91, 10.55, 1.55, 10.95, 12.24          # Enden (u), Ausladung, Schwelle unten, Holm oben
    gal = kasten(G_U0, G_U1, G_ZU, G_ZU + 0.35, -0.05, G_W)                 # Schwelle + Boden (ANNAHME: geschlossene Platte 0,35 m)
    gal = gal + kasten(G_U0, G_U1, G_ZU, G_ZO, G_W - 0.15, G_W)             # Bruestung vorn (ANNAHME: geschlossen statt Andreaskreuze mit Gitter)
    gal = gal + kasten(G_U0, G_U0 + 0.15, G_ZU, G_ZO, -0.05, G_W) + kasten(G_U1 - 0.15, G_U1, G_ZU, G_ZO, -0.05, G_W)
    V_ZT, V_W, V_U0, V_U1, V_ZO, V_O0, V_O1 = 17.25, 1.65, 1.83, 10.83, 20.82, 3.28, 9.31    # Traufe z, Ausladung, Traufe u, Anschluss z, Anschluss u
    for up in (G_U0 + 0.11, (G_U0 + G_U1) / 2, G_U1 - 0.11):                # 3 Pfosten vorn (Lage Enden/Mitte nach Foto 113231, Querschnitt ANNAHME 0,22 m)
        gal = gal + kasten(up - 0.11, up + 0.11, G_ZO, V_ZT + 0.1, G_W - 0.22, G_W)
    for us in np.linspace(G_U0 + 0.3, G_U1 - 0.3, 6):                       # 6 Kopfstreben unter dem Boden (ANNAHME: Zahl/Lage nach Foto, Wandfuss z 9,9)
        gal = gal + huelle([(us - 0.1, G_ZU, G_W - 0.3), (us + 0.1, G_ZU, G_W - 0.3), (us - 0.1, G_ZU, G_W - 0.05), (us + 0.1, G_ZU, G_W - 0.05),
                            (us - 0.1, 9.9, -0.05), (us + 0.1, 9.9, -0.05), (us - 0.1, 10.25, -0.05), (us + 0.1, 10.25, -0.05)])
    V_MZ, V_MW = 18.9, 0.55; fm = V_MW / V_W; V_M0, V_M1 = V_O0 + (V_U0 - V_O0) * 0.37, V_O1 + (V_U1 - V_O1) * 0.37    # Schweifung: ANNAHME Zwischenschnitt nach Umriss im Foto 113128
    d_ = 0.15
    vd = huelle([(V_O0, V_ZO, -0.05), (V_O1, V_ZO, -0.05), (V_O0, V_ZO - d_, -0.05), (V_O1, V_ZO - d_, -0.05), (V_M0, V_MZ, V_MW), (V_M1, V_MZ, V_MW), (V_M0, V_MZ - d_, V_MW), (V_M1, V_MZ - d_, V_MW)])
    vd = vd + huelle([(V_M0, V_MZ, V_MW), (V_M1, V_MZ, V_MW), (V_M0, V_MZ - d_, V_MW), (V_M1, V_MZ - d_, V_MW), (V_U0, V_ZT + d_, V_W), (V_U1, V_ZT + d_, V_W), (V_U0, V_ZT, V_W), (V_U1, V_ZT, V_W)])
    rumpf = rumpf + gal + vd
    beleg("wand", "Holzgalerie Nord (Boden, Bruestung, 3 Pfosten, 6 Streben)", "Foto-Triangulation foto_mass.py --tri (M-113231-001..-004)", breite=round(G_U1 - G_U0, 2), ausladung=G_W, schwelle_unten=G_ZU, holm_oben=G_ZO,
          hinweis="ANNAHME: Bruestung geschlossen (statt Andreaskreuze), Bodenplatte 0,35 m, Pfosten 0,22 m, Streben 6 Stueck bis z 9,9")
    beleg("dach", "Vordach Nord (geschweiftes Pultdach)", "Foto-Triangulation foto_mass.py --tri (M-113128-001..-004)", traufe_z=V_ZT, ausladung=V_W, traufbreite=round(V_U1 - V_U0, 2), anschluss_z=V_ZO, anschlussbreite=round(V_O1 - V_O0, 2),
          hinweis="ANNAHME: Schweifung aus einem Zwischenschnitt (z 18,9 / 0,55 m), Dachhaut 0,15 m")
    # Uhr Nord: Zifferblatt als flache Scheibe mit Ziffernring (Masse M-113029-008..-012, M-113205-014/-015), zwei Balkenkoepfe darueber
    U_UM, U_ZM, U_D, U_DI = 6.14, 33.49, 5.36, 3.52
    ring = M.cylinder(0.10 + 0.05, U_D / 2, U_D / 2, 64) - M.cylinder(0.3, U_DI / 2, U_DI / 2, 64).translate((0, 0, 0.11))     # Ring 10 cm, Innenfeld 6 cm vor der Wand: ANNAHME
    rumpf = rumpf + ring.translate((U_UM, U_ZM, -0.05)).transform(M_w)
    from bauteile import Wand as _Wand
    rumpf = rumpf + _Wand(ca, cb, aussen=ca + 5.0 * nn).zifferblatt(U_UM, U_ZM, U_D, U_DI, zeit=(12, 30), k=1.0 / 0.933)      # 15.11. abends (Nutzer: "Uhr noch nicht richtig"): Wulste, Ziffern, Zeiger; Zeit wie Foto 113029 (ANNAHME)
    for ub in (3.05, 9.10): rumpf = rumpf + kasten(ub - 0.15, ub + 0.15, 35.55, 36.0, -0.05, 0.25)            # Balkenkoepfe: Lage aus dem entzerrten Foto 113029, Groesse ANNAHME
    beleg("wand", "Uhr Nord (Zifferblatt 5,36 m, Innenfeld 3,52 m)", "foto_mass.py auf der Wandebene, Fotos 113029 und 113205", durchmesser=U_D, mitte_u=U_UM, mitte_z=U_ZM,
          hinweis="ANNAHME: Ring 10 cm / Innenfeld 6 cm vor der Wand; Ziffern, Zeiger, Sonne/Mond nicht modelliert; 2 Balkenkoepfe nach Augenschein")
    # Suedwand (15.11.2026, Nutzerbilder 14:47/15:35 "Modell zu gross"): im neuen SfM (Eckpaare) liegt die Suedwand bei x -7,10 (korrigierter Rahmen), der skalierte
    # LoD2-Umriss bei -7,6. Mit den neuen Kameras stimmt die Suedfassade mit der Nordseite ueberein (Uhrmitte 31,1 / 31,25 m, Uhr 4,9 / 5,0 m, Traufe ~37 m).
    # Lage-Veto: Koerper an x = -7,10 abschneiden (im Rohrahmen umgerechnet). ANNAHME: Wand senkrecht und parallel zur y-Achse; am Foto noch zu peilen.
    S_A, S_B = np.array([-7.035, 9.40]), np.array([-7.374, 20.90])          # Suedwand im KORRIGIERTEN Rahmen: Gerade durch 7 828 Wandpunkte des neuen SfM (Rest 2 cm), leicht schraeg
    roh = lambda p_: np.array(MC[:2]) + (np.asarray(p_) - np.array(MC[:2])) / MK; sa_, sb_ = roh(S_A), roh(S_B); st_ = (sb_ - sa_) / np.linalg.norm(sb_ - sa_); sn_ = np.array([st_[1], -st_[0]]); sn_ = sn_ if sn_[0] > 0 else -sn_
    rumpf = rumpf.trim_by_plane((float(sn_[0]), float(sn_[1]), 0.0), float(sn_ @ sa_)); X_SUED = float(sa_[0])
    beleg("wand", "Suedwand (Ebene)", "SfM-Neuaufbau mit Eckpaaren (sfm_neu), Wandpunkte z 8-33 m; Gegenprobe Uhr/Traufe im entzerrten Suedfoto 127", x=round(X_SUED, 2),
          hinweis="Lage-Veto der neuen SfM-Punkte, nicht am Foto gepeilt; Knauf-Tor Nord-Sued noch 0,9 m")
    ELEMENTE[:] = [e_ for e_ in ELEMENTE if e_["element"] != "Laterne mit Zwiebelhaube"]      # alte Laterne (Form ANNAHME) entfaellt, neue unten aus Fotomassen
    ELEMENTE[:] = [e_ for e_ in ELEMENTE if e_["element"] != "Zeltdach mit Ueberstand"]       # altes Dach (Sued/Ost/West gespiegelt angenommen) entfaellt, neues unten aus VIER gemessenen Traufecken
    koerper = massstab(rumpf, MK); N_BELEGE_ROH = len(ELEMENTE)
    # ---- DACH (15.11.2026) im korrigierten Rahmen: vier Traufecken trianguliert (Nord: M-113205-016/-025 + Ecke A; Sued: M-commons127-011/-012), Achse = Knauf ----
    D_E = [(4.34, 8.62, 36.79), (4.27, 22.06, 36.69), (-8.05, 21.76, 36.54), (-8.00, 8.77, 36.47)]      # NO, NW, SW, SO: Dachkante aussen oben (m)
    D_A = (-1.86, 15.11)                                                                              # Achse: x = Mitte der Traufen Nord/Sued (-1,86) = Knauf x (-1,85); y = Knauf (15,11)
    D_ZE = sum(e_[2] for e_ in D_E) / 4; D_RE = 6.38                                                    # mittlere Traufhoehe 36,62 (Laser 36,6); mittlerer Achsabstand der Traufkanten
    # 16.11.2026 (Nutzer: "Die Dachform passt noch nicht ganz"): waagerechtes Fernfoto vom Schlossberg (110756, 320 m, 26 px/m; Gegenprobe Uhrmitte-Traufe 5,41 m = Modell):
    # der Grat ist GERADE vom Trauf-Eck (z 36,6) bis zur Dachspitze am Laternenfuss z 45,2 (M-110756-001/-002: Steigung 1,31-1,38 durchgehend). Vorher geschweiftes Profil
    # mit Stumpf bei 44,1 (aus einem steilen Nahfoto); die Laserpunkte (r 6/5/4/3 m -> 37,5/38,5/40,0/41,5) liegen auf derselben Geraden (+-0,4 m).
    D_PROF = [(1.0, None), (0.05, 45.2)]                                   # (Anteil des Achsabstands, z)
    def ring(f_, z_, dz_=0.0): return [[D_A[0] + f_ * (e_[0] - D_A[0]), D_A[1] + f_ * (e_[1] - D_A[1]), (e_[2] if z_ is None else z_) - dz_] for e_ in D_E]
    dach = M.hull_points(ring(1.0, None) + ring(1.0, None, 0.23))
    for (f0_, z0_), (f1_, z1_) in zip(D_PROF[:-1], D_PROF[1:]): dach = dach + M.hull_points(ring(f0_, z0_) + ring(f0_, z0_, 0.23) + ring(f1_, z1_) + ring(f1_, z1_, 0.23))
    dach = dach + M.hull_points(ring(0.9, D_ZE - 0.3) + ring(0.196, 43.9))                                # Kern unter der Dachhaut
    koerper = koerper + dach
    beleg("dach", "Zeltdach geschweift mit Ueberstand, vier gemessene Traufecken", "Foto-Triangulation: Nordecken aus 6 Nordfotos, Suedecken aus 3 Suedfotos (Kameras SfM-Neuaufbau); Flaechenprofil DOM1-Laser",
          traufe_nord=36.74, traufe_sued=36.5, laenge_nord_sued=12.35, breite_nord=13.44, breite_sued=12.99, ueberstand_nord=0.9, ueberstand_sued=0.83,
          hinweis="Suedecken auf ~2-3 % (Knauf-Tor 0,9 m); Traufdicke 0,23 m ANNAHME; Aufschiebling aus dem Laserprofil")
    # ---- LATERNE (15.11.2026) im korrigierten Rahmen aus Fotomassen M-113205-017..-024 (Foto 113205, Ebene durch die Laternenachse) + Knauf-Triangulation ----
    L_X, L_Y, L_ZF = -1.86, 15.11, 45.2                       # Achse: y aus dem Knauf (Nordfotos), x = Mitte der gemessenen Traufen Nord/Sued = Knauf x aus der Triangulation; Fuss = Oberkante Dachstumpf (47,28 roh x 0,933)
    lat = M.cylinder(0.4, 1.35, 1.25, 4).rotate((0, 0, 0)).translate((L_X, L_Y, L_ZF - 0.25))           # Sockelplatte auf dem Dachstumpf (ANNAHME)
    for dx_, dy_ in ((0.8, 0), (-0.8, 0), (0, 0.8), (0, -0.8)):                                            # 4 Pfosten an den Hauptachsen: Aussenabstand 1,78 m (M-113205-024), Staerke ANNAHME 0,18 m
        lat = lat + M.cube((0.18, 0.18, 47.0 - L_ZF + 0.1)).translate((L_X + dx_ - 0.09, L_Y + dy_ - 0.09, L_ZF))
    lat = lat + M.cylinder(0.12, 1.425, 1.425, 4).translate((L_X, L_Y, 46.93)) + M.cylinder(0.22, 1.425, 1.0, 4).translate((L_X, L_Y, 47.05))                              # Krempe: 4 Spitzen an den Hauptachsen, Spitze zu Spitze 2,85 m bei z 47,0 (M-113205-023)
    profil = [(1.0, 47.2), (1.28, 47.6), (1.32, 47.95), (1.22, 48.6), (0.88, 49.3), (0.45, 49.85), (0.16, 50.17)]   # Zwiebelhaube: groesste Breite 2,64 m bei z 47,95 (M-113205-022), Hals z 50,17 (M-113205-019); Zwischenpunkte nach Augenschein
    for (r0_, z0_), (r1_, z1_) in zip(profil[:-1], profil[1:]): lat = lat + M.cylinder(z1_ - z0_, r0_, r1_, 32).translate((L_X, L_Y, z0_))
    lat = lat + M.cylinder(0.5, 0.12, 0.08, 16).translate((L_X, L_Y, 50.15)) + M.sphere(0.17, 20).translate((L_X, L_Y, 50.77)) + M.cylinder(0.9, 0.05, 0.02, 8).translate((L_X, L_Y, 50.86))   # Hals, Knauf z 50,77, Spitze bis 51,76
    koerper = koerper + lat
    beleg("dach", "Laterne: 4 Pfosten, Krempe, Zwiebelhaube, Knauf, Spitze", "foto_mass.py Foto 113205 auf der Ebene durch die Laternenachse (M-113205-017..-024); Knauf zusaetzlich aus 5 Nordfotos trianguliert (50,73 m)",
          krempe_z=47.0, krempe_breite=2.85, haube_breite=2.64, haube_breite_z=47.95, hals_z=50.17, knauf_z=50.77, spitze_z=51.76,
          hinweis="ANNAHME: Pfostenstaerke, Sockelplatte, Zwischenpunkte des Haubenprofils, Achse x (Blickrichtung); Hoehen unter der Haube (Fuss) aus der Triangulation")
    for e_ in ELEMENTE[N_BELEGE_LOD2:N_BELEGE_ROH]:                    # Masse der Belege in den korrigierten Rahmen: Laengen/Hoehen x MK, Winkel bleiben, x-Lagen um den Drehpunkt
        for q_, v_ in list(e_.items()):
            if isinstance(v_, (int, float)) and not isinstance(v_, bool) and q_ != "neigung_grad": e_[q_] = round(MC[0] + MK * (v_ - MC[0]), 2) if q_.startswith("x_bei") else round(v_ * MK, 2)
        e_["hinweis"] = (e_.get("hinweis", "") + " | Masse mit Lasermassstab 0,933 (DOM1); Rohmasse in den Protokollen M-* gelten im Rahmen vor der Korrektur").strip(" |")
    # ---- SUEDFASSADE (15.11.2026) im KORRIGIERTEN Rahmen, nach dem Skalieren: Masse M-commons127-002..-010, M-commons217-001..-003 (Kameras aus dem SfM-Neuaufbau) ----
    from bauteile import Wand, spitzbogen as b_spitz, rundbogen as b_rund
    WS = Wand(S_A, S_B, aussen=(-30.0, 15.0)); T_U = 5.76
    rel_s = os.path.join(HERE, "schwab_v3", "relief", "sued.npz")              # Relief Sued aus dem NEUEN OpenMVS-Netz (sfm_neu), korrigierter Rahmen; Bauteilfelder ausgeblendet
    if os.path.exists(rel_s.replace(".npz", "_voll.npz")):          # 15.11.2026 Nutzer: "Rest der Steine notfalls generieren" - Loecher des Scan-Reliefs mit generierten Quadern gefuellt (tools/steine_generieren.py)
        rel_s = rel_s.replace(".npz", "_voll.npz"); beleg("wand", "Generierte Quader Sued (Loecher des Scan-Reliefs, Sockelstreifen z 0-0,6 m)", "ANNAHME: tools/steine_generieren.py - Verband gewuerfelt, Schichthoehe und Hub aus dem echten Relief daneben", anteil=float(np.load(rel_s)["generiert_anteil"]), hinweis="ERFUNDEN, kein Mass: einzelne Steine entsprechen nicht dem Original")
    if os.path.exists(rel_s.replace("_voll.npz", "_eben.npz")) and rel_s.endswith("_voll.npz"): rel_s = rel_s.replace("_voll.npz", "_eben.npz")      # 16.11.2026 Nutzer (Beulen neben der Uhr): glatt behauene Eckquader ueber dem Gesims eben, Kontur aus der Fotofarbe (tools/relief_quader_eben.py); Fugen fehlen
    _fo_sued = os.path.join(HERE, "schwab_v3", "relief", "sued_foto.npz"); _ft_sued = [(0.0, 11.6, 9.9, 26.0)] if os.path.exists(_fo_sued) and os.environ.get("OHNE_FOTOSTEINE") != "1" else []      # 16.11.2026 Nutzer: 'Steine nach oben noch nicht korrekt' -> Quader mit Fugen aus dem feinen Fassadenbild (tools/steine_aus_foto.py)
    if os.path.exists(rel_s) and os.environ.get("OHNE_RELIEF") != "1":
        _fm = os.path.join(HERE, "schwab_v3", "relief", "sued_misch.npz"); _fein = os.path.exists(_fm) and os.environ.get("OHNE_FEIN") != "1"      # lokale Feinrechnung (tiefe_lokal.py, 4000 px) + relief_mischen.py, 2 cm
        koerper = koerper + relief_koerper(rel_s, tiefe=0.30, trend=True, null_felder=[(3.0, 8.4, 28.2, 33.75), (5.1, 6.4, 22.0, 23.95), (0.0, 11.5, 25.85, 26.95), (2.4, 7.2, 18.1, 18.5)], tief_felder=([(0.0, 11.6, 0.0, 9.9)] if _fein else []) + _ft_sued)
        if _ft_sued: koerper = koerper + relief_koerper(_fo_sued, tiefe=0.30, trend=True, rand_auslauf=False, null_felder=[(5.1, 6.4, 22.0, 23.95), (0.0, 11.5, 25.85, 26.95), (2.4, 7.2, 18.1, 18.5)]); beleg("wand", "Quader mit Fugen sued (mittlere Zone)", "feines Fassadenbild 1 cm (fassade_fein.py) -> tools/steine_aus_foto.py: Lagerfugen aus dem Zeilenprofil, Stossfugen je Schicht", steine=int(np.load(_fo_sued)["steine"]), hinweis="Fugenlage aus dem Foto (Schichtmodell: nicht jede einzelne Fuge stimmt), Fugentiefe 3 cm und ebene Steinflaeche ANNAHME; Bossen fehlen")
        if _fein:
            koerper = koerper + relief_koerper(_fm, tiefe=0.30, trend=True, rand_auslauf=False)
            beleg("wand", "Feines Relief Suedwand unten (2 cm)", "lokale Feinrechnung: 14 Fotos in 4000 px nur fuer dieses Feld (tools/tiefe_lokal.py), gemischt mit dem groben Relief (tools/relief_mischen.py)", fein_anteil=float(np.load(_fm)["fein"].mean()), hinweis="Scan-Relief, kein Mass; ohne Feindaten steht das grobe bzw. generierte Relief")
        beleg("wand", "Relief Suedwand z 0,6-34 m", "OpenMVS-Netz der neuen dichten Wolke (sfm_neu/openmvs/mesh.ply), Hoehenbild 5 cm, geklemmt -0,10..+0,15 m, Loecher 8 %", hinweis="Scan-Relief, kein Mass; Uhr-, Fenster-, Gesims- und Verdachungsfeld ausgeblendet")
    koerper = koerper + WS.kasten(T_U - 2.7, T_U + 2.7, 0.0, 6.9, -1.0, 0.0)                     # Torwand Sued: ANNAHME 1 m stark; der Suedbogen ist niedriger als die Durchfahrt (Nord 6,42 m)
    koerper = koerper - WS.prisma(b_spitz(4.49 / 2, 3.86, 5.85), u=T_U, w0=-1.3, w1=0.6)
    koerper = koerper - WS.prisma(b_rund(0.92, 22.26, 23.66), u=5.745, w0=-0.45, w1=0.6)        # Fenster: Tiefe ANNAHME 0,45 m; Steingewaende 2,02 m breit ist buendig (Farbe)
    koerper = koerper + WS.scheibe(5.71, 30.97, 4.95, -0.05, 0.10) - WS.scheibe(5.71, 30.97, 3.16, 0.06, 0.4)   # Uhr: Ring 10 cm, Innenfeld 6 cm vor der Wand (ANNAHME wie Nord)
    koerper = koerper + WS.zifferblatt(5.71, 30.97, 4.95, 3.16, zeit=(2, 5))                     # Wulste, 12 roemische Ziffern, Zeiger mit Sonne/Mond (Ablesung entzerrtes Foto commons 127; Zeit und Relieftiefen ANNAHME)
    for ub in (8.52, 2.97): koerper = koerper + WS.kasten(ub - 0.15, ub + 0.15, 32.95, 33.5, -0.05, 0.25)       # Balkenkoepfe: Lage aus dem entzerrten Foto 127, Groesse ANNAHME
    koerper = koerper + WS.kasten(0.0, WS.laenge, 26.0, 26.53, -0.05, 0.10)                      # Gesims: Ausladung ANNAHME 10 cm
    koerper = koerper + WS.kasten(2.57, 7.0, 18.22, 18.38, -0.05, 0.15)                          # Verdachung ueber der Inschrift (Georgsbild darunter ist flach): Staerke/Ausladung ANNAHME
    beleg("wand", "Suedfassade: Torbogen, Fenster, Uhr, Gesims, Verdachung", "foto_mass.py auf der Suedwandebene, Fotos commons 127 und 217 (M-commons127-002..-010, M-commons217-001..-003)", tor_breite=4.49, tor_scheitel=5.85,
          tor_kaempfer=3.86, uhr_durchmesser=4.95, uhr_mitte_z=30.97, fenster_breite=0.92, fenster_hoehe=1.41, gesims_z=26.53,
          hinweis="ANNAHME: Tiefen/Ausladungen, Torwand 1 m, Bogen aus Kreisboegen; Georgsbild, Eckquader und Bruchstein fehlen (Relief erst nach neuer dichter Wolke); Knauf-Tor Nord-Sued 0,9 m -> Masse auf ~2-3 %")
    # ---- WESTFASSADE (15.11.2026): Fenster auf der Mittelachse, Masse M-114039-001..-006 (Foto 114039, Kameras aus dem SfM-Neuaufbau); Wandebene aus den neuen SfM-Punkten ----
    WW = Wand((-7.37, 20.46), (3.30, 20.96), aussen=(-2.0, 40.0))               # Westwand: Ausgleichsebene des neuen Netzes (erste Annahme 20,85..21,00 lag am Suedende 0,39 m zu weit aussen; passt zum skalierten LoD2)
    rel_w = os.path.join(HERE, "schwab_v3", "relief", "west.npz")
    if os.path.exists(rel_w.replace(".npz", "_voll.npz")):          # 15.11.2026 Nutzer: "Rest der Steine notfalls generieren" - Loecher des Scan-Reliefs mit generierten Quadern gefuellt (tools/steine_generieren.py)
        rel_w = rel_w.replace(".npz", "_voll.npz"); beleg("wand", "Generierte Quader West (Loecher des Scan-Reliefs, Sockelstreifen z 0-0,6 m)", "ANNAHME: tools/steine_generieren.py - Verband gewuerfelt, Schichthoehe und Hub aus dem echten Relief daneben", anteil=float(np.load(rel_w)["generiert_anteil"]), hinweis="ERFUNDEN, kein Mass: einzelne Steine entsprechen nicht dem Original")
    if os.path.exists(rel_w.replace("_voll.npz", "_eben.npz")) and rel_w.endswith("_voll.npz"): rel_w = rel_w.replace("_voll.npz", "_eben.npz")      # 16.11.2026 Nutzer (Beulen neben der Uhr): glatt behauene Eckquader ueber dem Gesims eben, Kontur aus der Fotofarbe (tools/relief_quader_eben.py); Fugen fehlen
    _fo_west = os.path.join(HERE, "schwab_v3", "relief", "west_foto.npz"); _ft_west = [(0.0, 8.5, 9.4, 26.0)] if os.path.exists(_fo_west) and os.environ.get("OHNE_FOTOSTEINE") != "1" else []      # 16.11.2026 Nutzer: 'Steine nach oben noch nicht korrekt' -> Quader mit Fugen aus dem feinen Fassadenbild (tools/steine_aus_foto.py)
    if os.path.exists(rel_w) and os.environ.get("OHNE_RELIEF") != "1":
        _fm = os.path.join(HERE, "schwab_v3", "relief", "west_misch.npz"); _fein = os.path.exists(_fm) and os.environ.get("OHNE_FEIN") != "1"      # lokale Feinrechnung (tiefe_lokal.py, 4000 px) + relief_mischen.py, 2 cm
        koerper = koerper + relief_koerper(rel_w, tiefe=0.45, trend=True, null_felder=[(4.8, 6.0, 21.5, 23.7), (0.0, 8.4, 25.85, 26.95)], tief_felder=([(0.0, 8.5, 0.0, 9.4)] if _fein else []) + _ft_west)
        if _ft_west: koerper = koerper + relief_koerper(_fo_west, tiefe=0.45, trend=True, rand_auslauf=False, null_felder=[(4.8, 6.0, 21.5, 23.7), (0.0, 8.4, 25.85, 26.95)]); beleg("wand", "Quader mit Fugen west (mittlere Zone)", "feines Fassadenbild 1 cm (fassade_fein.py) -> tools/steine_aus_foto.py: Lagerfugen aus dem Zeilenprofil, Stossfugen je Schicht", steine=int(np.load(_fo_west)["steine"]), hinweis="Fugenlage aus dem Foto (Schichtmodell: nicht jede einzelne Fuge stimmt), Fugentiefe 3 cm und ebene Steinflaeche ANNAHME; Bossen fehlen")
        if _fein:
            koerper = koerper + relief_koerper(_fm, tiefe=0.45, trend=True, rand_auslauf=False)
            beleg("wand", "Feines Relief Westwand unten (2 cm)", "lokale Feinrechnung: 14 Fotos in 4000 px nur fuer dieses Feld (tools/tiefe_lokal.py), gemischt mit dem groben Relief (tools/relief_mischen.py)", fein_anteil=float(np.load(_fm)["fein"].mean()), hinweis="Scan-Relief, kein Mass; ohne Feindaten steht das grobe bzw. generierte Relief")
        beleg("wand", "Relief Westwand z 0,6-34 m (ohne Treppenturm)", "OpenMVS-Netz der neuen dichten Wolke, Hoehenbild 5 cm, geklemmt -0,10..+0,15 m", hinweis="Scan-Relief, kein Mass; Fenster- und Gesimsfeld ausgeblendet")
    koerper = koerper - WW.prisma(b_rund(0.81, 21.70, 23.45), u=5.40, w0=-0.8, w1=0.6)                          # grosses Fenster (Tiefe ANNAHME; Gewaende buendig = Farbe)
    for u0_, u1_, z0_, z1_ in ((5.31, 5.52, 27.82, 30.19), (5.20, 5.45, 33.0, 34.4), (5.33, 5.47, 16.93, 17.86), (5.27, 5.39, 10.46, 11.44)):   # Schlitzfenster; das oberste (z 33-34,4) ist aus steiler Sicht nur ungefaehr
        koerper = koerper - WW.kasten(u0_, u1_, z0_, z1_, -0.8, 0.6)
    koerper = koerper + WW.kasten(0.0, WW.laenge, 26.0, 26.53, -0.4, 0.10)                                      # Gesims West: Hoehe wie Sued (im Foto 114039 bei z ~26,5), Ausladung ANNAHME
    beleg("wand", "Westfassade: grosses Fenster, 4 Schlitzfenster, Gesims", "foto_mass.py auf der Westwandebene, Foto 114039 (M-114039-001..-006)", fenster_breite=0.81, fenster_hoehe=1.75, fensterachse_u=5.40,
          hinweis="ANNAHME: Tiefen, Schlitzbreiten 0,12-0,25 m aus einem steilen Foto, Gesimshoehe von der Suedseite; Wandlage West nur aus Wolke/LoD2; Treppenturm (LoD2-Nebenteil) unveraendert; Eckquader/Bruchstein fehlen")
    # ---- TREPPENTURM (15.11.2026): LoD2-Nebenteil (D-foermig, 2,8 x 2,5 m, flach) ersetzt durch Zylinder aus dem Kreisausgleich der neuen dichten Wolke ----
    # 16.11.2026 (Nutzer: "Tuermchen zu schmal, Daechlein noch nicht richtig"): Haube am entzerrten Foto commons 054 auf der Ebene durch die Turmachse gemessen (M-054-001..-005):
    # Schaft r 1,56 (Wolke 1,55), Gesims bis r 1,85 bei z 11,57, GESCHWEIFTE Kupferhaube bis z 13,5, Stange, Kugel bei z 14,6. Vorher: Zylinder r 1,52 mit geradem Kegel bis 14,2.
    TT_C, TT_R, TT_ZW, TT_RT = (1.85, 22.49), 1.555, 11.0, 1.85
    koerper = koerper - M.cube((5.4, 4.0, 16.0)).translate((-1.6, 21.03, -0.5))                                 # alten Anbau westlich der Westwand entfernen
    TT_PROF = [(0.0, 0.0), (TT_R, 0.0), (TT_R, TT_ZW), (1.70, 11.25), (TT_RT, 11.45), (TT_RT + 0.01, 11.57), (1.45, 11.92), (1.0, 12.37), (0.61, 12.80), (0.27, 13.20), (0.08, 13.50), (0.035, 13.9), (0.03, 14.52), (0.0, 14.52)]
    turm = M.revolve(CrossSection([[list(p_) for p_ in TT_PROF]]), 64) + M.sphere(0.16, 24).translate((0, 0, 14.6))
    if os.environ.get("OHNE_HOHL") != "1": turm = turm - M.cylinder(10.6, TT_R - float(os.environ.get("WAND_MM", "1.2")) * float(os.environ.get("SCALE", "87")) / 1000.0, TT_R - float(os.environ.get("WAND_MM", "1.2")) * float(os.environ.get("SCALE", "87")) / 1000.0, 48).translate((0, 0, 0.5))      # 16.11.2026 Nutzer: Fenster = echte Loecher -> Treppenturm hohl (Wand 0,35 m ANNAHME); im Hauptturm fuellt dessen Mauer den Hohlraum wieder
    for wz_, z_ in ((-35.0, 10.7), (35.0, 10.7), (-60.0, 8.0), (10.0, 6.2), (-35.0, 4.0)):                       # Schlitzfenster (Lage nach Foto 054/192 abgelesen, 0,12 x 0,6 m, 15 cm tief: ANNAHME)
        turm = turm - M.cube((0.7, 0.12, 0.6)).translate((TT_R - 0.45, -0.06, z_ - 0.3)).rotate((0, 0, 140.0 + wz_))
    koerper = koerper + turm.translate((TT_C[0], TT_C[1], 0.0))
    beleg("wand", "Treppenturm (Zylinder, Gesims, geschweifte Haube mit Stange und Kugel)", "foto_mass.py auf der Ebene durch die Turmachse, Foto commons 054 (M-054-001..-005), Gegenprobe Foto commons 192; Lage/Radius aus dem Kreisausgleich der dichten Wolke (r 1,54-1,57, Rest 2 cm)",
          radius=TT_R, traufradius=TT_RT, traufe=11.57, spitzenansatz=13.5, kugel=14.6, hinweis="ANNAHME: Schlitzfenster nur ungefaehr (Lage am Foto abgelesen), Gesimsprofil vereinfacht; Blechbahnen der Haube fehlen")
    # ---- 16.11.2026 HOLZFRIES unter der Traufe (feines Fassadenbild Nord/Sued, Fernfoto 110756): Rahmenwerk z 34,95-36,55 mit Schwelle, Raehm und Pfosten vor der Wand ----
    FR_E = [(3.49, 9.63), (3.32, 20.97), (-7.36, 20.58), (-7.03, 9.36)]; FR_M = (-1.9, 15.2)                    # Wandecken bei z 35,6 (aus dem Modellschnitt), NO, NW, SW, SO
    for a_, b_ in zip(FR_E, FR_E[1:] + FR_E[:1]):
        mi_ = (0.5 * (a_[0] + b_[0]), 0.5 * (a_[1] + b_[1])); Wf = Wand(a_, b_, aussen=(2 * mi_[0] - FR_M[0], 2 * mi_[1] - FR_M[1])); Lf = Wf.laenge
        koerper = koerper + Wf.kasten(-0.08, Lf + 0.08, 34.95, 35.2, -0.3, 0.08) + Wf.kasten(-0.08, Lf + 0.08, 36.3, 36.56, -0.3, 0.08)
        for k_ in range(6): koerper = koerper + Wf.kasten(k_ * (Lf - 0.24) / 5.0, k_ * (Lf - 0.24) / 5.0 + 0.24, 35.15, 36.35, -0.3, 0.07)
    beleg("wand", "Holzfries unter der Traufe (Schwelle, Raehm, je Seite 6 Pfosten)", "feines Fassadenbild Nord (fassade_fein, 1 cm) und Fernfoto 110756: Rahmenwerk z 34,95-36,55",
          hinweis="ANNAHME: Pfostenzahl 6 je Seite (in den Fotos zu dunkel zum Zaehlen - Zaehlprotokoll fehlt), Querschnitte 24-26 cm, 7-8 cm vor der Wand; Felder nicht zurueckgesetzt; Ost- und Westseite wie Nord")
    # ---- 16.11.2026 FENSTER ALS ECHTE LOECHER (Nutzer: "alles, was in Wirklichkeit durch ein Loch ist, zum Beispiel Fenster, muessen Loecher werden") ----
    if os.environ.get("OHNE_HOHL") != "1":
        from bauteile import aushoehlen; import time as _t; _t0 = _t.time()
        _sch = [WS.prisma(b_rund(0.92, 22.26, 23.66), u=5.745, w0=-1.7, w1=-0.4), WW.prisma(b_rund(0.81, 21.70, 23.45), u=5.40, w0=-1.7, w1=-0.7)]
        _sch += [WW.kasten(u0_, u1_, z0_, z1_, -1.7, -0.7) for u0_, u1_, z0_, z1_ in ((5.31, 5.52, 27.82, 30.19), (5.20, 5.45, 33.0, 34.4), (5.33, 5.47, 16.93, 17.86), (5.27, 5.39, 10.46, 11.44))]
        koerper, n_offen, v_hohl = aushoehlen(koerper, d=float(os.environ.get("WAND_MM", "1.2")) * float(os.environ.get("SCALE", "87")) / 1000.0, schnitte=_sch, fenster=[], min_m3=20.0, z_min=8.0)
        beleg("wand", f"Turm hohl, {n_offen} Fenster durchgebrochen (Sued, West, 4 Schlitze), Treppenturm hohl mit 5 Schlitzen", "Nutzerauftrag 16.11.2026; Fenstermasse wie oben", fenster_offen=n_offen, hohlraum_m3=round(v_hohl, 1),
              hinweis="Wandstaerke = duennste druckstabile Wand (Nutzer 16.11.2026): 1,2 mm im Druck (WAND_MM) = 0,10 m bei 1:87, auch Treppenturm; Innenraum ohne Decken, unter z 8 m massiv (Torgeschoss); die zwei Nordfenster haben geschlossene Laeden und bleiben Nischen")
        print(f"hohl: {n_offen} Durchbrueche, Hohlraum {v_hohl:.0f} m3, {_t.time() - _t0:.0f} s")
    cu, cv = haupt.mean(0); model = koerper.scale((K, K, K))   # 15.11.2026: NICHT zentrieren - STL bleibt im Rahmen (objekt.json rahmen); die Fotowerkzeuge (zentrierung 'achse') erwarten STL = Rahmen, sonst liegt das Modell um (cu, cv) neben Kameras/Wolke
else:
    H = 10.0                               # Gesamthoehe (m) - Quelle in masstabelle.json
    beleg("dach", "Grundkoerper", "ANNAHME: Rumpf ohne LoD2 (objekt.json lod2.id fehlt)", hoehe=H)
    model = M.cube((8.0, 8.0, H)).translate((-4.0, -4.0, 0.0)).scale((K, K, K))
if hasattr(model, "simplify"): model = model.simplify(0.005)      # 15.11.2026: nach der Massstabs-Skalierung fielen Splitterdreiecke (< 5 Mikrometer im Druckmassstab) im float32-STL als 17 Einzelkoerper heraus
from bauteile import kneifkanten_schliessen as _kn; model = _kn(model, r=0.25, stellen=3)      # 16.11.2026: nach Skalieren/Vereinfachen blieb mit 1,2-mm-Wand eine Beruehrkante (4 Flaechen) -> im Druckmassstab (mm) schliessen
mesh = model.to_mesh(); V = np.array(mesh.vert_properties)[:, :3]; F = np.asarray(mesh.tri_verts)
_mf, _mt = np.asarray(mesh.merge_from_vert), np.asarray(mesh.merge_to_vert)
if len(_mf): V[_mf] = V[_mt]; print("verschmolzene Doppelecken:", len(_mf))            # Manifold fuehrt Doppelecken getrennt; im STL muessen sie bitgleich sein
_vq, _inv = np.unique(np.round(V.astype(np.float64), 3), axis=0, return_inverse=True); F = _inv.ravel()[F]; V = _vq.astype(np.float32)   # Ecken auf 1 Mikrometer (Druckmassstab) verschweissen
F = F[(F[:, 0] != F[:, 1]) & (F[:, 1] != F[:, 2]) & (F[:, 0] != F[:, 2])]                                              # entartete Dreiecke (Kante der Laenge 0) entfernen
_fs = np.sort(F, axis=1); _u, _inv2, _cnt = np.unique(_fs, axis=0, return_inverse=True, return_counts=True); F = F[_cnt[_inv2.ravel()] == 1]                 # 15.11.2026: Flaechenpaare mit denselben drei Ecken (Lappen ohne Dicke nach dem Verschweissen) fallen sonst als 2-Flaechen-Koerper heraus
os.makedirs(os.path.dirname(OUT), exist_ok=True)
tri = V[F]; nrm = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]); nrm /= np.linalg.norm(nrm, axis=1, keepdims=True) + 1e-12
rec = np.zeros(len(F), dtype=[("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")]); rec["n"], rec["v"] = nrm, tri
with open(OUT, "wb") as f: f.write(b"schwab_v3".ljust(80, b" ")); f.write(np.uint32(len(F)).tobytes()); f.write(rec.tobytes())
json.dump([dict(e, seite_name=SEITEN.get(e["seite"], e["seite"])) for e in ELEMENTE], open(os.path.join(HERE, "schwab_v3", "elemente.json"), "w"), indent=1, ensure_ascii=False)
print("->", OUT)
