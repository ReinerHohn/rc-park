#!/usr/bin/env python3
"""test_flaeche_ortho.py - synthetische Pruefung von flaeche_ortho.py (18.11.2026): Zylinder, Kegel und n-Eck-Erker mit BEKANNTER Textur werden von Kameras ringsum analytisch
gerendert, das Werkzeug entzerrt sie, Vergleich mit der bekannten Textur an den Rasterzellen (mittlerer/p90-Fehler in Graustufen, Anteil Zellen mit >= 3 Fotos).
Aufruf: python3 tools/test_flaeche_ortho.py  (rc 0 = alles bestanden). Kein echtes Objekt noetig."""
import os, sys, json, math, tempfile, shutil
import numpy as np, cv2
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pfade import temp_ordner                                         # 22.11.2026: Temp nicht auf Root, beim Ende aufgeraeumt (auch nach assert)
import flaeche_ortho as FO

W, H, F_PX = 800, 600, 700.0


def kamera(C, ziel):
    C = np.asarray(C, float); f = np.asarray(ziel, float) - C; f /= np.linalg.norm(f); r = np.cross(f, [0, 0, 1.0]); r /= np.linalg.norm(r); d = np.cross(f, r)
    R = np.vstack([r, d, f]); return R, -R @ C


def strahlen(R, C):
    xs, ys = np.meshgrid(np.arange(W) + 0.5, np.arange(H) + 0.5); dc = np.c_[(xs.ravel() - W / 2) / F_PX, (ys.ravel() - H / 2) / F_PX, np.ones(W * H)]
    d = dc @ R; return np.broadcast_to(C, d.shape), d / np.linalg.norm(d, axis=1, keepdims=True)


def tex_rund(phi, z):
    """bekannte Textur auf Rotationsflaechen, periodisch in phi (ganzzahlige Frequenzen)"""
    b = 128 + 70 * np.sin(7 * phi + 0.5) * np.cos(2 * np.pi * z / 0.53); g = 128 + 60 * np.sin(5 * phi + 2 * np.pi * z / 0.43)
    r = 100 + 100 * (((np.floor(phi * 12 / (2 * np.pi)) + np.floor(z / 0.25)) % 2) == 0); return np.stack([b, g, r], -1)


def tex_eben(u, z):
    b = 128 + 70 * np.sin(2 * np.pi * u / 0.37 + 0.5) * np.cos(2 * np.pi * z / 0.53); g = 128 + 60 * np.sin(2 * np.pi * (u / 0.61 + z / 0.43))
    r = 100 + 100 * (((np.floor(u / 0.25) + np.floor(z / 0.25)) % 2) == 0); return np.stack([b, g, r], -1)


def render_rotation(R, C, r0, k, z0, z1):
    o, d = strahlen(R, C); ox, oy, oz = o[:, 0], o[:, 1], o[:, 2]; dx, dy, dz = d[:, 0], d[:, 1], d[:, 2]; rz0 = r0 - k * z0        # r(z) = rz0 + k z
    a = dx * dx + dy * dy - (k * dz) ** 2; b = 2 * (ox * dx + oy * dy - k * dz * (rz0 + k * oz)); c = ox * ox + oy * oy - (rz0 + k * oz) ** 2
    disc = b * b - 4 * a * c; img = np.zeros((H * W, 3)); gt_ok = np.zeros(H * W, bool)
    with np.errstate(all="ignore"):
        sq = np.sqrt(np.maximum(disc, 0)); t1 = (-b - sq) / (2 * a); t2 = (-b + sq) / (2 * a); best = np.full(H * W, np.inf)
        for t in (t1, t2):
            z = oz + t * dz; rad = rz0 + k * z; ok = (disc > 0) & (t > 0) & (z >= z0) & (z <= z1) & (rad > 0) & (t < best); best = np.where(ok, t, best)
    hit = np.isfinite(best); X = o[hit] + best[hit, None] * d[hit]; phi = np.mod(np.arctan2(X[:, 1], X[:, 0]), 2 * np.pi); img[hit] = tex_rund(phi, X[:, 2])
    return np.clip(img, 0, 255).astype(np.uint8).reshape(H, W, 3)


def render_eck(R, C, a, n, winkel0, flaechen, z0, z1):
    o, d = strahlen(R, C); best = np.full(H * W, np.inf); img = np.zeros((H * W, 3)); w = 2 * a * math.tan(math.pi / n)
    for k in flaechen:
        th = math.radians(winkel0) + 2 * math.pi * k / n; nn = np.array([math.cos(th), math.sin(th), 0.0]); dv = np.array([-nn[1], nn[0], 0.0]); p0 = a * nn
        nd = d @ nn
        with np.errstate(all="ignore"): t = (a - o @ nn) / nd
        X = o + t[:, None] * d; u = (X - p0) @ dv; ok = (nd < 0) & (t > 0) & (np.abs(u) <= w / 2) & (X[:, 2] >= z0) & (X[:, 2] <= z1) & (t < best)
        best = np.where(ok, t, best); img[ok] = tex_eben(u[ok], X[ok, 2])
    return np.clip(img, 0, 255).astype(np.uint8).reshape(H, W, 3)


def objekt_schreiben(tmp, cams_rendert):
    os.makedirs(os.path.join(tmp, "messprotokoll")); os.makedirs(os.path.join(tmp, "fotos"))
    json.dump(dict(fotos_dir=os.path.join(tmp, "fotos")), open(os.path.join(tmp, "objekt.json"), "w"))
    for nr, (R, t, img) in cams_rendert.items():
        cv2.imwrite(os.path.join(tmp, "fotos", nr + ".jpg"), img, [cv2.IMWRITE_JPEG_QUALITY, 97])
        json.dump(dict(foto=nr, kamera=dict(rvec=cv2.Rodrigues(R)[0].ravel().tolist(), t=t.tolist(), f_px=F_PX, cx=W / 2, cy=H / 2, k1=0.0)), open(os.path.join(tmp, "messprotokoll", f"K-{nr}.json"), "w"))


def pruefen(name, tmp, flaechen, gt, schwelle_med=10.0, schwelle_p90=40.0, mind_abgedeckt=0.9):
    json.dump(flaechen, open(os.path.join(tmp, "flaechen.json"), "w")); aus = os.path.join(tmp, "aus")
    FO.main([os.path.join(tmp, "objekt.json"), "--flaechen", os.path.join(tmp, "flaechen.json"), "--aus", aus, "--zelle", "0.03", "--max-fotos", "8"])
    rep = {r["id"]: r for r in json.load(open(os.path.join(aus, "flaechen_ortho.json")))}; ok_alle = True
    for fid, (X_gt, ) in gt.items():
        img = cv2.imread(os.path.join(aus, f"ortho_{fid}.png")).astype(np.float32); cnt = cv2.imread(os.path.join(aus, f"abdeckung_{fid}.png"), 0) > 0
        d = np.abs(img - X_gt).mean(2); d = d[cnt]; med, p90 = float(np.median(d)), float(np.percentile(d, 90)); ab = rep[fid]["abgedeckt"]
        ok = med < schwelle_med and p90 < schwelle_p90 and ab >= mind_abgedeckt; ok_alle &= ok
        print(f"  {'ok ' if ok else 'FEHLER'} {name}/{fid}: Abweichung median {med:.1f} / p90 {p90:.1f} Graustufen, abgedeckt {ab*100:.0f} %", flush=True)
    return ok_alle


def main():
    tmp0 = temp_ordner("flaeche_ortho_test_"); alle = True
    try:
        # 1) Zylinder (r 1,2, z 0..4) und 2) Kegel (r 1,5 -> 0,9) von 8 Kameras ringsum
        for name, k, r0 in (("zylinder", 0.0, 1.2), ("kegel", -0.15, 1.5)):
            tmp = os.path.join(tmp0, name); cams = {}
            for i in range(8):
                az = math.radians(45 * i + 10); C = np.array([8 * math.cos(az), 8 * math.sin(az), 2.0]); R, t = kamera(C, [0, 0, 2.0]); cams[f"c{i}"] = (R, t, render_rotation(R, C, r0, k, 0.0, 4.0))
            objekt_schreiben(tmp, cams)
            prof = [[0.0, r0], [4.0, r0 + 4 * k]]; fl = [dict(id="r", typ="rotation", achse=[0, 0], profil=prof, phi=[0, 360])]
            Xr, _, rr = FO.raster(fl[0], 0.03); phi = np.mod(np.arctan2(Xr[:, 1], Xr[:, 0]), 2 * np.pi); gt = tex_rund(phi, Xr[:, 2]).reshape(rr["nz"], rr["nu"], 3).astype(np.float32)
            alle &= pruefen(name, tmp, fl, dict(r=(gt,)), mind_abgedeckt=0.95)
            if name == "zylinder":                                                                   # GEGENPROBE: falscher Radius/falsche Achse MUSS deutlich schlechter sein, sonst beweist der Test nichts
                fehler = {}
                for bez, fl_f in (("Radius +10 %", [dict(id="r", typ="zylinder", achse=[0, 0], r=1.32, phi=[0, 360], z=[0, 4])]), ("Radius +3 %", [dict(id="r", typ="zylinder", achse=[0, 0], r=1.236, phi=[0, 360], z=[0, 4])]),
                                  ("Achse 10 cm versetzt", [dict(id="r", typ="zylinder", achse=[0.1, 0], r=1.2, phi=[0, 360], z=[0, 4])])):
                    json.dump(fl_f, open(os.path.join(tmp, "f2.json"), "w")); FO.main([os.path.join(tmp, "objekt.json"), "--flaechen", os.path.join(tmp, "f2.json"), "--aus", os.path.join(tmp, "aus2"), "--zelle", "0.03", "--max-fotos", "8"])
                    Xf, _, rf = FO.raster(fl_f[0], 0.03); rref = fl_f[0]["r"]; phi_t = (np.arange(rf["nu"]) + 0.5) * 2 * np.pi / rf["nu"]; zz = 4 - (np.arange(rf["nz"]) + 0.5) * 4 / rf["nz"]
                    gt_f = tex_rund(phi_t[None, :], zz[:, None]).astype(np.float32); im_f = cv2.imread(os.path.join(tmp, "aus2", "ortho_r.png")).astype(np.float32); fehler[bez] = float(np.median(np.abs(im_f - gt_f).mean(2)))
                med_ok = 1.8
                for bez, v in fehler.items(): print(f"  Gegenprobe {bez}: Abweichung median {v:.1f} Graustufen (richtig: ~{med_ok})")
                gp = fehler["Radius +10 %"] > 3 * med_ok and fehler["Achse 10 cm versetzt"] > 3 * med_ok; print(f"  {'ok ' if gp else 'FEHLER'} Gegenprobe: falsche Parameter sind deutlich schlechter"); alle &= bool(gp)
        # 3) n-Eck-Erker: Achteck, Apothem 1,2, Flaechen 7, 0, 1 (Aussennormalen -45, 0, +45 Grad), z 2..5, Kameras von vorn +-80 Grad
        tmp = os.path.join(tmp0, "erker"); cams = {}
        for i, azg in enumerate(range(-80, 81, 20)):
            az = math.radians(azg); C = np.array([8 * math.cos(az), 8 * math.sin(az), 3.5]); R, t = kamera(C, [1.2, 0, 3.5]); cams[f"c{i}"] = (R, t, render_eck(R, C, 1.2, 8, 0.0, [7, 0, 1], 2.0, 5.0))
        objekt_schreiben(tmp, cams)
        fl = [dict(id="erker", typ="polygon", achse=[0, 0], apothem=1.2, n=8, winkel0=0, flaechen=[7, 0, 1], z=[2.0, 5.0])]; gt = {}
        for F in FO.flaechen_expandieren(fl):
            Xr, _, rr = FO.raster(F, 0.03); d = np.array(F["d"]); u = (Xr - np.array(F["o"])) @ d; gt[F["id"]] = (tex_eben(u, Xr[:, 2]).reshape(rr["nz"], rr["nu"], 3).astype(np.float32), )
        # Flaechen mit schraeger Sicht sind nur teilweise gesehen (Rand): Abdeckung 0,75 genuegt
        alle &= pruefen("erker", tmp, fl, gt, mind_abgedeckt=0.75)
        # Geometrie des n-Ecks: Nachbarflaechen schliessen mit 45 Grad, Kantenpunkt passt
        fe = FO.flaechen_expandieren(fl); n0, n1 = np.array(fe[1]["n"]), np.array(fe[2]["n"]); ang = math.degrees(math.acos(float(n0 @ n1)))
        kante0 = np.array(fe[1]["o"]) + fe[1]["u"][1] * np.array(fe[1]["d"]); kante1 = np.array(fe[2]["o"]) + fe[2]["u"][0] * np.array(fe[2]["d"]); geo = abs(ang - 45) < 1e-6 and np.linalg.norm(kante0 - kante1) < 1e-9
        print(f"  {'ok ' if geo else 'FEHLER'} n-Eck-Geometrie: Winkel Nachbarflaechen {ang:.2f} Grad, Eckpunkte treffen sich ({np.linalg.norm(kante0 - kante1):.1e} m)"); alle &= bool(geo)
    finally: shutil.rmtree(tmp0, ignore_errors=True)
    print("flaeche_ortho: alle synthetischen Pruefungen bestanden" if alle else "flaeche_ortho: FEHLER"); return 0 if alle else 1


if __name__ == "__main__": sys.exit(main())
