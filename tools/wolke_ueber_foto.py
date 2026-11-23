#!/usr/bin/env python3
"""wolke_ueber_foto.py - Punktwolke UND Netzkanten mit der festen Kamera K-<nr> ueber das (entzerrte) Foto legen.
Frage (Nutzer 7.11.): Liegt die WOLKE auf den Fotokanten, das NETZ aber nicht -> Versatz kommt vom Netz, nicht von der Kamera.
  /media/oem/scan/venv-seg/bin/python -W ignore -I tools/wolke_ueber_foto.py modelle/<obj>/objekt.json <fotonr> --dicht <sfm/dicht_*> [--stl netz.stl] --aus x.jpg [--ausrichtung ...]
Wolke: fused.ply -> Modellrahmen (wolke_abstand_einseitig.wolke_im_modellrahmen), dann + K.rahmen_verschiebung wie das Netz in foto_diff._netz.
Kein Urteil per Auge allein: zusaetzlich Kennzahl = Median-Abstand (px) der Wolken-Randpunkte zu Fotokanten vs. Netzkanten zu Fotokanten."""
import os, sys, json, argparse, glob, numpy as np, cv2, trimesh
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from kamera_standort import kamera_standort   # 23.11.2026: standort_xyz > standort > Pose (231 K-Dateien ohne standort_xyz)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fehlteile_finden as FF, wolke_abstand_einseitig as WA, foto_diff as FD
from scipy.ndimage import distance_transform_edt

ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("foto"); ap.add_argument("--dicht", required=True); ap.add_argument("--stl")
ap.add_argument("--ausrichtung"); ap.add_argument("--npy"); ap.add_argument("--aus", required=True); ap.add_argument("--n", type=int, default=3000000)
a = ap.parse_args(); obj = json.load(open(a.objekt)); od = os.path.dirname(os.path.abspath(a.objekt)); root = os.path.dirname(os.path.dirname(od))
K = json.load(open(os.path.join(od, "messprotokoll", f"K-{a.foto}.json"))); kk = K["kamera"]
fp = glob.glob(os.path.join(root, obj["fotos_dir"], f"{a.foto}_*"))[0]; im = cv2.imread(fp); im, _ = FF.foto_entzerren(im, kk); H, W = im.shape[:2]
R, _ = cv2.Rodrigues(np.array(kk["rvec"], float)); t = np.array(kk["t"], float); f = kk["f_px"]; cx = kk.get("cx", W / 2); cy = kk.get("cy", H / 2)
rv = np.array(kk.get("rahmen_verschiebung", [0, 0, 0]), float)
def wolke_im_kamerarahmen(dicht, od):
    """fused.ply (SfM-Rahmen) -> Rahmen der K-Dateien: Aehnlichkeit (Umeyama) aus Kamerazentren der Dichtrekonstruktion gegen K.standort_xyz
    (OHNE Ausrichtungsdatei: die kann zu einem anderen Lauf gehoeren, 7.11. Wolke lag 60 m daneben). Rest-Abstand wird ausgegeben und muss < 5 cm sein."""
    import freiraum_pruefen as FP
    Kd = json.load(open(os.path.join(dicht, "kameras_unverzerrt.json"))); S = []; M = []
    for i, c in Kd.items():
        p = os.path.join(od, "messprotokoll", f"K-{i}.json")
        if not os.path.exists(p): continue
        k = json.load(open(p)).get("kamera", {})
        Sk = kamera_standort(k)
        if Sk is None: continue
        S.append(-np.array(c["R"]).T @ np.array(c["t"])); M.append(Sk)
    S = np.array(S); M = np.array(M); ms, mm = S.mean(0), M.mean(0); A = S - ms; B = M - mm
    U, D, Vt = np.linalg.svd(B.T @ A / len(S)); Sg = np.eye(3); Sg[2, 2] = np.sign(np.linalg.det(U @ Vt)); Rm = U @ Sg @ Vt
    s = np.trace(np.diag(D) @ Sg) / A.var(0).sum(); t0 = mm - s * Rm @ ms; rest = np.linalg.norm(s * (Rm @ S.T).T + t0 - M, axis=1)
    print(f"Wolke->Kamerarahmen: {len(S)} Kameras, s={s:.6f}, Rest median {np.median(rest)*100:.2f} cm, max {rest.max()*100:.2f} cm")
    assert np.median(rest) < 0.05, "Rahmen passt nicht"
    X = FP.ply_lesen(os.path.join(dicht, "fused.ply")); return s * (Rm @ X.T).T + t0
X = np.load(a.npy).astype(np.float64) if a.npy else wolke_im_kamerarahmen(a.dicht, od)
if len(X) > a.n: X = X[np.random.default_rng(0).choice(len(X), a.n, replace=False)]
def proj(P):
    Pc = P @ R.T + t; z = Pc[:, 2]; ok = z > 1; u = f * Pc[:, 0] / np.where(ok, z, 1) + cx; v = f * Pc[:, 1] / np.where(ok, z, 1) + cy
    return u, v, z, ok & (u >= 0) & (u < W) & (v >= 0) & (v < H)
u, v, z, ok = proj(X); ui = u[ok].astype(int); vi = v[ok].astype(int); zi = z[ok]
zb = np.full((H, W), np.inf, np.float32); np.minimum.at(zb, (vi, ui), zi.astype(np.float32))        # nahester Punkt je Pixel (z-Puffer)
sicht = zi <= zb[vi, ui] * 1.02 + 0.3
wm = np.zeros((H, W), np.uint8); wm[vi[sicht], ui[sicht]] = 255; wm = cv2.dilate(wm, np.ones((3, 3), np.uint8))
ov = im.copy(); ov[wm > 0] = (255, 255, 0)                                                         # Wolke cyan (BGR)
gray = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY); fk = cv2.Canny(cv2.GaussianBlur(gray, (0, 0), 2.0), 30, 90) > 0
bericht = dict(foto=a.foto, wolkenpunkte_im_bild=int(sicht.sum()))
if a.stl:
    m = trimesh.load(a.stl); m.apply_scale(obj.get("stl_massstab", 87) / 1000.0); m.apply_translation(rv)
    mk = FD.netzkanten(m, R, t, f, cx, cy, W, H)
    mk = np.asarray(mk); mk = mk.reshape(-1, mk.shape[-1])[:, :2] if mk.size else mk
    nm = np.zeros((H, W), bool)
    if mk.size:
        xi = np.clip(mk[:, 0].astype(int), 0, W - 1); yi = np.clip(mk[:, 1].astype(int), 0, H - 1); nm[yi, xi] = True
    ov[cv2.dilate(nm.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0] = (0, 0, 255)               # Netzkanten rot
    dist = distance_transform_edt(~fk); bericht["netzkanten_px"] = int(nm.sum()); bericht["median_abstand_netzkante_zu_fotokante_px"] = round(float(np.median(dist[nm])), 2) if nm.any() else None
# Wolken-Randpunkte: Punkte an Tiefensprung = Silhouette/Kantennaehe -> Abstand zur Fotokante
dz = cv2.Laplacian(np.where(np.isfinite(zb), zb, 0).astype(np.float32), cv2.CV_32F); rand = (np.abs(dz) > 1.0) & np.isfinite(zb)
dist = distance_transform_edt(~fk); bericht["wolkenrand_px"] = int(rand.sum()); bericht["median_abstand_wolkenrand_zu_fotokante_px"] = round(float(np.median(dist[rand])), 2) if rand.any() else None
bericht["median_abstand_zufall_px"] = round(float(np.median(dist)), 2); bericht["f_px"] = f; bericht["rahmen_verschiebung"] = rv.tolist()
cv2.imwrite(a.aus, cv2.resize(ov, None, fx=0.5, fy=0.5)); json.dump(bericht, open(os.path.splitext(a.aus)[0] + ".json", "w"), indent=1); print(json.dumps(bericht, indent=1))
