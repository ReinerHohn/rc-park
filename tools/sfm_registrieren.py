#!/usr/bin/env python3
"""sfm_registrieren.py - ein Foto ueber HANDPICKS in ein metrisch ausgerichtetes Netz einhaengen (Register AJ).

Wann: Merkmalsmatcher (SIFT) findet keine Verbindung (Schraegluftbild gegen Strassenfotos: 0 verifizierte Matches), aber im Foto
sind Punkte gepickt, deren 3D-Lage im Netz bekannt ist (trianguliert, SFM-AUSRICHTUNG-<name>.json) oder amtlich (anker3d.json:
Eckkanten-Linien, Bodenpunkte). Dann: Kamera (Drehung 3, Lage 3; Brennweite fest aus EXIF/objekt.json, Hauptpunkt Bildmitte)
per P3P/EPnP starten und mit Punkt- und Linienresiduen verfeinern. Danach werden alle Picks, die in >= 2 Kameras des Netzes
(alte + neue) liegen, trianguliert - so kommen Punkte der verdeckten Seiten (Ost/West, Suedtuermchen) ins metrische Nordsystem.
  /media/oem/scan/venv-colmap/bin/python -I tools/sfm_registrieren.py modelle/<objekt>/objekt.json --netz nord --foto 060 [--foto 061] [--schreiben]
        [--tausch tuermchen_NE tuermchen_NW]   # Picks vertauscht testen (symmetrische Tuermchen)
Schreibt bei --schreiben: SFM-AUSRICHTUNG-<netz>.json kameras[<foto>] (registriert="picks") + trianguliert, K-<foto>.json kamera_netz_<netz>.
"""
import sys, os, json, glob, math, argparse, numpy as np, cv2
from scipy.optimize import least_squares
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sfm_ausrichten as SA

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--netz", required=True); ap.add_argument("--foto", action="append", required=True)
    ap.add_argument("--schreiben", action="store_true"); ap.add_argument("--tausch", nargs=2, action="append", default=[])
    ap.add_argument("--f-frei", action="store_true", help="Brennweite mitschaetzen (sonst fest aus EXIF/objekt.json)")
    ap.add_argument("--spiegel", action="store_true", help="ANNAHME Dachsymmetrie: triangulierte N-Punkte an x gespiegelt (NE->SE, NW->SW) als Kontrollpunkte mit sigma 1 m")
    ap.add_argument("--hoehe", nargs=2, type=float, metavar=("Z", "SIGMA"), help="Kamerahoehe ueber Gelaende als weiche Bedingung (z. B. aus Zeilengleichheit gleich hoher Punkte: Schlossberg 061)")
    a = ap.parse_args(); obj = json.load(open(a.objekt)); od = os.path.dirname(os.path.abspath(a.objekt)); root = os.path.dirname(os.path.dirname(od))
    A = json.load(open(os.path.join(od, "anker3d.json")))["anker"]; pth = os.path.join(od, "messprotokoll", f"SFM-AUSRICHTUNG-{a.netz}.json"); S = json.load(open(pth))
    kams = {nr: SA.kam_aus_json(nr, d) for nr, d in S["kameras"].items()}
    # 3D-Kontrolle: triangulierte Netzpunkte (Sigma aus Datei) + amtliche Bodenpunkte
    # Kontrolle nur aus belastbaren Netzpunkten: sigma <= 2 m und nicht selbst erst ueber eines der zu registrierenden Fotos entstanden
    ctrl = {n: (np.array(t["xyz"]), max(0.3, float(t["sigma"][2]))) for n, t in S["trianguliert"].items()
            if float(t["sigma"][2]) <= 2.0 and not (set(t.get("mit_pick_kameras", [])) & set(a.foto))}
    for n, an in A.items():
        if n.startswith("ecke_boden"): ctrl[n] = (np.array(an["xyz"]), an["sigma"])
    if a.spiegel:
        for n, t in list(S["trianguliert"].items()):
            s = n.split("_")[-1]
            if s in ("NE", "NW") and "_".join(n.split("_")[:-1] + [s.replace("N", "S")]) not in ctrl:
                m = "_".join(n.split("_")[:-1] + [s.replace("N", "S")]); ctrl[m] = (np.array(t["xyz"]) * np.array([-1, 1, 1]), 1.0); print(f"ANNAHME Symmetrie: {m} = gespiegelt {n} -> {ctrl[m][0].round(2).tolist()} (sigma 1 m)")
    Ks = {}
    for pth_k in glob.glob(os.path.join(od, "messprotokoll", "K-*.json")): Ks[os.path.basename(pth_k)[2:-5]] = json.load(open(pth_k))
    neu = {}
    for nr in a.foto:
        K = Ks[nr]; foto = glob.glob(os.path.join(root, obj["fotos_dir"], nr + "_*"))[0]; H, W = cv2.imread(foto).shape[:2]; cx, cy = W / 2, H / 2
        f0 = K.get("brennweite_px") or obj["fotos"].get(nr, {}).get("brennweite_px")
        if not f0:   # EXIF aus dem Manifest / Datei
            from PIL import Image, ExifTags; T = {v: k for k, v in ExifTags.TAGS.items()}; im = Image.open(foto); ex = im.getexif(); exi = ex.get_ifd(0x8769)
            f35 = exi.get(T["FocalLengthIn35mmFilm"]); f0 = float(f35) / 36 * max(W, H) if f35 else None
        if not f0: raise SystemExit(f"{nr}: keine Brennweite (K-json brennweite_px / objekt.json / EXIF f35)")
        f0 = float(f0)
        punkte = dict(K.get("punkte", {}))
        for x, y in a.tausch:
            if x in punkte and y in punkte: punkte[x], punkte[y] = punkte[y], punkte[x]
        P3 = [(n, ctrl[n][0], ctrl[n][1], np.array(punkte[n], float)) for n in punkte if n in ctrl]
        L3 = [(n, A[n]["xyz"][:2], np.array(pts, float)) for n, pts in K.get("linien", {}).items() if n in A]
        print(f"\nFoto {nr}: {W}x{H}, f={f0:.0f} px (fest={not a.f_frei}); Kontrollpunkte {[p[0] for p in P3]}, Linien {[l[0] for l in L3]}")
        if len(P3) < 3: print("   weniger als 3 Kontrollpunkte - keine Registrierung"); continue
        Kmat = np.array([[f0, 0, cx], [0, f0, cy], [0, 0, 1.0]]); X = np.array([p[1] for p in P3]); uv = np.array([p[3] for p in P3])
        starts = []
        if len(P3) == 3:
            ok, rv, tv = cv2.solveP3P(X.reshape(-1, 1, 3), uv.reshape(-1, 1, 2), Kmat, None, flags=cv2.SOLVEPNP_P3P)
            starts = [(r.ravel(), t.ravel()) for r, t in zip(rv, tv)]
        else:
            for flag in (cv2.SOLVEPNP_EPNP, cv2.SOLVEPNP_ITERATIVE, cv2.SOLVEPNP_SQPNP):
                try:
                    ok, r, t = cv2.solvePnP(X.reshape(-1, 1, 3), uv.reshape(-1, 1, 2), Kmat, None, flags=flag)
                    if ok: starts.append((r.ravel(), t.ravel()))
                except Exception: pass
        def resid(p, roh=False):
            rvec, tv = p[:3], p[3:6]; f = p[6] if a.f_frei else f0; R = SA.rot(rvec); r = []; info = []
            Xc = X @ R.T + tv; z = Xc[:, 2]
            n_res = 2 * len(P3) + sum(len(l[2]) for l in L3) + (1 if a.hoehe else 0)
            if z.min() < 1: return (np.full(n_res, 1e3), []) if roh else np.full(n_res, 1e3)
            q = np.c_[f * Xc[:, 0] / z + cx, f * Xc[:, 1] / z + cy]
            for i, (n, _, sig, u) in enumerate(P3):
                w = 1 / math.sqrt(9 + (sig * f / z[i]) ** 2); d = q[i] - u; r += list(d * w); info.append((n, float(np.linalg.norm(d))))
            for n, (x, y), pts in L3:
                Lw = np.array([[x, y, -0.3], [x, y, SA.Z_KANTE_OBEN]]) @ R.T + tv; l2 = np.c_[f * Lw[:, 0] / Lw[:, 2] + cx, f * Lw[:, 1] / Lw[:, 2] + cy]
                v = l2[1] - l2[0]; nv = np.array([-v[1], v[0]]) / np.linalg.norm(v); d = (pts - l2[0]) @ nv; r += list(d / 3.0); info.append((n + " (Linie)", float(np.sqrt(np.mean(d ** 2)))))
            if a.hoehe: C = -R.T @ tv; r.append((C[2] - a.hoehe[0]) / a.hoehe[1])
            return (np.array(r), info) if roh else np.array(r)
        # weitere Starts: fruehere Registrierung (K-json) und ein Ring moeglicher Standorte (Azimut x Abstand x Hoehe), Blick auf die Turmmitte
        alt = K.get(f"kamera_netz_{a.netz}")
        if alt: starts.append((cv2.Rodrigues(np.array(alt["R"]))[0].ravel(), np.array(alt["t"])))
        ziel = np.array([0.0, 0.0, 30.0])
        for az in range(0, 360, 45):
            for dist in (30.0, 100.0, 300.0, 900.0):
                for hz in (2.0, 50.0, 400.0):
                    C = np.array([dist * math.cos(math.radians(az)), dist * math.sin(math.radians(az)), hz]); fw = ziel - C; fw /= np.linalg.norm(fw)
                    rt = np.cross(fw, [0, 0, 1.0]); rt /= np.linalg.norm(rt); dn = np.cross(fw, rt); R0 = np.vstack([rt, dn, fw])
                    starts.append((cv2.Rodrigues(R0)[0].ravel(), -R0 @ C))
        best = None
        for rv, tv in starts:
            p0 = np.r_[rv, tv, [f0] if a.f_frei else []]
            try: sol = least_squares(resid, p0, method="lm" if len(resid(p0)) >= len(p0) else "trf")
            except Exception as e: print("   Start verworfen:", e); continue
            if best is None or sol.cost < best.cost: best = sol
        if best is None: print("   keine Loesung"); continue
        r, info = resid(best.x, roh=True); R = SA.rot(best.x[:3]); t = best.x[3:6]; C = -R.T @ t; f = best.x[6] if a.f_frei else f0
        rms = float(np.sqrt(np.mean([v ** 2 for _, v in info])))
        if rms > 0.05 * H: print(f"   KEINE brauchbare Loesung (RMS {rms:.0f} px = {100 * rms / H:.1f} % der Bildhoehe) - nicht uebernommen"); continue
        print(f"   Standort {C.round(1).tolist()} (Abstand {np.hypot(C[0], C[1]):.0f} m, Hoehe {C[2]:.1f} m), f={f:.0f}; Residuen: " + ", ".join(f"{n}:{v:.0f}" for n, v in info) + f"  RMS {rms:.0f} px = {100 * rms / H:.2f} % der Bildhoehe")
        km = SA.Kam.__new__(SA.Kam); km.name = nr; km.R = R; km.t = t; km.fx = km.fy = f; km.cx, km.cy = cx, cy; km.k = []; km.fak = 1.0; km.off = (0.0, 0.0); km.W, km.H = W, H
        neu[nr] = dict(kam=km, rms=rms, info=info, f=f, punkte=punkte)
    if not neu: sys.exit(1)
    # Triangulation ueber alle Kameras des Netzes + neue
    alle = dict(kams); alle.update({nr: d["kam"] for nr, d in neu.items()})
    sammel = {}
    for nr, K in Ks.items():
        if nr not in alle: continue
        pk = neu[nr]["punkte"] if nr in neu else K.get("punkte", {})
        for n, uv in pk.items():
            if n.startswith("ecke_boden"): continue
            sammel.setdefault(n, []).append((alle[nr], alle[nr].bild(uv), nr))
    print("\nTriangulation (Netz " + a.netz + " + neue Kameras):"); tri = dict(S.get("trianguliert", {}))
    for n, lst in sorted(sammel.items()):
        if len(lst) < 2 or not any(nr in neu for _, _, nr in lst): continue
        X, sx, px = SA.triangulieren(alle, [(k, uv) for k, uv, _ in lst]); alt = S.get("trianguliert", {}).get(n)
        print(f"   {n:16s} x {X[0]:6.2f} y {X[1]:6.2f} z {X[2]:6.2f} +- {sx[2]:.2f}  Fotos {[nr for _, _, nr in lst]} Residuen {[round(v) for v in px]} px" + (f"   (vorher z {alt['xyz'][2]:.2f} aus {alt['fotos']})" if alt else "   NEU"))
        tri[n] = dict(xyz=X.round(2).tolist(), sigma=sx.round(2).tolist(), fotos=[nr for _, _, nr in lst], residuen_px=[round(v, 1) for v in px], anker_start=A.get(n, {}).get("xyz", [None] * 3), mit_pick_kameras=[nr for _, _, nr in lst if nr in neu])
    if a.schreiben:
        for nr, d in neu.items():
            km = d["kam"]; S["kameras"][nr] = dict(standort=km.zentrum().round(2).tolist(), f_px_original=float(km.fx), fak=1.0, off=[0.0, 0.0], R=km.R.tolist(), t=km.t.tolist(), cx=km.cx, cy=km.cy, k=[],
                                                   registriert="picks", rms_px=round(d["rms"], 1), residuen={n: round(v, 1) for n, v in d["info"]})
            Ks[nr][f"kamera_netz_{a.netz}"] = S["kameras"][nr]; json.dump(Ks[nr], open(os.path.join(od, "messprotokoll", f"K-{nr}.json"), "w"), indent=1, ensure_ascii=False)
        S["trianguliert"] = tri; json.dump(S, open(pth, "w"), indent=1, ensure_ascii=False); print("\ngeschrieben:", pth, "und K-<foto>.json")

if __name__ == "__main__":
    main()
