"""Punktmengen fuer den Kantenvergleich (venv-colmap): 1122-Teile (dicht) in geschriebener Lage und in 1120-Lage; 1120 sparse nach Teil der Beobachter."""
import os, sys, json, collections
import numpy as np, pycolmap
from scipy.spatial.transform import Rotation
sys.path.insert(0, "/home/oem/git/rc-park/.claude/worktrees/agent-a5d004d794431467c/tools")
import wand_dicke_tor as WD
D = "/media/oem/scan/rc-park_daten"; M = "/home/oem/git/rc-park/modelle"; OUT = os.path.dirname(os.path.abspath(__file__))
from sfm_seiten_modelle import ply_kopf, PLY_SATZ
def teile_laden_mm(sm, au, n_max=400000):
    st = {k: np.asarray(v["standort"], float) for k, v in au["kameras"].items()}; P, I = {}, {}
    for e in sm.get("teile", []):
        if e.get("teil") not in (sm.get("vereint") or []) or not e.get("modell"): continue
        fu = (e.get("dicht") or {}).get("fused"); r = pycolmap.Reconstruction(e["modell"]); X, Y = [], []
        for im in r.images.values():
            nm = os.path.splitext(im.name)[0]
            if im.has_pose and nm in st: X.append(im.projection_center()); Y.append(st[nm])
        X, Y = np.array(X), np.array(Y); keep = np.ones(len(X), bool)
        for _ in range(5):
            Mx = WD.sim3_fit(X[keep], Y[keep]); rest = np.linalg.norm(X @ Mx[:3, :3].T + Mx[:3, 3] - Y, axis=1); keep = rest < max(3 * np.median(rest[keep]), 0.3)
        n, h, _ = ply_kopf(fu); d = np.memmap(fu, PLY_SATZ, mode="r", offset=h, shape=(n,))
        idx = np.sort(np.random.default_rng(0).choice(n, min(n, n_max), replace=False)); p = np.asarray(d["p"][idx], float)
        P[str(e["teil"])] = p @ Mx[:3, :3].T + Mx[:3, 3]; I[str(e["teil"])] = dict(kameras=len(X), inlier=int(keep.sum()), rest_median_m=round(float(np.median(rest[keep])), 3), s=round(float(np.cbrt(np.linalg.det(Mx[:3, :3]))), 4))
    return P, I
sm = json.load(open(f"{D}/schwabentor-1122/pipe/sfm/seiten_modelle.json"))
for o in ("schwabentor-1122", "schwabentor-1120"):
    au = json.load(open(f"{M}/{o}/messprotokoll/SFM-AUSRICHTUNG-{o}.json"))
    P, I = teile_laden_mm(sm, au); print("1122-Teile in Lage", o, I)
    for k, v in P.items(): np.save(f"{OUT}/p1122_teil{k}_lage{o[-4:]}.npy", v.astype(np.float32))
# 1120 sparse: Punkte nach Teil (1122) der beobachtenden Bilder
L = json.load(open(f"{OUT}/lagen.json")); teil = L["teil"]
r = pycolmap.Reconstruction(f"{D}/schwabentor-1120/pipe/sfm/sparse/0"); a = json.load(open(f"{M}/schwabentor-1120/messprotokoll/SFM-AUSRICHTUNG-schwabentor-1120.json"))
T = a["transformation"]; s = T["s"]; R = Rotation.from_rotvec(T["rvec"]).as_matrix(); t = np.array(T["t"])
nm = {i: im.name for i, im in r.images.items()}; F = {k: [] for k in ("t0", "t1", "fern", "sonst")}
fern = {f"eigen__IMG_20261106_{x}.jpg" for x in ("110741", "110743", "110749", "110754", "110756", "110801", "110802", "111235", "111235_2", "111237")}
for p in r.points3D.values():
    ids = [nm[e.image_id] for e in p.track.elements]; c = collections.Counter(teil.get(n, -1) for n in ids)
    X = (np.asarray(p.xyz) - t) @ R / s
    if any(n in fern for n in ids): F["fern"].append(X)
    k, v = c.most_common(1)[0]
    if v >= 0.6 * len(ids) and k in (0, 1): F[f"t{k}"].append(X)
    else: F["sonst"].append(X)
for k, v in F.items(): np.save(f"{OUT}/p1120_sparse_{k}.npy", np.array(v, np.float32)); print("1120 sparse", k, len(v))
