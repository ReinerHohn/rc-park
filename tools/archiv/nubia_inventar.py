#!/usr/bin/env python3
"""Stufe 1: Inventur der Nubia-Handyfotos (EXIF, MD5, Schaerfe, pHash, dHash, SIFT-Merkmale, Miniatur).
Quelle read-only. Ausgabe unter AUS/cache und AUS/inventar_roh.json.
Aufruf: /media/oem/scan/venv-seg/bin/python -I tools/nubia_inventar.py"""
import os, sys, json, hashlib, glob, struct
from multiprocessing import Pool
import numpy as np, cv2
from PIL import Image, ImageOps
cv2.setNumThreads(1)
QUELLE = "/media/oem/TOSHIBA EXT/nubia-photos/3d-Quellen"
AUS = "/media/oem/TOSHIBA EXT/rc-park_auslagern/nubia_sortierung"
EING = "/media/oem/scan/rc-park_daten/kaufhaus/fotos_eingang"
CACHE = AUS + "/cache"

def liste():
    out = []
    for f in sorted(glob.glob(QUELLE + "/*/*.jpg")):
        out.append(("quelle", os.path.basename(os.path.dirname(f)), f))
    for f in sorted(glob.glob(EING + "/handy_2026-11-06*/*.jp*g")):
        out.append(("vorhanden", os.path.basename(os.path.dirname(f)), f))
    for f in sorted(glob.glob(EING + "/*.jp*g")):
        out.append(("eingang_root", "fotos_eingang", f))
    return out

def md5(f):
    h = hashlib.md5()
    with open(f, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()

def phash(g):
    s = cv2.resize(g, (32, 32), interpolation=cv2.INTER_AREA).astype(np.float32)
    d = cv2.dct(s)[:8, :8]
    m = np.median(d.flatten()[1:])
    bits = (d.flatten() > m)
    return "%016x" % int("".join("1" if b else "0" for b in bits), 2)

def dhash(g):
    s = cv2.resize(g, (9, 8), interpolation=cv2.INTER_AREA).astype(np.int16)
    bits = (s[:, 1:] > s[:, :-1]).flatten()
    return "%016x" % int("".join("1" if b else "0" for b in bits), 2)

def schaerfe(g):
    """g: Grau ~1000 px lange Kante. Laplace-Varianz global + 90. Perzentil der 32px-Kacheln (robust gegen Himmel)."""
    lap = cv2.Laplacian(g, cv2.CV_32F)
    glob_v = float(lap.var())
    h, w = lap.shape
    k = 32
    lap2 = lap[:h // k * k, :w // k * k].reshape(h // k, k, w // k, k)
    kv = lap2.var(axis=(1, 3)).flatten()
    return glob_v, float(np.percentile(kv, 90)), float(np.percentile(kv, 50))

def exif(f):
    im = Image.open(f)
    ex = im.getexif()
    sub = ex.get_ifd(0x8769)
    gps = ex.get_ifd(0x8825)
    r = {"breite": im.size[0], "hoehe": im.size[1], "orient": ex.get(274),
         "make": ex.get(271), "modell": ex.get(272),
         "datum": sub.get(36867) or ex.get(306),
         "brennweite_mm": sub.get(37386), "f_zahl": sub.get(33437),
         "belichtung_s": sub.get(33434), "iso": sub.get(34855),
         "brennweite_35": sub.get(41989), "digitalzoom": sub.get(41988),
         "gps_ifd_zeiger": ex.get(34853), "gps_tags": {str(k): str(v) for k, v in gps.items()}}
    return r, im

def arbeit(a):
    typ, ordner, f = a
    key = hashlib.md5(f.encode()).hexdigest()[:16]
    r = {"typ": typ, "ordner": ordner, "pfad": f, "name": os.path.basename(f), "key": key,
         "groesse_b": os.path.getsize(f)}
    try:
        r["md5"] = md5(f)
        e, im = exif(f)
        r.update(e)
        im.draft("L", (1100, 1100))  # schnelles JPEG-Verkleinern
        g = np.asarray(im.convert("L"))
        s = 1000.0 / max(g.shape)
        # Orientierung beachten: Bild logisch drehen (EXIF 6/8)
        g = cv2.resize(g, None, fx=s, fy=s, interpolation=cv2.INTER_AREA) if s < 1 else g
        o = r.get("orient")
        if o == 6: g = cv2.rotate(g, cv2.ROTATE_90_CLOCKWISE)
        elif o == 8: g = cv2.rotate(g, cv2.ROTATE_90_COUNTERCLOCKWISE)
        elif o == 3: g = cv2.rotate(g, cv2.ROTATE_180)
        r["hochformat"] = bool(g.shape[0] > g.shape[1])
        r["lap_global"], r["lap_k90"], r["lap_k50"] = schaerfe(g)
        r["phash"] = phash(g); r["dhash"] = dhash(g)
        mittel = float(g.mean()); r["helligkeit"] = mittel
        r["ueber_prozent"] = float((g > 245).mean() * 100); r["unter_prozent"] = float((g < 10).mean() * 100)
        # Miniatur (Farbe)
        im2 = Image.open(f); im2 = ImageOps.exif_transpose(im2); im2.draft("RGB", (700, 700))
        im2 = im2.convert("RGB"); im2.thumbnail((480, 480))
        im2.save(f"{CACHE}/{key}.jpg", quality=85)
        # SIFT
        g9 = g if max(g.shape) <= 960 else cv2.resize(g, None, fx=960 / max(g.shape), fy=960 / max(g.shape), interpolation=cv2.INTER_AREA)
        sift = cv2.SIFT_create(nfeatures=1500)
        kp, d = sift.detectAndCompute(g9, None)
        if d is None:
            d = np.zeros((0, 128), np.uint8); pts = np.zeros((0, 2), np.float32)
        else:
            pts = np.array([k.pt for k in kp], np.float32); d = np.clip(d, 0, 255).astype(np.uint8)
        np.savez(f"{CACHE}/{key}.npz", pts=pts, d=d)
        r["n_sift"] = int(len(pts))
        r["ok"] = True
    except Exception as ex:
        r["ok"] = False; r["fehler"] = repr(ex)
    return r

def liste_ref():
    out = []
    for obj in ("kaufhaus", "martinstor"):
        for f in sorted(glob.glob("/media/oem/scan/rc-park_daten/%s/fotos/*.jp*g" % obj)):
            out.append(("ref_" + obj, obj, os.path.realpath(f)))
    return out

if __name__ == "__main__":
    ref = len(sys.argv) > 1 and sys.argv[1] == "ref"
    L = liste_ref() if ref else liste()
    print(len(L), "Dateien", flush=True)
    with Pool(14) as p:
        res = []
        for i, r in enumerate(p.imap(arbeit, L, chunksize=4)):
            res.append(r)
            if i % 100 == 0: print(i, flush=True)
    json.dump(res, open(AUS + ("/inventar_ref.json" if ref else "/inventar_roh.json"), "w"), indent=0, default=lambda o: float(o) if hasattr(o, "numerator") else str(o))
    print("fehler:", sum(1 for r in res if not r["ok"]))
