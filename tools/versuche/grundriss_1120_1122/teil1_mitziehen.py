"""Gemeinsamer GPS-Fehler? Teil1 (geschrieben 1122) mit der Teil0-Korrektur (Sim3 1122->1120 aus Teil0-Kameras) mitziehen; Tor A + Kanten."""
import os, sys, json
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kanten as K   # laedt Mengen neu (dauert), nutzt tor_a/gf
OUT = os.path.dirname(os.path.abspath(__file__))
L = json.load(open(f"{OUT}/lagen.json")); st0, st1 = L["st"]["schwabentor-1120"], L["st"]["schwabentor-1122"]; teil = {os.path.splitext(k)[0]: v for k, v in L["teil"].items()}
nm = [n for n in sorted(set(st0) & set(st1)) if teil.get(n) == 0]; X1 = np.array([st1[n] for n in nm]); X0 = np.array([st0[n] for n in nm]); keep = np.ones(len(nm), bool)
for _ in range(6):
    Mx = K.WD.sim3_fit(X1[keep], X0[keep]); r = np.linalg.norm(X1 @ Mx[:3, :3].T + Mx[:3, 3] - X0, axis=1); keep = r < max(3 * np.median(r[keep]), 0.3)
print("Teil0-Korrektur: s %.4f, Rest %.3f m" % (np.cbrt(np.linalg.det(Mx[:3, :3])), np.median(r[keep])))
T1 = np.load(f"{OUT}/p1122_teil1_lage1122.npy").astype(float) @ Mx[:3, :3].T + Mx[:3, 3]; T0 = np.load(f"{OUT}/p1122_teil0_lage1120.npy").astype(float)
np.save(f"{OUT}/p1122_teil1_mitgezogen.npy", T1.astype(np.float32))
for name, P in (("Teil1 mitgezogen", T1), ("Teil0 (1120-Lage) + Teil1 mitgezogen", np.vstack([T0, T1]))):
    a, n = K.tor_a(P); ks = [k for g in K.gf for k in K.WD.kanten_messen(g, {"x": P})]
    print(f"== {name}: Tor A {100*a:.1f} %")
    for k in ks:
        v = k["teile"]["x"]; print(f"   Kante {k['von']}->{k['bis']}: " + (f"Lage {v['lage_m']:+.2f}, Dicke {v['dicke_m']:.2f}, n {v['n']}" if "lage_m" in v else f"kein Urteil n {v['n']}"))
# Kamerastandorte Teil1 mitgezogen gegen GPS-Richtung: Azimut um Turmmitte
c = np.array([-2.09, 15.16]); n1 = [n for n in st1 if teil.get(n) == 1]; Y = np.array([st1[n] for n in n1]) @ Mx[:3, :3].T + Mx[:3, 3]
print("Teil1-Kameras mitgezogen: Azimut-Median %.0f Grad, Entfernung %.1f m" % (np.degrees(np.median(np.arctan2(Y[:, 1] - c[1], Y[:, 0] - c[0]))) % 360, np.median(np.hypot(*(Y[:, :2] - c).T))))
