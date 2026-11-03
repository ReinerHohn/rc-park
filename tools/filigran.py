#!/usr/bin/env python3
"""filigran.py - zu filigrane Strukturen eines H0-Modells finden und als Einsteck-Teile (Stab/Nadel/Kugel) vorschlagen (Register BU, Phase 1: Erkennung + Bericht).

Idee (Nutzer): Was zu fein zum Drucken ist, wird nicht mitgedruckt, sondern von Hand aus Draht/Nadel/Perle nachgebaut. Das Modell bekommt dort eine Bohrung zum Einstecken.
Phase 1 (dieses Werkzeug): Wanddicke an vielen Oberflaechenpunkten messen (Strahl nach innen bis zur Gegenflaeche), zu duenne Punkte (< --min-mm) zu Gruppen verbinden, jede Gruppe per
Hauptachsen als STAB (lang und duenn: Nadel, Mast, Zinne), KUGEL (kompakt: Knauf) oder WAND (flaechig duenn: Kante, Zierleiste) einordnen und mit Position (Original-Meter), Laenge, Dicke,
Vorschlag fuer Stab/Perle ausgeben. Phase 2 (noch nicht gebaut): Teil abtrennen, Bohrung (Ø Stab + Spiel, Tiefe) einbauen, Liste der Einsteckteile als Stueckliste.
ANNAHMEN (nicht gemessen): Spiel der Bohrung 0.1 mm; Mindestdurchmesser Draht 0.3 mm; Mindesttiefe der Bohrung = 4 x Stabdurchmesser, mind. 2 mm. Nur Sichtpruefung der Gruppen ersetzt keine Anprobe.
  /media/oem/scan/venv-seg/bin/python -W ignore -I tools/filigran.py modelle/stl/<modell>_1-87.stl [--min-mm 0.8] [--massstab 87] [--punkte 400000] [--aus audit/filigran.json]
"""
import sys, os, json, argparse, numpy as np, trimesh
from scipy.spatial import cKDTree
from scipy.sparse.csgraph import connected_components
from scipy.sparse import coo_matrix

def duenne_punkte(m, n, min_mm, tiefe_max=3.0):
    pts, fi = trimesh.sample.sample_surface(m, n); nor = m.face_normals[fi]; o = pts - nor * 0.01
    loc, ir, _ = m.ray.intersects_location(o, -nor, multiple_hits=False); d = np.linalg.norm(loc - o[ir], axis=1) + 0.01
    keep = d < min_mm; return pts[ir][keep], d[keep], nor[fi][ir][keep]

def gruppen(P, radius):
    t = cKDTree(P); pr = t.query_pairs(radius, output_type="ndarray"); n = len(P)
    if len(pr) == 0: return np.arange(n)
    g = coo_matrix((np.ones(len(pr)), (pr[:, 0], pr[:, 1])), shape=(n, n)); return connected_components(g, directed=False)[1]

def klassifiziere(P, d, massstab):
    c = P.mean(0); u, s, vt = np.linalg.svd(P - c, full_matrices=False); ax = vt[0]; proj = (P - c) @ vt.T
    ext = np.ptp(proj, axis=0); L1, L2, L3 = np.sort(ext)[::-1]; t = float(np.median(d)) * 1.0
    if L1 > max(3.0, 4 * t) and L2 < 0.5 * L1: art = "STAB"
    elif L1 < max(3.0, 4 * t): art = "KUGEL"
    else: art = "WAND"
    return art, c, ax, (float(L1), float(L2), float(L3)), t

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("stl"); ap.add_argument("--min-mm", type=float, default=0.8); ap.add_argument("--massstab", type=float, default=87.0); ap.add_argument("--punkte", type=int, default=400000)
    ap.add_argument("--radius", type=float, default=1.5); ap.add_argument("--min-gruppe", type=int, default=20); ap.add_argument("--aus"); ap.add_argument("--draht", type=float, default=0.3, help="Mindestdurchmesser Draht/Nadel (mm), ANNAHME")
    a = ap.parse_args(); m = trimesh.load(a.stl, force="mesh"); k = a.massstab / 1000.0
    P, d, N = duenne_punkte(m, a.punkte, a.min_mm); print(f"{len(P)} duenne Punkte (< {a.min_mm} mm) von {a.punkte} Stichproben; Modell {m.bounds[1].round(0).tolist()} mm, wasserdicht {m.is_watertight}")
    if len(P) == 0: return
    g = gruppen(P, a.radius); out = []
    for gi in np.unique(g):
        Q = P[g == gi]
        if len(Q) < a.min_gruppe: continue
        art, c, ax, (L1, L2, L3), t = klassifiziere(Q, d[g == gi], a.massstab); dstab = max(round(2 * t * 0.9, 2), a.draht) if art != "WAND" else None
        out.append(dict(art=art, z_original_m=round(float(c[2]) * k, 2), pos_mm=[round(float(x), 1) for x in c], achse=[round(float(x), 2) for x in ax], laenge_mm=round(L1, 2), breite_mm=round(L2, 2), dicke_mm=round(2 * t, 2) if False else round(t, 2),
                        punkte=int(len(Q)), vorschlag=(f"Stab Ø {dstab} mm x {round(L1, 1)} mm, Bohrung Ø {round(dstab + 0.1, 2)} mm, Tiefe {max(2.0, round(4 * dstab, 1))} mm" if art == "STAB" else
                        f"Perle/Kugel Ø {round(max(L2, L1), 1)} mm, Zapfenbohrung Ø {a.draht + 0.1:.1f} mm" if art == "KUGEL" else "duenne Wand/Kante: verdicken (Mindestwand) oder weglassen")))
    out.sort(key=lambda x: -x["punkte"]); z = {x: sum(1 for o in out if o["art"] == x) for x in ("STAB", "KUGEL", "WAND")}
    print(f"{len(out)} Gruppen {z}")
    for o in out[:15]: print(f"  {o['art']:6} z {o['z_original_m']:5.1f} m  L {o['laenge_mm']:5.1f} mm  B {o['breite_mm']:4.1f}  Dicke~{o['dicke_mm']:.2f}  n={o['punkte']:5d}  {o['vorschlag']}")
    if a.aus: os.makedirs(os.path.dirname(os.path.abspath(a.aus)), exist_ok=True); json.dump(dict(stl=a.stl, min_mm=a.min_mm, gruppen=out), open(a.aus, "w"), indent=1, ensure_ascii=False); print("->", a.aus)

if __name__ == "__main__":
    main()
