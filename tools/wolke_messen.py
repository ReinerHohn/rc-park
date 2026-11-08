#!/usr/bin/env python3
"""wolke_messen.py <objekt> --wolke w.npy --kameras k.json --foto ip_IMG_6161.jpg --box x0,y0,x1,y1 [--bildbreite 1613] [--tiefe 0.4] [--name tuerm_links] [--aus messungen.json]
Direktmessung AUS DER WOLKE (Nutzerregel: messen statt suchen): Wolkenpunkte, die im Foto unter der Pixelbox liegen, vordere Tiefenschicht (--tiefe = Anteil naechster Punkte),
Ausgabe Lage im Objektrahmen u (entlang Fassade), n (Tiefe), z (Hoehe) als Median + p10/p90 + Punktzahl. Kameraparameter in Vollaufloesung (W aus kameras.json), Box in der Aufloesung
des angesehenen Bildes (--bildbreite, z. B. 1613 fuer das Overlay). Rahmen u = (n1, -n0) aus objekt.json fassade_n. Kein Fit, keine Suche."""
import sys, os, json, argparse, numpy as np
ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--wolke", required=True); ap.add_argument("--kameras", required=True); ap.add_argument("--foto", required=True)
ap.add_argument("--box", required=True); ap.add_argument("--bildbreite", type=float, default=1613); ap.add_argument("--tiefe", type=float, default=0.4); ap.add_argument("--name", default=""); ap.add_argument("--aus"); a = ap.parse_args()
R0 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = np.load(a.wolke)[:, :3]; K = json.load(open(a.kameras))[a.foto]; S = K["W"] / a.bildbreite
Rn = np.array(K["Rn"]); t = np.array(K["tn"]); X = P @ Rn.T + t; z = X[:, 2]; ok = z > 1
uv = K["f"] * X[:, :2] / np.where(ok, z, 1)[:, None] + [K["cx"], K["cy"]]
o = json.load(open(os.path.join(R0, "modelle", a.objekt, "objekt.json"))); n = np.array(o["fassade_n"]["wert"], float); n /= np.linalg.norm(n); u = np.array([n[1], -n[0]])
x0, y0, x1, y1 = [float(v) * S for v in a.box.split(",")]
m = ok & (uv[:, 0] > x0) & (uv[:, 0] < x1) & (uv[:, 1] > y0) & (uv[:, 1] < y1); Q = P[m]
if len(Q) < 30: sys.exit("zu wenig Wolkenpunkte unter der Box: %d" % len(Q))
d = z[m]; Q = Q[d <= np.percentile(d, 100 * a.tiefe)]; U = Q[:, :2] @ u; N = Q[:, :2] @ n
r = dict(name=a.name, foto=a.foto, box_px=a.box, n_punkte=int(len(Q)), u=round(float(np.median(U)), 3), u_p10_p90=[round(float(v), 3) for v in np.percentile(U, [10, 90])], n=round(float(np.median(N)), 3), z=round(float(np.median(Q[:, 2])), 3),
         z_p10_p90=[round(float(v), 3) for v in np.percentile(Q[:, 2], [10, 90])], methode="wolke_messen.py: Foto-Pixelbox -> vorderste Wolkenschicht, Median", wolke=os.path.basename(a.wolke))
print(json.dumps(r, ensure_ascii=False))
if a.aus:
    L = json.load(open(a.aus)) if os.path.exists(a.aus) else []; L.append(r); json.dump(L, open(a.aus, "w"), indent=1, ensure_ascii=False)
