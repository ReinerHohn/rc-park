#!/usr/bin/env python3
"""wolke_saeubern.py <objekt.json> --wolke ein.npy [--farben f.npy] --aus aus.npy [--umkreis 35] [--tief 1.0] - Wolke fuer Anzeige/Veto saeubern (15.11.2026):
(1) nur Punkte im --umkreis m um das Modell (Fernfeld = fremde Daecher + Rauschen, fuer das Objekt wertlos), (2) Punkte tiefer als --tief m IM
Baukoerper oberhalb --ab_hoehe weg (dort kann nichts sein), (3) Einzelpunkte ohne 3 Nachbarn in 0,5 m weg (GPU-knn). Schreibt aus.npy (+ Farben)
und ein Kontrollbild audit/wolke_sauber.png (Ansicht vorher | nachher). Die Rohwolke bleibt unveraendert."""
import sys, os, json, argparse, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def aus_pipe(pipe, od, name, min_winkel):
    """fused.ply + fused.ply.vis lesen, je Punkt den groessten Winkel zwischen dem ersten und den uebrigen Sehstrahlen (Kamera -> Punkt) bestimmen.
    Kleiner Winkel = alle Kameras fast am selben Ort = Tiefe nicht bestimmbar (ferner Hintergrund landet als 'schwebende Wolke' in falscher Tiefe)."""
    from scipy.spatial.transform import Rotation as Rot
    import wolke_neu_fusionieren as WF
    D = os.path.join(pipe, "dicht"); V = WF.ply_lesen(os.path.join(D, "fused.ply")); X = np.c_[V["x"], V["y"], V["z"]].astype(np.float64)
    raw = np.fromfile(os.path.join(D, "fused.ply.vis"), dtype=np.uint32); n = int(raw[0]) | (int(raw[1]) << 32); assert n == len(X), "vis passt nicht zur Wolke"
    cnt = np.zeros(n, np.int64); start = np.zeros(n, np.int64); p = 2
    for i in range(n): c = int(raw[p]); cnt[i] = c; start[i] = p + 1; p += 1 + c
    zf = os.path.join(D, "kamera_zentren.npy")                             # venv-seg hat trimesh, aber kein pycolmap -> Zentren vorher mit venv-colmap ablegen (--nur_zentren)
    if os.path.exists(zf): C = np.load(zf)
    else:
        import pycolmap; rec = pycolmap.Reconstruction(os.path.join(D, "sparse")); C = np.array([np.asarray(rec.images[i].projection_center()) for i in sorted(rec.reg_image_ids())]); np.save(zf, C)
    pt = np.repeat(np.arange(n), cnt); off = np.arange(cnt.sum()) - np.repeat(np.cumsum(cnt) - cnt, cnt); cam = raw[np.repeat(start, cnt) + off]
    r = C[cam] - X[pt]; r /= np.linalg.norm(r, axis=1, keepdims=True) + 1e-12; erst = np.cumsum(cnt) - cnt; r0 = r[np.repeat(erst, cnt)]
    dot = np.einsum("ij,ij->i", r, r0); mind = np.minimum.reduceat(dot, erst[cnt > 0]); w = np.zeros(n); w[cnt > 0] = np.degrees(np.arccos(np.clip(mind, -1, 1)))
    gut = w >= min_winkel
    T = json.load(open(os.path.join(od, "messprotokoll", f"SFM-AUSRICHTUNG-{name}.json")))["transformation"]; s = T["s"]; R = Rot.from_rotvec(T["rvec"]).as_matrix(); t = np.array(T["t"])
    return (((X[gut] - t) / s) @ R).astype(np.float32), np.c_[V["red"], V["green"], V["blue"]].astype(np.uint8)[gut], int((~gut).sum())


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--wolke", default=""); ap.add_argument("--pipe", default=""); ap.add_argument("--min_winkel", type=float, default=3.0); ap.add_argument("--farben", default=""); ap.add_argument("--aus", default=""); ap.add_argument("--nur_zentren", action="store_true")
    ap.add_argument("--umkreis", type=float, default=35.0); ap.add_argument("--tief", type=float, default=1.0); ap.add_argument("--ab_hoehe", type=float, default=12.0); a = ap.parse_args()
    objp = os.path.abspath(a.objekt); obj = json.load(open(objp)); od = os.path.dirname(objp); root = os.path.dirname(os.path.dirname(od))
    if "--nur_zentren" in sys.argv:
        import pycolmap; D_ = os.path.join(a.pipe, "dicht"); rec = pycolmap.Reconstruction(os.path.join(D_, "sparse"))
        np.save(os.path.join(D_, "kamera_zentren.npy"), np.array([np.asarray(rec.images[i].projection_center()) for i in sorted(rec.reg_image_ids())])); print("Kamerazentren abgelegt"); return
    import trimesh
    m = trimesh.load(os.path.join(root, obj["stl"])); m.apply_scale(float(obj.get("stl_massstab", 87)) / 1000.0); lo, hi = m.bounds; mid = (lo + hi) / 2
    if a.pipe:                                                              # Wolke direkt aus <pipe>/dicht/fused.ply + .vis: SCHNITTWINKEL-Filter (15.11.2026)
        P, F, nw = aus_pipe(a.pipe, od, os.path.basename(od), a.min_winkel); print(f"Schnittwinkel-Filter: {nw} Punkte mit < {a.min_winkel} Grad zwischen den Sehstrahlen verworfen (Tiefe unsicher: Hintergrund, Videobilder ohne Basis)")
    else: P = np.asarray(np.load(a.wolke), np.float32); F = np.load(a.farben) if a.farben else None
    n0 = len(P)
    k = (np.hypot(P[:, 0] - mid[0], P[:, 1] - mid[1]) < a.umkreis) & (P[:, 2] > lo[2] - 3) & (P[:, 2] < hi[2] + 5); n1 = int(k.sum())
    kb = k & np.all((P > lo + a.tief) & (P < hi - a.tief), axis=1) & (P[:, 2] > lo[2] + a.ab_hoehe); idx = np.flatnonzero(kb)
    if len(idx):
        drin = m.contains(P[idx].astype(float)); I = idx[drin]
        if len(I):
            d = np.abs(trimesh.proximity.signed_distance(m, P[I].astype(float))); k[I[d > a.tief]] = False
    n2 = int(k.sum())
    try:
        from gpu_knn import ball_anzahl
        Q = P[k]; c = np.asarray(ball_anzahl(Q, Q, 0.5, kmax=8)); kk = np.flatnonzero(k); k[kk[c < 4]] = False            # der Punkt selbst zaehlt mit
    except Exception as e: print("Einzelpunktfilter uebersprungen:", type(e).__name__, str(e)[:80])
    n3 = int(k.sum()); np.save(a.aus, P[k])
    if F is not None: np.save(a.aus.replace("punkte_modell", "punkte_farben") if "punkte_modell" in a.aus else a.aus[:-4] + "_farben.npy", F[k])
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    fig, ax = plt.subplots(1, 2, figsize=(16, 9)); rng = np.random.default_rng(0)
    for x, (Q, t) in zip(ax, ((P[np.hypot(P[:, 0] - mid[0], P[:, 1] - mid[1]) < 90], f"vorher ({n0} Punkte, 90-m-Ausschnitt)"), (P[k], f"nachher ({n3} Punkte)"))):
        s_ = rng.choice(len(Q), min(len(Q), 250000), replace=False); c_ = (F[np.flatnonzero(np.hypot(P[:, 0] - mid[0], P[:, 1] - mid[1]) < 90)][s_] / 255.0) if (F is not None and "vorher" in t) else ((F[k][s_] / 255.0) if F is not None else "k")
        x.scatter(Q[s_, 1], Q[s_, 2], s=0.15, c=c_); x.set_aspect("equal"); x.set_title(t); x.set_xlim(mid[1] - 60, mid[1] + 60); x.set_ylim(-5, 60)
    os.makedirs(os.path.join(od, "audit"), exist_ok=True); fig.tight_layout(); fig.savefig(os.path.join(od, "audit", "wolke_sauber.png"), dpi=70)
    print(f"SAEUBERN: {n0} -> Umkreis {n1} -> ohne Koerperinneres {n2} (-{n1 - n2}) -> ohne Einzelpunkte {n3} (-{n2 - n3}); Bild audit/wolke_sauber.png")


if __name__ == "__main__":
    main()
