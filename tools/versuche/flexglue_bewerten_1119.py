"""Seitentrennung pruefen: je Teilmodell Zahl der Nord-(A)/Sued-(B)-Bilder; liegen beide in einem Modell, wird es auf die Nord-Kameras gelegt und die
Sued-Kameras werden mit ihrer WAHREN Lage verglichen (Sued-Modell teil1 per vereinen3 B_nach_A ins Nord-System). Klein = richtig verbunden, gross = verklebt.
Aufruf: python bewerten.py <sparse-ordner mit Teilmodellen 0,1,...>"""
import sys, glob, json, numpy as np, pycolmap
W = "/media/oem/rcdaten/tmp/mt_seiten"; T = np.array(json.load(open(W + "/vereinen3/vereinen.json"))["B_nach_A"])
A = {i.name: i.projection_center() for i in pycolmap.Reconstruction(W + "/konsens3s/konsens/0").images.values()}
B = {i.name: i.projection_center() for i in pycolmap.Reconstruction(W + "/teil1/sparse/0").images.values()}
nur_a, nur_b = set(A) - set(B), set(B) - set(A); Bw = {n: T[:3, :3] @ c + T[:3, 3] for n, c in B.items()}   # Sued in wahrer Lage, Nord-System
gr = np.ptp(np.array(list(A.values())), 0).max()


def ume(P, Q):
    mp, mq = P.mean(0), Q.mean(0); U, S, Vt = np.linalg.svd((Q - mq).T @ (P - mp)); D = np.eye(3); D[2, 2] = np.sign(np.linalg.det(U @ Vt)); R = U @ D @ Vt
    s = (S * np.diag(D)).sum() / ((P - mp) ** 2).sum(); return s, R, mq - s * R @ mp


for m in sorted(glob.glob(sys.argv[1] + "/*/")):
    r = pycolmap.Reconstruction(m); g = {i.name: i.projection_center() for i in r.images.values()}; ka, kb = sorted(set(g) & nur_a), sorted(set(g) & nur_b)
    zeile = f"{m.rstrip('/').split('/')[-1]}: {len(g)} Bilder, Nord {len(ka)}, Sued {len(kb)}"
    if len(ka) >= 10 and len(kb) >= 5:
        s, R, t = ume(np.array([g[n] for n in ka]), np.array([A[n] for n in ka])); d = np.linalg.norm(s * np.array([g[n] for n in kb]) @ R.T + t - np.array([Bw[n] for n in kb]), axis=1)
        da = np.linalg.norm(s * np.array([g[n] for n in ka]) @ R.T + t - np.array([A[n] for n in ka]), axis=1)
        zeile += f" | Nord passt {100 * np.median(da) / gr:.2f} %, Sued gegen wahre Lage Median {100 * np.median(d) / gr:.2f} % -> " + ("RICHTIG VERBUNDEN" if np.median(d) < 0.02 * gr else "VERKLEBT")
    print(zeile)
