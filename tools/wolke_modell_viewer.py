#!/usr/bin/env python3
"""wolke_modell_viewer.py - Punktwolke gegen Modelle in EINER selbstenthaltenen 3D-HTML (three.js r128 via jsDelivr), Ebenen schaltbar.
Nutzerregel 8.11.: so schnell wie moeglich ein 3D-HTML zum Vergleichen Wolke gegen generiertes Modell.

  /media/oem/scan/venv-seg/bin/python -I tools/wolke_modell_viewer.py --wolke W.npy --achse-n NX,NY --out seite.html --titel TEXT \
      --modell NAME:pfad.stl:skala:#farbe [--modell ...] [--max-punkte 250000] [--box-rand 4]
Wolke: (N,>=3) in Modellmetern, z oben. STL: Skala auf Meter (1:87-STL in mm -> 0.087). Alles im selben Rahmen (Netzrahmen); Achsen = Modellachsen, keine Himmelsrichtungen.
Je Ebene ein Haken; Tiefenschnitt entlang der Fassadennormale n (Schieberegler von/bis) beschneidet Wolke UND Modelle - so sieht man Bogenhoehe/Lage im Schnitt.
Positionen uint16 je Ebene quantisiert (Spanne/65535), Indizes uint32; Seite < 16 MB."""
import argparse, base64, json, sys
import numpy as np, trimesh
ap = argparse.ArgumentParser(); ap.add_argument("--wolke", required=True); ap.add_argument("--achse-n", default="0.3338,0.9426"); ap.add_argument("--out", required=True); ap.add_argument("--titel", default="Wolke gegen Modell")
ap.add_argument("--modell", action="append", default=[]); ap.add_argument("--max-punkte", type=int, default=250000); ap.add_argument("--box-rand", type=float, default=4.0); a = ap.parse_args()
b64 = lambda x: base64.b64encode(np.ascontiguousarray(x).tobytes()).decode()
def quant(P):
    lo = P.min(0); sp = np.maximum(P.max(0) - lo, 1e-6); q = np.round((P - lo) / sp * 65535).astype(np.uint16); return dict(lo=lo.tolist(), sp=sp.tolist(), n=int(len(P)), p=b64(q))
ebenen = []; box = None
for spec in a.modell:
    nm, pf, sk, col = spec.split(":", 3); m = trimesh.load(pf, process=False); m.apply_scale(float(sk)); m.merge_vertices(); m.remove_unreferenced_vertices()
    V = np.asarray(m.vertices, float); F = np.asarray(m.faces, np.uint32); box = V if box is None else np.vstack([box, V[::50]])
    ebenen.append(dict(name=nm, farbe=col, art="mesh", **quant(V), f=b64(F), nf=int(len(F))))
P = np.load(a.wolke)[:, :3].astype(float)
if box is not None:
    lo, hi = box.min(0) - a.box_rand, box.max(0) + a.box_rand; P = P[np.all((P > lo) & (P < hi), axis=1)]
rng = np.random.default_rng(1)
if len(P) > a.max_punkte: P = P[rng.choice(len(P), a.max_punkte, replace=False)]
ebenen.insert(0, dict(name="Punktwolke", farbe="#ff5a3c", art="punkte", **quant(P)))
n = [float(x) for x in a.achse_n.split(",")]; mitte = ((P.min(0) + P.max(0)) / 2).tolist()
html = open(sys.argv[0].replace("wolke_modell_viewer.py", "wolke_modell_viewer_vorlage.html"), encoding="utf-8").read()
html = html.replace("/*DATEN*/", "const DATEN=" + json.dumps(dict(ebenen=ebenen, n=n, mitte=mitte, titel=a.titel)) + ";").replace("TITEL_PLATZ", a.titel)
open(a.out, "w", encoding="utf-8").write(html); print(a.out, f"{len(html)/1e6:.1f} MB", [(e['name'], e['n']) for e in ebenen])
