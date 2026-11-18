#!/usr/bin/env python3
"""teilfusion.py <workspace> <aus.ply> [--max_bilder N] [--min_num_pixels 8] [--max_image_size 1600] [--input_type photometric]
TEILFUSION (18.11.2026, Kaufhaus gk2: 595 Bilder, Tiefen+Normalenkarten 17,6 GB > 15 GB RAM). COLMAP-Fusion laedt alle Karten in den RAM;
mit use_cache (4,4 GB) laeuft sie auf 1 Thread und laedt staendig nach (4 h, 1,56 TB gelesen, nicht fertig). Hier VOLLE Aufloesung in Teilen:
  1. Bilder aus <workspace>/stereo/fusion.cfg nach Blickziel (Kamerazentrum + Blickrichtung x mittlere Punkttiefe) per k-means in Kerne teilen;
  2. jeder Teil = Kern + Nachbarbilder mit den meisten gemeinsamen SfM-Punkten bis max_bilder (die Fusion braucht die Nachbarn fuer die Konsistenz);
  3. je Teil COLMAP-Fusion ohne Cache, alle Kerne (Spiegel-Workspace mit Symlinks und eigener fusion.cfg);
  4. aus jedem Teil nur Punkte behalten, deren BEZUGSBILD (erstes Bild in fused.ply.vis = Startbild der Fusion) zum Kern gehoert -> jede Flaeche genau einmal.
max_bilder Standard: 60 % MemAvailable / 45 MB je Bild (Messung 18.11.: 100 Bilder 1600 px = 4,1 GB, 52 s, 28 Threads).
Pruefung 18.11.: Zuordnung vis-Index -> Bild (sortierte image_ids) 2934/2934 Punkte liegen im Bezugsbild.
Schreibt <aus.ply> (binary, x y z nx ny nz rgb wie COLMAP) und <aus.ply>.teile.json (Teile, Zeiten, Punkte)."""
import os, sys, json, time, shutil, argparse, numpy as np

DT = np.dtype([("x", "<f4"), ("y", "<f4"), ("z", "<f4"), ("nx", "<f4"), ("ny", "<f4"), ("nz", "<f4"), ("r", "u1"), ("g", "u1"), ("b", "u1")])


def ply_lesen(p):
    raw = open(p, "rb").read(); h = raw.index(b"end_header\n") + 11
    n = int([l for l in raw[:h].decode().splitlines() if l.startswith("element vertex")][0].split()[-1]); return np.frombuffer(raw[h:h + n * DT.itemsize], DT).copy()


def vis_ref(p, n):
    v = np.fromfile(p, np.uint8); m = int(v[:8].view("<u8")[0]); assert m == n, (m, n); ref = np.empty(m, np.int64); o = 8
    u4 = lambda i: int(v[i:i + 4].view("<u4")[0])
    for i in range(m): k = u4(o); ref[i] = u4(o + 4); o += 4 + 4 * k
    return ref


def ply_schreiben(p, P):
    with open(p, "wb") as f:
        f.write(("ply\nformat binary_little_endian 1.0\nelement vertex %d\nproperty float x\nproperty float y\nproperty float z\nproperty float nx\nproperty float ny\nproperty float nz\n"
                 "property uchar red\nproperty uchar green\nproperty uchar blue\nend_header\n" % len(P)).encode()); f.write(P.tobytes())


def kmeans(X, k, it=50, seed=0):
    rng = np.random.default_rng(seed); C = X[rng.choice(len(X), k, replace=False)]
    for _ in range(it):
        L = np.argmin(((X[:, None] - C[None]) ** 2).sum(-1), 1)
        C2 = np.array([X[L == j].mean(0) if (L == j).any() else C[j] for j in range(k)])
        if np.allclose(C2, C): break
        C = C2
    return L


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("ws"); ap.add_argument("aus"); ap.add_argument("--max_bilder", type=int, default=0)
    ap.add_argument("--min_num_pixels", type=int, default=5); ap.add_argument("--max_image_size", type=int, default=1600); ap.add_argument("--input_type", default="photometric"); ap.add_argument("--kern_anteil", type=float, default=0.6)
    a = ap.parse_args(); import pycolmap; t0 = time.time()
    if not a.max_bilder:
        frei = int([l for l in open("/proc/meminfo") if l.startswith("MemAvailable")][0].split()[1]) / 1048576; a.max_bilder = max(40, int(0.6 * frei / 0.045))
    namen = [l.strip() for l in open(os.path.join(a.ws, "stereo", "fusion.cfg")) if l.strip()]
    rec = pycolmap.Reconstruction(os.path.join(a.ws, "sparse")); ids = sorted(rec.images.keys()); idx_name = {i: rec.images[ii].name for i, ii in enumerate(ids)}
    by_name = {rec.images[ii].name: ii for ii in ids}; namen = [n for n in namen if n in by_name]; N = len(namen)
    print(f"{N} Bilder in fusion.cfg, max_bilder je Teil {a.max_bilder}", flush=True)
    pkt = {}; ziel = []
    for n in namen:
        im = rec.images[by_name[n]]; ps = [p.point3D_id for p in im.points2D if p.has_point3D()]; pkt[n] = set(ps)
        T = im.cam_from_world().matrix(); R = T[:, :3]; c = -R.T @ T[:, 3]; d = R.T @ np.array([0, 0, 1.0])
        tiefe = np.median([(R @ rec.points3D[p].xyz + T[:, 3])[2] for p in ps[:300]]) if ps else 10.0
        ziel.append(c + d * tiefe)
    ziel = np.array(ziel); kern_n = max(10, int(a.kern_anteil * a.max_bilder)); k = int(np.ceil(N / kern_n))
    L = kmeans(ziel, k) if k > 1 else np.zeros(N, int); teile = []
    for j in range(k):
        kern = [namen[i] for i in np.where(L == j)[0]]
        if not kern: continue
        if len(kern) > a.max_bilder:      # zu grosser Cluster -> nach Blickziel weiter teilen
            sub = kmeans(ziel[L == j], int(np.ceil(len(kern) / kern_n)), seed=j); teile += [[kern[i] for i in np.where(sub == s)[0]] for s in np.unique(sub)]
        else: teile.append(kern)
    alle = [] ; info = []; tmp = os.path.join(os.path.dirname(os.path.abspath(a.aus)), "teilfusion_tmp")
    for j, kern in enumerate(teile):
        kp = set().union(*(pkt[n] for n in kern)); ks = set(kern)
        nachb = sorted((n for n in namen if n not in ks), key=lambda n: -len(pkt[n] & kp))[:max(0, a.max_bilder - len(kern))]
        nachb = [n for n in nachb if len(pkt[n] & kp) > 0]; liste = kern + nachb
        shutil.rmtree(tmp, ignore_errors=True); os.makedirs(os.path.join(tmp, "stereo"))
        for x in ("images", "sparse"): os.symlink(os.path.join(os.path.abspath(a.ws), x), os.path.join(tmp, x))
        for x in ("depth_maps", "normal_maps", "consistency_graphs"):
            if os.path.exists(os.path.join(a.ws, "stereo", x)): os.symlink(os.path.join(os.path.abspath(a.ws), "stereo", x), os.path.join(tmp, "stereo", x))
        open(os.path.join(tmp, "stereo", "fusion.cfg"), "w").write("\n".join(liste) + "\n")
        fo = pycolmap.StereoFusionOptions(); fo.max_image_size = a.max_image_size; fo.min_num_pixels = a.min_num_pixels; t1 = time.time()
        pycolmap.stereo_fusion(os.path.join(tmp, "fused.ply"), tmp, options=fo, input_type=a.input_type, output_type="ply")
        P = ply_lesen(os.path.join(tmp, "fused.ply")); ref = vis_ref(os.path.join(tmp, "fused.ply.vis"), len(P))
        behalten = np.array([idx_name.get(int(r)) in ks for r in ref], bool) if len(P) else np.zeros(0, bool); alle.append(P[behalten])
        info.append(dict(teil=j, kern=len(kern), nachbarn=len(nachb), punkte_teil=int(len(P)), punkte_behalten=int(behalten.sum()), sekunden=round(time.time() - t1)))
        print(f"Teil {j + 1}/{len(teile)}: Kern {len(kern)} + {len(nachb)} Nachbarn -> {len(P)} Punkte, {int(behalten.sum())} behalten ({time.time() - t1:.0f} s)", flush=True)
    shutil.rmtree(tmp, ignore_errors=True)
    G = np.concatenate(alle) if alle else np.zeros(0, DT); ply_schreiben(a.aus, G)
    json.dump(dict(bilder=N, max_bilder=a.max_bilder, teile=info, punkte=int(len(G)), sekunden=round(time.time() - t0), min_num_pixels=a.min_num_pixels, max_image_size=a.max_image_size), open(a.aus + ".teile.json", "w"), indent=1)
    print(f"TEILFUSION {len(G)} Punkte aus {len(teile)} Teilen ({time.time() - t0:.0f} s) -> {a.aus}", flush=True); return 0 if len(G) else 3


if __name__ == "__main__": sys.exit(main())
