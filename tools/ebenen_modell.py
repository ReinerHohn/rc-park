#!/usr/bin/env python3
"""ebenen_modell.py - Scharfes Netz aus gemessenen Ebenen + Carving-Belegung (SPEC S8 Baustein 2+4+5). Keine Vorlagen, kein STL/Generator.

1. Ebenen: normalengefuehrtes RANSAC auf der Wolke (nur Punkte nahe der Carving-Belegung), Verfeinerung per SVD, Doppelte zusammengefasst.
2. Ebenenanordnung: jede Voxelzelle erhaelt den Vorzeichencode zu allen Ebenen; gleicher Code = gleiche konvexe Zelle der Anordnung.
3. Belegung je Zelle = Anteil Carving-Material (material.npz): >= solid -> fest, <= leer -> leer, dazwischen = Restfeld (Zelle UND Carving-Netz, Herkunft vermerkt).
4. Feste Zellen werden exakt aus ihren Halbraeumen gebaut (manifold3d), vereinigt -> scharfe Kanten auf den gemessenen Ebenen, wasserdicht.
5. Optional: 3D-Kanten (kanten_3d.json): Anteil der Linien, die auf einer Modellkante liegen (Pruefzahl; Kanten als Zwangslinien: zusaetzliche Ebenen aus Linienpaaren nicht umgesetzt).
  venv-seg/bin/python -I tools/ebenen_modell.py --dicht D --ausrichtung A --material material.npz --aus DIR [--kanten kanten_3d.json] [--ohne-bilder ..]
"""
import os, sys, json, time, argparse
import numpy as np, trimesh
from scipy import ndimage as ndi
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)


def abdeckung_m2(P, n, raster=0.25, min_pkt=3):
    """Von den Inlier-Punkten belegte Flaeche der Ebene (Raster 0,25 m, >= 3 Punkte je Zelle): Zufallsebenen aus verstreuten Punkten haben kaum Flaeche."""
    a = np.cross(n, [1.0, 0, 0] if abs(n[0]) < 0.9 else [0, 1.0, 0]); a /= np.linalg.norm(a); b = np.cross(n, a); ij = np.floor(np.c_[P @ a, P @ b] / raster).astype(np.int64)
    u, c = np.unique(ij[:, 0] * 1000003 + ij[:, 1], return_counts=True); return float((c >= min_pkt).sum()) * raster * raster


def ebenen_ransac(X, N, n_max=60, min_pts=2500, min_m2=0.0, tol=0.06, wink_deg=12.0, iters=400, seed=1, log=print):
    rng = np.random.default_rng(seed); rest = np.ones(len(X), bool); cw = np.cos(np.radians(wink_deg)); planes = []
    Xt = None
    while len(planes) < n_max:
        idx = np.where(rest)[0]
        if len(idx) < min_pts: break
        sub = idx if len(idx) <= 150000 else rng.choice(idx, 150000, replace=False); Xs, Ns = X[sub], N[sub]
        cand = rng.choice(len(Xs), iters, replace=False if len(Xs) >= iters else True); best = (0, None)
        for c in range(0, iters, 100):
            ci = cand[c:c + 100]; n = Ns[ci]; d = -(n * Xs[ci]).sum(1)
            dist = np.abs(Xs @ n.T + d[None]); ok = (dist < tol) & ((Ns @ n.T) > cw); cnt = ok.sum(0); b = int(cnt.argmax())
            if cnt[b] > best[0]: best = (int(cnt[b]), (n[b], d[b]))
        if best[1] is None or best[0] * len(idx) / len(sub) < min_pts: break
        n, d = best[1]
        for _ in range(3):                                                       # Verfeinern auf allen Restpunkten
            m = rest & (np.abs(X @ n + d) < tol) & ((N @ n) > cw); P = X[m]
            if len(P) < 10: break
            c0 = P.mean(0); u = np.linalg.svd(P - c0, full_matrices=False)[2][-1]; u = u * np.sign(u @ n); n = u; d = -n @ c0
        m = rest & (np.abs(X @ n + d) < tol) & ((N @ n) > cw)
        if m.sum() < min_pts or (min_m2 and abdeckung_m2(X[m], n) < min_m2): rest[np.where(m)[0][:60]] = False; continue
        planes.append((n.copy(), float(d), int(m.sum()))); rest &= ~m
    return planes


def ebenen_zusammen(planes, ang_deg=3.0, dist=0.10):
    out = []
    for n, d, c in sorted(planes, key=lambda p: -p[2]):
        for k, (n2, d2, c2) in enumerate(out):
            if n @ n2 > np.cos(np.radians(ang_deg)) and abs(d - d2) < dist: break
            if n @ n2 < -np.cos(np.radians(ang_deg)) and abs(d + d2) < dist: break
        else: out.append((n, d, c))
    return out


def zellen(material, lo, vox, planes, bbox_m=0.3, min_vox=12, solid=0.75, leer=0.25, log=print):
    """Vorzeichencode je Voxel -> Zellen. Rueckgabe: Zellliste (code, n_vox, anteil, bbox_min, bbox_max)."""
    ij = np.argwhere(material); lo_i = np.maximum(ij.min(0) - int(bbox_m / vox), 0); hi_i = np.minimum(ij.max(0) + int(bbox_m / vox) + 1, material.shape)
    sub = material[lo_i[0]:hi_i[0], lo_i[1]:hi_i[1], lo_i[2]:hi_i[2]]; o = np.asarray(lo) + lo_i * vox
    sh = sub.shape; code = np.zeros(sh, np.int64)
    gx = o[0] + (np.arange(sh[0]) + 0.5) * vox; gy = o[1] + (np.arange(sh[1]) + 0.5) * vox; gz = o[2] + (np.arange(sh[2]) + 0.5) * vox
    for k, (n, d, c) in enumerate(planes):
        dist = n[0] * gx[:, None, None] + n[1] * gy[None, :, None] + n[2] * gz[None, None, :] + d; code |= (dist > 0).astype(np.int64) << k
    u, inv, cnt = np.unique(code.ravel(), return_inverse=True, return_counts=True); frac = np.bincount(inv, weights=sub.ravel().astype(float), minlength=len(u)) / cnt
    log(f"Zellen im Quader: {len(u)} (Voxel {sub.size}), >= {min_vox} Voxel: {int((cnt>=min_vox).sum())}")
    return u, cnt, frac, o, sh, code, inv.reshape(sh), lo_i, hi_i


def belegung_strahlen(inv, n, leer, surf, alpha=0.1, lam=1.0, log=print):
    """Zellbelegung aus den Strahlen (carving_cache: leer = >= 2 Strahlsegmente Kamera->Punkt durchlaufen die Voxelzelle, surf = Punkte auf/hinter der Flaeche) per Graph-Cut.
    fest-Kosten einer Zelle = Zahl leerer Voxel; leer-Kosten = Flaechenvoxel + alpha * unbeobachtete Voxel (Material unter der Haut); Paarkosten = lam * gemeinsame Flaeche (Voxelseiten).
    Zellen am Quaderrand sind leer. Keine Hohlraumfuellung, keine Huelle."""
    from scipy.sparse import csr_matrix, coo_matrix
    from scipy.sparse.csgraph import maximum_flow
    f = inv.ravel(); L = np.bincount(f, weights=leer.ravel(), minlength=n); S = np.bincount(f, weights=surf.ravel(), minlength=n); V = np.bincount(f, minlength=n); U = V - L - S
    rand = np.zeros(n, bool)
    for ax in range(3):
        for sl in ((0, -1) if ax < 2 else (-1,)): rand[np.unique(np.take(inv, sl, axis=ax))] = True      # Unterseite (Boden) ist kein Rand
    c_fest = 100 * L + rand * 10 ** 9; c_leer = 100 * S + np.round(100 * alpha * U)
    A, B, W = [], [], []
    for ax in range(3):
        a = np.take(inv, range(inv.shape[ax] - 1), axis=ax).ravel(); b = np.take(inv, range(1, inv.shape[ax]), axis=ax).ravel(); m = a != b; A.append(a[m]); B.append(b[m])
    A = np.concatenate(A); B = np.concatenate(B); lo_, hi_ = np.minimum(A, B), np.maximum(A, B); key = lo_.astype(np.int64) * n + hi_; uk, cn = np.unique(key, return_counts=True)
    pa, pb = uk // n, uk % n; w = np.round(100 * lam * cn).astype(np.int64)
    s, t = n, n + 1; rows = np.r_[pa, pb, np.full(n, s), np.arange(n)]; cols = np.r_[pb, pa, np.arange(n), np.full(n, t)]; cap = np.r_[w, w, np.minimum(c_leer, 2 ** 30), np.minimum(c_fest, 2 ** 30)].astype(np.int32)
    G = csr_matrix((cap, (rows, cols)), shape=(n + 2, n + 2)); fl = maximum_flow(G, s, t).flow; res = (G - fl).tocsr(); res.data[res.data < 0] = 0; res.eliminate_zeros()
    from scipy.sparse.csgraph import breadth_first_order
    reach = breadth_first_order(res, s, directed=True, return_predecessors=False); fest = np.zeros(n, bool); fest[reach[reach < n]] = True
    log(f"Graph-Cut: {n} Zellen, fest {int(fest.sum())}, Schnittwert {int(fl[s].sum())}"); return fest.astype(float)


def zelle_bauen(code, planes, lo_c, hi_c, manifold, eps=2e-4):
    """eps: Zellen werden 0,2 mm aufgeblaeht, damit Nachbarn UEBERLAPPEN (sonst bleiben flaechig beruehrende Zellen getrennte Schalen). Konvexe Zelle: Quader der Voxelgrenzen (+Rand) geschnitten mit allen Halbraeumen, die den Quader wirklich teilen."""
    M = manifold.Manifold.cube(list(hi_c - lo_c), False).translate(list(lo_c)); corn = np.array([[x, y, z] for x in (lo_c[0], hi_c[0]) for y in (lo_c[1], hi_c[1]) for z in (lo_c[2], hi_c[2])])
    for k, (n, d, c) in enumerate(planes):
        s = 1 if (code >> k) & 1 else -1; sd = s * (corn @ n + d)
        if (sd > 1e-9).all(): continue                                  # Quader liegt ganz auf der Zellseite
        M = M.trim_by_plane((s * n).tolist(), float(-s * d) - eps)
        if M.is_empty(): break
    return M


def lauf(dicht, ausr, mat_pfad, aus, ohne_bilder=(), min_pts=2500, solid=0.75, leer=0.25, min_vox=1, tol=0.06, kanten=None, kleinst_m3=1.0, min_flaeche_m2=None, belegung="voxel", alpha=0.1, lam=1.0, log=print):
    import manifold3d as mf
    import wolke_carving as WC
    t0 = time.time(); os.makedirs(aus, exist_ok=True)
    z = np.load(mat_pfad); mat = z["material"]; lo = z["lo"]; vox = float(z["vox"])
    X, N, pi, ii, Cc = WC.wolke_laden(dicht, ausr, 3, ohne_bilder); log(f"Wolke {len(X)} Punkte ({time.time()-t0:.0f}s)")
    dist_m = ndi.distance_transform_edt(~mat) * vox; ix = np.clip(((X - lo) / vox).astype(int), 0, np.array(mat.shape) - 1); nah = dist_m[ix[:, 0], ix[:, 1], ix[:, 2]] < 0.4
    log(f"Punkte nahe Belegung (<0,4 m): {int(nah.sum())}")
    if min_flaeche_m2:                                                       # Mindestflaeche statt fester Punktzahl: Dichte = Punkte nahe Belegung / Oberflaeche der Belegung (Treppenraster -> Faktor 1,3 zu gross)
        fl = int((mat[1:] != mat[:-1]).sum() + (mat[:, 1:] != mat[:, :-1]).sum() + (mat[:, :, 1:] != mat[:, :, :-1]).sum()) * vox * vox / 1.3
        min_pts = max(30, int(0.5 * min_flaeche_m2 * nah.sum() / fl)); log(f"Oberflaeche ~{fl:.0f} m2, Dichte {nah.sum()/fl:.0f} Pkt/m2 -> min_pts {min_pts} (Mindestflaeche {min_flaeche_m2} m2)")
    pl = ebenen_ransac(X[nah], N[nah], min_pts=min_pts, min_m2=(min_flaeche_m2 or 0.0), tol=tol, log=log); pl = ebenen_zusammen(pl); log(f"Ebenen: {len(pl)} ({time.time()-t0:.0f}s) Stuetzpunkte {[p[2] for p in pl][:12]}")
    if len(pl) > 62: pl = pl[:62]
    u, cnt, frac, o, sh, code, inv, lo_i, hi_i = zellen(mat, lo, vox, pl, min_vox=min_vox, solid=solid, leer=leer, log=log)
    if belegung == "strahlen":
        zc = np.load(os.path.join(os.path.dirname(mat_pfad), "carving_cache.npz")); sl = tuple(slice(a, b) for a, b in zip(lo_i, hi_i))
        frac = belegung_strahlen(inv, len(u), zc["leer"][sl], zc["surf"][sl], alpha=alpha, lam=lam, log=log); solid = leer = 0.5
    # Zellen
    order = np.argsort(-cnt); fest, rest, tiny_fest = [], [], 0
    flat = code.ravel(); sort_i = np.argsort(flat, kind="stable"); starts = np.searchsorted(flat[sort_i], u)
    ends = np.r_[starts[1:], len(flat)]
    teile = []; herkunft = dict(ebene_fest=0, restfeld=0, verworfen_klein=0)
    mc = None
    for k in order:
        if cnt[k] < min_vox: herkunft["verworfen_klein"] += 1; continue
        if frac[k] <= leer: continue
        vi = sort_i[starts[k]:ends[k]]; ijk = np.array(np.unravel_index(vi, sh)).T
        lo_c = o + ijk.min(0) * vox - 0.5 * vox; hi_c = o + (ijk.max(0) + 1) * vox + 0.5 * vox
        M = zelle_bauen(int(u[k]), pl, lo_c, hi_c, mf)
        if M.is_empty(): continue
        if frac[k] >= solid: teile.append(M); herkunft["ebene_fest"] += 1
        else:
            if mc is None:
                m_all = WC.netz(mat, lo, vox, 0.75); mc = mf.Manifold(mf.Mesh(vert_properties=np.asarray(m_all.vertices, np.float32), tri_verts=np.asarray(m_all.faces, np.uint32)))
            R = M ^ mc
            if not R.is_empty(): teile.append(R); herkunft["restfeld"] += 1
    log(f"Teile {len(teile)} {herkunft} ({time.time()-t0:.0f}s)")
    U = mf.Manifold.batch_boolean(teile, mf.OpType.Add); me = U.to_mesh(); V = np.asarray(me.vert_properties)[:, :3]; F = np.asarray(me.tri_verts)
    log(f"Manifold: status {U.status()}, Volumen {U.volume():.1f}, Flaeche {U.surface_area():.1f}, Genus {U.genus()}")
    m = trimesh.Trimesh(V, F, process=False); teile_k = m.split(only_watertight=False); vols = np.array([abs(c.volume) for c in teile_k]); gross = [c for c, v in zip(teile_k, vols) if v >= kleinst_m3]
    log(f"Koerper {len(teile_k)}, davon >= {kleinst_m3} m3: {len(gross)}"); m = trimesh.util.concatenate(gross) if gross else m
    erg = dict(ebenen=[dict(n=np.round(p[0], 5).tolist(), d=round(p[1], 4), punkte=p[2]) for p in pl], zellen=herkunft, wasserdicht=bool(m.is_watertight), koerper=len(m.split(only_watertight=False)), volumen_m3=round(float(m.volume), 1),
               dreiecke=len(m.faces), sekunden=round(time.time() - t0, 1), params=dict(min_pts=min_pts, solid=solid, leer=leer, min_vox=min_vox, tol=tol),
               keine_stl_gelesen="Eingaben: Wolke, Ausrichtung, material.npz (Carving), kanten_3d.json; kein Generator-STL, kein LoD2 ausser dem schon in material.npz")
    m.export(os.path.join(aus, "ebenen_modell_m.stl")); m.export(os.path.join(aus, "ebenen_modell_m.ply")); json.dump(erg, open(os.path.join(aus, "ebenen_modell.json"), "w"), indent=1)
    log(json.dumps({k: v for k, v in erg.items() if k != "ebenen"})); return m, erg


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter); ap.add_argument("--dicht", required=True); ap.add_argument("--ausrichtung", required=True)
    ap.add_argument("--material", required=True); ap.add_argument("--aus", required=True); ap.add_argument("--ohne-bilder", nargs="*", default=[]); ap.add_argument("--min-pts", type=int, default=2500)
    ap.add_argument("--solid", type=float, default=0.75); ap.add_argument("--leer", type=float, default=0.25); ap.add_argument("--min-vox", type=int, default=1); ap.add_argument("--kanten"); ap.add_argument("--belegung", default="voxel", choices=["voxel", "strahlen"]); ap.add_argument("--alpha", type=float, default=0.1); ap.add_argument("--lam", type=float, default=1.0); ap.add_argument("--min-flaeche", type=float, help="Mindestflaeche je Ebene in m2 (ersetzt --min-pts)")
    a = ap.parse_args(); lauf(a.dicht, a.ausrichtung, a.material, a.aus, tuple(a.ohne_bilder), a.min_pts, a.solid, a.leer, a.min_vox, kanten=a.kanten, min_flaeche_m2=a.min_flaeche, belegung=a.belegung, alpha=a.alpha, lam=a.lam)


if __name__ == "__main__": main()
