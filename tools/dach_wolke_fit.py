#!/usr/bin/env python3
"""dach_wolke_fit.py - Satteldach-Parameter (baukasten 'satteldach') per CMA-ES in die Punktwolke einpassen (nur Wolkenabstand, ohne Foto): schnell, viele Auswertungen.
Ziel: Mittel(min(Abstand Wolkenpunkt -> Dachflaechen, c)) ueber Wolkenpunkte im Dachbereich (c = Kappung, robust gegen Gauben/Ausreisser). Flaechen: Vorder-/Hinterschraege + beide Giebelwaende (Aussenhaut).
  /media/oem/scan/venv-seg/bin/python -I tools/dach_wolke_fit.py --wolke W.npy --achse-n 0.3338,0.9426 --start u0,u1,ntv,ztv,nf,zf,nth,zth --aus fit.json
ACHTUNG: Wolke am Dach duenn und (Register) ~1 m zu tief - Ergebnis nur als 'naeher an der Wolke', Foto-Diff entscheidet (Regel 5)."""
import numpy as np, json, argparse, cma
import os as _o, sys as _s; _s.path.insert(0, _o.path.dirname(_o.path.abspath(__file__))); from gpu_knn import min_abstand, naechster, ball_anzahl   # GPU (Nutzerregel)
ap = argparse.ArgumentParser(); ap.add_argument("--wolke", required=True); ap.add_argument("--achse-n", default="0.3338,0.9426"); ap.add_argument("--start", required=True); ap.add_argument("--aus", required=True)
ap.add_argument("--kappung", type=float, default=0.5); ap.add_argument("--iter", type=int, default=120); a = ap.parse_args()
n = np.array([float(x) for x in a.achse_n.split(",")]); u = np.array([n[1], -n[0]])
P = np.load(a.wolke)[:, :3]; x0 = np.array([float(v) for v in a.start.split(",")])        # u0,u1,ntv,ztv,nf,zf,nth,zth
pu, pn, pz = P[:, :2] @ u, P[:, :2] @ n, P[:, 2]
sel = (pu > x0[0] - 1.5) & (pu < x0[1] + 1.5) & (pn > x0[6] - 1.5) & (pn < x0[2] + 1.5) & (pz > x0[3] - 0.5) & (pz < x0[5] + 1.5)
Q = np.c_[pu, pn, pz][sel]; print("Wolkenpunkte im Dachbereich", len(Q))
def flaechen(p):
    u0, u1, ntv, ztv, nf, zf, nth, zth = p; L = []
    def quad(A, B, C, D, ns=40):
        s, t = np.meshgrid(np.linspace(0, 1, ns), np.linspace(0, 1, ns)); s, t = s.ravel()[:, None], t.ravel()[:, None]
        return (1 - s) * (1 - t) * A + s * (1 - t) * B + s * t * C + (1 - s) * t * D
    A = lambda uu, nn, zz: np.array([uu, nn, zz])
    L.append(quad(A(u0, ntv, ztv), A(u1, ntv, ztv), A(u1, nf, zf), A(u0, nf, zf), 60))                 # Vorderschraege
    L.append(quad(A(u0, nf, zf), A(u1, nf, zf), A(u1, nth, zth), A(u0, nth, zth), 60))                 # Hinterschraege
    for uu in (u0, u1):                                                                                  # Giebelwaende (Dreieck/Fuenfeck grob als zwei Quads)
        L.append(quad(A(uu, ntv, ztv), A(uu, nf, zf), A(uu, nf, 10.5), A(uu, ntv, 10.5), 25)); L.append(quad(A(uu, nf, zf), A(uu, nth, zth), A(uu, nth, 10.5), A(uu, nf, 10.5), 25))
    return np.vstack(L)
def J(p):
    u0, u1, ntv, ztv, nf, zf, nth, zth = p
    if not (u1 - u0 > 5 and nth < nf < ntv and 10.5 < ztv < zf and 10.5 < zth < zf): return 10.0
    d = min_abstand(Q, flaechen(p)); return float(np.mean(np.minimum(d, a.kappung)))
print("Start J", round(J(x0), 4)); es = cma.CMAEvolutionStrategy(x0, 0.3, dict(popsize=24, seed=1, verbose=-9, maxiter=a.iter))
while not es.stop(): X = es.ask(); es.tell(X, [J(x) for x in X])
b = es.result.xbest; print("Ende J", round(J(b), 4), "Parameter", np.round(b, 3).tolist(), "Auswertungen", es.result.evaluations)
json.dump(dict(start=x0.tolist(), start_J=J(x0), fit=b.tolist(), fit_J=J(b), kappung=a.kappung, auswertungen=int(es.result.evaluations), namen="u0,u1,n_traufe_v,z_traufe_v,n_first,z_first,n_traufe_h,z_traufe_h"), open(a.aus, "w"), indent=1)
