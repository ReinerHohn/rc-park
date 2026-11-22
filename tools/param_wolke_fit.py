#!/usr/bin/env python3
"""param_wolke_fit.py - Parameter EINES parametrischen Bauteils (objekt.json['bauteile'][typ]) per CMA-ES gegen die Punktwolke einpassen (Nutzerweg 8.11.: Parameter drehen,
immer naeher an die Wolke). Baut nur dieses Bauteil (NUR_BAUTEIL in baukasten_gen.py, ~1 s) und misst:
  J = getrimmter Mittelwert Abstand Wolkenpunkt -> Bauteilflaeche (Wolkenpunkte im Kasten des Startmodells + Rand, die dem Bauteil nahe sind)
      + w_rueck * getrimmter Mittelwert Abstand Bauteilflaeche (nur nach oben/aussen zeigende Dreiecke, Aufwaerts-Normale > 0.3) -> Wolke   (verhindert Aufblaehen ins Leere)
Parameterraum: <objektordner>/parameter_raum.json[<typ>] oder --raum; Format {"param": {"lo":..,"hi":..,"start":..}}; fehlt "start", gilt der Wert aus objekt.json.
Ergebnis: <objektordner>/wolkenfit_<typ>.json (Werte vor/nach, J vor/nach, Median/P90 vor/nach) - uebernommen wird NICHTS ohne --uebernehmen (schreibt overrides in objekt.json:
Quelle 'param_wolke_fit.py gegen wolke_netzrahmen.npy', Regel 3b).
  /media/oem/scan/venv-seg/bin/python -I tools/param_wolke_fit.py kaufhaus_grob3 satteldach:haupt [--wolke W.npy] [--iter 40] [--pop 12] [--uebernehmen]
"""
import os, sys, json, argparse, subprocess, tempfile, numpy as np, trimesh, cma
from scipy.spatial import cKDTree
from concurrent.futures import ThreadPoolExecutor
ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("typ"); ap.add_argument("--wolke", default="/media/oem/scan/rc-park_null/wolke_netzrahmen.npy")
ap.add_argument("--raum"); ap.add_argument("--iter", type=int, default=40); ap.add_argument("--pop", type=int, default=12); ap.add_argument("--rand", type=float, default=1.5)
ap.add_argument("--zmin", type=float, default=None); ap.add_argument("--zmax", type=float, default=None); ap.add_argument("--trim", type=float, default=0.9); ap.add_argument("--w_rueck", type=float, default=0.5); ap.add_argument("--kerne", type=int, default=6); ap.add_argument("--gesamt", action="store_true", help="Gesamtmodell bewerten (alle Bauteile), nur die genannten Parameter aendern; sonst Teil allein (verfaelscht, wenn andere Teile im Kasten der Wolke liegen)"); ap.add_argument("--uebernehmen", action="store_true")
ap.add_argument("--fotos", help="Kameras im Netzrahmen (sfm_kameras_export.py) -> Foto-Kantenterm (Regel 9d)"); ap.add_argument("--bilder"); ap.add_argument("--roi", help="x0,y0,z0,x1,y1,z1 Netzrahmen (m): nur Modellkanten darin zaehlen"); ap.add_argument("--nfotos", type=int, default=5); ap.add_argument("--w_foto", type=float, default=1.0)
ap.add_argument("--teilbox", type=float, default=None, help="Messung NUR im Ausschnitt: Bauteil allein bauen, Box +/- M Meter; Modell- UND Wolkenpunkte ausserhalb zaehlen nicht (8.11.: Gesamtmetrik blind fuer kleine Teile)")
ap.add_argument("--mit", default="", help="mit --teilbox: Traegerbauteile (z.B. satteldach:haupt), die zum Bau noetig sind; die Box entsteht nur aus den zusaetzlichen Eckpunkten")
ap.add_argument("--py", default=os.path.expanduser("~/.venvs/rcpark/bin/python")); a = ap.parse_args()
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); OD = os.path.join(ROOT, "modelle", a.objekt); SC = 87.0; K = 1000.0 / SC
OBJ = json.load(open(os.path.join(OD, "objekt.json"))); TYPEN = a.typ.split(","); SPEC = {t: next(b for b in OBJ["bauteile"] if b["typ"] == t) for t in TYPEN}
raum_all = json.load(open(a.raum or os.path.join(OD, "parameter_raum.json"))); raum = {(t, k): v for t in TYPEN for k, v in raum_all.get(t, {}).items() if isinstance(v, dict) and "lo" in v}
if not raum: sys.exit(f"kein Parameterraum fuer {a.typ} in parameter_raum.json")
names = list(raum); lo = np.array([raum[n]["lo"] for n in names], float); hi = np.array([raum[n]["hi"] for n in names], float)
x0 = np.array([float(raum[n].get("start", SPEC[n[0]].get(n[1]))) for n in names], float)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from pfade import temp_ordner; TMP = temp_ordner("pwf_")      # 22.11.2026: aufgeraeumt, nie Root
def bauen(vals, tag, nur=False, nur_typ=None):
    ueber = {t: {} for t in TYPEN}
    for (t, n), v in zip(names, vals): ueber[t][n] = float(v)
    stl = f"_pwf_{os.getpid()}_{tag}.stl"
    env = dict(os.environ, **({} if (a.gesamt and not nur) else {"NUR_BAUTEIL": (nur_typ or a.typ)}), OBJ_DIR=a.objekt, STL_NAME=stl, SCALE=str(SC), ELEMENTE_AUS="/dev/null", BAUTEIL_PARAM=json.dumps(ueber))
    r = subprocess.run([a.py, os.path.join(ROOT, "tools", "baukasten_gen.py"), a.objekt], env=env, capture_output=True, text=True)
    p = os.path.join(ROOT, "modelle", "stl", stl)
    if r.returncode != 0 or not os.path.exists(p): return None
    m = trimesh.load(p, process=False); os.remove(p); m.apply_scale(1.0 / K); return m          # zurueck in m (Netzrahmen)
P = np.load(a.wolke)[:, :3].astype(np.float32)
m0 = bauen(x0, "start")
if m0 is None: sys.exit("Startbau fehlgeschlagen")
BOX = None
if a.teilbox is not None:
    mt = bauen(x0, "teil", nur=True, nur_typ=(a.mit + "," + a.typ) if a.mit else None)
    if mt is None: sys.exit("Teilbau fehlgeschlagen")
    if a.mit:
        from scipy.spatial import cKDTree
        mr = bauen(x0, "traeger", nur=True, nur_typ=a.mit); V = np.asarray(mt.vertices); V = V[cKDTree(np.asarray(mr.vertices)).query(V)[0] > 1e-4]
        if len(V) < 4: sys.exit("keine zusaetzlichen Eckpunkte (Teil unsichtbar?)")
        lo_t, hi_t = V.min(0), V.max(0)
    else: lo_t, hi_t = mt.bounds
    BOX = (lo_t - a.teilbox, hi_t + a.teilbox); print("Teilbox", np.round(BOX[0], 1), np.round(BOX[1], 1), flush=True)
b0 = m0.bounds if BOX is None else np.array(BOX); Pc = P[np.all((P >= b0[0] - a.rand) & (P <= b0[1] + a.rand), 1)]; Pc = Pc[(Pc[:, 2] >= (a.zmin if a.zmin is not None else -1e9)) & (Pc[:, 2] <= (a.zmax if a.zmax is not None else 1e9))]; print(f"Wolkenpunkte im Kasten: {len(Pc)}", flush=True)
import sys; sys.path.insert(0, "/media/oem/scan/p3d_site")                                         # PyTorch3D (CUDA, selbst gebaut)
import torch, threading                                                                              # GPU (Nutzerregel: GPU immer nutzen): knn_points = 0,13 s je Richtung (torch.cdist 3 s)
from pytorch3d.ops import knn_points
DEV = "cuda"; PG = torch.tensor(Pc, dtype=torch.float32, device=DEV)[None]; GLOCK = threading.Lock()
BL = torch.tensor(BOX[0], dtype=torch.float32, device=DEV) if BOX else None; BH = torch.tensor(BOX[1], dtype=torch.float32, device=DEV) if BOX else None
def probe_gpu(m, n, seed=1):
    """Oberflaechenproben auf der GPU: Dreiecke flaechengewichtet (multinomial), Schwerpunktkoordinaten; Rueckgabe Punkte (1,n,3) + Aufwaerts-Maske (n,)"""
    V = torch.tensor(m.vertices, dtype=torch.float32, device=DEV); F = torch.tensor(m.faces, dtype=torch.int64, device=DEV)
    A = V[F]; ar = torch.linalg.cross(A[:, 1] - A[:, 0], A[:, 2] - A[:, 0]); fl = ar.norm(dim=1); g = torch.Generator(device=DEV); g.manual_seed(seed)
    fi = torch.multinomial(fl / fl.sum(), n, replacement=True, generator=g); r = torch.rand(n, 2, device=DEV, generator=g); f = r.sum(1) > 1; r[f] = 1 - r[f]
    T = A[fi]; Q = T[:, 0] + r[:, :1] * (T[:, 1] - T[:, 0]) + r[:, 1:] * (T[:, 2] - T[:, 0]); up = (ar[fi, 2] / fl[fi].clamp_min(1e-12)) > 0.3
    return Q[None], up
def messen(m):
    with GLOCK:
        Qt, up = probe_gpu(m, 40000)
        if BL is not None:
            mk = ((Qt[0] >= BL) & (Qt[0] <= BH)).all(1); Qt = Qt[:, mk]; up = up[mk]
            if Qt.shape[1] < 100: return 9.0, 9.0, 9.0
        dd = knn_points(PG, Qt, K=1).dists[0, :, 0].sqrt().cpu().numpy()
        Qu = Qt[:, up]; ru = knn_points(Qu, PG, K=1).dists[0, :, 0].sqrt().cpu().numpy() if Qu.shape[1] > 100 else np.zeros(0)
    d0 = dd[dd < a.rand]
    if len(d0) < 200: return 9.0, 9.0, 9.0
    d = np.sort(d0)[: int(len(d0) * a.trim)]; r = np.sort(ru)[: int(len(ru) * a.trim)].mean() if len(ru) else 0.0
    return float(d.mean() + a.w_rueck * r), float(np.median(d0)), float(np.percentile(d0, 90))

# ---------------- Foto-Kantenterm (Regel 9d): Modellkanten in kalibrierte Fotos projizieren, Abstand zur naechsten Fotokante (m, gekappt) -----------------
FOTO = []
if a.fotos:
    import cv2
    KAM = json.load(open(a.fotos)); r0 = np.array([float(x) for x in a.roi.split(",")]).reshape(2, 3); cen = r0.mean(0); SK = 0.25
    cand = []
    for nm, k in KAM.items():
        R = np.array(k["Rn"]); t = np.array(k["tn"]); x = R @ cen + t
        if x[2] <= 0: continue
        uv = (k["f"] * x[:2] / x[2] + [k["cx"], k["cy"]])
        if 0 < uv[0] < k["W"] and 0 < uv[1] < k["H"]: cand.append((np.linalg.norm(np.array(k["C"]) - cen), nm, k))
    cand.sort(key=lambda c: c[0])
    for d_, nm, k in cand[: a.nfotos]:
        g = cv2.imread(os.path.join(a.bilder, nm), cv2.IMREAD_GRAYSCALE | cv2.IMREAD_IGNORE_ORIENTATION)
        if g is None: continue
        g = cv2.resize(g, None, fx=SK, fy=SK, interpolation=cv2.INTER_AREA); e = cv2.Canny(cv2.GaussianBlur(g, (0, 0), 1.5), 40, 110)
        DT = cv2.distanceTransform((e == 0).astype(np.uint8), cv2.DIST_L2, 3); FOTO.append((nm, k, DT, np.array(k["Rn"]), np.array(k["tn"]), np.array(k["C"])))
    print("Foto-Term:", [f[0] for f in FOTO], flush=True)
def foto_kosten(m):
    if not FOTO: return 0.0
    m = m.copy(); m.merge_vertices(); V = np.asarray(m.vertices); ed = m.face_adjacency_edges[m.face_adjacency_angles > 0.5]; fa = m.face_adjacency
    mid = 0.5 * (V[ed[:, 0]] + V[ed[:, 1]]); ln = np.linalg.norm(V[ed[:, 0]] - V[ed[:, 1]], axis=1); sel = np.all((mid >= r0[0]) & (mid <= r0[1]), 1) & (ln > 0.15) & (ln < 2.0)     # lange Kanten (Ziegelstufen, Traufe) ausgeschlossen
    if sel.sum() < 5: return 1.0
    A, B = V[ed[sel, 0]], V[ed[sel, 1]]; tot = []
    for nm, k, DT, R, t, C in FOTO:
        t_ = np.linspace(0, 1, 6)[None, :, None]; Pp = (A[:, None] * (1 - t_) + B[:, None] * t_).reshape(-1, 3); X = Pp @ R.T + t; z = np.maximum(X[:, 2], 1e-3)
        uv = (k["f"] * X[:, :2] / z[:, None] + [k["cx"], k["cy"]]) * SK; ok = (X[:, 2] > 0.5) & (uv[:, 0] >= 0) & (uv[:, 1] >= 0) & (uv[:, 0] < DT.shape[1] - 1) & (uv[:, 1] < DT.shape[0] - 1)
        if ok.sum() < 20: continue
        d = DT[uv[ok, 1].astype(int), uv[ok, 0].astype(int)]; dm = d / SK * (z[ok] / k["f"]); tot.append(float(np.minimum(dm, 1.0).mean()))     # px -> m an der Modellkante
    return float(np.mean(tot)) if tot else 1.0
def J(vals, tag):
    m = bauen(vals, tag)
    if m is None: return 9.0
    return messen(m)[0] + (a.w_foto * foto_kosten(m) if FOTO else 0.0)
J0, med0, p90_0 = messen(m0); print(f"Start J={J0:.4f} Median {med0:.3f} P90 {p90_0:.3f}", flush=True)
sg = (hi - lo) / 4.0; es = cma.CMAEvolutionStrategy(list(np.clip(x0, lo, hi)), 0.5, dict(popsize=a.pop, bounds=[list(lo), list(hi)], CMA_stds=list(sg), verbose=-9, seed=1))
best = (J0, x0.copy())
with ThreadPoolExecutor(a.kerne) as ex:
    for it in range(a.iter):
        X = es.ask(); Y = list(ex.map(lambda t: J(t[1], f"{it}_{t[0]}"), enumerate(X))); es.tell(X, Y)
        i = int(np.argmin(Y))
        if Y[i] < best[0]: best = (Y[i], np.array(X[i]))
        print(f"it {it:3d} bestJ {best[0]:.4f} (Generation min {min(Y):.4f})", flush=True)
        if es.stop(): break
m1 = bauen(best[1], "ende"); J1, med1, p90_1 = messen(m1)
res = dict(objekt=a.objekt, typ=a.typ, wolke=os.path.basename(a.wolke), n_wolke=int(len(Pc)), parameter=[f"{t}.{n}" for t, n in names], vorher={f"{t}.{n}": float(v) for (t, n), v in zip(names, x0)}, nachher={f"{t}.{n}": round(float(v), 4) for (t, n), v in zip(names, best[1])},
           J_vorher=J0, J_nachher=J1, median_vorher=med0, median_nachher=med1, p90_vorher=p90_0, p90_nachher=p90_1)
json.dump(res, open(os.path.join(OD, f"wolkenfit_{a.typ.replace(':', '_').replace(',', '+')}.json"), "w"), indent=1)
print(json.dumps(res, indent=1))
if a.uebernehmen and J1 < J0:
    for b in OBJ["bauteile"]:
        if b["typ"] in TYPEN:
            for n, v in res["nachher"].items():
                t_, n_ = n.split(".", 1)
                if t_ == b["typ"]: b[n_] = v; b.setdefault("werte_quellen", {})[n_] = f"param_wolke_fit.py (CMA-ES) gegen wolke_netzrahmen.npy, Abstand Wolke->Bauteil ({a.typ}), Median {med0:.3f}->{med1:.3f} m"
    json.dump(OBJ, open(os.path.join(OD, "objekt.json"), "w"), indent=1, ensure_ascii=False); print("uebernommen")
