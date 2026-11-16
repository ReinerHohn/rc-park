#!/usr/bin/env python3
"""objekt_anlegen.py - neues Bauwerk in den Pflichtrahmen aufnehmen (modelle/METHODE_MASSTABELLE.md), ohne Abschreiben.

  python3 tools/objekt_anlegen.py <objekt> --name "Schwabentor" --generator "SCALE=87 ~/.venvs/rcpark/bin/python modelle/schwabentor_gen.py" \\
      --stl modelle/stl/schwabentor_1-87.stl --fotos daten/schwabentor/fotos [--hoehe 40 --hoehe-quelle "Wikipedia ..."]
Legt an: modelle/<objekt>/objekt.json, masstabelle.json (Startzeilen: Gesamthoehe aus Dokument, wasserdicht, ein Koerper; Beobachtung "Quellen sichten"),
einen Generator-Rumpf mit beleg()-Register (falls die Generatordatei fehlt) und druckt den Pflichtablauf.
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
    for fn, data in (("objekt.json", obj), ("masstabelle.json", tab)):
        p = os.path.join(d, fn)
        if os.path.exists(p): print("vorhanden, nicht ueberschrieben:", p); continue
        json.dump(data, open(p, "w"), indent=1, ensure_ascii=False); print("angelegt:", p)
    # Fotoordner aus objekt.json["fotos_dir"] anlegen (Lehre Schwabentor 13.11.: Pfad zeigte ins Leere, kein Werkzeug fand Fotos).
    # --fotos-quelle DIR: Fotoordner wird dorthin verlinkt, wenn er noch fehlt (Symlink, Daten bleiben an ihrem Platz).
    fd = os.path.join(root, obj["fotos_dir"]); os.makedirs(fd, exist_ok=True) if not os.path.exists(fd) else None
    fq = opt("--fotos-quelle")
    if fq and os.path.isdir(fq) and os.path.isdir(fd) and not os.listdir(fd):
        os.rmdir(fd); os.symlink(os.path.abspath(fq), fd); print("fotos verlinkt:", fd, "->", fq)
    print("fotos_dir bereit:", fd, f"({len(os.listdir(fd)) if os.path.isdir(fd) else 0} Eintraege)")
    gp = os.path.join(root, genfile)
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
    from fassaden_kette import anbauen                 # Fassaden-Kette (tools/fassaden_kette.py): Reliefs je Wand, falls audit/fassaden_kette.json da ist
    koerper, belege = anbauen(koerper, OBJ)
    for b_ in belege: beleg(**b_)
    from bauteile import fenster_aus_json            # automatisch erkannte Fenster (Kettenstufe 'fenster' schreibt audit/fenster_auto.json)
    koerper, belege = fenster_aus_json(koerper, os.path.join(HERE, "{ob}", "audit", "fenster_auto.json"))
    for b_ in belege: beleg(**b_)
    if belege and os.environ.get("OHNE_HOHL") != "1":        # 16.11.2026 Nutzer: Fenster muessen echte Loecher sein -> Gebaeude hohl, erkannte Fenster durchgebrochen
        from bauteile import aushoehlen
        koerper, n_offen, v_hohl = aushoehlen(koerper, d=float(os.environ.get("WAND_MM", "1.2")) * float(os.environ.get("SCALE", "87")) / 1000.0)
        beleg("wand", "Gebaeude hohl, %d Fenster durchgebrochen" % n_offen, "bauteile.aushoehlen auf den automatisch erkannten Fenstern", hinweis="Wandstaerke 1,2 mm im Druck (WAND_MM, duennste druckstabile Wand), Innenraum ohne Decken und Zwischenwaende")
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
    main()
