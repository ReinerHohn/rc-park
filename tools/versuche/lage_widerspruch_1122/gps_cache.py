import sys, os, json, glob, math
S = "/tmp/claude-29999/-home-oem-git-rc-park/dc62add2-9ee3-4f76-85e0-42c96eea284b/scratchpad/"
sys.path.insert(0, S + "wt/tools")
from gps_ausrichtung import gps_exif
from bilder_holen import wgs84_zu_utm
import numpy as np
obj = json.load(open(S + "obj22/objekt.json")); r = obj["rahmen"]
m0 = np.array(r["mitte_utm"]); xh = np.array(r["xhat_utm"]); yh = np.array(r["yhat_utm"])
fd = sys.argv[1] if len(sys.argv) > 1 else "/media/oem/scan/rc-park_daten/schwabentor-1122/fotos"
ziel = sys.argv[2] if len(sys.argv) > 2 else "e/gps.json"
out = {}
for p in sorted(glob.glob(fd + "/*.jp*g")):
    g = gps_exif(p)
    if not g: continue
    try:
        if not all(math.isfinite(float(x)) for x in g) or (abs(float(g[0])) < 1e-6 and abs(float(g[1])) < 1e-6): continue
    except Exception: continue
    u = np.array(wgs84_zu_utm(*g)) - m0
    # in Objektrahmen (x,y): UTM = x*xh + y*yh -> x = u.xh, y = u.yh (orthonormal)
    out[os.path.splitext(os.path.basename(p))[0]] = dict(utm_rel=u.tolist(), obj=[float(u @ xh), float(u @ yh)])
json.dump(out, open(S + ziel, "w"))
if len(sys.argv) > 2:
    a = json.load(open(S + "e/gps.json")); b = out
    c = [k for k in a if k in b]; d = np.array([np.hypot(*(np.array(a[k]["obj"]) - np.array(b[k]["obj"]))) for k in c])
    print("gemeinsam", len(c), "nur1122", len(set(a) - set(b)), "nur ziel", len(set(b) - set(a)), "Abstand median", np.median(d) if len(d) else None, "n>1m", int((d > 1).sum()))
print(len(out), "mit GPS")
import collections; print(collections.Counter(k.split("__")[0] for k in out))
