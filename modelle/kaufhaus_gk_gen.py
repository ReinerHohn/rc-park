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
    koerper, belege = anbauen(koerper, OBJ, fenster=FJ)
    for b_ in belege + bel_f: beleg(**b_)
    belege = bel_f
    BF = obj.get("bauteile_foto")                    # 17.11.2026 Bauteil-Runde: Laube, Staffelgiebel, Gauben, Erker aus Fotos (Masse/Quellen in objekt.json bauteile_foto, Funktionen tools/bauteile.py)
    if BF and os.environ.get("OHNE_BAUTEILE") != "1":
        from bauteile import Wand, laube, staffelgiebel, schleppgaube, erker_polygon
        T = BF["traufwand"]; WT = Wand(T["a"], T["b"], aussen=T["aussen"]); GE = {}
        for g in BF["giebelebenen"]:                 # Rumpf an der gemessenen Giebelflaeche abschneiden (LoD2-Wand ~0,7 m zu weit aussen); Giebel, Dach und Waende enden dort
            GE[g["name"]] = Wand(g["a"], g["b"], aussen=g["aussen"]).versetzt(g["versatz"]); koerper = GE[g["name"]].halbraum_innen(koerper)
            beleg("wand", "Giebelwand %s auf der Foto-Ebene (Rumpf %.2f m zurueckgenommen)" % (g["name"], -g["versatz"]), g["quelle"])
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
        from bauteile import saeule, balkon, vorhangbogen_fenster
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
            koerper = koerper + erker_polygon(E["achse"], WT.n, E["apothem"], E["zonen"], konsole=E["konsole"], fenster=E["fenster"], felder=E.get("felder"), helm=E["helm"], knauf=E["knauf"], stange=E["stange"], wirt=koerper)
            beleg("wand", "%s %s: Achteck-Eckerker (Konsole, Wappenband, Fensterband 2 Lichter je Flaeche, Gesims, geschweifter Helm, Knauf)" % (E["name"], E["seite"]), E["quelle"], hinweis="ANNAHME: " + "; ".join(E["annahmen"]))
    cu, cv = haupt.mean(0); model = koerper.scale((K, K, K))   # 15.11.2026: NICHT zentrieren - STL bleibt im Rahmen (objekt.json rahmen); die Fotowerkzeuge (zentrierung 'achse') erwarten STL = Rahmen, sonst liegt das Modell um (cu, cv) neben Kameras/Wolke
else:
    H = 10.0                               # Gesamthoehe (m) - Quelle in masstabelle.json
    beleg("dach", "Grundkoerper", "ANNAHME: Rumpf ohne LoD2 (objekt.json lod2.id fehlt)", hoehe=H)
    model = M.cube((8.0, 8.0, H)).translate((-4.0, -4.0, 0.0)).scale((K, K, K))
from bauteile import stl_schreiben          # verschweisst Ecken, entfernt Lappen und Kruemel (16.11.2026: die Vorlage schrieb selbst und liess Zwei-Flaechen-Kruemel als Einzelkoerper stehen)
stl_schreiben(model, OUT, b"kaufhaus_gk")
json.dump([dict(e, seite_name=SEITEN.get(e["seite"], e["seite"])) for e in ELEMENTE], open(os.path.join(HERE, "kaufhaus_gk", "elemente.json"), "w"), indent=1, ensure_ascii=False)
print("->", OUT)
