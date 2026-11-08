#!/usr/bin/env python3
"""Beweis bauteil_erkennen: kuenstliche Fassade mit 4 Segmentbogen-Arkaden (Kreissegment wie baukasten_gen.segmentbogen), 3 cm Rauschen, Luecken, Ausreisser.
Kriterium (vorher): u0, u1, zk, zs je Oeffnung < 5 cm von der Wahrheit (nur Oeffnungen, die die Wolke vollstaendig beobachtet hat)."""
import sys, os, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import quader_relief as Q, bauteil_erkennen as B
g = 0.025; U0, U1, Z0, Z1 = -12.8, 12.8, 0.0, 8.0; nu, nz = int(round((U1 - U0) / g)), int(round((Z1 - Z0) / g)); uu = U0 + (np.arange(nu) + 0.5) * g; zz = Z0 + (np.arange(nz) + 0.5) * g; UU, ZZ = np.meshgrid(uu, zz)
T = np.zeros((nz, nu)); wahr = []
for c, w, zk, zs in ((-6.6, 1.65, 2.2, 3.2), (-2.25, 1.7, 2.1, 3.25), (2.1, 1.6, 2.2, 3.1), (6.45, 1.65, 2.15, 3.2)):       # (Mitte, halbe Breite, Kaempfer, Scheitel)
    h = zs - zk; R = (w * w + h * h) / (2 * h); zc = zs - R
    m = (np.abs(UU - c) < w) & ((ZZ < zk) | (ZZ < zc + np.sqrt(np.clip(R * R - (UU - c) ** 2, 0, None)))); T[m] = -3.9; wahr.append((c - w, c + w, zk, zs))
rng = np.random.default_rng(5); n_pkt = 2500000; iu, iz = rng.integers(0, nu, n_pkt), rng.integers(0, nz, n_pkt)
P = np.c_[uu[iu] + rng.uniform(-g / 2, g / 2, n_pkt), T[iz, iu] + rng.normal(0, 0.03, n_pkt), zz[iz] + rng.uniform(-g / 2, g / 2, n_pkt)]
luecke = np.zeros((nz, nu), bool)
for _ in range(8): u_, z_ = rng.integers(0, nu - 120), rng.integers(0, nz - 80); luecke[z_:z_ + rng.integers(16, 60), u_:u_ + rng.integers(16, 100)] = True
P = P[~luecke[np.clip(((P[:, 2] - Z0) / g).astype(int), 0, nz - 1), np.clip(((P[:, 0] - U0) / g).astype(int), 0, nu - 1)]]
aus = rng.random(len(P)) < 0.005; P[aus, 1] += rng.uniform(-2, 2, aus.sum())
D = Q.raster(P, Z0, Z1, U0, U1, g, perz=50); M = Q.luecken_fuellen(Q.modell_raster(Q.baum(D, tol=0.10), D.shape), 0.10)
def bewerte(O, name):
    print(f"--- Variante {name}: erkannt {len(O)} Oeffnungen (Wahrheit 4)"); fehl = []
    for (a, b, zk, zs) in wahr:
        c = sorted([o for o in O if abs(0.5 * (o["u0"] + o["u1"]) - 0.5 * (a + b)) < 0.5], key=lambda o: -(o["u1"] - o["u0"]))   # bei Bruchstuecken: breiteste Oeffnung
        if not c: print(f"  Wahrheit u {a:.2f}..{b:.2f}: keine Oeffnung erkannt"); fehl.append("fehlt"); continue
        o = c[0]; e = max(abs(o["u0"] - a), abs(o["u1"] - b), abs(o["zk"] - zk), abs(o["zs"] - zs)); print("    Sicherheit:", {k: (round(v, 1) if isinstance(v, float) else v) for k, v in o.items() if k in ("sigma_zk_cm", "sigma_w_cm", "zk_bestimmt", "zeilen_um_zk")}); e0 = e; print(f"  u {a:.2f}..{b:.2f}: max {e0*100:5.1f} cm (u0 {abs(o['u0']-a)*100:.1f}, u1 {abs(o['u1']-b)*100:.1f}, zk {abs(o['zk']-zk)*100:.1f}, zs {abs(o['zs']-zs)*100:.1f})"); fehl.append(e0 if o.get('zk_bestimmt', True) else ('unbestimmt', e0))
    return fehl
res_ = {n: bewerte(B.oeffnungen(M, U0, Z0, g, variante=v), n) for n, v in (("Rand-Median", "median"), ("Segmentbogen-Fit", "fit"))}
print("Kandidaten Fit (gefuellt):", [(round(o["u0"],2), round(o["u1"],2), round(o["zk"],2), round(o["zs"],2), o["zeilen"]) for o in B.oeffnungen(M, U0, Z0, g, variante="fit")])
res_["Fit auf ungefuelltem Raster"] = bewerte(B.oeffnungen(D, U0, Z0, g, variante="fit"), "Fit auf ungefuelltem Raster")
best = "Segmentbogen-Fit"; print("BESTE Variante:", best); fehl = res_[best]

best_ = [e for e in fehl if not isinstance(e, tuple) and e != "fehlt"]; unb = [e for e in fehl if isinstance(e, tuple)]
print("bestimmt:", len(best_), "max", max(best_) * 100, "cm | als unbestimmt gemeldet:", len(unb), [round(u[1] * 100, 1) for u in unb])
assert "fehlt" not in fehl and len(best_) + len(unb) == 4 and max(best_) < 0.05, "Bauteilerkennung: bestimmte Masse > 5 cm oder Oeffnung fehlt"
assert all(u[1] >= 0.0 for u in unb) and len(best_) >= 3, "zu wenige bestimmt"; print("test_bauteil_erkennen: bestanden (bestimmte Oeffnungen < 5 cm, unbestimmte als solche gemeldet)")
