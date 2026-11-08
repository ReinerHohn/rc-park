#!/usr/bin/env python3
"""wolke_mincut.py - BS49 Eigenbau: Wolkenebenen -> Zellzerlegung (Vorzeichenvektor, Voxel-Zuordnung) -> Min-Cut (scipy) -> wasserdichtes STL.
Nur numpy/scipy/trimesh/manifold3d (permissiv). Netzrahmen in m, STL in mm (m/0.087).
  venv-seg/bin/python -I tools/wolke_mincut.py [--vox 0.1 --merge 0.2 --lam 1.0 ...]"""
import json, glob, argparse, numpy as np, trimesh, manifold3d as m3
from scipy.spatial import cKDTree, HalfspaceIntersection, ConvexHull
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import maximum_flow
R = "/media/oem/scan/rc-park_null/"
ap = argparse.ArgumentParser()
ap.add_argument("--vox", type=float, default=0.1); ap.add_argument("--merge", type=float, default=0.2)
ap.add_argument("--minpts", type=int, default=8000); ap.add_argument("--lam", type=float, default=1.0)
ap.add_argument("--supp", type=float, default=0.9); ap.add_argument("--tail", type=float, default=1.0)
ap.add_argument("--rand", type=float, default=3.0); ap.add_argument("--prior", type=float, default=0.3); ap.add_argument("--bfak", type=float, default=0.3); ap.add_argument("--aus", default=R + "mincut/mincut_v1.stl"); ap.add_argument("--nray", type=int, default=120000); ap.add_argument("--cpu", action="store_true", help="kNN/Normalen auf CPU (cKDTree + numpy eigh) statt GPU")
a = ap.parse_args()
box = np.array([-14.6, 2.7, 0.6, 15.7, 17.0, 19.9]); lo, hi = box[:3] - 0.5, box[3:] + 0.5
X = np.load(R + "wolke_netzrahmen.npy").astype(np.float64); X = X[np.all((X >= lo) & (X <= hi), 1)]
lo = lo - np.array([a.rand, a.rand, 0.0]); hi = hi + a.rand; print("Punkte", len(X))
# --- Ebenen (n.x + d = 0), nach Punktzahl, nahe parallele zusammenfassen
E = [e for e in json.load(open(R + "wolke_foto/ebenen.json")) if e["punkte"] >= a.minpts]; E.sort(key=lambda e: -e["punkte"])
P = []
for e in E:
    n = np.array(e["n"]); n /= np.linalg.norm(n); d = e["d"]
    if any(abs(n @ q[0]) > 0.995 and abs(d - q[1] * np.sign(n @ q[0])) < a.merge for q in P): continue
    P.append((n, d))
# ANNAHME: Begrenzungsebenen (Gebaeudekasten) schliessen Rueck-/Seiten-/Bodenflaeche, Quelle: Bounding-Box der Wolke
NB = 0
for n_, d_ in [((1, 0, 0), -box[3]), ((-1, 0, 0), box[0]), ((0, 1, 0), -box[4]), ((0, 0, 1), -box[5]), ((0, 0, -1), box[2])]:
    P.append((np.array(n_, float), float(d_))); NB += 1
NP = len(P) - NB; bmask = sum(1 << i for i in range(NP, len(P)))
print("Ebenen nach Zusammenfassen", len(P), "von", len(E))
# --- Voxelgitter, Zellen = Vorzeichenvektor
v = a.vox; g0 = lo; dims = np.ceil((hi - lo) / v).astype(int); print("Gitter", dims, dims.prod())
ix = np.stack(np.meshgrid(*[np.arange(k) for k in dims], indexing="ij"), -1).reshape(-1, 3)
C = g0 + (ix + 0.5) * v
code = np.zeros(len(C), np.int64)
for i, (n, d) in enumerate(P): code |= ((C @ n + d) > 0).astype(np.int64) << i
uc, cid = np.unique(code, return_inverse=True); nc = len(uc); print("Zellen", nc)
cid3 = cid.reshape(dims)
vol = np.bincount(cid, minlength=nc) * v ** 3
# --- Daten aus Wolke: Oberflaechenvoxel, Normalen, Kameras
pi = np.floor((X - g0) / v).astype(int); pi = np.clip(pi, 0, dims - 1)
surf = np.zeros(dims, np.int32); np.add.at(surf, tuple(pi.T), 1)
rng = np.random.default_rng(1); S = X[rng.choice(len(X), min(a.nray, len(X)), replace=False)]
def normalen(X, S, k=16, gpu=True):
    """Flaechennormale (kleinster Eigenvektor der k-Nachbar-Kovarianz) je Zeile von S. GPU: knn_points + geschlossene 3x3-Formel (kleinster_ev aus wolke_streiffilter; torch eigh batched = OOM). Vorzeichen beliebig (wie numpy eigh), Verbraucher nutzen abs()."""
    if gpu:
        import sys, torch; sys.path.insert(0, "/media/oem/scan/p3d_site"); from pytorch3d.ops import knn_points
        def kleinster_ev(A):
            q = (A[:, 0, 0] + A[:, 1, 1] + A[:, 2, 2]) / 3; p1 = A[:, 0, 1] ** 2 + A[:, 0, 2] ** 2 + A[:, 1, 2] ** 2
            p2 = (A[:, 0, 0] - q) ** 2 + (A[:, 1, 1] - q) ** 2 + (A[:, 2, 2] - q) ** 2 + 2 * p1; p = (p2 / 6).sqrt().clamp_min(1e-30)
            I = torch.eye(3, dtype=A.dtype, device=A.device); B = (A - q[:, None, None] * I) / p[:, None, None]; r = (torch.linalg.det(B) / 2).clamp(-1, 1)
            lam = q + 2 * p * torch.cos(torch.acos(r) / 3 + 2 * np.pi / 3); M = A - lam[:, None, None] * I
            c = torch.stack([torch.linalg.cross(M[:, 0], M[:, 1]), torch.linalg.cross(M[:, 0], M[:, 2]), torch.linalg.cross(M[:, 1], M[:, 2])], 1)
            j = c.norm(dim=2).argmax(1); e = c[torch.arange(len(c)), j]; return e / e.norm(dim=1, keepdim=True).clamp_min(1e-30)
        c0 = X.mean(0); Xg = torch.as_tensor(X - c0, dtype=torch.float32, device="cuda")[None]; out = []
        for i in range(0, len(S), 100000):
            q = torch.as_tensor(S[i:i + 100000] - c0, dtype=torch.float32, device="cuda")[None]; idx = knn_points(q, Xg, K=k).idx[0]
            Nb = Xg[0][idx].double(); Nb = Nb - Nb.mean(1, keepdim=True); out.append(kleinster_ev(torch.einsum("nki,nkj->nij", Nb, Nb)).cpu().numpy())
        return np.concatenate(out)
    kd = cKDTree(X); _, nb = kd.query(S, k); Q = X[nb] - X[nb].mean(1, keepdims=True)
    return np.linalg.eigh(np.einsum("nki,nkj->nij", Q, Q))[1][:, :, 0]
Nn = normalen(X, S, 16, gpu=not a.cpu)
cams = np.array([json.load(open(f))["kamera"]["standort_xyz"] for f in sorted(glob.glob("/home/oem/git/rc-park/modelle/kaufhaus_null5/messprotokoll/K-*.json")) if json.load(open(f)).get("kamera", {}).get("standort_xyz")], float)
print("Kameras", len(cams))
# je Punkt naechste Kamera auf Normalen-Seite
dif = cams[None] - S[:, None]; dist = np.linalg.norm(dif, axis=2); cosn = np.abs(np.einsum("nci,ni->nc", dif, Nn)) / dist
sc = dist + 1e6 * (cosn < 0.3); j = sc.argmin(1); ok = sc[np.arange(len(S)), j] < 1e5
S, Nn, dif, dist, j = S[ok], Nn[ok], dif[ok], dist[ok], j[ok]
cam = cams[j]; dirn = (cam - S) / dist[np.arange(len(S)), j][:, None]
free = np.zeros(dims, np.float32); occ = np.zeros(dims, np.float32)
def march(t0, t1, arr):
    ts = np.arange(t0, t1, v * 0.7)
    for t in ts:
        m = (S + dirn * t)
        k = np.floor((m - g0) / v).astype(int); okk = np.all((k >= 0) & (k < dims), 1)
        np.add.at(arr, tuple(k[okk].T), 1.0)
march(0.3, 45, free) if False else None
# frei: von Punkt+0.3 m bis Kamera (max 45 m), belegt: 0.1..tail hinter dem Punkt
dmax = dist[np.arange(len(S)), j]
for t in np.arange(0.3, 45, v * 0.8):
    m = S + dirn * t; sel = t < dmax - 0.5
    k = np.floor((m[sel] - g0) / v).astype(int); okk = np.all((k >= 0) & (k < dims), 1); np.add.at(free, tuple(k[okk].T), 1.0)
for t in np.arange(0.1, a.tail, v * 0.8):
    m = S - dirn * t; k = np.floor((m - g0) / v).astype(int); okk = np.all((k >= 0) & (k < dims), 1); np.add.at(occ, tuple(k[okk].T), 1.0)
F = np.bincount(cid, weights=free.ravel(), minlength=nc); O = np.bincount(cid, weights=occ.ravel(), minlength=nc)
Fv = F / np.maximum(vol / v ** 3, 1); Ov = O / np.maximum(vol / v ** 3, 1)
print("Zellen mit frei>0.05/Vox:", int((Fv > 0.05).sum()), " belegt>0.05:", int((Ov > 0.05).sum()))
# --- Nachbarschaft + Flaeche + Oberflaechenstuetzung der Zellgrenzen
pair = {}
sup_vox = (surf > 0)
for ax in range(3):
    s0 = [slice(None)] * 3; s1 = [slice(None)] * 3; s0[ax] = slice(0, -1); s1[ax] = slice(1, None)
    A = cid3[tuple(s0)].ravel(); B = cid3[tuple(s1)].ravel(); dif_ = A != B
    sp = (sup_vox[tuple(s0)] | sup_vox[tuple(s1)]).ravel()[dif_]
    for x, y, s in zip(A[dif_], B[dif_], sp):
        k = (min(x, y), max(x, y)); t = pair.setdefault(k, [0, 0]); t[0] += 1; t[1] += int(s)
print("Nachbarpaare", len(pair))
# --- Graph: Quelle = innen, Senke = aussen
Wmax = 1000.0; src, snk = nc, nc + 1; r, c, w = [], [], []
def add(u, vv, cap):
    r.extend([u, vv]); c.extend([vv, u]); w.extend([cap, cap])
for (x, y), (n, s) in pair.items():
    ar = n * v * v; frac = s / n
    cap = a.lam * ar * max(0.05, 1 - a.supp * frac * 1.0)
    if (int(uc[x]) ^ int(uc[y])) & ~bmask == 0: cap *= a.bfak
    add(x, y, cap)
INF = 1e9; dr, dc, dw = [], [], []
# aussen-Terminal: Zellen mit Voxeln am Kastenrand (ohne Boden)
edge = np.zeros(nc, bool)
for ax in (0, 1, 2):
    for end in (0, -1):
        if ax == 2 and end == 0: continue
        sl = [slice(None)] * 3; sl[ax] = end; edge[np.unique(cid3[tuple(sl)])] = True
uni_out = 1.0 * Ov * vol / 1.0 * 4.0   # Kosten fuer 'aussen' bei Belegtstimmung
uni_in = 1.0 * Fv * vol / 1.0 * 4.0    # Kosten fuer 'innen' bei Freiraum
out_t = np.zeros(nc); in_t = np.zeros(nc)
# Quelle->u Kapazitaet = Kosten 'aussen'; u->Senke = Kosten 'innen'
cap_s = uni_out + a.prior * vol; cap_t = uni_in.copy(); cap_t[edge] += 1e6
# Teilvolumen am Rand: Randzellen sind Aussen
rows = r + list(np.full(nc, src)) + list(np.arange(nc))
cols = c + list(np.arange(nc)) + list(np.full(nc, snk))
vals = w + list(cap_s) + list(cap_t)
sc_ = 1000.0
G = coo_matrix((np.round(np.array(vals) * sc_).astype(np.int64).clip(0, 2**31 - 1).astype(np.int32), (rows, cols)), shape=(nc + 2, nc + 2)).tocsr()
G.sum_duplicates()
res = maximum_flow(G, src, snk); flow = res.flow
# erreichbar von Quelle im Restgraph = innen
resid = (G - flow).tocsr(); resid.data = (resid.data > 0).astype(np.int8); resid.eliminate_zeros()
from scipy.sparse.csgraph import breadth_first_order
reach = breadth_first_order(resid, src, directed=True, return_predecessors=False)
inside = np.zeros(nc, bool); inside[reach[reach < nc]] = True
print("Zellstat (vol, Fv, Ov, rand):", *[(round(vol[i],1),round(Fv[i],2),round(Ov[i],2),int(edge[i])) for i in np.argsort(-vol)[:15]]); print("Fluss", res.flow_value / sc_, "Innenzellen", int(inside.sum()), "Innenvolumen m3", float(vol[inside].sum()))
# --- Geometrie: je Innenzelle konvexe Huelle, Vereinigung per manifold3d
H = np.array([[*n, d] for n, d in P] + [[1, 0, 0, -hi[0]], [-1, 0, 0, lo[0]], [0, 1, 0, -hi[1]], [0, -1, 0, lo[1]], [0, 0, 1, -hi[2]], [0, 0, -1, lo[2]]])
# Halbraum: n.x + d > 0 ist Bit=1; HalfspaceIntersection erwartet A x + b <= 0
meshes = []; fail = 0
for ci in np.where(inside)[0]:
    vox = C[cid == ci]
    if len(vox) == 0: continue
    ip = vox.mean(0); bits = uc[ci]
    hs = []
    for i, (n, d) in enumerate(P):
        hs.append([*(-n), -d] if (bits >> i) & 1 else [*n, d])
    hs += [[1, 0, 0, -hi[0]], [-1, 0, 0, lo[0]], [0, 1, 0, -hi[1]], [0, -1, 0, lo[1]], [0, 0, 1, -hi[2]], [0, 0, -1, lo[2]]]
    hs = np.array(hs, float); hs[:, 3] -= 0.003  # 3 mm Ueberlappung gegen Float-Nahtluecken
    if np.any(hs[:, :3] @ ip + hs[:, 3] >= 0): ip = vox[np.argmin(np.max(vox @ hs[:, :3].T + hs[:, 3], 1))]
    try:
        hi_ = HalfspaceIntersection(hs, ip); pts = hi_.intersections; pts = pts[np.isfinite(pts).all(1)]
        hull = ConvexHull(pts); mm = trimesh.Trimesh(pts, hull.simplices, process=True); trimesh.repair.fix_normals(mm)
        meshes.append(mm)
    except Exception as ex:
        fail += 1
print("Zellkoerper", len(meshes), "Fehler", fail)
ms = []
for mm in meshes:
    mf = m3.Manifold(m3.Mesh(mm.vertices.astype(np.float32), mm.faces.astype(np.uint32)))
    if mf.status() == m3.Error.NoError and mf.volume() > 0: ms.append(mf)
U = m3.Manifold.batch_boolean(ms, m3.OpType.Add)
mo = U.to_mesh(); T = trimesh.Trimesh(np.array(mo.vert_properties)[:, :3], np.array(mo.tri_verts), process=False)
print("manifold status", U.status(), "genus", U.genus())
print("Vereinigung: Dreiecke", len(T.faces), "wasserdicht", T.is_watertight, "Volumen m3", round(T.volume, 1), "Komponenten", len(T.split(only_watertight=False)))
Tmm = trimesh.Trimesh(T.vertices / 0.087, T.faces, process=False); Tmm.export(a.aus); print("STL", a.aus, "wasserdicht(mm)", Tmm.is_watertight)
