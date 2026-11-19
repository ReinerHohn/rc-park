#!/usr/bin/env python3
"""seiten_vereinen_probe_1119.py <modell_A> <modell_B> <db.db> [--aus sim3.json] - VERSUCH 19.11.2026: zwei getrennt gerechnete Seitenmodelle ueber die (auch die geloeschten)
Bildpaare der Ursprungsdatenbank zueinander legen. Gemeinsame 3D-Punkte -> Sim3-Hypothesen (RANSAC). Jede Hypothese wird nach dem Winkel zwischen den mittleren Blickrichtungen
der Kameras von A und B eingeordnet: 'geklappt' (< 60 Grad = B auf derselben Seite wie A, die Verwechslung) oder 'gegenueber' (> 120 Grad) oder 'seitlich'.
Ausgabe: beste Hypothese je Klasse mit Zahl der erklaerten Punktpaare. Idee: die Verwechslung ist durch den Paar-Pruefer VERBOTEN, also zaehlt die beste nicht geklappte."""
import sys, json, sqlite3, collections, argparse
import numpy as np, pycolmap
M = 2147483647
def um(P, Q):
    mp, mq = P.mean(0), Q.mean(0); H = (Q - mq).T @ (P - mp) / len(P); U, S, Vt = np.linalg.svd(H); D = np.diag([1, 1, np.sign(np.linalg.det(U @ Vt))]); R = U @ D @ Vt
    return (S * np.diag(D)).sum() / max(1e-12, ((P - mp) ** 2).sum(1).mean()), R, mq - ((S * np.diag(D)).sum() / max(1e-12, ((P - mp) ** 2).sum(1).mean())) * R @ mp
def lies(p):
    r = pycolmap.Reconstruction(p); ims = [im for im in r.images.values() if im.has_pose]
    return r, {im.name: np.array([q.point3D_id if q.has_point3D() else -1 for q in im.points2D], dtype=np.int64) for im in ims}, {i: q.xyz for i, q in r.points3D.items()}, ims
ap = argparse.ArgumentParser(); ap.add_argument("a"); ap.add_argument("b"); ap.add_argument("db"); ap.add_argument("--aus"); ap.add_argument("--rel", type=float, default=0.02); a = ap.parse_args()
A, PA, XA, IA = lies(a.a); B, PB, XB, IB = lies(a.b); db = sqlite3.connect(f"file:{a.db}?mode=ro", uri=True); nm = dict(db.execute("select image_id, name from images"))
kor = {}; npaar = 0; je_paar = collections.Counter()
for pid, data in db.execute("select pair_id, data from two_view_geometries where rows >= 15"):
    x, y = nm[pid // M], nm[pid % M]; m = np.frombuffer(data, np.uint32).reshape(-1, 2)
    if x in PB and y in PA and x not in PA: x, y, m = y, x, m[:, ::-1]
    if not (x in PA and y in PB) or y in PA or x in PB: continue
    qa, qb = PA[x][m[:, 0]], PB[y][m[:, 1]]; ok = (qa >= 0) & (qb >= 0); npaar += 1
    for u, w in zip(qb[ok], qa[ok]): kor.setdefault(int(u), collections.Counter())[int(w)] += 1
print(f"A {len(PA)} Bilder {len(XA)} Punkte | B {len(PB)} Bilder {len(XB)} Punkte | Bildpaare A-B {npaar} | gemeinsame Punkte {len(kor)}")
if len(kor) < 12: sys.exit("zu wenige gemeinsame Punkte")
P = np.array([XB[k] for k in kor]); Q = np.array([XA[c.most_common(1)[0][0]] for c in kor.values()])
up = np.linalg.svd(np.array([im.cam_from_world().rotation.matrix()[0] for im in IA]))[2][-1]
def hor(v): v = v - up * (v @ up); return v / max(1e-9, np.linalg.norm(v))
vA = hor(np.median([im.cam_from_world().rotation.matrix()[2] for im in IA], 0)); VB = np.array([im.cam_from_world().rotation.matrix()[2] for im in IB])
thr = a.rel * np.percentile(np.linalg.norm(Q - np.median(Q, 0), axis=1), 50); rng = np.random.default_rng(0); best = {}
for _ in range(20000):
    ix = rng.choice(len(P), 3, replace=False); s, R, t = um(P[ix], Q[ix])
    if not np.isfinite(s) or s <= 0: continue
    inl = np.linalg.norm(s * P @ R.T + t - Q, axis=1) < thr; k = int(inl.sum())
    w = float(np.degrees(np.arccos(np.clip(vA @ hor(np.median(VB @ R.T, 0)), -1, 1)))); kl = "geklappt" if w < 60 else ("gegenueber" if w > 120 else "seitlich")
    kipp = float(np.degrees(np.arccos(np.clip(abs((R @ up) @ up), -1, 1))))          # bleibt das Lot erhalten? (B hat dasselbe Lot wie A, wenn die Abbildung stimmt)
    if kipp > 20: kl += "_gekippt"
    if k > best.get(kl, (0,))[0]: best[kl] = (k, w, kipp, s, R, t, inl)
for kl, (k, w, kipp, s, R, t, inl) in sorted(best.items(), key=lambda kv: -kv[1][0]):
    s2, R2, t2 = um(P[inl], Q[inl]); e = np.linalg.norm(s2 * P @ R2.T + t2 - Q, axis=1); print(f"  {kl:22s}: {k:5d} von {len(P)} Punktpaaren ({100 * k / len(P):.0f} %), Blickwinkel A/B {w:4.0f} Grad, Lot-Kippung {kipp:3.0f} Grad, Massstab B->A {s2:.3f}")
if a.aus: json.dump({kl: dict(n=int(v[0]), winkel=v[1], kippung=v[2], s=float(v[3]), R=np.asarray(v[4]).tolist(), t=np.asarray(v[5]).tolist()) for kl, v in best.items()}, open(a.aus, "w"))
