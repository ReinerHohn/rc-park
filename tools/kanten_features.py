#!/usr/bin/env python3
"""kanten_features.py - Linienhafte Features (Rippen, Baender, Leisten, Fensterstaebe, Dachkanten ...) in EINEM Foto automatisch finden, klassifizieren und auf die Modellflaeche legen.

Aufruf: kanten_features.py OBJ.json --kam K-6171 --fenster x0 y0 x1 y1 --box "x0,y0,z0,x1,y1,z1" [--farbe gold|dunkel|hell] [--schwelle 70] [--maske KURVEN.json]
        [--maskenbreite_px 40] [--paar_m 0.2] [--pruef K-6259] [--min_px 110] [--aus DIR] [--name N]
Ablauf (reine Geometrie + Bildverarbeitung, nichts objektspezifisch):
  1. Farbmaske (Standard: Goldanteil = (R+G)/2 - B) im Fenster -> Skelett (skeletonize).
  2. Optional --maske: Datei mit 3D-Kurven schon vorhandener Features ({"kurven": [[[x,y,z],...], ...]} Welt) -> in die Kamera projiziert und aus dem Skelett ausgenommen: uebrig bleibt, was FEHLT.
  3. Skelett in Zweige zerlegt (iterativ laengster Weg je Zusammenhang, Umgebung entfernt), je Zweig Strahl x Modellflaeche (STL-Teilnetz Box) -> 3D-Pfad, Spline.
  4. Klasse je Feature aus der 3D-Lage: waagerecht (|dz| klein gegen Laenge), senkrecht, geneigt; gerade (Pfeilhoehe < 3 % der Sehne) oder gebogen; Laenge, mittlere Normale.
Ausgabe: DIR/features_<name>.json (je Feature: klasse, laenge_m, pfad_xyz, normale_xyz, pixel), features_<name>.jpg (Foto + Pfade nummeriert, Klasse).
Grenzen: Tiefe kommt von der Modellflaeche (Fehler ~ Flaechenfehler, an Bogen A 2 cm); Entscheidung 'Feature gehoert ins Modell' trifft Foto-Gegenprobe (zweite Kamera) und die Abnahme; Wandrauschen bei niedriger Schwelle."""
import sys, os, json, glob, importlib.util
import numpy as np, cv2, trimesh
from skimage.morphology import skeletonize
from scipy.spatial import cKDTree
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components, dijkstra
from scipy.interpolate import splprep, splev
_d = os.path.dirname(os.path.abspath(__file__))
def lade(n):
    s = importlib.util.spec_from_file_location(n, os.path.join(_d, n + ".py")); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
EPI = lade("epilinie")
a = sys.argv[1:]
if len(a) < 7: sys.exit(__doc__)
opt = lambda n, d: a[a.index(n) + 1] if n in a else d
obj = json.load(open(a[0])); root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(a[0])))); od = os.path.join(root, os.path.dirname(obj["masstabelle"]))
kam = opt("--kam", None); fw = [int(v) for v in a[a.index("--fenster") + 1:a.index("--fenster") + 5]]; bx = [float(v) for v in opt("--box", "").split(",")]
farbe, th, mb, minpx, aus, name = opt("--farbe", "gold"), float(opt("--schwelle", 70)), int(opt("--maskenbreite_px", 40)), int(opt("--min_px", 110)), opt("--aus", "."), opt("--name", "feat"); os.makedirs(aus, exist_ok=True)
K = EPI.kam(od, kam); im = cv2.imread(glob.glob(os.path.join(root, obj["fotos_dir"], kam[2:] + "_*"))[0]); H, W = im.shape[:2]; x0, y0, x1, y1 = fw
f = im.astype(np.float32); sig = {"gold": np.clip((f[..., 2] + f[..., 1]) / 2 - f[..., 0], 0, None), "dunkel": 255 - f.mean(axis=2), "hell": f.mean(axis=2)}[farbe]
sk = skeletonize((sig > th)[y0:y1, x0:x1]); ys, xs = np.nonzero(sk); px = np.c_[xs + x0, ys + y0]
if "--maske" in a:
    mk = np.zeros((H, W), np.uint8)
    for kv in json.load(open(opt("--maske", "")))["kurven"]:
        q = [EPI.projekt(K, np.array(w)) for w in kv]; q = np.array([p for p in q if p is not None]).astype(np.int32)
        if len(q) > 1: cv2.polylines(mk, [q], False, 255, mb)
    px = px[mk[px[:, 1], px[:, 0]] == 0]
print("Skelettpixel", len(px))
kk = json.load(open(os.path.join(od, "messprotokoll", kam + ".json")))["kamera"]
m = trimesh.load(os.path.join(root, obj["stl"])); m.apply_scale(obj.get("stl_massstab", 87) / 1000.0); m.apply_translation(np.asarray(kk.get("rahmen_verschiebung", [0, 0, 0]), float))
ct = m.triangles_center; sel = np.all((ct >= bx[:3]) & (ct <= bx[3:]), axis=1); sub = trimesh.Trimesh(m.vertices, m.faces[sel], process=False); fn = np.asarray(sub.face_normals)
dbg = []; rest = np.ones(len(px), bool); tr = cKDTree(px); out = []
for it in range(80):
    ids = np.where(rest)[0]
    if len(ids) < 40: break
    pr = cKDTree(px[ids]).query_pairs(2.5, output_type="ndarray")
    if len(pr) == 0: break
    A = coo_matrix((np.ones(len(pr)), (pr[:, 0], pr[:, 1])), shape=(len(ids), len(ids))).tocsr(); A = A + A.T
    nc, lab = connected_components(A, directed=False); idx = np.where(lab == np.bincount(lab).argmax())[0]
    if len(idx) < 40: break
    sb = A[idx][:, idx]; d0 = dijkstra(sb, indices=0, unweighted=True); a_ = int(np.argmax(np.where(np.isinf(d0), -1, d0)))
    da, pred = dijkstra(sb, indices=a_, unweighted=True, return_predecessors=True); b_ = int(np.argmax(np.where(np.isinf(da), -1, da))); seq = [b_]
    while seq[-1] != a_ and pred[seq[-1]] >= 0: seq.append(int(pred[seq[-1]]))
    gl = ids[idx[seq[::-1]]]; nb = tr.query_ball_point(px[gl], 12.0); rest[np.unique(np.concatenate([np.array(v, int) for v in nb]))] = False
    if len(gl) < minpx: continue
    pp = px[gl][::6]; o = np.array([EPI.strahl(K, q)[0] for q in pp]); d = np.array([EPI.strahl(K, q)[1] for q in pp])
    loc, ir, it_ = sub.ray.intersects_location(o, d, multiple_hits=False)
    if len(ir) < 6: dbg.append((int(px[gl][0][0]), int(px[gl][0][1]), len(gl), len(ir))); continue
    nf = fn[it_] * np.where(np.sum(fn[it_] * d[ir], axis=1) > 0, -1.0, 1.0)[:, None]; nm = nf.mean(axis=0); nm /= np.linalg.norm(nm)
    P = loc[np.r_[True, np.linalg.norm(np.diff(loc, axis=0), axis=1) > 1e-3]]
    try: tck, _ = splprep(P.T, s=len(P) * 0.0004); Q = np.array(splev(np.linspace(0, 1, 24), tck)).T
    except Exception: continue
    L = float(np.linalg.norm(np.diff(Q, axis=0), axis=1).sum()); sehne = Q[-1] - Q[0]; sl = float(np.linalg.norm(sehne))
    if L < float(opt("--min_m", 0.35)): continue
    dz = abs(sehne[2]) / (sl + 1e-9); mid = Q[len(Q) // 2]; pfeil = float(np.linalg.norm(np.cross(Q[-1] - Q[0], mid - Q[0])) / (sl + 1e-9)) / (sl + 1e-9)
    ori = "waagerecht" if dz < 0.2 else ("senkrecht" if dz > 0.85 else "geneigt"); form = "gerade" if pfeil < 0.03 else "gebogen"
    pq = px[gl][::10].astype(float); tv = np.diff(pq, axis=0); ang = np.unwrap(np.arctan2(tv[:, 1], tv[:, 0])); wel = float(np.abs(np.diff(ang)).mean()) if len(ang) > 2 else 9.0   # Welligkeit: mittlere Richtungsaenderung je 10 px (Wandrauschen schlaengelt, Rippen laufen glatt)
    if wel > float(opt("--max_wellig", 9)): continue
    out.append(dict(wellig=round(wel, 2), klasse=f"{ori}, {form}", laenge_m=round(L, 2), pfad_xyz=Q.round(3).tolist(), normale_xyz=nm.round(3).tolist(), pixel=px[gl][::8].tolist()))
# Doppelkanten (zwei Goldkanten je Rippe) zu Mittellinie zusammenlegen: Pfade mit mittlerem 3D-Abstand < --paar_m (0,14) und gleicher Richtung
pm_ = float(opt("--paar_m", 0.2)); out.sort(key=lambda d: -d["laenge_m"]); used = set(); mer = []
for i, d in enumerate(out):
    if i in used: continue
    Qi = np.array(d["pfad_xyz"]); grp = [i]
    for j in range(i + 1, len(out)):
        if j in used: continue
        Qj = np.array(out[j]["pfad_xyz"]); Qj = Qj if np.linalg.norm(Qi[0] - Qj[0]) + np.linalg.norm(Qi[-1] - Qj[-1]) <= np.linalg.norm(Qi[0] - Qj[-1]) + np.linalg.norm(Qi[-1] - Qj[0]) else Qj[::-1]
        if np.linalg.norm(Qi - Qj, axis=1).mean() < pm_: grp.append(j); used.add(j); Qi = (Qi + Qj) / 2 if len(grp) == 2 else Qi
    d["pfad_xyz"] = Qi.round(3).tolist(); d["n_kanten"] = len(grp); mer.append(d)
out = mer
# Gegenprobe in zweiter Kamera: Anteil der in --pruef projizierten Pfadpunkte mit Signal in 8 px Umgebung
if "--pruef" in a:
    K2 = EPI.kam(od, opt("--pruef", "")); im2 = cv2.imread(glob.glob(os.path.join(root, obj["fotos_dir"], opt("--pruef", "")[2:] + "_*"))[0]); f2 = im2.astype(np.float32)
    s2 = {"gold": np.clip((f2[..., 2] + f2[..., 1]) / 2 - f2[..., 0], 0, None), "dunkel": 255 - f2.mean(axis=2), "hell": f2.mean(axis=2)}[farbe]; s2 = cv2.dilate(cv2.GaussianBlur(s2, (0, 0), 1.5), np.ones((7, 7), np.uint8)); H2, W2 = s2.shape
    def mw(q, dx, dy):
        v = [s2[int(p[1] + dy), int(p[0] + dx)] for p in q if p is not None and 0 <= p[0] + dx < W2 and 0 <= p[1] + dy < H2]; return (float(np.mean(v)), len(v)) if len(v) >= 8 else (None, len(v))
    for d in out:   # Kontrast = Signal auf dem Pfad / Mittel gleicher, seitlich verschobener Pfade (+-30 px); ohne echte Linie ~1, mit Linie deutlich > 1,5
        q = [EPI.projekt(K2, np.array(w)) for w in d["pfad_xyz"]]; m0, n0 = mw(q, 0, 0); rs = [mw(q, dx, dy)[0] for dx, dy in ((30, 0), (-30, 0), (0, 30), (0, -30), (22, 22), (-22, -22))]; rs = [r for r in rs if r is not None]
        d["gegenprobe"] = round(m0 / (np.mean(rs) + 1e-6), 2) if m0 is not None and rs else None; d["gegenprobe_n"] = n0
out.sort(key=lambda d: -d["laenge_m"]); json.dump(out, open(os.path.join(aus, f"features_{name}.json"), "w"))
c = im[y0:y1, x0:x1].copy(); fs = 1000 / c.shape[0]; c = cv2.resize(c, None, fx=fs, fy=fs, interpolation=cv2.INTER_AREA)
for i, d in enumerate(out):
    pts = ((np.array(d["pixel"]) - [x0, y0]) * fs).astype(np.int32); cv2.polylines(c, [pts], False, (255, 0, 255), 3); cv2.putText(c, f"{i} {d['klasse'][:6]} x{d['n_kanten']} w{d['wellig']} g{d.get('gegenprobe')}", tuple(pts[len(pts) // 2]), 0, 0.6, (0, 255, 255), 2)
cv2.imwrite(os.path.join(aus, f"features_{name}.jpg"), c); print(len(out), "Features:", [(i, d["klasse"], d["laenge_m"]) for i, d in enumerate(out)][:30])
