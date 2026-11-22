"""GPS-Fit (2D, wie lage_gps_pruefen) nur fuer die gemeinsamen Teil-0-Kameras, beide Laeufe, plus Paarabstaende horizontal."""
import os, sys, json, glob
import numpy as np
sys.path.insert(0, "/home/oem/git/rc-park/.claude/worktrees/agent-a5d004d794431467c/tools")
import lage_gps_pruefen as LGP
OUT = os.path.dirname(os.path.abspath(__file__)); M = "/home/oem/git/rc-park/modelle"
L = json.load(open(f"{OUT}/lagen.json")); teil = {os.path.splitext(k)[0]: v for k, v in L["teil"].items()}
obj = json.load(open(f"{M}/schwabentor-1120/objekt.json")); r = obj["rahmen"]; m0 = np.array(r["mitte_utm"]); xh = np.array(r["xhat_utm"]); yh = np.array(r["yhat_utm"])
fd = "/media/oem/scan/rc-park_daten/schwabentor-1122/fotos"
st0, st1 = L["st"]["schwabentor-1120"], L["st"]["schwabentor-1122"]
gps = {}
for n in sorted(set(st0) | set(st1)):
    hit = glob.glob(os.path.join(fd, glob.escape(n) + ".*")) or glob.glob(os.path.join("/media/oem/scan/rc-park_daten/schwabentor-1120/fotos", glob.escape(n) + ".*"))
    g = LGP.gps_exif(hit[0]) if hit else None
    g = [float(x) for x in g] if g else None
    if g and all(np.isfinite(g)) and abs(g[0]) > 1e-6: gps[n] = np.array(LGP.wgs84_zu_utm(*g)) - m0
def fit(namen, st):
    MU = np.array([st[n][:2] for n in namen]); MU = MU[:, 0:1] * xh + MU[:, 1:2] * yh; G = np.array([gps[n] for n in namen])
    rc, e = LGP.urteil(namen, MU, G); return e.get("gps_fit"), e.get("ransac")
import contextlib, io
for name, wahl in (("Teil0 gemeinsam", lambda n: teil.get(n) == 0), ("Teil1 gemeinsam", lambda n: teil.get(n) == 1), ("alle gemeinsam", lambda n: True)):
    nm = [n for n in sorted(set(st0) & set(st1) & set(gps)) if wahl(n)]
    for o, st in (("1120", st0), ("1122", st1)):
        with contextlib.redirect_stdout(io.StringIO()): g, ra = fit(nm, st)
        print(f"{name} n {len(nm)} Lauf {o}: Drehung {g['drehung_grad']:+.2f} Grad, Massstab {g['massstab']:.3f} (90%: {g['massstab_90'][0]:.3f}..{g['massstab_90'][1]:.3f}), Rest {g['rest_median_m']:.1f} m, RANSAC {ra}")
# 1120 voll (alle 1120-Kameras mit GPS) wie das Tor: welche Kameras tragen den Fit?
sys.path.insert(0, OUT); from eingaben_gruppe import gruppe
import collections
for o, st in (("1120", st0), ("1122", st1)):
    nm = [n for n in sorted(st) if n in gps]; MU = np.array([st[n][:2] for n in nm]); MU = MU[:, 0:1] * xh + MU[:, 1:2] * yh; G = np.array([gps[n] for n in nm])
    with contextlib.redirect_stdout(io.StringIO()): rc, e = LGP.urteil(nm, MU, G)
    g = e["gps_fit"]; th = np.radians(g["drehung_grad"]); Rm = np.array([[np.cos(th), -np.sin(th)], [np.sin(th), np.cos(th)]])
    P = MU @ Rm.T * g["massstab"]; t = np.median(G - P, 0); res = np.hypot(*(P + t - G).T); inl = res < 10
    print(f"Lauf {o} voll: n {len(nm)} Drehung {g['drehung_grad']:+.2f} x{g['massstab']:.3f} RANSAC {e.get('ransac')}; Inlier<10m je Teil(1122):", dict(collections.Counter((teil.get(n, 'kein'), bool(i)) for n, i in zip(nm, inl))))
    print("    je Gruppe Inlier/n:", {k: f"{sum(1 for n, i in zip(nm, inl) if gruppe(n) == k and i)}/{sum(1 for n in nm if gruppe(n) == k)}" for k in sorted(set(gruppe(n) for n in nm))})
    fern = [n for n in nm if np.hypot(*gps[n]) >= 100]
    for n in fern:
        mu = MU[nm.index(n)]; print(f"    FERN {o} {n[:60]}: GPS {np.hypot(*gps[n]):.0f} m, Modell {np.hypot(*mu):.0f} m, Richtung GPS {np.degrees(np.arctan2(gps[n][1], gps[n][0])):.1f} Modell {np.degrees(np.arctan2(mu[1], mu[0])):.1f}, in 1122 {n in st1}, Teil {teil.get(n)}")
    if o == "1120":
        nur = [n for n in nm if n not in st1]; print("    1120-GPS-Kameras, die in 1122 fehlen:", len(nur), dict(collections.Counter(gruppe(n) for n in nur)))
