#!/usr/bin/env python3
"""objekt_anlegen.py - neues Bauwerk in den Pflichtrahmen aufnehmen (modelle/METHODE_MASSTABELLE.md), ohne Abschreiben.

  python3 tools/objekt_anlegen.py <objekt> --name "Schwabentor" --generator "SCALE=87 ~/.venvs/rcpark/bin/python modelle/schwabentor_gen.py" \\
      --stl modelle/stl/schwabentor_1-87.stl --fotos daten/schwabentor/fotos [--hoehe 40 --hoehe-quelle "Wikipedia ..."]
Legt an: modelle/<objekt>/objekt.json, masstabelle.json (Startzeilen: Gesamthoehe aus Dokument, wasserdicht, ein Koerper; Beobachtung "Quellen sichten"),
einen Generator-Rumpf mit beleg()-Register (falls die Generatordatei fehlt) und druckt den Pflichtablauf.
Weitere Optionen: --ort, --fotos-quelle DIR (leeren Fotoordner dorthin verlinken), --generator-erneuern (nur Generator-Rumpf neu, wenn unberuehrt).
Vorhandene objekt.json/masstabelle.json werden NIE ueberschrieben. Umgebung: python3 genuegt (nur json). Exit 0.
"""
import sys, os, json

def main():
    a = sys.argv[1:]; ob = a[0]
    def opt(k, d=None): return a[a.index(k) + 1] if k in a else d
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); d = os.path.join(root, "modelle", ob); os.makedirs(d, exist_ok=True)
    gen = opt("--generator", f"SCALE=87 MINMM=0.8 ~/.venvs/rcpark/bin/python modelle/{ob}_gen.py"); stl = opt("--stl", f"modelle/stl/{ob}_1-87.stl")
    genfile = gen.split()[-1]
    obj = dict(name=opt("--name", ob), ort=opt("--ort", ""), generator=gen, stl=stl, stl_massstab=87, stl_einheit_mm=True, zentrierung="achse",
               masstabelle=f"modelle/{ob}/masstabelle.json", elemente=f"modelle/{ob}/elemente.json", audit=f"modelle/{ob}/audit",
               ueberwacht=[genfile, stl, f"modelle/{ob}/masstabelle.json", f"modelle/{ob}/elemente.json"],
               fotos_dir=opt("--fotos", f"daten/{ob}/fotos"), seiten_konvention={"+x": "Sued (festlegen!)", "-x": "Nord", "+y": "Ost", "-y": "West", "quelle": "OFFEN"},
               fotos={}, quellen={"dokument": "OFFEN", "lod2": "OFFEN", "dom1_dgm1": "OFFEN", "dop20": "OFFEN", "fotos": "OFFEN", "laser_punkte": "n/a (kostenpflichtig)"})
    hoehe = opt("--hoehe"); tab = {"_doku": "Masstabelle = einzige Wahrheit ueber die Masse; siehe modelle/METHODE_MASSTABELLE.md", "konstanten": {},
           "messungen": {"hoehe": {"typ": "hoehe_max"}, "wasserdicht": {"typ": "wasserdicht"}, "koerper": {"typ": "koerper_anzahl"}},
           "pruefungen": [{"name": "Wasserdicht (1=ja)", "wert": "wasserdicht", "soll": [1, 1], "quelle": "Druckfaehigkeit", "quelltyp": "modell", "merkmal": "druck"},
                          {"name": "Anzahl getrennte Koerper", "wert": "koerper", "soll": [1, 1], "quelle": "Schwebende Teile", "quelltyp": "modell", "merkmal": "druck"}],
           "beobachtungen_offen": [{"datum": "heute", "wer": "Anlage", "text": "Quellen sichten: Dokumente (Hoehe), LoD2 (Grundriss/Traufe), DOM1 (Dachform), Fotos je Seite", "naechster_schritt": "objekt.json/quellen fuellen, Zeilen mit Quelle anlegen"}]}
    if hoehe:
        h = float(hoehe); tab["pruefungen"].insert(0, {"name": "Gesamthoehe (m)", "wert": "hoehe", "soll": [h * 0.97, h * 1.03], "quelle": opt("--hoehe-quelle", "Dokument (eintragen!)"), "quelltyp": "dokument", "merkmal": "absolut_hoehe", "massstab": "dokument"})
    nur_gen = "--generator-erneuern" in a      # 16.11.2026: Kettenobjekte vom 14.11. hatten einen Generator aus der ALTEN Vorlage (ohne Fassaden/Fenster/Hohl) - nur den unberuehrten Rumpf erneuern, sonst nichts anfassen
    for fn, data in (() if nur_gen else (("objekt.json", obj), ("masstabelle.json", tab))):
        p = os.path.join(d, fn)
        if os.path.exists(p): print("vorhanden, nicht ueberschrieben:", p); continue
        json.dump(data, open(p, "w"), indent=1, ensure_ascii=False); print("angelegt:", p)
    # Fotoordner aus objekt.json["fotos_dir"] anlegen (Lehre Schwabentor 13.11.: Pfad zeigte ins Leere, kein Werkzeug fand Fotos).
    # --fotos-quelle DIR: Fotoordner wird dorthin verlinkt, wenn er noch fehlt (Symlink, Daten bleiben an ihrem Platz).
    if nur_gen and os.path.exists(os.path.join(d, "objekt.json")): genfile = json.load(open(os.path.join(d, "objekt.json")))["generator"].split()[-1]
    fd = os.path.join(root, obj["fotos_dir"]); os.makedirs(fd, exist_ok=True) if not (os.path.exists(fd) or nur_gen) else None
    fq = opt("--fotos-quelle")
    if not nur_gen and fq and os.path.isdir(fq) and os.path.isdir(fd) and not os.listdir(fd):
        os.rmdir(fd); os.symlink(os.path.abspath(fq), fd); print("fotos verlinkt:", fd, "->", fq)
    if not nur_gen: print("fotos_dir bereit:", fd, f"({len(os.listdir(fd)) if os.path.isdir(fd) else 0} Eintraege)")
    gp = os.path.join(root, genfile)
    if nur_gen and os.path.exists(gp):
        alt = open(gp).read()
        if "Generator-Rumpf (manifold3d)" not in alt or len(alt.splitlines()) > 100: print("Generator ist kein unberuehrter Rumpf - NICHT erneuert:", gp); return 3
        if "fenster_fuer_bau" in alt and "fenster_aus_json" in alt and "stl_schreiben" in alt and "oeffnungen_aus_json" in alt and "rueckwaende" in alt and "oeffnungen_aus_wandbild" in alt and "laube_aus_wandbild" in alt and "vorbauten_aus_json" in alt and "uhren_aus_json" in alt and "korrekturen_aus_json" in alt and "wolkenrest_koerper" in alt and "dach_aus_profil" in alt and "umgang_aus_json" in alt and "loch_gewaende_spaet" in alt and "bogen_gewaende_spaet" in alt and "hoehen_aus_json" in alt: print("Generator-Rumpf ist aktuell:", gp); return 0
        import time; os.replace(gp, gp + ".alt_" + time.strftime("%Y%m%d_%H%M")); print("alter Generator-Rumpf beiseitegelegt:", gp + ".alt_*")
    if not os.path.exists(gp):
        open(gp, "w").write(f'''#!/usr/bin/env python3
"""{ob}_gen.py - Generator-Rumpf (manifold3d). Jedes sichtbare Element meldet sich mit beleg(); Bau + Abnahme: tools/bauen_abnehmen.sh {ob}"""
import os, sys, json, numpy as np
from manifold3d import Manifold as M
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
from dach_bauen import gebaeude_aus_lod2, seiten_aus_rahmen
SCALE = float(os.environ.get("SCALE", "87")); K = 1000.0 / SCALE
OUT = os.path.join(HERE, "stl", "{ob}_1-{{SCALE:.0f}}.stl".format(SCALE=SCALE))
ELEMENTE = []
def beleg(seite, element, quelle, **masse): ELEMENTE.append(dict(seite=seite, element=element, quelle=quelle, **masse))
OBJ = os.path.join(HERE, "{ob}", "objekt.json"); obj = json.load(open(OBJ))
SEITEN = seiten_aus_rahmen(obj)
if obj.get("lod2", {{}}).get("id"):                    # Standard: LoD2-Grundriss + DOM1-Dach (dach.json, Nullstart-Schritt 'dach') - tools/dach_bauen.py
    koerper, belege, haupt = gebaeude_aus_lod2(OBJ)
    for b_ in belege: beleg(**b_)
    from bauteile import korrekturen_aus_json as _kw   # 21.11.2026: gemessener Wandversatz am GRUNDKOERPER, bevor Fenster/Relief daran gebaut werden (Abweichungsschleife)
    koerper, belege = _kw(koerper, os.path.join(HERE, "{ob}", "audit", "schleife_korrekturen.json"), art="wandversatz")
    for b_ in belege: beleg(**b_)
    # 17.11.2026 REIHENFOLGE: erst die erkannten Fenster in den Grundkoerper, dann das Relief mit offenen Fensterrechtecken (Relief zuerst liess jedes Fenster aus, vor dem eine Reliefplatte stand:
    # Kaufhaus 5 von 9). fenster_fuer_bau stellt 'Fenster' zurueck, in deren Rechteck das Netz fehlt (Vorbau/Erker davor) - Liste audit/fenster_bau.json.
    from fassaden_kette import anbauen, fenster_fuer_bau   # Fassaden-Kette (tools/fassaden_kette.py): Reliefs je Wand, falls audit/fassaden_kette.json da ist
    from bauteile import fenster_aus_json            # automatisch erkannte Fenster (Kettenstufe 'fenster' schreibt audit/fenster_auto.json)
    FJ = fenster_fuer_bau(OBJ, os.path.join(HERE, "{ob}", "audit", "fenster_auto.json"))
    koerper, bel_f = fenster_aus_json(koerper, FJ)
    koerper, belege = anbauen(koerper, OBJ, fenster=FJ)
    for b_ in belege + bel_f: beleg(**b_)
    from dach_bauen import ueber_traufe_nur_dach      # 17.11.2026: Fotodach (tools/dach_aus_fotos.py) - Reliefreste ueber der Traufe schweben sonst frei
    koerper, belege = ueber_traufe_nur_dach(koerper, OBJ)
    for b_ in belege: beleg(**b_)
    belege = bel_f                                   # aushoehlen nur, wenn Fenster gebaut wurden
    from bauteile import oeffnungen_aus_json         # 17.11.2026: automatisch erkannte Bogenoeffnungen / Tordurchfahrten (Kettenstufe 'fenster': tools/oeffnungen_bogen.py -> audit/oeffnungen_auto.json)
    koerper, belege_o, z_tor = oeffnungen_aus_json(koerper, os.path.join(HERE, "{ob}", "audit", "oeffnungen_auto.json"), innenwaende=obj.get("innenwaende"))      # 18.11.: Bogen vor einer Innenwand reicht bis zu ihr
    for b_ in belege_o: beleg(**b_)
    if obj.get("innenwaende") and os.environ.get("OHNE_LAUBE") != "1":   # 18.11.2026 (L2): Laube/Halle vor einer gemessenen Innenwand freilegen - Boegen = Umrisse aus dem Wandbild der Aussenwand
        from bauteile import laube_aus_wandbild
        koerper, bel_l = laube_aus_wandbild(koerper, obj["innenwaende"], os.path.join(HERE, "{ob}", "audit", "oeffnungen_aussen.json"), pfeiler_tiefe=float(obj.get("pfeiler_tiefe", 0.8)))
        for b_ in bel_l: beleg(**b_)
    IO_ = obj.get("innenwand_oeffnungen")            # 18.11.2026 (Kettenstufe 'bauplan', L2): Oeffnungen der Innenwaende aus ihrem Wandbild - nur wo die Innenwand freiliegt, VOR aushoehlen
    if IO_ and os.environ.get("OHNE_INNENWAND") != "1":
        from bauteile import oeffnungen_aus_wandbild
        koerper, bel_i = oeffnungen_aus_wandbild(koerper, os.path.join(HERE, "{ob}", IO_["datei"]), ncc_min=IO_.get("ncc_min", 0.2), ersatz={{k: tuple(v) for k, v in IO_.get("ersatz", {{}}).items()}}, nur_frei=True)
        for b_ in bel_i: beleg(**b_)
    if os.environ.get("OHNE_UMGANG") != "1":          # 21.11.2026: offener Umgang unter der Traufe (Kettenstufe 'bauplan': tools/umgang_aus_fotos.py -> audit/umgang_auto.json), VOR aushoehlen
        from bauteile import umgang_aus_json
        koerper, bel_ug = umgang_aus_json(koerper, os.path.join(HERE, "{ob}", "audit", "umgang_auto.json"))
        for b_ in bel_ug: beleg(**b_)
    from bauteile import korrekturen_aus_json          # 21.11.2026: Korrekturen der Abweichungsschleife (tools/ebenen_schleife.py -> audit/schleife_korrekturen.json), VOR dem Aushoehlen (Abtragen am hohlen Koerper wuerde die 1,2-mm-Wand durchschneiden)
    koerper, bel_k = korrekturen_aus_json(koerper, os.path.join(HERE, "{ob}", "audit", "schleife_korrekturen.json"), ohne="wandversatz")
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
        koerper, bel_v = vorbauten_aus_json(koerper, os.path.join(HERE, "{ob}", "audit", "vorbauten_auto.json"))
        for b_ in bel_v: beleg(**b_)
        from bauteile import wolkenrest_koerper           # 21.11.2026: Koerper aus dem Rest der dichten Wolke (rund, Kasten, Ring/Band, Stab; tools/koerper_schleife.py -> audit/koerper_auto.json, nur angenommene)
        koerper, bel_d = wolkenrest_koerper(koerper, os.path.join(HERE, "{ob}", "audit", "koerper_auto.json"))
        for b_ in bel_d: beleg(**b_)
        from bauteile import dach_aus_profil               # 21.11.2026: Dach mit Ueberstand/Laternenkoerper als Schichtprofil der dichten Wolke (tools/dach_profil_wolke.py -> audit/dach_profil.json)
        koerper, bel_p = dach_aus_profil(koerper, os.path.join(HERE, "{ob}", "audit", "dach_profil.json"))
        for b_ in bel_p: beleg(**b_)
        from bauteile import uhren_aus_json            # 21.11.2026: Turmuhren (Kettenstufe 'bauplan': tools/uhren_wandbild.py -> audit/uhren_auto.json)
        koerper, bel_u = uhren_aus_json(koerper, os.path.join(HERE, "{ob}", "audit", "uhren_auto.json"))
        for b_ in bel_u: beleg(**b_)
    from bauteile import loch_gewaende_spaet          # 23.11.2026: Loch/Gewaende (tools/loch_gewaende.py) auf der ECHTEN Oberflaeche nach allen Anbauten (Turm/Vorbau davor)
    koerper, bel_lg = loch_gewaende_spaet(koerper, FJ)
    for b_ in bel_lg: beleg(**b_)
    from bauteile import bogen_gewaende_spaet         # 24.11.2026 (1122w): Gewaende-Band um Tor-/Bogenoeffnungen (tools/bogen_gewaende.py -> gewaende_band in audit/oeffnungen_auto.json), echte Oberflaeche
    koerper, bel_bg = bogen_gewaende_spaet(koerper, os.path.join(HERE, "{ob}", "audit", "oeffnungen_auto.json"))
    for b_ in bel_bg: beleg(**b_)
    from bauteile import hoehen_aus_json              # 24.11.2026: Hoehen-Angleich waagerechter Bauteile (Kettenstufe 'bauplan_hoehen': tools/hoehen_angleich.py -> audit/hoehen_angleich.json), LETZTER Bauschritt
    koerper, bel_h = hoehen_aus_json(koerper, os.path.join(HERE, "{ob}", "audit", "hoehen_angleich.json"))
    for b_ in bel_h: beleg(**b_)
    tl_ = koerper.decompose()                        # Null-Volumen-Splitter entfernen (wie Kaufhaus-Generator 17.11.); echte schwebende Teile bleiben und fallen in der Pruefung auf
    if len(tl_) > 1 and any(t_.volume() < 1e-5 for t_ in tl_):
        koerper = M.batch_boolean([t_ for t_ in tl_ if t_.volume() >= 1e-5], __import__("manifold3d").OpType.Add); beleg("wand", "%d Null-Volumen-Splitter entfernt" % sum(1 for t_ in tl_ if t_.volume() < 1e-5), "Generator (decompose, Volumen < 1e-5 m3)")
    cu, cv = haupt.mean(0); model = koerper.scale((K, K, K))   # 15.11.2026: NICHT zentrieren - STL bleibt im Rahmen (objekt.json rahmen); die Fotowerkzeuge (zentrierung 'achse') erwarten STL = Rahmen, sonst liegt das Modell um (cu, cv) neben Kameras/Wolke
else:
    H = {hoehe or 10.0}                               # Gesamthoehe (m) - Quelle in masstabelle.json
    beleg("dach", "Grundkoerper", "ANNAHME: Rumpf ohne LoD2 (objekt.json lod2.id fehlt)", hoehe=H)
    model = M.cube((8.0, 8.0, H)).translate((-4.0, -4.0, 0.0)).scale((K, K, K))
from bauteile import stl_schreiben          # verschweisst Ecken, entfernt Lappen und Kruemel (16.11.2026: die Vorlage schrieb selbst und liess Zwei-Flaechen-Kruemel als Einzelkoerper stehen)
stl_schreiben(model, OUT, b"{ob}")
json.dump([dict(e, seite_name=SEITEN.get(e["seite"], e["seite"])) for e in ELEMENTE], open(os.path.join(HERE, "{ob}", "elemente.json"), "w"), indent=1, ensure_ascii=False)
print("->", OUT)
''')
        print("Generator-Rumpf angelegt:", gp)
    print(f"""
Pflichtablauf (modelle/METHODE_MASSTABELLE.md):
 1. Dokumente -> Gesamthoehe/Grundmasse als Zeilen (quelltyp dokument)      2. LoD2/DGM1 -> Grundriss, Traufe/First (lod2)
 3. DOM1 -> Dachform grob (laser_dom1, nur Flaechen >= 3 m)                   4. Fotos je Seite in objekt.json/fotos (seite, silhouette_frei), Vollbild fuer duenne Bauteile
 5. tools/bauen_abnehmen.sh {ob}  -> Pruefstand + audit/seiten.jpg ANSEHEN     6. Beobachtung -> fehlschlagende Zeile -> Generator (beleg()!) -> gruen -> Commit""")

if __name__ == "__main__":
    sys.exit(main() or 0)
