#!/usr/bin/env python3
"""restfeld_ausgleich.py - Ebene 1 der Konvergenzschleife (5.11.): je beobachteter Ebene (Wand/Dachflaeche) aus dem Restfeld (tools/restfeld_fassade.py)
eine robuste lineare Korrektur Rest(v) = a*v + b entlang der Ebenennormalen (v = Koordinate in der Ebene nach oben; a = Neigungsaenderung, b = Versatz).
Allgemein fuer jede ebene Flaeche, keine Bauteilregel. Nur Zellen, die zur Ebene selbst gehoeren: |Rest| <= --band (Erker, Gauben, Oeffnungen sind
Ausreisser und gehoeren Ebene 2 / den Bauteilen), mehrfach neu gewichtet (Median-Abweichung). Ebene gilt nur bei >= --min-anteil beobachtet und
>= --min-zellen Zellen; sonst keine Korrektur (unbeobachtet = Generatorwert bleibt).
Ausgabe JSON: ebenen [{id, n, o, dd, e, a, b, streuung_m, zellen, beobachtet_anteil}] - der Generator (rumpf_lod2 'ebenen_korrektur') verschiebt die
Punkte der passenden LoD2-Flaeche (Normale < 5 Grad, Abstand < 1,5 m) um n * (a*v + b).
  python3 tools/restfeld_ausgleich.py <restfeld_ordner> <aus.json> [--nur d02 ...]
"""
import os, sys, json, argparse
import numpy as np


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("ordner"); ap.add_argument("aus"); ap.add_argument("--nur", nargs="*"); ap.add_argument("--band", type=float, default=1.5)
    ap.add_argument("--min-anteil", type=float, default=0.2); ap.add_argument("--min-zellen", type=int, default=2000); ap.add_argument("--max-neigung", type=float, default=0.15); ap.add_argument("--max-streuung", type=float, default=0.2)
    a = ap.parse_args(argv); R = json.load(open(os.path.join(a.ordner, "restfeld.json"))); out = dict(quelle=os.path.abspath(a.ordner), stl=R["stl"], ebenen=[], verworfen={})
    for fid, F in R["fassaden"].items():
        if a.nur and fid not in a.nur: continue
        if F["beobachtet_anteil"] < a.min_anteil: out["verworfen"][fid] = f"beobachtet {F['beobachtet_anteil']}"; continue
        z = np.load(os.path.join(a.ordner, f"restfeld_{fid}.npz")); D, M_ = z["daten"], z["modell"]; c = float(z["zelle"]); z1 = float(z["z1"])
        r_ = D - M_; b_ = ~np.isnan(r_) & (np.abs(np.nan_to_num(r_)) <= a.band); iy, _ = np.nonzero(b_); v = z1 - (iy + 0.5) * c; r = r_[b_]
        if len(r) < a.min_zellen: out["verworfen"][fid] = f"{len(r)} Zellen"; continue
        A = np.c_[v - (z1 if F["e"][2] > 0.999 else 0.0) * 0, np.ones_like(v)]
        if F["e"][2] > 0.999: A[:, 0] = v - float(np.median(v))                                  # Wand: v = z absolut -> zentrieren (b = Versatz in Wandmitte)
        k = np.ones(len(r), bool)
        for _ in range(5):
            co = np.linalg.lstsq(A[k], r[k], rcond=None)[0]; e = r - A @ co; s = 1.4826 * np.median(np.abs(e[k])); k = np.abs(e) < max(2.5 * s, 0.05)
        aa, bb = float(co[0]), float(co[1])
        if abs(aa) > a.max_neigung: out["verworfen"][fid] = f"Neigung {aa:.3f} > {a.max_neigung}"; continue
        if s > a.max_streuung: out["verworfen"][fid] = f"Streuung {s:.3f} m > {a.max_streuung} (keine Ebene: Vorbauten/Stufen -> Ebene 2)"; continue
        v_ref = float(np.median(v)) if F["e"][2] > 0.999 else 0.0
        out["ebenen"].append(dict(id=fid, n=F["n"], o=F["o"], dd=F["dd"], e=F["e"], a=round(aa, 4), b=round(bb - aa * v_ref, 4), v_bezug=0.0,
                                  streuung_m=round(float(s), 3), zellen=int(k.sum()), beobachtet_anteil=F["beobachtet_anteil"]))
        print(f"{fid}: Rest = {aa:+.3f} * v {bb - aa * v_ref:+.3f}  (Streuung {s:.3f} m, {k.sum()} Zellen)")
    json.dump(out, open(a.aus, "w"), indent=1)


if __name__ == "__main__":
    main()
