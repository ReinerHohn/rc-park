#!/usr/bin/env python3
"""foto_skyline_orient.py — GENERISCH & automatisch: die wahre Kamera-Orientierung (Blickrichtung
+ Pitch) aus dem Abgleich der Foto-SKYLINE mit dem aus dem DEM gerenderten Horizont bestimmen —
unabhängig vom (oft ungenauen) Handy-Kompass. Struktur-agnostisch: braucht nur ein Foto mit
Himmel-Horizont + ein DEM + die Kamera-Position (UTM).

Pipeline:
  1. Foto-Skyline: Himmel-Maske (blau/hell) → unterste Himmel-Zeile je Spalte → Elevation-über-Azimut.
  2. DEM-Horizont: von der Kamera-Position je Azimut Strahl übers DEM → max. Elevationswinkel.
  3. Match: (dYaw, dPitch) robust (Median-|Δ|) finden → wahre Blickrichtung.

WICHTIG (hart gelernt): Der GPS-STANDORT koppelt mit der Orientierung. Ist die Position ungenau
(Handy ±5–10 m), schiebt der Match einen Teil in den Yaw. Für eine konsistente Pose Position
UND Orientierung GEMEINSAM lösen (oder Mehrbild/COLMAP). Skyline allein fixt die Orientierung
nur, wenn die Position stimmt.
"""
import argparse, json, math, numpy as np, cv2


def photo_skyline(img, f_cyl, proj="cylindrical"):
    hh, ww = img.shape[:2]
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV); H, S, V = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    sky = ((H > 95) & (H < 140) & (S > 40) & (V > 110)).astype(np.uint8)
    sl = np.full(ww, np.nan)
    for c in range(ww):
        rows = np.where(sky[:, c] > 0)[0]
        if len(rows) and rows.min() < hh*0.5:
            sl[c] = rows.max()
    cx, cy = ww/2, hh/2
    az = (np.arange(ww)-cx)/f_cyl*180/math.pi                  # rel. zur Blickmitte
    el = (cy-sl)/f_cyl*180/math.pi
    return az, el


def dem_horizon(alt_fn, camE, camN, camAlt, az_abs, dmax=1500, step=4):
    A = math.radians(az_abs); best = -90
    for d in range(15, dmax, step):
        z = alt_fn(camE+d*math.sin(A), camN+d*math.cos(A))
        if np.isnan(z): break
        best = max(best, math.degrees(math.atan2(z-camAlt, d)))
    return best


def match(az, el, alt_fn, camE, camN, camAlt, yaw0, span=45, yaw_rng=25):
    good = np.isfinite(el) & (np.abs(az) < span)
    azv, elv = az[good], el[good]
    best = None
    for dyaw in np.arange(-yaw_rng, yaw_rng+0.1, 1.0):
        demv = np.array([dem_horizon(alt_fn, camE, camN, camAlt, yaw0+dyaw+a) for a in azv])
        d = elv-demv; off = np.median(d)
        cost = float(np.median(np.abs(d-off)))
        if best is None or cost < best[0]:
            best = (cost, dyaw, off)
    return best                                                # (resid, dYaw, dPitch)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--foto", required=True)
    ap.add_argument("--dem", required=True, help="DEM .npy")
    ap.add_argument("--dem-originE", type=float, required=True)
    ap.add_argument("--dem-originN", type=float, required=True, help="N der TOP-Zeile (row0=Nord)")
    ap.add_argument("--camE", type=float, required=True); ap.add_argument("--camN", type=float, required=True)
    ap.add_argument("--eye", type=float, default=1.6, help="Augenhöhe über DEM-Boden (m)")
    ap.add_argument("--yaw0", type=float, required=True, help="Kompass-Startwert (Grad)")
    ap.add_argument("--f-mm", type=float, required=True); ap.add_argument("--sensor-mm", type=float, required=True)
    ap.add_argument("--frame-px", type=float, required=True, help="Einzelbild-Pixelbreite (für f_cyl)")
    ap.add_argument("--work-w", type=int, default=1600); ap.add_argument("--plot", default="")
    a = ap.parse_args()
    dgm = np.load(a.dem)
    def alt_fn(E, N):
        c = int(round(E-a.dem_originE)); r = int(round(a.dem_originN-N))
        return float(dgm[r, c]) if (0 <= r < dgm.shape[0] and 0 <= c < dgm.shape[1]) else np.nan
    camAlt = alt_fn(a.camE, a.camN)+a.eye
    img0 = cv2.imread(a.foto); H0, W0 = img0.shape[:2]
    ww = a.work_w; img = cv2.resize(img0, (ww, int(H0*ww/W0)))
    f_cyl = a.f_mm/a.sensor_mm*a.frame_px*ww/W0
    az, el = photo_skyline(img, f_cyl)
    resid, dyaw, dpitch = match(az, el, alt_fn, a.camE, a.camN, camAlt, a.yaw0)
    print(f"camAlt(DEM+eye)={camAlt:.1f} m  Skyline-gültig {100*np.isfinite(el).mean():.0f}%")
    print(f"Kompass-Korrektur {dyaw:+.1f}°  Pitch {dpitch:+.1f}°  Rest-|Δ| {resid:.2f}°")
    print(f"→ wahre Blickrichtung {(a.yaw0+dyaw)%360:.1f}°  (Kompass sagte {a.yaw0}°)")
    print(json.dumps({"yaw_true": (a.yaw0+dyaw) % 360, "dpitch": dpitch, "resid": resid}))
    if a.plot:
        import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
        grid = np.linspace(-45, 45, 181)
        dem = np.array([dem_horizon(alt_fn, a.camE, a.camN, camAlt, a.yaw0+dyaw+g) for g in grid])
        fig, ax = plt.subplots(figsize=(11, 3))
        ax.plot(az, el-dpitch, '.', ms=1, label="Foto-Skyline (korrigiert)")
        ax.plot(grid, dem, '-', lw=1.5, label="DEM-Horizont")
        ax.set_xlim(-45, 45); ax.grid(alpha=.3); ax.legend()
        ax.set_xlabel("Azimut rel. Blickrichtung [°]"); ax.set_ylabel("Elevation [°]")
        fig.tight_layout(); fig.savefig(a.plot, dpi=110); print("Plot ->", a.plot)


if __name__ == "__main__":
    main()
