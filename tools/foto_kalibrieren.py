#!/usr/bin/env python3
"""foto_kalibrieren.py - Kamera eines Fotos gegen AMTLICHE 3D-Punkte loesen (LoD2-Ecken, DOM1-Spitzen, Dokumenthoehe) -> echte Meter aus dem Foto.

Eingabe: modelle/<objekt>/anker3d.json (3D-Anker im Modellrahmen, mit sigma) und ein Pick-Protokoll modelle/<objekt>/messprotokoll/K-<foto>.json:
  {"punkte": {"ecke_boden_2": [u, v], "tuermchen_dom_0": [u, v], ...},            # Pixel im Vollbild
   "linien": {"ecke_boden_2": [[u1, v1], [u2, v2]]},                                 # Punkte AUF der senkrechten Kante durch diesen Anker (z frei)
   "brennweite_px": 2248 (optional, aus EXIF), "notiz": "..."}
Unbekannte: Drehung (3), Lage (3), Brennweite (1; Hauptpunkt = Bildmitte, keine Verzeichnung). Loesung: Startwerte per EPnP ueber mehrere f,
dann gewichtete kleinste Quadrate (scipy). Ausgabe: K-<foto>.json um "kamera" ergaenzt (R, t, f, Standort, Hoehe ueber Gelaende, Residuen).
Plausibilitaet: Strassenfotos haben Kamerahoehe 1,2-2,5 m; RMS-Residuum < ~0,5 % der Bildhoehe.
  /media/oem/scan/venv-seg/bin/python -W ignore -I tools/foto_kalibrieren.py modelle/<objekt>/objekt.json <foto-nr>
"""
import sys, os, json, glob, math, numpy as np, cv2
from scipy.optimize import least_squares

def projiziere(X, rvec, t, f, cx, cy):
    R, _ = cv2.Rodrigues(rvec); Xc = X @ R.T + t
    return np.c_[f * Xc[:, 0] / Xc[:, 2] + cx, f * Xc[:, 1] / Xc[:, 2] + cy], Xc[:, 2]

def main():
    objp, nr = sys.argv[1], sys.argv[2]; obj = json.load(open(objp)); root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(objp))))
    od = os.path.join(root, os.path.dirname(obj["masstabelle"])); A = json.load(open(os.path.join(od, "anker3d.json")))["anker"]
    kp = os.path.join(od, "messprotokoll", f"K-{nr}.json"); K = json.load(open(kp))
    fn = glob.glob(os.path.join(root, obj["fotos_dir"], nr + "_*"))[0]; H, W = cv2.imread(fn).shape[:2]; cx, cy = W / 2, H / 2
    # Modellrahmen (x Sued, y Ost, z oben) -> Kamerarahmen-Konvention von OpenCV (x rechts, y unten, z vorwaerts) uebernimmt die Drehung
    P3, P2, S = [], [], []
    for name, uv in K["punkte"].items():
        a = A[name]; P3.append(a["xyz"]); P2.append(uv); S.append(a["sigma"])
    P3, P2, S = np.array(P3, float), np.array(P2, float), np.array(S, float)
    lines = [(np.array(A[n]["xyz"][:2], float), np.array(pts, float)) for n, pts in K.get("linien", {}).items()]
    fexif = K.get("brennweite_px")

    def gewichte(p, fix_f=None):
        """Sigma der Anker (m) -> Pixel, EINMAL je Start eingefroren (sonst 'kauft' sich der Loeser mit grosser Brennweite kleine Residuen)."""
        rvec, t = p[:3], p[3:6]; f = fix_f if fix_f else p[6]; _, z = projiziere(P3, rvec, t, f, cx, cy)
        return 1.0 / np.sqrt(16.0 + (S * f / np.maximum(z, 1.0)) ** 2)
    def resid(p, fix_f=None, w=None):
        rvec, t = p[:3], p[3:6]; f = fix_f if fix_f else p[6]
        uv, z = projiziere(P3, rvec, t, f, cx, cy); w = w if w is not None else gewichte(p, fix_f); r = ((uv - P2) * w[:, None]).ravel()
        for xy, pts in lines:                                                   # Kantenpunkte: nur Querabstand zur projizierten Senkrechten
            L3 = np.array([[xy[0], xy[1], 0.0], [xy[0], xy[1], 40.0]]); l2, _ = projiziere(L3, rvec, t, f, cx, cy); d = l2[1] - l2[0]; n = np.array([-d[1], d[0]]) / np.linalg.norm(d)
            r = np.r_[r, ((pts - l2[0]) @ n) / 3.0]
        if K.get("strassenfoto"):                                              # Strassenfoto: Augenhoehe 1,7 +- 0,5 m als weiche Bedingung
            R, _ = cv2.Rodrigues(rvec); camz = float((-R.T @ t)[2]); r = np.r_[r, (camz - 1.7) / 0.5 * 3.0]
        if z.min() < 1: r = r * 1e3
        return r

    def look_at(cam, tgt):
        fw = tgt - cam; fw /= np.linalg.norm(fw); rt = np.cross(fw, [0, 0, 1.0]); rt /= np.linalg.norm(rt); dn = np.cross(fw, rt)
        R = np.vstack([rt, dn, fw]); rvec, _ = cv2.Rodrigues(R); return rvec.ravel(), -R @ cam
    best = None; fs = [fexif] if fexif else [0.3 * H, 0.4 * H, 0.5 * H, 0.65 * H, 0.85 * H, 1.1 * H, 1.5 * H, 2.0 * H]
    seite = K.get("seite", obj.get("fotos", {}).get(nr, {}).get("seite")); az0 = {"Sued": 0.0, "Nord": math.pi, "Ost": math.pi / 2, "West": -math.pi / 2}.get(seite, None)
    starts = []
    for f0 in fs:                                                          # Startwerte: EPnP (>= 4 Punkte) UND Rasterstart auf der Fotoseite (auch bei 3 Punkten)
        if len(P3) >= 4:
            Kc = np.array([[f0, 0, cx], [0, f0, cy], [0, 0, 1]], float)
            ok, rvec, tvec = cv2.solvePnP(P3.reshape(-1, 1, 3), P2.reshape(-1, 1, 2), Kc, None, flags=cv2.SOLVEPNP_EPNP)
            if ok: starts.append(np.r_[rvec.ravel(), tvec.ravel(), f0])
        azs = [az0 + d for d in np.radians([-40, -20, 0, 20, 40])] if az0 is not None else list(np.radians(range(0, 360, 30)))
        for az in azs:
            for dist in (12, 20, 32, 50, 80):
                for zt in (12, 25, 40):
                    cam = np.array([dist * math.cos(az), dist * math.sin(az), 1.7]); rv, tv = look_at(cam, np.array([0, 0, float(zt)]))
                    starts.append(np.r_[rv, tv, f0])
    if len(P3) >= 4 and not fexif:                                        # Brennweiten-Scan: je f PnP (EPnP + iterativ), bestes f als Start
        for f0 in np.linspace(0.25 * H, 2.5 * H, 46):
            Kc = np.array([[f0, 0, cx], [0, f0, cy], [0, 0, 1]], float)
            ok, rvec, tvec = cv2.solvePnP(P3.reshape(-1, 1, 3), P2.reshape(-1, 1, 2), Kc, None, flags=cv2.SOLVEPNP_EPNP)
            if ok:
                ok, rvec, tvec = cv2.solvePnP(P3.reshape(-1, 1, 3), P2.reshape(-1, 1, 2), Kc, None, rvec, tvec, True, flags=cv2.SOLVEPNP_ITERATIVE)
                starts.append(np.r_[rvec.ravel(), tvec.ravel(), f0])
    scored = sorted(starts, key=lambda p: float(np.sum(resid(p, fexif) ** 2)))[:12]
    for p0 in scored:
        try:
            w = gewichte(p0, fexif); sol = least_squares(lambda p: resid(p, fexif, w), p0[:6] if fexif else p0, method="trf", max_nfev=4000, x_scale="jac")
            w = gewichte(sol.x, fexif); sol = least_squares(lambda p: resid(p, fexif, w), sol.x, method="trf", max_nfev=4000, x_scale="jac")   # zweite Runde mit Gewichten der Loesung
        except Exception: continue
        cost = float(np.sum(sol.fun ** 2))
        if best is None or cost < best[0]: best = (cost, sol.x, p0[6])
    cost, p, f0 = best; rvec, t = p[:3], p[3:6]; f = fexif or p[6]
    R, _ = cv2.Rodrigues(rvec); cam = (-R.T @ t); uv, z = projiziere(P3, rvec, t, f, cx, cy); res = np.linalg.norm(uv - P2, axis=1)
    dres = {n: [int(round(float(x))) for x in (uv[i] - P2[i])] for i, n in enumerate(K["punkte"])}
    out = dict(residuen_du_dv=dres, rvec=rvec.tolist(), t=t.tolist(), f_px=float(f), cx=cx, cy=cy, bild=[W, H], standort_xyz=cam.round(2).tolist(), hoehe_ueber_gelaende=round(float(cam[2]), 2),
               abstand_zur_achse=round(float(math.hypot(cam[0], cam[1])), 1), residuen_px={n: round(float(r), 1) for n, r in zip(K["punkte"], res)},
               rms_px=round(float(np.sqrt(np.mean(res ** 2))), 1), plausibel_strassenfoto=bool(1.0 <= cam[2] <= 3.0), brennweite_quelle="EXIF" if fexif else "geloest")
    K["kamera"] = out; json.dump(K, open(kp, "w"), indent=1, ensure_ascii=False)
    print(f"K-{nr}: f={f:.0f} px ({f / H * 24:.1f} mm bei 24-mm-Bildhoehe), Standort {out['standort_xyz']} -> Hoehe {out['hoehe_ueber_gelaende']} m ueber Gelaende, Abstand {out['abstand_zur_achse']} m")
    print("  Residuen px:", out["residuen_px"], "| RMS", out["rms_px"], "| plausibel:", out["plausibel_strassenfoto"])
    print("  signiert (du, dv; dv>0 = Modellpunkt liegt im Bild TIEFER als Pick):", dres)

if __name__ == "__main__":
    main()
