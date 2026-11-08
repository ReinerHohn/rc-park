#!/usr/bin/env python3
"""test_wolke_umgebung.py - BEWEIS (bekannte Wahrheit) fuer wolke_umgebung.py. Synthetisch: Haus 12x8x8 + Erker (giebel) an +y, Wolke mit bekanntem Rauschen sigma=0.03 m.
  R  gemessenes sigma_0,5 liegt innerhalb 25 % des wahren sigma (Wand ohne Relief: Kachelgroessen liefern ~gleiches sigma)
  U  Strassenebene (z=0, 30 m), Nachbarhaus 6 m neben dem Haus, Himmelspunkte werden entfernt (>= 98 %), Haus + Erker bleiben (>= 98 %)
  K  Kontrolle: Wolke nur aus Haus -> es werden < 2 % entfernt
Aufruf: /media/oem/scan/venv-seg/bin/python -I tools/test_wolke_umgebung.py ; Exit 0 nur wenn alles besteht."""
import sys, os, math
import numpy as np
TOOLS = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, TOOLS)
import trimesh
from manifold3d import Manifold as M, CrossSection as C
import generator_elemente_schleife as GS, bauteil_element_wolke as BE, wolke_umgebung as WU

SIG = 0.03


def surf(tm, n_je_m2, seed):
    rng = np.random.default_rng(seed); S, _ = trimesh.sample.sample_surface(tm, int(tm.area * n_je_m2), seed=seed); return S + rng.normal(0, SIG, S.shape)


def main():
    rng = np.random.default_rng(5); haus = GS.aus_manifold(M.cube((12, 8, 8)).translate((-6, -4, 0)))
    ek, _ = BE.koerper("giebel", dict(cx=0.0, cy=4.0, phi=math.pi / 2, w=2.4, tiefe=1.3, z0=3.0, z1=6.5, gh=1.0), M, C); erker = GS.aus_manifold(ek)
    wahr = trimesh.util.concatenate([haus, erker]); Ph = surf(wahr, 1200, 1); Ph = Ph[Ph[:, 2] > 0.3]          # Unterseite/Fussbereich existiert in echten Wolken nicht (Boden-Ebene)
    nach = GS.aus_manifold(M.cube((10, 8, 9)).translate((12, -4, 0))); Pn = surf(nach, 300, 2); Pn = Pn[Pn[:, 2] > 0.3]
    xs = rng.uniform(-20, 40, 40000); ys = rng.uniform(-25, 25, 40000); Pb = np.c_[xs, ys, rng.normal(0, SIG, 40000)]
    Pb = Pb[(np.abs(Pb[:, 0]) > 0) & ~((Pb[:, 0] > -6) & (Pb[:, 0] < 6) & (Pb[:, 1] > -4) & (Pb[:, 1] < 4))]
    Ps = rng.uniform([-30, -30, 12], [40, 30, 30], (400, 3))
    P = np.vstack([Ph, Pn, Pb, Ps]); typ = np.r_[np.zeros(len(Ph)), np.ones(len(Pn)), np.ones(len(Pb)) * 2, np.ones(len(Ps)) * 3]
    basis = haus; mod = GS.Modell(basis); r = mod.res(P, band=30); zmin = 0.0
    rau = WU.rauschen_messen(P, basis, r, zmin); s05 = rau["kacheln"]["0.5"]["sigma_median"]; ok = True
    print(f"R sigma_0,5 gemessen {s05} (wahr {SIG}); 2 m: {rau['kacheln']['2.0']['sigma_median']}"); ok &= abs(s05 - SIG) <= 0.25 * SIG
    keep, inf = WU.umgebungsmaske(P, basis, r, zmin, s05)
    beh = [float(keep[typ == t].mean()) for t in range(4)]; print(f"U behalten: Haus+Erker {beh[0]:.3f}, Nachbar {beh[1]:.3f}, Strasse {beh[2]:.3f}, Himmel {beh[3]:.3f}", {k: v for k, v in inf.items() if k in ("boden", "ausreisser", "zusammenhang")}, inf["fenster"]["entfernt"])
    print("  Fenster", inf["fenster"]["aussen_m"], inf["fenster"]["innen_m"], "Erker-Anteil behalten", float(keep[(typ == 0) & (P[:, 1] > 4.05)].mean()), "Rest", float(keep[(typ == 0) & (P[:, 1] <= 4.05)].mean()))
    ok &= beh[0] >= 0.98 and beh[1] <= 0.02 and beh[2] <= 0.02 and beh[3] <= 0.02
    Pk = Ph; rk = mod.res(Pk, band=30); kk, ik = WU.umgebungsmaske(Pk, basis, rk, zmin, s05); print(f"K nur Haus: behalten {kk.mean():.4f}", {k: v for k, v in ik.items() if k in ("boden", "ausreisser", "zusammenhang")}, ik["fenster"]["aussen_m"], ik["fenster"]["innen_m"], ik["fenster"]["entfernt"]); ok &= kk.mean() >= 0.98
    print("BESTANDEN" if ok else "FEHLGESCHLAGEN"); sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
