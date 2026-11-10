#!/usr/bin/env python3
"""Diagnose zu wolke_verdeckung: Wolkentiefenkarte je Foto als Bild (Farbe = Tiefe, schwarz = keine gestuetzte Wolke) neben dem Foto.
Aufruf: venv-seg/bin/python -W ignore -I tools/wolke_verdeckung_karte.py <objekt> <foto> <aus.jpg> [--zelle 6] [--nmin 4] [--wolke W.npy]"""
import sys, os, json, glob, argparse, numpy as np, cv2
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import foto_diff as FD, fehlteile_finden as FF, wolke_verdeckung as WV
R0 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("foto"); ap.add_argument("aus"); ap.add_argument("--zelle", type=int, default=12)
ap.add_argument("--nmin", type=int, default=2); ap.add_argument("--wolke"); ap.add_argument("--schicht", type=float, default=0.6); a = ap.parse_args()
objp = os.path.join(R0, "modelle", a.objekt, "objekt.json"); obj = json.load(open(objp))
K = json.load(open(FF.k_datei(objp, obj, R0, a.foto))); im = cv2.imread(glob.glob(os.path.join(R0, obj["fotos_dir"], a.foto + "_*"))[0])
im, K = FD.foto_skalieren(im, K); H, W = im.shape[:2]; kk = K["kamera"]
R, t, f, _, _ = FF.kamera_laden(K, obj, a.foto, R0, W, H); cx, cy = float(kk.get("cx", W / 2)), float(kk.get("cy", H / 2))
wp = a.wolke or obj.get("kreis", {}).get("wolke") or "/media/oem/scan/rc-park_null/wolke_gemeinsam/lot2/j_voll_lot2.npy"
zc = WV.Verdecker(np.load(wp, mmap_mode="r")).zkarte(R, t, f, cx, cy, W, H, zelle=a.zelle, nmin=a.nmin, schicht=a.schicht).cpu().numpy().repeat(a.zelle, 0).repeat(a.zelle, 1)[:H, :W]
ok = np.isfinite(zc); print(f"Foto {a.foto}: gestuetzte Wolke in {ok.mean():.1%} der Pixel; Tiefe Median {np.median(zc[ok]) if ok.any() else float('nan'):.1f} m")
c = np.zeros((H, W, 3), np.uint8)
if ok.any():
    g = np.clip((zc - 2) / 40, 0, 1); c = cv2.applyColorMap((255 * (1 - g)).astype(np.uint8), cv2.COLORMAP_TURBO); c[~ok] = 0
o = np.hstack([im, c]); s = 1400 / o.shape[1]; cv2.imwrite(a.aus, cv2.resize(o, None, fx=s, fy=s, interpolation=cv2.INTER_AREA), [cv2.IMWRITE_JPEG_QUALITY, 85])
