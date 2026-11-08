#!/usr/bin/env python3
"""netz_verfeinern.py - Netz REGIONWEISE gegen Fotokanten verfeinern (differenzierbares Rendern, PyTorch3D 0.7.9, BSD-3).
  venv-seg/bin/python -W ignore -I tools/netz_verfeinern.py objekt.json --netz in.stl --aus out.stl --box x0,y0,z0,x1,y1,z1 --fotos 000,004,... [--holdout 016,043] [--iter 300]
Idee: nur Netzpunkte in der Region (Quader, K-Rahmen m) duerfen sich bewegen (Rest eingefroren); Verlust = Kanten des gerenderten Tiefenbildes
(weiche Rasterung, SoftRas-Tiefe) liegen auf Fotokanten: sum(e * DT)/sum(e) mit DT = gekappte Distanztransformation der Canny-Fotokanten (Region-Maske im Foto).
Bremsen: uniforme Laplace-Glaettung, Kantenlaenge, Normalkonsistenz (pytorch3d.loss), Verschiebung <= --max-cm. Holdout-Fotos gehen NIE in die Optimierung; ihr Verlust wird
mitgeschrieben (Proxy!). Massgeblich bleibt der echte Foto-Diff (tools/modell_wettbewerb.py) auf dem Ergebnis-STL.
Kameras: K-<nr>.json (COLMAP/OpenCV, k1 per Entzerrung des Fotos), Netz STL mm -> K-Rahmen m wie foto_diff._netz (mm*massstab/1000 + rahmen_verschiebung).
ANNAHME: Fotokanten = Canny nach Glaettung (nicht identisch mit foto_diff-Kantenmass); Kamera-Umrechnung OpenCV->PyTorch3D wird am ersten Foto per 4 Spiegelvarianten geprueft."""
import os, sys, json, glob, argparse, time
sys.path.insert(0, "/media/oem/scan/p3d_site"); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, cv2, torch, trimesh
import fehlteile_finden as FF
from pytorch3d.structures import Meshes
from pytorch3d.renderer import PerspectiveCameras, RasterizationSettings, MeshRasterizer
from pytorch3d.loss import mesh_laplacian_smoothing, mesh_edge_loss, mesh_normal_consistency

ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--netz", required=True); ap.add_argument("--aus", required=True); ap.add_argument("--box", required=True)
ap.add_argument("--fotos", required=True); ap.add_argument("--holdout", default=""); ap.add_argument("--iter", type=int, default=300); ap.add_argument("--breite", type=int, default=1400)
ap.add_argument("--lr", type=float, default=0.01); ap.add_argument("--max-cm", type=float, default=15.0); ap.add_argument("--w-lap", type=float, default=2.0); ap.add_argument("--w-kante", type=float, default=2.0)
ap.add_argument("--w-normal", type=float, default=0.5); ap.add_argument("--batch", type=int, default=4); ap.add_argument("--rand", type=float, default=0.4, help="Pufferrand der Region im Foto (m) fuer die Maske")
ap.add_argument("--log-alle", type=int, default=25); ap.add_argument("--fpp", type=int, default=6, help="Flaechen je Pixel (weiche Rasterung); 3 = schneller"); ap.add_argument("--pruefen", action="store_true", help="nur Kamerakonvention pruefen (4 Spiegelvarianten) und beenden"); ap.add_argument("--massstab", type=float, default=87.0); a = ap.parse_args()
dev = "cuda"; obj = json.load(open(a.objekt)); od = os.path.dirname(os.path.abspath(a.objekt)); root = os.path.dirname(os.path.dirname(od))
fotos = [f for f in a.fotos.split(",") if f]; hold = [f for f in a.holdout.split(",") if f]; box = np.array([float(v) for v in a.box.split(",")])
def lade_k(nr): return json.load(open(os.path.join(od, "messprotokoll", f"K-{nr}.json")))["kamera"]
k0 = lade_k((fotos + hold)[0]); rv = np.array(k0.get("rahmen_verschiebung", [0, 0, 0]), float)
m = trimesh.load(a.netz, force="mesh"); V0 = torch.tensor(m.vertices * (a.massstab / 1000.0) + rv, dtype=torch.float32, device=dev); F = torch.tensor(m.faces, dtype=torch.int64, device=dev)
inreg = ((V0[:, 0] >= box[0]) & (V0[:, 0] <= box[3]) & (V0[:, 1] >= box[1]) & (V0[:, 1] <= box[4]) & (V0[:, 2] >= box[2]) & (V0[:, 2] <= box[5]))
idx = torch.nonzero(inreg).squeeze(1); print(f"Netz {len(m.faces)} Flaechen, Regionspunkte {len(idx)} von {len(V0)}", flush=True)
if len(idx) < 50: sys.exit("Region fast leer")
CV2P3D = torch.diag(torch.tensor([-1.0, -1.0, 1.0], device=dev))
def lade_foto(nr):
    k = lade_k(nr); fp = glob.glob(os.path.join(root, obj["fotos_dir"], f"{nr}_*"))[0]; im = cv2.imread(fp); im, _ = FF.foto_entzerren(im, k); H, W = im.shape[:2]
    s = min(1.0, a.breite / W); im = cv2.resize(im, (int(W * s), int(H * s)), interpolation=cv2.INTER_AREA); h, w = im.shape[:2]
    g = cv2.GaussianBlur(cv2.cvtColor(im, cv2.COLOR_BGR2GRAY), (0, 0), 1.6); ed = cv2.Canny(g, 25, 70) > 0
    dt = cv2.distanceTransform((~ed).astype(np.uint8), cv2.DIST_L2, 3); dt = np.minimum(dt, 30.0) / 30.0
    R, _ = cv2.Rodrigues(np.array(k["rvec"], float)); t = np.array(k["t"], float); f = k["f_px"] * s; cx = k.get("cx", W / 2) * s; cy = k.get("cy", H / 2) * s
    # Regionsmaske: Bildhuelle der 8 Quaderecken (+Rand)
    b = box.copy(); b[:3] -= a.rand; b[3:] += a.rand; ec = np.array([[x, y, z] for x in (b[0], b[3]) for y in (b[1], b[4]) for z in (b[2], b[5])])
    pc = ec @ R.T + t; ok = pc[:, 2] > 1; msk = np.zeros((h, w), np.uint8)
    if ok.sum() >= 4:
        uv = np.stack([f * pc[ok, 0] / pc[ok, 2] + cx, f * pc[ok, 1] / pc[ok, 2] + cy], 1).astype(np.int32); cv2.fillConvexPoly(msk, cv2.convexHull(uv), 1)
    Rp = (CV2P3D @ torch.tensor(R, dtype=torch.float32, device=dev)).T[None]; Tp = (CV2P3D @ torch.tensor(t, dtype=torch.float32, device=dev))[None]
    cam = PerspectiveCameras(focal_length=torch.tensor([[f, f]], dtype=torch.float32, device=dev), principal_point=torch.tensor([[cx, cy]], dtype=torch.float32, device=dev),
                             in_ndc=False, image_size=torch.tensor([[h, w]], device=dev), R=Rp, T=Tp, device=dev)
    return dict(nr=nr, h=h, w=w, dt=torch.tensor(dt, device=dev), mask=torch.tensor(msk, dtype=torch.float32, device=dev), cam=cam, im=im, ed=ed, sicht=int(msk.sum()))
def rastern(F_, V_, p):
    sigma = (1.5 * 2.0 / min(p["h"], p["w"])) ** 2; rs = RasterizationSettings(image_size=(p["h"], p["w"]), blur_radius=float(np.log(1.0 / 1e-4 - 1.0) * sigma), faces_per_pixel=a.fpp, bin_size=0)
    fr = MeshRasterizer(cameras=p["cam"], raster_settings=rs)(Meshes(verts=[V_], faces=[F_]))
    z = fr.zbuf[0]; d = fr.dists[0]; ok = fr.pix_to_face[0] >= 0; prob = torch.sigmoid(-d / sigma) * ok
    gam = 0.3; zf = 120.0; zv = torch.where(ok, z, torch.full_like(z, zf)); zmin = zv.min(-1, keepdim=True).values.detach()              # SoftRas-Tiefe: naechste Flaeche dominiert (gam m)
    w_ = prob * torch.exp(-(zv - zmin) / gam); wb = torch.exp(-(zf - zmin) / gam) * (1 - prob).prod(-1, keepdim=True)
    D = ((w_ * torch.where(ok, z, torch.zeros_like(z))).sum(-1, keepdim=True) + wb * zf) / (w_.sum(-1, keepdim=True) + wb + 1e-8)
    return D[..., 0], (1 - (1 - prob).prod(-1))
SOBX = torch.tensor([[[-1, 0, 1], [-2, 0, 2], [-1, 0, 1]]], dtype=torch.float32, device=dev)[None] / 8.0
def kantenverlust(D, A, p):
    Dn = D[None, None]; gx = torch.nn.functional.conv2d(Dn, SOBX, padding=1); gy = torch.nn.functional.conv2d(Dn, SOBX.transpose(2, 3), padding=1)
    e = torch.tanh(torch.sqrt(gx ** 2 + gy ** 2 + 1e-12)[0, 0] / 0.15) * p["mask"]
    return (e * p["dt"]).sum() / (e.sum() + 1.0), float(e.sum())
t0 = time.time(); P = {nr: lade_foto(nr) for nr in fotos + hold}; print("Fotos geladen", len(P), round(time.time() - t0), "s; Regionsflaeche px je Foto (Median):", int(np.median([p["sicht"] for p in P.values()])), flush=True)
def verlust_eval(nr, V_):
    p = P[nr]
    if p["sicht"] < 2000: return None
    D, A = rastern(F, V_, p); return kantenverlust(D, A, p)[0]
if a.pruefen:
    p = P[fotos[0]]; D, A = rastern(F, V0, p)
    for fx in (False, True):
        for fy in (False, True):
            Dv = D.flip(1) if fx else D; Dv = Dv.flip(0) if fy else Dv; print("Spiegelung x", fx, "y", fy, "Kantenverlust", round(float(kantenverlust(Dv, A, p)[0]), 4), "Kantenmasse", round(kantenverlust(Dv, A, p)[1]))
    sil = (A.detach().cpu().numpy() > 0.5).astype(np.uint8); ov = p["im"].copy(); cs, _ = cv2.findContours(sil, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE); cv2.drawContours(ov, cs, -1, (0, 0, 255), 2); cv2.imwrite(a.aus + ".overlay.jpg", ov)
    cv2.imwrite(a.aus + ".pruef.png", np.hstack([cv2.cvtColor((255 * (D - D.min()) / (D.max() - D.min() + 1e-9)).clamp(0, 255).byte().cpu().numpy(), cv2.COLOR_GRAY2BGR), p["im"]])); sys.exit(0)
delta = torch.zeros((len(idx), 3), device=dev, requires_grad=True); opt = torch.optim.Adam([delta], lr=a.lr); rng = np.random.default_rng(0); log = []
usable = [nr for nr in fotos if P[nr]["sicht"] >= 2000]; print("nutzbare Trainingsfotos:", len(usable), "Holdout:", [nr for nr in hold if P[nr]["sicht"] >= 2000], flush=True)
def verts(): V_ = V0.clone(); V_[idx] = V0[idx] + delta; return V_
for it in range(a.iter + 1):
    opt.zero_grad(); V_ = verts(); batch = rng.choice(usable, min(a.batch, len(usable)), replace=False); lk = 0.0
    for nr in batch:
        D, A = rastern(F, V_, P[nr]); l, _ = kantenverlust(D, A, P[nr]); lk = lk + l / len(batch)
    me = Meshes(verts=[V_], faces=[F]); lreg = a.w_lap * mesh_laplacian_smoothing(me, method="uniform") + 1.0 * mesh_edge_loss(me) + a.w_normal * mesh_normal_consistency(me)
    loss = a.w_kante * lk + lreg; loss.backward(); opt.step()
    with torch.no_grad(): n = delta.norm(dim=1, keepdim=True); delta.mul_(torch.clamp(a.max_cm / 100.0 / (n + 1e-9), max=1.0))
    if it % a.log_alle == 0:
        with torch.no_grad():
            V_ = verts(); tr = np.mean([float(verlust_eval(nr, V_)) for nr in usable[:6]]); hv = [verlust_eval(nr, V_) for nr in hold]; hv = [float(x) for x in hv if x is not None]
        r = dict(it=it, train_kante=round(tr, 4), holdout_kante=round(float(np.mean(hv)), 4) if hv else None, reg=round(float(lreg), 4), max_cm=round(float(delta.norm(dim=1).max()) * 100, 2), s=round(time.time() - t0))
        log.append(r); print(r, flush=True)
Vf = verts().detach().cpu().numpy(); mm = (Vf - rv) * (1000.0 / a.massstab); out = trimesh.Trimesh(mm, m.faces, process=False); out.export(a.aus)
json.dump(dict(netz=a.netz, box=a.box, fotos=fotos, holdout=hold, log=log, wasserdicht=bool(out.is_watertight), args=vars(a)), open(a.aus + ".json", "w"), indent=1, default=str)
print("fertig", a.aus, "wasserdicht", out.is_watertight, flush=True)
