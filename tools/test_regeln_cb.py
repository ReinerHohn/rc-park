#!/usr/bin/env python3
"""test_regeln_cb.py - Gegenbeweis zu Register CB (2026-11-03): der Fehler 'zwei Boegen + Zwischenpfeiler je Flaeche' darf sich nicht wiederholen.

Baut in einem Wegwerf-Verzeichnis Kopien der Martinstor-Tabelle und fuehrt die FEHLER VON DAMALS absichtlich wieder ein; der Pruefstand MUSS jeden ablehnen:
  T1 Etikettenumgehung  : Oeffnungs-Anzahl mit Merkmal 'schlankheit' + Quelle sfm_bodenanker (wie damals)            -> Exit 2
  T2 Selbstbezug        : Oeffnungs-Anzahl, Merkmal 'anzahl', Protokoll = Datei, die der Generator selbst liest      -> Exit 2
  T3 Zaehlwiderspruch   : Soll [2,2], Zaehlprotokoll Z-043-001 sagt 1                                               -> Exit 2
  T4 Modellfehler       : Modell mit 2 Oeffnungen je Flaeche (STL aus dem Git-Stand VOR dem Fix) gegen Foto-Zaehlung  -> Exit 1 (FEHLER, nicht 'bestanden')
  T5 Zaehlprotokoll     : foto_zaehlung.py bricht ab, wenn voll sichtbare Flaechen verschieden viele Oeffnungen haben -> Exit != 0
  T6 Gutfall            : unveraenderte Tabelle + aktuelles STL                                                     -> Exit 0
Exit 0 = alle Gegenproben bestanden (die Fehler werden zuverlaessig gefangen).
  /media/oem/scan/venv-seg/bin/python -W ignore -I tools/test_regeln_cb.py [modelle/martinstor/objekt.json]
"""
import sys, os, json, shutil, subprocess, tempfile

HIER = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HIER); PY = sys.executable
OBJ = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "modelle/martinstor/objekt.json")
NAME_CB = "Ecktuermchen Arkadenband: Oeffnungen je Achteckflaeche (Foto-Zaehlung 043)"
if not any(p.get("name") == NAME_CB for p in json.load(open(os.path.join(os.path.dirname(os.path.abspath(OBJ)), "masstabelle.json"))).get("pruefungen", [])):
    # Gegenproben pruefen den PRUEFSTAND (Werkzeug), nicht das Objekt; sie brauchen die Martinstor-Zaehlpruefung 043. Objekte ohne sie
    # (kaufhaus_null4, 2026-11-04: StopIteration in bauen_abnehmen) laufen die Gegenproben am Martinstor.
    print(f"  Hinweis: {os.path.basename(os.path.dirname(os.path.abspath(OBJ)))} hat keine Zaehlpruefung '{NAME_CB[:40]}...' -> Gegenproben am Martinstor (Werkzeugtest)")
    OBJ = os.path.join(ROOT, "modelle/martinstor/objekt.json")

def lauf(args, **k):
    r = subprocess.run(args, capture_output=True, text=True, cwd=ROOT, **k); return r.returncode, r.stdout + r.stderr

def bauen(tmp, mut=None, stl=None):
    """Wegwerf-Wurzel mit Kopie von objekt.json/masstabelle.json/masse.json/messprotokoll; Generator + STL per Symlink/Kopie."""
    o = json.load(open(OBJ)); od = os.path.dirname(OBJ); name = os.path.basename(od)
    d = os.path.join(tmp, "modelle", name); os.makedirs(d); os.makedirs(os.path.join(tmp, "modelle", "stl"), exist_ok=True)
    for f in ("objekt.json", "masse.json"): shutil.copy(os.path.join(od, f), d)
    shutil.copytree(os.path.join(od, "messprotokoll"), os.path.join(d, "messprotokoll"))
    for f in os.listdir(os.path.join(ROOT, "modelle")):
        p = os.path.join(ROOT, "modelle", f)
        if f.endswith(".py"): os.symlink(p, os.path.join(tmp, "modelle", f))
    for f in ("profile_baender_tuermchen.json", "profile_generator.json", "fassade.json", "elemente.json", "anker3d.json"):
        if os.path.exists(os.path.join(od, f)): shutil.copy(os.path.join(od, f), d)
    t = json.load(open(os.path.join(od, "masstabelle.json")))
    if mut: mut(t)
    json.dump(t, open(os.path.join(d, "masstabelle.json"), "w"), indent=1, ensure_ascii=False)
    sp = os.path.join(ROOT, o["stl"]); shutil.copy(stl or sp, os.path.join(tmp, o["stl"]))
    return os.path.join(d, "objekt.json")

def pruefen(mut=None, stl=None):
    with tempfile.TemporaryDirectory() as tmp:
        return lauf([PY, "-W", "ignore", "-I", os.path.join(HIER, "pruefstand.py"), bauen(tmp, mut, stl)])

def main():
    erg = []
    NAME = "Ecktuermchen Arkadenband: Oeffnungen je Achteckflaeche (Foto-Zaehlung 043)"
    def foto(t): return next(p for p in t["pruefungen"] if p["name"] == NAME)
    def t1(t): p = foto(t); p.update(merkmal="schlankheit", quelltyp="sfm_bodenanker", protokoll="profile_baender_tuermchen.json")
    def t2(t): p = foto(t); p.update(merkmal="anzahl", quelltyp="foto_vollbild", protokoll="profile_baender_tuermchen.json")
    def t3(t): foto(t)["soll"] = [2, 2]
    rc, out = pruefen(t1); erg.append(("T1 Etikettenumgehung abgelehnt", rc == 2 and "Etikettenumgehung" in out, rc))
    rc, out = pruefen(t2); erg.append(("T2 Selbstbezug abgelehnt", rc == 2 and "SELBSTBEZUG" in out, rc))
    rc, out = pruefen(t3); erg.append(("T3 Zaehlwiderspruch abgelehnt", rc == 2 and "Zaehlprotokoll" in out, rc))
    # T4: STL vor dem Fix aus Git (Commit 615f721) - zeigt, dass die Foto-Pruefung das alte Modell FAENGT
    alt = tempfile.NamedTemporaryFile(suffix=".stl", delete=False); alt.close()
    o = json.load(open(OBJ)); g = subprocess.run(["git", "show", "615f721:" + o["stl"]], capture_output=True, cwd=ROOT)   # STL VOR dem CB-Fix (2 Oeffnungen; seit 0902260 ist HEAD schon der Fix -> T4 fiel immer durch, 2026-11-04)
    if g.returncode == 0 and len(g.stdout) > 1000:
        open(alt.name, "wb").write(g.stdout)
        rc, out = pruefen(None, alt.name); erg.append(("T4 Modell mit 2 Oeffnungen faellt durch (Exit 1, FEHLER-Zeile)", rc == 1 and "FEHLER  Ecktuermchen Arkadenband" in out, rc))
    else: erg.append(("T4 uebersprungen (kein Git-STL)", True, None))
    os.unlink(alt.name)
    # T5: Zaehlwerkzeug lehnt widerspruechliche Zaehlung ab
    with tempfile.TemporaryDirectory() as tmp:
        oj = bauen(tmp); rc, out = lauf([PY, "-W", "ignore", "-I", os.path.join(HIER, "foto_zaehlung.py"), oj, "043", "--was", "test", "--punkt", "A:voll:100,100", "--punkt", "A:voll:150,100", "--punkt", "B:voll:300,100"])
    erg.append(("T5 widerspruechliche Zaehlung abgelehnt", rc != 0 and "widerspruechlich" in out, rc))
    rc, out = pruefen(); erg.append(("T6 Gutfall besteht", rc == 0, rc))
    if rc != 0: print("T6-Ausgabe (Ende):\n" + out[-1500:])   # 10.11.: T6 fiel unter Volllast ohne sichtbaren Grund (OOM?) - Ursache muss im Log stehen
    bad = 0
    for n, ok, rc in erg: print(f"  {'OK    ' if ok else 'FEHLER'}  {n}  (Exit {rc})"); bad += 0 if ok else 1
    print("test_regeln_cb:", "alle Gegenproben bestanden" if not bad else f"{bad} Gegenprobe(n) FEHLGESCHLAGEN"); sys.exit(1 if bad else 0)

if __name__ == "__main__":
    main()
