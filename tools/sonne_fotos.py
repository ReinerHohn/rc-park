#!/usr/bin/env python3
"""sonne_fotos.py - Sonnenstand + Sonnenschein je Foto (2026-11-05, Nutzeridee: Schattenkarte aus Datum/Zeit, mit Wetter abgleichen).

Je Foto mit EXIF-Aufnahmezeit: UTC (OffsetTimeOriginal, sonst ANNAHME Europe/Berlin), Sonnenstand (schatten.sonnenstand, NOAA), Sonnenrichtung im
Modellrahmen (Meridiankonvergenz UTM 32 + objekt.json rahmen.xhat/yhat) und DWD-Sonnenscheindauer der Stunde (Station aus --dwd-station, Open Data
opendata.dwd.de CDC hourly/sun, Lizenz CC BY 4.0 "Deutscher Wetterdienst"). EXIF-Uhren sind oft falsch -> Ergebnis = VORHERSAGE; die Bestaetigung
macht die Schattensuche am Foto (Widerspruch = offene Beobachtung, nicht mitteln). Schreibt modelle/<obj>/sonne.json.

  python3 tools/sonne_fotos.py modelle/<obj>/objekt.json [--dwd /media/oem/scan/rc-park_daten/dwd]
"""
import os, sys, json, glob, math, argparse, datetime as dt
from zoneinfo import ZoneInfo
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from schatten import sonnenstand


def dwd_laden(d):
    S = {}
    for p in glob.glob(os.path.join(d, "*", "produkt_sd_stunde_*.txt")):
        for ln in open(p, encoding="latin-1"):
            f = ln.split(";")
            if len(f) < 4 or not f[1].strip().isdigit(): continue
            v = float(f[3]);
            if v >= 0: S[f[1].strip()] = v                                                            # MESS_DATUM YYYYMMDDHH (UTC, Stundenende), Minuten Sonnenschein
    return S


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--dwd", default="/media/oem/scan/rc-park_daten/dwd"); a = ap.parse_args(argv)
    from PIL import Image
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(a.objekt)))); obj = json.load(open(a.objekt)); la, lo = obj["lage"]["lat"], obj["lage"]["lon"]
    gam = (lo - 9.0) * math.sin(math.radians(la))                                                     # Meridiankonvergenz UTM 32 (Grad, Gitternord ostwaerts von geogr. Nord positiv)
    xh, yh = obj["rahmen"]["xhat_utm"], obj["rahmen"]["yhat_utm"]; S = dwd_laden(a.dwd); erg = {}
    for p in sorted(glob.glob(os.path.join(root, obj["fotos_dir"], "*"))):
        nr = os.path.basename(p)[:3]
        try: ex = Image.open(p).getexif(); sub = ex.get_ifd(0x8769); t = sub.get(36867) or ex.get(306); oz = sub.get(36881)
        except Exception: continue
        if not t: continue
        try: lok = dt.datetime.strptime(str(t).strip()[:19], "%Y:%m:%d %H:%M:%S")
        except ValueError: continue
        if oz: h_, m_ = int(oz[:3]), int(oz[0] + oz[4:6]); utc = lok - dt.timedelta(hours=h_, minutes=m_); zq = f"EXIF-Offset {oz}"
        else: utc = lok.replace(tzinfo=ZoneInfo("Europe/Berlin")).astimezone(dt.timezone.utc).replace(tzinfo=None); zq = "ANNAHME Europe/Berlin (kein Offset)"
        az, el = sonnenstand(utc, la, lo); ag = math.radians(az - gam); e_ = math.cos(math.radians(el))
        ve, vn = math.sin(ag) * e_, math.cos(ag) * e_; s = [ve * xh[0] + vn * xh[1], ve * yh[0] + vn * yh[1], math.sin(math.radians(el))]
        sd = S.get((utc + dt.timedelta(hours=1)).strftime("%Y%m%d%H"))                                  # Stunde, die nach utc endet
        erg[nr] = dict(exif=str(t), zeitzone=zq, utc=utc.isoformat(), azimut=round(az, 1), hoehe=round(el, 1), sonne_modell=[round(x, 4) for x in s],
                       dwd_sonne_min=sd, urteil=("Nacht" if el <= 0 else "Sonne" if (sd or 0) >= 30 else "bedeckt" if sd is not None and sd <= 5 else "unklar"))
    out = os.path.join(os.path.dirname(os.path.abspath(a.objekt)), "sonne.json")
    json.dump(dict(quelle="EXIF + NOAA-Sonnenstand + DWD Stundenwerte Sonnenschein (CC BY 4.0, Deutscher Wetterdienst)", fotos=erg), open(out, "w"), indent=1)
    from collections import Counter
    print(f"{len(erg)} Fotos mit Zeit -> {out}; Urteil: {dict(Counter(v['urteil'] for v in erg.values()))}")


if __name__ == "__main__":
    main()
