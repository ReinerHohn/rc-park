"""LIMAP-Prototyp Stufe 1 (venv-seg, GPU): Vorbereitung fuer einen kleinen Ausschnitt (Minuten statt Stunden): Ausschnitt = Kugel um ein Zentrum, Fotos = die am besten sehenden, verschieden verteilten.
Fotos werden entzerrt (SIMPLE_RADIAL k1 -> PINHOLE), Tiefenkarten aus der Wolke (Z-Puffer + Fuellen), COLMAP-Textmodell aus kam_lot2.json (Netzrahmen = Wolkenrahmen),
LIMAP (geometry-guided, LSD) -> Linien in Netzrahmen. Aufruf (venv-seg): limap_proto_vor.py KAM.json WOLKE.npy BILDER ZENTRUM_NPZ(kanten3d) OUTDIR [--n 16] [--radius 3.0] [--skala 0.5] [--detektor lsd]"""
import sys, os, json, shutil, numpy as np, cv2, torch, logging
from pathlib import Path
def opt(n, d, t=float): return t(sys.argv[sys.argv.index(n) + 1]) if n in sys.argv else d
N = opt("--n", 16, int); RAD = opt("--radius", 3.0); SK = opt("--skala", 0.5); DET = opt("--detektor", "lsd", str)
KAM = json.load(open(sys.argv[1])); P = np.load(sys.argv[2])[:, :3].astype(np.float32); BD = sys.argv[3]; kz = np.load(sys.argv[4]); out = Path(sys.argv[5]); dev = "cuda"
ep = kz["P"][(kz["vis"] >= 6) & (kz["kan"] / np.maximum(kz["vis"], 1) >= 0.5)]; c = np.median(ep, 0); print("Zentrum", c.round(2), flush=True)
roi = np.linalg.norm(P - c, axis=1) < RAD; print("Ausschnittspunkte", int(roi.sum()), flush=True); Pr = torch.from_numpy(P[roi]).to(dev)
sc = []
for f, K in KAM.items():
    Xc = Pr @ torch.tensor(K["Rn"], device=dev, dtype=torch.float32).T + torch.tensor(K["tn"], device=dev, dtype=torch.float32); z = Xc[:, 2]
    uv = K["f"] * Xc[:, :2] / z.clamp(min=0.5)[:, None] + torch.tensor([K["cx"], K["cy"]], device=dev); ok = (z > 1) & (uv[:, 0] >= 0) & (uv[:, 0] < K["W"]) & (uv[:, 1] >= 0) & (uv[:, 1] < K["H"]); sc.append((int(ok.sum()), f))
sc.sort(reverse=True); cand = [f for n, f in sc[:80] if n > 0.5 * sc[0][0]]; C = np.array([KAM[f]["C"] for f in cand]); Dd = np.array([np.array(KAM[f]["Rn"])[2] for f in cand]); feat = np.hstack([C / 10.0, Dd * 3.0])
sel = [0]; dm = np.linalg.norm(feat - feat[0], axis=1)
while len(sel) < min(N, len(cand)): j = int(np.argmax(dm)); sel.append(j); dm = np.minimum(dm, np.linalg.norm(feat - feat[j], axis=1))
fotos = [cand[i] for i in sel]; print("Fotos", len(fotos), fotos, flush=True)
for d in ("images", "sparse", "depth"): (out / d).mkdir(parents=True, exist_ok=True)
from scipy.spatial.transform import Rotation as Rot
ctxt = []; itxt = []; Pt = torch.from_numpy(P).to(dev)
for i, f in enumerate(fotos, 1):
    K = KAM[f]; im = cv2.imread(os.path.join(BD, f), cv2.IMREAD_COLOR | cv2.IMREAD_IGNORE_ORIENTATION); H0, W0 = im.shape[:2]; assert (W0, H0) == (K["W"], K["H"]), (f, W0, H0)
    Km = np.array([[K["f"], 0, K["cx"]], [0, K["f"], K["cy"]], [0, 0, 1]], float); und = cv2.undistort(im, Km, np.array([K["params"][3], 0, 0, 0], float), None, Km)
    w, h = int(W0 * SK), int(H0 * SK); und = cv2.resize(und, (w, h), interpolation=cv2.INTER_AREA); cv2.imwrite(str(out / "images" / (Path(f).stem + ".jpg")), und)
    fx, cx, cy = K["f"] * SK, K["cx"] * SK, K["cy"] * SK; ctxt.append("%d PINHOLE %d %d %.6f %.6f %.6f %.6f" % (i, w, h, fx, fx, cx, cy))
    q = Rot.from_matrix(np.array(K["Rn"])).as_quat(); t = K["tn"]; itxt.append("%d %.9f %.9f %.9f %.9f %.9f %.9f %.9f %d %s\n" % (i, q[3], q[0], q[1], q[2], t[0], t[1], t[2], i, Path(f).stem + ".jpg"))
    Xc = Pt @ torch.tensor(K["Rn"], device=dev, dtype=torch.float32).T + torch.tensor(K["tn"], device=dev, dtype=torch.float32); z = Xc[:, 2]
    u = (fx * Xc[:, 0] / z.clamp(min=0.5) + cx).round().long(); v = (fx * Xc[:, 1] / z.clamp(min=0.5) + cy).round().long(); ok = (z > 1) & (u >= 0) & (u < w) & (v >= 0) & (v < h)
    zb = torch.full((h * w,), 1e9, device=dev); zb.scatter_reduce_(0, (v * w + u)[ok], z[ok], "amin"); zb = zb.view(1, 1, h, w)
    for _ in range(3): zb = torch.where(zb > 1e8, -torch.nn.functional.max_pool2d(-zb, 5, 1, 2), zb)               # Loecher fuellen (naechstgelegener Z-Wert)
    D = zb[0, 0].cpu().numpy().astype(np.float64); D[D > 1e8] = np.inf; np.save(out / "depth" / (Path(f).stem + ".jpg.npy"), D)
(out / "sparse" / "cameras.txt").write_text("\n".join(ctxt) + "\n"); (out / "sparse" / "images.txt").write_text("".join(l + "\n" for l in itxt)); (out / "sparse" / "points3D.txt").write_text("")
# images.txt braucht je Bild eine (leere) Punktzeile
(out / "sparse" / "images.txt").write_text("".join(l.rstrip("\n") + "\n\n" for l in itxt))
print("Vorbereitung fertig", flush=True)
