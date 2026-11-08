"""LIMAP-Linien -> Netzrahmen exportieren und gegen Fotokanten messen (Kontrolle: gleiche Linien um 1,5 m verschoben).
venv-limap: limap_auswerten.py <out_dir/geometry_guided_final_model> <objektdir> <fotos_dir> <ziel_dir> [verschiebung_z=0.431]"""
import sys, os, json, glob, numpy as np, cv2
import limap.scene as S
mod, obj, fdir, ziel = sys.argv[1:5]; vz = float(sys.argv[5]) if len(sys.argv) > 5 else 0.431
os.makedirs(ziel, exist_ok=True)
h = S.HolisticReconstruction(); h.read(mod); sr = h.structure_recon; rec = h.point_recon
ids = sorted(sr.line3D_ids()); A = []; T = []; IM = []
for i in ids:
    l = sr.line(i); A.append([l.start, l.end]); el = l.track.elements; T.append(len(el)); IM.append(sorted({e.image_id for e in el}))
A = np.array(A, float) + np.array([0, 0, vz]); T = np.array(T); lang = np.linalg.norm(A[:, 1] - A[:, 0], axis=1)
np.save(os.path.join(ziel, "linien3d_netzrahmen.npy"), A); np.save(os.path.join(ziel, "linien3d_spur.npy"), T)
name = {i: im.name for i, im in rec.images.items()}
json.dump(dict(n=len(A), spurlaenge_ge3=int((T >= 3).sum()), ge5=int((T >= 5).sum()), ge10=int((T >= 10).sum()), laenge_median_m=float(np.median(lang)), laenge_p90=float(np.percentile(lang, 90)),
               bbox_min=A.reshape(-1, 3).min(0).tolist(), bbox_max=A.reshape(-1, 3).max(0).tolist(), rahmen="Netzrahmen = COLMAP-dicht + [0,0,%.3f]" % vz), open(os.path.join(ziel, "linien3d_info.json"), "w"), indent=1)
def proj(P, k, W, H):
    R, _ = cv2.Rodrigues(np.array(k["rvec"], float)); Pc = (R @ P.T).T + np.array(k["t"]); z = Pc[:, 2]
    s = W / k["bild"][0]; f = k["f_px"] * s; cx = k["cx"] * s; cy = k["cy"] * s
    return np.stack([f * Pc[:, 0] / np.maximum(z, 1e-6) + cx, f * Pc[:, 1] / np.maximum(z, 1e-6) + cy], 1), z
def deckung(A_, im, k, edt, W, H, n=25, tol=4.0):
    res = []
    for a, b in A_:
        P = a + (b - a) * np.linspace(0, 1, n)[:, None]; uv, z = proj(P, k, W, H)
        ok = (z > 1) & (uv[:, 0] >= 0) & (uv[:, 0] < W) & (uv[:, 1] >= 0) & (uv[:, 1] < H)
        if ok.sum() < n * 0.8: continue
        d = edt[uv[ok, 1].astype(int), uv[ok, 0].astype(int)]; res.append((d <= tol).mean())
    return np.array(res)
rng = np.random.default_rng(0); rows = []; sel = (T >= 3) & (lang >= 0.8)
for kf in sorted(glob.glob(os.path.join(obj, "messprotokoll", "K-*.json")))[::3]:
    nr = os.path.basename(kf)[2:5]; K = json.load(open(kf))
    if "kamera" not in K: continue
    k = K["kamera"]; fl = glob.glob(os.path.join(fdir, nr + "_*"))
    if not fl: continue
    im = cv2.imread(fl[0]); 
    if im is None: continue
    W = 1600; H = int(im.shape[0] * W / im.shape[1]); im = cv2.resize(im, (W, H), interpolation=cv2.INTER_AREA)
    s = W / k["bild"][0]; Km = np.array([[k["f_px"] * s, 0, k["cx"] * s], [0, k["f_px"] * s, k["cy"] * s], [0, 0, 1]])
    if k.get("k1"): im = cv2.undistort(im, Km, np.array([k["k1"], 0, 0, 0]), None, Km)
    g = cv2.GaussianBlur(cv2.cvtColor(im, cv2.COLOR_BGR2GRAY), (0, 0), 1.5); ed = cv2.Canny(g, 30, 90)
    edt = cv2.distanceTransform((ed == 0).astype(np.uint8), cv2.DIST_L2, 3)
    d1 = deckung(A[sel], im, k, edt, W, H)
    if len(d1) < 5: continue
    sh = A[sel] + np.array([1.2, 1.2, 0.0]) * rng.choice([-1, 1]); d0 = deckung(sh, im, k, edt, W, H)
    rows.append(dict(foto=nr, n_sichtbar=int(len(d1)), deckung_mittel=float(d1.mean()), anteil_ge70=float((d1 >= .7).mean()), kontrolle_mittel=float(d0.mean()) if len(d0) else None, kontrolle_ge70=float((d0 >= .7).mean()) if len(d0) else None))
    if len(rows) <= 4:
        o = im.copy()
        for a, b in A[sel]:
            uv, z = proj(np.array([a, b]), k, W, H)
            if (z > 1).all(): cv2.line(o, tuple(int(x) for x in uv[0]), tuple(int(x) for x in uv[1]), (0, 0, 255), 2)
        o[ed > 0] = (0, 255, 255); cv2.imwrite(os.path.join(ziel, "overlay_%s.jpg" % nr), o)
    print(rows[-1], flush=True)
agg = dict(fotos=len(rows), deckung_mittel=float(np.mean([r["deckung_mittel"] for r in rows])), anteil_ge70=float(np.mean([r["anteil_ge70"] for r in rows])),
           kontrolle_mittel=float(np.mean([r["kontrolle_mittel"] for r in rows if r["kontrolle_mittel"] is not None])), kontrolle_ge70=float(np.mean([r["kontrolle_ge70"] for r in rows if r["kontrolle_ge70"] is not None])), je_foto=rows)
json.dump(agg, open(os.path.join(ziel, "messung_deckung.json"), "w"), indent=1); print({k: v for k, v in agg.items() if k != "je_foto"})
