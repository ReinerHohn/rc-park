#!/usr/bin/env python3
"""kante_auf_flaeche.py - Kante aus EINEM Foto auf eine bekannte Flaeche (STL-Teilnetz) projizieren (Alternative zu kante_3d.py ohne Bildzuordnung).

Aufruf: kante_auf_flaeche.py OBJ.json --kam K-6171 --pix "x,y;x,y;..." --box "x0,y0,z0,x1,y1,z1" --aus DIR --name N [--farbe gold|dunkel|kante] [--sig 3] [--n_aus 24] [--achse_n nx ny]
Ablauf: Minimalkostenpfad (kante_3d.kosten) zwischen den Pixel-Wegpunkten (auf der Kante von Hand gesetzt); je Pixel Strahl -> Schnitt mit den Dreiecken des STL
innerhalb --box (Weltmeter, Flaeche z. B. Erker-Unterbau); erster Treffer; Medianfilter + Spline. Ausgabe kante_<name>.json (pfad_xyz, optional pfad_uvz).
Grenze: nur so genau wie die Flaeche (Silhouette in anderem Foto pruefen, Gegenprobe Pflicht); Kante muss auf der Flaeche liegen (erhabene Rippe: Flaeche = Rippengrund, Fehler ~ Reliefhoehe)."""
import sys, os, json, glob, importlib.util
import numpy as np, cv2, trimesh
from scipy.interpolate import splprep, splev
from scipy.signal import medfilt
_d = os.path.dirname(os.path.abspath(__file__))
def lade(n):
    s = importlib.util.spec_from_file_location(n, os.path.join(_d, n + ".py")); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
EPI, K3 = lade("epilinie"), lade("kante_3d")

def main():
    a = sys.argv[1:]
    if len(a) < 7 or a[0].startswith("-"): sys.exit(__doc__)
    opt = lambda n, d: a[a.index(n) + 1] if n in a else d
    obj = json.load(open(a[0])); root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(a[0])))); od = os.path.join(root, os.path.dirname(obj["masstabelle"]))
    kid = opt("--kam", None); pix = [tuple(float(v) for v in q.split(",")) for q in opt("--pix", "").split(";") if q]
    bx = [float(v) for v in opt("--box", "").split(",")]; aus, name, modus, sig, n_aus = opt("--aus", "."), opt("--name", "kante"), opt("--farbe", "gold"), float(opt("--sig", 3)), int(opt("--n_aus", 24))
    if not kid or len(pix) < 2 or len(bx) != 6: sys.exit("--kam, >= 2 --pix und --box noetig")
    os.makedirs(aus, exist_ok=True); K = EPI.kam(od, kid); im = cv2.imread(glob.glob(os.path.join(root, obj["fotos_dir"], kid[2:] + "_*"))[0])
    m = trimesh.load(os.path.join(root, obj["stl"])); m.apply_scale(obj.get("stl_massstab", 87) / 1000.0)
    kk = json.load(open(os.path.join(od, "messprotokoll", kid + ".json")))["kamera"]; m.apply_translation(np.asarray(kk.get("rahmen_verschiebung", [0, 0, 0]), float))
    ct = m.triangles_center; sel = np.all((ct >= bx[:3]) & (ct <= bx[3:]), axis=1)
    sub = trimesh.Trimesh(m.vertices, m.faces[sel], process=False); print("Dreiecke in Box:", int(sel.sum()))
    H, W = im.shape[:2]; xs, ys = [p[0] for p in pix], [p[1] for p in pix]; r = 40
    x0, y0, x1, y1 = max(int(min(xs)) - r, 0), max(int(min(ys)) - r, 0), min(int(max(xs)) + r, W), min(int(max(ys)) + r, H)
    from skimage.graph import route_through_array
    c = K3.kosten(im[y0:y1, x0:x1], modus, sig); pf = []
    for p, q in zip(pix[:-1], pix[1:]):
        w, _ = route_through_array(c, (int(p[1] - y0), int(p[0] - x0)), (int(q[1] - y0), int(q[0] - x0)), fully_connected=True, geometric=True); pf += [(cc + x0, rr + y0) for rr, cc in w]
    pf = np.array(pf, float)[::6]; o = np.array([EPI.strahl(K, q)[0] for q in pf]); d = np.array([EPI.strahl(K, q)[1] for q in pf])
    loc, ir, _ = sub.ray.intersects_location(o, d, multiple_hits=False); P = np.full((len(pf), 3), np.nan); P[ir] = loc
    ok = ~np.isnan(P[:, 0]); print("Treffer", int(ok.sum()), "von", len(pf))
    if ok.sum() < 5: sys.exit("zu wenige Treffer")
    P = P[ok]; Pm0 = P
    Pm = np.array([medfilt(P[:, i], 5) for i in range(3)]).T; k_ = np.r_[True, np.linalg.norm(np.diff(Pm, axis=0), axis=1) > 1e-4]; Pm = Pm[k_]; tck, _ = splprep(Pm.T, s=len(Pm) * 0.0004); Q = np.array(splev(np.linspace(0, 1, n_aus), tck)).T
    res = dict(name=name, kam=kid, pix=[list(p) for p in pix], pfad_xyz=Q.round(3).tolist(), n_treffer=int(ok.sum()), farbe=modus)
    if "--achse_n" in a:
        n_ = np.array([float(v) for v in a[a.index("--achse_n") + 1:a.index("--achse_n") + 3]]); n_ /= np.linalg.norm(n_); u_ = np.array([n_[1], -n_[0]])
        res["pfad_uvz"] = [[round(float(p[:2] @ u_), 3), round(float(p[:2] @ n_), 3), round(float(p[2]), 3)] for p in Q]
    json.dump(res, open(os.path.join(aus, f"kante_{name}.json"), "w"), indent=1); print("->", os.path.join(aus, f"kante_{name}.json"))
if __name__ == "__main__": main()
