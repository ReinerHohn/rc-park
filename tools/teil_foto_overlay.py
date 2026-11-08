#!/usr/bin/env python3
"""teil_foto_overlay.py <objekt> <typ> --fotos kameras_netz.json --bilder dir --shift du,dn,dz [--mit carrier] [--n 3] --out png
Kanten (Knickkanten) des Bauteils (um shift verschoben) in die naechsten kalibrierten Fotos projiziert, Ausschnitt um das Teil. Zum ANSEHEN (Regel 3/9b/9d)."""
import sys, os, json, argparse, subprocess, numpy as np, trimesh, cv2
ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("typ"); ap.add_argument("--fotos", required=True); ap.add_argument("--bilder", required=True)
ap.add_argument("--shift", default="0,0,0"); ap.add_argument("--mit", default=""); ap.add_argument("--n", type=int, default=3); ap.add_argument("--out", required=True)
ap.add_argument("--py", default=os.path.expanduser("~/.venvs/rcpark/bin/python")); a = ap.parse_args()
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); OD = os.path.join(ROOT, "modelle", a.objekt); K = 1000.0 / 87.0
OBJ = json.load(open(os.path.join(OD, "objekt.json"))); nn = np.array(OBJ["fassade_n"]["wert"], dtype=float); nn /= np.linalg.norm(nn); uu = np.array([nn[1], -nn[0]])
def bauen(nur, tag):
    stl = f"_ov_{os.getpid()}_{tag}.stl"; env = dict(os.environ, NUR_BAUTEIL=nur, OBJ_DIR=a.objekt, STL_NAME=stl, SCALE="87", ELEMENTE_AUS="/dev/null", BAUTEIL_PARAM="{}")
    r = subprocess.run([a.py, os.path.join(ROOT, "tools", "baukasten_gen.py"), a.objekt], env=env, capture_output=True, text=True); p = os.path.join(ROOT, "modelle", "stl", stl)
    if not os.path.exists(p): sys.exit("Bau fehlgeschlagen " + r.stderr[-300:])
    m = trimesh.load(p, process=False); os.remove(p); m.apply_scale(1.0 / K); return m
m = bauen((a.mit + "," + a.typ) if a.mit else a.typ, "t"); mm = m.copy(); mm.merge_vertices(); V = np.asarray(mm.vertices); ed = mm.face_adjacency_edges[mm.face_adjacency_angles > 0.5]
sd = [float(x) for x in a.shift.split(",")]; sh = np.array([sd[0] * uu[0] + sd[1] * nn[0], sd[0] * uu[1] + sd[1] * nn[1], sd[2]])
if a.mit:
    from scipy.spatial import cKDTree
    Rr, _ = trimesh.sample.sample_surface(bauen(a.mit, "r"), 200000); mid = 0.5 * (V[ed[:, 0]] + V[ed[:, 1]]); ed = ed[cKDTree(Rr).query(mid)[0] > 0.05]
A, B = V[ed[:, 0]] + sh, V[ed[:, 1]] + sh; cen = 0.5 * (A.mean(0) + B.mean(0)); ext = max(np.ptp(np.concatenate([A, B]), axis=0))
KAM = json.load(open(a.fotos)); cand = []
for nm, k in KAM.items():
    x = np.array(k["Rn"]) @ cen + np.array(k["tn"])
    if x[2] <= 1: continue
    uv = k["f"] * x[:2] / x[2] + [k["cx"], k["cy"]]
    if 0.1 * k["W"] < uv[0] < 0.9 * k["W"] and 0.1 * k["H"] < uv[1] < 0.9 * k["H"]: cand.append((np.linalg.norm(np.array(k["C"]) - cen), nm, k))
cand = [c for c in cand if 12 <= c[0] <= 45] or cand; cand.sort(key=lambda c: abs(c[0] - 25)); tiles = []
for d_, nm, k in cand[: a.n]:
    im = cv2.imread(os.path.join(a.bilder, nm), cv2.IMREAD_COLOR | cv2.IMREAD_IGNORE_ORIENTATION)
    if im is None: continue
    def pr(P):
        X = P @ np.array(k["Rn"]).T + np.array(k["tn"]); z = np.maximum(X[:, 2], 1e-3); return k["f"] * X[:, :2] / z[:, None] + [k["cx"], k["cy"]]
    pa, pb = pr(A), pr(B)
    for p0, p1 in zip(pa, pb): cv2.line(im, tuple(int(v) for v in p0), tuple(int(v) for v in p1), (0, 0, 255), 3)
    c = pr(cen[None])[0]; half = int(max(250, 1.2 * ext * k["f"] / max(np.linalg.norm(np.array(k["C"]) - cen), 1)))
    x0, y0 = int(max(c[0] - half, 0)), int(max(c[1] - half, 0)); t = im[y0:int(c[1] + half), x0:int(c[0] + half)]; t = cv2.resize(t, (600, int(600 * t.shape[0] / max(t.shape[1], 1))))
    cv2.putText(t, nm[-24:], (8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2); tiles.append(t)
h = min(t.shape[0] for t in tiles); cv2.imwrite(a.out, np.hstack([t[:h] for t in tiles])); print("geschrieben", a.out, len(tiles), "Fotos")
