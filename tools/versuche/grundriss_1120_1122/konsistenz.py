"""Konsistenz: SfM-Kamerazentren/-Punkte -> Objektrahmen mit der geschriebenen Transformation; Brennweiten je gemeinsamem Bild."""
import os, json
import numpy as np, pycolmap
from scipy.spatial.transform import Rotation
D = "/media/oem/scan/rc-park_daten"; M = "/home/oem/git/rc-park/modelle"; OUT = os.path.dirname(os.path.abspath(__file__))
rec = {}; fpx = {}
for o in ("schwabentor-1120", "schwabentor-1122"):
    a = json.load(open(f"{M}/{o}/messprotokoll/SFM-AUSRICHTUNG-{o}.json")); T = a["transformation"]; s = T["s"]; R = Rotation.from_rotvec(T["rvec"]).as_matrix(); t = np.array(T["t"])
    print(o, "sparse:", a.get("sparse"))
    r = pycolmap.Reconstruction(a.get("sparse") or f"{D}/{o}/pipe/sfm/sparse/0"); rec[o] = r
    inv = lambda X: (np.asarray(X) - t) @ R / s
    d = []
    for im in r.images.values():
        if not im.has_pose: continue
        nm = os.path.splitext(im.name)[0]; c = r.cameras[im.camera_id]; fpx[(o, nm)] = (c.params[0] / max(c.width, c.height), c.params[3] if len(c.params) > 3 else 0, c.width, c.height)
        if nm in a["kameras"]: d.append(np.linalg.norm(inv(im.projection_center()) - np.array(a["kameras"][nm]["standort"])))
    print("  Standort aus Transformation vs. geschrieben: Median %.3f m, max %.3f m (n %d)" % (np.median(d), np.max(d), len(d)))
    P = np.array([p.xyz for p in r.points3D.values()]); Pm = inv(P); w = (Pm[:, 2] > 1.5) & (Pm[:, 2] < 9)
    np.save(f"{OUT}/sparse_wand_{o}.npy", Pm[w].astype(np.float32))
    X = np.load(f"{M}/{o}/sfm/punkte_modell_{o}.npy", mmap_mode="r"); Xs = np.asarray(X[::max(1, len(X) // 400000)], float)
    for nm, Q in (("sparse", Pm[w]), ("dicht npy", Xs[(Xs[:, 2] > 1.5) & (Xs[:, 2] < 9)])):
        q = Q[(np.abs(Q[:, 1] - 15) < 4)]                                    # Schnitt y 11-19: x-Lage West-/Ostwand
        h, e = np.histogram(q[:, 0], bins=np.arange(-16, 12, 0.25)); top = np.argsort(-h)[:4]
        print(f"  {nm}: Schnitt y11-19, x-Gipfel: " + ", ".join(f"{e[i]:+.2f} ({h[i]})" for i in sorted(top)))
common = sorted({n for (o, n) in fpx if o == "schwabentor-1120"} & {n for (o, n) in fpx if o == "schwabentor-1122"})
rat = np.array([fpx[("schwabentor-1122", n)][0] / fpx[("schwabentor-1120", n)][0] for n in common]); k0 = np.array([fpx[("schwabentor-1120", n)][1] for n in common]); k1 = np.array([fpx[("schwabentor-1122", n)][1] for n in common])
print("Brennweite 1122/1120 je gemeinsamem Bild: Median %.3f, P5 %.3f, P95 %.3f, |Abw|>10%%: %d von %d" % (np.median(rat), np.percentile(rat, 5), np.percentile(rat, 95), (np.abs(rat - 1) > .1).sum(), len(rat)))
print("k1 1120 Median %.3f, 1122 Median %.3f" % (np.median(k0), np.median(k1)))
json.dump({n: [fpx[("schwabentor-1120", n)][:2], fpx[("schwabentor-1122", n)][:2]] for n in common}, open(f"{OUT}/brennweiten.json", "w"))
schlecht = [(n, round(r_, 2)) for n, r_ in zip(common, rat) if abs(r_ - 1) > .1]; print("Beispiele:", schlecht[:15])
