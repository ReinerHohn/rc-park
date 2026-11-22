import sys; sys.path.insert(0, "/tmp/claude-29999/-home-oem-git-rc-park/dc62add2-9ee3-4f76-85e0-42c96eea284b/scratchpad/e")
from lib import *
import glob
from scipy.spatial import cKDTree
K20 = json.load(open(glob.glob(S + "obj20/messprotokoll/SFM-AUSRICHTUNG-*.json")[0]))
P20 = np.load(S + "e/p20.npy"); P0 = np.load(S + "e/p22_t0.npy")
def turm(P, rad=7.5):
    w = np.hypot(P[:, 0] + 2.1, P[:, 1] - 15.2) < rad; z = P[w, 2]
    return w.sum(), np.percentile(z, [50, 99, 99.9]).round(2), z.max().round(2)
print("1120 Turm (r 7,5 m um Mitte): n, z p50/p99/p99.9, max", turm(P20))
print("1122 Teil0 Turm:", turm(P0))
# Kamerahoehe ueber Boden aus Sparse-Punkten (1120-Rahmen)
for nm, P, cams in [("1120", P20, {n: np.array(v["standort"]) for n, v in K20["kameras"].items() if v.get("standort")}),
                    ("1122t0", P0, {n: np.array(v["standort"]) for n, v in AUS["kameras"].items() if v.get("standort")})]:
    tr = cKDTree(P[:, :2]); h = []
    for n, c in cams.items():
        if not n.startswith("eigen__IMG") or np.hypot(c[0] + 2, c[1] - 15) > 40: continue
        idx = tr.query_ball_point(c[:2], 1.5)
        if len(idx) < 5: continue
        z = P[idx, 2]; z = z[z < c[2]]
        if len(z) < 5: continue
        h.append(c[2] - np.percentile(z, 10))
    h = np.array(h); print(nm, "Handy-Kameras mit Bodenpunkten", len(h), "Hoehe ueber Boden-p10 median %.2f m (p25 %.2f, p75 %.2f)" % tuple(np.percentile(h, [50, 25, 75])))
