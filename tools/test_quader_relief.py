#!/usr/bin/env python3
"""Beweis quader_relief an KUENSTLICHER SZENE (Wahrheit bekannt): Wand s=0, 2 Erker (0,8 m vor der Wand, z 5-11), 4 Segmentbogen-Arkaden (3,3 m breit, 3,9 m tief),
Treppengiebel-Oberkante; Wolke = Oberflaeche (s_vorn) + 3 cm Rauschen, 12 % Luecken (Schatten/Verdeckung), 0,5 % Ausreisser. Kriterium (vorher festgelegt, Plan SPEC_BEWEIS_ANSATZ): Kantenlage < 5 cm.
Vergleich: adaptiver Quaderbaum vs gleichmaessiges Raster 0,10 m (Carving-Analogon) bei gleicher Quaderzahl-Grenze."""
import sys, os, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import quader_relief as Q
g = 0.025; U0, U1, Z0, Z1 = -12.8, 12.8, 0.0, 16.0; nu, nz = int(round((U1 - U0) / g)), int(round((Z1 - Z0) / g)); uu = U0 + (np.arange(nu) + 0.5) * g; zz = Z0 + (np.arange(nz) + 0.5) * g; UU, ZZ = np.meshgrid(uu, zz)
T = np.zeros((nz, nu))                                                                  # Wahrheit s_vorn je Zelle
for a, b in ((-9.75, -8.0), (8.25, 9.75)): T[(UU >= a) & (UU < b) & (ZZ >= 5) & (ZZ < 11)] = 0.8
for c in (-6.6, -2.25, 2.1, 6.45):                                                       # Bogen: Rechteck bis z 2,2 + Segmentbogen bis 3,2
    w = 1.65; m = (np.abs(UU - c) < w) & (ZZ < 2.2 + 1.0 * np.sqrt(np.clip(1 - ((UU - c) / w) ** 2, 0, 1))); T[m] = -3.9
T[ZZ > 14.0] = np.nan; T[(ZZ > 12.0) & (np.abs(UU) > 8)] = np.nan                       # ausserhalb Treppengiebel-Silhouette: kein Koerper (Stufen 1 m)
st = (np.abs(UU) < 8) & (ZZ > 12.0); T[st & (ZZ > 12.0 + 2.0 * (1 - np.abs(UU) / 8) // 0.5 * 0.5 + 0.0)] = np.nan
rng = np.random.default_rng(3); n_pkt = 3500000
iu, iz = rng.integers(0, nu, n_pkt), rng.integers(0, nz, n_pkt); ok = np.isfinite(T[iz, iu]); iu, iz = iu[ok], iz[ok]
P = np.c_[uu[iu] + rng.uniform(-g / 2, g / 2, len(iu)), T[iz, iu] + rng.normal(0, 0.03, len(iu)), zz[iz] + rng.uniform(-g / 2, g / 2, len(iu))]
luecke = np.zeros((nz, nu), bool)
for _ in range(25): u_, z_ = rng.integers(0, nu - 120), rng.integers(0, nz - 80); luecke[z_:z_ + rng.integers(16, 80), u_:u_ + rng.integers(16, 120)] = True   # Luecken (Schatten/Autos), kein Fehler messbar
P = P[~luecke[np.clip(((P[:, 2] - Z0) / g).astype(int), 0, nz - 1), np.clip(((P[:, 0] - U0) / g).astype(int), 0, nu - 1)]]
aus = rng.random(len(P)) < 0.005; P[aus, 1] += rng.uniform(-2, 2, aus.sum())             # Ausreisser
D = Q.raster(P, Z0, Z1, U0, U1, g, perz=50)
for tol in (0.05, 0.10):
    B = Q.baum(D, tol=tol); M = Q.modell_raster(B, D.shape); e = Q.fehler(M, T); nm = Q.verschmelzen(B, D, tol)
    print(f"adaptiv tol {tol:.2f}: Quader {len(B)} (verschmolzen {nm}), Fehler s je Zelle p50 {e['p50']*100:.1f} cm p90 {e['p90']*100:.1f} cm p99 {e['p99']*100:.1f} cm max {e['max']*100:.0f} cm")
Ug = Q.gleichmaessig(D, 4); Mg = Q.modell_raster(Ug, D.shape); eg = Q.fehler(Mg, T); print(f"gleichmaessig 0,10 m: Quader {len(Ug)}, p50 {eg['p50']*100:.1f} cm p90 {eg['p90']*100:.1f} cm p99 {eg['p99']*100:.1f} cm max {eg['max']*100:.0f} cm")
B = Q.baum(D, tol=0.10); M = Q.luecken_fuellen(Q.modell_raster(B, D.shape), 0.10)
beob = np.isfinite(D)
z = np.argmin(np.abs(zz - 8.0)); r = lambda A: np.nan_to_num(A[z], nan=-9) > 0.4
def kanten(m, zeile=None):
    d = np.diff(m.astype(int)); return uu[1:][d != 0]
def beobachtete(kt, z):                                          # nur Wahrheitskanten, neben denen die Wolke beobachtet hat (0,2 m links und rechts)
    k = int(round(0.2 / g)); out = []
    for x in kt:
        i = int(round((x - U0) / g)); out.append(beob[z, max(i - k, 0):i + k].mean() > 0.9)
    return np.array(out)
kt, km = kanten(r(T)), kanten(r(M)); bz = beobachtete(kt, z); print("Erkerkanten z 8 m  Wahrheit", kt.round(2), "beobachtet", bz, " Modell", km.round(2))
for x in kt[bz]: assert np.min(np.abs(km - x)) < 0.05, f"Erkerkante {x:.2f} > 5 cm"
z = np.argmin(np.abs(zz - 1.0)); r = lambda A: np.nan_to_num(A[z], nan=0) < -1.0; kt, km = kanten(r(T)), kanten(r(M)); bz = beobachtete(kt, z); print("Bogenkanten z 1 m  Wahrheit", kt.round(2), "beobachtet", bz, " Modell", km.round(2))
for x in kt[bz]: assert np.min(np.abs(km - x)) < 0.05, f"Bogenkante {x:.2f} > 5 cm"
print("test_quader_relief: bestanden (Kanten < 5 cm)")
