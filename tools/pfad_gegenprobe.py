#!/usr/bin/env python3
"""pfad_gegenprobe.py - JEDEN 3D-Pfad (Rippe, Leiste ...) gegen unabhaengige Fotos pruefen: Pfadpunkte in die Kameras projizieren, Anteil auf stabilen Kanten (Stabilitaetskarte, 3 px Toleranz) = Treffer.
Aufruf: pfad_gegenprobe.py OBJ.json --pfad "bauteile/10/unterbau/rippen_pfade" --achse_n nx ny --fotos ip_IMG_6173.jpg,ip_IMG_6177.jpg,... [--kam KAM.json] [--ketten KETTEN.json (xyz-Pfade statt Objekt)] [--tol 3] [--min 0.55]
Ausgabe: je Pfad Trefferanteil je Foto, Mittel, Urteil (gut >= --min). Schwarz-Weiss-Pruefung Zweitfoto (Nutzer 12.11.: 'Bilder aus verschiedenen Winkeln uebereinanderlegen'); die Fotos duerfen NICHT die sein, aus denen der Pfad gemessen wurde."""
import sys, json, numpy as np, cv2
a = sys.argv[1:]
opt = lambda n, d: a[a.index(n) + 1] if n in a else d
D = "/media/oem/scan/rc-park_daten/kaufhaus_alle"; KAM = json.load(open(opt("--kam", D + "/sfm/kam_lot2.json"))); fotos = opt("--fotos", "ip_IMG_6173.jpg,ip_IMG_6177.jpg,ip_IMG_6250.jpg").split(","); tol = int(opt("--tol", 3)); mn = float(opt("--min", 0.55))
n = np.array([float(v) for v in a[a.index("--achse_n") + 1:a.index("--achse_n") + 3]]) if "--achse_n" in a else np.array([0.3338, 0.9426]); n /= np.linalg.norm(n); u = np.array([n[1], -n[0]])
xyz = lambda A: np.c_[np.outer(A[:, 0], u) + np.outer(A[:, 1], n), A[:, 2]]
def proj(c, P):
    R = np.array(c["Rn"]); q = P @ R.T + np.array(c["tn"]); x = q[:, 0] / q[:, 2]; y = q[:, 1] / q[:, 2]; s = 1 + c["params"][3] * (x * x + y * y); return np.c_[c["f"] * x * s + c["cx"], c["f"] * y * s + c["cy"]], q[:, 2]
paths = []
if "--ketten" in a: paths = [(f"K{i}", np.array(f["pfad_xyz"])) for i, f in enumerate(json.load(open(opt("--ketten", "")))) if f["laenge_m"] >= 0.5]
else:
    obj = json.load(open(a[0])); r = obj
    for k in opt("--pfad", "").split("/"): r = r[int(k)] if isinstance(r, list) else r[k]
    su = r.get("spiegel_u", 0)
    for i, q in enumerate(r.get("pfade", [])):
        A = np.array(q["pfad"] if isinstance(q, dict) else q); paths.append((f"P{i}", xyz(A)))
        if not (isinstance(q, dict) and q.get("spiegeln") is False): B = A.copy(); B[:, 0] = 2 * su - B[:, 0]; paths.append((f"P{i}m", xyz(B)))
    for i, q in enumerate(r.get("pfade_ohne_spiegel", [])): paths.append((f"S{i}", xyz(np.array(q["pfad"] if isinstance(q, dict) else q))))
maps = {}
for f in fotos:
    sm = cv2.imread(f"{D}/stabil/{f[:-4]}.png", 0); m = cv2.dilate((sm >= 255 * 0.4).astype(np.uint8), np.ones((2 * tol + 1, 2 * tol + 1), np.uint8)); maps[f] = (m, sm.shape[1] / KAM[f]["W"])
res = []
for nm, P in paths:
    P = np.array([P[0] + (P[-1] - P[0]) * t for t in []]) if False else P
    L = np.linalg.norm(np.diff(P, axis=0), axis=1); s = np.r_[0, np.cumsum(L)]; T = np.linspace(0, s[-1], 60); Q = np.c_[[np.interp(T, s, P[:, i]) for i in range(3)]].T; tr = []
    for f in fotos:
        p, z = proj(KAM[f], Q); m, sc = maps[f]; p = (p * sc).astype(int); ok = (z > 0.5) & (p[:, 0] >= 0) & (p[:, 0] < m.shape[1]) & (p[:, 1] >= 0) & (p[:, 1] < m.shape[0])
        tr.append(float(m[p[ok, 1], p[ok, 0]].mean()) if ok.sum() >= 20 else np.nan)
    mt = float(np.nanmean(tr)) if not np.all(np.isnan(tr)) else np.nan; res.append((nm, tr, mt))
    print(f"{nm:5s} L={s[-1]:.2f} m  " + "  ".join(f"{t:.2f}" for t in tr) + f"  Mittel {mt:.2f}  " + ("GUT" if mt >= mn else "SCHLECHT"))
