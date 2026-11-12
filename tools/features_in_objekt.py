#!/usr/bin/env python3
"""features_in_objekt.py - Features aus kanten_features.py (Sweep-gestuetzt) als Pfade in ein Generator-Bauteil uebernehmen (allgemein, nicht rippenspezifisch).
Aufruf: features_in_objekt.py OBJ.json FEATURES.json --pfad "bauteile/10/unterbau/rippen_pfade" --achse_n nx ny --spiegel_u U [--min_belegt 0.5] [--min_m 0.45] [--min_abstand 0.12]
        [--u 13 18.5] [--z 5.8 8.6] [--normale u n z] [--min_laenge_verbinden 0.08] [--trocken]
Schritte: Filter (Belegung, Laenge, Lagefenster) -> Fragmente verbinden (Enden < 0,08 m, Richtung stetig) -> Duplikate gegen vorhandene Pfade (inkl. Spiegel) verwerfen -> als pfade_ohne_spiegel (dict pfad/normale/spiegeln) anhaengen.
Danach IMMER: tools/bauen_abnehmen.sh + Render neben Foto ansehen (12.11.: 16 unverbundene Fragmente brachten Stoerkloetze, keine sichtbare Verbesserung -> verworfen)."""
import sys, json, numpy as np
a = sys.argv[1:]
if len(a) < 4: sys.exit(__doc__)
opt = lambda n, d, k=1, t=float: [t(v) for v in a[a.index(n) + 1:a.index(n) + 1 + k]] if n in a else d
obj = json.load(open(a[0])); F = json.load(open(a[1])); pt = a[a.index("--pfad") + 1].split("/")
r = obj
for k in pt: r = r[int(k)] if isinstance(r, list) else r[k]
nx, ny = opt("--achse_n", [0.3338, 0.9426], 2); n = np.array([nx, ny]); n /= np.linalg.norm(n); u = np.array([n[1], -n[0]])
su = opt("--spiegel_u", [r.get("spiegel_u", 0)])[0]; mb, mm, md = opt("--min_belegt", [0.5])[0], opt("--min_m", [0.45])[0], opt("--min_abstand", [0.12])[0]
ur, zr = opt("--u", [-1e9, 1e9], 2), opt("--z", [-1e9, 1e9], 2); nm = opt("--normale", None, 3)
uvz = lambda Q: (lambda Q: np.c_[Q[:, :2] @ u, Q[:, :2] @ n, Q[:, 2]])(np.array(Q))
def rs(A, k=24):
    s = np.r_[0, np.cumsum(np.linalg.norm(np.diff(A, axis=0), axis=1))]; t = np.linspace(0, s[-1], k); return np.c_[[np.interp(t, s, A[:, i]) for i in range(3)]].T
vor = []
for q in r.get("pfade", []):
    A = np.array(q["pfad"] if isinstance(q, dict) else q); vor.append(A)
    if not (isinstance(q, dict) and q.get("spiegeln") is False): B = A.copy(); B[:, 0] = 2 * su - B[:, 0]; vor.append(B)
for q in r.get("pfade_ohne_spiegel", []): vor.append(np.array(q["pfad"] if isinstance(q, dict) else q))
nuvz = lambda v: [float(v[0] * u[0] + v[1] * u[1]), float(v[0] * n[0] + v[1] * n[1]), float(v[2])]       # Normale xyz -> (u,n,z)
C, NO = [], []
for f in F:
    if f.get("belegt") is None or f["belegt"] < mb: continue
    A = uvz(f["pfad_xyz"])
    if ur[0] < A[:, 0].min() and A[:, 0].max() < ur[1] and zr[0] < A[:, 2].min() and A[:, 2].max() < zr[1]: C.append(A); NO.append(nuvz(f["normale_xyz"]) if f.get("normale_xyz") else None)
LUE = opt("--luecke_m", [0.35])[0]; COS = opt("--cos", [0.8])[0]
def tang(A, ende, k=4): v = (A[-1] - A[-1 - k]) if ende else (A[0] - A[k]); return v / (np.linalg.norm(v) + 1e-9)
ver = True
while ver:                                              # Fragmente verbinden: Luecke <= --luecke_m, Richtung beider Enden zur Verbindung stetig (cos >= --cos), auch umgekehrte Fragmente
    ver = False
    for i in range(len(C)):
        for j in range(len(C)):
            if i == j: continue
            for A, B, fl in ((C[i], C[j], 0), (C[i], C[j][::-1], 1)):
                g = B[0] - A[-1]; gl = float(np.linalg.norm(g))
                if gl > LUE or len(A) < 5 or len(B) < 5: continue
                d = g / (gl + 1e-9) if gl > 0.02 else None
                if (d is None or (tang(A, True) @ d > COS and tang(B, False) @ d > COS)) and tang(A, True) @ (-tang(B, False)) > COS:
                    C[i] = np.vstack([A, B]); C.pop(j); NO.pop(j); ver = True; break
            if ver: break
        if ver: break
from scipy.interpolate import splprep, splev
def glatt(A):                                           # Spline durch die Punkte (Luecken ueberbrueckt), 24 Punkte
    try: tck, _ = splprep(A.T, s=len(A) * 0.0004 * 4); return np.array(splev(np.linspace(0, 1, 24), tck)).T
    except Exception: return rs(A)
C = [glatt(A) for A in C]
neu = []; nneu = []
for A, N_ in zip(C, NO):
    L = float(np.linalg.norm(np.diff(A, axis=0), axis=1).sum())
    if L < mm: continue
    dm = min(np.linalg.norm(rs(A) - rs(W), axis=1).mean() for V in vor + neu for W in (V, V[::-1]))
    if dm > md: neu.append(A); nneu.append(N_)
print(f"{len(C)} Kandidaten nach Filter/Verbinden, {len(neu)} neu (Duplikat-Abstand > {md} m)")
if "--trocken" in a: sys.exit()
r.setdefault("pfade_ohne_spiegel", [])
r["pfade_ohne_spiegel"] += [dict(pfad=np.round(A, 3).tolist(), **({"normale": nm} if nm else ({"normale": [round(v, 3) for v in N_]} if N_ else {})), spiegeln=False) for A, N_ in zip(neu, nneu)]
json.dump(obj, open(a[0], "w"), indent=1, ensure_ascii=False)
