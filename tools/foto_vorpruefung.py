#!/usr/bin/env python3
"""foto_vorpruefung.py - Metadaten-Vorpruefung VOR dem Netz (Register BI): taugt ein Foto, und von welcher Seite/Entfernung wurde es gemacht?

Je Foto (Ordner mit JPG/PNG/HEIC-Konvertaten, optional ein Manifest mit lat/lon/heading wie tools/mapillary_rip.py):
  - EXIF: Kamera, Brennweite (mm und 35-mm-Aequivalent), Belichtungszeit, ISO, Digitalzoom, Aufnahmezeit, GPS + Richtung (GPSImgDirection)
  - Bildguete: Schaerfe (Laplace-Varianz auf 640 px), Breite
  - Lage zum Objekt (wenn GPS): Entfernung, Seite (nord/sued/ost/west im Modellrahmen aus anker3d.json), Blickwinkel zur Spitze atan((H-h)/d),
    schaut die Kamera zum Objekt (Richtung gegen Peilung)
  - Warnzeichen: unscharf, klein, hoher ISO, lange Belichtung, Digitalzoom, kein Brennweiten-EXIF, zu steiler Blick, schaut weg, alt
GPS in der Altstadt ist ca. 5-10 m, der Kompass 10-20 Grad: die Seite ist ein VORSCHLAG (Register BE: Seitenzuordnung aus Netzen allein ist unsicher),
die Lage taugt zum Aussortieren grober Ausreisser, nicht als genaue Pose.
  /media/oem/scan/venv-seg/bin/python -W ignore tools/foto_vorpruefung.py modelle/<objekt>/objekt.json <ordner> [--manifest <ordner>/manifest.json] [--hoehe 65] [--json aus.json]
(ohne -I: das Skript importiert bilder_holen.utm_zu_wgs84)
"""
import sys, os, json, math, argparse, glob, datetime
import numpy as np, cv2
from PIL import Image, ExifTags
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bilder_holen import utm_zu_wgs84

T = {v: k for k, v in ExifTags.TAGS.items()}; G = {v: k for k, v in ExifTags.GPSTAGS.items()}

def dms(v, ref):
    try: d = float(v[0]) + float(v[1]) / 60 + float(v[2]) / 3600; return -d if ref in ("S", "W") else d
    except Exception: return None

def exif_lesen(fp):
    try: im = Image.open(fp); ex = im.getexif()
    except Exception: return {}, None
    e = ex.get_ifd(0x8769); g = ex.get_ifd(0x8825); r = dict(modell=str(ex.get(T["Model"], "")).strip() or None, mm=e.get(T["FocalLength"]), f35=e.get(T["FocalLengthIn35mmFilm"]),
        belichtung=e.get(T["ExposureTime"]), iso=e.get(T["ISOSpeedRatings"]), zoom=e.get(T["DigitalZoomRatio"]), zeit=e.get(T["DateTimeOriginal"]) or ex.get(T["DateTime"]), breite=im.size[0], hoehe=im.size[1])
    if g.get(G["GPSLatitude"]) is not None and g.get(G["GPSLongitude"]) is not None:
        r["lat"] = dms(g[G["GPSLatitude"]], g.get(G["GPSLatitudeRef"])); r["lon"] = dms(g[G["GPSLongitude"]], g.get(G["GPSLongitudeRef"]))
        if g.get(G.get("GPSImgDirection", -1)) is not None: r["heading"] = float(g[G["GPSImgDirection"]])
    for k in ("mm", "f35", "belichtung", "iso", "zoom"):
        try: r[k] = float(r[k]) if r[k] is not None else None
        except Exception: r[k] = None
    return r, im

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("ordner"); ap.add_argument("--manifest"); ap.add_argument("--hoehe", type=float, default=65.0); ap.add_argument("--json")
    ap.add_argument("--min-schaerfe", type=float, default=40.0); ap.add_argument("--min-breite", type=int, default=1000); ap.add_argument("--max-winkel", type=float, default=55.0)
    a = ap.parse_args(); od = os.path.dirname(os.path.abspath(a.objekt)); A3 = json.load(open(os.path.join(od, "anker3d.json")))
    E0, N0 = A3["mitte_utm"]; lat0, lon0 = utm_zu_wgs84(E0, N0); xh, yh = np.array(A3["xhat_utm"]), np.array(A3["yhat_utm"])
    man = {}
    if a.manifest and os.path.exists(a.manifest):
        M = json.load(open(a.manifest)); man = {v["file"]: v for v in (M.get("views") or M.get("images") or []) if isinstance(v, dict) and "file" in v}
    fs = sorted(f for f in glob.glob(os.path.join(a.ordner, "*")) if f.lower().endswith((".jpg", ".jpeg", ".png")))
    R = []; jetzt = datetime.datetime.now()
    for fp in fs:
        nm = os.path.basename(fp); ex, im = exif_lesen(fp); mf = man.get(nm, {}); w = []
        if im is None: R.append(dict(datei=nm, warnungen=["nicht lesbar"])); continue
        g = cv2.imread(fp, cv2.IMREAD_GRAYSCALE); s = 640 / max(g.shape); sh = float(cv2.Laplacian(cv2.resize(g, None, fx=s, fy=s), cv2.CV_64F).var()) if g is not None else 0.0
        for k_, mk in (("modell", "exif_model"), ("f35", "exif_f35")):                 # verkleinerte Commons-Dateien tragen kein EXIF mehr: Manifest (Commons-API) als Rueckfall
            if not ex.get(k_) and mf.get(mk): ex[k_] = mf[mk]
        if mf.get("orig_w"): ex["breite"] = max(ex.get("breite") or 0, int(mf["orig_w"]))                  # Originalbreite statt der heruntergeladenen
        lat = float(mf["lat"]) if mf.get("lat") else ex.get("lat"); lon = float(mf["lon"]) if mf.get("lon") else ex.get("lon"); hd = float(mf["heading"]) if mf.get("heading") else ex.get("heading")
        r = dict(datei=nm, modell=ex.get("modell"), breite=ex.get("breite"), schaerfe=round(sh, 1), iso=ex.get("iso"), belichtung=ex.get("belichtung"), zoom=ex.get("zoom"), f35=ex.get("f35"), zeit=ex.get("zeit"))
        if mf.get("captured_at"): r["zeit"] = datetime.datetime.fromtimestamp(int(mf["captured_at"]) / 1000).strftime("%Y:%m:%d %H:%M:%S")
        if sh < a.min_schaerfe: w.append(f"unscharf ({sh:.0f} < {a.min_schaerfe:.0f})")
        if ex.get("breite", 0) < a.min_breite: w.append(f"klein ({ex.get('breite')} px)")
        if ex.get("iso") and ex["iso"] > 1600: w.append(f"hoher ISO {ex['iso']:.0f}")
        if ex.get("belichtung") and ex["belichtung"] > 1 / 60: w.append(f"lange Belichtung 1/{1 / ex['belichtung']:.0f} s (Verwacklung)")
        if ex.get("zoom") and ex["zoom"] > 1.05: w.append(f"Digitalzoom {ex['zoom']:.1f}x (zugeschnitten)")
        if ex.get("f35") is None and ex.get("mm") is None and not mf: w.append("kein Brennweiten-EXIF")
        if r.get("zeit"):
            try:
                alter = (jetzt - datetime.datetime.strptime(r["zeit"][:19], "%Y:%m:%d %H:%M:%S")).days / 365.25; r["alter_jahre"] = round(alter, 1)
                if alter > 5: w.append(f"alt ({alter:.0f} Jahre, Fassaden koennen sich geaendert haben)")
            except Exception: pass
        if lat is not None and lon is not None:
            dE = (lon - lon0) * math.cos(math.radians(lat0)) * 111320.0; dN = (lat - lat0) * 110574.0; x = dE * xh[0] + dN * xh[1]; y = dE * yh[0] + dN * yh[1]; d = math.hypot(x, y)
            seite = ("sued" if x > 0 else "nord") if abs(x) >= abs(y) else ("ost" if y > 0 else "west"); wk = math.degrees(math.atan2(a.hoehe - 1.6, max(d, 1.0)))
            r.update(entfernung_m=round(d, 0), seite_vorschlag=seite, winkel_spitze=round(wk, 0), x=round(x, 0), y=round(y, 0))
            if wk > a.max_winkel: w.append(f"steiler Blick zur Spitze ({wk:.0f} Grad, {d:.0f} m)")
            if hd is not None and mf.get("camera_type") != "spherical":
                peil = (math.degrees(math.atan2(-dE, -dN)) + 360) % 360     # Peilung Kamera -> Objekt (Grad von Nord)
                dl = abs((hd - peil + 180) % 360 - 180); r["blick_abweichung"] = round(dl, 0)
                if dl > 60: w.append(f"schaut vom Turm weg (Richtung {hd:.0f}, Peilung {peil:.0f}, Abweichung {dl:.0f} Grad)")
        r["warnungen"] = w; R.append(r)
    ok = [r for r in R if not r.get("warnungen")]; print(f"{len(R)} Fotos, {len(ok)} ohne Warnung, {len(R) - len(ok)} mit Warnung")
    from collections import Counter
    c = Counter(r["seite_vorschlag"] for r in R if r.get("seite_vorschlag")); print("Seiten (aus GPS):", dict(c) if c else "kein GPS")
    z = Counter(wm.split(" (")[0].split(" ")[0] + " " + (wm.split(" ")[1] if len(wm.split(" ")) > 1 else "") for r in R for wm in r.get("warnungen", [])); print("Warnungen:", dict(z.most_common()))
    for r in R[:8]: print(f"  {r['datei'][:26]:26} {str(r.get('seite_vorschlag', '-')):5} {str(r.get('entfernung_m', '-')):>5} m  Schaerfe {r.get('schaerfe')}  {'; '.join(r.get('warnungen', []))[:90]}")
    if a.json: json.dump(R, open(a.json, "w"), indent=1, ensure_ascii=False); print("geschrieben:", a.json)

if __name__ == "__main__":
    main()
