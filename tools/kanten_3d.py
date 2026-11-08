#!/usr/bin/env python3
"""kanten_3d.py - 3D-Linien aus kalibrierten Fotos (SPEC S8 Baustein 3). Eigenbau (LIMAP nicht installierbar, siehe Register).

Ablauf: LSD (OpenCV) je Foto -> Saat: 2D-Segment + Wolkenpunkte, die im selben Foto sichtbar sind (.vis), liefern Tiefe (1/z linear laengs der Linie)
-> 3D-Hypothese -> Projektion in ALLE Fotos, Zuordnung nach Abstand/Winkel/Ueberlappung -> Verfeinerung NUR aus den Bildsegmenten
(Ebenen Kamerazentrum+Segment, Linie = gemeinsame Schnittgerade, SVD) -> Neuabgleich mit engerer Toleranz -> >= min_fotos -> Dopplungen entfernen.
Die Wolke dient nur der Saat (Tiefe grob); Lage und Richtung der Linie entstehen aus den Bildsegmenten. Kein STL/LoD2.

  venv-seg/bin/python -I tools/kanten_3d.py --dicht DIR --ausrichtung SFM-AUSRICHTUNG.json --aus DIR [--ohne-bilder 001 ..] [--min-fotos 3]
Ausgabe: kanten_3d.json (Modellrahmen, m), kanten_3d.ply
"""
import os, sys, json, argparse, time
import numpy as np, cv2, torch
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import freiraum_pruefen as FP
DEV = "cuda" if torch.cuda.is_available() else "cpu"


def laden(dicht, ausr):
    tr = json.load(open(ausr))["transformation"]; s = float(tr["s"]); Ra = cv2.Rodrigues(np.array(tr["rvec"], float))[0]; ta = np.array(tr["t"], float)
    X = FP.ply_lesen(os.path.join(dicht, "fused.ply")); pi, ii = FP.vis_lesen(os.path.join(dicht, "fused.ply.vis"))
    K = json.load(open(os.path.join(dicht, "kameras_unverzerrt.json"))); ids = FP.vis_ids(dicht, K)
    return X, pi, ii, K, ids, (s, Ra, ta)


def segmente(dicht, K, ids, minlen=25.0):
    lsd = cv2.createLineSegmentDetector(cv2.LSD_REFINE_STD); S = []
    for i in ids:
        im = cv2.imread(os.path.join(dicht, "images", K[i]["bild"]), 0); r = lsd.detect(im)[0]
        r = np.zeros((0, 4), np.float32) if r is None else r.reshape(-1, 4)
        L = np.hypot(r[:, 2] - r[:, 0], r[:, 3] - r[:, 1]); S.append(r[L >= minlen].astype(np.float64))
    return S


def kamera(K, i):
    k = K[i]; Kmat = np.array([[k["fx"], 0, k["cx"]], [0, k["fy"], k["cy"]], [0, 0, 1.0]]); R = np.array(k["R"], float); t = np.array(k["t"], float)
    return Kmat, R, t, -R.T @ t, (k["W"], k["H"])


def saaten(X, pi, ii, K, ids, S, max_seg=700, tol_px=1.5, min_pts=8):
    H = []
    for a, i in enumerate(ids):
        Km, R, t, C, (W, Hh) = kamera(K, i); m = ii == a; P = X[pi[m]]; Xc = P @ R.T + t; z = Xc[:, 2]; ok = z > 0.5; Xc, z = Xc[ok], z[ok]
        uv = (Xc[:, :2] / z[:, None]) * [Km[0, 0], Km[1, 1]] + [Km[0, 2], Km[1, 2]]
        seg = S[a]; order = np.argsort(-np.hypot(seg[:, 2] - seg[:, 0], seg[:, 3] - seg[:, 1]))[:max_seg]
        uvt = torch.tensor(uv, device=DEV, dtype=torch.float32); zt = torch.tensor(z, device=DEV, dtype=torch.float32)
        for j in order:
            x1, y1, x2, y2 = seg[j]; d = np.array([x2 - x1, y2 - y1]); L = np.hypot(*d); u = d / L
            rel = uvt - torch.tensor([x1, y1], device=DEV, dtype=torch.float32); tt = (rel[:, 0] * u[0] + rel[:, 1] * u[1]) / L
            pd = (rel[:, 0] * -u[1] + rel[:, 1] * u[0]).abs(); sel = (pd < tol_px) & (tt > -0.02) & (tt < 1.02)
            if int(sel.sum()) < min_pts: continue
            t_ = tt[sel].cpu().numpy(); w = 1.0 / zt[sel].cpu().numpy()
            if t_.max() - t_.min() < 0.5: continue
            best = None
            for _ in range(30):
                q = np.random.choice(len(t_), 2, replace=False)
                if abs(t_[q[0]] - t_[q[1]]) < 0.1: continue
                sl = (w[q[1]] - w[q[0]]) / (t_[q[1]] - t_[q[0]]); ic = w[q[0]] - sl * t_[q[0]]; inl = np.abs(w - (ic + sl * t_)) < 0.03 * w
                if best is None or inl.sum() > best[0].sum(): best = (inl, sl, ic)
            if best is None or best[0].sum() < min_pts or best[0].sum() < 0.6 * len(t_): continue
            inl = best[0]; A = np.c_[np.ones(inl.sum()), t_[inl]]; ic, sl = np.linalg.lstsq(A, w[inl], rcond=None)[0]
            w0, w1 = ic, ic + sl
            if w0 <= 0 or w1 <= 0: continue
            P3 = []
            for (x, y, ww) in ((x1, y1, w0), (x2, y2, w1)):
                ray = np.array([(x - Km[0, 2]) / Km[0, 0], (y - Km[1, 2]) / Km[1, 1], 1.0]) / ww; P3.append(R.T @ (ray - t))
            H.append(np.array(P3))
    return np.array(H)


def projizieren(Hy, Km, R, t):
    Pc = Hy.reshape(-1, 3) @ R.T + t; z = Pc[:, 2]; uv = Pc[:, :2] / np.maximum(z, 1e-6)[:, None] * [Km[0, 0], Km[1, 1]] + [Km[0, 2], Km[1, 2]]
    return uv.reshape(-1, 2, 2), z.reshape(-1, 2)


def abgleich(Hy, K, ids, S, tol_px=3.0, cos_min=0.985, ueb_min=0.5, chunk=1500):
    """Je Hypothese und Foto: Index des besten Bildsegments (-1 keins). Rueckgabe (N, nFotos) und Restfehler px."""
    N = len(Hy); M = -np.ones((N, len(ids)), np.int32); E = np.full((N, len(ids)), np.inf)
    for a, i in enumerate(ids):
        Km, R, t, C, (W, Hh) = kamera(K, i); uv, z = projizieren(Hy, Km, R, t)
        ok = (z > 0.5).all(1) & (uv[:, :, 0] > -0.05 * W).all(1) & (uv[:, :, 0] < 1.05 * W).all(1) & (uv[:, :, 1] > -0.05 * Hh).all(1) & (uv[:, :, 1] < 1.05 * Hh).all(1)
        seg = S[a]
        if len(seg) == 0 or not ok.any(): continue
        sg = torch.tensor(seg, device=DEV, dtype=torch.float32); p = sg[:, :2]; q = sg[:, 2:]; dv = q - p; Ls = dv.norm(dim=1); u = dv / Ls[:, None]; nrm = torch.stack([-u[:, 1], u[:, 0]], 1)
        idx = np.where(ok)[0]
        for c in range(0, len(idx), chunk):
            ix = idx[c:c + chunk]; h = torch.tensor(uv[ix], device=DEV, dtype=torch.float32)       # (n,2,2)
            hd = h[:, 1] - h[:, 0]; hl = hd.norm(dim=1).clamp(min=1e-3); hu = hd / hl[:, None]
            cosv = (hu @ u.T).abs()                                                                    # (n,m)
            d0 = ((h[:, 0][:, None, :] - p[None]) * nrm[None]).sum(-1).abs(); d1 = ((h[:, 1][:, None, :] - p[None]) * nrm[None]).sum(-1).abs()
            a0 = ((h[:, 0][:, None, :] - p[None]) * u[None]).sum(-1); a1 = ((h[:, 1][:, None, :] - p[None]) * u[None]).sum(-1)
            lo = torch.minimum(a0, a1).clamp(min=0); hi = torch.maximum(a1, a0).minimum(Ls[None]); ueb = ((hi - lo).clamp(min=0)) / torch.minimum(hl[:, None], Ls[None])
            err = torch.maximum(d0, d1); good = (cosv > cos_min) & (err < tol_px) & (ueb > ueb_min)
            sc = torch.where(good, err, torch.full_like(err, 1e9)); mn, am = sc.min(1)
            m_ = (mn < 1e8).cpu().numpy(); M[ix[m_], a] = am.cpu().numpy()[m_]; E[ix[m_], a] = mn.cpu().numpy()[m_]
    return M, E


def verfeinern(Hy, M, K, ids, S):
    out = []
    for n in range(len(Hy)):
        fa = np.where(M[n] >= 0)[0]
        if len(fa) < 3: out.append(None); continue
        Ns, Cs = [], []
        for a in fa:
            Km, R, t, C, _ = kamera(K, ids[a]); x1, y1, x2, y2 = S[a][M[n, a]]
            r1 = R.T @ np.array([(x1 - Km[0, 2]) / Km[0, 0], (y1 - Km[1, 2]) / Km[1, 1], 1.0]); r2 = R.T @ np.array([(x2 - Km[0, 2]) / Km[0, 0], (y2 - Km[1, 2]) / Km[1, 1], 1.0])
            nn = np.cross(r1, r2); Ns.append(nn / np.linalg.norm(nn)); Cs.append(C)
        Ns = np.array(Ns); Cs = np.array(Cs); d = np.linalg.svd(Ns)[2][-1]
        if np.abs(Ns @ d).max() > 0.2: out.append(None); continue         # Ebenen schneiden sich nicht in einer Geraden
        mid = Hy[n].mean(0); b = (Ns * Cs).sum(1)
        A = np.vstack([Ns, d[None]]); bb = np.append(b, d @ mid); p = np.linalg.lstsq(A, bb, rcond=None)[0]
        ta = (Hy[n] - p) @ d; out.append((p + ta[0] * d, p + ta[1] * d, d, np.abs(Ns @ d).max()))
    return out


def entdoppeln(L, support, abst=0.12, wink_cos=0.99):
    order = np.argsort(-np.array(support)); keep = []
    for i in order:
        p0, p1 = L[i]; d = (p1 - p0) / np.linalg.norm(p1 - p0); dup = False
        for j in keep:
            q0, q1 = L[j]; e = (q1 - q0) / np.linalg.norm(q1 - q0)
            if abs(d @ e) < wink_cos: continue
            dist = max(np.linalg.norm(np.cross(p0 - q0, e)), np.linalg.norm(np.cross(p1 - q0, e)))
            a0, a1 = sorted([(p0 - q0) @ e, (p1 - q0) @ e]); ov = min(a1, np.linalg.norm(q1 - q0)) - max(a0, 0)
            if dist < abst and ov > 0.5 * min(np.linalg.norm(p1 - p0), np.linalg.norm(q1 - q0)): dup = True; break
        if not dup: keep.append(i)
    return keep


def lauf(dicht, ausr, aus, ohne_bilder=(), min_fotos=3, max_seg=700, log=print):
    t0 = time.time(); os.makedirs(aus, exist_ok=True); X, pi, ii, K, ids, (s, Ra, ta) = laden(dicht, ausr)
    if ohne_bilder:
        keep = [i for i in ids if i not in ohne_bilder]; drop = np.isin(ii, [ids.index(b) for b in ohne_bilder]); pi, ii = pi[~drop], ii[~drop]
    else: keep = ids
    log(f"Wolke {len(X)} Punkte, {len(ids)} Kameras ({len(ohne_bilder)} gestrichen)")
    S = segmente(dicht, K, ids); S = [(np.zeros((0, 4)) if ids[a] in ohne_bilder else S[a]) for a in range(len(ids))]
    log(f"Segmente: {sum(len(x) for x in S)} ({time.time()-t0:.0f}s)")
    np.random.seed(1); Hy = saaten(X, pi, ii, K, ids, S, max_seg=max_seg); log(f"Saaten: {len(Hy)} ({time.time()-t0:.0f}s)")
    M, E = abgleich(Hy, K, ids, S, tol_px=3.0); log(f"Abgleich1: >=3 Fotos {int(((M>=0).sum(1)>=min_fotos).sum())} ({time.time()-t0:.0f}s)")
    sel = np.where((M >= 0).sum(1) >= min_fotos)[0]; V = verfeinern(Hy[sel], M[sel], K, ids, S)
    ok = [k for k, v in enumerate(V) if v is not None]; R2 = np.array([[V[k][0], V[k][1]] for k in ok]); log(f"verfeinert: {len(ok)} ({time.time()-t0:.0f}s)")
    M2, E2 = abgleich(R2, K, ids, S, tol_px=1.5, cos_min=0.995, ueb_min=0.6); nf = (M2 >= 0).sum(1); g = np.where(nf >= min_fotos)[0]
    log(f"Abgleich2 (1,5 px): {len(g)} ({time.time()-t0:.0f}s)")
    Lg = R2[g]; sup = nf[g]; kp = entdoppeln(Lg, sup); Lg = Lg[kp]; Mg = M2[g][kp]; Eg = E2[g][kp]
    zu = lambda P: ((P - ta) @ Ra) / s                                                         # COLMAP-Rahmen -> Modellrahmen (m)
    lines = []
    for k in range(len(Lg)):
        fa = np.where(Mg[k] >= 0)[0]; lines.append(dict(p0=zu(Lg[k][0]).round(4).tolist(), p1=zu(Lg[k][1]).round(4).tolist(), fotos=[ids[a] for a in fa], n_fotos=int(len(fa)),
                                                         rms_px=round(float(np.sqrt(np.mean(Eg[k][fa] ** 2))), 2), laenge_m=round(float(np.linalg.norm(zu(Lg[k][1]) - zu(Lg[k][0]))), 3)))
    json.dump(dict(dicht=dicht, ausrichtung=ausr, ohne_bilder=list(ohne_bilder), min_fotos=min_fotos, seeds=int(len(Hy)), linien=lines), open(os.path.join(aus, "kanten_3d.json"), "w"), indent=0)
    V3 = np.array([[l["p0"], l["p1"]] for l in lines]).reshape(-1, 3); n = len(lines)
    with open(os.path.join(aus, "kanten_3d.ply"), "w") as f:
        f.write(f"ply\nformat ascii 1.0\nelement vertex {2*n}\nproperty float x\nproperty float y\nproperty float z\nelement edge {n}\nproperty int vertex1\nproperty int vertex2\nend_header\n")
        for v in V3: f.write("%.4f %.4f %.4f\n" % tuple(v))
        for k in range(n): f.write(f"{2*k} {2*k+1}\n")
    log(f"{n} Linien -> {aus} ({time.time()-t0:.0f}s)"); return lines


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter); ap.add_argument("--dicht", required=True); ap.add_argument("--ausrichtung", required=True)
    ap.add_argument("--aus", required=True); ap.add_argument("--ohne-bilder", nargs="*", default=[]); ap.add_argument("--min-fotos", type=int, default=3); ap.add_argument("--max-seg", type=int, default=700)
    a = ap.parse_args(); lauf(a.dicht, a.ausrichtung, a.aus, tuple(a.ohne_bilder), a.min_fotos, a.max_seg)


if __name__ == "__main__": main()
