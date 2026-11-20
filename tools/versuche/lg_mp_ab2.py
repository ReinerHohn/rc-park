"""lg_mp_ab2.py - sauberer A/B 20.11.2026 fuer LightGlue mp=True (gemischte Genauigkeit): GLEICHE ALIKED-Merkmale (float32, einmal berechnet),
Zuordnung einmal mit mp=False, einmal mit mp=True. Messgroessen: ms je Paar, Treffer je Paar, Anteil identischer Zuordnungen, RANSAC-Inlier (F, 3 px) je Paar.
Aufruf: venv-seg/bin/python -I tools/versuche/lg_mp_ab2.py <bildordner> [--n 30] [--resize 1600] [--kp 4096]"""
import sys, os, time, argparse, glob
import torch, cv2, numpy as np
from lightglue import LightGlue, ALIKED
from lightglue.utils import load_image, rbd
ap = argparse.ArgumentParser(); ap.add_argument("ordner"); ap.add_argument("--n", type=int, default=30); ap.add_argument("--resize", type=int, default=1600); ap.add_argument("--kp", type=int, default=4096); a = ap.parse_args()
dev = "cuda"; torch.cuda.set_per_process_memory_fraction(0.55)
namen = sorted(f for f in glob.glob(os.path.join(a.ordner, "*")) if f.lower().endswith((".jpg", ".jpeg", ".png")) and "__vf_" not in f)[:a.n]
ext = ALIKED(max_num_keypoints=a.kp).eval().to(dev); F = []
for f in namen:
    with torch.inference_mode(): F.append(ext.extract(load_image(f).to(dev), resize=a.resize))
paare = [(i, j) for i in range(len(F)) for j in range(i + 1, min(i + 5, len(F)))]
def lauf(mp):
    m = LightGlue(features="aliked", mp=mp).eval().to(dev); Z = []
    def alle():
        out = []
        for i, j in paare:
            with torch.inference_mode(): out.append(rbd(m({"image0": F[i], "image1": F[j]}))["matches"].cpu().numpy())
        torch.cuda.synchronize(); return out
    alle(); t = time.time(); Z = alle(); return Z, (time.time() - t) / len(paare) * 1000
def inl(Z):
    r = []
    for (i, j), z in zip(paare, Z):
        if len(z) < 8: r.append(0); continue
        P = rbd(F[i])["keypoints"].cpu().numpy()[z[:, 0]]; Q = rbd(F[j])["keypoints"].cpu().numpy()[z[:, 1]]
        _, k = cv2.findFundamentalMat(P, Q, cv2.FM_RANSAC, 3.0, 0.999); r.append(int(k.sum()) if k is not None else 0)
    return np.array(r)
A, ta = lauf(False); B, tb = lauf(True)
g = sum(len(set(map(tuple, x.tolist())) & set(map(tuple, y.tolist()))) for x, y in zip(A, B)); na = sum(len(x) for x in A); nb = sum(len(y) for y in B)
ia, ib = inl(A), inl(B)
print(f"{len(namen)} Bilder, {len(paare)} Paare, resize {a.resize}, {a.kp} Punkte")
print(f"float32: {ta:.1f} ms/Paar, Treffer {na}, RANSAC-Inlier Summe {ia.sum()}, Paare >= 60 Inlier: {(ia >= 60).sum()}")
print(f"gemischt: {tb:.1f} ms/Paar, Treffer {nb}, RANSAC-Inlier Summe {ib.sum()}, Paare >= 60 Inlier: {(ib >= 60).sum()}")
print(f"identische Zuordnungen: {100.0 * g / max(na, 1):.1f} % der float32-Treffer; Paare mit anderer >=60-Entscheidung: {int(((ia >= 60) != (ib >= 60)).sum())}")
