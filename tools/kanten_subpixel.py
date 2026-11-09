#!/usr/bin/env python3
"""Subpixel-Canny (Gradient-Parabel quer zur Kante) und Test, ob Kanten dadurch GERADER werden.
Test: LSD-Linien auf dem entzerrten Bild; je Linie Kantenpunkte (ganzzahliger Canny vs Subpixel) im Streifen +-2,5 px einsammeln, Gerade per Totalausgleich fitten, Rest-RMS (px) vergleichen.
Aufruf: python -I tools/kanten_subpixel.py BILD.png [--ausschnitt x0 x1 y0 y1 (Anteile)]"""
import sys, numpy as np, cv2

def subpixel_kanten(gray, sigma=1.0, lo=40, hi=100):
    g = cv2.GaussianBlur(gray.astype(np.float32), (0, 0), sigma); gx = cv2.Sobel(g, cv2.CV_32F, 1, 0, ksize=3) / 8; gy = cv2.Sobel(g, cv2.CV_32F, 0, 1, ksize=3) / 8; mag = np.hypot(gx, gy)
    ed = cv2.Canny(cv2.GaussianBlur(gray, (0, 0), sigma), lo, hi); ys, xs = np.where(ed > 0); H, W = g.shape
    ok = (xs > 1) & (xs < W - 2) & (ys > 1) & (ys < H - 2); xs, ys = xs[ok], ys[ok]
    nx = gx[ys, xs] / np.maximum(mag[ys, xs], 1e-6); ny = gy[ys, xs] / np.maximum(mag[ys, xs], 1e-6)
    def m_at(dx):                                                         # Betrag entlang der Gradientenrichtung, bilinear
        return cv2.remap(mag, (xs + dx * nx).astype(np.float32)[None], (ys + dx * ny).astype(np.float32)[None], cv2.INTER_LINEAR)[0]
    m0, mm, mp = mag[ys, xs], m_at(-1.0), m_at(1.0); den = mm - 2 * m0 + mp; off = np.where(np.abs(den) > 1e-6, 0.5 * (mm - mp) / den, 0.0).clip(-0.7, 0.7)   # Parabelscheitel
    return xs.astype(np.float64), ys.astype(np.float64), xs + off * nx, ys + off * ny

def rest_rms(lines, P, breite=2.5, minpts=15):
    out = []
    for q in lines:
        c = np.array([q[2] - q[0], q[3] - q[1]]); L = np.linalg.norm(c)
        if L < 25: continue
        c /= L; nv = np.array([-c[1], c[0]]); d = P - q[:2]; a = d @ c; r = d @ nv; m = (a > -2) & (a < L + 2) & (np.abs(r) < breite)
        if m.sum() < minpts: continue
        Q = d[m]; mu = Q.mean(0); u, s, vt = np.linalg.svd(Q - mu, full_matrices=False); res = (Q - mu) @ np.array([-vt[0][1], vt[0][0]]); out.append(float(np.sqrt((res ** 2).mean())))
    return np.array(out)

if __name__ == "__main__":
    im = cv2.imread(sys.argv[1]); H, W = im.shape[:2]; f = (0.1, 0.6, 0.35, 0.85)
    if "--ausschnitt" in sys.argv: i = sys.argv.index("--ausschnitt"); f = tuple(float(v) for v in sys.argv[i + 1:i + 5])
    im = im[int(H * f[2]):int(H * f[3]), int(W * f[0]):int(W * f[1])]; gray = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
    L = cv2.createLineSegmentDetector(cv2.LSD_REFINE_STD).detect(cv2.GaussianBlur(gray, (0, 0), 0.8))[0].reshape(-1, 4)
    x0, y0, xs, ys = subpixel_kanten(gray); Pi = np.c_[x0, y0]; Ps = np.c_[xs, ys]
    ri, rs = rest_rms(L, Pi), rest_rms(L, Ps); n = min(len(ri), len(rs))
    print("Linien mit genug Kantenpunkten: ganzzahlig %d, subpixel %d" % (len(ri), len(rs)))
    print("Rest-RMS Abweichung von der Geraden (px): ganzzahliger Canny Median %.3f Mittel %.3f | Subpixel Median %.3f Mittel %.3f" % (np.median(ri), ri.mean(), np.median(rs), rs.mean()))
    print("Anteil sehr gerader Kanten (RMS < 0.3 px): ganzzahlig %.0f %%  subpixel %.0f %%" % (100 * (ri < 0.3).mean(), 100 * (rs < 0.3).mean()))
