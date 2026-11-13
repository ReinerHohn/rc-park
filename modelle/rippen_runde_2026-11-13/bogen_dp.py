import json, glob, sys, numpy as np, cv2
from scipy.interpolate import splprep, splev
root = "/home/oem/git/rc-park"; ax = np.array([0.3338, 0.9426])
def cam(kid):
    k = json.load(open(f"{root}/modelle/kaufhaus_grob3/messprotokoll/{kid}.json"))["kamera"]
    R, _ = cv2.Rodrigues(np.array(k["rvec"], float)); t = np.array(k["t"], float); return dict(R=R, t=t, C=-R.T @ t, f=k["f_px"], cx=k["cx"], cy=k["cy"], k1=float(k.get("k1") or 0))
def ray(K, px):
    x, y = (px[0] - K["cx"]) / K["f"], (px[1] - K["cy"]) / K["f"]; xu, yu = x, y
    for _ in range(10): r2 = xu * xu + yu * yu; xu, yu = x / (1 + K["k1"] * r2), y / (1 + K["k1"] * r2)
    d = K["R"].T @ np.array([xu, yu, 1.0]); return K["C"], d / np.linalg.norm(d)
def proj(K, P):
    x = K["R"] @ P + K["t"]
    if x[2] <= 0: return None
    xn, yn = x[0] / x[2], x[1] / x[2]; r2 = xn * xn + yn * yn; return (K["f"] * xn * (1 + K["k1"] * r2) + K["cx"], K["f"] * yn * (1 + K["k1"] * r2) + K["cy"])
def uvz(P): return np.array([P[0] * ax[1] - P[1] * ax[0], P[0] * ax[0] + P[1] * ax[1], P[2]])
def inhuelle(P):
    u, n, z = uvz(P); return 13.7 < u < 17.4 and 11.6 < n < 14.0 and 6.2 < z < 8.4
def gold(im):
    f = im.astype(np.float32); s = np.clip((f[..., 2] + f[..., 1]) / 2 - f[..., 0], 0, None); return cv2.GaussianBlur(s, (0, 0), 1.5)
def lauf(name, pts, A="K-6162", B="K-6261", C3="K-d11"):
    KA, KB = cam(A), cam(B)
    iA = cv2.imread(glob.glob(f"{root}/daten/kaufhaus/fotos/{A[2:]}_*")[0]); iB = cv2.imread(glob.glob(f"{root}/daten/kaufhaus/fotos/{B[2:]}_*")[0]); gB = gold(iB); gB /= gB.max() + 1e-6
    pts = np.array(pts, float); tck, _ = splprep(pts.T, s=0, k=min(3, len(pts) - 1)); q = np.array(splev(np.linspace(0, 1, max(8, int(np.sum(np.hypot(*np.diff(pts, axis=0).T)) / 6))), tck)).T
    ts = np.arange(20, 60, 0.02); S = np.full((len(q), len(ts)), -1.0); P3 = np.zeros((len(q), len(ts), 3))
    for i, p in enumerate(q):
        c, d = ray(KA, p)
        for j, t in enumerate(ts):
            P = c + d * t; P3[i, j] = P
            if not inhuelle(P): continue
            b = proj(KB, P)
            if b is None: continue
            x, y = int(round(b[0])), int(round(b[1]))
            if 0 <= x < gB.shape[1] and 0 <= y < gB.shape[0]: S[i, j] = gB[max(y - 1, 0):y + 2, max(x - 1, 0):x + 2].max()
    # DP: Gold hoch, Tiefe stetig
    lam = 0.02; best = np.full_like(S, -1e9); arg = np.zeros(S.shape, int); best[0] = np.where(S[0] >= 0, S[0], -1e9)
    for i in range(1, len(q)):
        for j in range(len(ts)):
            if S[i, j] < 0: continue
            lo, hi = max(0, j - 15), min(len(ts), j + 16); cand = best[i - 1, lo:hi] - lam * np.abs(np.arange(lo, hi) - j); k = int(np.argmax(cand)); best[i, j] = S[i, j] + cand[k]; arg[i, j] = lo + k
    j = int(np.argmax(best[-1])); idx = [j]
    for i in range(len(q) - 1, 0, -1): j = arg[i, j]; idx.append(j)
    idx = idx[::-1]; P = np.array([P3[i, j] for i, j in enumerate(idx)]); sc = np.array([S[i, j] for i, j in enumerate(idx)])
    return q, P, sc, iA, iB, KA, KB
