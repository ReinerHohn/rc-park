#!/usr/bin/env python3
"""modell_lage_vergleich.py <modell_A> <modell_B> [--aus bericht.json] [--liste 10]

Zwei SfM-Modelle derselben Bilder gegeneinander: WO und BEI WELCHEN BILDERN weichen sie ab? (21.11.2026, Untersuchung "warum scheitert der globale Mapper", Nutzerauftrag.)
Gemeinsame Bilder -> robuste Aehnlichkeitsabbildung B -> A (Umeyama, 5 Runden mit den besten 60 %) -> je Bild:
  Lage-Abweichung in % der Szenengroesse (Szenengroesse = 5.-95.-Perzentil-Diagonale der Kamerastandorte in A), Drehungsabweichung in Grad, Brennweiten-Verhaeltnis B/A.
Ausgabe: Gesamt (Median, 90 %, Anteil > 2 %) und JE BILDQUELLE (Namensteil vor '__': eigene Fotos, Netz, Videoclip) - zeigt, ob wenige Quellen (freie Brennweite, Fernfotos)
die Abweichung tragen oder das ganze Modell verformt ist. rc 0 immer (Messwerkzeug).
"""
import sys, os, json, argparse, collections
import numpy as np


def umeyama(P, Q):
    mp, mq = P.mean(0), Q.mean(0); X, Y = P - mp, Q - mq; U, S, Vt = np.linalg.svd(Y.T @ X / len(P)); D = np.eye(3)
    if np.linalg.det(U) * np.linalg.det(Vt) < 0: D[2, 2] = -1
    R = U @ D @ Vt; s = np.trace(np.diag(S) @ D) / X.var(0).sum(); return s, R, mq - s * R @ mp


def lesen(p):
    import pycolmap
    r = pycolmap.Reconstruction(p); E = {}
    for im in r.images.values():
        w = im.cam_from_world() if callable(im.cam_from_world) else im.cam_from_world; R = w.rotation.matrix(); k = r.cameras[im.camera_id]
        E[os.path.basename(im.name)] = (-R.T @ w.translation, R, float(k.params[0]) / max(k.width, k.height))
    return E


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("a"); ap.add_argument("b"); ap.add_argument("--aus"); ap.add_argument("--liste", type=int, default=10); a = ap.parse_args()
    A, B = lesen(a.a), lesen(a.b); N = sorted(set(A) & set(B))
    if len(N) < 10: print(f"zu wenige gemeinsame Bilder ({len(N)})"); return 0
    PA = np.array([A[n][0] for n in N]); PB = np.array([B[n][0] for n in N]); ok = np.ones(len(N), bool)
    gr = float(np.linalg.norm(np.percentile(PA, 95, 0) - np.percentile(PA, 5, 0))) or 1.0; rng = np.random.default_rng(1); best = (-1, None)
    # RANSAC ueber Vierergruppen (Treffer = Lage <= 1 % der Szene), dann Ausgleich ueber die Treffer. Erste Fassung nahm "die besten 60 %": das waren die Videobilder auf EINER
    # Geraden (Kamerafahrt) -> Drehung um diese Gerade unbestimmt, scheinbare Abweichung aller uebrigen Bilder 12-14 % und Drehung 13 / 127 Grad fuer ALLE Bilder (Messfehler des Werkzeugs).
    for _ in range(600):
        i = rng.choice(len(N), 4, replace=False)
        try: s, R, t = umeyama(PB[i], PA[i])
        except Exception: continue
        if not np.isfinite(s) or s <= 0: continue
        d = np.linalg.norm((s * (R @ PB.T).T + t) - PA, axis=1); k = int((d <= 0.01 * gr).sum())
        if k > best[0]: best = (k, d <= 0.01 * gr)
    ok = best[1] if best[0] >= 4 else ok
    for _ in range(3):
        s, R, t = umeyama(PB[ok], PA[ok]); d = np.linalg.norm((s * (R @ PB.T).T + t) - PA, axis=1); ok2 = d <= 0.01 * gr
        if ok2.sum() >= 4: ok = ok2
    rel = d / gr * 100; print(f"Ausgleich ueber {int(ok.sum())} von {len(N)} Bildern (Lage <= 1 %)")
    rot = np.array([np.degrees(np.arccos(np.clip((np.trace(A[n][1] @ (B[n][1] @ R.T).T) - 1) / 2, -1, 1))) for n in N]); fv = np.array([B[n][2] / A[n][2] for n in N])
    q = lambda n: n.split("__vf_")[0] if "__vf_" in n else n.split("__")[0]; Q = collections.defaultdict(list)
    for i, n in enumerate(N): Q[q(n)].append(i)
    print(f"A {len(A)} Bilder, B {len(B)}, gemeinsam {len(N)}; Massstab B->A {s:.3f}")
    print(f"LAGE: Median {np.median(rel):.2f} % der Szene, 90 % unter {np.percentile(rel, 90):.2f} %, > 2 %: {int((rel > 2).sum())} Bilder ({(rel > 2).mean() * 100:.0f} %); DREHUNG Median {np.median(rot):.2f} Grad, > 2 Grad: {int((rot > 2).sum())}; BRENNWEITE |B/A-1| Median {np.median(np.abs(fv - 1)) * 100:.1f} %, > 5 %: {int((np.abs(fv - 1) > 0.05).sum())}")
    Z = []
    for k, I in sorted(Q.items(), key=lambda t: -len(t[1])):
        I = np.array(I); Z.append(dict(quelle=k, bilder=len(I), lage_median=round(float(np.median(rel[I])), 2), lage_ueber2=int((rel[I] > 2).sum()), dreh_median=round(float(np.median(rot[I])), 2), f_abw_median=round(float(np.median(np.abs(fv[I] - 1)) * 100), 1)))
    for z in Z[:a.liste]: print(f"  {z['quelle'][:28]:28s} {z['bilder']:4d} Bilder: Lage Median {z['lage_median']:6.2f} %, > 2 %: {z['lage_ueber2']:3d}, Drehung {z['dreh_median']:5.2f} Grad, Brennweite {z['f_abw_median']:5.1f} % anders")
    if a.aus: json.dump(dict(a=a.a, b=a.b, gemeinsam=len(N), lage_median=float(np.median(rel)), lage_p90=float(np.percentile(rel, 90)), ueber2=int((rel > 2).sum()), quellen=Z, bilder={n: [round(float(rel[i]), 2), round(float(rot[i]), 2), round(float(fv[i]), 3)] for i, n in enumerate(N)}), open(a.aus, "w"), indent=1)
    return 0


if __name__ == "__main__": sys.exit(main())
