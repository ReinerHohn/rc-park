"""3D-Viewer: Wolke (Fotofarben) + Kantenpunkte + Drahtgitter, Ebenen schaltbar, eigener Canvas-Renderer (kein WebGL noetig).
Aufruf: viewer_kanten_bauen.py OUT.html [--seg SEGMENTE.json] [--kp KANTENPUNKTE.npy] [--n 120000]"""
import sys, json, base64, numpy as np
def opt(n, d, t=str): return t(sys.argv[sys.argv.index(n) + 1]) if n in sys.argv else d
D = "/media/oem/scan/rc-park_daten/kaufhaus_alle"; Wd = "/media/oem/scan/rc-park_null/wolke_gemeinsam/lot2"
P = np.load(Wd + "/j_voll_lot2_crop.npy", mmap_mode="r"); rgb = np.load(Wd + "/j_crop_rgb2.npy", mmap_mode="r"); print("Wolke", P.shape, "RGB", rgb.shape, rgb.dtype, flush=True)
rng = np.random.default_rng(0); N = opt("--n", 120000, int); idx = np.sort(rng.choice(len(P), N, replace=False)); W = np.asarray(P[idx]); C = np.asarray(rgb[idx]); C = (C * 255 if C.dtype != np.uint8 and C.max() <= 1.01 else C).astype(np.uint8)
KP = np.load(opt("--kp", D + "/tsweep80_konsens.npy")); KP = KP[rng.choice(len(KP), min(len(KP), 60000), replace=False)]
S = json.load(open(opt("--seg", D + "/segmente_karte4.json")))["segmente"]
ctr = np.median(W, axis=0); SC = 400.0
def q(a): return base64.b64encode(np.round((np.asarray(a, np.float32) - ctr) * SC).astype("<i2").tobytes()).decode()
seg = np.array([[*s[0], *s[1]] for s in S], np.float32); sq = np.array([s[2] for s in S], np.uint8)
data = {"ctr": ctr.tolist(), "sc": SC, "w": q(W), "c": base64.b64encode(C.tobytes()).decode(), "k": q(KP), "s": q(seg.reshape(-1, 3)), "sq": base64.b64encode(sq.tobytes()).decode(), "nw": len(W), "nk": len(KP), "ns": len(S)}
html = open(__file__.replace("viewer_kanten_bauen.py", "viewer_kanten_vorlage.html")).read().replace("/*DATA*/", "const DATA=" + json.dumps(data) + ";")
open(sys.argv[1], "w").write(html); print("geschrieben", sys.argv[1], len(html) // 1024, "KB")
