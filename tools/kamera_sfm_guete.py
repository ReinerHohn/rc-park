#!/usr/bin/env python3
"""kamera_sfm_guete.py - Kamera-Guete JE FOTO aus einer COLMAP-SfM (sparse/0): Reprojektionsfehler und Zahl der Beobachtungen.

Anlass (teile_sichtpruefung Runde 2, 2026-11-09): Nahfotos mit Kamerafehler lassen Bauteile ROT erscheinen, obwohl das Bauteil passt. Wer die Pose nicht belegen kann, darf nicht urteilen.
Je Foto (Name wie in images.bin): n_beob (2D-Punkte mit 3D-Punkt), rms_px (Reprojektion der Punkte mit der gespeicherten Pose/Intrinsik, in Pixeln der Originalaufloesung), rms_proz (% der langen Bildseite),
n_inlier (Punkte mit Fehler < 4 px), spur_med (mediane Spurlaenge der gesehenen Punkte). Klassen: gut | grob | schlecht (Schwellen = Argumente).
GRENZE (Memo 7.11.): Reprojektionsfehler ist BLIND fuer einen gemeinsamen Lagefehler des ganzen SfM-Netzes; er sagt nur, ob die Pose zu ihren eigenen Merkmalen passt.
  /media/oem/scan/venv-seg/bin/python -I tools/kamera_sfm_guete.py SPARSE_DIR AUS.json [--min-beob 150] [--rms-schlecht-px 2.0]"""
import sys, os, json, struct, argparse, numpy as np
_NP = {0: 3, 1: 4, 2: 4, 3: 5, 4: 8, 5: 8, 6: 12, 7: 5, 8: 4, 9: 5, 10: 12}      # COLMAP Kamera-Modell -> Zahl Parameter

def lesen(sp):
    cams = {}; b = open(os.path.join(sp, "cameras.bin"), "rb").read(); o = 8
    for _ in range(struct.unpack_from("<Q", b, 0)[0]):
        cid, mod, w, h = struct.unpack_from("<iiQQ", b, o); o += 24; n = _NP[mod]; p = struct.unpack_from("<" + "d" * n, b, o); o += 8 * n; cams[cid] = (mod, w, h, p)
    pts = {}; b = open(os.path.join(sp, "points3D.bin"), "rb").read(); o = 8; n = struct.unpack_from("<Q", b, 0)[0]; sp_len = {}
    for _ in range(n):
        pid, x, y, z = struct.unpack_from("<Qddd", b, o); o += 32 + 3; err, tl = struct.unpack_from("<dQ", b, o); o += 16 + 8 * tl; pts[pid] = (x, y, z); sp_len[pid] = tl
    im = {}; b = open(os.path.join(sp, "images.bin"), "rb").read(); o = 8
    for _ in range(struct.unpack_from("<Q", b, 0)[0]):
        iid = struct.unpack_from("<i", b, o)[0]; q = struct.unpack_from("<4d", b, o + 4); t = struct.unpack_from("<3d", b, o + 36); cid = struct.unpack_from("<i", b, o + 60)[0]; o += 64
        e = b.index(b"\0", o); name = b[o:e].decode(); o = e + 1; npt = struct.unpack_from("<Q", b, o)[0]; o += 8
        a = np.frombuffer(b, dtype=np.dtype([("x", "<f8"), ("y", "<f8"), ("p", "<i8")]), count=npt, offset=o); o += 24 * npt; im[name] = (q, t, cid, a)
    return cams, pts, sp_len, im

def quat_R(q):
    w, x, y, z = q; return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)], [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)], [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])

def guete(sp, min_beob=150, rms_schlecht=2.0, rms_gut=1.0):
    cams, pts, spur, im = lesen(sp); out = {}
    for name, (q, t, cid, a) in im.items():
        mod, w, h, p = cams[cid]; g = a["p"] >= 0; ids = a["p"][g]; xy = np.stack([a["x"][g], a["y"][g]], 1); ok = np.array([i in pts for i in ids], bool) if len(ids) else np.zeros(0, bool)
        if ok.sum() < 5: out[name] = dict(n_beob=int(ok.sum()), klasse="schlecht", grund="zu wenige Beobachtungen"); continue
        X = np.array([pts[i] for i in ids[ok]]); Xc = X @ quat_R(q).T + np.array(t); u = Xc[:, :2] / Xc[:, 2:3]
        f = p[0]; cx, cy = (p[1], p[2]) if mod in (0, 2, 3, 4) else (p[2], p[3]); k1 = p[3] if mod == 2 else 0.0
        if mod == 1: fx, fy = p[0], p[1]
        else: fx = fy = f
        r2 = (u ** 2).sum(1); d = u * (1 + k1 * r2)[:, None]; pr = np.stack([fx * d[:, 0] + cx, fy * d[:, 1] + cy], 1); e = np.linalg.norm(pr - xy[ok], axis=1); e = e[Xc[:, 2] > 0]
        rms = float(np.sqrt(np.median(e ** 2))) if len(e) else None; L = float(max(w, h))
        cl = "schlecht" if (len(e) < min_beob or rms is None or rms > rms_schlecht) else ("gut" if rms <= rms_gut else "grob")
        out[name] = dict(n_beob=int(len(e)), rms_px=round(rms, 3) if rms is not None else None, rms_proz=round(100 * rms / L, 4) if rms is not None else None, n_inlier=int((e < 4).sum()),
                         spur_med=float(np.median([spur[i] for i in ids[ok]])), klasse=cl)
    return out

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("sparse"); ap.add_argument("aus"); ap.add_argument("--min-beob", type=int, default=150); ap.add_argument("--rms-schlecht-px", type=float, default=2.0); ap.add_argument("--rms-gut-px", type=float, default=1.0)
    a = ap.parse_args(); g = guete(a.sparse, a.min_beob, a.rms_schlecht_px, a.rms_gut_px); json.dump(g, open(a.aus, "w"), indent=0)
    import collections; print(len(g), "Fotos", dict(collections.Counter(v["klasse"] for v in g.values())))
