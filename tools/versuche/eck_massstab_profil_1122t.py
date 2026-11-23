"""Massstabsprofil der Kopplung Eck -> Teil entlang der Hauptachse (Kopie, CPU)."""
import sys, numpy as np, pycolmap
sys.path.insert(0, "/home/oem/git/rc-park/.claude/worktrees/agent-a38678dacd05d031c/tools")
import seiten_eck_koppeln as EK
from sim3_robust import umeyama, anwenden, matrix
A = "/media/oem/rcdaten/tmp/bruecke_sued_agent"
rE = pycolmap.Reconstruction(A + "/eck/sparse/1")
ausdE = EK.ausdehnung([p.xyz for p in rE.points3D.values()])
R = {0: pycolmap.Reconstruction(A + "/teil0"), 1: pycolmap.Reconstruction(A + "/teil1")}
for t in (0, 1):
    X, Y, ns, td = EK.punkte(rE, R[t], mit_tiefe=True)
    at = EK.ausdehnung([p.xyz for p in R[t].points3D.values()])
    M, pr, ok, g = EK.kopplung_pruefen(X, Y, ausdE, at, tiefe=td)
    print("Teil", t, pr, g)
    s1 = np.cbrt(np.linalg.det(M[:3, :3])); r = np.linalg.norm(anwenden(M, X) - Y, axis=1) / (s1 * td); inl = np.flatnonzero(r <= EK.SCHWELLE_REL)
    Q = X[inl]; _, _, Vt = np.linalg.svd(Q - Q.mean(0), full_matrices=False); u = (Q - Q.mean(0)) @ Vt[0]
    print("  Achse-Laenge (Eck-Einheiten) 5-95%:", np.round(np.percentile(u, [5, 95]), 3), "ausdE", round(ausdE, 3), "Tiefe-Median", round(float(np.median(td)), 3))
    qs = np.percentile(u, np.linspace(0, 100, 6))
    for k in range(5):
        w = inl[(u >= qs[k]) & (u <= qs[k + 1])]
        s, _, _ = umeyama(X[w], Y[w]); print(f"  Quintil {k}: n={len(w)} u={np.median(u[(u>=qs[k])&(u<=qs[k+1])]):.3f} s={s:.4f} tiefe={np.median(td[w]):.2f}")
    # Bootstrap der Haelften
    rng = np.random.default_rng(0); hs = []
    for b in range(50):
        bb = rng.choice(len(inl), len(inl)); ii = inl[bb]; uu = u[bb]
        h = [umeyama(X[ii[m]], Y[ii[m]])[0] for m in (uu < np.median(uu), uu >= np.median(uu))]; hs.append(abs(h[0] - h[1]) / np.mean(h))
    print("  Bootstrap Haelften", round(np.mean(hs), 4), "+-", round(np.std(hs), 4))
    # Haelften entlang der zweiten/dritten Achse
    for ax in (1, 2):
        v = (Q - Q.mean(0)) @ Vt[ax]; h = [umeyama(X[inl[m]], Y[inl[m]])[0] for m in (v < np.median(v), v >= np.median(v))]
        print(f"  Haelften Achse {ax}:", round(abs(h[0]-h[1])/np.mean(h), 4))
    # Bilder je Haelfte
    print("  gemeinsame Bilder", len(ns))
