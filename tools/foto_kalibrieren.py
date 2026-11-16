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
import sys, os, json, glob, math, numpy as np, cv2, trimesh
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scipy.optimize import least_squares

def projiziere(X, rvec, t, f, cx, cy):
    R, _ = cv2.Rodrigues(rvec); Xc = X @ R.T + t
    return np.c_[f * Xc[:, 0] / Xc[:, 2] + cx, f * Xc[:, 1] / Xc[:, 2] + cy], Xc[:, 2]

def silhouette_setup(im, root):
    """Foto-Silhouettenkante gegen den Himmel + Distanztransformation. Nur dieser Teil der Kontur ist zuverlaessig
    (unten stehen Nachbarhaeuser). Rueckgabe: DT (Pixelabstand zur naechsten Himmelkante), Himmelsmaske."""
    import sys as _s; _s.path.insert(0, os.path.join(root, "tools")); import foto_pick as FP
    sk = FP.himmel(im); kante = cv2.Canny(sk.astype(np.uint8) * 255, 50, 150) > 0
    dt = cv2.distanceTransform((~kante).astype(np.uint8), cv2.DIST_L2, 3)
    return dt, sk

def silhouetten_punkte3d(P3d, rvec, t, f, cx, cy, W, H, sk, n=500):
    """3D-Punkte, die bei DIESER Lage auf dem Silhouettenrand gegen Himmel liegen. Sie werden FESTGEHALTEN und in der Optimierung
    kontinuierlich projiziert - eine gerasterte Kante waere stueckweise konstant (numerischer Gradient null, nichts bewegt sich)."""
    uv, z = projiziere(P3d, rvec, t, f, cx, cy); ok = (z > 1) & (uv[:, 0] >= 0) & (uv[:, 0] < W) & (uv[:, 1] >= 0) & (uv[:, 1] < H)
    if ok.sum() < 1000: return None
    u = uv[ok, 0].astype(int); v = uv[ok, 1].astype(int); idx = np.nonzero(ok)[0]
    import render_kern as RK
    R3, _ = cv2.Rodrigues(np.asarray(rvec, float))
    M = RK.maske(P3d, R3, t, f, cx, cy, W, H, schliessen=7).astype(np.uint8)
    rand = cv2.dilate((cv2.Canny(M * 255, 50, 150) > 0).astype(np.uint8), np.ones((3, 3), np.uint8)) > 0
    nah = cv2.dilate(sk.astype(np.uint8), np.ones((21, 21), np.uint8)) > 0
    auf = rand[v, u] & nah[v, u]
    if auf.sum() < 50: return None
    w = idx[auf]; return P3d[w[np.linspace(0, len(w) - 1, min(n, len(w))).astype(int)]]

def dt_wert(dt, uv):
    """Bilinear interpolierter Abstand zur Fotokante - stetig in den Kameraparametern."""
    H, W = dt.shape; x = np.clip(uv[:, 0], 0, W - 1.001); y = np.clip(uv[:, 1], 0, H - 1.001)
    x0 = x.astype(int); y0 = y.astype(int); fx = x - x0; fy = y - y0
    return ((dt[y0, x0] * (1 - fx) + dt[y0, x0 + 1] * fx) * (1 - fy) + (dt[y0 + 1, x0] * (1 - fx) + dt[y0 + 1, x0 + 1] * fx) * fy)

AUGENHOEHE = 1.7      # Standard-Augenhoehe fuer Strassenfotos; je Objekt in objekt.json ueberschreibbar
ERLAUBT = {"--silhouette", "--sil-gewicht", "--stl"}

def main():
    objp, nr = sys.argv[1], sys.argv[2]
    unbekannt = [x for x in sys.argv[3:] if x.startswith("--") and x not in ERLAUBT]
    if unbekannt: raise SystemExit(f"unbekannte Option(en): {unbekannt}; erlaubt: {sorted(ERLAUBT)}")
    print(f"  Optionen erkannt: {[x for x in sys.argv[3:] if x.startswith('--')] or 'keine'}")
    a = sys.argv[1:]                                     # Optionsliste (eigener Name; 'a' wurde unten von der Ankerschleife ueberschrieben)
    global AUGENHOEHE
    obj = json.load(open(objp)); AUGENHOEHE = float(obj.get("augenhoehe_m", 1.7)); root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(objp))))
    od = os.path.join(root, os.path.dirname(obj["masstabelle"])); A = json.load(open(os.path.join(od, "anker3d.json")))["anker"]
    kp = os.path.join(od, "messprotokoll", f"K-{nr}.json"); K = json.load(open(kp))
    fn = glob.glob(os.path.join(root, obj["fotos_dir"], nr + "_*"))[0]; im = cv2.imread(fn); H, W = im.shape[:2]; cx, cy = W / 2, H / 2
    # Modellrahmen (x Sued, y Ost, z oben) -> Kamerarahmen-Konvention von OpenCV (x rechts, y unten, z vorwaerts) uebernimmt die Drehung
    P3, P2, S, namen = [], [], [], []
    for name, uv in K["punkte"].items():
        if name not in A: print(f"  Pick '{name}' hat keinen Anker in anker3d.json - uebersprungen"); continue
        ank = A[name]; P3.append(ank["xyz"]); P2.append(uv); S.append(ank["sigma"]); namen.append(name)   # NICHT 'a' - das ist sys.argv (Namenskonflikt machte alle Optionen wirkungslos, 2026-11-01)
    P3, P2, S = np.array(P3, float), np.array(P2, float), np.array(S, float)
    lines = [(np.array(A[n]["xyz"][:2], float), np.array(pts, float)) for n, pts in K.get("linien", {}).items()]
    if len(P3) == 0:                                                     # Exit 3 = uebersprungen (keine Daten), kein Absturz (Nullstart 5-9: ValueError bei 044/062)
        print(f"  Foto {nr}: keine Picks mit Anker in anker3d.json ({len(K.get('punkte', {}))} Punkte, {len(lines)} Linien) - keine Kalibrierung moeglich"); sys.exit(3)
    fexif = K.get("brennweite_px")
    if K.get("brennweite_frei"):                                            # Bild beschnitten/skaliert: EXIF-Brennweite in px ungueltig -> Brennweite mitschaetzen
        print(f"  Brennweite FREI ({K.get('brennweite_frei_grund', 'brennweite_frei gesetzt')}); EXIF {fexif} px nur Startwert-Hinweis"); fexif = None

    def gewichte(p, fix_f=None):
        """Sigma der Anker (m) -> Pixel, EINMAL je Start eingefroren (sonst 'kauft' sich der Loeser mit grosser Brennweite kleine Residuen)."""
        rvec, t = p[:3], p[3:6]; f = fix_f if fix_f else p[6]; _, z = projiziere(P3, rvec, t, f, cx, cy)
        return 1.0 / np.sqrt(16.0 + (S * f / np.maximum(z, 1.0)) ** 2)
    sil = "--silhouette" in a
    if sil:
        dt, sk = silhouette_setup(im, root)
        mm = trimesh.load(os.path.join(root, obj["stl"]))
        if obj.get("stl_einheit_mm", True): mm.apply_scale(obj.get("stl_massstab", 87) / 1000.0)
        cc = mm.bounds.mean(0) if obj.get("zentrierung", "huelle") == "huelle" else np.zeros(3)
        mm.apply_translation([-cc[0], -cc[1], -mm.bounds[0, 2]]); P3d, _ = trimesh.sample.sample_surface(mm, 400000, seed=0); P3d = np.asarray(P3d)
        gew_sil = float(a[a.index("--sil-gewicht") + 1]) if "--sil-gewicht" in a else 1.0
    SILP = [None]
    def resid(p, fix_f=None, w=None):
        rvec, t = p[:3], p[3:6]; f = fix_f if fix_f else p[6]
        uv, z = projiziere(P3, rvec, t, f, cx, cy); w = w if w is not None else gewichte(p, fix_f); r = ((uv - P2) * w[:, None]).ravel()
        for xy, pts in lines:                                                   # Kantenpunkte: nur Querabstand zur projizierten Senkrechten
            L3 = np.array([[xy[0], xy[1], 0.0], [xy[0], xy[1], 40.0]]); l2, _ = projiziere(L3, rvec, t, f, cx, cy); d = l2[1] - l2[0]; n = np.array([-d[1], d[0]]) / np.linalg.norm(d)
            r = np.r_[r, ((pts - l2[0]) @ n) / 3.0]
        if K.get("strassenfoto"):                                              # Strassenfoto: Augenhoehe 1,7 +- 0,5 m als weiche Bedingung
            R, _ = cv2.Rodrigues(rvec); camz = float((-R.T @ t)[2]); r = np.r_[r, (camz - AUGENHOEHE) / 0.5 * 3.0]
        if sil and SILP[0] is not None:                                     # Silhouettenterm: feste 3D-Randpunkte auf die Fotokante ziehen
            uvs, zs = projiziere(SILP[0], rvec, t, f, cx, cy)
            d = dt_wert(dt, uvs); d[zs < 1] = 150.0
            r = np.r_[r, gew_sil * np.sqrt(np.minimum(d, 150.0))]
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
                    cam = np.array([dist * math.cos(az), dist * math.sin(az), AUGENHOEHE]); rv, tv = look_at(cam, np.array([0, 0, float(zt)]))
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
    if sil and best is not None:                                            # ICP-artig: Randpunkte bei der aktuellen Lage neu bestimmen und nachoptimieren
        for runde in range(3):
            pb = best[1]; rv_, t_ = pb[:3], pb[3:6]; f_ = fexif or pb[6]
            SILP[0] = silhouetten_punkte3d(P3d, rv_, t_, f_, cx, cy, W, H, sk)
            if SILP[0] is None: print("  Silhouette: keine Randpunkte gegen Himmel"); break
            w = gewichte(pb, fexif)
            sol = least_squares(lambda p: resid(p, fexif, w), pb, method="trf", x_scale="jac", max_nfev=6000)
            uvs, _ = projiziere(SILP[0], sol.x[:3], sol.x[3:6], fexif or sol.x[6], cx, cy)
            print(f"  Silhouette Runde {runde + 1}: {len(SILP[0])} Randpunkte, mittlerer Kantenabstand {dt_wert(dt, uvs).mean():.1f} px")
            best = (float(np.sum(sol.fun ** 2)), sol.x, best[2])
    cost, p, f0 = best; rvec, t = p[:3], p[3:6]; f = fexif or p[6]
    R, _ = cv2.Rodrigues(rvec); cam = (-R.T @ t); uv, z = projiziere(P3, rvec, t, f, cx, cy); res = np.linalg.norm(uv - P2, axis=1)
    dres = {n: [int(round(float(x))) for x in (uv[i] - P2[i])] for i, n in enumerate(namen)}
    out = dict(silhouette_genutzt=bool(sil), residuen_du_dv=dres, rvec=rvec.tolist(), t=t.tolist(), f_px=float(f), cx=cx, cy=cy, bild=[W, H], standort_xyz=cam.round(2).tolist(), hoehe_ueber_gelaende=round(float(cam[2]), 2),
               abstand_zur_achse=round(float(math.hypot(cam[0], cam[1])), 1), residuen_px={n: round(float(r), 1) for n, r in zip(namen, res)},
               rms_px=round(float(np.sqrt(np.mean(res ** 2))), 1), plausibel_strassenfoto=bool(1.0 <= cam[2] <= 3.0), brennweite_quelle="EXIF" if fexif else "geloest")
    import kamera_plausibel as KP; ok_p, grund_p = KP.plausibel(float(f), (W, H), cam, max_m=3000)
    if not ok_p: print(f"K-{nr}: Loesung UNPLAUSIBEL ({grund_p}), rms {out['rms_px']} px - NICHT gespeichert (Punkte liegen zu flach oder sind falsch gepickt; Brennweite vorgeben)"); sys.exit(3)
    K["kamera"] = out
    K["kalibrier_optionen"] = [x for i_, x in enumerate(sys.argv[3:]) if x.startswith("--") or (i_ > 0 and sys.argv[3:][i_ - 1] == "--sil-gewicht")]   # Eingabe fuer den Nullstart: gleiche Loesung reproduzierbar (Register CK)
    __import__("json_sicher").schreiben(kp, K)
    print(f"K-{nr}: f={f:.0f} px ({f / H * 24:.1f} mm bei 24-mm-Bildhoehe), Standort {out['standort_xyz']} -> Hoehe {out['hoehe_ueber_gelaende']} m ueber Gelaende, Abstand {out['abstand_zur_achse']} m")
    print("  Residuen px:", out["residuen_px"], "| RMS", out["rms_px"], "| plausibel:", out["plausibel_strassenfoto"])
    print("  signiert (du, dv; dv>0 = Modellpunkt liegt im Bild TIEFER als Pick):", dres)

if __name__ == "__main__":
    main()
