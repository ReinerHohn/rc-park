#!/usr/bin/env python3
"""teil_sweep_gpu.py <objekt> <typ> --wolke w.npy [--mit satteldach:haupt] [--bereich 1.5] [--schritt 0.04] [--raum_aus raum.json]
GPU-Peaksuche (Nutzer 8.11.: "beim Durchsweepen den Peak finden"): Bauteil EINMAL bauen, Oberflaechenpunkte ziehen, dann ALLE Verschiebungen (du, dn, dz) im
Gitter +-bereich auf der GPU bewerten (Abstandsfeld der Wolke im Voxelgitter, Nachschlagen statt Neubau). Koordinaten: u entlang der Fassade, n senkrecht (Netzrahmen).
Schreibt <raum_aus> mit start-Werten am Peak (CMA-ES-Feinanpassung startet dort) und gibt die besten Peaks + Peak-Schaerfe aus."""
import sys, os, json, argparse, subprocess, numpy as np, trimesh
sys.path.insert(0, "/media/oem/scan/p3d_site"); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import torch
from pytorch3d.ops import knn_points
ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("typ"); ap.add_argument("--wolke", required=True); ap.add_argument("--mit", default="")
ap.add_argument("--bereich", type=float, default=1.5); ap.add_argument("--schritt", type=float, default=0.04); ap.add_argument("--raum_aus"); ap.add_argument("--rand", type=float, default=1.0)
ap.add_argument("--synth", default="", help="du,dn,dz: Wolke = Modellflaeche um diesen Versatz verschoben + Rauschen (Beweistest, kein echter Wolkeninhalt)")
ap.add_argument("--fotos", help="Kameras im Netzrahmen (sfm_kameras_export.py): Foto-Kantenterm"); ap.add_argument("--bilder"); ap.add_argument("--nfotos", type=int, default=6); ap.add_argument("--w_foto", type=float, default=1.0)
ap.add_argument("--sichtbar", action="store_true", help="Modellpunkte nur von der Strasse sichtbare Flaechen")
ap.add_argument("--synth_fehler", default="0.03,1.0", help="Rauschen sigma (m), Massfaktor der Wolkenform (Formfehler des Modells simulieren)")
ap.add_argument("--synth_dazu", action="store_true", help="synthetisches Teil ZUSAETZLICH zur echten Wolke (Stoerinhalt: Wand, andere Bauteile)")
ap.add_argument("--py", default=os.path.expanduser("~/.venvs/rcpark/bin/python")); a = ap.parse_args()
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); OD = os.path.join(ROOT, "modelle", a.objekt); K = 1000.0 / 87.0
OBJ = json.load(open(os.path.join(OD, "objekt.json"))); SPEC = next(b for b in OBJ["bauteile"] if b["typ"] == a.typ)
def bauen(nur, tag):
    stl = f"_sw_{os.getpid()}_{tag}.stl"; env = dict(os.environ, NUR_BAUTEIL=nur, OBJ_DIR=a.objekt, STL_NAME=stl, SCALE="87", ELEMENTE_AUS="/dev/null", BAUTEIL_PARAM="{}")
    r = subprocess.run([a.py, os.path.join(ROOT, "tools", "baukasten_gen.py"), a.objekt], env=env, capture_output=True, text=True); p = os.path.join(ROOT, "modelle", "stl", stl)
    if r.returncode != 0 or not os.path.exists(p): sys.exit("Bau fehlgeschlagen: " + nur + r.stderr[-300:])
    m = trimesh.load(p, process=False); os.remove(p); m.apply_scale(1.0 / K); return m
m = bauen((a.mit + "," + a.typ) if a.mit else a.typ, "t"); S, FI = trimesh.sample.sample_surface(m, 60000); NS = m.face_normals[FI]
if a.mit:
    from scipy.spatial import cKDTree
    R, _ = trimesh.sample.sample_surface(bauen(a.mit, "r"), 300000); kp = cKDTree(R).query(S)[0] > 0.03; S = S[kp]; NS = NS[kp]
if a.sichtbar:  # nur Flaechen, die eine Strassenkamera sieht: Normale zur Strasse (-n) oder nach oben
    nn = np.array(OBJ["fassade_n"]["wert"], dtype=float); nn /= np.linalg.norm(nn); kp = (NS[:, :2] @ nn < 0.2) | (NS[:, 2] > 0.5); S = S[kp]; NS = NS[kp]; print("nur sichtbare Flaechen:", len(S), flush=True)
if len(S) < 200: sys.exit("zu wenige Teilpunkte")
S = S[np.random.default_rng(0).choice(len(S), min(len(S), 6000), replace=False)]
n_ax = np.array(OBJ["fassade_n"]["wert"], dtype=float); n_ax /= np.linalg.norm(n_ax); u_ax = np.array([n_ax[1], -n_ax[0]]); lo, hi = S.min(0) - a.bereich - a.rand, S.max(0) + a.bereich + a.rand
P = np.load(a.wolke)[:, :3].astype(np.float32); P = P[np.all((P >= lo) & (P <= hi), 1)]
if a.synth:
    sd = np.array([float(x) for x in a.synth.split(",")]); rg = np.random.default_rng(5); M, FJ = trimesh.sample.sample_surface(m, 150000)
    if a.sichtbar:
        nn_ = np.array(OBJ["fassade_n"]["wert"], dtype=float); nn_ /= np.linalg.norm(nn_); NJ = m.face_normals[FJ]; M = M[(NJ[:, :2] @ nn_ < 0.2) | (NJ[:, 2] > 0.5)]
    sig_, sk_ = [float(x) for x in a.synth_fehler.split(",")]; M = (M - M.mean(0)) * sk_ + M.mean(0)  # Formfehler: Wolkenform um Faktor sk_ gegen das Modell skaliert
    M = M + np.array([sd[0] * u_ax[0] + sd[1] * n_ax[0], sd[0] * u_ax[1] + sd[1] * n_ax[1], sd[2]]); M = M + rg.normal(0, sig_, M.shape)
    N = rg.uniform(lo, hi, (30000, 3)); P = np.concatenate([M, N] + ([P] if a.synth_dazu else [])).astype(np.float32); P = P[np.all((P >= lo) & (P <= hi), 1)]; print("SYNTHETISCHE Wolke, Versatz", sd)
print("Teilpunkte", len(S), "Wolkenpunkte im Kasten", len(P), flush=True)
# Gitter hoechstens ~30 Mio Voxel
CAP = 1.5  # grosse Kappung: auch weit entfernte Bauteile sehen eine Abstandslandschaft (sonst flach)
dev = "cuda"; h = max(0.03, float(np.prod(hi - lo) / 30e6) ** (1 / 3)); dims = np.ceil((hi - lo) / h).astype(int); g = [torch.arange(d, device=dev, dtype=torch.float32) * h + float(l) for d, l in zip(dims, lo)]
Pg = torch.tensor(P, device=dev)[None]; D = torch.empty(tuple(int(d) for d in dims), device=dev)
X, Y = torch.meshgrid(g[0], g[1], indexing="ij")
for k in range(int(dims[2])):
    Q = torch.stack([X, Y, torch.full_like(X, float(g[2][k]))], -1).reshape(1, -1, 3); D[:, :, k] = knn_points(Q, Pg, K=1).dists[0, :, 0].sqrt().reshape(int(dims[0]), int(dims[1]))
D = D.clamp(max=CAP)
# Gegenrichtung: Abstandsfeld des MODELLS; Wolkenpunkte im Ausschnitt (Teilbox +-0.4) werden bei Verschiebung s an der Stelle c - s nachgeschlagen
DM = torch.empty_like(D); SgT = torch.tensor(S, device=dev, dtype=torch.float32)[None]
for k in range(int(dims[2])):
    Q = torch.stack([X, Y, torch.full_like(X, float(g[2][k]))], -1).reshape(1, -1, 3); DM[:, :, k] = knn_points(Q, SgT, K=1).dists[0, :, 0].sqrt().reshape(int(dims[0]), int(dims[1]))
DM = DM.clamp(max=CAP)
# Wolke->Modell: Wolkenpunkte, die bei Verschiebung s in der (verschobenen) Teilbox liegen (Box = Teil +-0.3); je Kandidat eigene Auswahl
Cr = torch.tensor(P[np.random.default_rng(1).choice(len(P), min(len(P), 25000), replace=False)], device=dev, dtype=torch.float32); print("Wolkenpunkte fuer Rueckrichtung", len(Cr), flush=True)
BLO = torch.tensor(S.min(0) - 0.3, device=dev, dtype=torch.float32); BHI = torch.tensor(S.max(0) + 0.3, device=dev, dtype=torch.float32)
NCNT = []
def trim_mask(d, m):
    n = m.sum(1); d = torch.where(m, d, torch.full_like(d, 1e9)); d = d.sort(dim=1)[0]; k = (n * 0.8).floor().clamp_min(1)
    c = torch.cumsum(torch.where(d > 1e8, torch.zeros_like(d), d), 1); idx = (k - 1).long()
    NCNT.append(n.float()); return torch.where(n >= 30, c.gather(1, idx[:, None])[:, 0] / k, torch.full_like(k, CAP))
Sg = torch.tensor(S, device=dev, dtype=torch.float32); ug = torch.tensor(u_ax, device=dev, dtype=torch.float32); ng = torch.tensor(n_ax, device=dev, dtype=torch.float32)
lo_t = torch.tensor(lo, device=dev, dtype=torch.float32); dimt = torch.tensor(dims, device=dev)
def trim(d): return d.sort(dim=1)[0][:, : int(d.shape[1] * 0.8)].mean(1)
def lookup(F, Q):
    idx = ((Q - lo_t) / h).round().long(); ok = ((idx >= 0) & (idx < dimt)).all(-1); idx = torch.minimum(idx.clamp_min(0), dimt - 1)
    d = F[idx[..., 0], idx[..., 1], idx[..., 2]]; return torch.where(ok, d, torch.full_like(d, CAP))

# ---- Foto-Kantenterm: Modellkanten (Knickkanten des Bauteils) in kalibrierte Fotos projiziert, Abstand zur naechsten Fotokante (Distanztransformation) ----
FOTOS = []
if a.fotos:
    import cv2
    from scipy.spatial import cKDTree
    mm = m.copy(); mm.merge_vertices(); V_ = np.asarray(mm.vertices); ed = mm.face_adjacency_edges[mm.face_adjacency_angles > 0.5]; mid = 0.5 * (V_[ed[:, 0]] + V_[ed[:, 1]]); ln = np.linalg.norm(V_[ed[:, 0]] - V_[ed[:, 1]], axis=1)
    dS = cKDTree(S).query(mid)[0]; print('Kanten gesamt', len(ed), 'Laenge ok', int(((ln > 0.1) & (ln < 4.0)).sum()), 'nahe Teil', int((dS < 0.3).sum()), flush=True); sel = (ln > 0.1) & (ln < 4.0) & (dS < 0.3); A_, B_ = V_[ed[sel, 0]], V_[ed[sel, 1]]
    tt = np.linspace(0, 1, 7)[None, :, None]; PE = (A_[:, None] * (1 - tt) + B_[:, None] * tt).reshape(-1, 3)
    if len(PE) == 0: sys.exit('Foto-Term: keine Modellkanten')
    if len(PE) > 3000: PE = PE[np.random.default_rng(2).choice(len(PE), 3000, replace=False)]
    KAM = json.load(open(a.fotos)); cen = S.mean(0); cand = []
    for nm, k in KAM.items():
        R_ = np.array(k["Rn"]); x = R_ @ cen + np.array(k["tn"])
        if x[2] <= 1: continue
        uv = k["f"] * x[:2] / x[2] + [k["cx"], k["cy"]]
        if 0.1 * k["W"] < uv[0] < 0.9 * k["W"] and 0.1 * k["H"] < uv[1] < 0.9 * k["H"]: cand.append((np.linalg.norm(np.array(k["C"]) - cen), nm, k))
    cand = [c for c in cand if 12 <= c[0] <= 45] or cand; cand.sort(key=lambda c: abs(c[0] - 25)); SK = 0.25
    for d_, nm, k in cand[: a.nfotos]:
        g = cv2.imread(os.path.join(a.bilder, nm), cv2.IMREAD_GRAYSCALE | cv2.IMREAD_IGNORE_ORIENTATION)
        if g is None: continue
        g = cv2.resize(g, None, fx=SK, fy=SK, interpolation=cv2.INTER_AREA); e = cv2.Canny(cv2.GaussianBlur(g, (0, 0), 1.5), 40, 110)
        DT = torch.tensor(cv2.distanceTransform((e == 0).astype(np.uint8), cv2.DIST_L2, 3), device=dev, dtype=torch.float32)
        FOTOS.append(dict(DT=DT, R=torch.tensor(k["Rn"], device=dev, dtype=torch.float32), t=torch.tensor(k["tn"], device=dev, dtype=torch.float32), f=float(k["f"]), c=(float(k["cx"]), float(k["cy"]))))
    PEg = torch.tensor(PE, device=dev, dtype=torch.float32); print("Foto-Term: %d Fotos, %d Kantenpunkte" % (len(FOTOS), len(PE)), [c[1] for c in cand[: a.nfotos]], flush=True)
def foto_kosten(sh):
    """sh (M,3) Netz-Verschiebung -> mittlerer Kantenabstand in m (gekappt 0.5), gemittelt ueber Fotos"""
    tot = 0.0
    for F in FOTOS:
        X = (PEg[None] + sh[:, None]) @ F["R"].T + F["t"]; z = X[..., 2].clamp_min(1e-3); u_ = F["f"] * X[..., 0] / z + F["c"][0]; v_ = F["f"] * X[..., 1] / z + F["c"][1]
        iu = (u_ * SK).round().long(); iv = (v_ * SK).round().long(); H_, W_ = F["DT"].shape; ok = (X[..., 2] > 0.5) & (iu >= 0) & (iv >= 0) & (iu < W_) & (iv < H_)
        d = F["DT"][iv.clamp(0, H_ - 1), iu.clamp(0, W_ - 1)] / SK * z / F["f"]; d = torch.where(ok, d.clamp(max=0.5), torch.full_like(d, 0.5)); tot = tot + d.mean(1)
    return tot / max(len(FOTOS), 1)
def bewerte(sh_uvz, blk=300):
    """sh_uvz (M,3) = (du,dn,dz) -> Abstand (M,) = Mittel aus Modell->Wolke und Wolke->Modell (je 80 % getrimmt)"""
    out = []
    for b in range(0, len(sh_uvz), blk):
        s_ = sh_uvz[b:b + blk]; sh = torch.zeros(len(s_), 3, device=dev); sh[:, :2] = s_[:, :1] * ug + s_[:, 1:2] * ng; sh[:, 2] = s_[:, 2]
        out.append(0.5 * (trim(lookup(D, Sg[None] + sh[:, None])) + trim_mask(lookup(DM, Cr[None] - sh[:, None]), ((Cr[None] - sh[:, None]) >= BLO).all(-1) & ((Cr[None] - sh[:, None]) <= BHI).all(-1))) + (a.w_foto * foto_kosten(sh) if FOTOS else 0.0))
    return torch.cat(out)
def raster(c, half, step):
    r = torch.arange(-half, half + 1e-6, step, device=dev); gu, gn, gz = torch.meshgrid(r, r, r, indexing="ij")
    return torch.stack([gu.ravel(), gn.ravel(), gz.ravel()], 1) + torch.tensor(c, device=dev, dtype=torch.float32)
import time; t0 = time.time()
# Stufe 1: grob ueber den ganzen Bereich
G1 = raster([0, 0, 0], a.bereich, 0.10); NCNT.clear(); s1 = bewerte(G1).cpu().numpy(); n1 = torch.cat(NCNT).cpu().numpy(); s1 = np.where(n1 < 0.5 * np.percentile(n1, 95), CAP, s1); g1 = G1.cpu().numpy(); null = float(bewerte(torch.zeros(1, 3, device=dev))[0])
print("Stufe 1 grob: %d Kandidaten (Schritt 0.10), Start %.3f m, bestes %.3f m, Median %.3f m  [%.1f s]" % (len(g1), null, s1.min(), np.median(s1), time.time() - t0), flush=True)
# bis zu 6 verschiedene Peaks (Mindestabstand 0.35 m) herausgreifen
inner = np.abs(g1).max(1) <= a.bereich - 0.15  # Randminima der Suchbox nie als Peak
order = [o for o in np.argsort(s1) if inner[o]]; peaks = []
for o in order:
    if all(np.linalg.norm(g1[o] - q[0]) > 0.35 for q in peaks): peaks.append((g1[o], s1[o]))
    if len(peaks) >= 6: break
verf = []
for c, sc0 in peaks:
    for half, step in ((0.15, 0.03), (0.04, 0.01), (0.012, 0.004)):
        G = raster(c, half, step); sc = bewerte(G).cpu().numpy(); gg = G.cpu().numpy(); cand = np.where(sc <= sc.min() + 0.002)[0]; c = gg[cand].mean(0); best = float(sc.min())  # Mitte des Plateaus
    verf.append((best, c, sc0)); print("  Peak grob (%.2f,%.2f,%.2f) %.3f -> fein (%.3f,%.3f,%.3f) %.3f m" % (*peaks[len(verf) - 1][0], sc0, *c, best), flush=True)
verf.sort(key=lambda t: t[0]); b1, c1, _ = verf[0]; b2 = verf[1][0] if len(verf) > 1 else float("nan"); c2 = verf[1][1] if len(verf) > 1 else None
# Bestimmtheit je Achse: Profil durch den besten Punkt, Breite des Bereichs mit Abstand <= bester + 0.01 m (Plateau = Achse nicht bestimmt)
bre = []
for ax in range(3):
    r = torch.arange(-1.0, 1.0 + 1e-6, 0.02, device=dev); Gp = torch.tensor(c1, device=dev, dtype=torch.float32).repeat(len(r), 1); Gp[:, ax] += r
    sp = bewerte(Gp).cpu().numpy(); ok = sp <= b1 + 0.01; k0 = int(np.abs(r.cpu().numpy()).argmin()); lo_i = k0
    while lo_i > 0 and ok[lo_i - 1]: lo_i -= 1
    hi_i = k0
    while hi_i < len(r) - 1 and ok[hi_i + 1]: hi_i += 1
    bre.append(float((hi_i - lo_i) * 0.02))
print("Plateaubreite (m) du/dn/dz: %.2f %.2f %.2f  (>0.3 = Achse NICHT bestimmt)" % tuple(bre), flush=True)
print("BESTER PLATZ: du %.3f dn %.3f dz %.3f -> Abstand %.3f m (Start %.3f m) | zweitbester Peak %.3f m bei (%.2f,%.2f,%.2f), Abstand zum besten %.2f m | Schaerfe (Median-bester)/Median = %.2f | %.1f s" % (c1[0], c1[1], c1[2], b1, null, b2, *(c2 if c2 is not None else (0, 0, 0)), np.linalg.norm(c1 - c2) if c2 is not None else 0, (np.median(s1) - b1) / np.median(s1), time.time() - t0))
res = dict(typ=a.typ, du=float(c1[0]), dn=float(c1[1]), dz=float(c1[2]), abstand_peak=b1, abstand_start=null, abstand_zweit=b2, plateau=bre, zweit=None if c2 is None else [float(x) for x in c2]); json.dump(res, open(os.path.join(OD, "sweep_" + a.typ.replace(":", "_") + ".json"), "w"), indent=1)
