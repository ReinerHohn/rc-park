"""Recherche-Punkt 9 (20.11.2026): DA3-BASE (Apache-2.0) mit UNSEREN Kameras als Fuelltiefe fuer Putzloecher - nur Test, nie Form.
Daten: Martinstor Rueckseite, Arbeitsordner der Messung schnell/fein (A_schnell: entzerrte Bilder, sparse, fotometrische Tiefenkarten 1600 px).
Je Bezugsbild: DA3 mit Bezugsbild + 7 Nachbarn (meiste gemeinsame Punkte), Posen und Brennweiten vorgegeben, Massstab an unsere Posen angeglichen.
Messung: (a) wo PatchMatch Tiefe hat: relativer Unterschied DA3 gegen PatchMatch (Median, p90); (b) Anteil der PatchMatch-Loecher im Bild, die DA3 fuellt,
(c) Bild dunkel: Foto | PatchMatch-Tiefe | DA3-Tiefe | Unterschied."""
import sys, os, glob, numpy as np, cv2
sys.path.insert(0, "/media/oem/rcdaten/da3/pkgs"); sys.path.insert(0, "/media/oem/rcdaten/da3/repo/src")
os.environ.setdefault("HF_HOME", "/media/oem/scan/hf_cache")
import torch
sys.path.append("/media/oem/scan/venv-colmap/lib/python3.12/site-packages"); import pycolmap   # nur pycolmap aus venv-colmap (hinten angehaengt, Rest aus venv-seg)
from depth_anything_3.api import DepthAnything3

W = "/media/oem/rcdaten/tmp/mt_seiten/fein_vgl/A_schnell"; AUS = "/media/oem/rcdaten/da3/aus"; os.makedirs(AUS, exist_ok=True)
r = pycolmap.Reconstruction(W + "/sparse")


def lies_karte(p):
    with open(p, "rb") as f:
        kopf = b""; n = 0
        while n < 3:
            c = f.read(1); kopf += c; n += c == b"&"
        w, h, ch = map(int, kopf.decode().strip("&").split("&")); return np.fromfile(f, np.float32).reshape(ch, h, w).transpose(1, 2, 0).squeeze()


def nachbarn(iid, k=7):
    z = {}
    for p in r.images[iid].points2D:
        if p.has_point3D():
            for e in r.points3D[p.point3D_id].track.elements:
                if e.image_id != iid: z[e.image_id] = z.get(e.image_id, 0) + 1
    return [i for i, _ in sorted(z.items(), key=lambda x: -x[1])[:k]]


SEITE = 1600
model = DepthAnything3.from_pretrained("depth-anything/DA3-BASE").to("cuda").eval()
ids = sorted(r.images, key=lambda i: -r.images[i].num_points3D)[:int(sys.argv[1]) if len(sys.argv) > 1 else 6]; erg = []
for iid in ids:
    sel = [iid] + nachbarn(iid); bilder, ex, K = [], [], []
    for i in sel:
        im = r.images[i]; cam = r.cameras[im.camera_id]; b = cv2.imread(os.path.join(W, "images", im.name)); Q = np.zeros((SEITE, SEITE, 3), np.uint8)
        Q[:b.shape[0], :b.shape[1]] = b[:SEITE, :SEITE]; q = os.path.join(AUS, f"q_{len(bilder)}.png"); cv2.imwrite(q, Q); bilder.append(q)   # auf Quadrat auffuellen: K bleibt gueltig (DA3 schneidet sonst mittig zu)
        ex.append(np.vstack([im.cam_from_world().matrix(), [0, 0, 0, 1]])); K.append(cam.calibration_matrix())
    with torch.autocast("cuda", dtype=torch.float16):
        pr = model.inference(bilder, extrinsics=np.array(ex, np.float32), intrinsics=np.array(K, np.float32), process_res=int(os.environ.get("DA3_RES", "504")), align_to_input_ext_scale=True)
    d3q = np.asarray(pr.depth[0], np.float32); name = r.images[iid].name; f_ = d3q.shape[0] / SEITE
    pm = lies_karte(os.path.join(W, "stereo/depth_maps", name + ".photometric.bin")); foto = cv2.imread(os.path.join(W, "images", name))
    H, Wd = pm.shape; d3 = d3q[:int(round(H * f_)), :int(round(Wd * f_))]; d3g = cv2.resize(d3, (Wd, H), interpolation=cv2.INTER_LINEAR); gueltig = pm > 0
    rel = np.abs(d3g[gueltig] - pm[gueltig]) / pm[gueltig]; q = np.median(d3g[gueltig] / pm[gueltig]); relq = np.abs(d3g[gueltig] / q - pm[gueltig]) / pm[gueltig]
    print(f"   Massstab DA3/PatchMatch {q:.3f}; nach Massstab-Angleich rel. Median {100*np.median(relq):.1f} %, p90 {100*np.percentile(relq, 90):.1f} %", flush=True)
    # Gebaeudemaske grob: Bereich, in dem PatchMatch in der Umgebung (101 px) ueberhaupt Tiefe hat -> Loecher darin = Putz/Fenster, nicht Himmel
    umg = cv2.dilate(gueltig.astype(np.uint8), np.ones((101, 101), np.uint8)) > 0; loch = umg & ~gueltig
    # Loch-Simulation: 80x80-Bloecke mit voller PatchMatch-Tiefe abdecken, aus einem 30-px-Ring fuellen: DA3 (Massstab+Versatz am Ring) gegen Ebene durch den Ring
    rng = np.random.default_rng(0); B, Rg = 80, 30; fe_d, fe_e = [], []; yy, xx = np.mgrid[0:B + 2 * Rg, 0:B + 2 * Rg]
    for _ in range(4000):
        y0, x0 = rng.integers(Rg, H - B - Rg), rng.integers(Rg, Wd - B - Rg); P = pm[y0 - Rg:y0 + B + Rg, x0 - Rg:x0 + B + Rg]; D = d3g[y0 - Rg:y0 + B + Rg, x0 - Rg:x0 + B + Rg]
        innen = np.zeros(P.shape, bool); innen[Rg:-Rg, Rg:-Rg] = True; ring = ~innen & (P > 0)
        if (P[innen] > 0).mean() < 0.98 or ring.sum() < 0.8 * (~innen).sum(): continue
        A = np.c_[D[ring], np.ones(ring.sum())]; ab = np.linalg.lstsq(A, P[ring], rcond=None)[0]; vd = ab[0] * D[innen] + ab[1]
        E = np.c_[xx[ring], yy[ring], np.ones(ring.sum())]; ce = np.linalg.lstsq(E, P[ring], rcond=None)[0]; ve = ce[0] * xx[innen] + ce[1] * yy[innen] + ce[2]
        w = P[innen] > 0; fe_d.append(np.median(np.abs(vd[w] - P[innen][w]) / P[innen][w])); fe_e.append(np.median(np.abs(ve[w] - P[innen][w]) / P[innen][w]))
        if len(fe_d) >= 150: break
    if fe_d: print(f"   Loch-Simulation {len(fe_d)} Bloecke: Fehler DA3 {100*np.median(fe_d):.2f} %, Ebene {100*np.median(fe_e):.2f} %; DA3 besser in {100*np.mean(np.array(fe_d) < np.array(fe_e)):.0f} %", flush=True)
    zeile = dict(bild=name, rel_median=float(np.median(rel)), rel_p90=float(np.percentile(rel, 90)), loch_anteil=float(loch.mean()), pm_gueltig=float(gueltig.mean())); erg.append(zeile)
    print(f"{name[:50]}: DA3 gegen PatchMatch rel. Median {100*zeile['rel_median']:.1f} %, p90 {100*zeile['rel_p90']:.1f} % | PatchMatch belegt {100*zeile['pm_gueltig']:.0f} %, Loecher am Bau {100*zeile['loch_anteil']:.0f} % (DA3 fuellt sie alle - Genauigkeit dort unbekannt)", flush=True)
    lo, hi = np.percentile(pm[gueltig], [2, 98]); farb = lambda D: cv2.applyColorMap(np.uint8(np.clip((D - lo) / (hi - lo), 0, 1) * 255), cv2.COLORMAP_TURBO)
    a = farb(pm); a[~gueltig] = 18; b = farb(d3g); dif = np.zeros_like(a); rd = np.zeros(pm.shape, np.float32); rd[gueltig] = np.abs(d3g - pm)[gueltig] / pm[gueltig]; dif = cv2.applyColorMap(np.uint8(np.clip(rd * 5, 0, 1) * 255), cv2.COLORMAP_INFERNO); dif[~gueltig] = 18
    s = 600 / H; zeig = [cv2.resize(x, None, fx=s, fy=s) for x in (foto, a, b, dif)]
    for x, t in zip(zeig, ("Foto", "PatchMatch (schwarz = Loch)", "DA3-BASE mit unseren Kameras", "Unterschied (hell = 20 %)")): cv2.putText(x, t, (10, 30), 0, 0.8, (240, 240, 240), 2)
    cv2.imwrite(os.path.join(AUS, f"da3_{len(erg)}.jpg"), np.hstack(zeig), [cv2.IMWRITE_JPEG_QUALITY, 85])
import json; json.dump(erg, open(os.path.join(AUS, "ergebnis.json"), "w"), indent=1)
