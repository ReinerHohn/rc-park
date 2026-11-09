"""Buendel zusammenfassen + Streuer entfernen. Aufruf: python -I tools/kanten_buendel.py SEG_IN.json KANTEN.npz OUT.json [--wink 4] [--dist 0.06] [--rand 1.0]
Fast parallele, dicht liegende, sich ueberlappende Segmente (gleiche Kante mehrfach geschaetzt) -> eine Gerade (Laengen-gewichtete Achse, Vereinigung der Ausdehnung).
Streuer: Segmente ausserhalb der Box der Wolken-Kantenpunkte (+rand m) entfallen (Box aus Daten, keine Handwerte)."""
import sys, json, numpy as np
def opt(n, d): return float(sys.argv[sys.argv.index(n) + 1]) if n in sys.argv else d
WINK = np.cos(np.radians(opt("--wink", 4))); DIST = opt("--dist", 0.06); RAND = opt("--rand", 1.0)
d = json.load(open(sys.argv[1])); S = d["segmente"] if isinstance(d, dict) else d
P = np.load(sys.argv[2])["P"]; lo = np.percentile(P, 0.5, 0) - RAND; hi = np.percentile(P, 99.5, 0) + RAND
A = np.array([s[0] for s in S], float); B = np.array([s[1] for s in S], float); q = np.array([s[2] for s in S]); sc = np.array([s[3] for s in S], float)
M = (A + B) / 2; ok = ((M >= lo) & (M <= hi)).all(1); print("Streuer entfernt:", int((~ok).sum()), "Box", lo.round(1), hi.round(1))
A, B, q, sc = A[ok], B[ok], q[ok], sc[ok]; n = len(A); L = np.linalg.norm(B - A, axis=1); U = (B - A) / np.maximum(L, 1e-9)[:, None]
par = list(range(n))
def find(i):
    while par[i] != i: par[i] = par[par[i]]; i = par[i]
    return i
def lot(p, a, u): v = p - a; return np.linalg.norm(v - (v @ u) * u)
for i in np.argsort(-L):
    for j in range(i + 1, n):
        if abs(U[i] @ U[j]) < WINK: continue
        if max(lot(A[j], A[i], U[i]), lot(B[j], A[i], U[i]), lot(A[i], A[j], U[j]), lot(B[i], A[j], U[j])) > DIST: continue
        ti = np.sort([(A[j] - A[i]) @ U[i], (B[j] - A[i]) @ U[i]])
        if min(ti[1], L[i]) - max(ti[0], 0) < 0.0: continue
        par[find(j)] = find(i)
G = {}
for i in range(n): G.setdefault(find(i), []).append(i)
out = []
for g in G.values():
    w = L[g]; u0 = U[g[0]]; Ug = np.array([U[k] * np.sign(U[k] @ u0) for k in g]); u = (Ug * w[:, None]).sum(0); u /= np.linalg.norm(u)
    c = (((A[g] + B[g]) / 2) * w[:, None]).sum(0) / w.sum(); t = np.concatenate([(A[g] - c) @ u, (B[g] - c) @ u])
    out.append([list(map(float, c + t.min() * u)), list(map(float, c + t.max() * u)), int(q[g[0]]), float(sc[g].max()), len(g)])
print("Segmente", len(S), "->", len(out), "Laenge %.0f -> %.0f m" % (L.sum(), sum(np.linalg.norm(np.array(o[1]) - np.array(o[0])) for o in out)))
json.dump({"segmente": out}, open(sys.argv[3], "w"))
