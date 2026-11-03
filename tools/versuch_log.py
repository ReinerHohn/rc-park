#!/usr/bin/env python3
"""versuch_log.py - JEDEN Versuch maschinenlesbar festhalten und daraus lernen (Register BU).

Das Register (VERSUCHSREGISTER_MARTINSTOR.md) ist Text fuer Menschen; hier steht dieselbe Information als Zeile pro Versuch in modelle/<objekt>/versuche.jsonl, damit man filtern und
auswerten kann: was wurde geaendert, mit welchen Parametern, welche Zahlen kamen heraus, was wurde gelernt, welche Folge. Ein Versuch ohne 'lehre' ist unvollstaendig.
  python3 -I tools/versuch_log.py modelle/<objekt>/objekt.json --neu --id kamera-opencv-drohne --frage "..." --aenderung "..." [--param k=v ...] [--metrik k=v ...] \\
        --ergebnis besser|schlechter|gleich|unklar --lehre "..." [--folge "..."] [--belegt ein_lauf|mehrere_laeufe|konsens]
  python3 -I tools/versuch_log.py modelle/<objekt>/objekt.json --zeige [--ergebnis schlechter] [--suche wort]     (Liste)
  python3 -I tools/versuch_log.py modelle/<objekt>/objekt.json --lehren                                          (alle Lehren, 'belegt' kenntlich: ein_lauf ist keine Wahrheit)
"""
import sys, os, json, time, argparse

def lade(p): return [json.loads(z) for z in open(p) if z.strip()] if os.path.exists(p) else []

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--neu", action="store_true"); ap.add_argument("--zeige", action="store_true"); ap.add_argument("--lehren", action="store_true")
    ap.add_argument("--id"); ap.add_argument("--frage"); ap.add_argument("--aenderung"); ap.add_argument("--param", nargs="*", default=[]); ap.add_argument("--metrik", nargs="*", default=[])
    ap.add_argument("--ergebnis", choices=["besser", "schlechter", "gleich", "unklar"]); ap.add_argument("--lehre"); ap.add_argument("--folge", default=""); ap.add_argument("--belegt", default="ein_lauf", choices=["ein_lauf", "mehrere_laeufe", "konsens"])
    ap.add_argument("--suche"); a = ap.parse_args(); p = os.path.join(os.path.dirname(os.path.abspath(a.objekt)), "versuche.jsonl"); V = lade(p)
    kv = lambda L: dict(x.split("=", 1) for x in L)
    if a.neu:
        for k in ("id", "frage", "aenderung", "ergebnis", "lehre"):
            if not getattr(a, k): sys.exit(f"--{k} fehlt (ein Versuch ohne Lehre ist unvollstaendig)")
        if any(v["id"] == a.id for v in V): sys.exit(f"id {a.id} existiert schon")
        e = dict(datum=time.strftime("%F %T"), id=a.id, frage=a.frage, aenderung=a.aenderung, param=kv(a.param), metrik=kv(a.metrik), ergebnis=a.ergebnis, lehre=a.lehre, folge=a.folge, belegt=a.belegt)
        open(p, "a").write(json.dumps(e, ensure_ascii=False) + "\n"); print("protokolliert:", a.id, f"({len(V) + 1} Versuche)"); return
    sel = [v for v in V if (not a.ergebnis or v["ergebnis"] == a.ergebnis) and (not a.suche or a.suche.lower() in json.dumps(v, ensure_ascii=False).lower())]
    if a.lehren:
        for v in sel: print(f"[{v['belegt']}] {v['id']} ({v['ergebnis']}): {v['lehre']}")
        return
    z = {k: sum(1 for v in V if v["ergebnis"] == k) for k in ("besser", "schlechter", "gleich", "unklar")}; print(f"{len(V)} Versuche {z}")
    for v in sel: print(f"{v['datum'][:10]} {v['id']:34} {v['ergebnis']:10} {v['belegt']:15} {v['frage'][:70]}")

if __name__ == "__main__":
    main()
