#!/usr/bin/env python3
"""foto_georef_overlay.py — GENERISCH & georef: ein in Weltkoordinaten (UTM) stehendes Modell
aus Kamera-Metadaten (GPS/Höhe/Kompass) in ein Foto projizieren — struktur-agnostisch
(Viadukt, Staumauer, Gelände, Gebäude). Metadaten = grober Start; Kanten-Feinschliff separat.

Kamera-Pose: Position E,N,alt (GPS) + yaw (Kompass), pitch, roll.
Modell-Georef: Zentrum E,N, Basis-Höhe, Achs-Azimut; lokales STL (x=Länge, y=Tiefe, z=Höhe).
Projektion: pinhole (normale Fotos) ODER cylindrical (gestitchte Panoramen).
"""
import argparse, json, numpy as np, cv2, trimesh


def model_to_enu(V, cE, cN, base_alt, azimuth_deg):
    A = np.radians(azimuth_deg)
    sa, ca = np.sin(A), np.cos(A)
    mx, my, mz = V[:, 0], V[:, 1], V[:, 2]
    E = cE + mx*sa + my*ca
    N = cN + mx*ca - my*sa
    U = base_alt + mz
    return np.column_stack([E, N, U])


def enu_to_cam(P_enu, camE, camN, camAlt, yaw_deg, pitch_deg=0.0, roll_deg=0.0):
    y, p, r = np.radians([yaw_deg, pitch_deg, roll_deg])
    fwd = np.array([np.sin(y)*np.cos(p), np.cos(y)*np.cos(p), np.sin(p)])
    up = np.array([0, 0, 1.0])
    right = np.cross(fwd, up); right /= np.linalg.norm(right)
    down = np.cross(fwd, right)
    if r:
        cr, sr = np.cos(r), np.sin(r)
        right, down = cr*right+sr*down, -sr*right+cr*down
    Rwc = np.array([right, down, fwd])
    rel = P_enu - np.array([camE, camN, camAlt])
    return rel @ Rwc.T                                   # (Xc right, Yc down, Zc forward)


def project(Xc, K, mode="pinhole", f_cyl=None):
    cx, cy, f = K[0, 2], K[1, 2], K[0, 0]
    X, Y, Z = Xc[:, 0], Xc[:, 1], Xc[:, 2]
    if mode == "cylindrical":
        fc = f_cyl or f
        ang = np.arctan2(X, Z)
        u = cx + fc*ang
        v = cy + fc*Y/np.hypot(X, Z)
        return np.column_stack([u, v]), Z
    Zc = np.clip(Z, 1e-6, None)
    return np.column_stack([cx + f*X/Zc, cy + f*Y/Zc]), Z


def render(a):
    cfg = json.load(open(a.cfg))
    img0 = cv2.imread(cfg["foto"]); H0, W0 = img0.shape[:2]
    ww = a.work_w; hh = int(H0*ww/W0); img = cv2.resize(img0, (ww, hh))
    f = cfg["f_mm"]/cfg["sensor_mm"]*ww
    K = np.array([[f, 0, ww/2.0], [0, f, hh/2.0], [0, 0, 1]], float)
    cam = cfg["cam"]; mdl = cfg["model"]
    f_cyl = None
    if cfg.get("proj") == "cylindrical":
        f_cyl = cfg["f_mm"]/cfg["sensor_mm"]*cfg["frame_px"]*ww/W0

    m = trimesh.load(mdl["stl"], force="mesh"); V = m.vertices.view(np.ndarray); Fc = m.faces
    P = model_to_enu(V, mdl["E"], mdl["N"], mdl["base_alt"], mdl["azimuth"])
    Xc = enu_to_cam(P, cam["E"], cam["N"], cam["alt"], cam["yaw"], cam.get("pitch", 0), cam.get("roll", 0))
    uv, Z = project(Xc, K, cfg.get("proj", "pinhole"), f_cyl)
    front = (Z > 0).mean()
    print(f"vor Kamera: {front*100:.0f}% der Vertices · proj={cfg.get('proj','pinhole')}")

    vis = img.copy(); lay = img.copy()
    order = np.argsort(-Z[Fc].mean(1))
    for fi in order:
        pts = uv[Fc[fi]].astype(np.int32)
        if (Z[Fc[fi]] <= 0).any(): continue
        if (pts < -2*ww).any() or (pts > 3*ww).any(): continue
        cv2.fillConvexPoly(lay, pts, (0, 200, 90), cv2.LINE_AA)
    vis = cv2.addWeighted(lay, a.alpha, vis, 1-a.alpha, 0)
    cv2.imwrite(a.out, cv2.resize(vis, (640, int(hh*640/ww))))
    cv2.imwrite(a.out.replace(".png", "_full.png"), vis)
    print("->", a.out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--cfg", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--work-w", type=int, default=1400); ap.add_argument("--alpha", type=float, default=0.4)
    render(ap.parse_args())
