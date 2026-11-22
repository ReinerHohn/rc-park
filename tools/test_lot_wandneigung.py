#!/usr/bin/env python3
"""Test Lot-Runde 22.11.2026: lot_wandneigung (Kippung vs. Anzug, Urteile), kipp_rotvec (echte Kippung im Kasten), lage_bestanden mit Lot, Pruefstand-Vergleich mit Mondkamera."""
import os, sys, math
import numpy as np
T = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, T)
import lot_wandneigung as LW

FEHLER = []
def pruef(b, txt):
    print(("ok   " if b else "FEHLER ") + txt)
    if not b: FEHLER.append(txt)


def turm(t_cm, anzug_cm=0.0, seiten=(0, 1, 2, 3), halb=6.0, h=30.0, n=60000, seed=0):
    """Quaderturm 12 x 12 m, Waende mit Aussennormale +x, -x, +y, -y; Kippung t (cm/m, Spitze wandert dorthin), Anzug a (cm/m, minus = nach innen)."""
    rng = np.random.default_rng(seed); P = []; W = []
    nor = [np.array(v, float) for v in ((1, 0), (-1, 0), (0, 1), (0, -1))]
    for i in seiten:
        nv = nor[i]; dv = np.array([-nv[1], nv[0]]); o = nv * halb
        u = rng.uniform(-halb, halb, n); z = rng.uniform(0, h, n); w = rng.normal(0, 0.03, n) + z * (anzug_cm / 100)
        xy = o + u[:, None] * dv + w[:, None] * nv + z[:, None] * (np.asarray(t_cm) / 100)
        P.append(np.c_[xy, z]); W.append(dict(id=f"w{i}", o=o.tolist(), d=dv.tolist(), n=nv.tolist(), u=[-halb, halb], z_oben=h, laenge=2 * halb))
    return np.vstack(P), W


X, W = turm([-4.0, 2.5]); k = LW.pruefen(X, {}, wand_liste=W)
pruef(k["rc"] == 3 and abs(k["t_cm_m"][0] + 4.0) < 0.3 and abs(k["t_cm_m"][1] - 2.5) < 0.3, f"4 Waende, Kippung (-4, 2,5) cm/m erkannt: {k.get('t_cm_m')} rc {k['rc']}")
X, W = turm([0.3, -0.2], anzug_cm=-3.0); k = LW.pruefen(X, {}, wand_liste=W)
pruef(k["rc"] == 0 and k["anzug_cm_m"] is not None and abs(k["anzug_cm_m"] + 3.0) < 0.3 and k["betrag_cm_m"] < 0.8, f"Anzug -3 cm/m (Verjuengung) ist keine Kippung: Anzug {k.get('anzug_cm_m')}, Kippung {k.get('betrag_cm_m')}, rc {k['rc']}")
X, W = turm([3.0, 0.0], seiten=(0, 2)); k = LW.pruefen(X, {}, wand_liste=W)
pruef(k["rc"] == 3 and k["anzug_cm_m"] is None and abs(k["t_cm_m"][0] - 3.0) < 0.3, f"2 Waende ueber Eck: Anzug a=0 angenommen, Kippung {k.get('t_cm_m')}, rc {k['rc']}")
X, W = turm([3.0, 0.0], seiten=(0, 1)); k = LW.pruefen(X, {}, wand_liste=W)
pruef(k["rc"] == 4, f"nur gegenueberliegende (parallele) Waende -> kein Urteil: {k.get('grund')}")
X, W = turm([3.0, 0.0], seiten=(0,)); k = LW.pruefen(X, {}, wand_liste=W)
pruef(k["rc"] == 4, "eine Wand -> kein Urteil")
k = LW.pruefen(np.zeros((10, 3)), {}, wand_liste=[])
pruef(k["rc"] == 4, "kein LoD2-Ziel -> kein Urteil")

# echte Kippung im Kasten des Feinfits
from scipy.spatial.transform import Rotation as R
import sfm_lod2_ausrichten as SA
for th in (0.0, 1.0, 2.88, -2.5):
    kk = SA.kipp_rotvec(math.radians(1.0), th)
    worst = max(math.degrees(math.acos(min(1.0, R.from_rotvec([sx * kk, sy * kk, th]).apply([0, 0, 1])[2]))) for sx in (-1, 1) for sy in (-1, 1))
    pruef(abs(worst - 1.0) < 0.02, f"kipp_rotvec bei Drehung {math.degrees(th):.0f} Grad: Kastenecke kippt {worst:.3f} Grad (Soll 1,0)")

# lage_bestanden mit Lot
import lage_proben as LP
basis = dict(gps=0, grundriss=0, seiten_blick=None, lage_proben=0)
pruef(LP.lage_bestanden(dict(basis, lot=0)) and LP.lage_bestanden(dict(basis, lot=None)) and not LP.lage_bestanden(dict(basis, lot=3)), "lage_bestanden: Lot 3 faellt, 0/None besteht")
pruef(LP.lot_rc(4) is None and LP.lot_rc(1) is None and LP.lot_rc(3) == 3, "lot_rc: kein Urteil/Absturz -> None")
os.environ["RCPARK_LOT_TOR"] = "hinweis"; pruef(LP.lage_bestanden(dict(basis, lot=3)), "RCPARK_LOT_TOR=hinweis: Lot 3 nur gemeldet"); del os.environ["RCPARK_LOT_TOR"]

# Pruefstand-Vergleich: eine Kamera 'am Mond' in der NEUEN Lage darf den Massstab nicht zerreissen
import lage_pruefstand as PS
rng = np.random.default_rng(1); ref = {f"k{i}": rng.uniform(-30, 30, 3).tolist() for i in range(40)}
kam = {n: (np.asarray(v) + rng.normal(0, 0.05, 3)).tolist() for n, v in ref.items()}; kam["k0"] = [2.277e6, 0.0, 0.0]
v = PS.lage_vergleich(kam, ref)
pruef(abs(v.get("massstab", 0) - 1.0) < 0.01, f"Mondkamera in der neuen Lage: Massstab x{v.get('massstab')}")

print("\n" + ("ALLE TESTS BESTANDEN" if not FEHLER else f"{len(FEHLER)} FEHLER"))
sys.exit(1 if FEHLER else 0)
