"""Pfeiler/Saeulen als Formfamilie (senkrechter Zylinder) aus der dichten Wolke - Kanten runder Pfeiler sind Silhouetten und wandern mit dem Blick,
der Tiefen-Sweep verwirft sie zu Recht; die Wolke hat die Pfeiler aber. Ablauf: (1) xy-Dichte im Schafthoehenband, kompakte Blobs (keine Waende: Laenge/Breite < 3),
(2) je Blob GPU-RANSAC-Kreis (3 Punkte -> Kreis, Inlier |r-R| < tol), (3) Hoehe aus belegten Scheiben, (4) Gleichheitsregel (Nutzer 9.11.): gemeinsamer Radius =
Median aller Pfeiler, Abweichung je Pfeiler im Bericht, (5) Ausgabe: n Mantellinien + Fuss-/Kopfring als Segmente quelle 7.
Aufruf: saeulen_fit.py WOLKE.npz|npy SEG_IN.json OUT.json [--zmin 3.0 --zmax 7.5] [--zelle 0.1] [--mind 40] [--rmin 0.2 --rmax 1.2] [--tol 0.04] [--n 8] [--gleich 1]
Keine Objektkonstanten; Hoehenband und Radien sind Parameter."""
import sys, json, numpy as np, torch
a = sys.argv; g = lambda k, d, t=float: t(a[a.index(k) + 1]) if k in a else d
ZMIN, ZMAX, ZELLE, MIND, RMIN, RMAX, TOL, N, GLEICH = g("--zmin", 3.0), g("--zmax", 7.5), g("--zelle", 0.1), g("--mind", 40, int), g("--rmin", 0.2), g("--rmax", 1.2), g("--tol", 0.04), g("--n", 8, int), g("--gleich", 1, int)
dev = "cuda"; W = np.load(a[1]); W = W["P"] if hasattr(W, "files") else W; W = W[:, :3].astype(np.float32); S0 = json.load(open(a[2]))
B = W[(W[:, 2] >= ZMIN) & (W[:, 2] < ZMAX)]
x0, y0 = B[:, 0].min(), B[:, 1].min(); ix = ((B[:, 0] - x0) / ZELLE).astype(int); iy = ((B[:, 1] - y0) / ZELLE).astype(int)
H = np.zeros((ix.max() + 1, iy.max() + 1), np.int32); np.add.at(H, (ix, iy), 1)
import cv2
mask = (H >= MIND).astype(np.uint8); nlab, lab, stats, cent = cv2.connectedComponentsWithStats(mask, 8)
kand = []
for i in range(1, nlab):
    w, h = stats[i, 3] * ZELLE, stats[i, 2] * ZELLE                                              # stats: (Spalte=iy, Zeile=ix) -> x-Ausdehnung = Zeilenzahl
    if max(w, h) > 3.0 or min(w, h) < 0.3 or max(w, h) / max(min(w, h), 1e-6) > 3: continue          # Waende/Linien raus, zu kleine raus
    kand.append((cent[i][1] * ZELLE + x0, cent[i][0] * ZELLE + y0, w, h))                        # cent = (Spalte, Zeile) = (iy, ix)
print("Blobs im Band %.1f-%.1f m: %d, Pfeiler-Kandidaten %d" % (ZMIN, ZMAX, nlab - 1, len(kand)), flush=True)
def kreis_ransac(Q, it=3000):
    """Q [M,2] GPU. 3 zufaellige Punkte -> Kreis (Umkreis); bester nach Inlierzahl."""
    M = len(Q); idx = torch.randint(0, M, (it, 3), device=dev); p = Q[idx]                       # [it,3,2]
    ax, ay = p[:, 0, 0], p[:, 0, 1]; bx, by = p[:, 1, 0], p[:, 1, 1]; cx, cy = p[:, 2, 0], p[:, 2, 1]
    d = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by)); ok = d.abs() > 1e-6
    ux = ((ax ** 2 + ay ** 2) * (by - cy) + (bx ** 2 + by ** 2) * (cy - ay) + (cx ** 2 + cy ** 2) * (ay - by)) / torch.where(ok, d, torch.ones_like(d))
    uy = ((ax ** 2 + ay ** 2) * (cx - bx) + (bx ** 2 + by ** 2) * (ax - cx) + (cx ** 2 + cy ** 2) * (bx - ax)) / torch.where(ok, d, torch.ones_like(d))
    R = torch.sqrt((ax - ux) ** 2 + (ay - uy) ** 2); gut = ok & (R > RMIN) & (R < RMAX)
    if not gut.any(): return None
    ux, uy, R = ux[gut], uy[gut], R[gut]; best = (-1, None)
    for c0 in range(0, len(ux), 256):
        sl = slice(c0, c0 + 256); r = torch.sqrt((Q[None, :, 0] - ux[sl, None]) ** 2 + (Q[None, :, 1] - uy[sl, None]) ** 2); inl = ((r - R[sl, None]).abs() < TOL).sum(1)
        v, i = inl.max(0)
        if int(v) > best[0]: best = (int(v), (float(ux[sl][i]), float(uy[sl][i]), float(R[sl][i])))
    return best
Wt = torch.tensor(W, device=dev); saeulen = []
for (cx, cy, w, h) in kand:
    m = ((Wt[:, 0] - cx).abs() < max(w, h) / 2 + 0.3) & ((Wt[:, 1] - cy).abs() < max(w, h) / 2 + 0.3) & (Wt[:, 2] >= ZMIN) & (Wt[:, 2] < ZMAX); Q = Wt[m]
    if len(Q) < 200: print("  Kandidat %.1f/%.1f: nur %d Punkte" % (cx, cy, len(Q))); continue
    res = kreis_ransac(Q[:, :2])
    if res is None: print("  Kandidat %.1f/%.1f: kein Kreis im Radiusbereich" % (cx, cy)); continue
    n_in, (ux, uy, R) = res; anteil = n_in / len(Q)
    if anteil < 0.25: print("  Kandidat %.1f/%.1f: Kreisanteil %.2f zu klein (kein Zylinder)" % (cx, cy, anteil)); continue
    # Hoehe: alle Wolkenpunkte im Schlauch, belegte 20-cm-Scheiben (>= 15 Punkte) von unten/oben
    m2 = ((Wt[:, 0] - ux) ** 2 + (Wt[:, 1] - uy) ** 2).sqrt(); tube = ((m2 - R).abs() < TOL * 1.5) & (Wt[:, 2] > ZMIN - 2.5) & (Wt[:, 2] < ZMAX + 3)
    zz = Wt[tube, 2]; hist = torch.histc(zz, bins=int((ZMAX + 3 - (ZMIN - 2.5)) / 0.2), min=ZMIN - 2.5, max=ZMAX + 3); belegt = torch.where(hist >= 15)[0]
    if len(belegt) < 3: continue
    zf = float(ZMIN - 2.5 + belegt[0] * 0.2); zk = float(ZMIN - 2.5 + (belegt[-1] + 1) * 0.2)
    saeulen.append(dict(cx=ux, cy=uy, R=R, z_fuss=zf, z_kopf=zk, inlier=n_in, punkte=int(len(Q)), anteil=round(anteil, 3)))
    print("  Pfeiler Mitte %.2f %.2f  R %.3f  z %.2f-%.2f  Inlier %d/%d" % (ux, uy, R, zf, zk, n_in, len(Q)), flush=True)
saeulen = [s for s in saeulen if s["anteil"] >= 0.4 and s["inlier"] >= 300]                      # nur klare Zylinder (Kreisanteil >= 0,4)
if GLEICH and len(saeulen) >= 2:
    stark = [s for s in saeulen if s["anteil"] >= 0.6]; Rm = float(np.median([s["R"] for s in (stark or saeulen)]))
    print("Gleichheitsregel: gemeinsamer Radius %.3f m (aus %d klaren Pfeilern); Abweichungen:" % (Rm, len(stark)), [round(s["R"] - Rm, 3) for s in saeulen])
    for s in saeulen:
        s["R_einzeln"] = s["R"]
        if abs(s["R"] - Rm) <= 0.1: s["R"] = Rm                                                 # gleich -> gemeinsamer Radius; sonst eigener (anderer Pfeilertyp)
        else: s["abweichend"] = True
seg = []
for s in saeulen:
    ring = lambda z: [[s["cx"] + s["R"] * np.cos(2 * np.pi * j / N), s["cy"] + s["R"] * np.sin(2 * np.pi * j / N), z] for j in range(N)]
    rf, rk = ring(s["z_fuss"]), ring(s["z_kopf"])
    for j in range(N): seg += [[rf[j], rk[j], 7, 1.0], [rf[j], rf[(j + 1) % N], 7, 1.0], [rk[j], rk[(j + 1) % N], 7, 1.0]]
S0["segmente"] = S0["segmente"] + seg; S0["saeulen"] = saeulen; json.dump(S0, open(a[3], "w")); print("Pfeiler", len(saeulen), "Segmente neu", len(seg), "gesamt", len(S0["segmente"]))
