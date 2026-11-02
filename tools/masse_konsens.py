#!/usr/bin/env python3
"""masse_konsens.py - Median-Konsens der automatisch abgeleiteten Masse ueber UNABHAENGIGE Nullstart-Laeufe (Register BR/BS).

Warum: Ein Einzellauf streut (ERKER_OBEN 34,5..39,75 m, DACHHOEHE 14,9..17,4 m; Register BO). Die Streuung kommt aus der Netzrealisierung, nicht aus dem Punktrauschen
(Bootstrap MAD ~ 0) - nur der Median ueber mehrere unabhaengige Laeufe ist robust. Der Median entfernt ZUFALL, keine systematischen Fehler (Hoehendrift, Clip-Kippen): die brauchen Anker.
Je Mass: n, Median, MAD, Spanne; Status stabil (Spanne <= --stabil), streut (Spanne > --streut oder < --min-laeufe Laeufe), sonst mittel. Abweichung des Referenzwerts (masse.json des Objekts) vom Median.
Aendert KEINEN Sollwert und keine masse.json (Regel: Sollwerte nie lockern); nur Bericht audit/masse_konsens.json + Tabelle. Uebernahme eines Medians in den Generator = bewusste Aenderung mit Quelle/historie.
  /media/oem/scan/venv-seg/bin/python -I tools/masse_konsens.py modelle/martinstor/objekt.json <masse.json oder Ordner/Glob> ... [--min-laeufe 3]
"""
import sys, os, json, glob, argparse, numpy as np

def lade(f):
    m = json.load(open(f))["masse"]; return {n: float(x["wert"]) for n, x in m.items() if isinstance(x, dict) and isinstance(x.get("wert"), (int, float))}

def konsens(Laeufe, ref, stabil=0.3, streut=1.0, min_laeufe=3):
    namen = sorted({n for L in Laeufe for n in L}); out = {}
    for n in namen:
        v = np.array([L[n] for L in Laeufe if n in L]); md = float(np.median(v)); mad = float(np.median(abs(v - md))); sp = float(v.max() - v.min())
        st = "streut" if (len(v) < min_laeufe or sp > streut) else ("stabil" if sp <= stabil else "mittel")
        out[n] = dict(n=int(len(v)), median=round(md, 3), mad=round(mad, 3), spanne=round(sp, 3), min=round(float(v.min()), 3), max=round(float(v.max()), 3), status=st, referenz=ref.get(n),
                      ref_minus_median=(round(ref[n] - md, 3) if n in ref else None))
    return out

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("quellen", nargs="+"); ap.add_argument("--min-laeufe", type=int, default=3)
    ap.add_argument("--stabil", type=float, default=0.3); ap.add_argument("--streut", type=float, default=1.0); a = ap.parse_args()
    od = os.path.dirname(os.path.abspath(a.objekt)); fs = []
    for q in a.quellen:
        fs += [q] if os.path.isfile(q) else (glob.glob(os.path.join(q, "**", "masse.json"), recursive=True) if os.path.isdir(q) else glob.glob(q, recursive=True))
    fs = sorted(set(f for f in fs if f.endswith("masse.json")))
    L = []
    for f in fs:
        try: L.append(lade(f))
        except Exception as e: print("uebersprungen", f, e)
    if len(L) < 2: sys.exit(f"zu wenige Laeufe ({len(L)})")
    ref = lade(os.path.join(od, "masse.json")); K = konsens(L, ref, a.stabil, a.streut, a.min_laeufe)
    print(f"{len(L)} Laeufe; {'Mass':24}{'n':>3}{'Median':>9}{'MAD':>7}{'Spanne':>8}  Status   Ref-Median")
    for n, r in K.items():
        if r["spanne"] == 0 and (r["ref_minus_median"] in (0, None)): continue
        print(f"{'':10}{n:24}{r['n']:3d}{r['median']:9.2f}{r['mad']:7.2f}{r['spanne']:8.2f}  {r['status']:8} {r['ref_minus_median'] if r['ref_minus_median'] is not None else '-'}")
    os.makedirs(os.path.join(od, "audit"), exist_ok=True)
    json.dump(dict(laeufe=len(L), quellen=fs, schwellen=dict(stabil=a.stabil, streut=a.streut, min_laeufe=a.min_laeufe), masse=K,
                   hinweis="Median entfernt Zufall, keine systematischen Fehler; aendert keinen Sollwert"), open(os.path.join(od, "audit", "masse_konsens.json"), "w"), indent=1, ensure_ascii=False)

if __name__ == "__main__":
    main()
