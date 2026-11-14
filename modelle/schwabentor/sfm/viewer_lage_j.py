"""3D-Vergleich alte Lage vs. Variante J (Schwabentor) mit LoD2-Waenden, Kameras und GPS -> HTML (three.js).
Aufruf: python -I viewer_lage_j.py <ausgabe.html>"""
import sys, json, pickle, base64, struct, numpy as np
from scipy.spatial.transform import Rotation as Rot
R0 = "/home/oem/git/rc-park/"; S = R0 + "modelle/schwabentor/sfm/"
sys.path.insert(0, S); sys.path.insert(0, R0 + "tools")
import variante_i as VI, variante_j as VJ
from sichtrichtung_kohaerenz import fused_xyz
from gps_ausrichtung import gps_exif
from bilder_holen import wgs84_zu_utm

obj = json.load(open(R0 + "modelle/schwabentor/objekt.json")); r = obj["rahmen"]
m0 = np.array(r["mitte_utm"]); xh = np.array(r["xhat_utm"]); yh = np.array(r["yhat_utm"])
X0 = np.load(S + "punkte_modell_schwabentor.npy").astype(float); C = np.load(S + "punkte_farben_schwabentor.npy")
F = VJ.fluegel_maske(X0); XJ = VJ.lage_j(X0, F)
toU = lambda X: np.c_[X[:, 0:1] * xh + X[:, 1:2] * yh, X[:, 2]]
UA, UJ = toU(X0), toU(XJ)
ok = (np.hypot(UA[:, 0], UA[:, 1]) < 60) & (np.hypot(UJ[:, 0], UJ[:, 1]) < 60)
rng = np.random.default_rng(0)
idx = np.r_[rng.choice(np.flatnonzero(ok & ~F), 230000, replace=False), rng.choice(np.flatnonzero(ok & F), 40000, replace=False)]
enc = lambda A: base64.b64encode(np.round(A * 100).astype(np.int16).tobytes()).decode()
col = C[idx].astype(np.uint8) if C.max() > 1 else (C[idx] * 255).astype(np.uint8)

# Kameras (Hauptnetz) in beiden Lagen + GPS
V = np.load(S + "punkte_modell_schwabentor_veto.npy"); c = np.median(V[:, :2], axis=0)
Xf = fused_xyz("/media/oem/scan/rc-park_daten/schwabentor/pipe/dicht/fused.ply"); P = X0 - np.array([c[0], c[1], 0])
fwd = np.linalg.lstsq(np.c_[Xf, np.ones(len(Xf))][::50], P[::50], rcond=None)[0]
names, CC = [], []
with open("/media/oem/scan/rc-park_daten/schwabentor/pipe/dicht/sparse/images.bin", "rb") as f:
    n = struct.unpack("<Q", f.read(8))[0]
    for _ in range(n):
        f.read(4); q = struct.unpack("<4d", f.read(32)); t = np.array(struct.unpack("<3d", f.read(24))); f.read(4); nm = b""
        while (ch := f.read(1)) != b"\x00": nm += ch
        k = struct.unpack("<Q", f.read(8))[0]; f.read(24 * k)
        R = Rot.from_quat([q[1], q[2], q[3], q[0]]).as_matrix(); names.append(nm.decode()); CC.append(-R.T @ t)
CM = np.c_[np.array(CC), np.ones(len(CC))] @ fwd + np.array([c[0], c[1], 0])
CA, CJ = toU(CM), toU(VI.lage_i(CM))
nah = np.hypot(CA[:, 0], CA[:, 1]) < 60
gps = []
for nm_, a in zip(names, CA):
    g = gps_exif("/media/oem/scan/rc-park_daten/schwabentor/pipe/dicht/images/" + nm_)
    if g:
        u = np.array(wgs84_zu_utm(*g)) - m0
        if np.hypot(*u) < 80: gps.append([u[0], u[1], 1.6])
gps = np.array(gps)

# LoD2-Waende als Linien
B = pickle.load(open("/media/oem/scan/rc-park_daten/schwabentor/lod2_umkreis70.pkl", "rb"))
lin = []; hl = []
for b in B:
    for W in b["walls"]:
        Q = np.c_[W[:, :2] - m0, W[:, 2] - b["gz"]]
        if np.hypot(*Q[:, :2].mean(0)) > 50: continue
        for i in range(len(Q)):
            lin.append(np.r_[Q[i], Q[(i + 1) % len(Q)]]); hl.append(1 if b["id"].endswith(("PLcp", "Tvdv")) else 0)
lin = np.array(lin)

D = dict(n=len(idx), nf=40000, alt=enc(UA[idx]), neu=enc(UJ[idx]), col=base64.b64encode(col.tobytes()).decode(),
         kalt=enc(CA[nah]), kneu=enc(CJ[nah]), gps=enc(gps), lod=enc(lin.reshape(-1, 3)), lodh=hl)
tpl = open(S + "viewer_lage_j.tpl.html").read()
open(sys.argv[1], "w").write(tpl.replace("/*__DATA__*/null", json.dumps(D)))
print("geschrieben", sys.argv[1], len(idx), "Punkte,", len(lin), "Wandkanten,", len(gps), "GPS")
