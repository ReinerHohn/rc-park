"""Naehe Drahtgitter <-> Referenzpunkte (GPU, gpu_knn). Aufruf: gitter_naehe.py SEG.json REF1.npy[,REF2.npy] [--tol 0.10]
Abdeckung = Anteil der Referenzpunkte mit Segment innerhalb tol; Treffer = Anteil der Segment-Stuetzpunkte (alle 5 cm) mit Referenzpunkt innerhalb tol. Je Hoehenband.
Referenz = Kantenpunkte (Wolken-Vote K oder Tiefen-Sweep-Konsens). KEINE Wahrheit: beide Quellen koennen dieselben Fehler haben (Register: Quellen-Blindheit)."""
import sys, json, numpy as np, torch
sys.path.insert(0, __file__.rsplit("/", 1)[0]); from gpu_knn import min_abstand
tol = float(sys.argv[sys.argv.index("--tol") + 1]) if "--tol" in sys.argv else 0.10
d = json.load(open(sys.argv[1])); S = d["segmente"] if isinstance(d, dict) else d
pts = []
for s in S:
    a = np.array(s[0]); b = np.array(s[1]); n = max(2, int(np.linalg.norm(b - a) / 0.05)); pts.append(a + (b - a) * np.linspace(0, 1, n)[:, None])
Q = np.vstack(pts).astype(np.float32); bands = [(-9, 12, "z<12"), (12, 15, "12-15"), (15, 99, ">15")]
for rf in sys.argv[2].split(","):
    R = np.load(rf); R = R["P"] if hasattr(R, "files") else R; R = R[:, :3].astype(np.float32)
    f = lambda A, B: (lambda x: np.asarray(x.cpu() if hasattr(x, 'cpu') else x))(min_abstand(A, B)); dq = f(Q, R); dr = f(R, Q)   # je Richtung EIN Aufruf (vorher 3x)
    zq = Q[:, 2]; zr = R[:, 2]
    print("Referenz", rf.split("/")[-1], "Punkte", len(R), "| Segmentpunkte", len(Q))
    for lo, hi, nm in bands:
        mq = (zq >= lo) & (zq < hi); mr = (zr >= lo) & (zr < hi)
        print("  %-5s Treffer %.2f (n=%d)   Abdeckung %.2f (n=%d)" % (nm, (dq[mq] < tol).mean() if mq.any() else float("nan"), mq.sum(), (dr[mr] < tol).mean() if mr.any() else float("nan"), mr.sum()))
