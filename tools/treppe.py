#!/usr/bin/env python3
"""treppe.py - mehrstufige Treppe: grob rechnen, Guete messen, entscheiden ob die naechste Stufe sich lohnt (Register BU, Plan 3.6).

Gedanke: fuer ein NEUES Objekt nicht gleich die teuerste Stufe rechnen. Stufe fuer Stufe (grob -> mittel -> fein -> Video ...) nullstart.py laufen lassen, nach jeder Stufe die
Pruefungen auswerten und nur weitermachen, solange der Gewinn ueber dem Rauschen liegt. Am Ende steht, was die Treppe gebracht hat und welche Merkmale offen bleiben (naechster Hebel = meist DATEN).
Guete = Quote bestandener Pruefungen, die in ALLEN bisherigen Stufen vorkommen (Bandpruefungen tragen das Fenster im Namen und existieren je Lauf anders, vgl. sweetspot.py),
getrennt nach Quelltyp: UNABHAENGIG (lod2, laser_dom1, dokument) zaehlt mehr als Messungen aus denselben Fotos. ANNAHME: Rauschband +-5 Pruefungen (Register BL: +-3; die 4 gleich konfigurierten Nachtlaeufe 3.11. streuten auf den gemeinsamen Pruefungen aber 43..49, also 6 -> Standard 5).
Entscheidung: Gewinn der unabhaengigen Quote UND der Gesamtzahl gegen die beste fruehere Stufe; <= Rauschband in --geduld Stufen hintereinander -> STOPP (kein Gewinn mehr ueber dem Zufall).
Grenzen (ehrlich): bei einem neuen Objekt hat die Masstabelle anfangs wenige unabhaengige Sollwerte (Hoehe aus Dokument, LoD2, DOM1) -> die Guete ist dann blind fuer alles andere.
Ein Gewinn kleiner als das Rauschen ist keine Entscheidung; mehrere Laeufe je Stufe (--wiederhole) verkleinern es nicht automatisch, zeigen aber die Streuung.

  python3 -I tools/treppe.py modelle/<objekt>/objekt.json --ziel <objekt>_null [--stufen treppe.json] [--rauschen 3] [--geduld 1] [--trocken]
  python3 -I tools/treppe.py modelle/<objekt>/objekt.json --auswerten <ordner mit stufe_*/ oder lauf_*/>      (nur auswerten, nichts rechnen)
Stufen-Datei (JSON, Standard modelle/<objekt>/treppe.json, sonst eingebaute Leiter): {"stufen": [{"name": "grob", "args": "--stufe grob --grob-px 800"}, ...]}
Schreibt <datenplatte-neben-ziel>/treppe_<datum>/stufe_<name>/ (Pruefbericht, Masstabelle, Bericht) und modelle/<objekt>/treppe_verlauf.json + TREPPE.md.
"""
import sys, os, json, glob, shutil, subprocess, argparse, time, collections

UNABH = {"lod2", "laser_dom1", "dokument"}
STANDARD = [{"name": "grob", "args": "--stufe grob --grob-px 800"}, {"name": "mittel", "args": "--stufe grob --grob-px 1000"},
            {"name": "fein", "args": "--stufe voll"}, {"name": "video", "args": "--stufe voll --videos"}]

def lade(d):
    """Pruefbericht + Masstabelle eines Stufenordners -> {name: (ok, quelltyp, merkmal)}."""
    pb = json.load(open(os.path.join(d, "pruefbericht.json"))); tab = {}
    mp = os.path.join(d, "masstabelle.json")
    if os.path.exists(mp):
        for r in json.load(open(mp)).get("pruefungen", []): tab[r["name"]] = (r.get("quelltyp", "?"), r.get("merkmal", "?"))
    return {x["name"]: (bool(x["ok"]),) + tab.get(x["name"], ("?", "?")) for x in pb["pruefungen"]}

def bewerte(ordner, rauschen=5, geduld=1):
    """Auswertung ueber Stufenordner in Reihenfolge; liefert Zeilen und Entscheidung. Vergleich nur auf gemeinsamen Pruefungen."""
    R = [(os.path.basename(d), lade(d)) for d in ordner]
    gemeinsam = set.intersection(*[set(r) for _, r in R]) if R else set()
    zeilen = []; beste_ges = beste_unab = -1; ohne_gewinn = 0; stopp = None
    for i, (n, r) in enumerate(R):
        ges = sum(r[k][0] for k in gemeinsam); un = sum(r[k][0] for k in gemeinsam if r[k][1] in UNABH); nun = sum(1 for k in gemeinsam if r[k][1] in UNABH)
        gewinn = None if i == 0 else (ges - beste_ges, un - beste_unab)
        if i > 0:
            if gewinn[0] <= rauschen and gewinn[1] <= rauschen: ohne_gewinn += 1
            else: ohne_gewinn = 0
            if ohne_gewinn >= geduld and stopp is None: stopp = n
        beste_ges = max(beste_ges, ges); beste_unab = max(beste_unab, un)
        zeilen.append(dict(stufe=n, gesamt=f"{ges}/{len(gemeinsam)}", unabhaengig=f"{un}/{nun}", gewinn=gewinn, alle=f"{sum(v[0] for v in r.values())}/{len(r)}"))
    offen = collections.Counter()
    if R:
        for k, v in R[-1][1].items():
            if not v[0]: offen[v[2]] += 1
    return dict(zeilen=zeilen, gemeinsame_pruefungen=len(gemeinsam), stopp_nach=stopp, rauschband=rauschen, offene_merkmale_letzte_stufe=dict(offen.most_common()))

HEBEL = {"schlankheit": "Fotos/Ansichten aus Entfernung bzw. von oben (Silhouette)", "hoehe": "amtliche Hoehen (LoD2/DOM1) oder Fotos mit Massstab", "lage": "mehr Bodenanker (LoD2-Ecken, Picks)",
         "relief": "Nahaufnahmen (Detailserien)", "grundriss": "Fotos aus mehreren Richtungen um das Objekt / amtlicher Grundriss (LoD2)", "hoehe_flaeche": "DOM1/LoD2-Flaechenhoehen, Fotos von oben", "verhaeltnis": "Fotos mit bekannter Pose, Silhouettenverhaeltnisse", "form": "Fotos aus anderen Richtungen / hoeherer Standort", "?": "Merkmal in der Masstabelle benennen"}

def bericht(erg, ordner):
    M = ["# Treppe (automatisch)", "", f"Gemeinsame Pruefungen aller Stufen: {erg['gemeinsame_pruefungen']}, Rauschband +-{erg['rauschband']}", "",
         "| Stufe | gesamt (gemeinsam) | davon unabhaengig | Gewinn ges/unabh | alle Pruefungen der Stufe |", "|---|---|---|---|---|"]
    for z in erg["zeilen"]: M.append(f"| {z['stufe']} | {z['gesamt']} | {z['unabhaengig']} | {z['gewinn'] if z['gewinn'] else '-'} | {z['alle']} |")
    M += ["", f"**Entscheidung:** " + (f"STOPP nach Stufe '{erg['stopp_nach']}' - kein Gewinn ueber dem Rauschen mehr." if erg["stopp_nach"] else "Gewinn bis zur letzten Stufe ueber dem Rauschen - weitere Stufe lohnt sich.")]
    if erg["offene_merkmale_letzte_stufe"]:
        M += ["", "Offene (nicht bestandene) Pruefungen der letzten Stufe nach Merkmal, mit naechstem Hebel:"] + [f"- {k}: {v} -> {HEBEL.get(k, HEBEL['?'])}" for k, v in erg["offene_merkmale_letzte_stufe"].items()]
    return "\n".join(M) + "\n"

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--ziel"); ap.add_argument("--stufen"); ap.add_argument("--rauschen", type=int, default=5); ap.add_argument("--geduld", type=int, default=1)
    ap.add_argument("--auswerten"); ap.add_argument("--trocken", action="store_true"); ap.add_argument("--wiederhole", type=int, default=1); a = ap.parse_args()
    od = os.path.dirname(os.path.abspath(a.objekt)); repo = os.path.dirname(os.path.dirname(od))
    if a.auswerten:
        ordner = sorted(d for d in glob.glob(os.path.join(a.auswerten, "*")) if os.path.exists(os.path.join(d, "pruefbericht.json")))
        if not ordner: sys.exit("keine Stufenordner mit pruefbericht.json")
        erg = bewerte(ordner, a.rauschen, a.geduld); print(bericht(erg, ordner)); return
    if not a.ziel: sys.exit("--ziel fehlt")
    sf = a.stufen or os.path.join(od, "treppe.json"); stufen = json.load(open(sf))["stufen"] if os.path.exists(sf) else STANDARD
    zd = os.path.realpath(os.path.join(repo, "modelle", a.ziel)); basis = os.path.join(os.path.dirname(zd), f"treppe_{time.strftime('%Y%m%d_%H%M')}")
    if a.trocken:
        for s in stufen: print(f"{s['name']:8} x{a.wiederhole}: tools/nullstart.py {a.objekt} --ziel {a.ziel} {s['args']}")
        print("Ziel:", basis); return
    os.makedirs(basis, exist_ok=True); ordner = []
    for s in stufen:
        for w in range(a.wiederhole):
            name = f"{s['name']}" + (f"_{w + 1}" if a.wiederhole > 1 else ""); d = os.path.join(basis, "stufe_" + name); os.makedirs(d, exist_ok=True)
            cmd = [sys.executable, "-I", "tools/nullstart.py", a.objekt, "--ziel", a.ziel] + s["args"].split(); t0 = time.time(); print(f"== {name}: {' '.join(cmd[2:])}", flush=True)
            with open(os.path.join(d, "lauf.log"), "w") as f: rc = subprocess.run(cmd, cwd=repo, stdout=f, stderr=subprocess.STDOUT).returncode
            for fn in ("pruefbericht.json", "masstabelle.json", "masse.json", "nullstart_bericht.json"):
                if os.path.exists(os.path.join(zd, fn)): shutil.copy2(os.path.join(zd, fn), d)
            print(f"   rc {rc}, {time.time() - t0:.0f} s", flush=True)
            if rc != 0 or not os.path.exists(os.path.join(d, "pruefbericht.json")): print("   Stufe fehlgeschlagen - Treppe endet", flush=True); break
            ordner.append(d)
        else:
            erg = bewerte(ordner, a.rauschen, a.geduld)
            if erg["stopp_nach"]: print(f"STOPP nach '{erg['stopp_nach']}': kein Gewinn ueber dem Rauschen", flush=True); break
            continue
        break
    if not ordner: sys.exit("keine Stufe lief durch")
    erg = bewerte(ordner, a.rauschen, a.geduld); txt = bericht(erg, ordner); open(os.path.join(basis, "TREPPE.md"), "w").write(txt); print(txt)
    vp = os.path.join(od, "treppe_verlauf.json"); v = json.load(open(vp)) if os.path.exists(vp) else []
    v.append(dict(datum=time.strftime("%F %T"), ordner=basis, **erg)); json.dump(v, open(vp, "w"), indent=1, ensure_ascii=False)

if __name__ == "__main__":
    main()
