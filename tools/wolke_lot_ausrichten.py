#!/usr/bin/env python3
"""wolke_lot_ausrichten.py <objekt> --wolke w.npy --kameras k.json --wolke_aus w_lot.npy --kameras_aus k_lot.json [--wolke_rgb ...]
Starre Drehung (keine Verformung) von Wolke UND Kameras: Boden waagerecht (u-Neigung 0), Wand lotrecht (kein Ueberhang), Wandnormale = fassade_n (Gier 0).
Grund (8.11.): Umeyama auf Kamerazentren legt die Drehung um flach liegende Kameras schlecht fest -> Wolke 1,6 Grad quer, 2,1 Grad Ueberhang gekippt. Physik als Vorgabe
(Boden eben, Fassade lotrecht), Drehpunkt = Wandmitte. Pruefung: Ebenen nach der Drehung neu angepasst (Ausgabe)."""
import sys, os, json, argparse, numpy as np
ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--wolke", required=True); ap.add_argument("--kameras", required=True); ap.add_argument("--wolke_aus", required=True); ap.add_argument("--kameras_aus", required=True)
ap.add_argument("--zmin_wand", type=float, default=2.5); a = ap.parse_args()
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); OBJ = json.load(open(os.path.join(ROOT, "modelle", a.objekt, "objekt.json")))
nax = np.array(OBJ["fassade_n"]["wert"], dtype=float); nax /= np.linalg.norm(nax); uax = np.array([nax[1], -nax[0]])
B = np.array([[uax[0], uax[1], 0], [nax[0], nax[1], 0], [0, 0, 1.0]])    # Welt -> lokal (u,n,z)
Wall = np.load(a.wolke); P = Wall[:, :3].astype(np.float64); L = P @ B.T
def rob(A, y, tol0=0.4, tolmin=0.08, it=8):
    m = np.ones(len(y), bool)
    for q in range(it):
        c = np.linalg.lstsq(A[m], y[m], rcond=None)[0]; r = np.abs(A @ c - y); m = r < max(tol0 * (0.7 ** q), tolmin)
    return c
G0 = (L[:, 1] < 11) & (L[:, 1] > 3) & (np.abs(L[:, 0]) < 12); G0 &= (L[:, 2] < 2.0) & (L[:, 2] > -1.0)   # Platz (Indexmenge, fest)
W0 = (np.abs(L[:, 0]) < 8) & (L[:, 2] > a.zmin_wand) & (L[:, 2] < 10) & (L[:, 1] > 13.0) & (L[:, 1] < 14.0)
def fits(L):
    cg = rob(np.c_[L[G0, 0], L[G0, 1], np.ones(G0.sum())], L[G0, 2], tol0=0.6, tolmin=0.5, it=1); cw = rob(np.c_[L[W0, 0], L[W0, 2], np.ones(W0.sum())], L[W0, 1], tol0=0.4, tolmin=0.3)
    return cg, cw, L[W0].mean(0)
def rodrigues(v, w):   # minimale Drehung, die Einheitsvektor v auf w legt
    v = v / np.linalg.norm(v); w = w / np.linalg.norm(w); k = np.cross(v, w); s_ = np.linalg.norm(k); c_ = float(v @ w)
    if s_ < 1e-12: return np.eye(3)
    K_ = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]]); return np.eye(3) + K_ + K_ @ K_ * ((1 - c_) / s_ ** 2)
piv = fits(L)[2]; cg, cw, _ = fits(L); print("Ebenen vorher: Boden", np.round(cg, 4), "n_Boden", int(G0.sum()), "Wand", np.round(cw, 4), "n_Wand", int(W0.sum()), flush=True)
R1 = rodrigues(np.array([-cg[0], -cg[1], 1.0]), np.array([0, 0, 1.0]))            # Boden-Normale -> z (Roll + Nick)
cg1, cw1, _ = fits((L - piv) @ R1.T + piv); ang = np.arctan(cw1[0]); c_, s_ = np.cos(-ang * 0 + ang), np.sin(ang)
Rz = np.array([[c_, s_, 0], [-s_, c_, 0], [0, 0, 1]])                                 # Gier: Wandnormale -> n (Vorzeichen per Pruefung)
best = None
for sg in (1, -1):
    Rl_ = np.array([[np.cos(sg * ang), -np.sin(sg * ang), 0], [np.sin(sg * ang), np.cos(sg * ang), 0], [0, 0, 1]]) @ R1; c1, c2, _ = fits((L - piv) @ Rl_.T + piv); e = abs(c2[0])
    if best is None or e < best[0]: best = (e, Rl_)
Rl = best[1]
cg, cw, _ = fits((L - piv) @ Rl.T + piv)
print("NACH Drehung: Boden u-Neigung %.3f Grad, Wand Gier %.3f Grad, Wand Ueberhang %.3f Grad" % (np.degrees(np.arctan(cg[0])), np.degrees(np.arctan(cw[0])), np.degrees(np.arctan(cw[1]))))
Rw = B.T @ Rl @ B; pw = piv @ B                    # Drehung in Weltachsen, Pivot in Welt
Pn = (P - pw) @ Rw.T + pw; out = Wall.copy(); out[:, :3] = Pn.astype(Wall.dtype); np.save(a.wolke_aus, out)
K = json.load(open(a.kameras)); K2 = {}
for nm, k in K.items():
    Rn = np.array(k["Rn"]); tn = np.array(k["tn"]); C = np.array(k["C"]); k2 = dict(k); k2["Rn"] = (Rn @ Rw.T).tolist(); k2["tn"] = (tn + Rn @ pw - Rn @ Rw.T @ pw).tolist(); k2["C"] = (Rw @ (C - pw) + pw).tolist(); K2[nm] = k2
json.dump(K2, open(a.kameras_aus, "w")); json.dump(dict(R=Rw.tolist(), pivot=pw.tolist(), quelle="Boden eben, Wand lotrecht (starre Drehung)"), open(a.kameras_aus + ".rot.json", "w"), indent=1); print("geschrieben", a.wolke_aus, a.kameras_aus)
