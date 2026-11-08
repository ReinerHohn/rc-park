#!/usr/bin/env python3
"""test_ebenen_modell.py - synthetischer Beweis fuer kanten_3d.py + ebenen_modell.py (SPEC S8).
Szene (Modellrahmen, m): Kasten 20 x 10 x 8, Halle dahinter, 4 Rundbogen-Arkaden in der Front y=0, Satteldach (First 11 m), beide Giebelwaende als TREPPENGIEBEL (5 Stufen) -
der Code kennt keine Giebel/Bogen/Arkaden. Eingaben: gerenderte Ansichten (74 Kameras) + Wolke mit Rauschen 3 cm + Sichtlisten. Die Sollform wird NUR zur Bewertung gelesen.
  Ablauf: synth -> kanten_3d -> wolke_carving (ohne LoD2) -> ebenen_modell -> Messung (Kanten, Stufen, IoU).
  /media/oem/scan/venv-seg/bin/python -W ignore -I tools/test_ebenen_modell.py --aus DIR [--nur-bewerten]
"""
import os, sys, json, argparse, time
import numpy as np, trimesh, cv2
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)


def soll():
    import manifold3d as M
    box = lambda a, b: M.Manifold.cube([b[0] - a[0], b[1] - a[1], b[2] - a[2]]).translate(a)
    k = box([0, 0, 0], [20, 10, 8])
    # Satteldach (Prisma entlang x), Traufe 8, First 11 bei y=5
    dach = box([0.5, 0, 8], [19.5, 10, 11]).trim_by_plane([0, 0.6, -1], -8.0).trim_by_plane([0, -0.6, -1], -14.0); k = k + dach
    # Treppengiebel an x=0 und x=20: Stufen 5 x (1 m breit, 0,6 m hoch), 0,5 m dick
    for x0 in (0.0, 19.5):
        for s in range(5): k = k + box([x0, s * 1.0, 8], [x0 + 0.5, 10 - s * 1.0, 8 + 0.6 * (s + 1)])
    k = k - box([1, 0.8, 0], [19, 6, 4])
    for cx in [2.5, 7.0, 13.0, 17.5]:       # Rundbogen: Pfeiler 3 m breit, Scheitel 3,5 m + Radius 1,5
        k = k - box([cx - 1.5, -0.1, 0], [cx + 1.5, 0.9, 2.0]); k = k - M.Manifold.cylinder(1.0, 1.5, 1.5, 64).rotate([90, 0, 0]).translate([cx, 0.9, 2.0])
    mm = k.to_mesh(); return trimesh.Trimesh(np.asarray(mm.vert_properties)[:, :3], np.asarray(mm.tri_verts), process=True)


def kamera_pose(c, ziel=(10, 5, 4)):
    z = np.array(ziel, float) - c; z /= np.linalg.norm(z); x = np.cross(z, [0, 0, 1.0]); x /= np.linalg.norm(x); y = np.cross(z, x); R = np.array([x, y, z]); return R, -R @ c


def synth_schreiben(aus, sk, n_pkt=90000, rausch=0.03, seed=3, W=640, H=436, f=600.0):
    rng = np.random.default_rng(seed); os.makedirs(os.path.join(aus, "images"), exist_ok=True)
    pts, fidx = trimesh.sample.sample_surface(sk, n_pkt, seed=seed); nrm = sk.face_normals[fidx]
    gx, gy = rng.uniform(-30, 50, 20000), rng.uniform(-35, 40, 20000); inb = ~((gx > -0.3) & (gx < 20.3) & (gy > -0.3) & (gy < 10.3))
    pts = np.r_[pts, np.c_[gx[inb], gy[inb], np.zeros(inb.sum())]]; nrm = np.r_[nrm, np.tile([0, 0, 1.0], (inb.sum(), 1))]
    cams = []
    for i in range(60): a = 2 * np.pi * i / 60; r = 27 + 4 * np.sin(3 * a); cams.append([10 + 1.2 * r * np.cos(a), 5 + r * 1.0 * np.sin(a) - 0 * a, rng.uniform(1.6, 7.0)])
    for i in range(14): a = 2 * np.pi * i / 14; cams.append([10 + 20 * np.cos(a), 5 + 18 * np.sin(a), rng.uniform(16, 24)])
    cams = np.array(cams); ray = sk.ray; vi, ci = [], []; K = {}
    u, v = np.meshgrid(np.arange(W) + .5, np.arange(H) + .5); dcam = np.stack([(u - W / 2) / f, (v - H / 2) / f, np.ones_like(u)], -1).reshape(-1, 3); licht = np.array([0.4, -0.7, 0.6]); licht /= np.linalg.norm(licht)
    for k, c in enumerate(cams):
        R, t = kamera_pose(c); d = pts - c; L = np.linalg.norm(d, axis=1); d /= L[:, None]; fr = (nrm * (c - pts)).sum(1) > 0; idx = np.where(fr)[0]
        loc, ir, _ = ray.intersects_location(np.tile(c, (len(idx), 1)), d[idx], multiple_hits=False); ok = np.ones(len(idx), bool); ok[ir] = np.linalg.norm(loc - pts[idx][ir], axis=1) < 0.05
        sel = idx[ok]; vi.append(sel); ci.append(np.full(len(sel), k))
        dm = dcam @ R; dm /= np.linalg.norm(dm, axis=1, keepdims=True); loc, ir, fi = ray.intersects_location(np.tile(c, (len(dm), 1)), dm, multiple_hits=False)
        g = np.full(W * H, 0.0); g[:] = 210.0; zz = np.where(dm[:, 2] < -1e-3, -c[2] / dm[:, 2], np.inf); gr = np.isfinite(zz)
        g[gr] = 130.0                   # Boden mit Schachbrett (Textur fuer Pose irrelevant)
        n = sk.face_normals[fi]; g[ir] = 70 + 150 * np.clip(n @ licht * 0.5 + 0.5, 0, 1)
        im = np.clip(g.reshape(H, W) + rng.normal(0, 2, (H, W)), 0, 255).astype(np.uint8); cv2.imwrite(os.path.join(aus, "images", "%03d.jpg" % k), im)
        K["%03d" % k] = dict(bild="%03d.jpg" % k, W=W, H=H, fx=f, fy=f, cx=W / 2, cy=H / 2, R=R.tolist(), t=t.tolist())
    vi = np.concatenate(vi); ci = np.concatenate(ci); o = np.argsort(vi, kind="stable"); vi, ci = vi[o], ci[o]; cnt = np.bincount(vi, minlength=len(pts)); X = pts + rng.normal(0, rausch, pts.shape)
    with open(os.path.join(aus, "fused.ply"), "wb") as fh:
        fh.write(("ply\nformat binary_little_endian 1.0\nelement vertex %d\nproperty float x\nproperty float y\nproperty float z\nproperty float nx\nproperty float ny\nproperty float nz\nproperty uchar red\nproperty uchar green\nproperty uchar blue\nend_header\n" % len(X)).encode())
        a = np.zeros(len(X), dtype=[("x", "<f4"), ("y", "<f4"), ("z", "<f4"), ("nx", "<f4"), ("ny", "<f4"), ("nz", "<f4"), ("r", "u1"), ("g", "u1"), ("b", "u1")]); a["x"], a["y"], a["z"] = X.T; a["nx"], a["ny"], a["nz"] = nrm.T; fh.write(a.tobytes())
    out = [np.array([len(X) & 0xffffffff, len(X) >> 32], "<u4")]; starts = np.r_[0, np.cumsum(cnt)]
    for k in range(len(X)): out.append(np.r_[cnt[k], ci[starts[k]:starts[k + 1]]].astype("<u4"))
    np.concatenate(out).astype("<u4").tofile(os.path.join(aus, "fused.ply.vis")); json.dump(K, open(os.path.join(aus, "kameras_unverzerrt.json"), "w"))
    import freiraum_pruefen as FP0; FP0.images_bin_schreiben(aus, list(K))   # vis-Index k = k-ter Schluessel (Register CW)
    json.dump(dict(transformation=dict(s=1.0, rvec=[0, 0, 0], t=[0, 0, 0])), open(os.path.join(aus, "ausrichtung.json"), "w"))


def bewerten(sk, m, linien, aus):
    from scipy.spatial import cKDTree
    res = {}
    # Soll-Kanten: Flaechenkanten mit Knickwinkel > 35 Grad, Laenge >= 0,4 m (Rundbogen: viele kurze Facetten -> Mindestlaenge/Winkel filtern sie weitgehend)
    adj = sk.face_adjacency; ang = sk.face_adjacency_angles; e = sk.face_adjacency_edges; L = np.linalg.norm(sk.vertices[e[:, 0]] - sk.vertices[e[:, 1]], axis=1); sel = (ang > np.radians(35)) & (L > 0.4)
    S = []
    for a, b in e[sel]:
        for t in np.linspace(0, 1, max(2, int(np.linalg.norm(sk.vertices[a] - sk.vertices[b]) / 0.05))): S.append(sk.vertices[a] * (1 - t) + sk.vertices[b] * t)
    S = np.array(S); q = trimesh.proximity.ProximityQuery(m); d = np.abs(q.signed_distance(S)); res["soll_kanten_punkte"] = int(len(S)); res["soll_kanten_abw_median_cm"] = round(float(np.median(d)) * 100, 1)
    res["soll_kanten_abw_p90_cm"] = round(float(np.quantile(d, 0.9)) * 100, 1); res["soll_kanten_anteil_unter_5cm"] = round(float((d < 0.05).mean()), 3)
    # Modell-Flaechen (Stichprobe) gegen Soll
    P = m.sample(40000); d2 = np.abs(trimesh.proximity.ProximityQuery(sk).signed_distance(P)); res["modell_flaeche_abw_median_cm"] = round(float(np.median(d2)) * 100, 1); res["modell_flaeche_abw_p95_cm"] = round(float(np.quantile(d2, 0.95)) * 100, 1)
    # Treppengiebel: Hoehe der Oberkante entlang y an der Giebelwand x=0,25 (Strahlen von oben), Plateaus zaehlen
    ys = np.arange(0.05, 10, 0.05); org = np.c_[np.full(len(ys), 0.25), ys, np.full(len(ys), 20.0)]
    def hoehen(mesh):
        loc, ir, _ = mesh.ray.intersects_location(org, np.tile([0, 0, -1.0], (len(ys), 1)), multiple_hits=False); h = np.full(len(ys), np.nan); h[ir] = loc[:, 2]; return h
    h = hoehen(m); hs = hoehen(sk); fin = h[np.isfinite(h)]; zs = np.round(fin / 0.15) * 0.15; u, c = np.unique(zs, return_counts=True)
    plateaus = [round(float(x), 2) for x, n in zip(u, c) if n >= 8 and x > 8.2]; res["giebel_plateaus_modell_m"] = plateaus; res["giebel_stufen_modell"] = len(plateaus); res["giebel_hoehe_abw_median_cm"] = round(float(np.nanmedian(np.abs(h - hs))) * 100, 1)
    # Voxel-IoU
    pts = np.random.default_rng(1).uniform([-1, -1, -0.5], [21, 11, 12], (400000, 3)); a = sk.contains(pts); b = m.contains(pts); res["iou"] = round(float((a & b).sum() / max((a | b).sum(), 1)), 3)
    res["wasserdicht"] = bool(m.is_watertight); res["koerper"] = len(m.split(only_watertight=False)); res["arkaden_oeffnungen_front"] = arkaden(m)
    # 3D-Linien gegen Soll-Kanten
    if linien:
        Lp = [(np.array(l["p0"]), np.array(l["p1"])) for l in linien["linien"]]; tr = cKDTree(S); dd = []
        for p0, p1 in Lp:
            T = np.linspace(0, 1, 12)[:, None]; Q = p0 * (1 - T) + p1 * T; dd.append(np.median(tr.query(Q)[0]))
        dd = np.array(dd); res["linien"] = len(Lp); res["linien_median_abstand_zu_sollkanten_cm"] = round(float(np.median(dd)) * 100, 1); res["linien_anteil_auf_sollkante_unter_5cm"] = round(float((dd < 0.05).mean()), 3)
    return res


def arkaden(m):
    ys = 0.4; xs = np.arange(0.05, 20, 0.05); org = np.c_[xs, np.full(len(xs), -5.0), np.full(len(xs), 1.0)]; loc, ir, _ = m.ray.intersects_location(org, np.tile([0, 1.0, 0], (len(xs), 1)), multiple_hits=False)
    y = np.full(len(xs), np.nan); y[ir] = loc[:, 1]; off = ~(y < 0.45) | ~np.isfinite(y)             # Strahl in Hoehe 1 m: durch die Front hindurch (Oeffnung) = Treffer erst hinter 0,45 m
    return int(np.sum(np.diff(np.r_[0, off.astype(int)]) == 1))


MINFL = float(os.environ.get('MINFL', 1.0))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--aus", required=True); ap.add_argument("--nur-bewerten", action="store_true"); ap.add_argument("--negativ", action="store_true"); a = ap.parse_args(); aus = a.aus; t0 = time.time()
    import kanten_3d as K3, wolke_carving as WC, ebenen_modell as EM
    sk = soll(); d = os.path.join(aus, "wolke"); sub = os.path.join(aus, "ebenen")
    m_mem = None
    if not a.nur_bewerten:
        synth_schreiben(d, sk); print(f"synth {time.time()-t0:.0f}s", flush=True)
        K3.lauf(d, os.path.join(d, "ausrichtung.json"), os.path.join(aus, "kanten"), min_fotos=3)
        WC.lauf(d, os.path.join(d, "ausrichtung.json"), [-8, -12, -1], [28, 18, 14], os.path.join(aus, "carv"), 87.0, (), 0.10, n_beob=900000)
        m_mem, _ = EM.lauf(d, os.path.join(d, "ausrichtung.json"), os.path.join(aus, "carv", "material.npz"), sub, min_flaeche_m2=MINFL, solid=0.5, leer=0.5, tol=0.06)
    m = trimesh.load(os.path.join(sub, "ebenen_modell_m.ply")); linien = json.load(open(os.path.join(aus, "kanten", "kanten_3d.json")))
    res = bewerten(sk, m_mem if m_mem is not None else m, linien, aus)
    json.dump(res, open(os.path.join(aus, "test_ergebnis.json"), "w"), indent=1); print(json.dumps(res, indent=1))
    ok = res["soll_kanten_abw_p90_cm"] < 5 and res["giebel_stufen_modell"] >= 4 and res["wasserdicht"] and res["koerper"] == 1
    print("BESTANDEN" if ok else "NICHT BESTANDEN", f"({time.time()-t0:.0f}s)"); sys.exit(0 if ok else 1)


if __name__ == "__main__": main()
