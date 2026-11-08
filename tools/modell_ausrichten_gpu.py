#!/usr/bin/env python3
"""modell_ausrichten_gpu.py <objekt> --wolke w.npy [--typ bauteil|ganz] [--sichtbar] [--stl_aus out.stl]
GPU-Sweep ueber ALLE Freiheitsgrade eines Modells/Bauteils (Nutzer 8.11.: 'Elemente drehen, mit GPU Vollgas alles uebers ganze Ding'):
  Verschiebung (du,dn,dz), Drehung (gier um z, nick um u, roll um n = Kippen in der Fassadenebene), Streckung (su entlang der Fassade, sz Hoehe).
Verfahren: Start 4-D-Gitter (du,dn,gier,su), danach Koordinatenabstieg ueber alle 8 Parameter mit halbierten Bereichen (Pyramide). Bewertung wie teil_sweep_gpu
(Abstandsfeld der Wolke, zweiseitig, 80 % getrimmt, Wolke genug im Teilbereich). Fassadenachse aus objekt.json (fassade_n)."""
import sys, os, json, argparse, subprocess, time, numpy as np, trimesh
sys.path.insert(0, "/media/oem/scan/p3d_site"); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import torch
from pytorch3d.ops import knn_points
ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--wolke", required=True); ap.add_argument("--typ", default="ganz"); ap.add_argument("--mit", default="")
ap.add_argument("--sichtbar", action="store_true"); ap.add_argument("--rand", type=float, default=8.0); ap.add_argument("--stl_aus"); ap.add_argument("--zmin", type=float, default=1.0)
ap.add_argument("--du_max", type=float, default=5.0); ap.add_argument("--fotos"); ap.add_argument("--bilder"); ap.add_argument("--nfotos", type=int, default=8); ap.add_argument("--w_foto", type=float, default=1.0); ap.add_argument("--su_max", type=float, default=0.30)
ap.add_argument("--su_lo", type=float, default=0.95); ap.add_argument("--su_hi", type=float, default=1.45); ap.add_argument("--sz_lo", type=float, default=0.95); ap.add_argument("--sz_hi", type=float, default=1.20)   # Grenzen aus Sichtbeobachtung (masstabelle beobachtungen_offen 8.11.): gegen Schrumpf-Falle
ap.add_argument("--start", help="JSON mit Startzustand (du..sz) aus vorigem Lauf"); ap.add_argument("--basis", help="JSON der Gesamt-Ausrichtung: Modell wird zuerst damit transformiert (Teil-Schleife im Rahmen des Gesamtergebnisses)"); ap.add_argument("--dn_max", type=float, default=4.0); ap.add_argument("--gier_max", type=float, default=10.0); ap.add_argument("--out_json"); ap.add_argument("--ns", type=int, default=8000, help="Modell-Oberflaechenpunkte (mehr = weniger Rauschen)"); ap.add_argument("--nur_bewerten", action="store_true", help="nur Score des Startzustands (Wolke+Foto) ausgeben, nicht optimieren (Annahme-Tor teil_tor.py)")
ap.add_argument("--py", default=os.path.expanduser("~/.venvs/rcpark/bin/python")); a = ap.parse_args()
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); OD = os.path.join(ROOT, "modelle", a.objekt); K = 1000.0 / 87.0
OBJ = json.load(open(os.path.join(OD, "objekt.json"))); nax = np.array(OBJ["fassade_n"]["wert"], dtype=float); nax /= np.linalg.norm(nax); uax = np.array([nax[1], -nax[0]])
dev = "cuda"; CAP = 1.0
def bauen(nur, tag):
    stl = f"_au_{os.getpid()}_{tag}.stl"; env = dict(os.environ, OBJ_DIR=a.objekt, STL_NAME=stl, SCALE="87", ELEMENTE_AUS="/dev/null", BAUTEIL_PARAM="{}")
    if nur: env["NUR_BAUTEIL"] = nur
    r = subprocess.run([a.py, os.path.join(ROOT, "tools", "baukasten_gen.py"), a.objekt], env=env, capture_output=True, text=True); p = os.path.join(ROOT, "modelle", "stl", stl)
    if not os.path.exists(p): sys.exit("Bau fehlgeschlagen " + r.stderr[-300:])
    m = trimesh.load(p, process=False); os.remove(p); m.apply_scale(1.0 / K); return m
m = bauen("" if a.typ == "ganz" else ((a.mit + "," + a.typ) if a.mit else a.typ), "t")
if a.basis:
    bs = json.load(open(a.basis)); cB = np.array(bs["zentrum"]); u3b = np.array([uax[0], uax[1], 0.0]); n3b = np.array([nax[0], nax[1], 0.0]); Bb = np.stack([u3b, n3b, np.array([0, 0, 1.0])])
    def _rz(w): c, s_ = np.cos(w), np.sin(w); return np.array([[c, -s_, 0], [s_, c, 0], [0, 0, 1]])
    def _rx(w): c, s_ = np.cos(w), np.sin(w); return np.array([[1, 0, 0], [0, c, -s_], [0, s_, c]])
    def _ry(w): c, s_ = np.cos(w), np.sin(w); return np.array([[c, 0, s_], [0, 1, 0], [-s_, 0, c]])
    Rb = _rz(np.radians(bs["gier_grad"])) @ _rx(np.radians(bs["nick_grad"])) @ _ry(np.radians(bs["roll_grad"]))
    Lb = (np.asarray(m.vertices) - cB) @ Bb.T; m.vertices = cB + (((Lb * np.array([bs["su"], 1.0, bs["sz"]])) @ Rb.T) + np.array([bs["du"], bs["dn"], bs["dz"]])) @ Bb; print("Basis-Transformation angewandt", flush=True)
S, FI = trimesh.sample.sample_surface(m, 120000, seed=0); NS = m.face_normals[FI]
if a.sichtbar: kp = (NS[:, :2] @ nax < 0.2) | (NS[:, 2] > 0.5); S = S[kp]
S = S[np.random.default_rng(0).choice(len(S), min(len(S), a.ns), replace=False)]
c0 = S.mean(0); u3 = np.array([uax[0], uax[1], 0.0]); n3 = np.array([nax[0], nax[1], 0.0]); e3 = np.array([0, 0, 1.0]); B = np.stack([u3, n3, e3])   # Zeilen = lokale Achsen
L = (S - c0) @ B.T; lo_m, hi_m = L.min(0) - 0.3, L.max(0) + 0.3
lo, hi = S.min(0) - a.rand, S.max(0) + a.rand
P = np.load(a.wolke)[:, :3].astype(np.float32); P = P[np.all((P >= lo) & (P <= hi), 1) & (P[:, 2] > a.zmin)]; print("Teilpunkte", len(S), "Wolkenpunkte", len(P), flush=True)
h = max(0.05, float(np.prod(hi - lo) / 40e6) ** (1 / 3)); dims = np.ceil((hi - lo) / h).astype(int); print("Voxel", h, dims, flush=True)
gx = [torch.arange(d, device=dev, dtype=torch.float32) * h + float(l) for d, l in zip(dims, lo)]; X, Y = torch.meshgrid(gx[0], gx[1], indexing="ij")
def feld(pts):
    Pg = torch.tensor(pts, device=dev, dtype=torch.float32)[None]; F = torch.empty(tuple(int(d) for d in dims), device=dev)
    for k in range(int(dims[2])):
        Q = torch.stack([X, Y, torch.full_like(X, float(gx[2][k]))], -1).reshape(1, -1, 3); F[:, :, k] = knn_points(Q, Pg, K=1).dists[0, :, 0].sqrt().reshape(int(dims[0]), int(dims[1]))
    return F.clamp(max=CAP)
D = feld(P); DM = feld(S); lo_t = torch.tensor(lo, device=dev, dtype=torch.float32); dimt = torch.tensor(dims, device=dev)
def lookup(F, Q):
    idx = ((Q - lo_t) / h).round().long(); ok = ((idx >= 0) & (idx < dimt)).all(-1); idx = torch.minimum(idx.clamp_min(0), dimt - 1); d = F[idx[..., 0], idx[..., 1], idx[..., 2]]; return torch.where(ok, d, torch.full_like(d, CAP))
Lg = torch.tensor(L, device=dev, dtype=torch.float32); Bg = torch.tensor(B, device=dev, dtype=torch.float32); c0g = torch.tensor(c0, device=dev, dtype=torch.float32)
Pl = (P - c0) @ B.T; Pr = P[np.all((Pl >= L.min(0) - 1.0) & (Pl <= L.max(0) + 1.0), 1)]; print("feste Rueckrichtungsregion:", len(Pr), "Wolkenpunkte", flush=True)
Cr = torch.tensor(Pr[np.random.default_rng(1).choice(len(Pr), min(len(Pr), 12000), replace=False)], device=dev, dtype=torch.float32); Lc = (Cr - c0g) @ Bg.T
LOM = torch.tensor(lo_m, device=dev, dtype=torch.float32); HIM = torch.tensor(hi_m, device=dev, dtype=torch.float32)
def rot(axis, ang):
    c, s = torch.cos(ang), torch.sin(ang); o, z = torch.ones_like(ang), torch.zeros_like(ang)
    if axis == 0: return torch.stack([torch.stack([o, z, z], -1), torch.stack([z, c, -s], -1), torch.stack([z, s, c], -1)], -2)
    if axis == 1: return torch.stack([torch.stack([c, z, s], -1), torch.stack([z, o, z], -1), torch.stack([-s, z, c], -1)], -2)
    return torch.stack([torch.stack([c, -s, z], -1), torch.stack([s, c, z], -1), torch.stack([z, z, o], -1)], -2)
def matrizen(Xc):   # Xc (M,8): du dn dz gier nick roll su sz (Winkel Grad) -> R (M,3,3), sk (M,3), sh (M,3)
    g, nk, ro = [torch.deg2rad(Xc[:, i]) for i in (3, 4, 5)]; R = rot(2, g) @ rot(0, nk) @ rot(1, ro); sk = torch.stack([Xc[:, 6], torch.ones_like(Xc[:, 6]), Xc[:, 7]], 1); return R, sk, Xc[:, :3]
def trim(d): return d.sort(dim=1)[0][:, : int(d.shape[1] * 0.8)].mean(1)

# ---- Foto-Kantenterm: Modellkanten aller Teile in mehrere kalibrierte Fotos (aus verschiedenen Richtungen), Abstand zur naechsten Fotokante in m ----
FOTOS = []
if a.fotos:
    import cv2
    mm = m.copy(); mm.merge_vertices(); V_ = np.asarray(mm.vertices); ed = mm.face_adjacency_edges[mm.face_adjacency_angles > 0.6]; ln = np.linalg.norm(V_[ed[:, 0]] - V_[ed[:, 1]], axis=1); ed = ed[(ln > 0.3) & (ln < 8)]
    tt = np.linspace(0, 1, 5)[None, :, None]; PE = (V_[ed[:, 0]][:, None] * (1 - tt) + V_[ed[:, 1]][:, None] * tt).reshape(-1, 3)
    if len(PE) > 5000: PE = PE[np.random.default_rng(2).choice(len(PE), 5000, replace=False)]
    LE = torch.tensor((PE - c0) @ B.T, device=dev, dtype=torch.float32)
    KAM = json.load(open(a.fotos)); cen = S.mean(0); cand = []
    for nm, k in KAM.items():
        Rk = np.array(k["Rn"]); x = Rk @ cen + np.array(k["tn"]); Ck = -Rk.T @ np.array(k["tn"])
        if x[2] <= 1: continue
        uv = k["f"] * x[:2] / x[2] + [k["cx"], k["cy"]]
        if 0.2 * k["W"] < uv[0] < 0.8 * k["W"] and 0.2 * k["H"] < uv[1] < 0.8 * k["H"] and 15 <= np.linalg.norm(Ck - cen) <= 60: cand.append((nm, k, Ck))
    # Blickrichtungs-Vielfalt: Fernstes-Punkt-Auswahl nach Kameraposition
    pick = [0]
    while len(pick) < min(a.nfotos, len(cand)):
        dm = [min(np.linalg.norm(cand[i][2] - cand[j][2]) for j in pick) for i in range(len(cand))]; pick.append(int(np.argmax(dm)))
    SK = 0.25
    for i in pick:
        nm, k, _ = cand[i]; g = cv2.imread(os.path.join(a.bilder, nm), cv2.IMREAD_GRAYSCALE | cv2.IMREAD_IGNORE_ORIENTATION)
        if g is None: continue
        g = cv2.resize(g, None, fx=SK, fy=SK, interpolation=cv2.INTER_AREA); e = cv2.Canny(cv2.GaussianBlur(g, (0, 0), 1.5), 40, 110)
        FOTOS.append(dict(DT=torch.tensor(cv2.distanceTransform((e == 0).astype(np.uint8), cv2.DIST_L2, 3), device=dev, dtype=torch.float32), R=torch.tensor(k["Rn"], device=dev, dtype=torch.float32), t=torch.tensor(k["tn"], device=dev, dtype=torch.float32), f=float(k["f"]), c=(float(k["cx"]), float(k["cy"]))))
    print("Foto-Term: %d Fotos %s, %d Kantenpunkte" % (len(FOTOS), [cand[i][0][-18:] for i in pick], len(PE)), flush=True)
def foto_kosten(R, sk, sh):
    Lp = torch.einsum("mij,mnj->mni", R, LE[None] * sk[:, None, :]); We = c0g + (Lp + sh[:, None, :]) @ Bg; tot = 0.0
    for F in FOTOS:
        X = We @ F["R"].T + F["t"]; z = X[..., 2].clamp_min(1e-3); iu = ((F["f"] * X[..., 0] / z + F["c"][0]) * SK).round().long(); iv = ((F["f"] * X[..., 1] / z + F["c"][1]) * SK).round().long(); H_, W_ = F["DT"].shape
        ok = (X[..., 2] > 0.5) & (iu >= 0) & (iv >= 0) & (iu < W_) & (iv < H_); d = F["DT"][iv.clamp(0, H_ - 1), iu.clamp(0, W_ - 1)] / SK * z / F["f"]; tot = tot + torch.where(ok, d.clamp(max=0.5), torch.full_like(d, 0.5)).mean(1)
    return tot / max(len(FOTOS), 1)
NCNT = []
def bewerte(Xc, blk=250):
    out = []
    for b in range(0, len(Xc), blk):
        R, sk, sh = matrizen(Xc[b:b + blk])
        Lp = torch.einsum("mij,nj->mni", R, Lg[None, :, :].expand(len(R), -1, -1)[0] * 1.0) if False else torch.einsum("mij,mnj->mni", R, Lg[None] * sk[:, None, :])
        W = c0g + (Lp + sh[:, None, :]) @ Bg; f1 = trim(lookup(D, W))
        # Rueckrichtung: FESTE Wolkenregion (Modellbox +-1 m, unabhaengig vom Kandidaten) -> jeder Wolkenpunkt ohne Modell in der Naehe kostet (gekappt 0.5 m). Verhindert Schrumpfen.
        Li = torch.einsum("mji,mnj->mni", R, Lc[None] - sh[:, None, :]) / sk[:, None, :]; Wm = c0g + Li @ Bg; dd = lookup(DM, Wm).clamp(max=0.5)
        out.append(0.5 * (f1 + dd.mean(1)) + (a.w_foto * foto_kosten(R, sk, sh) if FOTOS else 0.0))
    return torch.cat(out)
def gitter(x, idx, halfs, nst):
    ax = [torch.linspace(-hf, hf, nst[i], device=dev) for i, hf in enumerate(halfs)]; G = torch.stack([t.ravel() for t in torch.meshgrid(*ax, indexing="ij")], 1)
    Xc = x[None].repeat(len(G), 1)
    for j, i in enumerate(idx): Xc[:, i] += G[:, j]
    Xc[:, 6] = Xc[:, 6].clamp(a.su_lo, a.su_hi); Xc[:, 7] = Xc[:, 7].clamp(a.sz_lo, a.sz_hi)
    return Xc
x0_ = [0, 0, 0, 0, 0, 0, 1.0, 1.0]
if a.start: st = json.load(open(a.start)); x0_ = [st[k] for k in ('du', 'dn', 'dz', 'gier_grad', 'nick_grad', 'roll_grad', 'su', 'sz')]
x = torch.tensor(x0_, device=dev, dtype=torch.float32); x[6] = x[6].clamp(a.su_lo, a.su_hi); x[7] = x[7].clamp(a.sz_lo, a.sz_hi); t0 = time.time(); s0 = float(bewerte(x[None])[0]); print("Start Abstand %.3f m" % s0, flush=True)
if a.nur_bewerten: print("SCORE %.5f" % s0); sys.exit(0)
# Runde 0: 4-D Start (du, dn, gier, su)
if not a.start: x[6] = (a.su_lo + a.su_hi) / 2
G = gitter(x, [0, 1, 3, 6], [a.du_max, a.dn_max, a.gier_max, (a.su_hi - a.su_lo) / 2], [int(8 * a.du_max) + 1, 33, 21, 25]); sc = bewerte(G)
i = int(sc.argmin()); x = G[i].clone(); print("Runde 0 (4-D, %d Kandidaten): %.3f m  x=%s [%.0f s]" % (len(G), float(sc[i]), np.round(x.cpu().numpy(), 3), time.time() - t0), flush=True)
best = float(sc[i]); f = 1.0
for r in range(1, 9):
    for idx, halfs, nst in (([0, 1, 2], [max(3, a.du_max / 3) * f, 2 * f, 2 * f], [25, 25, 25]), ([3, 4, 5], [6 * f, 4 * f, 6 * f], [13, 11, 13]), ([6, 7], [0.2 * f, 0.15 * f], [21, 17]), ([0, 3, 6], [1.5 * f, 4 * f, 0.15 * f], [15, 13, 13])):
        G = gitter(x, idx, halfs, nst); s_ = bewerte(G); i = int(s_.argmin())
        if float(s_[i]) <= best: best = float(s_[i]); x = G[i].clone()
    print("Runde %d (Bereich x%.3f): %.4f m  x=%s [%.0f s]" % (r, f, best, np.round(x.cpu().numpy(), 3), time.time() - t0), flush=True); f *= 0.6
xs = x.cpu().numpy(); names = ["du", "dn", "dz", "gier_grad", "nick_grad", "roll_grad", "su", "sz"]
res = dict(typ=a.typ, abstand_start=s0, abstand_ende=best, **{k: float(v) for k, v in zip(names, xs)}, zentrum=[float(v) for v in c0])
json.dump(res, open(a.out_json or os.path.join(OD, "ausrichtung_%s.json" % a.typ.replace(":", "_")), "w"), indent=1); print("ERGEBNIS", json.dumps(res))
if a.stl_aus:   # ausgerichtetes Netz (m -> mm 1:87 wie Generator)
    R, sk, sh = matrizen(x[None]); V = torch.tensor(np.asarray(m.vertices), device=dev, dtype=torch.float32); Lv = (V - c0g) @ Bg.T; Lp = torch.einsum("ij,nj->ni", R[0], Lv * sk[0]); W = (c0g + (Lp + sh[0]) @ Bg).cpu().numpy()
    mo = m.copy(); mo.vertices = W; mo.apply_scale(K); mo.export(a.stl_aus); print("STL", a.stl_aus)
