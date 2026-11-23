"""Kamerazentren-Probe eichen: richtige Kopplungen (Selbsttests mit Wahrheit + 1122) vs. Spiegel (Punkte + Kameras gespiegelt)."""
import sys, glob, os, json, numpy as np, pycolmap
W = "/home/oem/git/rc-park/.claude/worktrees/agent-a38678dacd05d031c/tools"; sys.path.insert(0, W)
import seiten_eck_koppeln as EK
from sim3_robust import anwenden


def spiegel(Y, P):
    c = np.median(P, 0); _, _, Vt = np.linalg.svd(P - c, full_matrices=False); n = Vt[1]; return Y - 2 * np.outer((Y - c) @ n, n)


def probe(E, Z, tag):
    ausd = EK.ausdehnung([p.xyz for p in E.points3D.values()]); P = np.array([p.xyz for p in Z.points3D.values()]); az = EK.ausdehnung(P)
    X, Y, ns, td = EK.punkte(E, Z, mit_tiefe=True)
    if len(ns) < 3 or len(X) < 100: return
    eE = {im.name: im for im in E.images.values() if im.has_pose}; eZ = {im.name: im for im in Z.images.values() if im.has_pose}
    CX = np.array([eE[n].projection_center() for n in ns]); CY = np.array([eZ[n].projection_center() for n in ns])
    for art in ("richtig", "spiegel"):
        Yv, CYv = (Y, CY) if art == "richtig" else (spiegel(Y, P), spiegel(CY, P))
        M, pr, ok, g = EK.kopplung_pruefen(X, Yv, ausd, az, tiefe=td)
        if M is None: print(tag, art, "keine Sim3"); continue
        s = np.cbrt(np.linalg.det(M[:3, :3])); d = np.linalg.norm(anwenden(M, CX) - CYv, axis=1) / (s * np.median(td))
        print(f"{tag:45s} {art:8s} ok={ok!s:5s} ant={pr['anteil']} kam_med={np.median(d):.4f} kam_max={d.max():.4f} n={len(ns)}", flush=True)


for o in sorted(glob.glob("/media/oem/rcdaten/tmp/durchblick/selbst_*/k*")):
    if not os.path.isfile(o + "/stufe/eck.json"): continue
    T = {"A": pycolmap.Reconstruction(o + "/teilA"), "B": pycolmap.Reconstruction(o + "/teilB")}
    for m in sorted(glob.glob(o + "/stufe/zwischen*/sparse/*/images.bin"))[:6]:
        E = pycolmap.Reconstruction(os.path.dirname(m))
        for t, Z in T.items(): probe(E, Z, o.split("durchblick/")[1] + "/" + m.split("stufe/")[1][:22] + t)
A = "/media/oem/rcdaten/tmp/bruecke_sued_agent"
for m in ("eck/sparse/1", "m_fest_s20/sparse/1"):
    E = pycolmap.Reconstruction(A + "/" + m)
    for t in (0, 1): probe(E, pycolmap.Reconstruction(f"{A}/teil{t}"), "1122t/" + m + str(t))
