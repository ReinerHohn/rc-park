import sys; sys.path.insert(0, "/tmp/claude-29999/-home-oem-git-rc-park/dc62add2-9ee3-4f76-85e0-42c96eea284b/scratchpad/e")
from lib import *
import glob, os
sys.path.insert(0, S + "wt/tools")
os.chdir(S + "wt")
import wolke_grundriss_pruefen as WG
zid = OBJ["lod2"]["id"]
GR = WG.grundrisse(OBJ, 60.0)
gf = [np.asarray(g) for b in GR if b["id"] == zid for g in b["ground"]]
andere = [np.asarray(g) for b in GR if b["id"] != zid for g in b["ground"]]
np.save(S + "e/lod2_ziel.npy", np.array(gf[0])); import pickle; pickle.dump(dict(ziel=gf, andere=andere), open(S + "e/lod2.pkl", "wb"))
print("Ziel-Grundflaechen", len(gf), [g.shape for g in gf], "x", gf[0][:, 0].min(), gf[0][:, 0].max(), "y", gf[0][:, 1].min(), gf[0][:, 1].max())
r = pycolmap.Reconstruction(B22 + "sparse/0")
t0 = set(zentren(pycolmap.Reconstruction(B22 + "seiten_modelle/teil0_b/0")))
P0, P1 = [], []
for p in r.points3D.values():
    ims = {stamm(r.images[el.image_id].name) for el in p.track.elements}
    if p.error > 2.0 or len(ims) < 3: continue
    x = sfm_zu_obj(p.xyz)
    (P0 if len(ims & t0) > len(ims) / 2 else P1).append(x)
P0, P1 = np.array(P0), np.array(P1); np.save(S + "e/p22_t0.npy", P0); np.save(S + "e/p22_t1.npy", P1)
K20 = json.load(open(glob.glob(S + "obj20/messprotokoll/SFM-AUSRICHTUNG-*.json")[0]))
T2 = K20["transformation"]; s2 = T2["s"]; R2 = rodr(T2["rvec"]); tt2 = np.array(T2["t"])
r20 = pycolmap.Reconstruction("/media/oem/scan/rc-park_daten/schwabentor-1120/pipe/sfm/sparse/0")
P20 = np.array([(p.xyz - tt2) @ R2 / s2 for p in r20.points3D.values() if p.error < 2.0 and p.track.length() >= 3])
np.save(S + "e/p20.npy", P20)
# Kontrolle: 1120 Kamera aus sparse/0 mit Transformation = Messprotokoll?
Z = zentren(r20); d = [np.linalg.norm((Z[n] - tt2) @ R2 / s2 - np.array(v["standort"])) for n, v in K20["kameras"].items() if n in Z and v.get("standort")]
print("1120 sparse/0 + Transformation vs Messprotokoll: median", np.median(d))
print(len(P0), len(P1), len(P20))
