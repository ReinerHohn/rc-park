#!/usr/bin/env python3
"""wolke_entzerren_lod2.py - GENERISCH: verzerrte Fotowolke (SfM aus einseitigen Strassenfotos) affin auf die amtliche Umgebung ziehen.

Warum (Kaufhaus 2026-11-04): Die Aehnlichkeitstransformation (sfm_lod2_ausrichten) legt Fassaden richtig auf LoD2-Waende, aber eine SfM-Wolke aus
Fotos von EINER Seite ist in sich verzerrt (Brennweite/Verzeichnung schlecht bestimmt): Kaufhaus-Wolke Traufe/Erkerabstand 0,48, Foto 018 0,57;
Wolkendach 3,35 m unter DOM1 bei passenden Nachbarfassaden. Massstabsfreie Verhaeltnisse widersprechen -> keine 7-Parameter-Loesung moeglich.
Hier: X' = s R (X * (1,1,kz)) + t (8 Parameter, Standard; frei affin 12 mit --modell affin), robust, ICP, gegen LoD2-Waende + LoD2-Daecher ALLER Gebaeude im Umkreis + DGM1, Klassen gleich gewichtet
(Wand / Dach / Boden je 1/3), Regularisierung A -> Aehnlichkeit (Gewicht --reg). Ergebnis ist eine FORM-Wolke fuer Sichtvergleich, Hybrid und
Fassadenproportionen - KEIN Mass (Masse kommen aus LoD2/DOM1/Foto-Protokollen; die Zielflaechen selbst sind LoD2).

  /media/oem/scan/venv-seg/bin/python -W ignore -I tools/wolke_entzerren_lod2.py modelle/<obj>/objekt.json <seite> [--n 60000] [--modell aehnlich_z|affin] [--reg 0.3] [--radius 50]
liest sfm/dicht_<seite>_modell.npy, schreibt sfm/dicht_<seite>_entzerrt.npy + audit/wolke_entzerren_<seite>.json (A, b, Residuen je Klasse vorher/nachher).
"""
import sys, os, json, glob, argparse, numpy as np
from scipy.spatial import cKDTree
from scipy.optimize import least_squares
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def ziel(obj, radius, dichte=0.3):
    import lod2_gebaeude as LG
    R = obj["rahmen"]; c0 = np.array(R["mitte_utm"]); xh, yh = np.array(R["xhat_utm"]), np.array(R["yhat_utm"])
    lok = lambda P: np.c_[(P[:, :2] - c0) @ xh, (P[:, :2] - c0) @ yh, P[:, 2] - R["gelaende"]]
    pts, nrm, kl = [], [], []; rng = np.random.default_rng(0)
    for meta, polys in LG.extract(obj["lod2"]["gml"], center=tuple(c0), radius=radius):
        for t, P in polys:
            if t not in ("WallSurface", "RoofSurface"): continue
            Q = lok(P); n = np.zeros(3)
            for i in range(1, len(Q) - 1):
                n = np.cross(Q[i] - Q[0], Q[i + 1] - Q[0])
                if np.linalg.norm(n) > 1e-6: break
            if np.linalg.norm(n) < 1e-9: continue
            n /= np.linalg.norm(n)
            for i in range(1, len(Q) - 1):
                a, b, c = Q[0], Q[i], Q[i + 1]; A = 0.5 * np.linalg.norm(np.cross(b - a, c - a)); k = max(1, int(A / dichte ** 2))
                u = rng.random((k, 2)); f = u.sum(1) > 1; u[f] = 1 - u[f]
                pts.append(a + u[:, :1] * (b - a) + u[:, 1:] * (c - a)); nrm.append(np.repeat(n[None], k, 0)); kl.append(np.full(k, 0 if t == "WallSurface" else 1))
    T, N, K = np.vstack(pts), np.vstack(nrm), np.concatenate(kl)
    ek, nk = int(c0[0] // 1000), int(c0[1] // 1000)
    f = glob.glob(f"/media/oem/scan/rc-park_daten/_geo/**/dgm1_32_{ek}_{nk}_1_bw_*.xyz", recursive=True)
    if f:
        g = np.loadtxt(f[0]); L = lok(g); L = L[(np.abs(L[:, 0]) < radius) & (np.abs(L[:, 1]) < radius)]
        T = np.vstack([T, L]); N = np.vstack([N, np.repeat([[0, 0, 1.0]], len(L), 0)]); K = np.r_[K, np.full(len(L), 2)]
    return T, N, K


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("seite"); ap.add_argument("--n", type=int, default=60000)
    ap.add_argument("--reg", type=float, default=0.3, help="Zug von A zur Aehnlichkeit (0 = freie Affinitaet)"); ap.add_argument("--radius", type=float, default=50.0)
    ap.add_argument("--dicht", help="npy (Standard sfm/dicht_<seite>_modell.npy)"); ap.add_argument("--modell", choices=("aehnlich_z", "affin"), default="aehnlich_z"); a = ap.parse_args()
    obj = json.load(open(a.objekt)); od = os.path.dirname(os.path.abspath(a.objekt)); obj = __import__('objekt_rahmen').ergaenzen(obj, od); s = a.seite
    src = a.dicht or os.path.join(od, "sfm", f"dicht_{s}_modell.npy"); P = np.load(src).astype(float)
    rng = np.random.default_rng(0); X = P[rng.choice(len(P), min(a.n, len(P)), replace=False)]
    T, N, K = ziel(obj, a.radius); baum = cKDTree(T)
    print(f"Wolke {len(P)} Punkte ({len(X)} fuer den Fit), Ziel {len(T)} Flaechenpunkte (Wand {np.sum(K == 0)}, Dach {np.sum(K == 1)}, Boden {np.sum(K == 2)})")
    from scipy.spatial.transform import Rotation as Rot
    # Modell (Standard 'aehnlich_z', 8 Parameter): X' = s * R(Y * (1, 1, kz)) + t - Aehnlichkeit + Hoehenstreckung um z=0 (einseitige Wolken sind vor allem
    # in der Hoehe gestaucht/gedehnt); 'affin' (12) ist frei und gleitet entlang einer Fassadenlinie weg (Kaufhaus: Singulaerwerte 2,2/0,3).
    def matrix(p):
        if a.modell == "affin": return p[:9].reshape(3, 3)
        return np.exp(p[3]) * Rot.from_rotvec(p[:3]).as_matrix() @ np.diag([1, 1, np.exp(p[4])])
    def abbild(p, Y): return Y @ matrix(p).T + p[-3:]
    def bericht(p, Y, tag):
        M = abbild(p, Y); d, j = baum.query(M); r = np.einsum("ij,ij->i", M - T[j], N[j]); out = {}
        for k, nm in enumerate(("wand", "dach", "boden")):
            m = (K[j] == k) & (d < 1.5); out[nm] = dict(n=int(m.sum()), median_abs=float(np.median(np.abs(r[m]))) if m.any() else None)
        print(f"  {tag}: " + "  ".join(f"{k} n={v['n']} |r| {v['median_abs']:.2f} m" if v['median_abs'] is not None else f"{k} -" for k, v in out.items())); return out
    p = np.r_[np.eye(3).ravel(), np.zeros(3)] if a.modell == "affin" else np.zeros(8); vor = bericht(p, X, "vorher")
    for sw in (3.0, 2.0, 1.2, 0.8):
        for _ in range(3):
            M = abbild(p, X); d, j = baum.query(M, distance_upper_bound=sw)
            ok = np.isfinite(d); Xo, jj = X[ok], j[ok]; kk = K[jj]
            w = np.zeros(len(jj))
            for k in range(3):
                m = kk == k
                if m.any(): w[m] = 1.0 / np.sqrt(m.sum())                                          # Klassen gleich gewichtet (sonst entscheidet allein die Fassade)
            w *= np.sqrt(len(jj) / 3)
            def r(q):
                A = matrix(q); rr = np.einsum("ij,ij->i", Xo @ A.T + q[-3:] - T[jj], N[jj]) * w
                if a.modell != "affin": return rr
                S = np.linalg.svd(A, compute_uv=False); return np.r_[rr, a.reg * np.sqrt(len(jj)) * (S - S.mean())]   # Regularisierung: Singulaerwerte gleich = Aehnlichkeit
            p = least_squares(r, p, loss="huber", f_scale=sw / 3, max_nfev=100).x
    nach = bericht(p, X, "nachher")
    A = matrix(p); U, S, Vt = np.linalg.svd(A)
    print(f"A Singulaerwerte {S.round(3).tolist()} (1 = keine Dehnung), det {np.linalg.det(A):.3f}, b {p[-3:].round(2).tolist()} m" + ("" if a.modell == "affin" else f"; Massstab {np.exp(p[3]):.3f}, Hoehenstreckung kz {np.exp(p[4]):.3f}, Drehung {np.degrees(np.linalg.norm(p[:3])):.2f} Grad"))
    Pe = abbild(p, P); np.save(os.path.join(od, "sfm", f"dicht_{s}_entzerrt.npy"), Pe.astype(np.float32))
    os.makedirs(os.path.join(od, "audit"), exist_ok=True)
    json.dump(dict(werkzeug="wolke_entzerren_lod2.py", quelle=os.path.basename(src), modell=a.modell, A=A.tolist(), b=p[-3:].tolist(), singulaerwerte=S.tolist(), reg=a.reg, **({} if a.modell == "affin" else dict(massstab=float(np.exp(p[3])), kz=float(np.exp(p[4])))), residuen_vorher=vor, residuen_nachher=nach,
                   hinweis="Form-Wolke fuer Sichtvergleich/Hybrid/Proportionen - KEIN Mass (Ziel ist LoD2 selbst)"), open(os.path.join(od, "audit", f"wolke_entzerren_{s}.json"), "w"), indent=1)
    print(f"geschrieben: sfm/dicht_{s}_entzerrt.npy, audit/wolke_entzerren_{s}.json")


if __name__ == "__main__":
    main()
