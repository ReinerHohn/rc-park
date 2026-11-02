#!/usr/bin/env python3
"""video_ausrichten.py - Drohnen-/Video-SfM (video_sfm.py) per 3D-3D-Punktkorrespondenzen am Nordnetz ausrichten (Aehnlichkeitstransformation, RANSAC) (Register BQ).

Je Paar (Videoframe, registriertes Strassenfoto) werden COLMAP-SIFT-Deskriptoren aus beiden Datenbanken gematcht (gegenseitig nachster Nachbar + Ratio); ein Treffer, dessen Keypoints in
BEIDEN Rekonstruktionen einen 3D-Punkt tragen, liefert ein 3D-3D-Paar. RANSAC-Umeyama (Sim3) ueber alle eindeutigen Paare. Der MASSSTAB des Ergebnisses stammt aus dem Nordnetz (Bodenanker) -
unabhaengig sind hier nur die FORM-Residuen (Verzerrung/Hoehenverlauf), nicht die Skala. Ausgabe: audit/video_ausrichtung.json (+ Transformation Video -> Modellrahmen in Metern).
  /media/oem/scan/venv-colmap/bin/python -I tools/video_ausrichten.py modelle/<objekt>/objekt.json <video_sfm_ordner> [--modell 1] [--jeder 3]
"""
import sys, os, json, sqlite3, argparse, numpy as np, pycolmap

def lade_db(dbp):
    c = sqlite3.connect(f"file:{dbp}?mode=ro", uri=True); names = {i: n for i, n in c.execute("select image_id,name from images")}
    kp = {}; ds = {}
    for i, r, cc, b in c.execute("select image_id,rows,cols,data from keypoints"): kp[i] = np.frombuffer(b, np.float32).reshape(r, cc)[:, :2] if r else np.zeros((0, 2), np.float32)
    for i, r, cc, b in c.execute("select image_id,rows,cols,data from descriptors"): ds[i] = np.frombuffer(b, np.uint8).reshape(r, cc) if r else np.zeros((0, 128), np.uint8)
    return names, kp, ds

def punkt3d(rec, name2id, name):
    """Keypoint-Index -> 3D-Punkt-ID (oder -1) fuer ein Bild einer Rekonstruktion (points2D-Reihenfolge = Keypoint-Reihenfolge)."""
    iid = name2id.get(name); im = rec.images[iid] if (iid is not None and rec.exists_image(iid)) else None
    if im is None: return None
    return np.array([p.point3D_id if p.has_point3D() else -1 for p in im.points2D], dtype=np.int64)

def umeyama(A, B):
    mA, mB = A.mean(0), B.mean(0); a, b = A - mA, B - mB; U, S, Vt = np.linalg.svd(b.T @ a / len(A)); d = np.ones(3); d[-1] = np.sign(np.linalg.det(U @ Vt))
    R = U @ np.diag(d) @ Vt; s = (S * d).sum() / ((a ** 2).sum() / len(A)); t = mB - s * R @ mA; return s, R, t

def ransac(A, B, tol, it=4000, seed=1):
    rng = np.random.default_rng(seed); best = None
    for _ in range(it):
        k = rng.choice(len(A), 4, replace=False)
        try: s, R, t = umeyama(A[k], B[k])
        except Exception: continue
        if not (s > 0): continue
        e = np.linalg.norm(s * (A @ R.T) + t - B, axis=1); inl = e < tol
        if best is None or inl.sum() > best[0].sum(): best = (inl, s, R, t)
    inl = best[0]
    for _ in range(5):                                                          # Verfeinerung auf den Inliern
        s, R, t = umeyama(A[inl], B[inl]); e = np.linalg.norm(s * (A @ R.T) + t - B, axis=1); inl = e < tol
    return inl, s, R, t, e

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("video"); ap.add_argument("--modell", default="1"); ap.add_argument("--jeder", type=int, default=3)
    ap.add_argument("--modus", default="alles", choices=["alles", "dump", "match", "fit", "cpu"], help="alles (Standard) = dump (venv-colmap) -> match (venv-seg, GPU/torch, automatisch) -> fit; cpu = alles in numpy (langsam, Notfall)"); ap.add_argument("--ratio", type=float, default=0.85); ap.add_argument("--tol-m", type=float, default=1.5, help="Inlier-Schwelle in Metern (Modellrahmen)"); a = ap.parse_args()
    a.modus_ursprung = a.modus
    od = os.path.dirname(os.path.abspath(a.objekt)); dev = "cpu (numpy/BLAS; venv-colmap hat kein torch)"
    recV = pycolmap.Reconstruction(os.path.join(a.video, "sparse", a.modell)); nV, kV, dV = lade_db(os.path.join(a.video, "db.db")); n2V = {n: i for i, n in nV.items()}
    recN = pycolmap.Reconstruction(os.path.join(od, "sfm", "sparse_nord", "0")); nN, kN, dN = lade_db(os.path.join(od, "sfm", "db_nord.db")); n2N = {n: i for i, n in nN.items()}
    S = json.load(open(os.path.join(od, "messprotokoll", "SFM-AUSRICHTUNG-nord.json")))["transformation"]; sN = S["s"]
    imV = sorted([im.name for im in recV.images.values()])[::a.jeder]; imN = sorted([im.name for im in recN.images.values()])
    print(f"Video-Frames {len(imV)} (jeder {a.jeder}.) x Strassenfotos {len(imN)}, Geraet {dev}", flush=True)
    tN = {n: dN[n2N[n]].astype(np.float32) / 512.0 for n in imN if n2N.get(n) in dN}; idN = {n: punkt3d(recN, n2N, n) for n in imN}
    dump = os.path.join(a.video, "match_dump.npz"); pj = os.path.join(a.video, "paare.json")
    if a.modus == "alles":                                                       # GPU-Weg automatisch: Dump -> GPU-Matching in venv-seg -> Anpassung
        import subprocess; seg = os.environ.get("VENV_SEG_PY", "/media/oem/scan/venv-seg/bin/python"); hier = os.path.dirname(os.path.abspath(__file__))
        if os.path.exists(seg):
            a.modus = "dump"
        else: print("WARNUNG: venv-seg fehlt - Matching auf der CPU", flush=True); a.modus = "cpu"
    paare = {}; npaar = 0; a.auto_gpu = (a.modus_ursprung == "alles") and a.modus == "dump"
    if a.modus == "dump":
        Z = {"vnames": np.array(imV), "nnames": np.array(imN)}
        for k, nv in enumerate(imV):
            ids = punkt3d(recV, n2V, nv); Z[f"V{k}_d"] = dV[n2V[nv]]; Z[f"V{k}_i"] = ids if ids is not None else np.full(len(dV[n2V[nv]]), -1)
        for k, nn in enumerate(imN):
            ids = punkt3d(recN, n2N, nn); Z[f"N{k}_d"] = dN[n2N[nn]]; Z[f"N{k}_i"] = ids if ids is not None else np.full(len(dN[n2N[nn]]), -1)
        np.savez(dump, **Z); print("Dump:", dump, flush=True)
        if a.auto_gpu:
            r = subprocess.run([seg, "-W", "ignore", "-I", os.path.join(hier, "video_match_gpu.py"), a.video, "--ratio", str(a.ratio)], capture_output=True, text=True); print(r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr[-300:], flush=True)
            if r.returncode != 0: sys.exit("GPU-Matching fehlgeschlagen")
            a.modus = "fit"; P = json.load(open(pj)); paare = {tuple(int(x) for x in k.split(",")): v for k, v in P["paare"].items()}; npaar = P["bildpaare"]
        else: return
    if a.modus_ursprung != "alles": paare = {}; npaar = 0
    if a.modus == "fit" and a.modus_ursprung != "alles":
        P = json.load(open(pj)); paare = {tuple(int(x) for x in k.split(",")): v for k, v in P["paare"].items()}; npaar = P["bildpaare"]
    elif a.modus in ("cpu",):
        for nv in imV:
            iv = n2V[nv]; ids = punkt3d(recV, n2V, nv)
            if ids is None or iv not in dV or (ids >= 0).sum() < 30: continue
            tv = dV[iv].astype(np.float32) / 512.0
            for nn in imN:
                if nn not in tN or idN[nn] is None: continue
                sim = tv @ tN[nn].T; i2 = np.argpartition(-sim, 1, axis=1)[:, :2]; vv = np.take_along_axis(sim, i2, 1); o = np.argsort(-vv, axis=1); i2 = np.take_along_axis(i2, o, 1); vv = np.take_along_axis(vv, o, 1)
                ok = np.arccos(np.clip(vv[:, 0], -1, 1)) < a.ratio * np.arccos(np.clip(vv[:, 1], -1, 1)); back = sim.argmax(0); mut = back[i2[:, 0]] == np.arange(len(tv)); m = np.nonzero(ok & mut)[0]
                if len(m) < 12: continue
                j = i2[m, 0]; pv = ids[m]; pn = idN[nn][j]; g = (pv >= 0) & (pn >= 0)
                for x, y in zip(pv[g], pn[g]): paare[(int(x), int(y))] = paare.get((int(x), int(y)), 0) + 1
                npaar += 1
    print(f"{npaar} Bildpaare mit Treffern, {len(paare)} eindeutige 3D-3D-Paare", flush=True)
    if len(paare) < 12: sys.exit("zu wenige 3D-3D-Paare - keine Ausrichtung")
    ks = list(paare); A = np.array([recV.points3D[k[0]].xyz for k in ks]); B = np.array([recN.points3D[k[1]].xyz for k in ks]); w = np.array([paare[k] for k in ks])
    tol = a.tol_m * sN                                                          # Meter -> Einheiten des Nordnetzes
    inl, s, R, t, e = ransac(A, B, tol); res_m = e[inl] / sN
    out = dict(video=a.video, modell=a.modell, bildpaare=npaar, paare=len(ks), inlier=int(inl.sum()), skala_video_zu_nord=float(s), skala_m_je_videoeinheit=float(s / sN), rms_m=float(np.sqrt((res_m ** 2).mean())), median_m=float(np.median(res_m)),
               R=R.tolist(), t=t.tolist(), tol_m=a.tol_m, hinweis="Massstab stammt aus dem Nordnetz (Bodenanker); unabhaengig sind nur die Form-Residuen")
    print(f"Inlier {inl.sum()} / {len(ks)}; Skala Video->Nord {s:.4f} ({s / sN:.3f} m je Videoeinheit); Residuum RMS {out['rms_m']:.2f} m, Median {out['median_m']:.2f} m")
    # Form-Residuen ueber der Hoehe (Nord -> Modellrahmen: z)
    rv = S["rvec"]; Rm = pycolmap.Rotation3d(np.array(rv)).matrix() if hasattr(pycolmap, "Rotation3d") else None; tm = np.array(S["t"])
    if Rm is not None:
        Xm = ((B[inl] - tm) @ Rm) / sN; z = Xm[:, 2]; bins = [0, 10, 20, 30, 40, 50, 70]; hz = []
        for lo, hi in zip(bins[:-1], bins[1:]):
            k = (z >= lo) & (z < hi)
            if k.sum() >= 5: hz.append(dict(z=[lo, hi], n=int(k.sum()), median_m=round(float(np.median(res_m[k])), 3))); print(f"  z {lo:2d}-{hi:2d} m: n={k.sum():4d}  Median-Residuum {np.median(res_m[k]):.2f} m")
        out["hoehenverlauf"] = hz
    os.makedirs(os.path.join(od, "audit"), exist_ok=True); json.dump(out, open(os.path.join(od, "audit", "video_ausrichtung.json"), "w"), indent=1)

if __name__ == "__main__":
    main()
