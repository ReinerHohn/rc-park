#!/usr/bin/env python3
"""kamera_guete_lot2.py - modellUNABHAENGIGE Kameraguete je Foto aus der gemeinsamen SfM (sparse/0 + kam_lot2.json).

Liest NUR: sparse/{cameras,images,points3D}.bin und kam_lot2.json (sowie eigene Ausgabe). Kein STL, kein Netz, keine objekt.json-Geometrie,
keine teile_sicht-/foto_diff-Ausgabe (Z1; Beweis: tools/kamera_guete_lot2.py --dateizugriffe).
Verfahren (Z2, kein Eigenbezug): Leave-one-out je Foto i. Jeder Punkt, den i sieht und mind. 2 ANDERE Fotos sehen, wird NUR aus den anderen
Beobachtungen neu trianguliert (Strahlen-Kleinste-Quadrate, Posen der anderen fest). Daraus PnP-RANSAC + LM-Verfeinerung (f, k1 fest) -> Pose i.
Abweichung gegen die gespeicherte Pose: Lage dC (m), Winkel (Grad); daraus Lagefehler IN METERN auf einer Flaeche im Abstand d
(Gitter von Bildstrahlen, Punkt bei Tiefe d mit gespeicherter Pose -> mit LOO-Pose projiziert -> Pixel -> Meter).
Rauschboden je Foto: Halbierung der Punkte (zwei unabhaengige PnP). Reprojektionsfehler je Bildzone (Mitte/Mitte/Rand) mit voller Pose.
GRENZE (Z4): Gleichtaktfehler aller Kameras (Kippung, Massstab, Verschiebung) sind SfM-intern unsichtbar.
Aufruf: /media/oem/scan/venv-seg/bin/python -I tools/kamera_guete_lot2.py [--synth] [--aus JSON]"""
import sys, os, json, struct, argparse, numpy as np, cv2

D = "/media/oem/scan/rc-park_daten/kaufhaus_alle"
SPARSE = D + "/sfm/sparse/0"; KAM = D + "/sfm/kam_lot2.json"
AUS = "/home/oem/git/rc-park/modelle/kaufhaus_grob3/audit/kamera_guete_lot2.json"
_NP = {0: 3, 1: 4, 2: 4, 3: 5}


def quat_R(q):
    w, x, y, z = q
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)], [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


def lese_sparse(sp=SPARSE):
    cams = {}; b = open(sp + "/cameras.bin", "rb").read(); o = 8
    for _ in range(struct.unpack_from("<Q", b, 0)[0]):
        cid, mod, w, h = struct.unpack_from("<iiQQ", b, o); o += 24; n = _NP[mod]; p = struct.unpack_from("<" + "d" * n, b, o); o += 8 * n; cams[cid] = (mod, w, h, p)
    im = {}; b = open(sp + "/images.bin", "rb").read(); o = 8
    for _ in range(struct.unpack_from("<Q", b, 0)[0]):
        iid = struct.unpack_from("<i", b, o)[0]; q = struct.unpack_from("<4d", b, o + 4); t = struct.unpack_from("<3d", b, o + 36); cid = struct.unpack_from("<i", b, o + 60)[0]; o += 64
        e = b.index(b"\0", o); name = b[o:e].decode(); o = e + 1; npt = struct.unpack_from("<Q", b, o)[0]; o += 8
        a = np.frombuffer(b, dtype=np.dtype([("x", "<f8"), ("y", "<f8"), ("p", "<i8")]), count=npt, offset=o); o += 24 * npt
        R = quat_R(q); im[iid] = dict(name=name, R=R, t=np.array(t), C=-R.T @ np.array(t), cid=cid, xy=np.stack([a["x"], a["y"]], 1), pid=a["p"].copy())
    pts = {}; b = open(sp + "/points3D.bin", "rb").read(); o = 8
    for _ in range(struct.unpack_from("<Q", b, 0)[0]):
        pid, x, y, z = struct.unpack_from("<Qddd", b, o); o += 32 + 3; err, tl = struct.unpack_from("<dQ", b, o); o += 16
        tr = np.frombuffer(b, dtype=np.dtype([("i", "<i4"), ("k", "<i4")]), count=tl, offset=o); o += 8 * tl; pts[pid] = (np.array([x, y, z]), tr["i"].copy(), tr["k"].copy())
    return cams, im, pts


def entzerre(xy, par):
    """SIMPLE_RADIAL (f,cx,cy,k1): Pixel -> normierte unverzerrte Koordinaten."""
    f, cx, cy = par[0], par[1], par[2]; k = par[3] if len(par) > 3 else 0.0
    d = (xy - [cx, cy]) / f; u = d.copy()
    for _ in range(12): u = d / (1 + k * (u ** 2).sum(1, keepdims=True))
    return u


def verzerre(u, par):
    f, cx, cy = par[0], par[1], par[2]; k = par[3] if len(par) > 3 else 0.0
    return f * u * (1 + k * (u ** 2).sum(1, keepdims=True)) + [cx, cy]


def aehnlichkeit(A, B):
    mu, mv = A.mean(0), B.mean(0); H = (A - mu).T @ (B - mv); U, S, Vt = np.linalg.svd(H); d = np.sign(np.linalg.det(Vt.T @ U.T)); Dm = np.diag([1, 1, d]); R = Vt.T @ Dm @ U.T
    s = (S * np.diag(Dm)).sum() / ((A - mu) ** 2).sum(); return s, R, mv - s * R @ mu


def triangulieren(Cs, Ds):
    """Strahlen-Kleinste-Quadrate; Cs,Ds (n,3) Zentren/Richtungen -> X."""
    A = np.zeros((3, 3)); b = np.zeros(3)
    for c, d in zip(Cs, Ds):
        M = np.eye(3) - np.outer(d, d); A += M; b += M @ c
    return np.linalg.solve(A, b)


class Szene:
    def __init__(self):
        self.cams, self.im, self.pts = lese_sparse(); self.kam = json.load(open(KAM))
        self.name2id = {v["name"]: i for i, v in self.im.items()}
        ids = [i for i in self.im if self.im[i]["name"] in self.kam]
        s, R, t = aehnlichkeit(np.array([self.im[i]["C"] for i in ids]), np.array([self.kam[self.im[i]["name"]]["C"] for i in ids]))
        self.s = s            # Meter je SfM-Einheit (lot2)
        for v in self.im.values(): v["par"] = self.cams[v["cid"]][3]; v["WH"] = self.cams[v["cid"]][1:3]

    def loo(self, iid, min_andere=2, maxpt=1500, rng=None, nur=None, perturb=None):
        """LOO-Pose von Foto iid. nur: Index-Teilmenge der Punkte (fuer Halbierung). Rueckgabe dict oder None."""
        v = self.im[iid]; m = v["pid"] >= 0; pid = v["pid"][m]; xy = v["xy"][m]; X = []; keep = []
        for j, (p, q) in enumerate(zip(pid, xy)):
            Xp, ti, tk = self.pts[p]; sel = ti != iid
            if sel.sum() < min_andere: continue
            Cs = []; Ds = []
            for ii, kk in zip(ti[sel], tk[sel]):
                w = self.im[ii]; u = entzerre(w["xy"][kk][None], w["par"])[0]; d = w["R"].T @ np.array([u[0], u[1], 1.0]); Ds.append(d / np.linalg.norm(d)); Cs.append(w["C"])
            Cs = np.array(Cs); Ds = np.array(Ds)
            cosm = (Ds @ Ds.T).min()
            if cosm > np.cos(np.radians(2.0)): continue                       # Triangulationswinkel < 2 Grad
            Xt = triangulieren(Cs, Ds)
            if (((Xt - Cs) * Ds).sum(1) <= 0).any(): continue
            res = np.linalg.norm(np.cross(Xt - Cs, Ds), axis=1) / np.linalg.norm(Xt - Cs, axis=1)
            if res.max() * v["par"][0] > 6.0: continue                         # Strahlabstand grob in Pixel
            X.append(Xt); keep.append(j)
        if len(X) < 12: return None
        X = np.array(X); u = entzerre(xy[keep], v["par"]); n = len(X)
        if n > maxpt:
            r = rng or np.random.default_rng(0); sel = r.choice(n, maxpt, replace=False); X = X[sel]; u = u[sel]; n = maxpt
        if nur is not None: X = X[nur(n)]; u = u[nur(n)]
        K = np.eye(3); pix = u  # normierte Koordinaten: K=I, Schwelle in normierten Einheiten
        f = v["par"][0]
        ok, rv, tv, inl = cv2.solvePnPRansac(X, pix, K, None, iterationsCount=800, reprojectionError=4.0 / f, confidence=0.999, flags=cv2.SOLVEPNP_EPNP)
        if not ok or inl is None or len(inl) < 10: return None
        inl = inl.ravel(); rv, tv = cv2.solvePnPRefineLM(X[inl], pix[inl], K, None, rv, tv)
        Rm = cv2.Rodrigues(rv)[0]; t = tv.ravel(); C = -Rm.T @ t
        return dict(R=Rm, t=t, C=C, n=n, inl=int(len(inl)), X=X, u=pix, inliers=inl)

    def abweichung(self, iid, e, d_sfm_list):
        """Pose-Abweichung (SfM-Einheiten -> Meter) und Flaechenfehler bei Abstaenden (m)."""
        v = self.im[iid]; dC = (e["C"] - v["C"]) * self.s; dR = e["R"] @ v["R"].T
        ang = np.degrees(np.arccos(np.clip((np.trace(dR) - 1) / 2, -1, 1)))
        f = v["par"][0]; W, H = v["WH"]
        gx, gy = np.meshgrid(np.linspace(0.15, 0.85, 5) * W, np.linspace(0.15, 0.85, 5) * H); g = np.stack([gx.ravel(), gy.ravel()], 1)
        ug = entzerre(g, v["par"]); out = {}
        for dm in d_sfm_list:                                                   # dm in SfM-Einheiten (Tiefe)
            Xw = (np.c_[ug, np.ones(len(ug))] * dm) @ v["R"] + v["C"]          # Punkt bei Tiefe dm mit gespeicherter Pose
            Xc = Xw @ e["R"].T + e["t"]; ue = Xc[:, :2] / Xc[:, 2:3]
            pxe = verzerre(ue, v["par"]); px = float(np.linalg.norm(pxe - g, axis=1).mean())
            out[dm] = (px, px * (dm * self.s) / f)                              # Pixel, Meter an der Flaeche
        return dC, float(ang), out

    def reproj_zonen(self, iid):
        v = self.im[iid]; m = v["pid"] >= 0; pid = v["pid"][m]; xy = v["xy"][m]
        if len(pid) < 5: return None
        X = np.array([self.pts[p][0] for p in pid]); Xc = X @ v["R"].T + v["t"]; z = Xc[:, 2]
        pr = verzerre(Xc[:, :2] / z[:, None], v["par"]); e = np.linalg.norm(pr - xy, axis=1); W, H = v["WH"]
        r = np.linalg.norm((xy - [W / 2, H / 2]) / (0.5 * np.hypot(W, H)), axis=1); o = {}
        for nm, lo, hi in (("mitte", 0, .4), ("mittel", .4, .7), ("rand", .7, 9)):
            s = (r >= lo) & (r < hi) & (z > 0); o[nm] = (round(float(np.sqrt(np.median(e[s] ** 2))), 3) if s.sum() >= 5 else None, int(s.sum()))
        return o, float(np.median(z[z > 0]))


# ---------------- Klassen ----------------
TOL_GROB_M = 0.10     # Pruefer-Toleranz (Ziel 10 cm, Nutzer): ab hier wird ein Bauteil durch Kamerafehler falsch ROT
TOL_GUT_M = 0.03      # gut: Fehler + 2 sigma_Halbierung <= 3 cm (Rauschboden der Methode, siehe Bericht)


def klasse(fehler_m, sigma_m, inl, n_unabh):
    g = []
    if fehler_m is None: return "unbrauchbar", ["nicht belegbar: <12 unabhaengig triangulierbare Punkte / PnP scheitert"]
    if inl < 30: g.append(f"nur {inl} Inlier")
    obere = fehler_m + 2 * (sigma_m or 0)
    if obere > TOL_GROB_M or inl < 30: g.append(f"Fehler {fehler_m:.3f} m + 2 sigma {2 * (sigma_m or 0):.3f} m > {TOL_GROB_M} m" if obere > TOL_GROB_M else ""); return "unbrauchbar", [x for x in g if x]
    if obere > TOL_GUT_M: g.append(f"Fehler+2sigma {obere:.3f} m > {TOL_GUT_M} m"); return "grob", g
    return "gut", g


def bewerte(S, iid, rng):
    v = S.im[iid]; zon = S.reproj_zonen(iid)
    if zon is None: return dict(klasse="unbrauchbar", fehler_m_bei_abstand=None, fehler_px=None, gruende=["zu wenige Beobachtungen"])
    zonen, zmed = zon; e = S.loo(iid, rng=rng)
    if e is None: return dict(klasse="unbrauchbar", fehler_m_bei_abstand=None, fehler_px=None, abstand_m=round(zmed * S.s, 1), reproj_px=zonen, gruende=["nicht belegbar: zu wenige unabhaengig triangulierbare Punkte"])
    ds = [zmed, 10.0 / S.s]; dC, ang, o = S.abweichung(iid, e, ds)
    # Rauschboden: zwei disjunkte Haelften der LOO-Punkte
    perm = rng.permutation(e["n"]); h = []
    for sl in (perm[::2], perm[1::2]):
        e2 = S.loo(iid, rng=np.random.default_rng(1), nur=lambda n, sl=sl: sl[sl < n])
        if e2 is not None: h.append(S.abweichung(iid, e2, [zmed])[2][zmed][1])
    sig = float(abs(h[0] - h[1]) / 2) if len(h) == 2 else None
    f_m, f_px = o[zmed][1], o[zmed][0]
    kl, gr = klasse(f_m, sig, e["inl"], e["n"])
    return dict(klasse=kl, fehler_m_bei_abstand=round(f_m, 4), abstand_m=round(zmed * S.s, 1), fehler_px=round(f_px, 3), fehler_m_bei_10m=round(o[10.0 / S.s][1], 4),
                dC_m=round(float(np.linalg.norm(dC)), 4), dWinkel_grad=round(ang, 4), sigma_halbierung_m=None if sig is None else round(sig, 4), n_loo_punkte=e["n"], n_inlier=e["inl"],
                reproj_px=zonen, gruende=gr)


def synth(S, n_foto=30, seed=3):
    """Bekannte Posenstoerung der GESPEICHERTEN Pose (0,05/0,1/0,3 m; 0,2/0,5 Grad; gemischt) -> wird Abweichung gemessen, Klasse richtig?"""
    rng = np.random.default_rng(seed); ids = list(S.im); rng.shuffle(ids); stufen = [(0.05, 0), (0.1, 0), (0.3, 0), (0, 0.2), (0, 0.5), (0.1, 0.3), (0, 0)]; zeilen = []; used = 0
    for iid in ids:
        if used >= n_foto: break
        v = S.im[iid]
        if S.loo(iid, rng=np.random.default_rng(0)) is None: continue
        used += 1; R0, t0, C0 = v["R"].copy(), v["t"].copy(), v["C"].copy(); zon = S.reproj_zonen(iid); zmed = zon[1]
        for dm, dg in stufen:
            r = np.random.default_rng(int(rng.integers(1 << 30))); dirv = r.normal(size=3); dirv /= np.linalg.norm(dirv); ax = r.normal(size=3); ax /= np.linalg.norm(ax)
            Rp = cv2.Rodrigues(ax * np.radians(dg))[0] @ R0; Cp = C0 + dirv * dm / S.s
            v["R"], v["C"], v["t"] = Rp, Cp, -Rp @ Cp
            row = bewerte(S, iid, np.random.default_rng(0)); row.update(foto=v["name"], eingespielt_m=dm, eingespielt_grad=dg)
            # Soll: Flaechenfehler (Meter) aus der Stoerung selbst, ohne LOO
            e0 = dict(R=R0, t=t0, C=C0); soll = S.abweichung(iid, e0, [zmed])[2][zmed][1]; row["soll_fehler_m"] = round(soll, 4); zeilen.append(row)
        v["R"], v["t"], v["C"] = R0, t0, C0
    return zeilen


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--aus", default=AUS); ap.add_argument("--synth", action="store_true"); ap.add_argument("--dateizugriffe", action="store_true"); ap.add_argument("--n", type=int, default=0)
    a = ap.parse_args(); S = Szene(); rng = np.random.default_rng(0)
    if a.dateizugriffe:                                                          # Z1: open() mitprotokollieren
        import builtins; log = []; _o = builtins.open; builtins.open = lambda f, *k, **w: (log.append(str(f)), _o(f, *k, **w))[1]
        for iid in list(S.im)[:3]: bewerte(S, iid, rng)
        S2 = Szene(); builtins.open = _o; print("\n".join(sorted(set(log)))); sys.exit(0)
    if a.synth:
        z = synth(S); json.dump(z, open(a.aus.replace(".json", "_synth.json"), "w"), indent=0)
        import collections
        for st in sorted({(r["eingespielt_m"], r["eingespielt_grad"]) for r in z}):
            rr = [r for r in z if (r["eingespielt_m"], r["eingespielt_grad"]) == st and r["fehler_m_bei_abstand"] is not None]
            if not rr: continue
            print(st, "n", len(rr), "gemessen Flaechenfehler m med", round(float(np.median([r["fehler_m_bei_abstand"] for r in rr])), 3), "soll med", round(float(np.median([r["soll_fehler_m"] for r in rr])), 3),
                  "Klassen", dict(collections.Counter(r["klasse"] for r in rr)))
        sys.exit(0)
    ids = list(S.im)[:a.n] if a.n else list(S.im); out = {}
    for k, iid in enumerate(ids):
        out[S.im[iid]["name"]] = bewerte(S, iid, rng)
        if k % 40 == 0: print(k, len(ids), flush=True)
    json.dump(out, open(a.aus, "w"), indent=1)
    import collections; print(dict(collections.Counter(v["klasse"] for v in out.values())))
