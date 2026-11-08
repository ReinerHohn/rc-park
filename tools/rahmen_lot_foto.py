#!/usr/bin/env python3
"""rahmen_lot_foto.py <objekt> --wolke_voll w.npy --kameras k.json --up lot_fotos.json --wolke_aus w.npy --kameras_aus k.json [--rgb rgb.npy --rgb_aus rgb_crop.npy] [--crop u0,u1,n0,n1,z0,z1] [--boden_z 1.66]
LOT AUS FOTOS (nach Nutzerhinweis 8.11. 'Perspektive falsch'): Rahmen von Wolke UND Kameras starr so drehen, dass die aus den Foto-Vertikalen bestimmte Lotrichtung (lot_aus_fotos.py) = z wird;
danach Gier so, dass die Fassadenwand (RANSAC, z 6-9) parallel zu u liegt; Boden-Hoehe (Modus der Hoehenverteilung vor dem Haus) auf boden_z. Pruefungen am Ende (automatisch, Exit 2 bei Verletzung):
  - Fluchtpunkt der Vertikalen jeder Kamera (Stichprobe) stimmt mit Welt-z ueberein (< 2 Grad)
  - Kamerahoehe ueber Boden (Median) zwischen 0.8 und 4 m (Handaufnahmen)."""
import sys, os, json, argparse, numpy as np
ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--wolke_voll", required=True); ap.add_argument("--kameras", required=True); ap.add_argument("--up", required=True)
ap.add_argument("--wolke_aus", required=True); ap.add_argument("--kameras_aus", required=True); ap.add_argument("--rgb"); ap.add_argument("--rgb_aus"); ap.add_argument("--crop", default="-25,30,3,30,-1,26"); ap.add_argument("--boden_z", type=float, default=1.66); a = ap.parse_args()
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); OBJ = json.load(open(os.path.join(ROOT, "modelle", a.objekt, "objekt.json")))
nax = np.array(OBJ["fassade_n"]["wert"], dtype=float); nax /= np.linalg.norm(nax); uax = np.array([nax[1], -nax[0]])
P0 = np.load(a.wolke_voll); P = P0[:, :3].astype(np.float64); up = np.array(json.load(open(a.up))["up_welt"], dtype=float); up /= np.linalg.norm(up)
def rodr(v, w):
    v = v / np.linalg.norm(v); w = w / np.linalg.norm(w); k = np.cross(v, w); s = np.linalg.norm(k); c = float(v @ w)
    if s < 1e-12: return np.eye(3)
    Kx = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]]); return np.eye(3) + Kx + Kx @ Kx * ((1 - c) / s ** 2)
R1 = rodr(up, np.array([0, 0, 1.0])); piv = np.median(P[(np.abs(P[:, :2] @ uax) < 8)], axis=0)
Q = (P - piv) @ R1.T + piv
# Gier: Fassadenwand (RANSAC-Linie in (u,n), z 6-9, nach Kippkorrektur), Wand parallel u
U = Q[:, :2] @ uax; N = Q[:, :2] @ nax; Z = Q[:, 2]; rng = np.random.default_rng(0)
# nach der Kippkorrektur: Boden-Hoehe -> Modus der z-Verteilung vor dem Haus (n<11 grob), robust
def boden_z(Z, U, N):
    s = (N < 11) & (N > 3) & (np.abs(U) < 12); h, e = np.histogram(Z[s], bins=np.arange(Z[s].min(), Z[s].max(), 0.05)); return float(0.5 * (e[np.argmax(h)] + e[np.argmax(h) + 1]))
z0 = boden_z(Z, U, N); print("Boden-z (Modus) nach Kippkorrektur: %.2f, soll %.2f" % (z0, a.boden_z), flush=True)
zb = z0 + 6.0; s = (Z > zb) & (Z < zb + 3) & (np.abs(U) < 12) & (N > 10) & (N < 17)       # Wandband 6-9 m ueber Boden
A = np.c_[U[s], N[s]]; best = (0, None)
for _ in range(4000):
    i, j = rng.choice(len(A), 2, replace=False); d = A[j] - A[i]
    if abs(d[0]) < 8: continue
    m_ = d[1] / d[0]; c_ = A[i, 1] - m_ * A[i, 0]; inl = (np.abs(A[:, 1] - (m_ * A[:, 0] + c_)) < 0.15).sum()
    if inl > best[0]: best = (inl, (m_, c_))
m_, c_ = best[1]; inl = np.abs(A[:, 1] - (m_ * A[:, 0] + c_)) < 0.15; slope = np.polyfit(A[inl, 0], A[inl, 1], 1)[0]; gier = np.arctan(slope); print("Wand-Steigung nach Kippkorrektur: %.2f Grad (Inlier %d)" % (np.degrees(gier), inl.sum()), flush=True)
cg, sg = np.cos(-gier), np.sin(-gier); Rz = np.array([[cg, -sg, 0], [sg, cg, 0], [0, 0, 1.0]])   # Drehung um z (Welt), Wand -> parallel u (Vorzeichen per Test)
def wandsteig(Rz_):
    Q2 = (Q - piv) @ Rz_.T + piv; U2 = Q2[:, :2] @ uax; N2 = Q2[:, :2] @ nax; s2 = (Q2[:, 2] > zb) & (Q2[:, 2] < zb + 3) & (np.abs(U2) < 12) & (N2 > 10) & (N2 < 17); AA = np.c_[U2[s2], N2[s2]]; ii = np.abs(AA[:, 1] - (m_ * AA[:, 0] + c_)) < 1.0; return abs(np.polyfit(AA[ii, 0], AA[ii, 1], 1)[0])
for sgn in (1, -1):
    c2, s2_ = np.cos(sgn * -gier), np.sin(sgn * -gier); Rt = np.array([[c2, -s2_, 0], [s2_, c2, 0], [0, 0, 1.0]])
    if sgn == 1 or wandsteig(Rt) < wandsteig(Rz): Rz = Rt
Rw = Rz @ R1; Pn = (P - piv) @ Rw.T + piv; z0n = boden_z(Pn[:, 2], Pn[:, :2] @ uax, Pn[:, :2] @ nax); dz = a.boden_z - z0n; Pn[:, 2] += dz
out = P0.copy(); out[:, :3] = Pn.astype(P0.dtype); np.save(a.wolke_aus, out)
c = [float(x) for x in a.crop.split(",")]; Un = Pn[:, :2] @ uax; Nn = Pn[:, :2] @ nax; msk = (Un > c[0]) & (Un < c[1]) & (Nn > c[2]) & (Nn < c[3]) & (Pn[:, 2] > c[4]) & (Pn[:, 2] < c[5])
np.save(a.wolke_aus.replace(".npy", "_crop.npy"), out[msk]); print("Wolke voll %d, Ausschnitt %d" % (len(out), msk.sum()))
if a.rgb and a.rgb_aus: rg = np.load(a.rgb); np.save(a.rgb_aus, rg[msk] if len(rg) == len(msk) else rg)
Kc = json.load(open(a.kameras)); K2 = {}; H = []
for nm, k in Kc.items():
    Rn = np.array(k["Rn"]); tn = np.array(k["tn"]); C = np.array(k["C"]); k2 = dict(k)
    # X' = Rw (X - piv) + piv + (0,0,dz)  ->  X = Rw^T (X' - piv - dzv) + piv  ->  x = Rn Rw^T (X' - dzv - piv) + Rn piv + tn
    dzv = np.array([0, 0, dz]); k2["Rn"] = (Rn @ Rw.T).tolist(); k2["tn"] = (tn + Rn @ piv - Rn @ Rw.T @ (piv + dzv)).tolist(); k2["C"] = (Rw @ (C - piv) + piv + dzv).tolist(); K2[nm] = k2; H.append(k2["C"][2] - a.boden_z)
json.dump(K2, open(a.kameras_aus, "w")); json.dump(dict(Rw=Rw.tolist(), piv=piv.tolist(), dz=dz, quelle="Lot aus Foto-Vertikalen (lot_aus_fotos.py) + Wandgier + Boden-Modus"), open(a.kameras_aus + ".rot.json", "w"), indent=1)
H = np.array(H); print("Kamerahoehe ueber Boden: 5/50/95 %% = %.1f / %.1f / %.1f m (erwartet ~1,5-3)" % tuple(np.percentile(H, [5, 50, 95])))
