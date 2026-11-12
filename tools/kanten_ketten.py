#!/usr/bin/env python3
"""kanten_ketten.py - DURCHGEHENDE Linienzuege (Bogenrippen, Baender, Staebe) automatisch aus einem Foto: Skelett der Kantenkarte, an Kreuzungen GERADEAUS weiter (kleinste Richtungsaenderung), dann 3D wie kanten_features (Strahl x Modellflaeche, Sweep-Tiefen, Spline).
Aufruf: kanten_ketten.py OBJ.json --kam K-6171 --fenster x0 y0 x1 y1 --box "x0,y0,z0,x1,y1,z1" [--farbe stabil|gold|band] [--schwelle 130] [--sweep SWEEP.npz --nur_ref] [--schliessen 9] [--max_winkel 35] [--min_m 0.6] [--aus DIR --name N]
Ablauf: Kreuzungspixel (>= 3 Nachbarn) entfernen -> Segmente (laengster Weg, Stummel < 12 px verworfen) -> an jeder Kreuzung Segmentenden paaren: Tangenten (letzte 18 px) gegenlaeufig, Winkel < --max_winkel (Standard 35 Grad), beste Paare zuerst, Ende nur einmal -> Ketten -> je Kette 3D-Pfad (Sweep-Tiefe wo belegt, sonst Flaechentiefe; Belegung gemeldet) -> Spline 32 Punkte.
Ausgabe: DIR/ketten_<name>.json (wie features: klasse, laenge_m, pfad_xyz, normale_xyz, belegt, n_segmente, pixel) + ketten_<name>.jpg (Foto, Ketten farbig nummeriert). Grenzen: Tiefe nur auf Flaechenband gesichert; Doppelkanten (zwei Goldkanten je Rippe) bleiben zwei Ketten (Mittellinie: features_in_objekt Duplikatabstand)."""
import sys, os, json, glob, importlib.util
import numpy as np, cv2, trimesh
from skimage.morphology import skeletonize
from scipy.spatial import cKDTree
from scipy.ndimage import convolve, label
from scipy.interpolate import splprep, splev
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import dijkstra
_d = os.path.dirname(os.path.abspath(__file__))
def lade(n):
    s = importlib.util.spec_from_file_location(n, os.path.join(_d, n + ".py")); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
EPI = lade("epilinie")
a = sys.argv[1:]
if len(a) < 6: sys.exit(__doc__)
opt = lambda n, d: a[a.index(n) + 1] if n in a else d
obj = json.load(open(a[0])); root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(a[0])))); od = os.path.join(root, os.path.dirname(obj["masstabelle"]))
kam = opt("--kam", None); fw = [int(v) for v in a[a.index("--fenster") + 1:a.index("--fenster") + 5]]; bx = [float(v) for v in opt("--box", "").split(",")]
farbe, th, aus, name = opt("--farbe", "stabil"), float(opt("--schwelle", 130)), opt("--aus", "."), opt("--name", "ketten"); os.makedirs(aus, exist_ok=True)
MAXW = np.cos(np.radians(float(opt("--max_winkel", 35)))); MINM = float(opt("--min_m", 0.6))
K = EPI.kam(od, kam); im = cv2.imread(glob.glob(os.path.join(root, obj["fotos_dir"], kam[2:] + "_*"))[0]); H, W = im.shape[:2]; x0, y0, x1, y1 = fw
if farbe == "stabil":
    sm = cv2.imread(os.path.join(opt("--stabildir", "/media/oem/scan/rc-park_daten/kaufhaus_alle/stabil"), "ip_IMG_" + kam[2:] + ".png"), 0); sig = cv2.resize(sm, (W, H), interpolation=cv2.INTER_LINEAR).astype(np.float32)
elif farbe == "band":   # 12.11.: Rippenkoerper = schwarze Farbe (neutral dunkel) + Gold, Putz (rot) faellt weg -> EIN Skelett je Rippe statt eines je Goldlinie
    from skimage.morphology import remove_small_objects
    fi = im.astype(int); r_, g_, b_ = fi[..., 2], fi[..., 1], fi[..., 0]
    bm = ((fi.max(2) < 80) & ((r_ - b_) < 30)) | ((g_ > 0.62 * r_) & (r_ > 140) & ((r_ - b_) > 70)); bm = cv2.morphologyEx(bm.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((11, 11), np.uint8))
    gl = cv2.dilate((((g_ > 0.62 * r_) & (r_ > 140) & ((r_ - b_) > 70)).astype(np.uint8)), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (31, 31))); bm = bm * gl   # dunkle Pixel nur nahe Gold (Schatten in den Zwickeln ist keine Rippe)
    bm = remove_small_objects(bm.astype(bool), 800).astype(np.uint8); bm = cv2.morphologyEx(bm, cv2.MORPH_OPEN, np.ones((7, 7), np.uint8)); sig = bm.astype(np.float32) * 255
else:
    f = im.astype(np.float32); sig = np.clip((f[..., 2] + f[..., 1]) / 2 - f[..., 0], 0, None)
msk = (sig[y0:y1, x0:x1] > th).astype(np.uint8); cl = int(opt('--schliessen', 0))
if cl: msk = cv2.morphologyEx(msk, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (cl, cl)))   # Luecken der Kantenkarte schliessen (Fragmente entstehen dort, nicht an Kreuzungen)
sk = skeletonize(msk > 0); nb = convolve(sk.astype(np.uint8), np.ones((3, 3), np.uint8), mode="constant") - 1
junc = sk & (nb >= 3); jd = cv2.dilate(junc.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool); seg = sk & ~jd
lab, ns = label(seg, structure=np.ones((3, 3))); jl, nj = label(jd, structure=np.ones((3, 3)))
def langster(ys, xs):                                    # geordneter laengster Weg einer Segmentkomponente
    P = np.c_[xs, ys]; n = len(P); pr = cKDTree(P).query_pairs(1.5, output_type="ndarray")
    if len(pr) == 0: return P
    A = coo_matrix((np.ones(len(pr)), (pr[:, 0], pr[:, 1])), shape=(n, n)).tocsr(); A = A + A.T; d0 = dijkstra(A, indices=0, unweighted=True); a_ = int(np.argmax(np.where(np.isinf(d0), -1, d0)))
    da, pred = dijkstra(A, indices=a_, unweighted=True, return_predecessors=True); b_ = int(np.argmax(np.where(np.isinf(da), -1, da))); s = [b_]
    while s[-1] != a_ and pred[s[-1]] >= 0: s.append(int(pred[s[-1]]))
    return P[s[::-1]]
segs = []
for i in range(1, ns + 1):
    ys, xs = np.nonzero(lab == i)
    if len(xs) < 12: continue
    segs.append(langster(ys, xs).astype(float))
print("Segmente", len(segs), "Kreuzungen", nj)
def tangente(S, ende, k=18):                             # nach AUSSEN gerichtet
    v = (S[-1] - S[-1 - min(k, len(S) - 1)]) if ende else (S[0] - S[min(k, len(S) - 1)]); return v / (np.linalg.norm(v) + 1e-9)
ends = []                                                # (seg, ende, punkt, tangente, kreuzungs-id)
jpts = np.array(np.nonzero(jd)).T[:, ::-1] if jd.any() else np.zeros((0, 2)); jtree = cKDTree(jpts) if len(jpts) else None
for si, S in enumerate(segs):
    for e in (0, 1):
        p = S[-1] if e else S[0]
        if jtree is None: continue
        dd, jj = jtree.query(p)
        if dd <= 4.5: ends.append((si, e, p, tangente(S, bool(e)), int(jl[jpts[jj][1], jpts[jj][0]])))
paare = []
for jid in set(e[4] for e in ends):
    E_ = [e for e in ends if e[4] == jid]
    for i in range(len(E_)):
        for j in range(i + 1, len(E_)):
            if E_[i][0] == E_[j][0]: continue
            c = float(E_[i][3] @ (-E_[j][3])); v = E_[j][2] - E_[i][2]; vn = np.linalg.norm(v)
            gerade = 1.0 if vn < 3 else min(float(E_[i][3] @ (v / vn)), float(-E_[j][3] @ (v / vn)))
            if c >= MAXW and gerade >= MAXW - 0.1: paare.append((c + gerade, E_[i], E_[j]))
paare.sort(key=lambda t: -t[0]); benutzt = set(); nachbar = {}
for sc, e1, e2 in paare:
    k1, k2 = (e1[0], e1[1]), (e2[0], e2[1])
    if k1 in benutzt or k2 in benutzt: continue
    benutzt |= {k1, k2}; nachbar.setdefault(e1[0], []).append((e1[1], e2[0], e2[1])); nachbar.setdefault(e2[0], []).append((e2[1], e1[0], e1[1]))
besucht = set(); ketten = []
for s0 in range(len(segs)):
    if s0 in besucht: continue
    st = s0                                              # an ein Kettenende laufen
    while True:
        nx = [n for n in nachbar.get(st, []) if n[1] not in besucht and n[1] != s0]
        if not nx: break
        break
    # Kette als Pfad durch Nachbarschaftsgraph (jedes Segment max. 2 Nachbarn)
    ende_s = s0; vorg = None
    while True:
        nn = [n for n in nachbar.get(ende_s, []) if n[1] != vorg]
        if len(nn) == 0 or nn[0][1] == s0: break
        vorg, ende_s = ende_s, nn[0][1]
    kette = []; cur = ende_s; prev = None; ein_e = None
    # von ende_s aus alle Segmente der Kette sammeln und Orientierung bestimmen
    reihe = [ende_s]; seen = {ende_s}; cur = ende_s
    while True:
        nn = [n for n in nachbar.get(cur, []) if n[1] not in seen]
        if not nn: break
        cur = nn[0][1]; reihe.append(cur); seen.add(cur)
    besucht |= seen; ketten.append(reihe)
def kettenpixel(reihe):
    P = []; vor = None
    for k, si in enumerate(reihe):
        S = segs[si]
        if k == 0:
            if len(reihe) > 1:
                nxt = reihe[1]; ok = [n for n in nachbar[si] if n[1] == nxt][0]; S = S if ok[0] == 1 else S[::-1]
            P.append(S); vor = S[-1]
        else:
            S = S if np.linalg.norm(S[0] - vor) <= np.linalg.norm(S[-1] - vor) else S[::-1]; P.append(S); vor = S[-1]
    return np.vstack(P) + [x0, y0]
SW = None
if "--sweep" in a:
    zz = np.load(opt("--sweep", "")); Ps = zz["P"]; ok_ = np.isin(zz["ref"], [i for i, f_ in enumerate(zz["fotos"]) if kam[2:] in str(f_)]) if "--nur_ref" in a else np.ones(len(Ps), bool)
    pj = [EPI.projekt(K, q_) for q_ in Ps]; vv = np.array([p_ is not None for p_ in pj]) & ok_; Ps = Ps[vv]; pj = np.array([p_ for p_, o_ in zip(pj, vv) if o_]); SW = (cKDTree(pj), np.linalg.norm(Ps - K["c"], axis=1))
kk = json.load(open(os.path.join(od, "messprotokoll", kam + ".json")))["kamera"]
m = trimesh.load(os.path.join(root, obj["stl"])); m.apply_scale(obj.get("stl_massstab", 87) / 1000.0); m.apply_translation(np.asarray(kk.get("rahmen_verschiebung", [0, 0, 0]), float))
ct = m.triangles_center; sel = np.all((ct >= bx[:3]) & (ct <= bx[3:]), axis=1); sub = trimesh.Trimesh(m.vertices, m.faces[sel], process=False); fn = np.asarray(sub.face_normals)
out = []
for reihe in ketten:
    PX = kettenpixel(reihe); pp = PX[::5]
    if len(pp) < 8: continue
    o = np.array([EPI.strahl(K, q)[0] for q in pp]); d = np.array([EPI.strahl(K, q)[1] for q in pp]); loc, ir, it_ = sub.ray.intersects_location(o, d, multiple_hits=False)
    if len(ir) < 8: continue
    tt = np.linalg.norm(loc - K["c"], axis=1); belegt = None
    if SW is not None:
        dd_, jj_ = SW[0].query(pp[ir], distance_upper_bound=6.0); fl = np.isfinite(dd_) & (np.abs(SW[1][np.minimum(jj_, len(SW[1]) - 1)] - tt) < 0.6); belegt = float(fl.mean())
        if fl.sum() >= 4:
            s_ = np.arange(len(ir), dtype=float); tz = np.interp(s_, s_[fl], SW[1][jj_[fl]]); tz = np.convolve(np.pad(tz, 4, mode="edge"), np.ones(9) / 9, mode="valid"); loc = o[ir] + d[ir] * tz[:, None]
    nf = fn[it_] * np.where(np.sum(fn[it_] * d[ir], axis=1) > 0, -1.0, 1.0)[:, None]; nm = nf.mean(axis=0); nm /= np.linalg.norm(nm)
    P3 = loc[np.r_[True, np.linalg.norm(np.diff(loc, axis=0), axis=1) > 1e-3]]
    try: tck, _ = splprep(P3.T, s=len(P3) * 0.0016); Q = np.array(splev(np.linspace(0, 1, 32), tck)).T
    except Exception: continue
    L = float(np.linalg.norm(np.diff(Q, axis=0), axis=1).sum())
    if L < MINM: continue
    sehne = Q[-1] - Q[0]; dz = abs(sehne[2]) / (np.linalg.norm(sehne) + 1e-9)
    out.append(dict(klasse=("waagerecht" if dz < 0.2 else "senkrecht" if dz > 0.85 else "geneigt"), laenge_m=round(L, 2), n_segmente=len(reihe), belegt=None if belegt is None else round(belegt, 2), pfad_xyz=Q.round(3).tolist(), normale_xyz=nm.round(3).tolist(), pixel=PX[::8].tolist()))
out.sort(key=lambda t: -t["laenge_m"]); json.dump(out, open(os.path.join(aus, f"ketten_{name}.json"), "w"))
c = im[y0:y1, x0:x1].copy(); fs = 1000 / c.shape[0]; c = cv2.resize(c, None, fx=fs, fy=fs, interpolation=cv2.INTER_AREA); rng = np.random.default_rng(3)
for i, dd in enumerate(out):
    col = tuple(int(v) for v in rng.integers(80, 255, 3)); pts = ((np.array(dd["pixel"]) - [x0, y0]) * fs).astype(np.int32); cv2.polylines(c, [pts], False, col, 4); cv2.putText(c, f"{i}:{dd['laenge_m']}m s{dd['n_segmente']}", tuple(pts[len(pts) // 2]), 0, 0.6, (255, 255, 255), 2)
cv2.imwrite(os.path.join(aus, f"ketten_{name}.jpg"), c); print(len(out), "Ketten:", [(i, d["klasse"], d["laenge_m"], d["n_segmente"], d["belegt"]) for i, d in enumerate(out)][:24])
