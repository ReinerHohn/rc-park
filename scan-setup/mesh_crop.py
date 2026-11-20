#!/usr/bin/env python3
"""Schneidet ein binaeres PLY-Mesh (nur xyz + Dreiecke) auf einen Quader zu.
Nutzung: mesh_crop.py eingabe.ply ausgabe.ply xmin xmax ymin ymax zmin zmax [--stl]
Die Grenzen sind in Koordinaten des Meshes (der Viewer zeigt sie an).
Behalten werden alle Flaechen, deren drei Ecken im Quader liegen; ungenutzte Punkte fallen weg.
"""
import sys, struct
import numpy as np

def lies(pfad):
    with open(pfad, "rb") as f:
        kopf = b""
        while not kopf.endswith(b"end_header\n"):
            kopf += f.readline()
        t = kopf.decode().split("\n")
        nv = int(next(z for z in t if z.startswith("element vertex")).split()[2])
        nf = int(next(z for z in t if z.startswith("element face")).split()[2])
        if "binary_little_endian" not in kopf.decode() or sum(z.startswith("property") for z in t) != 4:
            sys.exit("nur binary_little_endian PLY mit x,y,z + Flaechenliste (wie OpenMVS) unterstuetzt")
        v = np.frombuffer(f.read(nv * 12), "<f4").reshape(nv, 3)
        fl = np.frombuffer(f.read(nf * 13), np.dtype([("n", "u1"), ("i", "<u4", 3)]))
    return v, fl["i"]

def schreibe_ply(pfad, v, f):
    kopf = (f"ply\nformat binary_little_endian 1.0\nelement vertex {len(v)}\nproperty float32 x\n"
            f"property float32 y\nproperty float32 z\nelement face {len(f)}\n"
            "property list uint8 uint32 vertex_indices\nend_header\n").encode()
    fl = np.empty(len(f), np.dtype([("n", "u1"), ("i", "<u4", 3)]))
    fl["n"] = 3; fl["i"] = f
    with open(pfad, "wb") as o:
        o.write(kopf); o.write(v.astype("<f4").tobytes()); o.write(fl.tobytes())

def schreibe_stl(pfad, v, f):
    d = np.zeros(len(f), np.dtype([("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")]))
    d["v"] = v[f]
    nn = np.cross(d["v"][:, 1] - d["v"][:, 0], d["v"][:, 2] - d["v"][:, 0])
    d["n"] = nn / np.maximum(np.linalg.norm(nn, axis=1, keepdims=True), 1e-20)
    with open(pfad, "wb") as o:
        o.write(b"mesh_crop".ljust(80, b"\0")); o.write(struct.pack("<I", len(f))); o.write(d.tobytes())

if __name__ == "__main__":
    a = [x for x in sys.argv[1:] if x != "--stl"]
    if len(a) != 8:
        sys.exit(__doc__)
    v, f = lies(a[0])
    lo = np.array([a[2], a[4], a[6]], float); hi = np.array([a[3], a[5], a[7]], float)
    drin = ((v >= lo) & (v <= hi)).all(axis=1)
    f = f[drin[f].all(axis=1)]
    benutzt = np.unique(f)
    neu = np.full(len(v), -1, np.int64); neu[benutzt] = np.arange(len(benutzt))
    v, f = v[benutzt], neu[f].astype(np.uint32)
    schreibe_ply(a[1], v, f)
    if "--stl" in sys.argv:
        schreibe_stl(a[1].rsplit(".", 1)[0] + ".stl", v, f)
    print(f"{len(v)} Punkte, {len(f)} Flaechen -> {a[1]}")
