#!/usr/bin/env python3
"""foto_wichtigkeit.py - Wichtigkeit je Foto aus einem COLMAP-Buendel (Sweet-Spot-Frage, Nutzer 7.11.). Nur Lesen.
  /media/oem/scan/venv-colmap/bin/python -I tools/foto_wichtigkeit.py SPARSE_DIR [--aus x.json] [--min-spur 3]
Je Bild: Zahl der 3D-Punkte (n), 'allein' = Punkte, die ohne dieses Bild nur noch < min-spur Bilder sehen (verlieren Triangulierbarkeit; Abdeckung, die nur dieses Bild traegt),
'einzig' = Punkte, die nur dieses Bild + 1 weiteres sehen, Anteil allein/n. Rangliste + gierige Auswahl: wie viele Bilder braucht man, damit >= X % der Punkte weiter >= min-spur Bilder haben
(Mengen-Ueberdeckung, Greedy). Aussage ist ABDECKUNG, keine Genauigkeit; Leave-One-Out am Diff bleibt die Pruefung."""
import sys, json, argparse, numpy as np, pycolmap
ap = argparse.ArgumentParser(); ap.add_argument("sparse"); ap.add_argument("--aus"); ap.add_argument("--min-spur", type=int, default=3); ap.add_argument("--anteile", default="0.9,0.95,0.99"); a = ap.parse_args()
R = pycolmap.Reconstruction(a.sparse)
spur = {}; namen = {}
for iid, im in R.images.items():
    namen[iid] = im.name
    for p in im.points2D:
        if p.has_point3D(): spur.setdefault(p.point3D_id, set()).add(iid)
ms = a.min_spur; gut = {pid: s for pid, s in spur.items() if len(s) >= ms}
allein = {i: 0 for i in namen}; n = {i: 0 for i in namen}
for pid, s in spur.items():
    for i in s: n[i] += 1
for pid, s in gut.items():
    if len(s) == ms:
        for i in s: allein[i] += 1
rows = [dict(name=namen[i], n=n[i], allein=allein[i], anteil_allein=round(allein[i] / max(1, n[i]), 3)) for i in namen]
rows.sort(key=lambda r: -r["allein"])
# Greedy-Ueberdeckung: Punkte brauchen >= ms gewaehlte Bilder
pts = list(gut.items()); need = np.full(len(pts), ms); sel = []; rest = set(namen)
bild_pts = {i: [] for i in namen}
for k, (pid, s) in enumerate(pts):
    for i in s: bild_pts[i].append(k)
anteile = [float(x) for x in a.anteile.split(",")]; erg = {}; 
while rest and len(erg) < len(anteile):
    gew = {i: int((need[bild_pts[i]] > 0).sum()) for i in rest}; b = max(gew, key=gew.get)
    if gew[b] == 0: break
    sel.append(b); rest.discard(b)
    for k in bild_pts[b]: need[k] -= 1
    cov = float((need <= 0).mean())
    for x in anteile:
        if cov >= x and x not in erg: erg[x] = len(sel)
print(f"Bilder {len(namen)}, Punkte {len(spur)} (>= {ms} Bilder: {len(gut)})")
print("Bilder fuer Abdeckung (Greedy):", {f"{int(x*100)}%": v for x, v in erg.items()})
print("wichtigste (allein):", [(r["name"], r["allein"]) for r in rows[:8]])
print("entbehrlichste (allein=0):", [r["name"] for r in rows if r["allein"] == 0][:40], "Anzahl", sum(1 for r in rows if r["allein"] == 0))
if a.aus: json.dump(dict(bilder=rows, greedy=erg, auswahl=[namen[i] for i in sel]), open(a.aus, "w"), indent=1)
