#!/usr/bin/env python3
"""rueckwand_tiefe.py <objekt.json> <oeffnungen_aussen.json> [--schreiben] - LEIBUNGSTIEFE je Objekt fuer bauteile.rueckwaende (Regel A) aus den Fotos.
18.11.2026 (Ziel H0 von null, Luecke L2, Kettenstufe 'bauplan'). Bisher mass ein Agent die Tiefe von Hand (Kaufhaus: foto_mass an Fenster 3, 0,14 / 0,19 m).
Quelle: tools/oeffnungen_wandbild.py auf den AUSSENwaenden (feines Wandbild der Stufe fenster): je Fenster-Zone die Tiefe aus der Parallaxe der Einzelfoto-Orthos
(innen minus Wandring). Genommen werden Zonen der Klasse 'fenster' mit NCC innen >= --ncc (0,2), nicht flach, Tiefe --spanne (0,06 .. 0,6 m: darunter Tafel/Bild,
darueber Fehlmessung durch Spiegelung/Innenraum). Ab --min_n (3) Fenstern: Median = rueckwand.tiefe (gemessen, Streuung p25..p75 im Beleg).
Sonst ANNAHME 0,15 m (Anhalt: Kaufhaus-Fotomass 0,14 / 0,19 m an einem anderen Haus; Beleg sagt es). Von Hand eingetragene "rueckwand" (ohne "auto") bleibt (rc 3).
Ausgabe: audit/rueckwand_auto.json; mit --schreiben objekt.json "rueckwand" {tiefe, quelle, hinweis, auto}."""
import os, sys, json, time, argparse, numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("oeffnungen"); ap.add_argument("--schreiben", action="store_true")
    ap.add_argument("--ncc", type=float, default=0.2); ap.add_argument("--spanne", nargs=2, type=float, default=[0.06, 0.6]); ap.add_argument("--min_n", type=int, default=3); ap.add_argument("--annahme", type=float, default=0.15)
    a = ap.parse_args(); obj = json.load(open(a.objekt)); od = os.path.dirname(os.path.abspath(a.objekt))
    D = json.load(open(a.oeffnungen)) if os.path.exists(a.oeffnungen) else {}; werte = []
    for fid, F in D.items():
        if F.get("innen"): continue
        for e in F.get("oeffnungen", []):
            if e.get("klasse") == "fenster" and e.get("tiefe") is not None and not e.get("flach") and e.get("ncc_innen", 0) >= a.ncc and a.spanne[0] <= e["tiefe"] <= a.spanne[1]: werte.append((e["tiefe"], fid, e["zone"], e.get("fotos")))
    t = [w[0] for w in werte]; jetzt = time.strftime("%Y-%m-%d")
    if len(t) >= a.min_n:
        tm = round(float(np.median(t)), 3); q25, q75 = (round(float(x), 3) for x in np.percentile(t, [25, 75]))
        rw = dict(tiefe=tm, quelle=f"tools/rueckwand_tiefe.py: Median der Parallaxentiefe (oeffnungen_wandbild.py, Einzelfoto-Orthos, innen minus Wandring) an {len(t)} Fenstern ({', '.join(sorted(set(w[1] for w in werte)))}), p25..p75 {q25}..{q75} m; Datei {os.path.basename(a.oeffnungen)}",
                  hinweis="gemessen = Glas-/Rahmenebene hinter der Wandflaeche; ANNAHME: gleiche Tiefe fuer alle Oeffnungen des Hauses", auto="bauplan " + jetzt, n=len(t), streuung=[q25, q75])
    else:
        rw = dict(tiefe=a.annahme, quelle=f"ANNAHME: {a.annahme} m (nur {len(t)} belastbare Fenstertiefen < {a.min_n}; Anhalt Kaufhaus-Fotomass 0,14 / 0,19 m an einem anderen Haus, modelle/kaufhaus_gk/objekt.json rueckwand)",
                  hinweis="nicht gemessen - mit Fotomass (foto_mass --kamera, zwei Gegenrichtungen) ersetzen", auto="bauplan " + jetzt, n=len(t))
    json.dump(dict(rueckwand=rw, fenster=[dict(tiefe=w[0], fassade=w[1], zone=w[2], fotos=w[3]) for w in werte]), open(os.path.join(od, "audit", "rueckwand_auto.json"), "w"), indent=1, ensure_ascii=False)
    print(f"Rueckwand-Tiefe {rw['tiefe']} m aus {len(t)} Fenstern" + ("" if len(t) >= a.min_n else " -> ANNAHME") + (f" (Werte {sorted(round(x, 2) for x in t)})" if t else ""))
    if a.schreiben:
        if obj.get("rueckwand") and not obj["rueckwand"].get("auto"): print("objekt.json hat eine VON HAND gemessene rueckwand - NICHT ueberschrieben"); return 3
        obj["rueckwand"] = rw; __import__("json_sicher").schreiben(a.objekt, obj); print("objekt.json rueckwand geschrieben")
    return 0


if __name__ == "__main__":
    sys.exit(main())
