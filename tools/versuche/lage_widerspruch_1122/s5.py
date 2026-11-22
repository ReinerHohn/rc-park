import sys; sys.path.insert(0, "/tmp/claude-29999/-home-oem-git-rc-park/dc62add2-9ee3-4f76-85e0-42c96eea284b/scratchpad/e")
from lib import *
import glob
r = pycolmap.Reconstruction(B22 + "sparse/0")
C = {n: sfm_zu_obj(c) for n, c in zentren(r).items()}
t0 = set(zentren(pycolmap.Reconstruction(B22 + "seiten_modelle/teil0_b/0"))); t1 = set(zentren(pycolmap.Reconstruction(B22 + "seiten_modelle/teil1_b/0")))
K20 = json.load(open(glob.glob(S + "obj20/messprotokoll/SFM-AUSRICHTUNG-*.json")[0]))
print("1120 transformation", {k: K20["transformation"][k] for k in ("s",)}, K20.get("verfahren"))
Z20 = {n: np.array(v["standort"]) for n, v in K20["kameras"].items() if v.get("standort") is not None}
print("1120 Kamerahoehe median", np.median([z[2] for z in Z20.values()]), " 1122", np.median([c[2] for c in C.values()]))
print("1122 teil0 Hoehe median", np.median([C[n][2] for n in t0]), "teil1", np.median([C[n][2] for n in t1]))
print("1120 teil0-Bilder Hoehe median", np.median([Z20[n][2] for n in t0 if n in Z20]), "teil1-Bilder", np.median([Z20[n][2] for n in t1 if n in Z20]))
print("GPS 1120 alle:", kurz(gps_fit(Z20)))
print("GPS 1120 nur teil0-Bilder:", kurz(gps_fit({n: Z20[n] for n in t0 if n in Z20})))
print("GPS 1120 nur teil1-Bilder:", kurz(gps_fit({n: Z20[n] for n in t1 if n in Z20})))
print("GPS 1120 Rest-Bilder:", kurz(gps_fit({n: Z20[n] for n in Z20 if n not in t0 and n not in t1})))
print("GPS 1122 teil0:", kurz(gps_fit({n: C[n] for n in t0})))
# GPS-Rest je Bild unter 1120 vs 1122 fuer teil0
