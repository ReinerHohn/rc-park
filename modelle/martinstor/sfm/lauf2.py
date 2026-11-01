#!/usr/bin/env python3
"""lauf2.py - SfM je FASSADENSEITE getrennt (Register AH): Nord- und Suedfotos duerfen nicht gemeinsam gematcht werden,
weil beide Uhrseiten gleich aussehen und COLMAP sie sonst zu EINER Fassade verklebt (Befund 2026-11-01: alle 36 Kameras auf einer Seite).
Dazu: Verkleinern MIT EXIF (PIL), Brennweiten-Prior aus EXIF (f35 oder Modell-Sensorbreite) in der COLMAP-Datenbank.
  /media/oem/scan/venv-colmap/bin/python -I modelle/martinstor/sfm/lauf2.py <seite> <fotonr> [<fotonr> ...]
Schreibt bilder_<seite>/, db_<seite>.db, sparse_<seite>/.
"""
import pycolmap, os, sys, time, glob, sqlite3, numpy as np
from PIL import Image, ExifTags
S = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(os.path.dirname(S)))
FOTOS = os.path.join(ROOT, "daten/martinstor/fotos"); MAXPX = 2000
T = {v: k for k, v in ExifTags.TAGS.items()}
SENSOR_MM = {"Canon EOS 1000D": 22.2, "Canon EOS 5D Mark II": 36.0, "PENTAX Optio 50L": 5.76, "DSC-W5": 7.18, "NIKON D7000": 23.6,
             "Canon PowerShot A650 IS": 7.6, "PENTAX K-5": 23.7, "DSC-S500": 5.76}   # Sensorbreiten (Herstellerangaben, 1/2.5" = 5,76 mm, 1/1.8" = 7,18, 1/1.7" = 7,6)

def exif_f_px(im):
    ex = im.getexif(); exi = ex.get_ifd(0x8769); model = str(ex.get(T["Model"], "")).strip()
    f35 = exi.get(T["FocalLengthIn35mmFilm"]); fmm = exi.get(T["FocalLength"]); L = max(im.size)   # Sensorbreite/36 mm gehoeren zur LANGEN Bildseite (auch im Hochformat)
    if f35: return float(f35) / 36.0 * L, f"f35={f35}"
    if fmm and model in SENSOR_MM: return float(fmm) / SENSOR_MM[model] * L, f"{model} {float(fmm):.1f} mm / {SENSOR_MM[model]} mm"
    return None, (f"{model} {fmm} mm ohne Sensorbreite" if fmm else "kein EXIF")

def main():
    seite = sys.argv[1]; nrs = sys.argv[2:]; bilder = os.path.join(S, f"bilder_{seite}"); db = os.path.join(S, f"db_{seite}.db"); aus = os.path.join(S, f"sparse_{seite}")
    os.makedirs(bilder, exist_ok=True); os.makedirs(aus, exist_ok=True)
    if os.path.exists(db): os.remove(db)
    prior = {}
    for nr in nrs:
        p = glob.glob(os.path.join(FOTOS, nr + "_*"))[0]; im = Image.open(p); im = im.convert("RGB") if im.mode != "RGB" else im
        fpx, grund = exif_f_px(im); s = min(1.0, MAXPX / max(im.size))
        im2 = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS) if s < 1 else im
        kw = {"exif": im.info["exif"]} if "exif" in im.info else {}
        im2.save(os.path.join(bilder, nr + ".jpg"), quality=95, **kw)
        if fpx: prior[nr + ".jpg"] = fpx * s
        print(f"  {nr}: {im.width}x{im.height} -> {im2.width}x{im2.height}, Brennweite {'%.0f px' % (fpx * s) if fpx else '-'} ({grund})", flush=True)
    t0 = time.time()
    pycolmap.extract_features(db, bilder, camera_mode=pycolmap.CameraMode.PER_IMAGE)
    # Brennweiten-Prior setzen (COLMAP liest EXIF selbst nur bei f35 bzw. bekannter Sensor-DB; hier explizit)
    con = sqlite3.connect(db); cur = con.cursor(); gesetzt = 0
    for img_id, name, cam_id in cur.execute("select image_id, name, camera_id from images").fetchall():
        if name not in prior: continue
        model, w, h, params, pf = cur.execute("select model, width, height, params, prior_focal_length from cameras where camera_id=?", (cam_id,)).fetchone()
        par = np.frombuffer(params, dtype=np.float64).copy(); par[0] = prior[name]
        cur.execute("update cameras set params=?, prior_focal_length=1 where camera_id=?", (par.tobytes(), cam_id)); gesetzt += 1
    con.commit(); con.close()
    print(f"Merkmale {time.time() - t0:.0f} s, Brennweiten-Prior fuer {gesetzt} von {len(nrs)} Bildern", flush=True)
    t0 = time.time(); pycolmap.match_exhaustive(db); print(f"Zuordnung {time.time() - t0:.0f} s", flush=True)
    t0 = time.time(); karten = pycolmap.incremental_mapping(db, bilder, aus)
    print(f"Aufbau {time.time() - t0:.0f} s, {len(karten)} Teilmodell(e)", flush=True)
    for i, k in karten.items():
        reg = sorted(os.path.splitext(im.name)[0] for im in k.images.values())
        print(f"  Modell {i}: {k.num_reg_images()} von {len(nrs)} Fotos registriert, {k.num_points3D()} Punkte, Reproj {k.compute_mean_reprojection_error():.2f} px; fehlt: {sorted(set(nrs) - set(reg))}", flush=True)
        for im in sorted(k.images.values(), key=lambda im: im.name):
            c = k.cameras[im.camera_id]; print(f"     {im.name} f={c.params[0]:.0f} px ({c.width}x{c.height}) {im.num_points3D} Pkt")

if __name__ == "__main__":
    main()
