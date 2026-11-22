"""GPS-Standorte der Teil-0/1-Fotos per inversem Teil-0-GPS-Fit in den Modellrahmen -> Kreise ins Grundrissbild; Azimute je Teil."""
import sys, os, json, math, numpy as np, cv2
sys.path.insert(0, sys.argv[1]); sys.argv = sys.argv[1:]
import importlib.util
spec = importlib.util.spec_from_file_location("B", os.path.join(sys.argv[0], "versuche", "durchblick_beleg_1122.py")); B = importlib.util.module_from_spec(spec); spec.loader.exec_module(B)
import pycolmap
from paarvorwahl import gps_aus_exif; from netz_fotos_holen import geo; from seiten_erkennen import richtung
A = "/media/oem/rcdaten/tmp/durchblick"; K = "/media/oem/scan/rc-park_daten/schwabentor-1122"
sj = json.load(open(f"{K}/pipe/sfm/seiten.json")); g = sj["gemeinschaft"]; teil = {k: t for t, s in enumerate(sj["seiten"]) for k in s["gruppen"]}; alt = lambda n: teil.get(g.get(n))
r = pycolmap.Reconstruction(f"{A}/sparse/0"); C = {im.name: np.asarray(im.projection_center()) for im in r.images.values() if im.has_pose}
au = json.load(open(f"{A}/eingang/SFM-AUSRICHTUNG-schwabentor-1122.json")); st = {k: np.asarray(v["standort"], float) for k, v in au["kameras"].items() if v.get("standort") is not None}
n0 = [n for n in C if alt(n) == 0 and os.path.splitext(n)[0] in st]
(s, R, t), _ = B.ransac(np.array([C[n] for n in n0]), np.array([st[os.path.splitext(n)[0]] for n in n0]), 1.0); M = lambda X: (s * (R @ np.asarray(X).T)).T + t
mitte = geo(json.load(open(f"{A}/eingang/objekt.json"))); gps = {}; az = {0: [], 1: []}
for n in C:
    if not n.startswith("eigen__") or alt(n) not in (0, 1): continue
    q = gps_aus_exif(os.path.join(f"{K}/fotos", n))
    if q is None: continue
    w, d = richtung(mitte, q)
    if 15 <= d <= 300: gps[n] = np.array([d * math.sin(math.radians(w)), d * math.cos(math.radians(w))]); az[alt(n)].append(w)
for k in (0, 1):
    v = np.radians(az[k]); print(f"Teil {k}: {len(v)} GPS-Fotos, mittlere Standrichtung {np.degrees(np.arctan2(np.sin(v).mean(), np.cos(v).mean())) % 360:.0f} Grad")
nn = [n for n in gps if alt(n) == 0]; X = M(np.array([C[n] for n in nn]))[:, :2]; Y = np.array([gps[n] for n in nn])
(sg, Rg, tg), il = B.ransac(Y, X, 8.0)                       # GPS -> Modellrahmen aus Teil 0
print(f"GPS->Modell aus Teil 0: Drehung {B.dreh(Rg):.1f} Grad, Massstab {sg:.3f}, {len(il)}/{len(nn)} Inlier")
im = cv2.imread(f"{A}/beleg/grundriss_nah.png")
# Rahmen des Bildes wie im Beleg: LoD2-Mitte +-35 m
import wolke_grundriss_pruefen as WG
obj = json.load(open(f"{A}/eingang/objekt.json")); zid = obj["lod2"]["id"]; mz = np.vstack([np.asarray(gf)[:, :2] for b in WG.grundrisse(obj, 60.0) if b["id"] == zid for gf in b["ground"]]).mean(0)
lo = mz - 35; k_ = 960 / 70; px = lambda v: (int(20 + (v[0] - lo[0]) * k_), int(980 - (v[1] - lo[1]) * k_))
d1 = []
for n, q in gps.items():
    p = (sg * (Rg @ q)) + tg; cv2.circle(im, px(p), 6, (200, 60, 0) if alt(n) == 0 else (0, 0, 220), 1)
    if alt(n) == 1: d1.append(np.linalg.norm(p - M(C[n][None])[0, :2]))
print(f"Teil-1-Kameras gegen ihr GPS (GPS ueber Teil-0-Fit im Modellrahmen): Median {np.median(d1):.1f} m, P90 {np.percentile(d1, 90):.1f} m")
cv2.putText(im, "Kreise = GPS-Standorte (ueber Teil-0-GPS-Fit), blau Teil 0, rot Teil 1", (10, 42), 0, 0.5, (0, 0, 0), 1)
cv2.imwrite(f"{A}/beleg/grundriss_gps.png", im); print("->", f"{A}/beleg/grundriss_gps.png")
