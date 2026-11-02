#!/usr/bin/env python3
"""massstab_quelle_gps.py - Massstabsquelle GPS der FOTOS (horizontal, unabhaengig von den Bodenankern) (Register BP).

Foto-EXIF-GPS (Handy/Mapillary/Commons-Fotograf) gegen die Kameraorte des SfM-Modells (messprotokoll/SFM-AUSRICHTUNG-<seite>.json 'kameras', Modellrahmen
in Metern). Je Kamera mit Modellentfernung >= --min-abstand zur Turmachse (Ursprung, LoD2): s = |GPS-Ort| / |Modellort|. Kamerapaare (Basis 20-27 m) sind bei 5-10 m GPS zu
verrauscht (Test: s 1,06-1,31). Aggregat Median + MAD, Unsicherheit per Bootstrap ueber die Kameras. GPS in der Altstadt ist 5-10 m: bei 30-60 m
Basis ca. 10-20 % je Paar - die Quelle taugt als grober, UNABHAENGIGER Gegenpruefer (Bodenanker koennten den Massstab verbiegen), nicht als Feinmassstab.
Weit entfernte Kameras (> --max-entfernung vom Turm; Pose extrapoliert) werden ausgeschlossen. Commons-GPS kann der Motivort statt des Fotografen sein (ANNAHME: Fotografenort).
  /media/oem/scan/venv-seg/bin/python -W ignore -I tools/massstab_quelle_gps.py modelle/<objekt>/objekt.json [--seite nord]
Ausgabe: modelle/<objekt>/audit/massstab_gps.json (Schema massstab_schwarm.py).
"""
import sys, os, json, glob, math, argparse, itertools, numpy as np
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bilder_holen import utm_zu_wgs84  # noqa: F401  (nur um die Abhaengigkeit sichtbar zu halten)

def utm32(lat, lon):
    a = 6378137.0; f = 1 / 298.257222101; e2 = f * (2 - f); ep2 = e2 / (1 - e2); k0 = 0.9996; lon0 = math.radians(9.0)
    la = math.radians(lat); lo = math.radians(lon); N = a / math.sqrt(1 - e2 * math.sin(la) ** 2); T = math.tan(la) ** 2; C = ep2 * math.cos(la) ** 2; A = math.cos(la) * (lo - lon0)
    M = a * ((1 - e2 / 4 - 3 * e2 ** 2 / 64 - 5 * e2 ** 3 / 256) * la - (3 * e2 / 8 + 3 * e2 ** 2 / 32 + 45 * e2 ** 3 / 1024) * math.sin(2 * la) + (15 * e2 ** 2 / 256 + 45 * e2 ** 3 / 1024) * math.sin(4 * la) - (35 * e2 ** 3 / 3072) * math.sin(6 * la))
    return (500000 + k0 * N * (A + (1 - T + C) * A ** 3 / 6 + (5 - 18 * T + T * T + 72 * C - 58 * ep2) * A ** 5 / 120),
            k0 * (M + N * math.tan(la) * (A * A / 2 + (5 - T + 9 * C + 4 * C * C) * A ** 4 / 24 + (61 - 58 * T + T * T + 600 * C - 330 * ep2) * A ** 6 / 720)))

def dms(v, r):
    d = float(v[0]) + float(v[1]) / 60 + float(v[2]) / 3600; return -d if r in ("S", "W") else d

def gps_fotos(ordner):
    out = {}
    for f in sorted(glob.glob(os.path.join(ordner, "*"))):
        try: g = Image.open(f).getexif().get_ifd(0x8825)
        except Exception: continue
        if g.get(2) and g.get(4): out[os.path.basename(f)[:3]] = (dms(g[2], g[1]), dms(g[4], g[3]))
    return out

def schaetze(P_gps, P_mod, min_abstand):
    """P_*: {foto: (x, y)} gleiche Schluessel -> Liste (paar, s)."""
    ks = sorted(P_gps); R = []
    for a, b in itertools.combinations(ks, 2):
        dm = float(np.hypot(*(np.array(P_mod[a]) - np.array(P_mod[b])))); dg = float(np.hypot(*(np.array(P_gps[a]) - np.array(P_gps[b]))))
        if dm >= min_abstand: R.append(((a, b), dg / dm, dm))
    return R

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--seite", default="nord"); ap.add_argument("--min-abstand", type=float, default=20.0)
    ap.add_argument("--max-entfernung", type=float, default=150.0); ap.add_argument("--boot", type=int, default=500); ap.add_argument("--ordner")
    a = ap.parse_args(); od = os.path.dirname(os.path.abspath(a.objekt)); obj = json.load(open(a.objekt)); A = json.load(open(os.path.join(od, "anker3d.json")))
    Em, Nm = A["mitte_utm"]; xh = np.array(A["xhat_utm"]); yh = np.array(A["yhat_utm"])
    kam = json.load(open(os.path.join(od, "messprotokoll", f"SFM-AUSRICHTUNG-{a.seite}.json")))["kameras"]
    G = gps_fotos(a.ordner or os.path.realpath(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), obj["fotos_dir"])))
    Pg, Pm, ausg = {}, {}, {}
    for k, c in kam.items():
        if k not in G: continue
        E, N = utm32(*G[k]); d = np.array([E - Em, N - Nm]); g = (float(d @ xh), float(d @ yh)); m = (c["standort"][0], c["standort"][1])
        if math.hypot(*m) > a.max_entfernung: ausg[k] = f"Modellabstand {math.hypot(*m):.0f} m > {a.max_entfernung:.0f} m (Pose extrapoliert)"; continue
        Pg[k] = g; Pm[k] = m
    # Primaer: Entfernung Kamera -> Turmachse (Ursprung des Modellrahmens aus LoD2, unabhaengig vom GPS): Basis 30-65 m statt 20-27 m der Kamerapaare
    R = [((k, "turm"), math.hypot(*Pg[k]) / math.hypot(*Pm[k]), math.hypot(*Pm[k])) for k in sorted(Pg) if math.hypot(*Pm[k]) >= a.min_abstand]; out = dict(quelle="gps_fotos", richtung="horizontal", s_definition="wahre Meter / Modellmeter, 1.0 = konsistent",
        unabhaengig_von=["Bodenanker", "LoD2", "DOM1", "Fotopicks"], abhaengig_von=["Kameraorte des Netzes (Netzgeometrie, nicht deren Massstab)"],
        annahmen=["ANNAHME: EXIF-GPS = Ort des Fotografen (Commons kann Motivort sein); Altstadt-GPS 5-10 m", f"ANNAHME: Kameras > {a.max_entfernung:.0f} m vom Turm ausgeschlossen"],
        blind=["keine Hoehe (GPS-Hoehe +-10 m)", "grob: 10-20 % je Paar"], ausgeschlossen=ausg, kameras=sorted(Pg))
    if len(R) < 3: out.update(schaetzungen=[], n=len(R), median=None, mad=None, sigma=None, hinweis=f"zu wenige Kameras ({len(R)}) aus {len(Pg)} Kameras mit GPS im Netz"); print(out["hinweis"])
    else:
        s = np.array([r[1] for r in R]); md = float(np.median(s)); mad = float(np.median(abs(s - md))); rng = np.random.default_rng(1)
        bs = [float(np.median(rng.choice(s, len(s), replace=True))) for _ in range(a.boot)]; sig = float(np.std(bs)) if len(s) >= 3 else None
        out.update(schaetzungen=[dict(id=f"{p[0]}-{p[1]}", wert_s=round(v, 4), abstand_modell_m=round(d, 1), beleg=f"GPS-Entfernung/Modellentfernung Kamera {p[0]} zur Turmachse") for p, v, d in R], n=len(R), n_kameras=len(Pg), median=round(md, 4), mad=round(mad, 4), sigma=(round(sig, 4) if sig else None))
        print(f"GPS-Quelle: {len(Pg)} Kameras: s = {md:.3f}  MAD {mad:.3f}  Bootstrap-Sigma {sig if sig is None else round(sig, 3)}  (ausgeschlossen: {ausg})")
    os.makedirs(os.path.join(od, "audit"), exist_ok=True); json.dump(out, open(os.path.join(od, "audit", "massstab_gps.json"), "w"), indent=1, ensure_ascii=False)

if __name__ == "__main__":
    main()
