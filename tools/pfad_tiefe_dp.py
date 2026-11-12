#!/usr/bin/env python3
"""pfad_tiefe_dp.py - Tiefe je Pfad per Mehrfoto-Optimierung: 2D-Pixel der Kette in der Referenzkamera sind fest, die Tiefe entlang jedes Strahls wird per Viterbi-DP so gewaehlt, dass die Projektion in vielen Nahfotos auf Kanten (Distanztransformation der Stabilitaetskarte) faellt und die Tiefe entlang der Kette glatt bleibt.
Aufruf: pfad_tiefe_dp.py OBJ.json KETTEN.json --kam K-6171 --box "x0,y0,z0,x1,y1,z1" [--band 0.6] [--schritt 0.01] [--lambda 3] [--opt N_FOTOS 8] [--pruef_fotos a.jpg,b.jpg] [--min_m 0.6] [--aus DIR --name N]
Ablauf: je Kette Pixel (Feld 'pixel', Schritt 8 px) -> Strahl x Modellflaeche = Startttiefe t0 -> Kandidaten t0 +- band -> Kosten = mittlere Kantenentfernung (px, bei 10 gekappt) in den Optimierfotos -> DP mit Glattheit (lambda * (dt/0,03)^2) -> Spline -> Pruefkosten in zurueckgehaltenen Fotos VORHER (Flaechentiefe) und NACHHER; Gewinn = Verbesserung der Pruefkosten.
Ausgabe: DIR/tiefe_<name>.json (wie Ketten + kosten_vorher, kosten_nachher (Pruef), n_opt, n_pruef)."""
import sys, os, json, glob, importlib.util
import numpy as np, cv2, trimesh
from scipy.interpolate import splprep, splev
_d = os.path.dirname(os.path.abspath(__file__))
s_ = importlib.util.spec_from_file_location("epilinie", os.path.join(_d, "epilinie.py")); EPI = importlib.util.module_from_spec(s_); s_.loader.exec_module(EPI)
a = sys.argv[1:]
if len(a) < 6: sys.exit(__doc__)
opt = lambda n, d: a[a.index(n) + 1] if n in a else d
obj = json.load(open(a[0])); root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(a[0])))); od = os.path.join(root, os.path.dirname(obj["masstabelle"]))
F = json.load(open(a[1])); kam = opt("--kam", "K-6171"); bx = [float(v) for v in opt("--box", "").split(",")]; band = float(opt("--band", 0.6)); st = float(opt("--schritt", 0.01)); LAM = float(opt("--lambda", 3)); MINM = float(opt("--min_m", 0.6)); aus = opt("--aus", "."); name = opt("--name", "tiefe")
D = "/media/oem/scan/rc-park_daten/kaufhaus_alle"; KAM = json.load(open(D + "/sfm/kam_lot2.json"))
alle = opt("--fotos", "ip_IMG_6173.jpg,ip_IMG_6177.jpg,ip_IMG_6249.jpg,ip_IMG_6250.jpg,ip_IMG_6251.jpg,ip_IMG_6172.jpg,ip_IMG_6168.jpg,ip_IMG_6180.jpg,ip_IMG_6185.jpg").split(",")
pruef = opt("--pruef_fotos", "ip_IMG_6177.jpg,ip_IMG_6251.jpg,ip_IMG_6168.jpg").split(","); optf = [f for f in alle if f not in pruef]
DT = {}
for f in alle:
    sm = cv2.imread(f"{D}/stabil/{f[:-4]}.png", 0); DT[f] = (cv2.distanceTransform((sm < 255 * 0.4).astype(np.uint8), cv2.DIST_L2, 3).astype(np.float32), sm.shape[1] / KAM[f]["W"])
def proj(c, P):
    R = np.array(c["Rn"]); q = P @ R.T + np.array(c["tn"]); x = q[:, 0] / q[:, 2]; y = q[:, 1] / q[:, 2]; s = 1 + c["params"][3] * (x * x + y * y); return np.c_[c["f"] * x * s + c["cx"], c["f"] * y * s + c["cy"]], q[:, 2]
import torch
dev = "cuda" if torch.cuda.is_available() else "cpu"
DTT = {f: torch.from_numpy(v[0]).to(dev) for f, v in DT.items()}
KT = {f: dict(R=torch.tensor(KAM[f]["Rn"], dtype=torch.float32, device=dev), t=torch.tensor(KAM[f]["tn"], dtype=torch.float32, device=dev), f=KAM[f]["f"], cx=KAM[f]["cx"], cy=KAM[f]["cy"], k1=KAM[f]["params"][3]) for f in alle}
def kosten(P, fl):                                                  # GPU: P (n,3) -> mittlere Kantenentfernung (px, <= 10) ueber Fotos
    Pt = torch.as_tensor(np.asarray(P), dtype=torch.float32, device=dev); tot = torch.zeros(len(Pt), device=dev)
    for f in fl:
        c = KT[f]; q = Pt @ c["R"].T + c["t"]; x = q[:, 0] / q[:, 2]; y = q[:, 1] / q[:, 2]; sk = 1 + c["k1"] * (x * x + y * y); sc = DT[f][1]
        px = ((c["f"] * x * sk + c["cx"]) * sc).round().long(); py = ((c["f"] * y * sk + c["cy"]) * sc).round().long(); dt = DTT[f]; ok = (q[:, 2] > 0.5) & (px >= 0) & (px < dt.shape[1]) & (py >= 0) & (py < dt.shape[0])
        v = torch.full((len(Pt),), 10.0, device=dev); v[ok] = torch.clamp(dt[py[ok], px[ok]], max=10.0); tot += v
    return (tot / len(fl)).cpu().numpy()
K = EPI.kam(od, kam); kk = json.load(open(os.path.join(od, "messprotokoll", kam + ".json")))["kamera"]
m = trimesh.load(os.path.join(root, obj["stl"])); m.apply_scale(obj.get("stl_massstab", 87) / 1000.0); m.apply_translation(np.asarray(kk.get("rahmen_verschiebung", [0, 0, 0]), float))
ct = m.triangles_center; sel = np.all((ct >= bx[:3]) & (ct <= bx[3:]), axis=1); sub = trimesh.Trimesh(m.vertices, m.faces[sel], process=False); fn = np.asarray(sub.face_normals)
ts = np.arange(-band, band + 1e-9, st); out = []
for ci, f in enumerate(F):
    if f["laenge_m"] < MINM: continue
    px = np.array(f["pixel"], float)
    if len(px) < 8: continue
    o = np.array([EPI.strahl(K, q)[0] for q in px]); d = np.array([EPI.strahl(K, q)[1] for q in px]); loc, ir, it_ = sub.ray.intersects_location(o, d, multiple_hits=False)
    if len(ir) < 8: continue
    px, o, d = px[ir], o[ir], d[ir]; t0 = np.linalg.norm(loc - o, axis=1); t0 = np.interp(np.arange(len(t0)), np.arange(len(t0)), np.convolve(np.pad(t0, 2, mode="edge"), np.ones(5) / 5, mode="valid"))
    Pv = o + d * t0[:, None]; kv = float(kosten(Pv, [x for x in pruef]).mean())
    M = len(px); C = np.zeros((M, len(ts)))
    PP = (o[:, None, :] + d[:, None, :] * (t0[:, None] + ts[None, :])[:, :, None]).reshape(-1, 3); C = kosten(PP, optf).reshape(M, len(ts))                     # alle Kandidaten auf einmal (GPU)
    pen = LAM * ((ts[:, None] - ts[None, :]) / 0.03) ** 2; acc = C[0].copy(); bp = np.zeros((M, len(ts)), int)
    for i in range(1, M):
        tot = acc[:, None] + pen; bp[i] = tot.argmin(0); acc = tot.min(0) + C[i]
    k_ = int(acc.argmin()); idx = [k_]
    for i in range(M - 1, 0, -1): k_ = bp[i][k_]; idx.append(k_)
    idx = idx[::-1]; tz = t0 + ts[idx]; P3 = o + d * tz[:, None]; kn = float(kosten(P3, pruef).mean())
    try: tck, _ = splprep(P3.T, s=len(P3) * 0.0016); Q = np.array(splev(np.linspace(0, 1, 32), tck)).T
    except Exception: continue
    nf = fn[it_] * np.where(np.sum(fn[it_] * d, axis=1) > 0, -1.0, 1.0)[:, None]; nm = nf.mean(axis=0); nm /= np.linalg.norm(nm)
    r = dict(f); r.update(pfad_xyz=Q.round(3).tolist(), normale_xyz=nm.round(3).tolist(), pruefkosten_vorher=round(kv, 2), pruefkosten_nachher=round(kn, 2), versatz_median_m=round(float(np.median(np.abs(ts[idx]))), 3), n_opt=len(optf), n_pruef=len(pruef)); out.append(r)
    print(f"Kette {ci}: {f['laenge_m']} m, Pruefkosten (px bis Kante) vorher {kv:.2f} -> nachher {kn:.2f}, Tiefenversatz Median {np.median(np.abs(ts[idx])):.3f} m", flush=True)
json.dump(out, open(os.path.join(aus, f"tiefe_{name}.json"), "w"))
if out: print("Mittel Pruefkosten vorher %.2f nachher %.2f (%d Ketten)" % (np.mean([r['pruefkosten_vorher'] for r in out]), np.mean([r['pruefkosten_nachher'] for r in out]), len(out)))
