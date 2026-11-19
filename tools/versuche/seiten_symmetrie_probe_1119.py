#!/usr/bin/env python3
"""seiten_symmetrie_probe_1119.py <modell_A> <modell_B> <db.db> --aus <ordner> - VERSUCH 19.11.2026: Rueckseiten-Modell B ueber die SYMMETRIE an das Vorderseiten-Modell A setzen.
Gedanke: die Verwechslung selbst ist eine Messung. Die 'geklappte' Lage (B-Wand auf A-Wand, Kameras auf derselben Seite) entsteht aus der wahren Lage durch eine halbe
Drehung um die senkrechte Turmachse. Also: wahre Lage = geklappte Lage, um 180 Grad um die Achse gedreht (waagerecht: x -> 2a - x). Die Achse a (2 Unbekannte) geht durch den
Helm; gesucht wird das a, bei dem die gedrehten OBEREN Punkte von B wieder auf die oberen Punkte von A fallen (ein Helm mit 2-zaehliger Drehsymmetrie bildet sich auf sich ab).
Voraussetzung: der Bau ist oben drehsymmetrisch - sonst gaebe es die Verwechslung meist gar nicht. Ausgabe: verbund.npz (Punkte A, Punkte B in A, Kameras), Kennzahlen."""
import sys, os, json, sqlite3, collections, argparse
import numpy as np, pycolmap
from scipy.spatial import cKDTree
M = 2147483647
def um(P, Q):
    mp, mq = P.mean(0), Q.mean(0); H = (Q - mq).T @ (P - mp) / len(P); U, S, Vt = np.linalg.svd(H); D = np.diag([1, 1, np.sign(np.linalg.det(U @ Vt))]); R = U @ D @ Vt
    s = (S * np.diag(D)).sum() / max(1e-12, ((P - mp) ** 2).sum(1).mean()); return s, R, mq - s * R @ mp
def lies(p):
    r = pycolmap.Reconstruction(p); ims = [im for im in r.images.values() if im.has_pose]
    return r, {im.name: np.array([q.point3D_id if q.has_point3D() else -1 for q in im.points2D], dtype=np.int64) for im in ims}, {i: q.xyz for i, q in r.points3D.items()}, ims
ap = argparse.ArgumentParser(); ap.add_argument("a"); ap.add_argument("b"); ap.add_argument("db"); ap.add_argument("--aus", required=True); a = ap.parse_args(); os.makedirs(a.aus, exist_ok=True)
A, PA, XA, IA = lies(a.a); B, PB, XB, IB = lies(a.b); db = sqlite3.connect(f"file:{a.db}?mode=ro", uri=True); nm = dict(db.execute("select image_id, name from images")); kor = {}
for pid, data in db.execute("select pair_id, data from two_view_geometries where rows >= 15"):
    x, y = nm[pid // M], nm[pid % M]; m = np.frombuffer(data, np.uint32).reshape(-1, 2)
    if x in PB and y in PA and x not in PA: x, y, m = y, x, m[:, ::-1]
    if not (x in PA and y in PB) or y in PA or x in PB: continue
    qa, qb = PA[x][m[:, 0]], PB[y][m[:, 1]]; ok = (qa >= 0) & (qb >= 0)
    for u, w in zip(qb[ok], qa[ok]): kor.setdefault(int(u), collections.Counter())[int(w)] += 1
P = np.array([XB[k] for k in kor]); Q = np.array([XA[c.most_common(1)[0][0]] for c in kor.values()])
# Lot von A aus den Kamera-x-Achsen, Vorzeichen aus den y-Achsen (Bild-y zeigt nach unten)
RA = [im.cam_from_world().rotation.matrix() for im in IA]; up = np.linalg.svd(np.array([r[0] for r in RA]))[2][-1]; up *= -np.sign(np.median(np.array([r[1] for r in RA]) @ up))
thr = 0.02 * np.percentile(np.linalg.norm(Q - np.median(Q, 0), axis=1), 50); rng = np.random.default_rng(0); best = (0, None)
for _ in range(20000):
    ix = rng.choice(len(P), 3, replace=False); s, R, t = um(P[ix], Q[ix])
    if not np.isfinite(s) or s <= 0 or abs((R @ up) @ up) < 0.94: continue                   # Lot muss erhalten bleiben (< 20 Grad)
    inl = np.linalg.norm(s * P @ R.T + t - Q, axis=1) < thr
    if inl.sum() > best[0]: best = (int(inl.sum()), inl)
inl = best[1]
for _ in range(3): s, R, t = um(P[inl], Q[inl]); inl = np.linalg.norm(s * P @ R.T + t - Q, axis=1) < thr
print(f"geklappte Lage: {int(inl.sum())} von {len(P)} Punktpaaren, Rest Median {np.median(np.linalg.norm(s * P[inl] @ R.T + t - Q[inl], axis=1)):.4f} Einheiten, Massstab {s:.3f}")
# waagerechtes Achsensystem
e1 = np.cross(up, [1, 0, 0]); e1 /= np.linalg.norm(e1); e2 = np.cross(up, e1); E = np.array([e1, e2, up])
def lok(X): return np.asarray(X) @ E.T
pa = lok(np.array(list(XA.values()))); ca = lok(np.array([im.projection_center() for im in IA])); fb = lambda X: lok(s * np.asarray(X) @ R.T + t)
pb = fb(np.array(list(XB.values()))); cb = fb(np.array([im.projection_center() for im in IB])); q = lok(Q[inl])              # q = gemeinsame Wandpunkte (Turmwand)
boden = np.percentile(ca[:, 2], 20); wm = np.median(q[:, :2], 0); H = np.percentile(q[:, 2], 98) - boden                  # H ~ Hoehe der gemeinsamen Wand ueber den Kameras
nah = lambda X: np.linalg.norm(X[:, :2] - wm, axis=1) < 0.6 * H
oa = pa[nah(pa) & (pa[:, 2] > np.percentile(q[:, 2], 90))]; ob = pb[nah(pb) & (pb[:, 2] > np.percentile(q[:, 2], 90))]
print(f"Wandhoehe ueber Kameras H = {H:.3f}; obere Punkte (ueber der gemeinsamen Wand, Umkreis 0,6 H): A {len(oa)}, B {len(ob)}")
if len(oa) < 30 or len(ob) < 30: sys.exit("zu wenige obere Punkte fuer die Achssuche")
baum = cKDTree(oa); d0 = 0.01 * H; a0 = np.median(np.vstack([oa, ob])[:, :2], 0); bestes = (-1, a0)
for schritt, weite in ((0.02 * H, 0.5 * H), (0.004 * H, 0.03 * H)):
    z = bestes[1]; g = np.arange(-weite, weite + 1e-9, schritt)
    for dx in g:
        for dy in g:
            ac = z + [dx, dy]; rb = ob.copy(); rb[:, :2] = 2 * ac - rb[:, :2]; n = int((baum.query(rb, distance_upper_bound=d0)[0] < np.inf).sum())
            if n > bestes[0]: bestes = (n, ac)
n, ac = bestes; print(f"Achse: {n} von {len(ob)} gedrehten oberen B-Punkten treffen A (Schranke 1 % H) -> {100 * n / len(ob):.0f} %; Achse {np.round(ac - wm, 3)} von der Wandmitte (in H: {np.round((ac - wm) / H, 3)})")
dreh = lambda X: np.c_[2 * ac - X[:, :2], X[:, 2]]
pb2, cb2 = dreh(pb), dreh(cb); fa = np.median(q[:, :2], 0); fbm = 2 * ac - fa
print(f"Turmtiefe (Abstand Vorderwand - gedrehte Rueckwand) = {np.linalg.norm(fa - fbm):.3f} Einheiten = {np.linalg.norm(fa - fbm) / H:.2f} H")
col = lambda rec: np.array([p.color for p in rec.points3D.values()], np.uint8)
np.savez(os.path.join(a.aus, "verbund.npz"), pa=pa.astype(np.float32), pb=pb2.astype(np.float32), ca=ca.astype(np.float32), cb=cb2.astype(np.float32), fa=col(A), fb=col(B), achse=ac, wm=wm, H=H, boden=boden, pb_geklappt=pb.astype(np.float32))
json.dump(dict(s=float(s), R=R.tolist(), t=t.tolist(), E=E.tolist(), achse=ac.tolist(), H=float(H), inlier=int(inl.sum()), obere_treffer=n, obere_b=len(ob)), open(os.path.join(a.aus, "symmetrie.json"), "w"))
