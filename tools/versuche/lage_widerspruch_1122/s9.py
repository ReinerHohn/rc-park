import json, glob, numpy as np, collections, os
from PIL import Image
S = "/tmp/claude-29999/-home-oem-git-rc-park/dc62add2-9ee3-4f76-85e0-42c96eea284b/scratchpad/"
GPS = json.load(open(S + "e/gps.json"))
K20 = json.load(open(glob.glob(S + "obj20/messprotokoll/SFM-AUSRICHTUNG-*.json")[0]))["kameras"]
fd = "/media/oem/scan/rc-park_daten/schwabentor-1122/fotos/"
rows = []
for n, g in GPS.items():
    if n not in K20 or not K20[n].get("standort"): continue
    p = glob.glob(fd + n + ".*")
    try:
        ex = Image.open(p[0])._getexif() or {}; t = ex.get(36867) or ex.get(306)
    except Exception: t = None
    M = np.array(K20[n]["standort"][:2]); G = np.array(g["obj"])
    if np.hypot(*G) > 100: continue
    rows.append((t or "", n, M, G))
rows.sort()
print("n", len(rows))
# Sitzungen: Zeitluecke > 10 min
import datetime
def ts(t):
    try: return datetime.datetime.strptime(t, "%Y:%m:%d %H:%M:%S")
    except Exception: return None
sess = []; last = None; k = -1
for t, n, M, G in rows:
    tt = ts(t)
    if tt is None: sess.append(-1); continue
    if last is None or (tt - last).total_seconds() > 600: k += 1
    sess.append(k); last = tt
D = np.array([G - M for _, _, M, G in rows]); Ms = np.array([M for _, _, M, _ in rows])
az = np.degrees(np.arctan2(Ms[:, 1] - 15, Ms[:, 0] + 2))
for k in sorted(set(sess)):
    w = np.array(sess) == k
    tt = [rows[i][0] for i in np.flatnonzero(w)]
    d = D[w]; good = np.hypot(*(d - np.median(d, 0)).T) < 10
    print(f"Sitzung {k}: n {w.sum()} {tt[0][:16]}..{tt[-1][11:16]}  GPS-Kamera Median {np.median(d[good],0).round(1)} m (|{np.hypot(*np.median(d[good],0)):.1f}|), Streuung {np.median(np.hypot(*(d[good]-np.median(d[good],0)).T)):.1f}; Kameras Mitte {np.median(Ms[w],0).round(1)}")
for a0 in range(-180, 180, 60):
    w = (az >= a0) & (az < a0 + 60)
    if w.sum() < 4: continue
    d = D[w]; print(f"Richtung {a0:+4d}..{a0+60:+4d} Grad: n {w.sum()} GPS-Kamera Median {np.median(d,0).round(1)} m, Abstand zur Turmmitte Kamera {np.median(np.hypot(Ms[w,0]+2, Ms[w,1]-15)):.1f} m")
np.save(S + "e/gps_rest20.npy", np.c_[Ms, D, np.array(sess)])
