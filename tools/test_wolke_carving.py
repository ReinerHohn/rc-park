#!/usr/bin/env python3
"""test_wolke_carving.py - Beweise fuer tools/wolke_carving.py (Koerper NUR aus der Wolke).
  unabhaengig  : synthetische Wolke (Halle hinter 4 Arkaden) -> Koerper; jeder Zugriff auf *.stl/*.obj/*.ply-Modelle ausser der eigenen Ausgabe laesst den Test FEHLSCHLAGEN (open/trimesh.load/np.fromfile abgefangen)
  synth        : Halle bleibt ein zusammenhaengender Leerraum (Anteil leer im Sollvolumen), 1 Koerper, wasserdicht, Arkaden = 4 Oeffnungen in der Fassadenebene
  (Kaufhaus/Martinstor: Aufruf von wolke_carving.py selbst, Ergebnis siehe wolke_carving.json)
Aufruf: /media/oem/scan/venv-seg/bin/python -W ignore tools/test_wolke_carving.py synth --aus DIR
"""
import os, sys, json, builtins, argparse
import numpy as np, trimesh
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)

# Sollform (Modellrahmen, m): Gebaeude 20 x 10 x 8, Fassade y=0, Wand 0.8 m, Halle x1..19 y0.8..6 z0..4, 4 Arkaden 3,0 m breit, 3,5 m hoch
EIGENE = [""]   # eigene Ausgabe (Neuladen zur Wasserdichtepruefung ist erlaubt)
GEB = ([0, 0, 0], [20, 10, 8]); HALLE = ([1, 0.8, 0], [19, 6, 4]); ARK_X = [3.5, 8.5, 13.5, 18.5 - 0.0]; ARK_B = 3.0; ARK_H = 3.5


def sollkoerper():
    import manifold3d as M
    def box(a, b): return M.Manifold.cube([b[0] - a[0], b[1] - a[1], b[2] - a[2]]).translate(a)
    k = box(*GEB) - box(*HALLE)
    for cx in [2.5, 7.0, 13.0, 17.5]: k = k - box([cx - ARK_B / 2, -0.1, 0], [cx + ARK_B / 2, 0.9, ARK_H])
    mm = k.to_mesh(); return trimesh.Trimesh(np.asarray(mm.vert_properties)[:, :3], np.asarray(mm.tri_verts), process=True)


def synth_schreiben(aus, n_pkt=60000, n_kam=40, rausch=0.03, seed=3):
    sk = sollkoerper(); rng = np.random.default_rng(seed); os.makedirs(aus, exist_ok=True)
    P, Nn = trimesh.sample.sample_surface(sk, n_pkt, seed=seed)[:2], None
    pts, fidx = trimesh.sample.sample_surface(sk, n_pkt, seed=seed); nrm = sk.face_normals[fidx]
    gx, gy = rng.uniform(-25, 45, 12000), rng.uniform(-30, 30, 12000); inb = ~((gx > -0.3) & (gx < 20.3) & (gy > -0.3) & (gy < 10.3))
    pts = np.r_[pts, np.c_[gx[inb], gy[inb], np.zeros(inb.sum())]]; nrm = np.r_[nrm, np.tile([0, 0, 1.0], (inb.sum(), 1))]
    cams = [];
    for i in range(n_kam):
        a = np.radians(-70 + 140 * i / (n_kam - 1)); r = rng.uniform(14, 24); cams.append([10 + r * np.sin(a), -r * np.cos(a) * 0.9 - 3, rng.uniform(1.5, 6.5)])
    for i in range(14):   # Luftbilder (Drohne): Dach sichtbar machen, wie bei echten Daten
        a = np.radians(-60 + 120 * i / 13); cams.append([10 + 14 * np.sin(a), -2 - 12 * np.cos(a), rng.uniform(14, 26)])
    n_kam += 14; cams = np.array(cams); ray = trimesh.ray.ray_triangle.RayMeshIntersector(sk); vi, ci = [], []
    for k, c in enumerate(cams):
        d = pts - c; L = np.linalg.norm(d, axis=1); d /= L[:, None]; fr = (nrm * (c - pts)).sum(1) > 0
        idx = np.where(fr)[0]; hit = ray.intersects_location(np.tile(c, (len(idx), 1)), d[idx], multiple_hits=False); loc, ir, _ = hit
        ok = np.ones(len(idx), bool); ok[ir] = np.linalg.norm(loc - pts[idx][ir], axis=1) < 0.05;   # Strahl ohne Treffer = frei (Boden liegt nicht im Netz)
        sel = idx[ok]; vi.append(sel); ci.append(np.full(len(sel), k))
    vi = np.concatenate(vi); ci = np.concatenate(ci); o = np.argsort(vi, kind="stable"); vi, ci = vi[o], ci[o]
    cnt = np.bincount(vi, minlength=len(pts)); X = pts + rng.normal(0, rausch, pts.shape)
    with open(os.path.join(aus, "fused.ply"), "wb") as f:
        f.write(("ply\nformat binary_little_endian 1.0\nelement vertex %d\nproperty float x\nproperty float y\nproperty float z\nproperty float nx\nproperty float ny\nproperty float nz\nproperty uchar red\nproperty uchar green\nproperty uchar blue\nend_header\n" % len(X)).encode())
        a = np.zeros(len(X), dtype=[("x", "<f4"), ("y", "<f4"), ("z", "<f4"), ("nx", "<f4"), ("ny", "<f4"), ("nz", "<f4"), ("r", "u1"), ("g", "u1"), ("b", "u1")])
        a["x"], a["y"], a["z"] = X.T; a["nx"], a["ny"], a["nz"] = nrm.T; f.write(a.tobytes())
    out = [np.array([len(X) & 0xffffffff, len(X) >> 32], "<u4")]; starts = np.r_[0, np.cumsum(cnt)]
    for k in range(len(X)): out.append(np.r_[cnt[k], ci[starts[k]:starts[k + 1]]].astype("<u4"))
    np.concatenate(out).astype("<u4").tofile(os.path.join(aus, "fused.ply.vis"))
    K = {}
    for k, c in enumerate(cams):   # Kamera blickt grob zum Gebaeude; R/t nur fuer das Zentrum noetig (C = -R^T t)
        z = np.array([10, 5, 3]) - c; z /= np.linalg.norm(z); x = np.cross(z, [0, 0, 1.0]); x /= np.linalg.norm(x); y = np.cross(z, x); R = np.array([x, y, z]); K["%03d" % k] = dict(bild="%03d.jpg" % k, W=1600, H=1090, fx=1500, fy=1500, cx=800, cy=545, R=R.tolist(), t=(-R @ c).tolist())
    json.dump(K, open(os.path.join(aus, "kameras_unverzerrt.json"), "w"))
    import freiraum_pruefen as FP0; FP0.images_bin_schreiben(aus, sorted(K))   # vis-Index k = Kamera k = Schluessel "%03d" % k (Register CW)
    json.dump(dict(transformation=dict(s=1.0, rvec=[0, 0, 0], t=[0, 0, 0])), open(os.path.join(aus, "ausrichtung.json"), "w"))
    sk.export(os.path.join(aus, "SOLL_nur_zur_Bewertung.stl")); return sk


def test_lod2(aus):
    """LoD2-Dach liegt 1 m falsch (z=9 statt 8), wo die Wolke Dachpunkte hat -> Wolke gewinnt (widerspruch, Koerper nicht hoeher als 8,4 m); unbeobachtetes Dach (Wolke ohne Dachpunkte) -> LoD2 ergaenzt."""
    import wolke_carving as W
    sk = synth_schreiben(os.path.join(aus, "wolke")); res = {}
    for name, dz, ohne_dach in (("falsch_1m", 1.0, False), ("unbeobachtet", 0.0, True)):
        d = os.path.join(aus, "wolke")
        if ohne_dach:   # Dachpunkte (z > 7,5) entfernen: Fall 'Wolke sieht das Dach nicht'
            import shutil; d2 = os.path.join(aus, "wolke_ohne_dach"); os.makedirs(d2, exist_ok=True)
            for f in ("kameras_unverzerrt.json", "ausrichtung.json"): shutil.copy(os.path.join(d, f), d2)
            shutil.copytree(os.path.join(d, "sparse"), os.path.join(d2, "sparse"), dirs_exist_ok=True)   # vis-Index bleibt gleich
            import freiraum_pruefen as FP; X = FP.ply_lesen(os.path.join(d, "fused.ply")); n = len(X); pi, ii = FP.vis_lesen(os.path.join(d, "fused.ply.vis")); keep = X[:, 2] < 7.5; new = np.cumsum(keep) - 1; ok = keep[pi]
            raw = open(os.path.join(d, "fused.ply"), "rb").read(); hl = raw.index(b"end_header\n") + 11; dt = np.dtype([("x", "<f4"), ("y", "<f4"), ("z", "<f4"), ("nx", "<f4"), ("ny", "<f4"), ("nz", "<f4"), ("r", "u1"), ("g", "u1"), ("b", "u1")]); arr = np.frombuffer(raw[hl:], dtype=dt)[keep]
            hd = raw[:hl].decode().replace("element vertex %d" % n, "element vertex %d" % len(arr)); open(os.path.join(d2, "fused.ply"), "wb").write(hd.encode() + arr.tobytes())
            pi2, ii2 = new[pi[ok]], ii[ok]; o = np.argsort(pi2, kind="stable"); pi2, ii2 = pi2[o], ii2[o]; cnt = np.bincount(pi2, minlength=len(arr)); st = np.r_[0, np.cumsum(cnt)]
            out = [np.array([len(arr) & 0xffffffff, len(arr) >> 32], "<u4")] + [np.r_[cnt[k], ii2[st[k]:st[k + 1]]].astype("<u4") for k in range(len(arr))]; np.concatenate(out).astype("<u4").tofile(os.path.join(d2, "fused.ply.vis")); d = d2
        roof = ("RoofSurface", np.array([[0, 0, 8 + dz], [20, 0, 8 + dz], [20, 10, 8 + dz], [0, 10, 8 + dz]], float))
        erg = W.lauf(d, os.path.join(aus, "wolke", "ausrichtung.json"), [-30, -35, -2], [50, 35, 14], os.path.join(aus, "k_" + name), 87.0, (), 0.10, n_beob=600000, lod2=[roof])
        mat = np.load(os.path.join(aus, "k_" + name, "material.npz")); M = mat["material"]; top = (M[int(round((2 + 30) / 0.1)):int(round((18 + 30) / 0.1)), int(round((2 + 35) / 0.1)):int(round((8 + 35) / 0.1))].any((0, 1)).nonzero()[0].max() + 1) * float(mat["vox"]) + mat["lo"][2]
        res[name] = dict(klasse=erg["lod2_flaechen"][0]["klasse"], dach_oberkante_m=round(float(top), 2), koerper=erg["kennzahlen"]["koerper"], wasserdicht=bool(erg["kennzahlen"]["wasserdicht"]))
    ok = res["falsch_1m"]["klasse"] == "widerspruch" and res["falsch_1m"]["dach_oberkante_m"] < 8.4 and res["unbeobachtet"]["klasse"] == "unbeobachtet_lod2" and res["unbeobachtet"]["dach_oberkante_m"] > 7.8
    json.dump(res, open(os.path.join(aus, "test_lod2.json"), "w"), indent=1); print(json.dumps(res, indent=1)); return ok


def test_synth(aus):
    # Unabhaengigkeit: waehrend des Laufs darf keine Modelldatei gelesen werden
    gelesen = []; _open = builtins.open; _load = trimesh.load
    def open2(p, *a, **k):
        if isinstance(p, (str, os.PathLike)) and str(p).lower().endswith((".stl", ".obj", ".off", ".glb")) and not str(p).startswith(EIGENE[0]) and (a[:1] in (("r",), ("rb",), ()) or "mode" not in k and not a): gelesen.append(str(p))
        return _open(p, *a, **k)
    def load2(p, *a, **k):
        if isinstance(p, (str, os.PathLike)) and str(p).lower().endswith((".stl", ".obj", ".off", ".glb", ".ply")) and not str(p).startswith(EIGENE[0]): gelesen.append(str(p))
        return _load(p, *a, **k)
    sk = synth_schreiben(os.path.join(aus, "wolke")); EIGENE[0] = os.path.join(aus, "koerper")
    import wolke_carving as W
    builtins.open = open2; trimesh.load = load2
    if os.environ.get("NEGATIV") == "1": trimesh.load(os.path.join(aus, "wolke", "SOLL_nur_zur_Bewertung.stl"))   # Gegenprobe: gelesenes Modell-STL MUSS den Test fehlschlagen lassen
    try:
        erg = W.lauf(os.path.join(aus, "wolke"), os.path.join(aus, "wolke", "ausrichtung.json"), [-30, -35, -2], [50, 35, 12], os.path.join(aus, "koerper"), 87.0, (), 0.10, n_beob=600000, schritt=0.1)
    finally:
        builtins.open = _open; trimesh.load = _load
    m = trimesh.load(os.path.join(aus, "koerper", "wolke_carving_1-87.stl")); m.apply_scale(1 / 1000 * 87)   # STL in mm 1:87 -> m
    mat = np.load(os.path.join(aus, "koerper", "material.npz")); M = mat["material"]; lo = mat["lo"]; v = float(mat["vox"])
    ix = lambda p: np.floor((np.asarray(p) - lo) / v).astype(int)
    a, b = ix(np.array(HALLE[0]) + 0.5), ix(np.array(HALLE[1]) - 0.5); halle = M[a[0]:b[0], a[1]:b[1], max(a[2], ix([0, 0, 0.5])[2]):ix([0, 0, 3.5])[2]]
    leer_anteil = 1 - halle.mean()
    # Arkaden: Material-Querschnitt in der Fassadenebene y = 0.4 m, z 0.5..3.0 m -> Anzahl Luecken
    iy = ix([0, 0.4, 0])[1]; sl = M[ix([0, 0, 0])[0]:ix([20, 0, 0])[0], iy, ix([0, 0, 1.5])[2]]; frei = ~sl; lab = np.diff(np.r_[0, frei.astype(int), 0]); st = np.where(lab == 1)[0]; en = np.where(lab == -1)[0]; n_ark = int(sum(1 for a_, b_ in zip(st, en) if b_ - a_ >= 15 and a_ > 0 and b_ < len(sl)))   # Luecken >= 1,5 m, nicht am Schnittrand
    g = np.arange(0.25, 20, 0.5); gy = np.arange(0.25, 10, 0.5); gz = np.arange(0.25, 8, 0.5); Pq = np.stack(np.meshgrid(g, gy, gz, indexing="ij"), -1).reshape(-1, 3)
    soll_in = sollkoerper().contains(Pq); ist_in = M[tuple(np.clip(ix(Pq + np.array([0, 0, 0.0])).T, 0, np.array(M.shape)[:, None] - 1))]; iou = float((soll_in & ist_in).sum() / max((soll_in | ist_in).sum(), 1))
    sc = trimesh.Trimesh(m.vertices, m.faces); soll = sollkoerper()
    ok = dict(keine_modelldatei_gelesen=(len(gelesen) == 0), ein_koerper=erg["kennzahlen"]["koerper"] == 1, wasserdicht=bool(erg["kennzahlen"]["wasserdicht"]) and bool(erg["stl_wasserdicht_nach_laden"]),
              halle_ein_volumen=(leer_anteil >= 0.85), arkaden_4=(n_ark == 4))
    res = dict(ok=ok, halle_leer_anteil=round(float(leer_anteil), 3), arkaden_gezaehlt=n_ark, iou_voxel_gegen_soll=round(iou, 3), volumen_m3=erg["kennzahlen"]["volumen_m3"], soll_volumen_m3=round(float(soll.volume), 1), gelesen=gelesen)
    res["ok"] = {k: bool(x) for k, x in ok.items()}; json.dump(res, open(os.path.join(aus, "test_synth.json"), "w"), indent=1, default=float); print(json.dumps(res, indent=1, default=float)); return all(ok.values())


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("modus", choices=["synth", "lod2"]); ap.add_argument("--aus", required=True); a = ap.parse_args()
    sys.exit(0 if (test_synth(a.aus) if a.modus == 'synth' else test_lod2(a.aus)) else 1)
