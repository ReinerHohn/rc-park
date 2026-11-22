import sys; sys.path.insert(0, "/tmp/claude-29999/-home-oem-git-rc-park/dc62add2-9ee3-4f76-85e0-42c96eea284b/scratchpad/e")
from lib import *
import collections
r = pycolmap.Reconstruction(B22 + "sparse/0")
C = {n: sfm_zu_obj(c) for n, c in zentren(r).items()}
t0 = zentren(pycolmap.Reconstruction(B22 + "seiten_modelle/teil0_b/0")); t1 = zentren(pycolmap.Reconstruction(B22 + "seiten_modelle/teil1_b/0"))
gp = set(json.load(open(S + "obj22/audit/kamera_plausibel.json"))["ausschliessen"])
fern = {n for n in C if np.linalg.norm(C[n][:2]) > 150}
for ref in ["schwab_v3", "schwabentor-1120"]:
    rr = pycolmap.Reconstruction(f"/media/oem/scan/rc-park_daten/{ref}/pipe/sfm/sparse/0"); Z = zentren(rr)
    print(ref, len(Z), "Bilder; Beispiel", list(Z)[:2])
    for tn, T in [("teil0", t0), ("teil1", t1)]:
        nm = [n for n in T if n in Z and n not in gp and n not in fern]
        if len(nm) < 6: print(" ", tn, "gemeinsam", len(nm)); continue
        a = np.array([C[n] for n in nm]); b = np.array([Z[n] for n in nm])
        s, R, t, _ = robust_sim3(b, a, q=70)          # ref -> 1122-Objektrahmen
        res = np.linalg.norm(b @ R.T * s + t - a, axis=1)
        g = collections.defaultdict(list)
        for n, x in zip(nm, res): g[n.split("__")[0]].append(x)
        print(f"  {tn}: gemeinsam {len(nm)} Rest median {np.median(res):.2f} m p80 {np.percentile(res,80):.2f} max {res.max():.1f}  | je Gruppe " +
              ", ".join(f"{k} {len(v)}:{np.median(v):.2f}" for k, v in g.items()))
        # Ortsabhaengigkeit des Rests: lineare Verzerrung (affin) statt aehnlich?
        A = np.c_[b @ R.T * s + t, np.ones(len(b))]
        w = res < np.percentile(res, 90)
        X, *_ = np.linalg.lstsq(A[w], a[w], rcond=None)
        ra = np.linalg.norm(A @ X - a, axis=1)
        L = X[:3, :3].T; U, Sg, Vt = np.linalg.svd(L[:2, :2])
        print(f"     affin statt aehnlich: Rest median {np.median(ra):.2f} m; 2D-Singulaerwerte {Sg.round(3)} (Anisotropie {Sg[0]/Sg[1]:.3f})")
