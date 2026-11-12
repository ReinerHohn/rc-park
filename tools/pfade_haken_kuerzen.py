#!/usr/bin/env python3
"""pfade_haken_kuerzen.py - Haken/U-Schlaufen an Pfadenden von Rippenpfaden abschneiden (Skelett-Artefakte an Kreuzungen/Fuessen).
Aufruf: pfade_haken_kuerzen.py OBJ.json --pfad bauteile/10/unterbau/rippen_pfade [--grad 60] [--min_punkte 8] [--schreiben]
Regel: Richtung des Pfades = Mittel der mittleren 50 % der Segmente; vom Ende (und Anfang) werden Punkte entfernt, solange das Segment mehr als --grad von dieser Richtung abweicht (Knick). Pfad bleibt >= --min_punkte; danach neu auf 24 Punkte abgetastet."""
import sys, json, numpy as np
a = sys.argv[1:]
if len(a) < 3: sys.exit(__doc__)
opt = lambda n, d: a[a.index(n) + 1] if n in a else d
obj = json.load(open(a[0])); r = obj
for k in opt("--pfad", "").split("/"): r = r[int(k)] if isinstance(r, list) else r[k]
grad, mp = float(opt("--grad", 60)), int(opt("--min_punkte", 8))
def rs(A, k=24):
    s = np.r_[0, np.cumsum(np.linalg.norm(np.diff(A, axis=0), axis=1))]; t = np.linspace(0, s[-1], k); return np.c_[[np.interp(t, s, A[:, i]) for i in range(3)]].T
for i, e in enumerate(r.get("pfade_ohne_spiegel", [])):
    A = np.array(e["pfad"] if isinstance(e, dict) else e, float); n0 = len(A); S = np.diff(A, axis=0); L = np.linalg.norm(S, axis=1, keepdims=True); S = S / (L + 1e-9)
    mid = S[len(S) // 4:len(S) - len(S) // 4].mean(0); mid /= np.linalg.norm(mid) + 1e-9; cs = lambda s_: float(np.degrees(np.arccos(np.clip(s_ @ mid, -1, 1))))
    lo, hi = 0, len(A) - 1
    while hi - lo > mp and cs(S[hi - 1]) > grad: hi -= 1
    while hi - lo > mp and cs(S[lo]) > grad: lo += 1
    if lo or hi < len(A) - 1:
        B = rs(A[lo:hi + 1]); print(f"Pfad {i}: {n0} -> {hi - lo + 1} Punkte (Anfang -{lo}, Ende -{len(A) - 1 - hi}), Laenge {np.linalg.norm(np.diff(A, axis=0), axis=1).sum():.2f} -> {np.linalg.norm(np.diff(B, axis=0), axis=1).sum():.2f} m")
        q = [[round(float(v), 3) for v in p] for p in B]
        if isinstance(e, dict): e["pfad"] = q
        else: r["pfade_ohne_spiegel"][i] = q
if "--schreiben" in a: json.dump(obj, open(a[0], "w"), indent=1, ensure_ascii=False); print("geschrieben")
