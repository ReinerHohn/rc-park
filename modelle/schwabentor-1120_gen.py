#!/usr/bin/env python3
"""schwabentor-1120_gen.py - Generator-Rumpf (manifold3d). Jedes sichtbare Element meldet sich mit beleg(); Bau + Abnahme: tools/bauen_abnehmen.sh schwabentor-1120"""
import os, sys, json, numpy as np
from manifold3d import Manifold as M
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
from dach_bauen import gebaeude_aus_lod2, seiten_aus_rahmen
SCALE = float(os.environ.get("SCALE", "87")); K = 1000.0 / SCALE
OUT = os.path.join(HERE, "stl", "schwabentor-1120_1-{SCALE:.0f}.stl".format(SCALE=SCALE))
ELEMENTE = []
def beleg(seite, element, quelle, **masse): ELEMENTE.append(dict(seite=seite, element=element, quelle=quelle, **masse))
OBJ = os.path.join(HERE, "schwabentor-1120", "objekt.json"); obj = json.load(open(OBJ))
SEITEN = seiten_aus_rahmen(obj)
if obj.get("lod2", {}).get("id"):                    # Standard: LoD2-Grundriss + DOM1-Dach (dach.json, Nullstart-Schritt 'dach') - tools/dach_bauen.py
    koerper, belege, haupt = gebaeude_aus_lod2(OBJ)
    for b_ in belege: beleg(**b_)
    from bauteile import korrekturen_aus_json as _kw   # 21.11.2026: gemessener Wandversatz am GRUNDKOERPER, bevor Fenster/Relief daran gebaut werden (Abweichungsschleife)
    koerper, belege = _kw(koerper, os.path.join(HERE, "schwabentor-1120", "audit", "schleife_korrekturen.json"), art="wandversatz")
    for b_ in belege: beleg(**b_)
    # 17.11.2026 REIHENFOLGE: erst die erkannten Fenster in den Grundkoerper, dann das Relief mit offenen Fensterrechtecken (Relief zuerst liess jedes Fenster aus, vor dem eine Reliefplatte stand:
    # Kaufhaus 5 von 9). fenster_fuer_bau stellt 'Fenster' zurueck, in deren Rechteck das Netz fehlt (Vorbau/Erker davor) - Liste audit/fenster_bau.json.
    from fassaden_kette import anbauen, fenster_fuer_bau   # Fassaden-Kette (tools/fassaden_kette.py): Reliefs je Wand, falls audit/fassaden_kette.json da ist
    from bauteile import fenster_aus_json            # automatisch erkannte Fenster (Kettenstufe 'fenster' schreibt audit/fenster_auto.json)
    FJ = fenster_fuer_bau(OBJ, os.path.join(HERE, "schwabentor-1120", "audit", "fenster_auto.json"))
    koerper, bel_f = fenster_aus_json(koerper, FJ)
    koerper, belege = anbauen(koerper, OBJ, fenster=FJ)
    for b_ in belege + bel_f: beleg(**b_)
    from dach_bauen import ueber_traufe_nur_dach      # 17.11.2026: Fotodach (tools/dach_aus_fotos.py) - Reliefreste ueber der Traufe schweben sonst frei
    koerper, belege = ueber_traufe_nur_dach(koerper, OBJ)
    for b_ in belege: beleg(**b_)
    belege = bel_f                                   # aushoehlen nur, wenn Fenster gebaut wurden
    from bauteile import oeffnungen_aus_json         # 17.11.2026: automatisch erkannte Bogenoeffnungen / Tordurchfahrten (Kettenstufe 'fenster': tools/oeffnungen_bogen.py -> audit/oeffnungen_auto.json)
    koerper, belege_o, z_tor = oeffnungen_aus_json(koerper, os.path.join(HERE, "schwabentor-1120", "audit", "oeffnungen_auto.json"), innenwaende=obj.get("innenwaende"))      # 18.11.: Bogen vor einer Innenwand reicht bis zu ihr
    for b_ in belege_o: beleg(**b_)
    if obj.get("innenwaende") and os.environ.get("OHNE_LAUBE") != "1":   # 18.11.2026 (L2): Laube/Halle vor einer gemessenen Innenwand freilegen - Boegen = Umrisse aus dem Wandbild der Aussenwand
        from bauteile import laube_aus_wandbild
        koerper, bel_l = laube_aus_wandbild(koerper, obj["innenwaende"], os.path.join(HERE, "schwabentor-1120", "audit", "oeffnungen_aussen.json"), pfeiler_tiefe=float(obj.get("pfeiler_tiefe", 0.8)))
        for b_ in bel_l: beleg(**b_)
    IO_ = obj.get("innenwand_oeffnungen")            # 18.11.2026 (Kettenstufe 'bauplan', L2): Oeffnungen der Innenwaende aus ihrem Wandbild - nur wo die Innenwand freiliegt, VOR aushoehlen
    if IO_ and os.environ.get("OHNE_INNENWAND") != "1":
        from bauteile import oeffnungen_aus_wandbild
        koerper, bel_i = oeffnungen_aus_wandbild(koerper, os.path.join(HERE, "schwabentor-1120", IO_["datei"]), ncc_min=IO_.get("ncc_min", 0.2), ersatz={k: tuple(v) for k, v in IO_.get("ersatz", {}).items()}, nur_frei=True)
        for b_ in bel_i: beleg(**b_)
    from bauteile import korrekturen_aus_json          # 21.11.2026: Korrekturen der Abweichungsschleife (tools/ebenen_schleife.py -> audit/schleife_korrekturen.json), VOR dem Aushoehlen (Abtragen am hohlen Koerper wuerde die 1,2-mm-Wand durchschneiden)
    koerper, bel_k = korrekturen_aus_json(koerper, os.path.join(HERE, "schwabentor-1120", "audit", "schleife_korrekturen.json"), ohne="wandversatz")
    for b_ in bel_k: beleg(**b_)
    if belege and os.environ.get("OHNE_HOHL") != "1":        # 16.11.2026 Nutzer: Fenster muessen echte Loecher sein -> Gebaeude hohl, erkannte Fenster durchgebrochen
        from bauteile import aushoehlen
        koerper, n_offen, v_hohl = aushoehlen(koerper, d=float(os.environ.get("WAND_MM", "1.2")) * float(os.environ.get("SCALE", "87")) / 1000.0, z_min=z_tor)      # z_tor: unter dem Scheitel einer Durchfahrt (+ 0,5 m Gewoelbe, ANNAHME) bleibt das Torgeschoss massiv
        beleg("wand", "Gebaeude hohl, %d Fenster durchgebrochen" % n_offen, "bauteile.aushoehlen auf den automatisch erkannten Fenstern", hinweis="Wandstaerke 1,2 mm im Druck (WAND_MM, duennste druckstabile Wand), Innenraum ohne Decken und Zwischenwaende")
        RW_ = obj.get("rueckwand") or dict(tiefe=0.15, quelle="ANNAHME: 0,15 m (keine Kettenmessung - Stufe bauplan nicht gelaufen; Anhalt Kaufhaus-Fotomass 0,14 / 0,19 m)")
        if os.environ.get("OHNE_RUECKWAND") != "1":      # 18.11.2026 REGEL A (Kettenstufe 'bauplan' misst objekt.json "rueckwand"): hinter jeder durchgebrochenen Oeffnung eine Rueckwand in Leibungstiefe - kein Blick ins Hohlinnere
            from bauteile import rueckwaende, DURCH
            koerper, rw_info = rueckwaende(koerper, DURCH, RW_["tiefe"], float(os.environ.get("WAND_MM", "1.2")) * float(os.environ.get("SCALE", "87")) / 1000.0)
            beleg("wand", "Rueckwand hinter %d Oeffnungen in Leibungstiefe %.2f m (Kragen zum Hohlraum geschlossen)" % (len(rw_info), RW_["tiefe"]), RW_["quelle"], hinweis=RW_.get("hinweis", ""), umrisse=rw_info)
            from bauteile import entlueften                 # Hohlraum nach Regel A ringsum zu -> Schacht zur Standflaeche (sonst 2 Koerper / Luftblase)
            koerper, bel_e = entlueften(koerper)
            for b_ in bel_e: beleg(**b_)
    if os.environ.get("OHNE_VORBAU") != "1":          # 20.11.2026: Vorbauten (Erker/Galerie/Vordach) aus dem Ebenen-Sweep - Kettenstufe 'bauplan': tools/vorbauten_bauplan.py -> audit/vorbauten_auto.json
        from bauteile import vorbauten_aus_json
        koerper, bel_v = vorbauten_aus_json(koerper, os.path.join(HERE, "schwabentor-1120", "audit", "vorbauten_auto.json"))
        for b_ in bel_v: beleg(**b_)
        from bauteile import drehkoerper_aus_wolkenrest   # 21.11.2026: runde Anbauten (Treppenturm) aus dem Rest der dichten Wolke (tools/wolke_rest.py --uebernehmen -> audit/koerper_auto.json)
        koerper, bel_d = drehkoerper_aus_wolkenrest(koerper, os.path.join(HERE, "schwabentor-1120", "audit", "koerper_auto.json"))
        for b_ in bel_d: beleg(**b_)
        from bauteile import dach_aus_profil               # 21.11.2026: Dach mit Ueberstand/Laternenkoerper als Schichtprofil der dichten Wolke (tools/dach_profil_wolke.py -> audit/dach_profil.json)
        koerper, bel_p = dach_aus_profil(koerper, os.path.join(HERE, "schwabentor-1120", "audit", "dach_profil.json"))
        for b_ in bel_p: beleg(**b_)
        from bauteile import uhren_aus_json            # 21.11.2026: Turmuhren (Kettenstufe 'bauplan': tools/uhren_wandbild.py -> audit/uhren_auto.json)
        koerper, bel_u = uhren_aus_json(koerper, os.path.join(HERE, "schwabentor-1120", "audit", "uhren_auto.json"))
        for b_ in bel_u: beleg(**b_)
    tl_ = koerper.decompose()                         # Null-Volumen-Splitter entfernen (wie Kaufhaus-Generator 17.11.); echte schwebende Teile bleiben und fallen in der Pruefung auf
    if len(tl_) > 1 and any(t_.volume() < 1e-5 for t_ in tl_):
        koerper = M.batch_boolean([t_ for t_ in tl_ if t_.volume() >= 1e-5], __import__("manifold3d").OpType.Add); beleg("wand", "%d Null-Volumen-Splitter entfernt" % sum(1 for t_ in tl_ if t_.volume() < 1e-5), "Generator (decompose, Volumen < 1e-5 m3)")
    cu, cv = haupt.mean(0); model = koerper.scale((K, K, K))   # 15.11.2026: NICHT zentrieren - STL bleibt im Rahmen (objekt.json rahmen); die Fotowerkzeuge (zentrierung 'achse') erwarten STL = Rahmen, sonst liegt das Modell um (cu, cv) neben Kameras/Wolke
else:
    H = 10.0                               # Gesamthoehe (m) - Quelle in masstabelle.json
    beleg("dach", "Grundkoerper", "ANNAHME: Rumpf ohne LoD2 (objekt.json lod2.id fehlt)", hoehe=H)
    model = M.cube((8.0, 8.0, H)).translate((-4.0, -4.0, 0.0)).scale((K, K, K))
from bauteile import stl_schreiben          # verschweisst Ecken, entfernt Lappen und Kruemel (16.11.2026: die Vorlage schrieb selbst und liess Zwei-Flaechen-Kruemel als Einzelkoerper stehen)
stl_schreiben(model, OUT, b"schwabentor-1120")
json.dump([dict(e, seite_name=SEITEN.get(e["seite"], e["seite"])) for e in ELEMENTE], open(os.path.join(HERE, "schwabentor-1120", "elemente.json"), "w"), indent=1, ensure_ascii=False)
print("->", OUT)
