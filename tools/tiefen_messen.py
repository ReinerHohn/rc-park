#!/usr/bin/env python3
"""tiefen_messen.py - Tiefen der Fassadenelemente (Nische, Arkade, Vorsprung) aus der dichten Mehrbild-Wolke statt ANNAHME (Stufe 9 "ohne Handwerte", 2026-11-05).

Je Element (fassade_parsing elemente.json, Fassadenrahmen o + u*d, Normale n nach aussen): Punkte der Wolke im Elementkasten (Rand 0,3 m nach innen),
Rueckversatz t = Wandebene - s (s = Abstand entlang n; Wandebene = Median s der Wolke im 1-m-Band um die Fassadenebene, z ueber 2 m).
Histogramm 0,25 m: Schichten = lokale Maxima mit >= min_anteil der Punkte. Tiefe (hinten) = tiefste Schicht, Vorsprung = vorderste Schicht < -0,1 m.
Klassenwert = Median der groessten stimmigen Gruppe (Breite 0,3 m, >= 3 Elemente und >= 30 %%), sonst 'unsicher' (bleibt ANNAHME).
Beleg Kaufhaus f02: vier Arkadenboegen zeigen je zwei Schichten 0,25-0,5 m (Bogenlaibung/Pfeiler) und 4,0-4,25 m (Rueckwand) -> Arkadentiefe ~4,1 statt ANNAHME 3,0.
Zirkelfrei: die Wolke kommt aus Merkmalszuordnung der Fotos, nicht aus dem Modell; Hoehenrahmen geht nicht ein (Tiefe = waagerechter Abstand).
  /media/oem/scan/venv-seg/bin/python -I tools/tiefen_messen.py <objekt.json> <elemente.json> [--wolke sfm/dicht_alle_modell.npy] [--aus tiefen.json]
"""
import os, sys, json, argparse
import numpy as np

KLASSE_PARAM = {"fenster": "nische_m", "tuer": "nische_m", "bogen": "bogen_tiefe_m", "gaube": "gauben_tiefe_m", "figur": "figur_vorsprung_m", "balkon": "balkon_vorsprung_m"}
VORSPRUNG = {"figur", "balkon"}


def schichten(t, schritt=0.25, lo=-2.0, hi=8.0, min_anteil=0.08, min_n=30):
    h, b = np.histogram(t, bins=np.arange(lo, hi + 1e-9, schritt)); c = 0.5 * (b[:-1] + b[1:]); out = []
    for i in range(len(h)):
        if h[i] >= max(min_n, min_anteil * len(t)) and h[i] >= (h[i - 1] if i else 0) and h[i] >= (h[i + 1] if i + 1 < len(h) else 0):
            w = slice(max(0, i - 1), i + 2); out.append(float((c[w] * h[w]).sum() / max(1, h[w].sum())))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("elemente"); ap.add_argument("--wolke"); ap.add_argument("--aus"); ap.add_argument("--min-stimmen", type=int, default=2); ap.add_argument("--min-tiefe", type=float, default=0.15, help="kleiner = von der Wand nicht unterscheidbar (Gegenprobe Kaesten auf glatter Wand: 0,07-0,11 m)")
    a = ap.parse_args(argv); od = os.path.dirname(os.path.abspath(a.objekt))
    P = np.load(a.wolke or os.path.join(od, "sfm", "dicht_alle_modell.npy")); E = json.load(open(a.elemente)); je = {}
    for fid, F in E["fassaden"].items():
        n = np.array(F["n"], float); d = np.array(F["d"], float); o = np.array(F["o"], float); rel = P[:, :2] - o; u = rel @ d; s = rel @ n; z = P[:, 2]
        bd = (np.abs(s) < 1.0) & (z > 2.0)
        if bd.sum() < 200: continue
        wand = float(np.median(s[bd]))
        for e in F["elemente"]:
            if e.get("stimmen", 0) < a.min_stimmen or e["klasse"] not in KLASSE_PARAM: continue
            k = (u > e["u0"] + 0.3) & (u < e["u1"] - 0.3) & (z > max(e["z0"] + 0.3, 0.5)) & (z < e["z1"] - 0.3)
            if k.sum() < 60: continue
            t = wand - s[k]; sch = schichten(t[(t > -2) & (t < 8)])
            if not sch: continue
            if e["klasse"] in VORSPRUNG:
                v = [x for x in sch if x < -0.1]
                if v: je.setdefault(e["klasse"], []).append(dict(fassade=fid, u=[e["u0"], e["u1"]], wert=round(-min(v), 3), schichten=[round(x, 2) for x in sch], n=int(k.sum())))
            else:
                je.setdefault(e["klasse"], []).append(dict(fassade=fid, u=[e["u0"], e["u1"]], wert=round(max(sch), 3), schichten=[round(x, 2) for x in sch], n=int(k.sum())))
    erg = {}
    for kl, L in je.items():                                                                          # groesste stimmige Gruppe (Breite 0,3 m) statt Median: Elemente hinter Erkern/Marktstaenden
        w = np.sort(np.array([x["wert"] for x in L])); best = (0, 0)                                  # messen etwas anderes (Kaufhaus: 3 von 5 Boegen 4,17-4,27, einer nur Laibung)
        for i in range(len(w)):
            j = int(np.searchsorted(w, w[i] + 0.3, side="right")); best = max(best, (j - i, i))
        k_, i_ = best; g = w[i_:i_ + k_]; ok = k_ >= 3 and k_ >= 0.3 * len(w) and float(np.median(g)) >= a.min_tiefe   # Gegenprobe: glatte Wand liefert 0,07-0,11 m
        erg[kl] = dict(param=KLASSE_PARAM[kl], wert=round(float(np.median(g)), 3) if ok else None, n=len(w), gruppe=int(k_), spanne=[round(float(g.min()), 3), round(float(g.max()), 3)],
                       status="gemessen" if ok else "unsicher (bleibt ANNAHME)", elemente=L)
        print(f"  {kl:7s} -> {KLASSE_PARAM[kl]:20s} {('%.2f m' % erg[kl]['wert']) if ok else '   -  '}  (Gruppe {k_}/{len(w)} Elemente, {g.min():.2f}..{g.max():.2f})  {erg[kl]['status']}")
    aus = a.aus or os.path.join(os.path.dirname(os.path.abspath(a.elemente)), "tiefen.json")
    json.dump(dict(klassen=erg, quelle="tiefen_messen.py: dichte Mehrbild-Wolke, Schichten je Element", wolke=a.wolke or "sfm/dicht_alle_modell.npy"), open(aus, "w"), indent=1)
    print("->", aus)


if __name__ == "__main__":
    main()
