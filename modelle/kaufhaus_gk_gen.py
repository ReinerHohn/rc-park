#!/usr/bin/env python3
"""kaufhaus_gk_gen.py - Generator-Rumpf (manifold3d). Jedes sichtbare Element meldet sich mit beleg(); Bau + Abnahme: tools/bauen_abnehmen.sh kaufhaus_gk"""
import os, sys, json, numpy as np
from manifold3d import Manifold as M
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
from dach_bauen import gebaeude_aus_lod2, seiten_aus_rahmen
SCALE = float(os.environ.get("SCALE", "87")); K = 1000.0 / SCALE
OUT = os.path.join(HERE, "stl", "kaufhaus_gk_1-{SCALE:.0f}.stl".format(SCALE=SCALE))
ELEMENTE = []
def beleg(seite, element, quelle, **masse): ELEMENTE.append(dict(seite=seite, element=element, quelle=quelle, **masse))
OBJ = os.path.join(HERE, "kaufhaus_gk", "objekt.json"); obj = json.load(open(OBJ))
SEITEN = seiten_aus_rahmen(obj)
if obj.get("lod2", {}).get("id"):                    # Standard: LoD2-Grundriss + DOM1-Dach (dach.json, Nullstart-Schritt 'dach') - tools/dach_bauen.py
    koerper, belege, haupt = gebaeude_aus_lod2(OBJ)
    for b_ in belege: beleg(**b_)
    # 17.11.2026 REIHENFOLGE: erst die erkannten Fenster in den Grundkoerper, dann das Relief mit offenen Fensterrechtecken. Vorher (Relief zuerst) liess fenster_aus_json jedes Fenster aus, vor dem
    # eine Reliefplatte stand (5 von 9). fenster_fuer_bau stellt 'Fenster' zurueck, in deren Rechteck das Netz fehlt (Vorbau/Erker davor) - Liste audit/fenster_bau.json.
    from fassaden_kette import anbauen, fenster_fuer_bau   # Fassaden-Kette (tools/fassaden_kette.py): Reliefs je Wand, falls audit/fassaden_kette.json da ist
    from bauteile import fenster_aus_json            # automatisch erkannte Fenster (Kettenstufe 'fenster' schreibt audit/fenster_auto.json)
    FJ = fenster_fuer_bau(OBJ, os.path.join(HERE, "kaufhaus_gk", "audit", "fenster_auto.json"))
    koerper, bel_f = fenster_aus_json(koerper, FJ)
    BF = obj.get("bauteile_foto"); BR = None
    if BF and os.environ.get("OHNE_BAUTEILE") != "1" and os.environ.get("OHNE_REIN") != "1":   # 17.11.2026 Runde 3: Restbrei weg + Relief dort auf Wandniveau, wo Fotobauteile stehen (fassaden_kette.relief_bereinigen)
        from bauteile import Wand
        T = BF["traufwand"]; WT = Wand(T["a"], T["b"], aussen=T["aussen"]); VF, BK, FG, BD, L = BF.get("vorhangfenster"), BF.get("balkon"), BF.get("figuren"), BF.get("baldachine"), BF["laube"]
        NF_ = os.environ.get("REIN_OHNE_FENSTER") == "1"     # Versuch: Fenster-/Balkonflaechen NICHT ersetzen (Relief-Gewaende bleiben, nur Klumpenfilter)
        BR = dict(ersetzt=([] if NF_ else [(WT, a_ - 0.25, b_ + 0.25, VF["z0"] - 0.3, VF["spitze"] + 0.3) for a_, b_ in (VF or {}).get("fenster", [])]
                  + ([(WT, BK["u0"] - 0.3, BK["u1"] + 0.3, BK["z_boden"] - 0.8, BK["z_handlauf"] + 0.15)] if BK else []))
                  + [(WT, f_["u"] - 0.45, f_["u"] + 0.45, f_["z_scheitel"] + min(z for z, _ in FG["konsole"]) - 0.1, f_["z_scheitel"] + 0.1) for f_ in (FG or {}).get("liste", [])]
                  + [(WT, b2["u"] - 0.5, b2["u"] + 0.5, b2["z_spitze"] + min(st[0] for st in BD["stufen"]) - 0.1, b2["z_spitze"] + 0.05) for b2 in (BD or {}).get("liste", [])]
                  + [("rund", E_["achse"], 1.3 * max(a_ for _, _, a_ in E_["zonen"]) / np.cos(np.pi / 8), E_["konsole"][0] - 0.2, E_["helm"][-1][0]) for E_ in BF.get("erker", [])],   # Erker steht vor zwei Waenden
                  erhalten=[(WT, L["u0"], L["u1"], 0.0, max(b2["scheitel"] for b2 in L["boegen"]) + 0.05)])
    koerper, belege = anbauen(koerper, OBJ, fenster=FJ, bereinigen=BR)
    for b_ in belege + bel_f: beleg(**b_)
    belege = bel_f
    BF = obj.get("bauteile_foto")                    # 17.11.2026 Bauteil-Runde: Laube, Staffelgiebel, Gauben, Erker aus Fotos (Masse/Quellen in objekt.json bauteile_foto, Funktionen tools/bauteile.py)
    if BF and os.environ.get("OHNE_BAUTEILE") != "1":
        from bauteile import Wand, laube, staffelgiebel, schleppgaube, erker_polygon
        T = BF["traufwand"]; WT = Wand(T["a"], T["b"], aussen=T["aussen"]); GE = {}
        for g in BF["giebelebenen"]:                 # Rumpf an der gemessenen Giebelflaeche abschneiden (LoD2-Wand ~0,7 m zu weit aussen); Giebel, Dach und Waende enden dort
            GE[g["name"]] = Wand(g["a"], g["b"], aussen=g["aussen"]).versetzt(g["versatz"]); koerper = GE[g["name"]].halbraum_innen(koerper)
            beleg("wand", "Giebelwand %s auf der Foto-Ebene (Rumpf %.2f m zurueckgenommen)" % (g["name"], -g["versatz"]), g["quelle"])
        DS_ = BF.get("dach_schindeln"); SCH = None
        if DS_ and os.environ.get("OHNE_SCHINDELN") != "1":   # 17.11.2026 Runde 3: Biberschwanz-Reihen als Stufenrelief auf den Dachflaechen (bauteile.schindeln), angebaut NACH dem Aushoehlen
            from bauteile import schindeln
            SCH, n_fl, n_r = schindeln(koerper, DS_["abstand"], DS_["tiefe"], nz_min=DS_["nz_min"], nz_max=DS_["nz_max"], z_min=DS_["z_min"])
            beleg("dach", "Dachdeckung: %d Reihen auf %d Dachflaechen, Reihenabstand %.3f m, Stufe %.3f m" % (n_r, n_fl, DS_["abstand"], DS_["tiefe"]), DS_["quelle"], hinweis="ANNAHME: " + "; ".join(DS_["annahmen"]))
        L = BF["laube"]; koerper, _ = laube(koerper, WT, L["boegen"], L["tiefe"], L["decke"], pfeiler_tiefe=L["pfeiler_tiefe"], u0=L["u0"], u1=L["u1"],
                                            stirn=[(GE[s["giebel"]], s) for s in L.get("stirn", [])], frei=L.get("frei") if BF.get("saeulen") else None, unten=L.get("boden", -0.5))
        beleg("wand", "Laube: %d Korbboegen + offene Halle %.2f m tief, Stirnbogen West" % (len(L["boegen"]), L["tiefe"]), L["quelle"], hinweis="ANNAHME: " + "; ".join(L["annahmen"]))
        if BF.get("saeulen"): beleg("wand", "Laube: Pfeilerzone bis Kaempfer freigeraeumt (Saeulen statt Wandpfeiler)", L["frei_quelle"])
        if "boden" in L: beleg("wand", "Laube: Boden/Pflaster auf z %.2f (Bogenunterkanten)" % L["boden"], L["boden_quelle"])
    if belege and os.environ.get("OHNE_HOHL") != "1":        # 16.11.2026 Nutzer: Fenster muessen echte Loecher sein -> Gebaeude hohl, erkannte Fenster durchgebrochen
        from bauteile import aushoehlen
        koerper, n_offen, v_hohl = aushoehlen(koerper, d=float(os.environ.get("WAND_MM", "1.2")) * float(os.environ.get("SCALE", "87")) / 1000.0)
        beleg("wand", "Gebaeude hohl, %d Fenster durchgebrochen" % n_offen, "bauteile.aushoehlen auf den automatisch erkannten Fenstern", hinweis="Wandstaerke 1,2 mm im Druck (WAND_MM, duennste druckstabile Wand), Innenraum ohne Decken und Zwischenwaende")
    if BF and os.environ.get("OHNE_BAUTEILE") != "1":   # 17.11.2026 Runde 2: Saeulen, Vorhangbogenfenster, Balkon (tools/bauteile.py saeule / vorhangbogen_fenster / balkon), alle NACH dem Aushoehlen
        from bauteile import saeule, balkon, vorhangbogen_fenster, figur, baldachin
        if SCH is not None: koerper = koerper + SCH
        FG = BF.get("figuren"); BD = BF.get("baldachine")
        if FG and os.environ.get("OHNE_FIGUREN") != "1":   # 17.11.2026 Runde 3: Figuren + Baldachine aus grob3 uebertragen (uebertrag_grob3.py), KLIPSTEIL-Kandidaten
            for f_ in FG["liste"]:
                koerper = koerper + figur(WT, f_["u"], FG["w_achse"], [[f_["z_scheitel"] + z, r] for z, r in FG["konsole"]], [[f_["z_scheitel"] + z, b_, d_] for z, b_, d_ in FG["koerper"]])
            beleg("wand", "%d Figuren auf Rundkonsolen zwischen den Obergeschossfenstern (KLIPSTEIL-Kandidat)" % len(FG["liste"]), FG["quelle"], hinweis="ANNAHME: " + "; ".join(FG["annahmen"]), klipsteil=True, u=[f_["u"] for f_ in FG["liste"]])
        if BD and os.environ.get("OHNE_FIGUREN") != "1":
            for b2 in BD["liste"]:
                koerper = koerper + baldachin(WT, b2["u"], BD["w_wand"] + b2["ds"], b2["z_spitze"], BD["stufen"], BD["fialen"], einbindung=BD["einbindung"], kegel_h=BD["kegel_h"])
            beleg("wand", "%d Baldachine ueber den Figuren (Haube + Krone + 3 Fialen, KLIPSTEIL-Kandidat)" % len(BD["liste"]), BD["quelle"], hinweis="ANNAHME: " + "; ".join(BD["annahmen"]), klipsteil=True, u=[b2["u"] for b2 in BD["liste"]])
        SA = BF.get("saeulen")
        if SA:
            for i, s in enumerate(SA["liste"]):
                ecke = i in (0, len(SA["liste"]) - 1)
                koerper = koerper + saeule(WT, s["u"], SA["w"], SA["z0"], SA["z1"], s["d"], basis=SA["basis_ecke" if ecke else "basis"], kapitell=SA["kapitell_ecke" if ecke else "kapitell"])
            beleg("wand", "Laube: %d runde Saeulen mit Plinthe, Wulst und Aufweitung (statt Wandpfeiler)" % len(SA["liste"]), SA["quelle"], hinweis="ANNAHME: " + "; ".join(SA["annahmen"]),
                  durchmesser=[s["d"] for s in SA["liste"]])
        VF = BF.get("vorhangfenster")
        if VF:
            for u0_, u1_ in VF["fenster"]:
                zu_, ab_, pf_ = vorhangbogen_fenster(WT, u0_, u1_, VF["z0"], VF["z1"], VF["schulter"], VF["spitze"], VF["mitte"], VF["feld"], exponent=VF["exponent"], kaempfer=VF.get("kaempfer"), w_fuell=tuple(VF["w_fuell"]))
                koerper = (koerper + zu_ - ab_) + pf_
            beleg("wand", "%d Obergeschossfenster mit Vorhangbogen (3 Felder, 2 Pfosten an den Spitzen, Kaempfer)" % len(VF["fenster"]), VF["quelle"], hinweis="ANNAHME: " + "; ".join(VF["annahmen"]))
        BK = BF.get("balkon")
        if BK:
            koerper = koerper + balkon(WT, BK["u0"], BK["u1"], BK["z_boden"], BK["w_vorne"], BK["z_handlauf"], BK["docken"], BK["pfosten"], BK["konsolen"], platte=BK["platte"],
                                       konsole=tuple(BK["konsole"]), seiten_docken=BK["seiten_docken"])
            beleg("wand", "Balkon ueber der Laube: Bodenplatte, %d Konsolen, %d Pfosten, %d Docken vorn + je %d seitlich, Handlauf" % (len(BK["konsolen"]), len(BK["pfosten"]), len(BK["docken"]), BK["seiten_docken"]),
                  BK["quelle"], hinweis="ANNAHME: " + "; ".join(BK["annahmen"]))
    if BF and os.environ.get("OHNE_BAUTEILE") != "1":   # massive Anbauten NACH dem Aushoehlen (sonst Null-Volumen-Splitter an den Gauben: 11 Teilnetze)
        for G in BF["staffelgiebel"]:
            koerper = koerper + staffelgiebel(GE[G["giebel"]], G["mitte_u"], G["spitze_breite"], G["spitze_z"], G["flanken"], dicke=G["dicke"], fuss_z=G["fuss_z"])
            n_st = {s: len(st) for s, st in G["flanken"]}
            beleg("dach", "Staffelgiebel %s: Spitzblock + %s Stufen je Flanke mit Abdeckung" % (G["giebel"], "/".join(str(v) for v in n_st.values())), G["quelle"],
                  hinweis="ANNAHME: Dicke %.2f, Abdeckungsprofil; ab Stufe %s (Flanke) aus dem gemessenen Rhythmus fortgesetzt" % (G["dicke"], G.get("annahme_ab")))
        g = BF["gauben"]; ab_g = None
        for G in g["liste"]:
            zf = g["dach_z0"] + g["dach_s"] * (-G["w_front"])
            zu, ab = schleppgaube(WT, G["u"], G["w_front"], zf, g["breite"], g["hoehe"], g["neigung"], g["dach_z0"], g["dach_s"], dach_breite=g["dach_breite"], ueberstand=g["ueberstand"], fenster=g["fenster"])
            koerper = koerper + zu; ab_g = ab if ab_g is None else ab_g + ab
            beleg("dach", "Schleppgaube %s (u %.2f, Front %.2f hinter der Traufwand)" % (G["name"], G["u"], -G["w_front"]), g["quelle"], hinweis="ANNAHME: " + "; ".join(g["annahmen"]))
        if ab_g is not None: koerper = koerper - ab_g
        for E in BF["erker"]:
            ek = erker_polygon(E["achse"], WT.n, E["apothem"], E["zonen"], konsole=E["konsole"], fenster=E["fenster"], felder=E.get("felder"), helm=E["helm"], knauf=E["knauf"], stange=E["stange"], wirt=koerper,
                               konsole_rippen=E.get("konsole_rippen") if os.environ.get("OHNE_ERKERDETAIL") != "1" else None)
            if DS_ and DS_.get("helm") and SCH is not None:       # Runde 3: Helmdeckung mit demselben Reihenabstand (ANNAHME)
                hs, _, _ = schindeln(ek, DS_["abstand"], DS_["tiefe"], nz_min=DS_["nz_min"], nz_max=DS_["nz_max"], z_min=E["helm"][0][0] + 0.05, min_m2=DS_.get("helm_min_m2", 0.3)); ek = ek + hs
            koerper = koerper + ek
            beleg("wand", "%s %s: Achteck-Eckerker (Konsole mit Rippennetz, Wappenband mit Medaillons, Fensterband 2 Lichter je Flaeche mit Kaempfer und Kielbogenkopf, Gesims, geschweifter Helm mit Deckung, Knauf)" % (E["name"], E["seite"]), E["quelle"] + " | " + E.get("quelle_runde3", ""), hinweis="ANNAHME: " + "; ".join(E["annahmen"]))
    tl_ = koerper.decompose()                       # 17.11.2026 Runde 3: Null-Volumen-Splitter (10 Dreiecke an einer Konsolrippe, 0,0 m3) entfernen; echte schwebende Teile (Volumen) bleiben und fallen in der Pruefung auf
    if len(tl_) > 1:
        weg_ = [t_ for t_ in tl_ if t_.volume() < 1e-5]
        if weg_: koerper = M.batch_boolean([t_ for t_ in tl_ if t_.volume() >= 1e-5], __import__("manifold3d").OpType.Add); beleg("wand", "%d Null-Volumen-Splitter entfernt" % len(weg_), "Generator (decompose, Volumen < 1e-5 m3)")
    cu, cv = haupt.mean(0); model = koerper.scale((K, K, K))   # 15.11.2026: NICHT zentrieren - STL bleibt im Rahmen (objekt.json rahmen); die Fotowerkzeuge (zentrierung 'achse') erwarten STL = Rahmen, sonst liegt das Modell um (cu, cv) neben Kameras/Wolke
else:
    H = 10.0                               # Gesamthoehe (m) - Quelle in masstabelle.json
    beleg("dach", "Grundkoerper", "ANNAHME: Rumpf ohne LoD2 (objekt.json lod2.id fehlt)", hoehe=H)
    model = M.cube((8.0, 8.0, H)).translate((-4.0, -4.0, 0.0)).scale((K, K, K))
from bauteile import stl_schreiben          # verschweisst Ecken, entfernt Lappen und Kruemel (16.11.2026: die Vorlage schrieb selbst und liess Zwei-Flaechen-Kruemel als Einzelkoerper stehen)
stl_schreiben(model, OUT, b"kaufhaus_gk")
json.dump([dict(e, seite_name=SEITEN.get(e["seite"], e["seite"])) for e in ELEMENTE], open(os.path.join(HERE, "kaufhaus_gk", "elemente.json"), "w"), indent=1, ensure_ascii=False)
print("->", OUT)
