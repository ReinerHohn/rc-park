import json, numpy as np, pycolmap
S = "/tmp/claude-29999/-home-oem-git-rc-park/dc62add2-9ee3-4f76-85e0-42c96eea284b/scratchpad/"
B22 = "/media/oem/scan/rc-park_daten/schwabentor-1122/pipe/sfm/"


def rodr(v):
    v = np.asarray(v, float); th = np.linalg.norm(v)
    if th < 1e-12: return np.eye(3)
    k = v / th; K = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
    return np.eye(3) + np.sin(th) * K + (1 - np.cos(th)) * K @ K


AUS = json.load(open(S + "obj22/messprotokoll/SFM-AUSRICHTUNG-schwabentor-1122.json"))
TR = AUS["transformation"]; TS = TR["s"]; TRm = rodr(TR["rvec"]); TT = np.array(TR["t"])
VER = json.load(open(B22 + "sparse/0/vereint.json"))
M1 = np.array(VER["teile"][1]["matrix"])
GPS = json.load(open(S + "e/gps.json"))
OBJ = json.load(open(S + "obj22/objekt.json"))


def sfm_zu_obj(X):
    """X_sfm = s R X_modell + t -> X_modell."""
    return (np.asarray(X) - TT) @ TRm / TS


def stamm(n): return n.rsplit(".", 1)[0]


def zentren(rec):
    return {stamm(im.name): np.asarray(im.projection_center()) for im in rec.images.values() if im.has_pose}


def umeyama(a, b, mit_s=True):
    """b ~ s R a + t (3D)."""
    ma, mb = a.mean(0), b.mean(0); a0, b0 = a - ma, b - mb
    U, Sg, Vt = np.linalg.svd(b0.T @ a0 / len(a))
    D = np.eye(3); D[2, 2] = np.sign(np.linalg.det(U @ Vt))
    R = U @ D @ Vt; s = (Sg * np.diag(D)).sum() / ((a0 ** 2).sum() / len(a)) if mit_s else 1.0
    return s, R, mb - s * R @ ma


def robust_sim3(a, b, it=5, q=80):
    w = np.ones(len(a), bool)
    for _ in range(it):
        s, R, t = umeyama(a[w], b[w]); r = np.linalg.norm(a @ R.T * s + t - b, axis=1)
        w = r <= max(np.percentile(r, q), 1e-9)
    return s, R, t, r


def fit2d(a, b):
    ma, mb = a.mean(0), b.mean(0); a0, b0 = a - ma, b - mb; U, Sg, Vt = np.linalg.svd(a0.T @ b0)
    d = np.sign(np.linalg.det(Vt.T @ U.T)); D = np.diag([1, d]); R = Vt.T @ D @ U.T
    s = (Sg * np.diag(D)).sum() / max((a0 ** 2).sum(), 1e-12); return s, R, mb - s * R @ ma


def winkel(R): return float(np.degrees(np.arctan2(R[1, 0], R[0, 0])))


def gps_fit(cent_obj, nah=100.0, seed=0, boot=300):
    """cent_obj: name -> Objektrahmen-Standort. Fit GPS(obj-Rahmen 2D) ~ s R M + t, RANSAC < 10 m wie lage_gps_pruefen. Rueckgabe dict."""
    nm = [n for n in cent_obj if n in GPS]
    if len(nm) < 10: return dict(n=len(nm))
    M = np.array([cent_obj[n][:2] for n in nm]); G = np.array([GPS[n]["obj"] for n in nm])
    nah_ = np.hypot(*G.T) < nah; M, G = M[nah_], G[nah_]; nm = [n for n, k in zip(nm, nah_) if k]
    ok = np.isfinite(M).all(1) & (np.hypot(*M.T) < 1000); M, G = M[ok], G[ok]; nm = [n for n, k in zip(nm, ok) if k]
    rng = np.random.default_rng(seed); best = None
    for _ in range(3000):
        i = rng.choice(len(G), 2, replace=False)
        if np.hypot(*(G[i[0]] - G[i[1]])) < 10: continue
        s, R, t = fit2d(M[i], G[i]); inl = np.hypot(*(M @ R.T * s + t - G).T) < 10
        if best is None or inl.sum() > best.sum(): best = inl
    w = best
    for _ in range(3): s, R, t = fit2d(M[w], G[w]); res = np.hypot(*(M @ R.T * s + t - G).T); w = res < 10
    s, R, t = fit2d(M[w], G[w]); res = np.hypot(*(M @ R.T * s + t - G).T)
    iw = np.flatnonzero(w); ys, ss = [], []
    for _ in range(boot):
        i = rng.choice(iw, len(iw)); s_, R_, _ = fit2d(M[i], G[i]); ys.append(winkel(R_)); ss.append(s_)
    return dict(n=len(G), inlier=int(w.sum()), dreh=winkel(R), dreh90=np.percentile(ys, [5, 95]).round(2).tolist(), s=float(s),
                s90=np.percentile(ss, [5, 95]).round(3).tolist(), rest=float(np.median(res[w])), namen=[nm[i] for i in iw], _M=M, _G=G, _w=w, _srt=(s, R, t))


def kurz(g):
    if "dreh" not in g: return f"n {g['n']} (zu wenig)"
    return f"n {g['n']} inl {g['inlier']} Drehung {g['dreh']:+.2f} ({g['dreh90'][0]:+.1f}..{g['dreh90'][1]:+.1f}) Massstab x{g['s']:.3f} ({g['s90'][0]:.3f}..{g['s90'][1]:.3f}) Rest {g['rest']:.2f} m"
