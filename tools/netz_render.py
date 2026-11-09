"""Eigenpruefung 3D-Netze: Painter-Rasterung (orthografisch) mit Lambert-Schattierung aus mehreren Richtungen. Aufruf: python -I netz_render.py IN.npz OBJEKT.json OUT_PREFIX [--farbe objekt|grau]"""
import sys, json, numpy as np, cv2
z = np.load(sys.argv[1]); O = json.load(open(sys.argv[2])); pre = sys.argv[3]; V = z["V"].astype(np.float64); F = z["F"]; off = np.r_[0, np.cumsum(z["ntri"])]; ids = z["ids"]
n = np.array(O["fassade_n"]["wert"], float)[:2]; n /= np.linalg.norm(n); out = np.array([n[0], n[1], 0.0]); Cm = np.median(V, 0)
oid = np.zeros(len(F), int)
for k in range(len(ids)): oid[off[k]:off[k + 1]] = ids[k]
def render(az, el, fn, W=1200):
    a = np.radians(az); e = np.radians(el); d = np.array([np.cos(e) * (np.cos(a) * out[0] - np.sin(a) * out[1]), np.cos(e) * (np.sin(a) * out[0] + np.cos(a) * out[1]), np.sin(e)])   # Blickrichtung zur Kamera
    up = np.array([0, 0, 1.0]); r = np.cross(up, d); r /= np.linalg.norm(r); u = np.cross(d, r); X = (V - Cm) @ np.c_[r, u, d]; ext = np.abs(X[:, :2]).max(); sc = W * 0.48 / ext
    P2 = np.c_[X[:, 0] * sc + W / 2, -X[:, 1] * sc + W * 0.45]; T = F; tri = X[T]; nn = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]); nl = np.linalg.norm(nn, axis=1) + 1e-9; nn /= nl[:, None]
    nn = np.where((nn[:, 2] < 0)[:, None], -nn, nn); lam = 0.35 + 0.65 * np.abs(nn @ np.array([0.3, 0.4, 0.86])); zt = tri[:, :, 2].mean(1); im = np.full((int(W * 0.9), W, 3), 255, np.uint8)
    for t in np.argsort(zt):
        c = cv2.cvtColor(np.uint8([[[(oid[t] * 47) % 180, 150, 255]]]), cv2.COLOR_HSV2BGR)[0, 0].astype(float) * lam[t]
        cv2.fillConvexPoly(im, P2[T[t]].astype(np.int32), tuple(int(v) for v in c))
    cv2.imwrite(fn, im)
render(0, 5, pre + "_vorn.jpg"); render(55, 20, pre + "_schraeg.jpg"); render(90, 5, pre + "_seite.jpg"); print("ok")
