#!/usr/bin/env python3
"""helm_profil_wolke.py - Profil r(z) eines N-eckigen Helms/Turms (Apothem je Hoehe) aus der Fotowolke, mit Achslage und Flaechenphase (generisch, kein Objektname).

Gegenprobe zu Foto-Silhouetten (Regel 9d: Wolke = Lage + Gegenprobe, Form = Fotos). Eine Silhouettenbreite liegt zwischen Apothem und Eckradius und
kann bei auskragenden Punkten (Traufspitzen) um Tiefenversatz*tan(Blickhoehe) falsch in z sein (Lehre L31); der Flaechenmitten-Abstand aus der Wolke ist davon frei.
  helm_profil_wolke.py WOLKE.npy --achse X Y --normale NX NY --z0 13.0 --z1 19 [--dz 0.25] [--n 8] [--quer 0.5] [--rmax 2.6] [--out PROTOKOLL.json]
Ausgabe: (1) Phasenfit je Band (Achteck vs Kreis, Achsversatz, Apothem), (2) Mitten-Profil a(z) = Median des Abstands entlang +Normale fuer |quer| < --quer.
Nur die zur Strasse gewandte Haelfte hat Wolkenpunkte; Rueckseite bleibt ANNAHME (Spiegelung).
Rechnung: boolesche Fenster auf 1,8 Mio Punkten (< 1 s, keine Nachbarsuche) -> bewusst numpy, GPU brachte hier nichts."""
import sys, json, numpy as np
from scipy.optimize import least_squares
a = sys.argv
def opt(k, d=None, t=float): return t(a[a.index(k) + 1]) if k in a else d
if len(a) < 2 or a[1].startswith("-"): print(__doc__); sys.exit(1)
W = np.load(a[1])[:, :3]; c0 = np.array([float(x) for x in a[a.index("--achse") + 1:a.index("--achse") + 3]]); nn = np.array([float(x) for x in a[a.index("--normale") + 1:a.index("--normale") + 3]]); nn /= np.linalg.norm(nn)
uu = np.array([nn[1], -nn[0]]); z0, z1, dz = opt("--z0"), opt("--z1"), opt("--dz", 0.25); N = int(opt("--n", 8)); quer = opt("--quer", 0.5); rmax = opt("--rmax", 2.6); phi_n = np.arctan2(nn[1], nn[0]); w = np.pi / N
def f(p, P):
    cx, cy, A, ph = p; d = P - [cx, cy]; r = np.hypot(*d.T); phi = np.arctan2(d[:, 1], d[:, 0]) - phi_n - ph; q = ((phi + w) % (2 * w)) - w
    return r - A / np.cos(q)
phasen, mitte = [], []
for za in np.arange(z0, z1 - 1e-9, dz):
    s = (W[:, 2] >= za) & (W[:, 2] < za + dz); d = W[s, :2] - c0; ra = np.hypot(*d.T)
    m = (np.abs(d @ nn) < rmax) & (np.abs(d @ uu) < rmax) & ((d @ nn) > 0.3); P = W[s][m][:, :2]
    if (np.abs(d[m] @ uu) < quer).sum() < 30: continue
    mitte.append({"z": round(za + dz / 2, 3), "a_median": round(float(np.median((P - c0) @ nn)[()] if False else np.median(((P - c0) @ nn)[np.abs((P - c0) @ uu) < quer])), 3), "n": int((np.abs((P - c0) @ uu) < quer).sum())})
# Phasenfit in groben Baendern ueber der Traufzone (nur Punkte nahe der Huelle: r < 1,2 * Median-Apothem)
for zb in np.arange(max(z0, 15.0), z1 - 0.5, 0.8):
    s = (W[:, 2] >= zb) & (W[:, 2] < zb + 0.8); P = W[s][:, :2]; d = P - c0; ang = np.degrees(np.arctan2(d @ uu, d @ nn)); r = np.hypot(*d.T)
    am = np.median(((P - c0) @ nn)[(np.abs((P - c0) @ uu) < quer) & (r < rmax)]) if ((np.abs((P - c0) @ uu) < quer) & (r < rmax)).sum() > 30 else None
    if am is None: continue
    k = (np.abs(ang) < 95) & (r < 1.25 * am + 0.1) & (r > 0.6 * am); P = P[k]
    if len(P) < 200: continue
    best = None
    for ph in np.radians(np.arange(-w * 180 / np.pi, w * 180 / np.pi, 3.0)):
        rr = least_squares(f, [c0[0], c0[1], am, ph], args=(P,), loss="soft_l1", f_scale=0.05)
        if best is None or rr.cost < best.cost: best = rr
    cx, cy, A, ph = best.x; ph = (np.degrees(ph) + 180 / N) % (360 / N) - 180 / N
    rc = least_squares(lambda p: np.hypot(*(P - p[:2]).T) - p[2], [c0[0], c0[1], am], loss="soft_l1", f_scale=0.05)
    phasen.append({"z0": round(zb, 2), "z1": round(zb + 0.8, 2), "n": int(len(P)), "dx": round(float(cx - c0[0]), 3), "dy": round(float(cy - c0[1]), 3), "apothem": round(float(A), 3), "phase_grad": round(float(ph), 1), "kosten_n_eck": round(float(best.cost), 3), "kosten_kreis": round(float(rc.cost), 3)})
res = {"werkzeug": "tools/helm_profil_wolke.py", "wolke": a[1], "achse": c0.tolist(), "normale": nn.tolist(), "n_seiten": N, "quer": quer, "phasenfit": phasen, "mitten_profil": mitte,
       "hinweis": "Mitten-Profil = Abstand der Huelle entlang +Normale (Flaechenmitte), nicht Silhouette; Wolke dick ~0,05 m (Kachel/Rauschen)."}
for p in phasen: print("Phasenfit", p)
for m in mitte: print("a(z)", m)
if "--out" in a: json.dump(res, open(a[a.index("--out") + 1], "w"), indent=1, ensure_ascii=False); print("->", a[a.index("--out") + 1])
