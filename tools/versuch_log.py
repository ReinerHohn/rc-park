#!/usr/bin/env python3
"""versuch_log.py - AUTOMATISCHES Versuchslog (Nutzerauftrag 7.11.: nichts doppelt versuchen, Fehlschlaege mitschreiben).
Bibliothek (von Werkzeugen am Ende eines Laufs aufgerufen) + CLI.
  import versuch_log as VL; VL.log(objekt_json, werkzeug, args, ergebnis={...kennzahlen...}, status="ok"|"keine_werte"|"fehler", notiz="")
  python3 tools/versuch_log.py liste OBJEKT_JSON [--suche TEXT] [--n 30]      # VOR einem neuen Versuch ansehen
  python3 tools/versuch_log.py eintragen OBJEKT_JSON WERKZEUG --status fehler --notiz "..." [--ergebnis x.json] [--args "..."]
Schreibt modelle/<objekt>/versuche_auto.jsonl (eine Zeile je Lauf, nur anhaengen) und erzeugt modelle/<objekt>/VERSUCHE_AUTO.md (Tabelle der letzten 200).
Prueft automatisch: gleiche Kennzahlen wie ein frueherer Lauf mit ANDEREN Argumenten -> Warnung 'IDENTISCH_MIT_VORLAUF' (haette BS7 gefangen: Raster-Lauf = Punkt-Lauf).
Ersetzt NICHT das handgeschriebene Register (Deutung/Ursache), liefert die lueckenlose Rohspur."""
import os, sys, json, time, hashlib, argparse

def _pfade(objekt_json):
    od = os.path.dirname(os.path.abspath(objekt_json)); return os.path.join(od, "versuche_auto.jsonl"), os.path.join(od, "VERSUCHE_AUTO.md")

def _kennung(ergebnis):
    """Hash der gerundeten Zahlen (4 Stellen), unabhaengig von Schluesselreihenfolge."""
    def rd(x):
        if isinstance(x, float): return round(x, 4)
        if isinstance(x, dict): return {k: rd(v) for k, v in sorted(x.items())}
        if isinstance(x, (list, tuple)): return [rd(v) for v in x]
        return x
    return hashlib.sha1(json.dumps(rd(ergebnis), sort_keys=True, default=str).encode()).hexdigest()[:12]

def lesen(objekt_json):
    jp, _ = _pfade(objekt_json); z = []
    if os.path.exists(jp):
        for l in open(jp):
            try: z.append(json.loads(l))
            except Exception: pass
    return z

def log(objekt_json, werkzeug, args, ergebnis=None, status="ok", notiz=""):
    jp, mp = _pfade(objekt_json); alt = lesen(objekt_json); ergebnis = ergebnis or {}
    kn = _kennung(ergebnis) if ergebnis else None; a = " ".join(map(str, args)) if not isinstance(args, str) else args
    warn = None
    if kn:
        for z in reversed(alt):
            if z.get("kennung") == kn and z.get("werkzeug") == werkzeug and z.get("args") != a:
                warn = f"IDENTISCH_MIT_VORLAUF {z['zeit']} (andere Argumente) - Option wirkungslos? Ergebnis nicht als neues Mass werten"; break
    z = dict(zeit=time.strftime("%Y-%m-%d %H:%M:%S"), werkzeug=werkzeug, args=a, status=status, notiz=notiz, kennung=kn, ergebnis=ergebnis, warnung=warn)
    with open(jp, "a") as f: f.write(json.dumps(z, ensure_ascii=False, default=str) + "\n")
    _md(objekt_json)
    if warn: print("VERSUCH_LOG WARNUNG:", warn, flush=True)
    return z

def _md(objekt_json):
    _, mp = _pfade(objekt_json); z = lesen(objekt_json)[-200:]
    L = ["# Versuche (automatisch, nicht von Hand aendern)", "Quelle: versuche_auto.jsonl; Deutung/Ursache im modelle/VERSUCHSREGISTER_*.md und modelle/NICHTS_GEBRACHT.md", "",
         "| Zeit | Werkzeug | Status | Warnung | Notiz | Argumente |", "|---|---|---|---|---|---|"]
    for e in reversed(z): L.append(f"| {e['zeit']} | {e['werkzeug']} | {e['status']} | {e.get('warnung') or ''} | {(e.get('notiz') or '')[:80]} | `{(e.get('args') or '')[:120]}` |")
    open(mp, "w").write("\n".join(L) + "\n")

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); sp = ap.add_subparsers(dest="cmd", required=True)
    l = sp.add_parser("liste"); l.add_argument("objekt"); l.add_argument("--suche", default=""); l.add_argument("--n", type=int, default=30)
    e = sp.add_parser("eintragen"); e.add_argument("objekt"); e.add_argument("werkzeug"); e.add_argument("--status", default="ok"); e.add_argument("--notiz", default=""); e.add_argument("--ergebnis"); e.add_argument("--args", default="")
    a = ap.parse_args()
    if a.cmd == "liste":
        z = [x for x in lesen(a.objekt) if a.suche.lower() in json.dumps(x, ensure_ascii=False).lower()][-a.n:]
        for x in z: print(f"{x['zeit']} {x['werkzeug']:22s} {x['status']:12s} {x.get('warnung') or ''} {x.get('notiz') or ''} | {(x.get('args') or '')[:100]}")
        print(f"{len(z)} Eintraege")
    else:
        log(a.objekt, a.werkzeug, a.args, json.load(open(a.ergebnis)) if a.ergebnis else None, a.status, a.notiz)
