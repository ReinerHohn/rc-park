"""Streuerfilter fuers Drahtgitter: kurze (<lmin) Segmente ohne Nachbar-Endpunkt im Abstand r, und schwach gestuetzte (score<smin) Segmente ueber zmin fallen raus.
Aufruf: gitter_streuer.py IN.json OUT.json [--zmin 13] [--lmin 0.6] [--r 0.25] [--smin 0.6]"""
import sys, json, numpy as np
a = sys.argv; g = lambda k, d: float(a[a.index(k) + 1]) if k in a else d
zmin, lmin, r, smin = g("--zmin", 13), g("--lmin", 0.6), g("--r", 0.25), g("--smin", 0.6)
S = json.load(open(a[1])); seg = S["segmente"]
A = np.array([[*s[0], *s[1]] for s in seg]); L = np.linalg.norm(A[:, 3:] - A[:, :3], axis=1)
E = np.vstack([A[:, :3], A[:, 3:]]); idx = np.r_[np.arange(len(seg)), np.arange(len(seg))]
keep = []
for i, s in enumerate(seg):
    if max(A[i, 2], A[i, 5]) < zmin: keep.append(True); continue
    if s[3] < smin: keep.append(False); continue
    if L[i] < lmin:
        nb = 0
        for p in (A[i, :3], A[i, 3:]):
            d = np.linalg.norm(E - p, axis=1); nb += ((d < r) & (idx != i)).any()
        keep.append(nb >= 2)   # beide Enden angeschlossen
    else: keep.append(True)
S["segmente"] = [s for s, k in zip(seg, keep) if k]
print("vorher", len(seg), "nachher", len(S["segmente"]), "hoch", sum(1 for s in S["segmente"] if max(s[0][2], s[1][2]) >= zmin))
json.dump(S, open(a[2], "w"))
