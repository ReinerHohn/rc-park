"""faecher_fit.py - Faecherparameter (Erker 1) per Zwei-Foto-Konsens am Gold-Signal anpassen (13.11.2026).
Idee: Das 3D-Modell ist der Messer. Rippenmittellinien werden in K-6162 und K-6261 projiziert; Score = mittleres normiertes Gold-Signal
entlang der Linien in BEIDEN Fotos (Mehrdeutigkeit der Tiefe entfaellt, weil beide Ansichten dasselbe 3D pruefen).
Aufruf: /media/oem/scan/venv-seg/bin/python -W ignore -I faecher_fit.py  (aus /home/oem/git/rc-park)
Ausgabe: faecher_fit.json (Parameter, Score vorher/nachher je Foto)."""
import json, glob, math, sys, numpy as np, cv2
from scipy.optimize import differential_evolution
root = "/home/oem/git/rc-park"; ax = np.array([0.3338, 0.9426]); AC = 12.27; ZT, ZF = 8.12, 6.45; UM = 15.52
def cam(kid):
    k = json.load(open(f"{root}/modelle/kaufhaus_grob3/messprotokoll/{kid}.json"))["kamera"]; R, _ = cv2.Rodrigues(np.array(k["rvec"], float)); t = np.array(k["t"], float)
    return dict(R=R, t=t, f=k["f_px"], cx=k["cx"], cy=k["cy"], k1=float(k.get("k1") or 0))
def goldmap(kid, box):
    im = cv2.imread(glob.glob(f"{root}/daten/kaufhaus/fotos/{kid[2:]}_*")[0]).astype(np.float32); g = np.clip((im[..., 2] + im[..., 1]) / 2 - im[..., 0], 0, None)
    g = cv2.GaussianBlur(g, (0, 0), 2.0); x0, y0, x1, y1 = box; c = g[y0:y1, x0:x1]; lm = cv2.dilate(c, np.ones((41, 41))); return np.clip(c / (lm + 3.0), 0, 1)   # lokal normiert
def proj(K, P):
    x = P @ K["R"].T + K["t"]; xn, yn = x[:, 0] / x[:, 2], x[:, 1] / x[:, 2]; r2 = xn * xn + yn * yn
    return np.column_stack([K["f"] * xn * (1 + K["k1"] * r2) + K["cx"], K["f"] * yn * (1 + K["k1"] * r2) + K["cy"]])
nsurf = lambda z: np.interp(z, [6.45, 6.9, 7.2, 7.4, 7.6, 7.8, 8.12], [12.55, 12.70, 13.00, 13.25, 13.43, 13.60, 13.75])
def rippen(p, N=30):
    wf, ak, am, ao, ex = p; out = []
    W = lambda z: wf + (0.665 - wf) * (z - ZF) / (ZT - ZF)
    RIB = [(-1, ak, "k"), (1, -ak, "k"), (0, 0, "m"), (0, -am, "k"), (0, am, "k"), (-1, -ao, "a")]
    for th in (0, 45, -45):
        T = math.radians(th)
        for a0, a1, f in RIB + ([(1, ao, "a")] if th == -45 else []):
            pts = []
            for h in np.linspace(0, 1, N):
                z = ZT - (ZT - ZF) * h; g = {"a": h ** ex, "k": h * h * (3 - 2 * h), "m": h}[f]; s = a0 + (a1 - a0) * g; du = W(z) * s; rho = nsurf(z) - AC
                u = UM + rho * math.sin(T) + du * math.cos(T); n = AC + rho * math.cos(T) - du * math.sin(T)
                pts.append([u * ax[1] + n * ax[0], -u * ax[0] + n * ax[1], z])
            out.append(np.array(pts))
    return out
def score(p, K, G, box, ret=False):
    s = []
    for L in rippen(p):
        px = proj(K, L) - np.array(box[:2]); ok = (px[:, 0] >= 0) & (px[:, 0] < G.shape[1] - 1) & (px[:, 1] >= 0) & (px[:, 1] < G.shape[0] - 1)
        if ok.sum() < 3: continue
        s.append(G[px[ok, 1].astype(int), px[ok, 0].astype(int)].mean())
    return float(np.mean(s))
if __name__ == "__main__":
    ka, kb = cam("K-6162"), cam("K-6261"); ba, bb = (330, 1700, 770, 2050), (600, 2250, 1200, 2700); ga, gb = goldmap("K-6162", ba), goldmap("K-6261", bb)
    f = lambda p: -(score(p, ka, ga, ba) + score(p, kb, gb, bb)) / 2
    p0 = [0.30, 0.8, 0.7, 0.85, 1.6]; s0 = (score(p0, ka, ga, ba), score(p0, kb, gb, bb))
    # Nullkontrolle: gleicher Fit gegen verschobenes Gold-Bild (180 px) -> Score darf nicht gleich gut werden
    gz = np.roll(ga, 90, axis=1); gzb = np.roll(gb, 90, axis=1)
    r = differential_evolution(f, [(0.10, 0.45), (0.3, 1.0), (0.3, 1.0), (0.5, 1.0), (1.0, 2.5)], seed=1, maxiter=40, popsize=14, tol=1e-4, polish=False)
    s1 = (score(r.x, ka, ga, ba), score(r.x, kb, gb, bb)); nz = (score(r.x, ka, gz, ba), score(r.x, kb, gzb, bb))
    res = dict(start=p0, start_score_6162=s0[0], start_score_6261=s0[1], fit=list(map(float, r.x)), fit_score_6162=s1[0], fit_score_6261=s1[1], nullkontrolle_verschoben=nz, params="foot_halbbreite, a1_kreuz, a1_mittelknauf, a1_aussen, exponent_aussen")
    json.dump(res, open(f"{root}/modelle/rippen_runde_2026-11-13/faecher_fit.json", "w"), indent=1); print(json.dumps(res, indent=1))
