import sys; sys.path.insert(0, "/tmp/claude-29999/-home-oem-git-rc-park/dc62add2-9ee3-4f76-85e0-42c96eea284b/scratchpad/e")
from lib import *
r = pycolmap.Reconstruction(B22 + "sparse/0")
C = {n: sfm_zu_obj(c) for n, c in zentren(r).items()}
t0 = set(zentren(pycolmap.Reconstruction(B22 + "seiten_modelle/teil0_b/0"))); t1 = set(zentren(pycolmap.Reconstruction(B22 + "seiten_modelle/teil1_b/0")))
gp = set(json.load(open(S + "obj22/audit/kamera_plausibel.json"))["ausschliessen"])
fern = {n for n in C if np.linalg.norm(C[n][:2]) > 150}
o20 = json.load(open(S + "obj20/objekt.json"))
print("rahmen 1120", o20["rahmen"]["mitte_utm"], o20["rahmen"]["xhat_utm"], " 1122", OBJ["rahmen"]["mitte_utm"], OBJ["rahmen"]["xhat_utm"])
import glob
a20 = glob.glob(S + "obj20/messprotokoll/SFM-AUSRICHTUNG-*.json"); print(a20)
K20 = json.load(open(a20[0]))["kameras"]
Z20 = {n: np.array(v["standort"]) for n, v in K20.items() if v.get("standort") is not None}


def zerlege(s, R):
    yaw = np.degrees(np.arctan2(R[1, 0], R[0, 0])); tilt = np.degrees(np.arccos(np.clip(R[2, 2], -1, 1)))
    return f"Drehung um z {yaw:+.2f} Grad, Kippung {tilt:.2f} Grad, Massstab x{s:.4f}"


for tn, T in [("teil0", t0), ("teil1", t1)]:
    nm = [n for n in T if n in Z20 and n not in gp and n not in fern and np.linalg.norm(Z20[n][:2]) < 150]
    a = np.array([C[n] for n in nm]); b = np.array([Z20[n] for n in nm])
    s, R, t, res = robust_sim3(a, b, q=70)
    print(f"{tn}: 1122-Lage -> 1120-Lage (n {len(nm)}): {zerlege(s, R)}, Versatz {np.round(t,2)}, Rest median {np.median(res):.2f} m")
# gemeinsamer Fit auf teil0, Rest der teil1-Kameras
for ref in ["schwab_v3", "schwabentor-1120"]:
    Z = zentren(pycolmap.Reconstruction(f"/media/oem/scan/rc-park_daten/{ref}/pipe/sfm/sparse/0"))
    n0 = [n for n in t0 if n in Z and n not in gp and n not in fern]; n1 = [n for n in t1 if n in Z and n not in gp and n not in fern]
    b0 = np.array([Z[n] for n in n0]); a0 = np.array([C[n] for n in n0])
    s, R, t, res0 = robust_sim3(b0, a0, q=70)
    b1 = np.array([Z[n] for n in n1]); a1 = np.array([C[n] for n in n1])
    r1 = np.linalg.norm(b1 @ R.T * s + t - a1, axis=1)
    print(f"{ref}: Fit auf teil0 ({len(n0)}, Rest {np.median(res0):.2f}) -> teil1-Kameras ({len(n1)}) liegen in 1122 im Median {np.median(r1):.2f} m daneben (p10 {np.percentile(r1,10):.2f} p90 {np.percentile(r1,90):.2f})")
    s1, R1, tt1, rr1 = robust_sim3(b1, a1, q=70)
    # relative Lage teil1 gegen teil0: (s1,R1) vs (s,R)
    Rr = R1 @ R.T; print(f"   teil1 relativ zu teil0 (1122 gegen {ref}): {zerlege(s1 / s, Rr)}")
