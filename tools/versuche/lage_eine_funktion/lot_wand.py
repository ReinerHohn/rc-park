"""Dritte, unabhaengige Lotquelle: Wandnormalen der dichten Wolke (senkrechte Waende -> Normalen waagerecht). Leicht: memmap, jeder k-te Punkt."""
import json, numpy as np, math, sys, os
from scipy.spatial.transform import Rotation as Rot
T = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); sys.path.insert(0, T)
import seiten_gps_vereinen as SG
W = "/home/oem/git/rc-park"; D = "/media/oem/scan/rc-park_daten"
def ang(u, v): u = np.asarray(u, float); v = np.asarray(v, float); return math.degrees(math.acos(min(1.0, abs(u @ v) / np.linalg.norm(u) / np.linalg.norm(v))))
dt = np.dtype([("x", "<f4"), ("y", "<f4"), ("z", "<f4"), ("nx", "<f4"), ("ny", "<f4"), ("nz", "<f4"), ("r", "u1"), ("g", "u1"), ("b", "u1")])
for ziel in sys.argv[1:]:
    ply = f"{D}/{ziel}/pipe/dicht/fused.ply"; kj = f"{D}/{ziel}/pipe/kameras.json"; au = f"{W}/modelle/{ziel}/messprotokoll/SFM-AUSRICHTUNG-{ziel}.json"
    if not all(os.path.isfile(p) for p in (ply, kj, au)): print(ziel, "fehlt"); continue
    kopf = open(ply, "rb").read(4096); e = kopf.index(b"end_header\n") + 11; n = int([l for l in kopf[:e].decode(errors="ignore").splitlines() if l.startswith("element vertex")][0].split()[-1])
    V = np.memmap(ply, dtype=dt, mode="r", offset=e, shape=(n,))[::max(1, n // 300000)]
    N = np.c_[V["nx"], V["ny"], V["nz"]].astype(float); N = N[np.isfinite(N).all(1)]; N /= np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-9)
    KJ = json.load(open(kj)); Rs = np.array([b["R"] for b in KJ["bilder"]], float); C = np.array([b["C"] for b in KJ["bilder"]], float)
    ach = np.asarray(SG.lot_aus_bild_achsen(Rs), float)
    dc = np.linalg.norm(C - np.median(C, 0), axis=1); nah = dc <= np.percentile(dc, 70); cm = C[nah].mean(0); eb = np.linalg.svd(C[nah] - cm)[2][2]
    AU = json.load(open(au)); z_m = Rot.from_rotvec(AU["transformation"]["rvec"]).as_matrix()[:, 2]
    up = ach.copy()
    for _ in range(6):                                                      # Wandnormalen: |n.up| < sin 20 Grad, Lot = kleinster Singulaervektor
        w = np.abs(N @ up) < math.sin(math.radians(20)); up_n = np.linalg.svd(N[w], full_matrices=False)[2][2]; up = up_n if up_n @ ach > 0 else -up_n
    # Boden: Normalen fast parallel zu up
    print(f"{ziel}: Wandnormalen {w.sum()} | Wand vs Bildachsen {ang(up, ach):.2f} | Wand vs Ebene {ang(up, eb):.2f} | Wand vs Feinfit {ang(up, z_m):.2f} Grad")
