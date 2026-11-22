#!/usr/bin/env python3
"""durchblick_gps_kopplung_1122.py <ausrichtung_kopplung.json> <seiten.json der Kette> <objekt.json> <fotos> - GPS-Probe nach der Eck-Kopplung:
2D-Aehnlichkeit Ausrichtung -> GPS (Ost/Nord um die Objektmitte) aus den Teil-0-Kameras (RANSAC 8 m wie im Beleg), dann Teil-1-Kameras (gekoppelte Lage) gegen ihr eigenes GPS.
Dazu je Teil ein eigener Fit (Drehung/Massstab) - Unterschied = Verdrehung Teil 1 gegen Teil 0 laut GPS."""
import os, sys, json, math, importlib.util, numpy as np
T = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, T)
sp = importlib.util.spec_from_file_location("B", os.path.join(T, "versuche", "durchblick_beleg_1122.py")); B = importlib.util.module_from_spec(sp); sp.loader.exec_module(B)
from paarvorwahl import gps_aus_exif; from netz_fotos_holen import geo; from seiten_erkennen import richtung
au_p, sj_p, obj_p, bilder = sys.argv[1:5]
st = {k: np.asarray(v["standort"], float) for k, v in json.load(open(au_p))["kameras"].items() if v.get("standort") is not None}
sj = json.load(open(sj_p)); g = sj["gemeinschaft"]; teil = {k: t for t, s in enumerate(sj["seiten"]) for k in s["gruppen"]}; mitte = geo(json.load(open(obj_p)))
gps = {}
for n in g:
    k = os.path.splitext(n)[0]
    if not n.startswith("eigen__") or k not in st: continue
    q = gps_aus_exif(os.path.join(bilder, n))
    if q is None: continue
    w, d = richtung(mitte, q)
    if 15.0 <= d <= 300.0: gps[n] = np.array([d * math.sin(math.radians(w)), d * math.cos(math.radians(w))])
fits = {}
for t in (0, 1):
    nn = [n for n in gps if teil.get(g[n]) == t]
    X = np.array([st[os.path.splitext(n)[0]][:2] for n in nn]); Y = np.array([gps[n] for n in nn])
    (s, R, tt), ik = B.ransac(X, Y, 8.0); fits[t] = (s, R, tt, nn, X, Y)
    print(f"Teil {t}: {len(nn)} Geotags, {len(ik)} stimmig, Drehung {B.dreh(R):.1f} Grad, Massstab {s:.3f}, Rest {np.median(np.linalg.norm((s * (R @ X.T)).T + tt - Y, axis=1)[ik]):.2f} m")
s0, R0, t0, *_ = fits[0]; _, _, _, nn1, X1, Y1 = fits[1]
d = np.linalg.norm((s0 * (R0 @ X1.T)).T + t0 - Y1, axis=1)
print(f"Teil 1 gegen GPS ueber den Teil-0-Fit: n {len(d)}, Median {np.median(d):.1f} m, P90 {np.percentile(d, 90):.1f} m")
print(f"Verdrehung Teil 1 gegen Teil 0 laut GPS: {((B.dreh(fits[1][1]) - B.dreh(R0) + 180) % 360 - 180):+.1f} Grad, Massstab {fits[1][0] / s0:.3f}")
