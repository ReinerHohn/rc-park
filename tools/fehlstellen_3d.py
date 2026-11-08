#!/usr/bin/env python3
"""fehlstellen_3d.py - FEHLENDE Elemente eines Modells aus dem Foto-Diff als 3D-Kandidatenregionen (2026-11-08).

Verfahren (generisch, Objekt/STL/Wolke per Argument):
 1. je Foto foto_diff (im Prozess, Kostenkarte --kostenkarte, Bewertungsmaske = Silhouette + Rand): GELB = Fotokantenpixel (fkp), deren Abstand zur
    naechsten Modellkante die Kappe (= --tol, Standard 0,35 m) erreicht (dM >= 1).
 2. jeder gelbe Pixel -> Strahl der Fotokamera (Lochkamera auf dem um k1 entzerrten Foto, wie foto_diff: R,t,f,cx,cy aus K-<foto>.json) -> 3D-Punkt =
    Tiefe der VORDEREN Wolkenschicht im Schlauch (--schlauch, 0,15 m): Median der Tiefen aller Schlauchpunkte, die hoechstens --schicht (0,5 m) hinter dem
    naechsten Schlauchpunkt liegen (sonst mischt Wolke hinter Luecken/Fenstern); < --min-wolke (8) Punkte -> verworfen (Wolke blind, z. B. Dach; Anteil gemeldet).
 3. Punkte aller Fotos, ausserhalb der Modellbox + --nachbar (4 m) verworfen, DBSCAN (eps 0,4 m, eigene Umsetzung mit scipy) -> Regionen; mindestens
    --min-fotos (3) Fotos muessen die Region stuetzen (jedes Foto >= --min-punkte-foto Punkte darin), sonst verworfen. Rang = Punktzahl * Fotozahl.
 4. Ausgabe <objektordner>/fehlstellen.json (oder --json) + PNG (Front x-z, Seite y-z, Oben x-y).
Quellen-Blindheit: die Wolke sieht Dach/steile Flaechen schlecht (verworfener Anteil wird gemeldet); Kantenpixel sind Fotokanten, keine Aussage, WAS fehlt.
Aufruf: /media/oem/scan/venv-seg/bin/python -I tools/fehlstellen_3d.py modelle/kaufhaus_grob/objekt.json --stl modelle/stl/kaufhaus_grob_1-87.stl \
        --wolke /media/oem/scan/rc-park_null/wolke_netzrahmen.npy --fotos 000,004,...
"""
import sys, os, json, glob, argparse, contextlib, io, numpy as np, cv2, trimesh
from scipy.spatial import cKDTree
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fehlteile_finden as FF, foto_diff as FD

def gelbe_pixel(objp, nr, stl, tol, outdir, glaettung):
    """foto_diff (Kostenkarte) -> gelbe Pixel (u,v) im entzerrten Foto + Kamera. Karten werden in outdir wiederverwendet."""
    obj = json.load(open(objp)); root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(objp))))
    kp = FF.k_datei(objp, obj, root, nr); K = json.load(open(kp)); kk = K["kamera"]
    npz = os.path.join(outdir, f"kosten_{nr}.npz"); mask = os.path.join(outdir, f"maske_{nr}.png")
    base = [objp, nr, "--stl", stl, "--aus", outdir, "--tol", str(tol), "--glaettung", str(glaettung)]
    if not os.path.exists(npz):
        import time
        for versuch in range(8):                                                                                           # GPU mit fremden Jobs geteilt: bei OOM warten und wiederholen
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    FD.main(base + ["--maske-aus", mask])
                    FD.main(base + ["--bewertung-maske", mask, "--kostenkarte", npz])
                break
            except Exception as ex:
                if "out of memory" not in str(ex) or versuch == 7: raise
                import torch; torch.cuda.empty_cache(); print(f"  {nr}: GPU voll, warte 30 s (Versuch {versuch + 1})", flush=True); time.sleep(30)
    z = np.load(npz); gelb = z["fkp"] & (z["dM"].astype(np.float32) >= 0.999)
    im = cv2.imread(glob.glob(os.path.join(root, obj["fotos_dir"], nr + "_*"))[0]); H, W = im.shape[:2]
    R, t, f, quelle, _ = FF.kamera_laden(K, obj, nr, root, W, H)
    vs, us = np.nonzero(gelb)
    return dict(R=np.asarray(R, float), t=np.asarray(t, float), f=float(f), cx=float(kk.get("cx", W / 2)), cy=float(kk.get("cy", H / 2)), u=us, v=vs, fk=int(z["fkp"].sum()), kk=kk)

def strahlpunkte(cam, P, tree_uv, uv, zc, u, v, schlauch, schicht, min_wolke):
    """Je Pixel (u,v) 3D-Punkt aus der Wolke (Schlauch um den Strahl). Rueckgabe (Punkte[n,3], ok-Maske)."""
    R, t, f = cam["R"], cam["t"], cam["f"]; d = np.c_[(u - cam["cx"]) / f, (v - cam["cy"]) / f, np.ones(len(u))]            # Kamerarichtung (z=1) -> Tiefe = z
    out = np.full((len(u), 3), np.nan); zmin_ok = 6.0                                                                      # Wolkenpunkte naeher als 3 m nie als Tiefe (Strahlnaehe)
    rpx = schlauch * f / zmin_ok                                                                                           # grosszuegiger Bildradius, danach exakt in 3D
    nb = tree_uv.query_ball_point(np.c_[u, v], r=rpx)
    for i, idx in enumerate(nb):
        if len(idx) < min_wolke: continue
        idx = np.asarray(idx); Xc = P_cam[idx]                                                                             # Wolke in Kamerakoordinaten
        z = Xc[:, 2]; dn = d[i] / np.linalg.norm(d[i]); s = Xc @ dn; perp = np.linalg.norm(Xc - np.outer(s, dn), axis=1)   # Abstand zum Strahl
        m = (perp <= schlauch) & (z > zmin_ok)
        if m.sum() < min_wolke: continue
        zz = z[m]; z0 = np.percentile(zz, 5); sel = zz <= z0 + schicht
        if sel.sum() < min_wolke: continue
        zm = float(np.median(zz[sel])); out[i] = R.T @ (d[i] * zm - t)
    return out

def dbscan(X, eps, min_pts):
    tr = cKDTree(X); nb = tr.query_ball_point(X, r=eps, return_length=True); core = nb >= min_pts
    pairs = tr.query_pairs(eps, output_type="ndarray")
    if len(pairs): pairs = pairs[core[pairs[:, 0]] & core[pairs[:, 1]]]
    n = len(X); g = coo_matrix((np.ones(len(pairs)), (pairs[:, 0], pairs[:, 1])), shape=(n, n)) if len(pairs) else coo_matrix((n, n))
    _, lab = connected_components(g, directed=False); lab = lab.copy()
    # Randpunkte: naechster Kernpunkt in eps; sonst Rauschen (-1)
    ci = np.nonzero(core)[0]
    if len(ci):
        trc = cKDTree(X[ci]); dd, jj = trc.query(X); ok = dd <= eps; lab = np.where(core, lab, np.where(ok, lab[ci[jj]], -1)); lab[~core & ~ok] = -1
    else: lab[:] = -1
    lab[~core & (lab >= 0) & False] = -1
    return lab

def dbscan_rekursiv(X, eps, min_pts, gross, tiefe=0):
    """DBSCAN; Cluster mit Boxdiagonale > gross (m) werden mit halbem eps neu zerlegt (Kette ueber dichte Fassadentextur trennen), bis eps < 0,1 m."""
    lab = dbscan(X, eps, min_pts); out = np.full(len(X), -1); nxt = 0
    for l in sorted(set(lab) - {-1}):
        idx = np.nonzero(lab == l)[0]; Y = X[idx]; diag = float(np.linalg.norm(np.percentile(Y, 98, 0) - np.percentile(Y, 2, 0)))
        if diag > gross and eps / 2 >= 0.1:
            sub = dbscan_rekursiv(Y, eps / 2, min_pts, gross, tiefe + 1)
            for sl in sorted(set(sub) - {-1}): out[idx[sub == sl]] = nxt; nxt += 1
        else: out[idx] = nxt; nxt += 1
    return out

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0]); ap.add_argument("objekt"); ap.add_argument("--stl", required=True); ap.add_argument("--wolke", required=True)
    ap.add_argument("--fotos", required=True, help="Komma-Liste, z. B. 000,004"); ap.add_argument("--tol", type=float, default=0.35); ap.add_argument("--glaettung", type=float, default=0.18)
    ap.add_argument("--schlauch", type=float, default=0.15); ap.add_argument("--schicht", type=float, default=0.5); ap.add_argument("--min-wolke", type=int, default=8)
    ap.add_argument("--eps", type=float, default=0.4); ap.add_argument("--min-pts", type=int, default=15); ap.add_argument("--min-fotos", type=int, default=3); ap.add_argument("--min-punkte-foto", type=int, default=5)
    ap.add_argument("--nachbar", type=float, default=4.0); ap.add_argument("--max-pixel", type=int, default=20000, help="Obergrenze gelber Pixel je Foto (gleichmaessig ausgeduennt)")
    ap.add_argument("--arbeit", required=True, help="Ordner fuer Kostenkarten/Masken/foto_diff-Ausgabe (wiederverwendet)"); ap.add_argument("--png"); ap.add_argument("--json"); ap.add_argument("--top", type=int, default=15)
    ap.add_argument("--vox", type=float, default=0.2); ap.add_argument("--gross", type=float, default=4.0, help="Regionen mit Boxdiagonale > gross m werden mit halbem eps weiter zerlegt"); ap.add_argument("--cache", action="store_true", help="punkte_cache.npz in --arbeit wiederverwenden (nur Clustering neu)")
    ap.add_argument("--fassade-n", type=float, nargs=2, default=None, help="Fassadennormale (nx ny) im Modellrahmen -> n_median = Lage zur Fassade (m)")
    a = ap.parse_args(argv); os.makedirs(a.arbeit, exist_ok=True)
    global P_cam
    obj = json.load(open(a.objekt)); od = os.path.dirname(os.path.abspath(a.objekt))
    wolke = np.load(a.wolke).astype(np.float64); fotos = [s.strip() for s in a.fotos.split(",") if s.strip()]
    pts, fid, stat = [], [], {}
    box = None; cache = os.path.join(a.arbeit, "punkte_cache.npz")
    if a.cache and os.path.exists(cache):                                                                                  # Punkte einer frueheren Runde (gleiche Fotos/Wolke/Schlauch) wiederverwenden
        c_ = np.load(cache, allow_pickle=True); pts, fid, stat, box = [c_["X"]], list(c_["fid"]), json.loads(str(c_["stat"])), c_["box"]; fotos = []
    for nr in fotos:
        cam = gelbe_pixel(a.objekt, nr, a.stl, a.tol, a.arbeit, a.glaettung)
        if box is None:                                                                                                    # Modellbox im Rahmen der Kamera (wie foto_diff._netz)
            m = trimesh.load(a.stl); m.apply_scale(obj.get("stl_massstab", 87) / 1000.0); tr_ = np.asarray(cam["kk"].get("rahmen_verschiebung", [0, 0, 0]), float); m.apply_translation(tr_); box = m.bounds.copy()
        u, v = cam["u"], cam["v"]
        if len(u) > a.max_pixel: sel = np.linspace(0, len(u) - 1, a.max_pixel).astype(int); u, v = u[sel], v[sel]
        P_cam = wolke @ cam["R"].T + cam["t"]; vorn = P_cam[:, 2] > 1.0
        uv = np.c_[cam["f"] * P_cam[:, 0] / np.maximum(P_cam[:, 2], 1e-6) + cam["cx"], cam["f"] * P_cam[:, 1] / np.maximum(P_cam[:, 2], 1e-6) + cam["cy"]]
        idx_v = np.nonzero(vorn)[0]; Pc_full = P_cam; P_cam = Pc_full[idx_v]; tree = cKDTree(uv[idx_v])
        X = strahlpunkte(cam, None, tree, uv[idx_v], None, u, v, a.schlauch, a.schicht, a.min_wolke)
        ok = np.isfinite(X[:, 0]); X = X[ok]
        lo, hi = box[0] - a.nachbar, box[1] + a.nachbar; inb = np.all((X >= lo) & (X <= hi), 1)
        stat[nr] = dict(gelb_px=int(len(cam["u"])), benutzt=int(len(u)), mit_wolke=int(ok.sum()), anteil_ohne_wolke=round(1 - float(ok.mean()) if len(ok) else 1.0, 3), in_box=int(inb.sum()), fotokantenpixel=cam["fk"])
        print(f"  {nr}: gelb {len(cam['u'])} (benutzt {len(u)}), mit Wolke {ok.sum()} ({100 * ok.mean():.0f} %), in Box+{a.nachbar:g} m {inb.sum()}", flush=True)
        pts.append(X[inb]); fid += [nr] * int(inb.sum())
    X = np.vstack(pts) if pts else np.zeros((0, 3)); fid = np.array(fid)
    if fotos: np.savez_compressed(cache, X=X, fid=fid, stat=json.dumps(stat), box=box)
    n_roh = len(X)
    if len(X):                                                                                                             # Voxelstuetzung: nur Voxel (vox m), in denen >= min_fotos verschiedene Fotos Punkte haben (Einzelfoto-Rauschen, Verdecker, Texturkanten weg)
        key = np.floor(X / a.vox).astype(np.int64); _, inv = np.unique(key, axis=0, return_inverse=True); inv = inv.ravel()
        fi_ = np.unique(fid, return_inverse=True)[1]; vf = np.unique(np.c_[inv, fi_], axis=0); nf_vox = np.bincount(vf[:, 0], minlength=inv.max() + 1)
        keep = nf_vox[inv] >= a.min_fotos; X, fid = X[keep], fid[keep]
    regionen = []; verworfen = dict(wenig_fotos=0, voxel_ohne_stuetzung=int(n_roh - len(X)))
    if len(X) >= a.min_pts:
        lab = dbscan_rekursiv(X, a.eps, a.min_pts, a.gross)
        for l in sorted(set(lab) - {-1}):
            mm = lab == l; fs, cnt = np.unique(fid[mm], return_counts=True); stuetz = [str(f_) for f_, c in zip(fs, cnt) if c >= a.min_punkte_foto]
            if len(stuetz) < a.min_fotos: verworfen["wenig_fotos"] += 1; continue
            Y = X[mm]; c = np.median(Y, 0); lo_, hi_ = np.percentile(Y, 2, 0), np.percentile(Y, 98, 0)
            nn = None if a.fassade_n is None else float(np.median(Y[:, :2] @ np.asarray(a.fassade_n, float)))
            regionen.append(dict(n_median=None if nn is None else round(nn, 2), mittelpunkt=[round(float(x), 2) for x in c], box=[round(float(x), 2) for x in np.r_[lo_, hi_]], punkte=int(mm.sum()), fotos=len(stuetz), fotos_liste=stuetz, rang=int(mm.sum()) * len(stuetz)))
    regionen.sort(key=lambda r: -r["rang"])
    for i, r in enumerate(regionen, 1): r["nr"] = i
    erg = dict(objekt=a.objekt, stl=a.stl, wolke=a.wolke, tol_m=a.tol, schlauch_m=a.schlauch, eps_m=a.eps, min_fotos=a.min_fotos, modellbox=[[round(float(x), 2) for x in b] for b in box], nachbar_m=a.nachbar,
               punkte_gesamt=int(len(X)), verworfen=verworfen, je_foto=stat, regionen=regionen,
               hinweis="Fotokanten ohne Modellkante, auf die vordere Wolkenschicht projiziert. Wolke blind am Dach/steilen Flaechen: Anteil ohne Wolke je Foto in je_foto. ANNAHME: Wolkenrahmen = Kamerarahmen (rahmen_verschiebung der K-Dateien).")
    jp = a.json or os.path.join(od, "fehlstellen.json"); json.dump(erg, open(jp, "w"), indent=1, ensure_ascii=False)
    print(f"{len(X)} 3D-Punkte, {len(regionen)} Regionen (verworfen wegen < {a.min_fotos} Fotos: {verworfen['wenig_fotos']}) -> {jp}")
    for r in regionen[:a.top]: print(f"  {r['nr']:2d}. rang {r['rang']:7d}  pkt {r['punkte']:5d}  fotos {r['fotos']:2d}  mitte {r['mittelpunkt']}  box {r['box']}")
    if a.png: zeichnen(a.png, wolke, X, regionen, box, a.top)
    return erg

def zeichnen(pfad, wolke, X, regionen, box, top):
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    fig, ax = plt.subplots(1, 3, figsize=(21, 7)); lo, hi = box[0] - 4, box[1] + 4
    w = wolke[np.all((wolke >= lo) & (wolke <= hi), 1)]; w = w[:: max(1, len(w) // 60000)]
    ach = [("Front x-z", 0, 2), ("Seite y-z", 1, 2), ("Oben x-y", 0, 1)]; cm = plt.get_cmap("tab20")
    for a_, (ti, i, j) in zip(ax, ach):
        a_.scatter(w[:, i], w[:, j], s=0.3, c="0.8"); a_.add_patch(plt.Rectangle((box[0][i], box[0][j]), box[1][i] - box[0][i], box[1][j] - box[0][j], fill=False, ec="k", lw=1))
        for k, r in enumerate(regionen[:top]):
            b = r["box"]; col = cm(k % 20); a_.add_patch(plt.Rectangle((b[i], b[j]), b[3 + i] - b[i], b[3 + j] - b[j], fill=False, ec=col, lw=2))
            a_.text(b[i], b[3 + j], str(r["nr"]), color=col, fontsize=11, weight="bold")
        a_.set_title(ti); a_.set_aspect("equal"); a_.set_xlim(lo[i], hi[i]); a_.set_ylim(lo[j], hi[j])
    fig.tight_layout(); fig.savefig(pfad, dpi=80); plt.close(fig)

if __name__ == "__main__":
    main()
