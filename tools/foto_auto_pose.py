#!/usr/bin/env python3
"""foto_auto_pose.py — VOLLAUTOMATISCH die Kamera-Pose eines bekannten 3D-Modells in einem
Foto finden (keine Hand-Korrespondenzen, kein Klicken).

Analysis-by-Synthesis:
  1. Struktur-Maske automatisch (Farbe/Textur: nicht Wald, nicht Himmel) → wo ist das Bauwerk.
  2. Intrinsics K aus EXIF.
  3. GROB: Kamera-Pose (Abstand/Azimut/Elevation/Versatz) absuchen, Modell-Silhouette rendern,
     die mit größtem IoU zur Maske gewinnt (weiter Konvergenzradius).
  4. FEIN: Pose per Powell auf Chamfer-Distanz (Modell-Kanten ↔ Masken-Rand, via Distanztrafo)
     — Masken-Rand ist wald-frei, also saubere Zielkanten.
Pose (rvec,tvec) wird als JSON ausgegeben; tools/foto_modell_overlay.py rendert damit.
"""
import argparse, json, numpy as np, cv2, trimesh
from scipy.optimize import minimize

L, N, PP, R, ZS = 224.0, 9, 224.0/9, 10.0, 36*0.61
TARGET = np.array([0.0, 3.0, ZS])            # Modell-Mittelpunkt (x,y,z)


def structure_mask(img):
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV); H, S, V = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    b, g, r = img[..., 0].astype(int), img[..., 1].astype(int), img[..., 2].astype(int)
    green = (g > r+12) & (g > b+5)
    sky = (H > 90) & (H < 135) & (S > 60) & (V > 120)
    fg = ((~green) & (~sky) & (S < 110)).astype(np.uint8)*255
    fg = cv2.morphologyEx(fg, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    fg = cv2.morphologyEx(fg, cv2.MORPH_CLOSE, np.ones((15, 15), np.uint8))
    n, lab, st, _ = cv2.connectedComponentsWithStats(fg)
    if n > 1:
        fg = (lab == 1+np.argmax(st[1:, cv2.CC_STAT_AREA])).astype(np.uint8)*255
    return fg


def look_at(d, az, el, tgt, roll=0.0):
    """Kamera im Abstand d um tgt (Azimut az um z, Elevation el). Gibt rvec,tvec (OpenCV)."""
    off = d*np.array([np.sin(az)*np.cos(el), -np.cos(az)*np.cos(el), np.sin(el)])
    C = tgt + off
    fwd = (tgt - C); fwd /= np.linalg.norm(fwd)
    up = np.array([0, 0, 1.0])
    x = np.cross(fwd, up);
    if np.linalg.norm(x) < 1e-6: x = np.array([1.0, 0, 0])
    x /= np.linalg.norm(x)
    y = np.cross(fwd, x)
    Rwc = np.array([x, y, fwd])                      # world->cam rows
    if roll:
        cr, sr = np.cos(roll), np.sin(roll)
        Rwc = np.array([[cr, sr, 0], [-sr, cr, 0], [0, 0, 1]]) @ Rwc
    rvec, _ = cv2.Rodrigues(Rwc)
    tvec = -Rwc @ C
    return rvec.ravel(), tvec


def proj(pts, rvec, tvec, K):
    p, _ = cv2.projectPoints(pts.astype(np.float64), rvec, tvec, K, None)
    return p.reshape(-1, 2)


def silhouette(V, F, rvec, tvec, K, shape):
    uv = proj(V, rvec, tvec, K).astype(np.int32)
    img = np.zeros(shape, np.uint8)
    for f in F:
        cv2.fillConvexPoly(img, uv[f], 255)
    return img


def model_edges_pts(rvec, tvec, K):
    """charakteristische Modell-Kanten (Bogen-Leibungen + Deck + Pfeiler-Senkrechten)."""
    pts = []
    for k in range(N):
        xc = -L/2 + (k+0.5)*PP
        pts += [[xc+R*np.cos(a), 0, ZS+R*np.sin(a)] for a in np.linspace(np.pi, 0, 24)]
        pts += [[xc+R*np.cos(a), 6, ZS+R*np.sin(a)] for a in np.linspace(np.pi, 0, 24)]
    pts += [[x, 0, ZS+R+1] for x in np.linspace(-L/2, L/2, 80)]        # Deck vorn
    pts += [[x, 0, 0] for x in np.linspace(-L/2, L/2, 40)]             # Basis vorn
    return np.array(pts, float)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--foto", required=True); ap.add_argument("--stl", required=True)
    ap.add_argument("--f-mm", type=float, required=True); ap.add_argument("--sensor-mm", type=float, required=True)
    ap.add_argument("--work-w", type=int, default=900)
    ap.add_argument("--out-pose", required=True); ap.add_argument("--out-vis", default="")
    a = ap.parse_args()
    img0 = cv2.imread(a.foto); H0, W0 = img0.shape[:2]
    img = cv2.resize(img0, (a.work_w, int(H0*a.work_w/W0))); h, w = img.shape[:2]
    f = a.f_mm/a.sensor_mm*a.work_w
    K = np.array([[f, 0, w/2.0], [0, f, h/2.0], [0, 0, 1]], float)
    mask = structure_mask(img); maskb = (mask > 0)
    m = trimesh.load(a.stl, force="mesh"); V = m.vertices.view(np.ndarray); F = m.faces

    # --- GROB: IoU-Suche über Abstand/Azimut/Elevation ---
    def iou(rvec, tvec):
        sil = silhouette(V, F, rvec, tvec, K, (h, w)) > 0
        inter = (sil & maskb).sum(); uni = (sil | maskb).sum()
        return inter/uni if uni else 0
    best = None
    for az in np.deg2rad(np.arange(-70, 71, 10)):
        for el in np.deg2rad(np.arange(-25, 11, 5)):
            for d in np.arange(60, 221, 20):
                rv, tv = look_at(d, az, el, TARGET)
                s = iou(rv, tv)
                if best is None or s > best[0]:
                    best = (s, d, az, el)
    _, d0, az0, el0 = best
    print(f"grob: IoU {best[0]:.2f}  d={d0:.0f} az={np.degrees(az0):.0f}° el={np.degrees(el0):.0f}°")

    # Verfeinern GROB per Powell auf -IoU (Param d,az,el + Zielversatz tx,tz)
    def negiou(p):
        d, az, el, tx, tz = p
        rv, tv = look_at(d, az, el, TARGET+np.array([tx, 0, tz]))
        return 1-iou(rv, tv)
    r1 = minimize(negiou, [d0, az0, el0, 0, 0], method="Powell",
                  options=dict(xtol=0.5, ftol=1e-3, maxiter=200))
    d, az, el, tx, tz = r1.x
    print(f"IoU-fein: IoU {1-r1.fun:.2f}  d={d:.0f} az={np.degrees(az):.0f}° el={np.degrees(el):.0f}°")

    # --- FEIN: Chamfer auf Masken-Rand ---
    edge = cv2.Canny(mask, 50, 150)
    dt = cv2.distanceTransform(255-edge, cv2.DIST_L2, 3)
    ept = model_edges_pts(0, 0, K)
    def chamfer(p):
        d, az, el, tx, tz = p
        rv, tv = look_at(d, az, el, TARGET+np.array([tx, 0, tz]))
        uv = proj(ept, rv, tv, K)
        xi = np.clip(uv[:, 0], 0, w-1).astype(int); yi = np.clip(uv[:, 1], 0, h-1).astype(int)
        return float(np.mean(np.minimum(dt[yi, xi], 25)))        # truncated → robust
    r2 = minimize(chamfer, r1.x, method="Powell", options=dict(xtol=0.3, ftol=1e-3, maxiter=300))
    d, az, el, tx, tz = r2.x
    rv, tv = look_at(d, az, el, TARGET+np.array([tx, 0, tz]))
    print(f"Chamfer-fein: {r2.fun:.2f}px  d={d:.0f} az={np.degrees(az):.0f}° el={np.degrees(el):.0f}°")

    json.dump({"rvec": rv.tolist(), "tvec": tv.ravel().tolist(), "work_w": a.work_w,
               "K": K.tolist(), "foto": a.foto, "stl": a.stl}, open(a.out_pose, "w"), indent=1)
    print("Pose ->", a.out_pose)
    if a.out_vis:
        sil = silhouette(V, F, rv, tv, K, (h, w))
        vis = img.copy(); lay = img.copy(); lay[sil > 0] = (0, 200, 90)
        vis = cv2.addWeighted(lay, 0.45, vis, 0.55, 0)
        for p in proj(model_edges_pts(0, 0, K), rv, tv, K).astype(int):
            cv2.circle(vis, tuple(p), 1, (0, 255, 255), -1)
        cv2.imwrite(a.out_vis, cv2.resize(vis, (560, int(h*560/w))))
        print("Vis ->", a.out_vis)


if __name__ == "__main__":
    main()
