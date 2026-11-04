#!/usr/bin/env python3
"""zeit_je_modell.py - Wanduhr je Nullstart-Stufe und je Schritt aus ALLEN vorhandenen nullstart_bericht.json (Sweetspot 'viele Modelle in kurzer Zeit').
Zeigt, wo die Zeit eines Modell-Laufs bleibt (Median/Min/Max ueber Laeufe), getrennt nach Stufe (grob/mittel/fein/...); Schritte mit Nummernanhang (kalibrieren_030) werden zusammengefasst.
Nur LESEN. Grenzen: Laeufe sind teils mit parallelen anderen Jobs gelaufen (Zeiten dann zu hoch), 'sekunden' fehlt bei einigen Schritten (netzwahl, anlegen) und fehlt bei alten Berichten ganz;
Nutzen (Modellguete) steht hier NICHT - dafuer sweetspot.json/treppe.py. Ergebnis: modelle/aufwand/zeit_je_modell.json.
  python3 -I tools/zeit_je_modell.py [--wurzel /media/oem/scan/rc-park_null]
"""
import sys, os, re, json, glob, argparse, statistics, time

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--wurzel", default="/media/oem/scan/rc-park_null"); a = ap.parse_args()
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); fs = sorted(glob.glob(os.path.join(a.wurzel, "**", "nullstart_bericht.json"), recursive=True)); je = {}; n_ok = 0
    for f in fs:
        try: b = json.load(open(f))
        except Exception: continue
        S = [s for s in b.get("schritte", []) if isinstance(s.get("sekunden"), (int, float))]
        if not S: continue
        n_ok += 1; st = str(b.get("stufe") or "?"); d = je.setdefault(st, dict(laeufe=[], schritte={})); d["laeufe"].append(sum(s["sekunden"] for s in S))
        agg = {}
        for s in S: k = re.sub(r"_\d+$", "", s["schritt"]); agg[k] = agg.get(k, 0.0) + s["sekunden"]
        for k, v in agg.items(): d["schritte"].setdefault(k, []).append(v)
    out = {}; print(f"{len(fs)} Berichte gefunden, {n_ok} mit Zeitangaben\n")
    for st, d in sorted(je.items()):
        L = d["laeufe"]; print(f"Stufe {st}: {len(L)} Laeufe, Summe der Schrittzeiten Median {statistics.median(L) / 60:.1f} min (min {min(L) / 60:.1f}, max {max(L) / 60:.1f})")
        top = sorted(d["schritte"].items(), key=lambda kv: -statistics.median(kv[1]))[:6]; out[st] = dict(laeufe=len(L), median_s=round(statistics.median(L), 1), min_s=round(min(L), 1), max_s=round(max(L), 1), schritte={k: round(statistics.median(v), 1) for k, v in top})
        for k, v in top: print(f"    {k:22} Median {statistics.median(v):7.0f} s  ({100 * statistics.median(v) / statistics.median(L):4.1f} %)  n={len(v)}")
    p = os.path.join(repo, "modelle", "aufwand", "zeit_je_modell.json"); os.makedirs(os.path.dirname(p), exist_ok=True)
    json.dump(dict(stand=time.strftime("%F %T"), stufen=out, grenzen="Zeiten teils bei parallelen Jobs; Nutzen nicht enthalten"), open(p, "w"), indent=1, ensure_ascii=False); print("\n->", p)

if __name__ == "__main__":
    main()
