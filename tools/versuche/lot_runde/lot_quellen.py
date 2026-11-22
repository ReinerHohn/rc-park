#!/usr/bin/env python3
"""lot_quellen.py <ziel> [...] - LOT-RUNDE 22.11.2026: welche Lot-Quelle laesst das Modell NICHT kippen? (venv-colmap: pycolmap fuer sparse/0)

Bezug = gemeinsamer Kippvektor der Waende (tools/lot_wandneigung.py) der GESCHRIEBENEN Ausrichtung (modelle/<ziel>/sfm/punkte_modell_<ziel>.npy):
die wahre Turmachse im Modellrahmen ist u = (tx, ty, 100)/|..| (t in cm/m). Jede Lot-Quelle v (im SfM-Rahmen) wird mit der Drehung der Ausrichtung
(X_sfm = s R X_modell + t) in den Modellrahmen gebracht (R^T v). Waere v das Lot des Modells, kippte das Modell um k_v = 100 (u_xy/u_z - v_xy/v_z) cm/m.
Quellen: Kameraebene (70 % nahe Kameras, wie Ausrichtung alt), Bild-x-Achsen (seiten_gps_vereinen.lot_info), Wandlot dicht (Normalen der dichten Wolke fused.ply,
wie versuche/lage_eine_funktion/lot_wand.py), Wandlot sparse (Normalen per Nachbar-PCA der sparse/0-Punkte), Fluchtpunkte (schwerkraft_je_bild.lot_welt),
Hochachse der geschriebenen Ausrichtung (= 'Feinfit', k = t selbst). EXIF-Schwerkraft: nubia Z2462N schreibt keine (kein MakerNote/Beschleunigung; geprueft).
UNABHAENGIGKEIT: Wandlot dicht nutzt dieselbe Wolke wie der Bezug (nicht unabhaengig); sparse/Fluchtpunkte/Kameras nicht."""
import os, sys, json, math
import numpy as np
from scipy.spatial import cKDTree
from scipy.spatial.transform import Rotation as Rot
T = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); sys.path.insert(0, T)
import seiten_gps_vereinen as SG, lot_wandneigung as LW, schwerkraft_je_bild as SJ
W = "/home/oem/git/rc-park"; D = "/media/oem/scan/rc-park_daten"


def wandlot(N, start, grad=20.0, it=6):
    """Lot = kleinster Singulaervektor der fast waagerechten Normalen (Waende), iterativ ab start."""
    up = np.asarray(start, float)
    for _ in range(it):
        w = np.abs(N @ up) < math.sin(math.radians(grad))
        u = np.linalg.svd(N[w], full_matrices=False)[2][2]; up = u if u @ start > 0 else -u
    return up, int(w.sum())


def normalen_pca(P, k=16, max_n=400000, seed=0):
    if len(P) > max_n: P = P[np.random.default_rng(seed).choice(len(P), max_n, replace=False)]
    _, J = cKDTree(P).query(P, k=k); Q = P[J] - P[J].mean(1, keepdims=True); Cv = np.einsum("nki,nkj->nij", Q, Q)
    ev, evec = np.linalg.eigh(Cv); planar = ev[:, 0] / np.maximum(ev[:, 1], 1e-12) < 0.05
    return evec[planar, :, 0]


def dicht_normalen(ply, n_ziel=300000):
    dt = np.dtype([("x", "<f4"), ("y", "<f4"), ("z", "<f4"), ("nx", "<f4"), ("ny", "<f4"), ("nz", "<f4"), ("r", "u1"), ("g", "u1"), ("b", "u1")])
    kopf = open(ply, "rb").read(4096); e = kopf.index(b"end_header\n") + 11
    n = int([l for l in kopf[:e].decode(errors="ignore").splitlines() if l.startswith("element vertex")][0].split()[-1])
    V = np.memmap(ply, dtype=dt, mode="r", offset=e, shape=(n,))[::max(1, n // n_ziel)]
    N = np.c_[V["nx"], V["ny"], V["nz"]].astype(float); N = N[np.isfinite(N).all(1)]; return N / np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-9)


def kipp(u_true, v_m):
    return 100 * (u_true[:2] / u_true[2] - v_m[:2] / v_m[2])


def stand(ziel, mit_flucht=True):
    kj = f"{D}/{ziel}/pipe/kameras.json"; au = f"{W}/modelle/{ziel}/messprotokoll/SFM-AUSRICHTUNG-{ziel}.json"; ob = f"{W}/modelle/{ziel}/objekt.json"
    wo = f"{W}/modelle/{ziel}/sfm/punkte_modell_{ziel}.npy"; ply = f"{D}/{ziel}/pipe/dicht/fused.ply"; sp = f"{D}/{ziel}/pipe/sfm/sparse/0"
    KJ = json.load(open(kj)); AU = json.load(open(au)); obj = json.load(open(ob)); R = Rot.from_rotvec(AU["transformation"]["rvec"]).as_matrix()
    tor = LW.pruefen(np.load(wo, mmap_mode="r"), obj); t = np.array(tor.get("t_cm_m") or [np.nan, np.nan]); u_true = np.r_[t / 100, 1.0]; u_true /= np.linalg.norm(u_true)
    print(f"\n=== {ziel}: Bezug {LW.bericht_zeile(tor)}", flush=True)
    Rs = np.array([b["R"] for b in KJ["bilder"]], float); C = np.array([b["C"] for b in KJ["bilder"]], float)
    li = SG.lot_info(Rs); bx = np.asarray(li["oben"], float)
    dc = np.linalg.norm(C - np.median(C, 0), axis=1); nah = dc <= np.percentile(dc, 70); eb = np.linalg.svd(C[nah] - C[nah].mean(0))[2][2]; eb = eb if eb @ bx > 0 else -eb
    Q = {"kameraebene": eb, "bild_x": bx, "feinfit_geschrieben": R[:, 2]}
    if os.path.isfile(ply): Q["wandlot_dicht"], nw = wandlot(dicht_normalen(ply), bx); print(f"  Wandlot dicht: {nw} Wandnormalen")
    try:
        import pycolmap
        r = pycolmap.Reconstruction(sp); P = np.array([p.xyz for p in r.points3D.values() if p.track.length() >= 3 and p.error < 2.0])
        Ns = normalen_pca(P); Q["wandlot_sparse"], nw = wandlot(Ns, bx); print(f"  Wandlot sparse: {len(P)} Punkte, {len(Ns)} ebene Normalen, {nw} Wandnormalen")
    except Exception as e: print("  sparse nicht lesbar:", e)
    if mit_flucht:
        cams = KJ["kameras"]; ks = []
        for b in KJ["bilder"]:
            c = cams[str(b["cam"])]; p = c["params"]; ks.append(dict(name=b["name"], R=b["R"], f=p[0] if c["model"] in ("SIMPLE_PINHOLE", "SIMPLE_RADIAL", "RADIAL") else 0.5 * (p[0] + p[1]),
                                                                  cx=p[1] if c["model"] in ("SIMPLE_PINHOLE", "SIMPLE_RADIAL", "RADIAL") else p[2], cy=p[2] if c["model"] in ("SIMPLE_PINHOLE", "SIMPLE_RADIAL", "RADIAL") else p[3],
                                                                  breite=c["width"], hoehe=c["height"]))
        fl = SJ.lot_welt(ks, f"{D}/{ziel}/fotos", n_max=200, oben_ref=bx)
        if fl: Q["fluchtpunkte"] = np.array(fl["oben"]); print(f"  Fluchtpunkte: {fl['n']} Bilder, {fl['getragen']} < 3 Grad, Streuung Median {fl['streuung_median_grad']:.2f} / p90 {fl['streuung_p90_grad']:.2f} Grad")
    erg = {}
    for k_, v in Q.items():
        v = np.asarray(v, float) / np.linalg.norm(v); vm = R.T @ v; vm = vm if vm[2] > 0 else -vm; kv = kipp(u_true, vm)
        erg[k_] = dict(kipp_cm_m=[round(float(x), 2) for x in kv], betrag_cm_m=round(float(np.hypot(*kv)), 2), betrag_grad=round(math.degrees(math.atan(np.hypot(*kv) / 100)), 2),
                       richtung_grad=round(math.degrees(math.atan2(kv[1], kv[0])), 0), oben_sfm=v.tolist())
        print(f"  {k_:20s} Kippung {erg[k_]['betrag_cm_m']:5.2f} cm/m ({erg[k_]['betrag_grad']:.2f} Grad) Richtung {erg[k_]['richtung_grad']:+.0f}  ({kv[0]:+.2f}, {kv[1]:+.2f})", flush=True)
    names = list(Q)
    for i in range(len(names)):
        for j in range(i):
            a = math.degrees(math.acos(min(1, abs(float(np.asarray(Q[names[i]]) @ np.asarray(Q[names[j]])) / np.linalg.norm(Q[names[i]]) / np.linalg.norm(Q[names[j]])))))
            erg.setdefault("_winkel", {})[f"{names[i]}|{names[j]}"] = round(a, 2)
    return dict(tor=tor, quellen=erg)


if __name__ == "__main__":
    ausd = os.environ.get("LOT_AUS", "/media/oem/rcdaten/tmp/lot_runde"); os.makedirs(ausd, exist_ok=True)
    for z in sys.argv[1:]:
        e = stand(z, mit_flucht=os.environ.get("LOT_FLUCHT", "1") == "1"); json.dump(e, open(os.path.join(ausd, f"lot_quellen_{z}.json"), "w"), indent=1, default=float)
