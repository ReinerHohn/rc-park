#!/usr/bin/env python3
"""tiefe_lokal.py <objekt.json> <sparse> <bilder> --name N --a x y --b x y --aussen x y --feld u0 u1 z0 z1 [--k 12] [--max_size 4000] [--px 0.01] [--massstab k x y z]
LOKALE FEINRECHNUNG DER TIEFE: feines Hoehenbild (Standard 1 cm) NUR fuer ein Wandfeld - fuer Steinreliefs, Figuren, Masswerk (Nutzer 15.11.2026).

Warum: die dichte Wolke des ganzen Objekts rechnet mit 1000-1600 px Bildkante (Register: groesser bringt GLOBAL nichts, kostet Stunden) -> Netz ~3 cm, Relief 5 cm.
Auf EINER Stelle sind dagegen wenige nahe Fotos in VOLLER Aufloesung bezahlbar:
  1. Fotos waehlen: die k besten fuer das Feld (fassaden_kette.fotos_fuer_wand: Abdeckung x px/m x Frontalitaet).
  2. Teilnetz aus <sparse> nur mit diesen Bildern (Kameras bleiben die des Gesamtbuendels - keine neue Ausrichtung, gleicher Rahmen).
  3. COLMAP undistort (max_size) -> PatchMatch geometrisch (GPU) -> Fusion.
  4. Punkte in den Modellrahmen (SFM-AUSRICHTUNG), auf das Feld +-Band beschneiden, je Zelle Median des Abstands vor der Wandebene -> Hoehenbild im
     Format von relief_einsatz.py (rel, a, t, n, u0, z0, px, ...) = direkt als Relief-Einsatz baubar; dazu <name>.jpg (Schattierung) und Punktdichte.
--massstab: das Hoehenbild soll im ROHRAHMEN liegen (Schwabentor Nord): Punkte X_roh = M + (X - M) / k vor dem Rastern.
Arbeitsordner: <rc-park_daten>/<objekt>/tiefe_lokal/<name> (Datenplatte, waehrend des Laufs 2-4 GB, danach nur fused.ply). Start als Job: JOB_GPU_MB=6500 tools/job_start.sh ...
VRAM: 3200 px ~2,2 GB, 4000 px ~3 GB je Lauf - zwei 4000-px-Laeufe PLUS ein weiterer GPU-Nutzer (OWLv2, Kontrollbild) liefen in 'CUDA out of memory'; Budget 4500 MiB je 4000-px-Lauf ansetzen.
"""
import sys, os, json, argparse, time, shutil, numpy as np, cv2
HIER = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HIER)


def ply_lesen(p):
    with open(p, "rb") as f:
        kopf = b""
        while not kopf.endswith(b"end_header\n"): kopf += f.readline()
        n = int([l for l in kopf.decode().splitlines() if l.startswith("element vertex")][0].split()[-1]); props = [l.split()[1:] for l in kopf.decode().splitlines() if l.startswith("property")]
        dt = np.dtype([(nm, {"float": "<f4", "uchar": "u1", "double": "<f8"}[t]) for t, nm in props]); return np.frombuffer(f.read(n * dt.itemsize), dtype=dt, count=n)


def bilder_anpassen(rec, bilder):
    """21.11.2026 (Schwabentor-Kette: tiefe_lokal 'vom System beendet (Signal 6)' fuer w01 und w03): das Buendel war aus auf 1600 px verkleinerten Bildern gerechnet
    (Kamera 1200x1600), der Bildordner der Kette enthaelt die ORIGINALE (3000x4000). COLMAPs Entzerrer bricht dann ab ('Uncaught exceptions in thread pool', SIGABRT).
    Hier: jede Kamera auf die echte Dateigroesse umrechnen (gleiches Seitenverhaeltnis = nur Massstab; volle Aufloesung ist der Sinn der Feinrechnung),
    Bilder mit fehlender Datei oder anderem Seitenverhaeltnis aus dem Teilnetz nehmen. Liefert die Zahl der verbleibenden Bilder."""
    import cv2
    fertig = {}; raus = []
    for im in list(rec.images.values()):
        if not im.has_pose: continue
        cam = rec.cameras[im.camera_id]; p = os.path.join(bilder, im.name); b = cv2.imread(p, cv2.IMREAD_UNCHANGED) if os.path.exists(p) else None
        if b is None: raus.append((im.name, "Datei fehlt")); rec.deregister_frame(im.frame_id); continue
        h, w = b.shape[:2]
        if (w, h) == (cam.width, cam.height) or fertig.get(im.camera_id) == (w, h): continue
        if im.camera_id in fertig or abs(w / h - cam.width / cam.height) > 0.01 * cam.width / cam.height:
            raus.append((im.name, f"Datei {w}x{h}, Kamera {cam.width}x{cam.height}")); rec.deregister_frame(im.frame_id); continue
        print(f"Kamera {im.camera_id}: {cam.width}x{cam.height} -> {w}x{h} (Bildordner hat eine andere Aufloesung als das Buendel)", flush=True); cam.rescale(w, h); fertig[im.camera_id] = (w, h)
    if raus: print("aus dem Teilnetz genommen:", raus[:6], flush=True)
    return sum(1 for im in rec.images.values() if im.has_pose)


def main():
    import pycolmap, resource
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))                     # 15.11.2026: zwei Abstuerze (CUDA out of memory) schrieben je 590 MB Speicherabbild nach /var/lib/systemd/coredump = Root-Platte
    from scipy.spatial.transform import Rotation as Rot
    from fassaden_kette import fotos_fuer_wand
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("sparse"); ap.add_argument("bilder"); ap.add_argument("--name", required=True); ap.add_argument("--a", nargs=2, type=float, required=True); ap.add_argument("--b", nargs=2, type=float, required=True)
    ap.add_argument("--aussen", nargs=2, type=float, required=True); ap.add_argument("--feld", nargs=4, type=float, required=True); ap.add_argument("--k", type=int, default=12); ap.add_argument("--max_size", type=int, default=4000); ap.add_argument("--px", type=float, default=0.01)
    ap.add_argument("--band", type=float, default=0.5); ap.add_argument("--massstab", nargs=4, type=float); ap.add_argument("--nur_raster", action="store_true"); ap.add_argument("--ausrichtung"); a = ap.parse_args(); t0 = time.time()
    od = os.path.dirname(os.path.abspath(a.objekt)); name = os.path.basename(od); W = f"/media/oem/scan/rc-park_daten/{name}/tiefe_lokal/{a.name}"; os.makedirs(W, exist_ok=True)
    A = np.array(a.a); B = np.array(a.b); t = (B - A) / np.linalg.norm(B - A); n = np.array([t[1], -t[0]]); n = n if (np.array(a.aussen) - A) @ n > 0 else -n; u0, u1, z0, z1 = a.feld
    T = json.load(open(a.ausrichtung or os.path.join(od, "messprotokoll", f"SFM-AUSRICHTUNG-{name}.json")))["transformation"]; s = T["s"]; R = Rot.from_rotvec(T["rvec"]).as_matrix(); tt = np.array(T["t"])
    Am, Bm = A + u0 * t, A + u1 * t                                        # Feldenden im Rahmen der Wandangabe; fuer die Fotowahl in den Kamerarahmen (korrigiert) bringen
    if a.massstab: k_, M_ = a.massstab[0], np.array(a.massstab[1:3]); Am, Bm = M_ + k_ * (Am - M_), M_ + k_ * (Bm - M_); zf = k_
    else: zf = 1.0
    fused = os.path.join(W, "fused.ply")
    if not a.nur_raster or not os.path.exists(fused):
        # Fotowahl FUER STEREO (erster Lauf 15.11.: die 12 besten Fotos standen fast am selben Fleck -> Schnittwinkel < 3 Grad, der Geometriefilter warf 70-85 % der Tiefen weg):
        # gierig nach Guete, aber jedes neue Foto muss zu einem gewaehlten 4-35 Grad Blickwinkel-Unterschied haben und zu keinem < 1,5 Grad (Doppel).
        _, kand = fotos_fuer_wand(od, Am, Bm, n, z0 * zf, z1 * zf, k=60); mitte = np.r_[0.5 * (Am + Bm), 0.5 * (z0 + z1) * zf]; gew = []; ri = []
        for sc, _, f in kand:
            K_ = json.load(open(os.path.join(od, "messprotokoll", "K-" + f + ".json")))["kamera"]; v = np.array(K_["standort_xyz"], float) - mitte; v /= np.linalg.norm(v)
            w_ = [np.degrees(np.arccos(np.clip(v @ r_, -1, 1))) for r_ in ri]
            if not ri or (min(w_) >= 1.5 and any(4.0 <= x <= 35.0 for x in w_)): gew.append((sc, f)); ri.append(v)
            if len(gew) >= a.k: break
        fotos = [f for _, f in gew]; print("Fotos:", [(f[-12:], round(sc)) for sc, f in gew], flush=True)
        rec = pycolmap.Reconstruction(a.sparse); namen = {os.path.splitext(im.name)[0]: im.name for im in rec.images.values()}; nimm = {namen[f] for f in fotos if f in namen}
        if len(nimm) < 4: print(f"ABBRUCH: nur {len(nimm)} der gewaehlten Fotos im Netz"); return 1
        for im in list(rec.images.values()):
            if im.name not in nimm: rec.deregister_frame(im.frame_id)
        if bilder_anpassen(rec, a.bilder) < 4: print("ABBRUCH: weniger als 4 Fotos passen zu ihrer Kamera (Bildgroesse)"); return 1
        sp = os.path.join(W, "sparse_teil"); shutil.rmtree(sp, ignore_errors=True); os.makedirs(sp); rec.write(sp)
        for d_ in ("images", "stereo", "sparse"): shutil.rmtree(os.path.join(W, d_), ignore_errors=True)
        uo = pycolmap.UndistortCameraOptions(); uo.max_image_size = a.max_size; pycolmap.undistort_images(W, sp, a.bilder, output_type="COLMAP", undistort_options=uo); print(f"entzerrt {len(nimm)} Bilder, {time.time() - t0:.0f} s", flush=True)
        po = pycolmap.PatchMatchOptions(); po.max_image_size = a.max_size; po.geom_consistency = True; po.gpu_index = "0"; po.cache_size = 12; po.filter_min_triangulation_angle = 1.5; po.geom_consistency_max_cost = 2.0
        pycolmap.patch_match_stereo(W, options=po); print(f"PatchMatch fertig, {time.time() - t0:.0f} s", flush=True)
        fo = pycolmap.StereoFusionOptions(); fo.max_image_size = a.max_size; fo.min_num_pixels = 2; fo.max_reproj_error = 3.0; fo.max_depth_error = 0.03; fo.max_normal_error = 25; pycolmap.stereo_fusion(fused, W, options=fo, input_type="geometric", output_type="ply"); print(f"Fusion fertig, {time.time() - t0:.0f} s", flush=True)
    for d_ in ("stereo", "images", "sparse"): shutil.rmtree(os.path.join(W, d_), ignore_errors=True)   # Zwischendaten weg (2-4 GB je Feld; 15.11. liefen so 13 GB auf der Datenplatte voll) - fused.ply und sparse_teil bleiben
    V = ply_lesen(fused); X = ((np.c_[V["x"], V["y"], V["z"]].astype(np.float64) - tt) / s) @ R
    if a.massstab: k_, M3 = a.massstab[0], np.array(a.massstab[1:]); X = M3 + (X - M3) / k_
    uu = (X[:, :2] - A) @ t; dd = (X[:, :2] - A) @ n; g = (uu >= u0) & (uu < u1) & (X[:, 2] >= z0) & (X[:, 2] < z1) & (np.abs(dd) < a.band); uu, dd, zz = uu[g], dd[g], X[g, 2]
    px = a.px; Wn = int(round((u1 - u0) / px)); Hn = int(round((z1 - z0) / px)); iu = np.clip(((uu - u0) / px).astype(int), 0, Wn - 1); iv = np.clip((Hn - 1 - (zz - z0) / px).astype(int), 0, Hn - 1); zelle = iv * Wn + iu
    o = np.lexsort((dd, zelle)); zs, ds = zelle[o], dd[o]; st = np.r_[0, np.flatnonzero(np.diff(zs)) + 1]; anz = np.diff(np.r_[st, len(zs)]); med = ds[st + anz // 2]
    hm = np.full(Hn * Wn, np.nan, np.float32); hm[zs[st]] = med; cnt = np.zeros(Hn * Wn, np.int32); cnt[zs[st]] = anz; hm = hm.reshape(Hn, Wn); cnt = cnt.reshape(Hn, Wn); loch = ~np.isfinite(hm); roh = float(loch.mean())
    for _ in range(3):                                                    # kleine Loecher aus Nachbarn (Median 3x3 der gueltigen)
        f_ = cv2.medianBlur(np.nan_to_num(hm, nan=-9).astype(np.float32), 3); nimm_ = loch & (f_ > -5); hm[nimm_] = f_[nimm_]; loch = ~np.isfinite(hm)
    yy, xx = np.mgrid[0:Hn, 0:Wn]; G = np.c_[xx[~loch], yy[~loch], np.ones((~loch).sum())]; ko = np.linalg.lstsq(G, hm[~loch], rcond=None)[0]
    rel = hm - (ko[0] * xx + ko[1] * yy + ko[2]); rel -= np.nanmedian(rel[~loch]); rel[loch] = 0.0; q5, q95 = np.percentile(rel[~loch], [5, 95]); rel = np.clip(rel, -0.30, 0.40)
    aus = os.path.join(od, "relief", a.name + ".npz"); os.makedirs(os.path.dirname(aus), exist_ok=True)
    np.savez_compressed(aus, rel=rel.astype(np.float32), a=A, t=t, n=n, u0=u0, z0=z0, px=px, lochanteil=float(loch.mean()), lochanteil_roh=roh, hub_p5_p95=float(q95 - q5), ebene_abstand_m=float(ko[2]), trend_je_m=np.array([ko[0] / px, -ko[1] / px]),
                        oeffnung=np.zeros_like(loch), punkte_je_zelle_median=float(np.median(cnt[cnt > 0])) if (cnt > 0).any() else 0.0)
    lx = np.gradient(rel, px, axis=1); lz = np.gradient(rel, px, axis=0); sh = np.clip(0.7 - 0.25 * lx + 0.35 * lz, 0, 1); im = cv2.cvtColor((sh * 255).astype(np.uint8), cv2.COLOR_GRAY2BGR); im[loch] = (0, 0, 255); cv2.imwrite(os.path.splitext(aus)[0] + ".jpg", im)
    print(f"{a.name}: {Wn}x{Hn} Zellen a {px*100:.1f} cm, {g.sum()} Punkte im Feld ({g.sum() / max((u1-u0)*(z1-z0), 1e-9):.0f} je m2), Median {np.median(cnt[cnt > 0]) if (cnt > 0).any() else 0:.0f} Punkte/Zelle, Loecher {loch.mean()*100:.1f} % (roh {roh*100:.1f} %), Hub p5-p95 {(q95-q5)*100:.1f} cm, {time.time() - t0:.0f} s -> {aus}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
