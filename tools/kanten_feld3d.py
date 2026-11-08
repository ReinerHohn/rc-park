#!/usr/bin/env python3
"""kanten_feld3d.py - S10 Teil B: gemeinsames 3D-Kantenfeld aus weichen Mehrsicht-Kantenkarten (EMAP-Prinzip, Eigenbau) + Geraden/Kurven.

Prinzip (EMAP/NEF: Kantenkarten mehrerer Ansichten -> 3D-Kantenevidenz, keine Zuordnung zwischen Fotos). EMAP (cvg/EMAP, MIT laut README-Angabe, NeuS/NeuralUDF-Basis, Training je Szene,
Tage auf 8 GB-GPU zu schwer) wird NICHT benutzt; hier Voxel-Akkumulation mit Sichtbarkeit:
 1. Kandidaten-Voxel = Schale um die Wolke (fused.ply, nur Punkte mit >= 2 Trainingsfotos; Holdout-Fotos zaehlen nicht). Die Wolke liefert nur WO Oberflaeche ist.
 2. Je Voxel und Trainingsfoto: Projektion; sichtbar, wenn Voxeltiefe <= kleinste Tiefe der 3x3-Nachbarn der Tiefenkarte + tau (Tiefenkarten = Sichtbarkeit, nicht Kantenquelle);
    Evidenz = max der weichen Kantenkarte im Fenster (Voxelgroesse in px).
 3. Bestaetigung: Evidenz >= BEST (0,5) in >= MIN_FOTOS Fotos MIT >= MIN_LICHT verschiedenen Lichtgruppen (EXIF-Stunde, sonst je Foto eine Gruppe) und Blickwinkelstreuung
    (Resultierende der Blickrichtungen < cos(MIN_WINKEL)) und Anteil bestaetigend/sichtbar >= MIN_ANTEIL. Schatten (an Licht gebunden) und Textur (nur in Naehe) fallen so.
 4. Score = mittlere Evidenz ueber sichtbare Fotos; 3D-NMS (3x3x3) -> duenne Kantenpunkte.
 5. Extraktion: sequentielles RANSAC Geraden, dann Kreisboegen (3D-Kreis aus 3 Punkten), Rest bleibt Punkte.
Keine Objektnamen/Festwerte: alles aus --dicht/--karten. Schwellen stehen unten fest und werden nicht am Pruefbild getunt.

  venv-seg/bin/python -I tools/kanten_feld3d.py --dicht DIR --karten KARTENROOT --aus DIR [--ohne-fotos 001 ..] [--voxel 0.1] [--box x0 x1 y0 y1 z0 z1]
Ausgabe: feld_punkte.npz (Punkte, Score, nconf, nvis), kanten_geraden.json, kanten_kurven.json, kanten_punkte.ply
"""
import os, sys, json, argparse, time, glob
import numpy as np, cv2, torch
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
DEV = "cuda" if torch.cuda.is_available() else "cpu"
BEST, MIN_FOTOS, MIN_LICHT, MIN_WINKEL_GRAD, MIN_ANTEIL = 0.5, 3, 3, 5.0, 0.3     # fest, vor dem Lauf gesetzt (ANNAHME), nicht am Pruefbild getunt
SCHALE_M = 0.15                                                                     # Kandidatenschale um die Wolke (ANNAHME: Wolkenstreuung ~ 10 cm)
TAU_REL, TAU_ABS = 0.02, 0.15                                                       # Sichtbarkeitstoleranz: 2 % der Tiefe + 15 cm


def depth_lesen(p):
    raw = open(p, "rb").read(); i = 0; n = 0; hd = []
    while n < 3:
        j = raw.index(b"&", i); hd.append(int(raw[i:j])); i = j + 1; n += 1
    w, h, c = hd; a = np.frombuffer(raw[i:], dtype="<f4").reshape((w, h, c), order="F"); return np.ascontiguousarray(a.transpose(1, 0, 2)[:, :, 0])


def kamera(k):
    Km = np.array([[k["fx"], 0, k["cx"]], [0, k["fy"], k["cy"]], [0, 0, 1.0]]); R = np.array(k["R"], float); t = np.array(k["t"], float)
    return Km, R, t, -R.T @ t


def lichtgruppen(ids, sonne_json):
    """Gruppenindex je Foto: gleiche Aufnahmestunde (EXIF) = gleiche Lichtlage; ohne EXIF eigene Gruppe (ANNAHME: unbekannt = verschieden)."""
    ex = {}
    if sonne_json and os.path.exists(sonne_json):
        try: ex = {n: v.get("exif") for n, v in json.load(open(sonne_json))["fotos"].items()}
        except Exception: ex = {}
    key = {}; g = []
    for i in ids:
        e = ex.get(i); k = (e[:13] if e else "foto" + i)
        g.append(key.setdefault(k, len(key)))
    return np.array(g), len(key)


def feld(cams, karten, tiefen, kandidaten, gruppen, ngr, vox, log=print, chunk=150000):
    """cams: Liste (Km,R,t,C,W,H); karten[i]: uint8-Tensor (H,W) GPU; tiefen[i]: float-Tensor (H,W) GPU (0 = ungueltig); kandidaten (N,3).
    Rueckgabe je Kandidat: nvis, nconf, nlicht, resultierende Blickrichtung, mittlere Evidenz (sichtbar)."""
    nc = len(cams); N = len(kandidaten); RAD = (1, 2, 3, 4, 6, 8)
    pyr = [torch.stack([torch.nn.functional.max_pool2d(k[None, None].float(), 2 * r + 1, 1, r)[0, 0].to(torch.uint8) for r in RAD]) for k in karten]   # je Foto (6,H,W); Fenster = Voxelgroesse in px
    out = dict(nvis=np.zeros(N, np.int16), nconf=np.zeros(N, np.int16), nlicht=np.zeros(N, np.int16), res=np.ones(N, np.float32), mean=np.zeros(N, np.float32))
    G = torch.zeros((nc, ngr), device=DEV, dtype=torch.float16); G[torch.arange(nc), torch.tensor(gruppen)] = 1
    for c0 in range(0, N, chunk):
        P = torch.tensor(kandidaten[c0:c0 + chunk], device=DEV, dtype=torch.float32); n = len(P)
        vis = torch.zeros((n, nc), device=DEV, dtype=torch.bool); conf = torch.zeros((n, nc), device=DEV, dtype=torch.bool); ev = torch.zeros((n, nc), device=DEV)
        vs = torch.zeros((n, 3), device=DEV)
        for a, (Km, R, t, C, W, H) in enumerate(cams):
            Rt = torch.tensor(R, device=DEV, dtype=torch.float32); tt = torch.tensor(t, device=DEV, dtype=torch.float32)
            Pc = P @ Rt.T + tt; z = Pc[:, 2]; ok = z > 0.5
            u = Pc[:, 0] / z.clamp(min=1e-3) * float(Km[0, 0]) + float(Km[0, 2]); v = Pc[:, 1] / z.clamp(min=1e-3) * float(Km[1, 1]) + float(Km[1, 2])
            ok &= (u >= 0) & (u < W - 1) & (v >= 0) & (v < H - 1)
            ui = u.round().long().clamp(0, W - 1); vi = v.round().long().clamp(0, H - 1)
            D = tiefen[a]; dm = D[vi, ui]; tau = TAU_ABS + TAU_REL * z
            vi_ok = ok & (dm > 0) & (z <= dm + tau)                                                       # nicht hinter naechster Oberflaeche (Tiefenkarte am Pixel, Min-Pool vorab)
            rp = (0.5 * vox * float(Km[0, 0]) / z.clamp(min=1.0)); lv = torch.stack([(rp - r).abs() for r in RAD], 1).argmin(1)    # Fenster-Halbbreite = halbe Voxelgroesse in px
            e = pyr[a][lv, vi, ui].float() / 255.0
            vis[:, a] = vi_ok; conf[:, a] = vi_ok & (e >= BEST); ev[:, a] = torch.where(vi_ok, e, torch.zeros_like(e))
            dirv = (torch.tensor(C, device=DEV, dtype=torch.float32) - P); dirv = dirv / dirv.norm(dim=1, keepdim=True).clamp(min=1e-6)
            vs += dirv * conf[:, a:a + 1].float()
        nv = vis.sum(1); ncf = conf.sum(1); nl = ((conf.half() @ G) > 0).sum(1)
        res = vs.norm(dim=1) / ncf.clamp(min=1)
        out["nvis"][c0:c0 + n] = nv.cpu().numpy(); out["nconf"][c0:c0 + n] = ncf.cpu().numpy(); out["nlicht"][c0:c0 + n] = nl.cpu().numpy(); out["res"][c0:c0 + n] = res.cpu().numpy()
        out["mean"][c0:c0 + n] = (ev.sum(1) / nv.clamp(min=1)).cpu().numpy()
        if (c0 // chunk) % 5 == 0: log(f"  Voxel {c0 + n}/{N}")
    return out


def auswahl(o, min_fotos=MIN_FOTOS, min_licht=MIN_LICHT, min_winkel=MIN_WINKEL_GRAD, min_anteil=MIN_ANTEIL):
    anteil = o["nconf"] / np.maximum(o["nvis"], 1)
    return (o["nconf"] >= min_fotos) & (o["nlicht"] >= min_licht) & (o["res"] < np.cos(np.radians(min_winkel))) & (anteil >= min_anteil)


def nms3d(P, score, vox, ok, SL=64):
    """3D-Nichtmaximum-Unterdrueckung (3x3x3) auf Voxelraster in x-Platten (GPU-Speicher); gibt Indizes der behaltenen Punkte (unter ok)."""
    idx = np.where(ok)[0]
    if len(idx) == 0: return idx
    lo = P[idx].min(0) - 2 * vox; ij = np.round((P[idx] - lo) / vox).astype(np.int64) + 1; sh = ij.max(0) + 2; sc = score[idx]; keep = np.zeros(len(idx), bool)
    for x0 in range(0, int(sh[0]), SL):
        x1 = min(x0 + SL, int(sh[0])); m = (ij[:, 0] >= x0 - 1) & (ij[:, 0] < x1 + 1)
        if not m.any(): continue
        q = ij[m]; g = torch.zeros((x1 - x0 + 2, int(sh[1]), int(sh[2])), device=DEV, dtype=torch.float32); xx = q[:, 0] - (x0 - 1); o_ = (xx >= 0) & (xx < g.shape[0])
        t_ = (torch.tensor(xx[o_], device=DEV), torch.tensor(q[o_, 1], device=DEV), torch.tensor(q[o_, 2], device=DEV)); g[t_] = torch.tensor(sc[m][o_], device=DEV, dtype=torch.float32)
        mx = torch.nn.functional.max_pool3d(g[None, None], 3, 1, 1)[0, 0]; k = (g[t_] >= mx[t_]).cpu().numpy(); sel = np.where(m)[0][o_]
        inner = (ij[sel, 0] >= x0) & (ij[sel, 0] < x1); keep[sel[k & inner]] = True; del g, mx
    return idx[keep]


# ----------------------------------------------------------------- Geraden / Kreisboegen
def geraden(P, abst=0.08, min_len=1.0, min_in=12, n_max=500, nach=3.0, seed=0):
    from scipy.spatial import cKDTree
    rng = np.random.default_rng(seed); rest = np.ones(len(P), bool); tree = cKDTree(P); out = []
    for _ in range(n_max):
        idx = np.where(rest)[0]
        if len(idx) < min_in: break
        best = None
        for _t in range(150):
            i = rng.choice(idx); nb = [j for j in tree.query_ball_point(P[i], nach) if rest[j]]
            if len(nb) < min_in: continue
            j = rng.choice(nb)
            if j == i: continue
            d = P[j] - P[i]; L = np.linalg.norm(d)
            if L < 0.3: continue
            d /= L; Q = P[idx] - P[i]; w = np.linalg.norm(Q - np.outer(Q @ d, d), axis=1); inl = idx[w < abst]
            if best is None or len(inl) > len(best): best = inl
        if best is None or len(best) < min_in: break
        for _r in range(3):                                                                         # Neuanpassung (SVD) und Inlier neu
            c = P[best].mean(0); d = np.linalg.svd(P[best] - c)[2][0]; Q = P[idx] - c; w = np.linalg.norm(Q - np.outer(Q @ d, d), axis=1); best = idx[w < abst]
        if len(best) < min_in: rest[best[:1]] = False; continue
        c = P[best].mean(0); d = np.linalg.svd(P[best] - c)[2][0]; tt = (P[best] - c) @ d; L = tt.max() - tt.min()
        rest[best] = False
        if L >= min_len: out.append(dict(p0=(c + tt.min() * d).round(3).tolist(), p1=(c + tt.max() * d).round(3).tolist(), laenge_m=round(float(L), 3), n=int(len(best)),
                                         dichte_je_m=round(float(len(best) / L), 1)))
    return out, rest


def kreis3(a, b, c):
    """Kreis durch 3 Punkte: Mittelpunkt, Radius, Normale, Basis (e1,e2)."""
    ab, ac = b - a, c - a; n = np.cross(ab, ac); nn = np.linalg.norm(n)
    if nn < 1e-6: return None
    ctr = a + (np.cross(n, ab) * (ac @ ac) + np.cross(ac, n) * (ab @ ab)) / (2 * nn * nn); r = np.linalg.norm(ctr - a); n = n / nn
    e1 = (a - ctr) / r; e2 = np.cross(n, e1); return ctr, r, n, e1, e2


def boegen(P, abst=0.08, r_min=0.5, r_max=15.0, min_in=15, min_wink=60.0, n_max=100, nach=6.0, seed=1, versuche=400):
    from scipy.spatial import cKDTree
    rng = np.random.default_rng(seed); rest = np.ones(len(P), bool); tree = cKDTree(P); out = []
    for _ in range(n_max):
        idx = np.where(rest)[0]
        if len(idx) < min_in: break
        best = None
        for _t in range(versuche):
            i = rng.choice(idx); nb = np.array([j for j in tree.query_ball_point(P[i], nach) if rest[j]])
            if len(nb) < min_in: continue
            j, k = rng.choice(nb, 2, replace=False); K = kreis3(P[i], P[j], P[k])
            if K is None or not (r_min < K[1] < r_max): continue
            ctr, r, n, e1, e2 = K; Q = P[idx] - ctr; h = Q @ n; rho = np.linalg.norm(Q - np.outer(h, n), axis=1)
            inl = idx[(np.abs(h) < abst) & (np.abs(rho - r) < abst)]
            if best is None or len(inl) > len(best[0]): best = (inl, K)
        if best is None or len(best[0]) < min_in: break
        inl = best[0]; ctr, r, n, e1, e2 = best[1]
        ang = np.degrees(np.arctan2((P[inl] - ctr) @ e2, (P[inl] - ctr) @ e1)); sa = np.sort(ang); lue = np.diff(np.r_[sa, sa[0] + 360]); umfang = 360 - lue.max()
        rest[inl] = False
        if umfang >= min_wink:
            a0 = sa[(np.argmax(lue) + 1) % len(sa)]; out.append(dict(mitte=ctr.round(3).tolist(), radius_m=round(float(r), 3), normale=n.round(4).tolist(), e1=e1.round(4).tolist(), e2=e2.round(4).tolist(),
                                                                   winkel_von=round(float(a0), 1), winkel_umfang=round(float(umfang), 1), n=int(len(inl)), dichte_je_m=round(float(len(inl) / (np.radians(umfang) * r)), 1)))
    return out, rest


def punkte_ply(pfad, P, C=None):
    with open(pfad, "w") as f:
        f.write(f"ply\nformat ascii 1.0\nelement vertex {len(P)}\nproperty float x\nproperty float y\nproperty float z\nproperty uchar red\nproperty uchar green\nproperty uchar blue\nend_header\n")
        for i, p in enumerate(P): c = (255, 255, 255) if C is None else C[i]; f.write("%.3f %.3f %.3f %d %d %d\n" % (*p, *c))


# ----------------------------------------------------------------- Lauf auf einem Objekt
def lauf(dicht, kartenroot, aus, ohne=(), vox=0.05, box=None, pipes=("p1", "p2", "p3", "p4"), sonne=None, log=print):
    import freiraum_pruefen as FP
    t0 = time.time(); os.makedirs(aus, exist_ok=True); K = json.load(open(os.path.join(dicht, "kameras_unverzerrt.json"))); ids = sorted(K, key=int)   # nur Trainingsbild-Reihenfolge, NICHT vis-Index (der kommt aus FP.vis_ids)
    tr = [i for i in ids if i not in ohne]; log(f"{len(tr)} Trainingsfotos, {len(ohne)} ohne")
    cams, karten, tiefen = [], [], []
    for i in tr:
        Km, R, t, C = kamera(K[i]); W, H = K[i]["W"], K[i]["H"]; cams.append((Km, R, t, C, W, H))
        m = np.mean([cv2.imread(os.path.join(kartenroot, p, f"{i}.png"), 0).astype(np.float32) for p in pipes], 0)                  # WEICHES MITTEL der Pipelines
        mt = torch.tensor(m, device=DEV)[None, None]; karten.append(mt[0, 0].round().clamp(0, 255).to(torch.uint8))
        D = depth_lesen(os.path.join(dicht, "stereo", "depth_maps", f"{K[i]['bild']}.geometric.bin")); D = np.where(D > 0, D, np.inf).astype(np.float32)
        Dt = torch.tensor(D, device=DEV)[None, None]; Dmin = -torch.nn.functional.max_pool2d(-Dt, 3, 1, 1)[0, 0]; tiefen.append(torch.where(torch.isinf(Dmin), torch.zeros_like(Dmin), Dmin))
    log(f"Karten+Tiefen geladen {time.time()-t0:.0f}s")
    X = FP.ply_lesen(os.path.join(dicht, "fused.ply")); pi, ii = FP.vis_lesen(os.path.join(dicht, "fused.ply.vis"))
    vn = FP.vis_ids(dicht, K); nv = np.bincount(pi[~np.isin(ii, [vn.index(o) for o in ohne])], minlength=len(X)); X = X[nv >= 2]   # vis-Index = Bild-ID-Reihenfolge (Register CV), nicht Namensreihenfolge
    if box is not None: lo, hi = np.array(box[0::2]), np.array(box[1::2]); X = X[((X >= lo) & (X <= hi)).all(1)]
    lo = X.min(0) - SCHALE_M - vox; sh = np.ceil((X.max(0) + SCHALE_M + vox - lo) / vox).astype(int) + 1; log(f"Raster {tuple(sh)} = {int(np.prod(sh))/1e6:.0f} M Zellen")
    ij = np.round((X - lo) / vox).astype(np.int64); rk = int(round(SCHALE_M / vox)); vks = []; SL = 96
    for x0 in range(0, int(sh[0]), SL):                                                              # Platten mit Rand (GPU-Speicher), Dilatation = Max-Pool
        x1 = min(x0 + SL, int(sh[0])); m = (ij[:, 0] >= x0 - rk) & (ij[:, 0] < x1 + rk)
        if not m.any(): continue
        q = ij[m]; occ = torch.zeros((x1 - x0 + 2 * rk, int(sh[1]), int(sh[2])), device=DEV, dtype=torch.float16); xx = q[:, 0] - (x0 - rk); ok_ = (xx >= 0) & (xx < occ.shape[0])
        occ[torch.tensor(xx[ok_], device=DEV), torch.tensor(q[ok_, 1], device=DEV), torch.tensor(q[ok_, 2], device=DEV)] = 1
        sc = torch.nn.functional.max_pool3d(occ[None, None], 2 * rk + 1, 1, rk)[0, 0][rk:rk + x1 - x0] > 0; v = sc.nonzero().cpu().numpy(); v[:, 0] += x0; vks.append(v); del occ, sc
    vk = np.concatenate(vks); torch.cuda.empty_cache()
    cand = (lo + vk * vox).astype(np.float32); log(f"Kandidaten {len(cand)} ({time.time()-t0:.0f}s)")
    gr, ngr = lichtgruppen(tr, sonne); log(f"Lichtgruppen {ngr}")
    o = feld(cams, karten, tiefen, cand, gr, ngr, vox, log); ok = auswahl(o); log(f"bestaetigt {int(ok.sum())} ({time.time()-t0:.0f}s)")
    keep = nms3d(cand, o["mean"], vox, ok); P = cand[keep]; log(f"nach NMS {len(P)}")
    np.savez_compressed(os.path.join(aus, "feld_punkte.npz"), P=P, score=o["mean"][keep], nconf=o["nconf"][keep], nvis=o["nvis"][keep], nlicht=o["nlicht"][keep], vox=vox)
    for tag, kw in (("k2", dict(min_fotos=2, min_licht=2)), ("k4", dict(min_fotos=4, min_licht=3)), ("ohnelicht", dict(min_licht=1)), ("anteil05", dict(min_anteil=0.5))):   # Empfindlichkeit (nicht Teil des Standardergebnisses)
        kk_ = nms3d(cand, o["mean"], vox, auswahl(o, **kw)); np.savez_compressed(os.path.join(aus, f"feld_punkte_{tag}.npz"), P=cand[kk_], vox=vox); log(f"Variante {tag}: {len(kk_)} Punkte")
    gl, rest = geraden(P); gl_pts = len(P) - int(rest.sum()); bg, rest2 = boegen(P[rest])
    json.dump(dict(geraden=gl), open(os.path.join(aus, "kanten_geraden.json"), "w"), indent=0); json.dump(dict(boegen=bg), open(os.path.join(aus, "kanten_kurven.json"), "w"), indent=0)
    punkte_ply(os.path.join(aus, "kanten_punkte.ply"), P); log(f"Geraden {len(gl)} ({gl_pts} Punkte), Boegen {len(bg)} ({time.time()-t0:.0f}s)")
    return dict(P=P, geraden=gl, boegen=bg, ids=tr, o=o, keep=keep)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter); ap.add_argument("--dicht", required=True); ap.add_argument("--karten", required=True); ap.add_argument("--aus", required=True)
    ap.add_argument("--ohne-fotos", nargs="*", default=[]); ap.add_argument("--voxel", type=float, default=0.05); ap.add_argument("--box", nargs=6, type=float); ap.add_argument("--sonne"); ap.add_argument("--pipelines", default="p1,p2,p3,p4")
    a = ap.parse_args(); lauf(a.dicht, a.karten, a.aus, tuple(a.ohne_fotos), a.voxel, a.box, tuple(a.pipelines.split(",")), a.sonne)


if __name__ == "__main__": main()
