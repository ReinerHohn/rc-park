"""Rueckprojektions-Gegenprobe (Foto-Farbkonsistenz) fuer Wolkenpunkte.

Fuer jeden Punkt der dichten Wolke (SfM-Frame, gleiche Reihenfolge wie vis-Datei)
werden die Sichtkameras aus fused.ply.vis genommen, der Punkt in jedes Foto
projiziert und dort ein Grauwert-Patch ausgeschnitten. Mass: mittlere paarweise
NCC der Patches. Gut gestuetzte, richtige Punkte ergeben hohe NCC; falsche
Treffer (Muster liegt auf anderem Bildinhalt) ergeben niedrige NCC.

Aufruf: python rueckprojektion_flaeche.py <gruppe> <n>
  gruppe: fluegel | fassade
"""
import os, sys, struct
import numpy as np
from PIL import Image

PIPE = "/media/oem/scan/rc-park_daten/schwabentor/pipe/dicht"
SPARSE = os.path.join(PIPE, "sparse")
IMGS = os.path.join(PIPE, "images")
SCR = "/tmp/claude-29999/-home-oem-git-rc-park/856e2705-d32a-409d-80ce-2f80ec2b33a2/scratchpad"
MODEL_NP = "/home/oem/git/rc-park/modelle/schwabentor/sfm/punkte_modell_schwabentor.npy"
NV = os.path.join(SCR, "nviews.npy")
PATCH = 9          # Halbbreite Patch in Pixeln (auf Kameraaufloesung)
SCALE = 0.25       # Bilder fuer Patchsuche auf 1/4 verkleinert (Kameraintrinsik wird mitskaliert)


def read_cameras(p):
    cams = {}
    with open(p, "rb") as f:
        n = struct.unpack("<Q", f.read(8))[0]
        for _ in range(n):
            cid, mid = struct.unpack("<ii", f.read(8))
            w, h = struct.unpack("<QQ", f.read(16))
            npar = {0: 3, 1: 4, 2: 4, 3: 5, 4: 8}[mid]
            par = struct.unpack("<%dd" % npar, f.read(8 * npar))
            cams[cid] = (mid, w, h, par)
    return cams


def read_images(p):
    imgs = []
    with open(p, "rb") as f:
        n = struct.unpack("<Q", f.read(8))[0]
        for _ in range(n):
            iid = struct.unpack("<i", f.read(4))[0]
            q = struct.unpack("<4d", f.read(32))
            t = struct.unpack("<3d", f.read(24))
            cid = struct.unpack("<i", f.read(4))[0]
            name = b""
            while True:
                ch = f.read(1)
                if ch == b"\x00":
                    break
                name += ch
            n2d = struct.unpack("<Q", f.read(8))[0]
            f.read(24 * n2d)
            imgs.append(dict(id=iid, q=q, t=t, cam=cid, name=name.decode()))
    return imgs


def qmat(q):
    w, x, y, z = q
    return np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
    ])


def vis_lesen(p):
    b = np.fromfile(p, dtype="<u4"); n = int(b[0]) | (int(b[1]) << 32); i = 2; out = []
    for _ in range(n):
        c = int(b[i]); out.append(b[i + 1:i + 1 + c].copy()); i += 1 + c
    return out


def project(X, cam, R, t):
    mid, w, h, par = cam
    Xc = X @ R.T + t
    z = Xc[:, 2]
    if mid == 0:      # SIMPLE_PINHOLE f,cx,cy
        f, cx, cy = par[0], par[1], par[2]; fx = fy = f
    else:             # PINHOLE / SIMPLE_RADIAL: fx,fy,cx,cy bzw. f,cx,cy,k
        if mid == 1:
            fx, fy, cx, cy = par[0], par[1], par[2], par[3]
        else:
            fx = fy = par[0]; cx, cy = par[1], par[2]
    with np.errstate(divide="ignore", invalid="ignore"):
        u = fx * Xc[:, 0] / z + cx
        v = fy * Xc[:, 1] / z + cy
    return u, v, z, w, h


def main():
    grp, n = sys.argv[1], int(sys.argv[2])
    cams = read_cameras(os.path.join(SPARSE, "cameras.bin"))
    imgs = read_images(os.path.join(SPARSE, "images.bin"))
    byid = {im["id"]: im for im in imgs}
    print("Kameras", len(cams), "Bilder", len(imgs), flush=True)

    # Punkt-Koordinaten im SfM-Frame (Dichte-Wolke) und Maske aus Modellframe
    Dp = np.load("/media/oem/scan/rc-park_daten/schwabentor/pipe/dicht_xyz_tmp.npy").astype(np.float64)
    M = np.load(MODEL_NP).astype(np.float64)
    c = np.median(np.load("/home/oem/git/rc-park/modelle/schwabentor/sfm/punkte_modell_schwabentor_veto.npy")[:, :2], axis=0)
    Pm = M - np.array([c[0], c[1], 0])
    nv = np.load(NV)
    ok = nv >= 3
    if grp == "fluegel":
        m = (Pm[:, 0] > 3.5) & (Pm[:, 1] < -1.5) & ok
    else:
        m = (Pm[:, 0] < 0) & (Pm[:, 1] > -3) & (Pm[:, 2] > 2) & (Pm[:, 2] < 10) & ok
    idx = np.where(m)[0]
    rng = np.random.default_rng(0)
    idx = rng.choice(idx, min(n, len(idx)), replace=False)
    print("Gruppe", grp, "Punkte gezogen", len(idx), flush=True)

    V = vis_lesen("/media/oem/scan/rc-park_daten/schwabentor/pipe/dicht/fused.ply.vis")

    # Bildindex-Hypothese pruefen: vis-Eintraege als Bild-ID (sortiert) oder Listenposition
    ids_sorted = sorted(byid.keys())
    pos_map = {k: byid[ids_sorted[k]] for k in range(len(ids_sorted))} if len(ids_sorted) else {}

    def bild_fuer(vi):
        return byid.get(int(vi))

    # Gueltigkeitstest: Anteil der projizierten Punkte, die vor der Kamera liegen und im Bild
    test_ids = idx[:50]
    treffer = {"id": 0, "pos": 0}
    tot = 0
    for pi in test_ids:
        X = Dp[pi:pi + 1]
        for vi in V[pi][:3]:
            tot += 1
            for key, im in (("id", byid.get(int(vi))), ("pos", pos_map.get(int(vi)))):
                if im is None:
                    continue
                cam = cams[im["cam"]]
                R = qmat(im["q"]); t = np.array(im["t"])
                u, v, z, w, h = project(X, cam, R, t)
                if z[0] > 0 and 0 <= u[0] < w and 0 <= v[0] < h:
                    treffer[key] += 1
    print("Indexpruefung (von %d): id=%d pos=%d" % (tot, treffer["id"], treffer["pos"]), flush=True)
    use = "id" if treffer["id"] >= treffer["pos"] else "pos"
    print("Verwende Hypothese:", use, flush=True)

    # Graustufen-Bilder bei Kameraaufloesung (klein genug fuer Patches)
    cache = {}

    def gray(im):
        key = im["id"]
        if key not in cache:
            cam = cams[im["cam"]]
            I = Image.open(os.path.join(IMGS, im["name"])).convert("L")
            I = I.resize((cam[1], cam[2]))
            cache[key] = np.asarray(I, dtype=np.float32)
        return cache[key]

    def patch(G, u, v):
        ui, vi = int(round(u)), int(round(v))
        if ui - PATCH < 0 or vi - PATCH < 0 or ui + PATCH >= G.shape[1] or vi + PATCH >= G.shape[0]:
            return None
        p = G[vi - PATCH:vi + PATCH + 1, ui - PATCH:ui + PATCH + 1].ravel()
        p = p - p.mean(); s = np.linalg.norm(p)
        return p / s if s > 1e-6 else None

    scores = []
    for pi in idx:
        X = Dp[pi:pi + 1]
        ps = []
        vlist = V[pi][:8]
        for vi in vlist:
            key = int(vi) if use == "id" else None
            im = byid.get(int(vi)) if use == "id" else pos_map.get(int(vi))
            if im is None:
                continue
            cam = cams[im["cam"]]
            R = qmat(im["q"]); t = np.array(im["t"])
            u, v, z, w, h = project(X, cam, R, t)
            if not (z[0] > 0):
                continue
            G = gray(im)
            # Kamerabild und Projektion auf Kameraaufloesung: Gray ist bereits auf cam-Groesse
            p = patch(G, u[0], v[0])
            if p is not None:
                ps.append(p)
        if len(ps) >= 2:
            P_ = np.array(ps)
            C = P_ @ P_.T
            k = len(ps)
            scores.append((C.sum() - k) / (k * (k - 1)))
    scores = np.array(scores)
    print(grp, "ausgewertet", len(scores), "NCC Median %.3f  p25 %.3f  p75 %.3f" % (
        np.median(scores), np.percentile(scores, 25), np.percentile(scores, 75)), flush=True)


if __name__ == "__main__":
    main()
