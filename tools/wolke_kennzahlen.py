#!/usr/bin/env python3
"""wolke_kennzahlen.py - S10 Teil C: gleiche Kennzahlen fuer jede Wolkenvariante (fused.ply im metrischen Modellsystem, z oben).
Referenzebenen EINMAL aus der Referenzvariante (F0) per sequentiellem RANSAC (senkrechte Ebenen = Geraden im Grundriss), danach alle Varianten gegen DIESELBEN Ebenen und Zellen:
  rausch_p50/p90   : |Abstand| der Punkte im Band +-BAND um die Ebene (Wandpunkte), cm
  schale_10_90     : 10-90 %-Abfallbreite der Punktdichte quer zur Wand (Profil Abstand -0,5..0,5 m, geglaettet), cm  (= Kantenschaerfe der Wandschale)
  kante_oben       : Dichteabfall in der Wandebene quer zur Oberkante (Zellzeilen unter/ueber der Wandoberkante), 10-90 %-Hoehe, cm (echte 3D-Kante Wand/Dach)
  abdeckung        : Anteil belegter Zellen (ZELLE m) im Rechteck der Referenzwand (F0 belegt = 100 % nur dort, wo F0 belegt war ist nicht vorausgesetzt)
  vor_fassade      : Punkte 0,3..3 m VOR der Ebene (Kameraseite) innerhalb der Wandflaeche, Anteil an den Wandpunkten (%), und je m2
Keine Objektwerte: Ebenenzahl/Mindestgroesse relativ zur Wolke, Band/Zelle sind Parameter (Standard).
  /media/oem/scan/venv-seg/bin/python -I tools/wolke_kennzahlen.py --ref DIR_F0 --kameras kameras_unverzerrt.json --aus out.json VAR1_DIR VAR2_DIR ...   (je Ordner fused.ply)
"""
import os, sys, json, argparse
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
BAND, ZELLE, VORN = 0.15, 0.25, 3.0


def lesen(d):
    p = d if d.endswith(".ply") else os.path.join(d, "fused.ply")
    with open(p, "rb") as f:
        hd = []
        while True:
            l = f.readline().decode("ascii").strip(); hd.append(l)
            if l == "end_header": break
        n = int([h for h in hd if h.startswith("element vertex")][0].split()[-1]); props = [h.split()[1:] for h in hd if h.startswith("property")]
        dt = np.dtype([(q[1], {"float": "<f4", "uchar": "u1", "double": "<f8", "int": "<i4"}[q[0]]) for q in props]); a = np.frombuffer(f.read(n * dt.itemsize), dtype=dt)
    return np.c_[a["x"], a["y"], a["z"]].astype(np.float64), (np.c_[a["nx"], a["ny"], a["nz"]].astype(np.float64) if "nx" in a.dtype.names else None)


def ebenen_ransac(P, N, cam, n_max=6, zmin=1.0, schwelle=0.12, min_anteil=0.02, iters=600, seed=0, winkel=25.0, nz_max=0.3, min_flaeche=20.0):
    """Senkrechte Ebenen (Gerade im Grundriss x,y), sequentiell. Rueckgabe Liste dict(o,d,n,u,z): o Punkt, d Richtung, n Normale (zur Kameraseite)."""
    rng = np.random.default_rng(seed); ok = P[:, 2] > zmin
    if N is not None: ok &= np.abs(N[:, 2]) < nz_max                                   # nur Punkte mit waagerechter Normale (Wandpunkte), sonst fuellen Strassen/Daecher/Streuung die Ebene
    Q = P[ok]; NQ = None if N is None else N[ok, :2] / np.maximum(np.linalg.norm(N[ok, :2], axis=1, keepdims=True), 1e-9); rest = np.ones(len(Q), bool); out = []; mincnt = max(2000, int(min_anteil * len(P)))
    from scipy import ndimage
    for _ in range(n_max):
        idx = np.where(rest)[0]
        if len(idx) < mincnt: break
        sub = Q[rng.choice(idx, min(len(idx), 80000), replace=False), :2]; best = (0, None)
        for _ in range(iters):
            i, j = rng.choice(len(sub), 2, replace=False); d = sub[j] - sub[i]; L = np.hypot(*d)
            if L < 2.0: continue
            n = np.array([-d[1], d[0]]) / L; c = (np.abs((sub - sub[i]) @ n) < schwelle).sum()
            if c > best[0]: best = (c, (sub[i], n))
        o, n = best[1]; ang = (lambda nn: np.abs(NQ @ nn) > np.cos(np.radians(winkel))) if NQ is not None else (lambda nn: True)
        inl = rest & (np.abs((Q[:, :2] - o) @ n) < schwelle) & ang(n)
        if inl.sum() < mincnt: break
        X = Q[inl, :2]; m = X.mean(0); u_, s_, vt = np.linalg.svd(X - m, full_matrices=False); d = vt[0]; n = np.array([-d[1], d[0]])          # Verfeinerung
        inl = rest & (np.abs((Q[:, :2] - m) @ n) < schwelle) & ang(n); X = Q[inl]
        if n @ (cam[:2] - m) < 0: n = -n
        u = (X[:, :2] - m) @ d; zq = X[:, 2]; gz = 0.5; u0 = u.min(); z0 = zq.min(); gi = np.floor((u - u0) / gz).astype(int); gj = np.floor((zq - z0) / gz).astype(int)
        cnt = np.zeros((gi.max() + 1, gj.max() + 1)); np.add.at(cnt, (gi, gj), 1); lab, nl = ndimage.label(cnt >= 3)                          # Wandstueck = groesste zusammenhaengende belegte Flaeche
        if nl == 0: rest &= ~inl; continue
        gr = ndimage.sum(cnt, lab, range(1, nl + 1)); L = 1 + int(np.argmax(gr)); ii_, jj_ = np.where(lab == L); fl = (lab == L).sum() * gz * gz
        rest &= ~inl
        if fl < min_flaeche: continue
        ue = [u0 + ii_.min() * gz, u0 + (ii_.max() + 1) * gz]; ze = [z0 + jj_.min() * gz, z0 + (jj_.max() + 1) * gz]
        out.append(dict(o=m.tolist(), d=d.tolist(), n=n.tolist(), u=[float(x) for x in ue], z=[float(x) for x in ze], n_inlier=int(inl.sum()), flaeche_belegt_m2=round(float(fl), 1)))
    return out


def isoliert(P, k=8, faktor=3.0, gpu=True):
    """Isolierte Punkte: mittlerer kNN-Abstand > faktor * Median (Luftpunkte, unabhaengig von der Ebene). gpu=True: PyTorch3D knn_points (Beweis CPU==GPU: GPU_LUECKEN Stand der Umsetzung), gpu=False: alter cKDTree."""
    if gpu:
        try:
            import torch; sys.path.insert(0, "/media/oem/scan/p3d_site"); from pytorch3d.ops import knn_points
            Xg = torch.as_tensor(np.asarray(P - P.mean(0), np.float32), device="cuda")[None]; md = np.empty(len(P))
            for i in range(0, len(P), 500000):
                dd = knn_points(Xg[:, i:i + 500000], Xg, K=k + 1).dists[0, :, 1:].clamp_min(0).sqrt().double(); md[i:i + 500000] = dd.mean(1).cpu().numpy()
            return md > faktor * np.median(md)
        except Exception as e: print("isoliert: GPU nicht verfuegbar (%s) -> CPU" % e)
    from scipy.spatial import cKDTree
    d, _ = cKDTree(P).query(P, k=k + 1, workers=-1); md = d[:, 1:].mean(1); return md > faktor * np.median(md)


def _nachbarn_gpu(P, Q, radius, K=256):
    """Nachbarn im Radius per knn_points(K) + Radiusmaske: -> (Koordinaten (n,K,3) float64, Maske (n,K)) oder None, wenn irgendwo K voll (abgeschnitten -> CPU-Rueckfall)."""
    import torch; sys.path.insert(0, "/media/oem/scan/p3d_site"); from pytorch3d.ops import knn_points
    c0 = P.mean(0); Xg = torch.as_tensor(np.asarray(P - c0, np.float32), device="cuda")[None]; Qg = torch.as_tensor(np.asarray(Q - c0, np.float32), device="cuda")[None]
    r = knn_points(Qg, Xg, K=K); m = r.dists[0] <= radius ** 2
    if bool(m[:, -1].any()): return None
    return (P[r.idx[0].cpu().numpy()]), m.cpu().numpy()


def rauheit(P, idx, radius=0.30, n_max=8000, seed=0, gpu=True):
    """Lokale Rauheit: sqrt(kleinster Eigenwert) der Nachbarschaft (Radius m) um Wandpunkte = Rauschen ohne Annahme einer GLOBALEN Ebene. Rueckgabe (p50, p90) cm.
    gpu=True: Nachbarsuche per knn_points (K=256 + Radiusmaske; wird irgendwo K voll -> CPU-Rueckfall, Originalverhalten), Eigenwerte weiter numpy float64."""
    rng = np.random.default_rng(seed); sel = idx if len(idx) <= n_max else rng.choice(idx, n_max, replace=False); sg = []
    g = None
    if gpu:
        try: g = _nachbarn_gpu(P, P[sel], radius)
        except Exception as e: print("rauheit: GPU nicht verfuegbar (%s) -> CPU" % e)
    if g is not None:
        Nb, M = g
        for l, m in zip(Nb, M):
            if m.sum() < 12: continue
            Y = l[m]; X = Y - Y.mean(0); sg.append(np.sqrt(max(np.linalg.eigvalsh(X.T @ X / len(Y))[0], 0)))
    else:
        from scipy.spatial import cKDTree
        if not hasattr(rauheit, "_c") or rauheit._c[0] is not P: rauheit._c = (P, cKDTree(P))
        tr = rauheit._c[1]; nb = tr.query_ball_point(P[sel], radius, workers=-1)
        for i, l in zip(sel, nb):
            if len(l) < 12: continue
            X = P[l] - P[l].mean(0); sg.append(np.sqrt(max(np.linalg.eigvalsh(X.T @ X / len(l))[0], 0)))
    if not sg: return None, None
    return round(float(np.percentile(sg, 50)) * 100, 2), round(float(np.percentile(sg, 90)) * 100, 2)


def kennzahlen(P, E, band=BAND, zelle=ZELLE, N=None, winkel=25.0, iso=None):
    res = []
    for e in E:
        o = np.array(e["o"]); d = np.array(e["d"]); n = np.array(e["n"]); u = (P[:, :2] - o) @ d; s = (P[:, :2] - o) @ n; z = P[:, 2]
        im = (u >= e["u"][0]) & (u <= e["u"][1]) & (z >= e["z"][0]) & (z <= e["z"][1])
        wand = im & (np.abs(s) <= band)
        if N is not None: wand &= np.abs(N[:, :2] @ n) / np.maximum(np.linalg.norm(N[:, :2], axis=1), 1e-9) > np.cos(np.radians(winkel))         # Wandpunkte: Normale wandparallel gerichtet wie bei der Ebenenfindung
        vorn = im & (s > band) & (s <= VORN); r = np.abs(s[wand])
        # Schalenprofil
        h, ed = np.histogram(s[im & (np.abs(s) <= 0.5)], bins=100, range=(-0.5, 0.5)); h = np.convolve(h, np.ones(3) / 3, "same"); pk = h.max()
        c = int(np.argmax(h)); lo = c
        while lo > 0 and h[lo] > 0.1 * pk: lo -= 1
        hi_ = c
        while hi_ < len(h) - 1 and h[hi_] > 0.1 * pk: hi_ += 1
        l90 = c
        while l90 > 0 and h[l90] > 0.9 * pk: l90 -= 1
        h90 = c
        while h90 < len(h) - 1 and h[h90] > 0.9 * pk: h90 += 1
        breite = ((hi_ - lo) - (h90 - l90)) / 2.0 * 0.01        # Anstiegs+Abfallbreite 10-90 % (je Seite im Mittel), m
        # Oberkante: Dichte je z-Zeile (0,1 m) in der Wand; 10-90-Abfall um die Wandoberkante
        zz = np.arange(e["z"][0], e["z"][1] + 0.1, 0.1); hz, _ = np.histogram(z[wand], bins=zz); hz = np.convolve(hz, np.ones(3) / 3, "same")
        ref = np.median(hz[hz > 0]) if (hz > 0).any() else 0; top = np.where(hz > 0.5 * ref)[0]
        if ref > 0 and len(top):
            t = top[-1]; k90 = t
            while k90 > 0 and hz[k90] < 0.9 * ref: k90 -= 1
            k10 = t
            while k10 < len(hz) - 1 and hz[k10] > 0.1 * ref: k10 += 1
            oben = (k10 - k90) * 0.1
        else: oben = None
        # Abdeckung
        nu = int(np.ceil((e["u"][1] - e["u"][0]) / zelle)); nz = int(np.ceil((e["z"][1] - e["z"][0]) / zelle))
        iu = np.floor((u[wand] - e["u"][0]) / zelle).astype(int).clip(0, nu - 1); iz = np.floor((z[wand] - e["z"][0]) / zelle).astype(int).clip(0, nz - 1)
        occ = np.zeros((nu, nz), bool); occ[iu, iz] = True; fl = (e["u"][1] - e["u"][0]) * (e["z"][1] - e["z"][0])
        rp50, rp90 = rauheit(P, np.where(wand)[0])
        res.append(dict(rauheit_p50_cm=rp50, rauheit_p90_cm=rp90, n_wand=int(wand.sum()), rausch_p50_cm=round(float(np.percentile(r, 50)) * 100, 2), rausch_p90_cm=round(float(np.percentile(r, 90)) * 100, 2), schale_10_90_cm=round(breite * 100, 1),
                        kante_oben_cm=None if oben is None else round(oben * 100, 1), abdeckung=round(float(occ.mean()), 3), vor_fassade_n=int(vorn.sum()), vor_fassade_prozent=round(100 * float(vorn.sum()) / max(1, wand.sum()), 2),
                        vor_fassade_je_m2=round(float(vorn.sum()) / fl, 2), vor_isoliert_prozent=None if iso is None else round(100 * float((vorn & iso).sum()) / max(1, wand.sum()), 2), vor_isoliert_n=None if iso is None else int((vorn & iso).sum()), flaeche_m2=round(fl, 1), occ_zellen=int(occ.sum())))
    return res


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter); ap.add_argument("--ref", required=True); ap.add_argument("--kameras", required=True); ap.add_argument("--aus", required=True)
    ap.add_argument("--n-ebenen", type=int, default=10); ap.add_argument("--min-anteil", type=float, default=0.004); ap.add_argument("varianten", nargs="+"); a = ap.parse_args()
    K = json.load(open(a.kameras)); cam = np.mean([-np.array(k["R"]).T @ np.array(k["t"]) for k in K.values()], 0)
    Pref, Nref = lesen(a.ref); E = ebenen_ransac(Pref, Nref, cam, a.n_ebenen, min_anteil=a.min_anteil, min_flaeche=15.0); print("Referenzebenen:", [(round(e["n_inlier"] / 1000), "k", [round(x, 2) for x in e["n"]], e["flaeche_belegt_m2"]) for e in E], flush=True)
    erg = dict(ebenen=E, band=BAND, zelle=ZELLE, vorn=VORN, varianten={})
    for v in a.varianten:
        P, Nv = lesen(v); name = os.path.basename(v.rstrip("/")) if not v.endswith(".ply") else os.path.basename(os.path.dirname(v)); iso = isoliert(P); r = kennzahlen(P, E, N=Nv, iso=iso); erg['varianten'][name] = dict(punkte=int(len(P)), isoliert_gesamt_prozent=round(100 * float(iso.mean()), 2)); erg["varianten"][name].update(ebenen=r)
        w = np.array([x["n_wand"] for x in r], float); print(name, len(P), "p50", [x["rausch_p50_cm"] for x in r], "p90", [x["rausch_p90_cm"] for x in r], "abd", [x["abdeckung"] for x in r], "vor%", [x["vor_fassade_prozent"] for x in r], flush=True)
    json.dump(erg, open(a.aus, "w"), indent=1)


if __name__ == "__main__": main()
