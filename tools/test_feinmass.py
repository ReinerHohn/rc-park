#!/usr/bin/env python3
"""test_feinmass.py - SYNTHETISCHER BEWEIS fuer f1_fein (modelle/archiv/SPEC_ORNAMENT_FEINMASS.md).
Testflaeche mit aufgesetzten Rippen (bekannte Lage, Metrik in m) wird mit der echten Kamera eines kalibrierten Fotos exakt gerastert und als undurchsichtiges Paneel in das
ECHTE Foto kopiert (Foto = Wahrheit mit Rippen an bekannter Stelle). Modelle: (a) Rippen richtig, (b) Rippen um 0,15 m versetzt, (c) glatte Flaeche ohne Rippen.
Erwartung: f1_fein (a) deutlich > (b), (c); die Grobzahl (Analog zur Hauptzahl: dieselben Kanten, Toleranz 0,14 m, Foto-Kanten nach 0,18-m-Glaettung) trennt (a) von (b)/(c)
KLEINER als f1_fein. Aufruf: python -I tools/test_feinmass.py <objekt> <foto> [--modul teil_fotoform]
"""
import sys, os, json, glob, argparse, importlib, numpy as np, cv2, trimesh
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fehlteile_finden as FF, render_kern as RK, foto_diff as FD
R0 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def bogen(c, r, w0, w1, n=14):
    return [c + r * np.array([np.cos(a), np.sin(a)]) for a in np.linspace(w0, w1, n)]


def rippen(shift=0.0):
    """Rippen als Liste von 2D-Polylinien (m) in der Paneelebene: zwei sich kreuzende Spitzbogen + senkrechte Mittelrippe."""
    pl = [bogen(np.array([-1.0, -1.2]), 1.9, 0.0, np.pi / 2.2), bogen(np.array([1.0, -1.2]), 1.9, np.pi - np.pi / 2.2, np.pi), [np.array([0.0, -1.2]), np.array([0.0, 1.2])]]
    return [[p + np.array([shift, 0.0]) for p in l] for l in pl]


def paneel(R, t, z0, mit_rippen, shift, B=2.6, Hh=3.0, zc=(0.0, 0.0)):
    """Paneel-Mesh in WELT-Koordinaten: Ebene bei Kamera-z = z0, Mitte (zc) in Bildmitte-Richtung; Rippen b 0,08 m, vor 0,06 m."""
    def wel(xy, dz): return R.T @ (np.array([xy[0] + zc[0], xy[1] + zc[1], z0 - dz]) - t)
    teile = [trimesh.creation.box(extents=(B, Hh, 0.05))]; teile[0].apply_translation((zc[0], zc[1], z0 + 0.025))
    if mit_rippen:
        for l in rippen(shift):
            for a_, b_ in zip(l[:-1], l[1:]):
                a_, b_ = np.asarray(a_), np.asarray(b_); L = np.linalg.norm(b_ - a_) + 0.02; ang = np.arctan2(*(b_ - a_)[::-1])
                bx = trimesh.creation.box(extents=(L, 0.08, 0.06)); bx.apply_transform(trimesh.transformations.rotation_matrix(ang, (0, 0, 1)))
                bx.apply_translation(((a_ + b_)[0] / 2 + zc[0], (a_ + b_)[1] / 2 + zc[1], z0 - 0.03))
                teile.append(bx)
    m = trimesh.util.concatenate(teile); V = np.asarray(m.vertices); Vw = (R.T @ (V - t).T).T   # Kamera-Koordinaten -> Welt
    return trimesh.Trimesh(Vw, m.faces, process=False)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("foto"); ap.add_argument("--modul", default="teil_fotoform"); ap.add_argument("--z", type=float, default=14.0)
    ap.add_argument("--aus", default="/media/oem/scan/rc-park_tmp/feinmass/render"); a = ap.parse_args()
    TF = importlib.import_module(a.modul)
    objp = os.path.join(R0, "modelle", a.objekt, "objekt.json"); obj = json.load(open(objp)); K = json.load(open(FF.k_datei(objp, obj, R0, a.foto)))
    bild = glob.glob(os.path.join(R0, obj["fotos_dir"], a.foto + "_*"))[0]; im, K = FD.foto_skalieren(cv2.imread(bild), K); kk = K["kamera"]; H, W = im.shape[:2]
    im, _ = FF.foto_entzerren(im, kk); R, t, f, _, _ = FF.kamera_laden(K, obj, a.foto, R0, W, H); cx, cy = float(kk.get("cx", W / 2)), float(kk.get("cy", H / 2))
    zc = (0.0, 0.0)
    def rendern(mit, sh):
        m = paneel(R, t, a.z, mit, sh, zc=zc); d, fid, _ = RK.dreiecke_rastern(m, R, t, f, cx, cy, W, H); return m, np.asarray(d, np.float32), fid
    # WAHRHEIT: Paneel mit richtigen Rippen ins echte Foto (schattiert aus Normalen, undurchsichtig)
    mw, dw, fw = rendern(True, 0.0); fin = np.isfinite(dw); fn = np.asarray(mw.face_normals, np.float32); nz = fn[np.clip(fw, 0, None)]
    kam_n = (R @ nz.reshape(-1, 3).T).T.reshape(nz.shape); sh = np.clip(np.abs(kam_n @ np.array([-0.4, -0.5, 0.77])), 0, 1)
    grau = (60 + 170 * sh).astype(np.uint8); foto = im.copy(); foto[fin] = np.dstack([grau] * 3)[fin]
    ys, xs = np.nonzero(fin); roi = np.zeros((H, W), bool); roi[ys.min():ys.max() + 1, xs.min():xs.max() + 1] = True; roi = cv2.dilate(roi.astype(np.uint8), np.ones((9, 9), np.uint8)) > 0
    gray = cv2.cvtColor(foto, cv2.COLOR_BGR2GRAY); ff = TF.feinkanten_foto(gray, roi) & roi
    # GROB-Analog: Fotokanten aus 0,18-m-geglaettetem Bild (sigma_px = 0,18 m / Pixelgroesse), Toleranz 0,14 m
    px_m = a.z / f; sg = 0.18 / px_m / 2.0; gg = cv2.GaussianBlur(gray, (0, 0), max(sg, 1.0)); fg = TF.feinkanten_foto(gg, roi) & roi
    tol_f = TF.FEIN_TOL_M / px_m; tol_g = 0.14 / px_m; erg = {}
    for name, mit, sh_ in (("richtig", True, 0.0), ("versetzt_0.15", True, 0.15), ("ohne_rippen", False, 0.0)):
        m, d, fid = rendern(mit, sh_); mf = TF.feinkanten_modell(d, fid, np.asarray(m.face_normals, np.float32)) & roi
        pf, rf = TF.fein_bewerten(mf, ff, tol_f); f1f = 2 * pf * rf / (pf + rf)
        mg = mf  # Modellkanten gleich, grobe Toleranz + grobe Fotokanten
        pg, rg = TF.fein_bewerten(mg, fg, tol_g); f1g = 2 * pg * rg / (pg + rg)
        erg[name] = {"f1_fein": round(f1f, 3), "praez_f": round(pf, 3), "recall_f": round(rf, 3), "f1_grob_analog": round(f1g, 3), "mk_px": int(mf.sum())}
        ov = (foto // 2).copy(); ov[ff] = (255, 160, 0); ov[mf] = (0, 220, 0); ov[mf & ff] = (255, 255, 255)
        ys, xs = np.nonzero(roi); os.makedirs(a.aus, exist_ok=True); cv2.imwrite(os.path.join(a.aus, f"synth_{a.foto}_{name}.jpg"), ov[ys.min():ys.max(), xs.min():xs.max()], [cv2.IMWRITE_JPEG_QUALITY, 85])
    cv2.imwrite(os.path.join(a.aus, f"synth_{a.foto}_wahrheit.jpg"), foto[ys.min():ys.max(), xs.min():xs.max()], [cv2.IMWRITE_JPEG_QUALITY, 85])
    print(json.dumps(erg, indent=1))
    r, v, o = erg["richtig"], erg["versetzt_0.15"], erg["ohne_rippen"]
    ok = r["f1_fein"] > v["f1_fein"] + 0.1 and r["f1_fein"] > o["f1_fein"] + 0.1
    print("BEWEIS f1_fein trennt richtig/versetzt/ohne:", "BESTANDEN" if ok else "FEHLGESCHLAGEN", "| Spreizung grob-analog (richtig - versetzt):", round(r["f1_grob_analog"] - v["f1_grob_analog"], 3), "fein:", round(r["f1_fein"] - v["f1_fein"], 3))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
