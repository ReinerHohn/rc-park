#!/usr/bin/env python3
"""wolke_gauben_messen.py - Dachgauben AUS DER WOLKE messen: Wolkenpunkte, die ueber der Dachebene stehen (Abstand > --schwelle), werden in der Dachebene (u, z) zu Haufen
gruppiert (Rasterverfahren, 0,25 m); je Haufen: Mitte u/z, Breite/Hoehe (P3-P97), Vorsprung = hoechster Abstand ueber der Ebene (P95). Haufen derselben Hoehe (z-Streuung < --reihe_tol)
bilden eine Reihe: Anzahl, Mitte, Teilung (Ausgleichsgerade). Generisch (keine Objektnamen): Dachebene aus objekt.json-Bauteil (satteldach: n_traufe_v/z_traufe_v/n_first/z_first, achse_n).
ZAEHLUNG der Gauben NICHT hier (Regel 9, Foto): Anzahl_wolke nur zum Konsistenzvergleich. Ausgabe JSON {reihen:[{n_wolke, u_mitte, pitch, z_mitte, t, breite, hoehe, vorsprung}]}.
  /media/oem/scan/venv-seg/bin/python -I tools/wolke_gauben_messen.py kaufhaus_grob3 satteldach:haupt --aus modelle/kaufhaus_grob3/gauben_messung.json [--wolke W.npy]"""
import os, sys, json, argparse, numpy as np
from scipy import ndimage
ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("dach"); ap.add_argument("--aus", required=True); ap.add_argument("--wolke", default="/media/oem/scan/rc-park_null/wolke_netzrahmen.npy")
ap.add_argument("--schwelle", type=float, default=0.35); ap.add_argument("--zmin", type=float, default=11.8); ap.add_argument("--umax", type=float, default=7.0); ap.add_argument("--reihe_tol", type=float, default=0.8)
ap.add_argument("--min_punkte", type=int, default=150); a = ap.parse_args()
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); O = json.load(open(os.path.join(ROOT, "modelle", a.objekt, "objekt.json"))); D = next(b for b in O["bauteile"] if b["typ"] == a.dach)
n = np.array(D["achse_n"], float); n /= np.linalg.norm(n); u = np.array([n[1], -n[0]]); P = np.load(a.wolke)[:, :3]
U, N = P[:, :2] @ u, P[:, :2] @ n; ntv, ztv, nf, zf = (float(D[k]) for k in ("n_traufe_v", "z_traufe_v", "n_first", "z_first")); sl = (zf - ztv) / (ntv - nf)
dev = (P[:, 2] - (ztv + (ntv - N) * sl)) * np.cos(np.arctan(sl)); m = (dev > -0.6) & (dev < 3.0) & (P[:, 2] > a.zmin) & (N < ntv + 0.5) & (N > nf - 1) & (np.abs(U) < a.umax + 4)
U, Z, dev = U[m], P[m, 2], dev[m]; hoch = dev > a.schwelle; g = 0.25; iu = np.floor((U[hoch] + 20) / g).astype(int); iz = np.floor(Z[hoch] / g).astype(int)
H = np.zeros((int(60 / g), int(40 / g)), int); np.add.at(H, (iu, iz), 1); H = ndimage.binary_closing(H >= 2, iterations=1); lab, nl = ndimage.label(H)
cl = []
for k in range(1, nl + 1):
    ui, zi = np.nonzero(lab == k); uc, zc = ui.mean() * g - 20 + g / 2, zi.mean() * g + g / 2
    s = hoch & (np.abs(U - uc) < (np.ptp(ui) + 3) * g / 2) & (np.abs(Z - zc) < (np.ptp(zi) + 3) * g / 2)
    if s.sum() < a.min_punkte or abs(uc) > a.umax: continue
    cl.append(dict(u=float(np.median(U[s])), z=float(np.median(Z[s])), breite=float(np.percentile(U[s], 97) - np.percentile(U[s], 3)), hoehe=float(np.percentile(Z[s], 97) - np.percentile(Z[s], 3)), vorsprung=float(np.percentile(dev[s], 95)), n_punkte=int(s.sum())))
cl.sort(key=lambda c: c["z"]); reihen = []
for c in cl:
    for r in reihen:
        if abs(np.mean([x["z"] for x in r]) - c["z"]) < a.reihe_tol: r.append(c); break
    else: reihen.append([c])
out = []
for r in reihen:
    r.sort(key=lambda c: c["u"]); us = np.array([c["u"] for c in r]); pitch = float(np.polyfit(np.arange(len(r)), us, 1)[0]) if len(r) > 1 else None; zm = float(np.mean([c["z"] for c in r]))
    out.append(dict(n_wolke=len(r), u_mitte=float(us.mean()), pitch=pitch, z_mitte=zm, t=(zm - ztv) / (zf - ztv), breite=float(np.mean([c["breite"] for c in r])), hoehe=float(np.mean([c["hoehe"] for c in r])), vorsprung=float(np.mean([c["vorsprung"] for c in r])), haufen=r))
res = dict(quelle=f"Wolke {os.path.basename(a.wolke)}, Punkte > {a.schwelle} m ueber der Dachebene von {a.dach}, tools/wolke_gauben_messen.py (Zaehlung nur Konsistenz, Regel 9)", reihen=out)
json.dump(res, open(a.aus, "w"), indent=1); print(json.dumps([{k: (round(v, 2) if isinstance(v, float) else v) for k, v in r.items() if k != "haufen"} for r in out], indent=1))
