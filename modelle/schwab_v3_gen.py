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
    rumpf = (koerper + wand).trim_by_plane((-nn[0], -nn[1], 0.0), float(-(nn @ ca)))
    beleg("wand", "Nordwand (Ebene)", "Foto-Peilung foto_mass.py --tri2d der Wandecken am Uhrgeschoss (M-113205-012/-013)", x_bei_y9=3.72, x_bei_y21=3.54,
          hinweis="ANNAHME: Wand ueber die ganze Hoehe in dieser Ebene (Anzug/Sockel noch nicht gemessen)")
    # Relief-Einsatz Nordwand (Nutzerentscheidung 15.11.2026): Hoehenbild aus dem OpenMVS-Netz als Platte vor der gepeilten Wandebene; Wand, Kanten und
    # Oeffnungen bleiben Sache des Generators. Erzeugt mit tools/relief_einsatz.py (modelle/schwab_v3/relief/nord.npz), geprueft mit tools/relief_test.py.
    from relief_einsatz import koerper as relief_koerper
    rel_n = os.path.join(HERE, "schwab_v3", "relief", "nord.npz")
    if os.path.exists(rel_n) and os.environ.get("OHNE_RELIEF") != "1":
        rumpf = rumpf + relief_koerper(rel_n, tiefe=0.12, null_felder=[(2.6, 5.4, 23.9, 27.1), (6.9, 9.7, 23.9, 27.1), (1.6, 11.1, 9.7, 21.1)])   # Fensterfelder baut der Generator scharf (unten)
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
    for ub in (3.05, 9.10): rumpf = rumpf + kasten(ub - 0.15, ub + 0.15, 35.55, 36.0, -0.05, 0.25)            # Balkenkoepfe: Lage aus dem entzerrten Foto 113029, Groesse ANNAHME
    beleg("wand", "Uhr Nord (Zifferblatt 5,36 m, Innenfeld 3,52 m)", "foto_mass.py auf der Wandebene, Fotos 113029 und 113205", durchmesser=U_D, mitte_u=U_UM, mitte_z=U_ZM,
          hinweis="ANNAHME: Ring 10 cm / Innenfeld 6 cm vor der Wand; Ziffern, Zeiger, Sonne/Mond nicht modelliert; 2 Balkenkoepfe nach Augenschein")
    koerper = massstab(rumpf + dach + lat, MK)
    for e_ in ELEMENTE[N_BELEGE_LOD2:]:                    # Masse der Belege in den korrigierten Rahmen: Laengen/Hoehen x MK, Winkel bleiben, x-Lagen um den Drehpunkt
        for q_, v_ in list(e_.items()):
            if isinstance(v_, (int, float)) and not isinstance(v_, bool) and q_ != "neigung_grad": e_[q_] = round(MC[0] + MK * (v_ - MC[0]), 2) if q_.startswith("x_bei") else round(v_ * MK, 2)
        e_["hinweis"] = (e_.get("hinweis", "") + " | Masse mit Lasermassstab 0,933 (DOM1); Rohmasse in den Protokollen M-* gelten im Rahmen vor der Korrektur").strip(" |")
    cu, cv = haupt.mean(0); model = koerper.scale((K, K, K))   # 15.11.2026: NICHT zentrieren - STL bleibt im Rahmen (objekt.json rahmen); die Fotowerkzeuge (zentrierung 'achse') erwarten STL = Rahmen, sonst liegt das Modell um (cu, cv) neben Kameras/Wolke
else:
    H = 10.0                               # Gesamthoehe (m) - Quelle in masstabelle.json
    beleg("dach", "Grundkoerper", "ANNAHME: Rumpf ohne LoD2 (objekt.json lod2.id fehlt)", hoehe=H)
    model = M.cube((8.0, 8.0, H)).translate((-4.0, -4.0, 0.0)).scale((K, K, K))
if hasattr(model, "simplify"): model = model.simplify(0.005)      # 15.11.2026: nach der Massstabs-Skalierung fielen Splitterdreiecke (< 5 Mikrometer im Druckmassstab) im float32-STL als 17 Einzelkoerper heraus
mesh = model.to_mesh(); V = np.array(mesh.vert_properties)[:, :3]; F = np.asarray(mesh.tri_verts)
_mf, _mt = np.asarray(mesh.merge_from_vert), np.asarray(mesh.merge_to_vert)
if len(_mf): V[_mf] = V[_mt]; print("verschmolzene Doppelecken:", len(_mf))            # Manifold fuehrt Doppelecken getrennt; im STL muessen sie bitgleich sein
_vq, _inv = np.unique(np.round(V.astype(np.float64), 3), axis=0, return_inverse=True); F = _inv.ravel()[F]; V = _vq.astype(np.float32)   # Ecken auf 1 Mikrometer (Druckmassstab) verschweissen
F = F[(F[:, 0] != F[:, 1]) & (F[:, 1] != F[:, 2]) & (F[:, 0] != F[:, 2])]                                              # entartete Dreiecke (Kante der Laenge 0) entfernen
os.makedirs(os.path.dirname(OUT), exist_ok=True)
tri = V[F]; nrm = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]); nrm /= np.linalg.norm(nrm, axis=1, keepdims=True) + 1e-12
rec = np.zeros(len(F), dtype=[("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")]); rec["n"], rec["v"] = nrm, tri
with open(OUT, "wb") as f: f.write(b"schwab_v3".ljust(80, b" ")); f.write(np.uint32(len(F)).tobytes()); f.write(rec.tobytes())
json.dump([dict(e, seite_name=SEITEN.get(e["seite"], e["seite"])) for e in ELEMENTE], open(os.path.join(HERE, "schwab_v3", "elemente.json"), "w"), indent=1, ensure_ascii=False)
print("->", OUT)
