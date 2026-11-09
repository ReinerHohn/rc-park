"""Median-Fusion der Kantenquellen je Wolkenpunkt (KEIN Mittelwert): Anteil_i = kan_i / vis; fusioniert = Median ueber die Quellen (bei 3 Quellen: mindestens 2 muessen
den Punkt klar stuetzen, eine Einzelquelle mit Rauschen kann ihn nicht hochziehen). Ausgabe im Format von kanten_3d_vote (P, vis, kan) -> direkt fuer kanten_segmente/kanten_schleife.
Aufruf: python -I tools/kanten_fusion.py QUELLEN.npz OUT.npz [--ohne sam]"""
import sys, numpy as np
z = np.load(sys.argv[1]); P = z["P"]; vis = z["vis"]; kan = z["kan"].astype(np.float32); nam = [str(x) for x in z["quellen"]]; use = [i for i, n in enumerate(nam) if not ("--ohne" in sys.argv and n == sys.argv[sys.argv.index("--ohne") + 1])]
r = kan[use] / np.maximum(vis, 1)[None]
TOP = float(sys.argv[sys.argv.index("--top") + 1]) if "--top" in sys.argv else 0.04
if "--rang" in sys.argv:                      # Rang-Median: je Quelle die besten TOP-Anteile (unter Punkten mit >=8 Sichten) = 1, sonst 0; Mehrheit der Quellen entscheidet (Median der Binaerentscheidungen)
    ok = vis >= 8; B = np.zeros_like(r)
    for k in range(len(use)): t = np.quantile(r[k][ok], 1 - TOP); B[k] = (r[k] >= t) & ok; print(nam[use[k]], "Schwelle %.2f -> %d Punkte" % (t, int(B[k].sum())))
    r = B
med = np.median(r, axis=0); print("Quellen:", [nam[i] for i in use])
for thr in (0.5, 0.7, 0.9): print("Median>=%.1f (>=8 Sichten): %d" % (thr, int(((vis >= 8) & (med >= thr)).sum())), "  je Quelle:", [int(((vis >= 8) & (r[k] >= thr)).sum()) for k in range(len(use))])
np.savez_compressed(sys.argv[2], P=P, vis=vis, kan=np.round(med * vis).astype(np.int16))
