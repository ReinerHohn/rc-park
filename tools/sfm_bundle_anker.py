#!/usr/bin/env python3
"""sfm_bundle_anker.py - Buendelausgleich MIT amtlichen Ankern (Register AI): COLMAP-Netz nicht nachtraeglich aehnlich transformieren,
sondern Kameras, 3D-Punkte und (unbekannte) Brennweiten GEMEINSAM gegen LoD2-Eckkanten und Bodenpunkte loesen.

Warum: Ein einseitig fotografiertes, fast ebenes Bauwerk (Suedfassade Martinstor) ergibt ein in sich verzerrtes SfM-Netz
(Brennweite/Tiefe mehrdeutig). Das Nordnetz liess sich mit 7 Parametern ausrichten (Residuen 1-8 px), das Suednetz nicht
(Residuen 100-275 px, Untergruppen-Massstaebe 0,23..0,89). Die Anker muessen deshalb IN die Ausgleichung - genau das
'Gleichungssystem aus vielen Bildern + ein absoluter Referenzwert'.

Unbekannte: je Kamera Drehung (3), Lage (3), Brennweite (1; EXIF-Prior = starker Prior); je SfM-Punkt xyz.
Beobachtungen: alle COLMAP-Spurpunkte (Pixel, sigma 1 px, soft_l1), Eckkanten-Linienpicks (Abstand Pick zu projizierter Kante,
sigma 3 px), Bodenpunkt-Picks (sigma je Pick), optional ANNAHME Strassenkamera-Hoehe. Rahmen = Modellsystem (anker3d.json),
Massstab/Lot/Nordung kommen aus den Ankern, nicht aus einer Annahme.
Start: beste Aehnlichkeitstransformation aus tools/sfm_ausrichten.py (darf grob sein).
  /media/oem/scan/venv-colmap/bin/python -I tools/sfm_bundle_anker.py modelle/<objekt>/objekt.json --sparse <sparse/0> --fotos <picks-fotos>
        --name sued [--kamerahoehe 1.7 1.0] [--luftbilder ...] [--schreiben]
Schreibt messprotokoll/SFM-AUSRICHTUNG-<name>.json (gleiches Format wie sfm_ausrichten.py, "methode": "buendel_anker") und
sfm/punkte_modell_<name>.npy; der Viewer tools/sfm_html_viewer.py liest beides.
"""
import sys, os, json, math, argparse, time, numpy as np, cv2
from scipy.optimize import least_squares
from scipy.sparse import lil_matrix
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sfm_ausrichten as SA
import pycolmap

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--sparse", required=True); ap.add_argument("--fotos", nargs="*")
    ap.add_argument("--name", required=True); ap.add_argument("--schreiben", action="store_true")
    ap.add_argument("--kamerahoehe", nargs=2, type=float, metavar=("H0", "SIGMA")); ap.add_argument("--luftbilder", nargs="*", default=[])
    ap.add_argument("--prior-sigma", type=float, default=0.03, help="relative Sigma der EXIF-Brennweite (Standard 3 %)")
    ap.add_argument("--spur-sigma", type=float, default=1.0, help="Sigma der COLMAP-Spurpunkte in SfM-Pixeln")
    a = ap.parse_args()
    obj, root, od, A, rec, kams, Ks = SA.lade(a.objekt, a.sparse)
    if a.fotos: Ks = {nr: K for nr, K in Ks.items() if nr in a.fotos}
    B = SA.beobachtungen(A, kams, Ks); print(f"SfM: {len(kams)} Kameras, {rec.num_points3D()} Punkte; Anker-Beobachtungen {len(B)} aus {sorted({b[0] for b in B})}")
    # --- Startwert: Aehnlichkeitstransformation (grob)
    prior_h = (a.kamerahoehe[0], a.kamerahoehe[1], [nr for nr in kams if nr not in a.luftbilder]) if a.kamerahoehe else None
    best = None
    for p0 in SA.starts(rec, kams):
        try: sol = least_squares(SA.resid, p0, args=(B, kams, False, prior_h), method="trf", x_scale="jac", max_nfev=2000, loss="soft_l1")
        except Exception: continue
        if best is None or sol.cost < best.cost: best = sol
    s = math.exp(best.x[0]); R = SA.rot(best.x[1:4]); t = best.x[4:7]; Rm = R.T; sm = 1.0 / s; tm = -Rm @ t * sm
    print(f"Start (Aehnlichkeit): Kosten {best.cost:.1f}, Massstab {s:.4f}")
    # --- Netz in Modellrahmen: Kameras R' = R_s R, t' = (R_s t + t_s)/s ; Punkte X_m = Rm (X_s - t)/s
    nrs = sorted(kams); ci = {nr: i for i, nr in enumerate(nrs)}
    pids = sorted(rec.points3D.keys()); pi = {pid: j for j, pid in enumerate(pids)}
    X0 = np.array([rec.points3D[pid].xyz for pid in pids]) @ Rm.T * sm + tm      # X_m = Rm X_s / s + tm (wie sfm_ausrichten.nach_modell)
    # Brennweiten-Prior aus Netzbericht (sfm_netz.py) falls vorhanden, sonst aus K-json brennweite_px (Original-px) * fak
    prior_f = {}
    nb = os.path.join(od, "sfm", f"netz_{a.name}.json")
    if os.path.exists(nb):
        N = json.load(open(nb)); last = N["runden"][-1]["kameras"]
        for nr, r in last.items():
            if r.get("prior_f_px") and nr in kams: prior_f[nr] = float(r["prior_f_px"])
    for nr, K in Ks.items():
        if K.get("brennweite_px") and nr not in prior_f: prior_f[nr] = float(K["brennweite_px"]) * kams[nr].fak
    print("Brennweiten-Prior (SfM-px):", {k: round(v) for k, v in prior_f.items()})
    # Spurbeobachtungen
    obs_c, obs_p, obs_uv = [], [], []
    for im in rec.images.values():
        nr = os.path.splitext(im.name)[0]
        if nr not in ci: continue
        for p2 in im.points2D:
            if p2.has_point3D() and p2.point3D_id in pi: obs_c.append(ci[nr]); obs_p.append(pi[p2.point3D_id]); obs_uv.append(p2.xy)
    obs_c = np.array(obs_c); obs_p = np.array(obs_p); obs_uv = np.array(obs_uv); nC = len(nrs); nP = len(pids)
    print(f"Spurbeobachtungen: {len(obs_uv)}; Unbekannte: {7 * nC + 3 * nP}")
    # Parametervektor
    p0 = np.zeros(7 * nC + 3 * nP)
    for nr, i in ci.items():
        k = kams[nr]; Rc = k.R @ R; tc = (k.R @ t + k.t) / s; p0[7 * i:7 * i + 3] = cv2.Rodrigues(Rc)[0].ravel(); p0[7 * i + 3:7 * i + 6] = tc; p0[7 * i + 6] = k.fx
    p0[7 * nC:] = X0.ravel()
    kdist = {nr: list(kams[nr].k) for nr in nrs}; cxy = {nr: (kams[nr].cx, kams[nr].cy) for nr in nrs}
    def proj_cam(i, X, p):
        nr = nrs[i]; Rc = SA.rot(p[7 * i:7 * i + 3]); tc = p[7 * i + 3:7 * i + 6]; f = p[7 * i + 6]
        Xc = X @ Rc.T + tc; z = Xc[:, 2]; x = Xc[:, 0] / z; y = Xc[:, 1] / z; r2 = x * x + y * y
        d = 1.0 + sum(kk * r2 ** (m + 1) for m, kk in enumerate(kdist[nr]))
        return np.c_[f * x * d + cxy[nr][0], f * y * d + cxy[nr][1]], z
    # Anker-Residuen (gleiche Form wie sfm_ausrichten.resid, aber mit freien Kameras)
    def anker_res(p, roh=False):
        r = []; info = []
        for b in B:
            nr, art, n, uv, X, sig = b[:6]; spx = b[6] if len(b) > 6 else SA.SIGMA_PICK_PX; i = ci[nr]; k = kams[nr]; f = p[7 * i + 6]
            q, z = proj_cam(i, X, p)
            if z.min() < 0.1: r += [1e3] * (len(uv) + 1 if art == "linie" else 2); info.append((nr, art, n, 999.0)); continue
            sig_px = np.sqrt((spx * k.fak) ** 2 + (sig * f / z.mean()) ** 2)
            if art == "punkt":
                d = uv[0] - q[0]; r += list(d / sig_px); info.append((nr, art, n, float(np.linalg.norm(d) / k.fak)))
            else:
                v = q[1] - q[0]; nv = np.array([-v[1], v[0]]) / np.linalg.norm(v); d = (uv - q[0]) @ nv; r += list(d / sig_px)
                info.append((nr, art, n, float(np.sqrt(np.mean(d ** 2)) / k.fak)))
                dimg = uv[-1] - uv[0]; cosw = (dimg @ (q[0] - q[1])) / (np.linalg.norm(dimg) * np.linalg.norm(v) + 1e-9); r.append((1.0 - cosw) / 0.1)
        return (np.array(r), info) if roh else np.array(r)
    n_ank = len(anker_res(p0))
    def resid(p):
        X = p[7 * nC:].reshape(-1, 3); r = np.empty(2 * len(obs_uv))
        for i in range(nC):
            m = obs_c == i; q, z = proj_cam(i, X[obs_p[m]], p); d = (q - obs_uv[m]) / a.spur_sigma
            d[z < 0.05] = 50.0; r[np.flatnonzero(m) * 2] = d[:, 0]; r[np.flatnonzero(m) * 2 + 1] = d[:, 1]
        parts = [r, anker_res(p)]
        pr = np.array([(p[7 * ci[nr] + 6] - fp) / (a.prior_sigma * fp) for nr, fp in prior_f.items()]); parts.append(pr)
        if prior_h:
            h = []
            for nr in prior_h[2]:
                i = ci[nr]; Rc = SA.rot(p[7 * i:7 * i + 3]); c = -Rc.T @ p[7 * i + 3:7 * i + 6]; h.append((c[2] - prior_h[0]) / prior_h[1])
            parts.append(np.array(h))
        return np.concatenate(parts)
    # Jacobi-Struktur
    nres = len(resid(p0)); J = lil_matrix((nres, len(p0)), dtype=np.int8)
    for o in range(len(obs_uv)):
        i, j = obs_c[o], obs_p[o]; J[2 * o:2 * o + 2, 7 * i:7 * i + 7] = 1; J[2 * o:2 * o + 2, 7 * nC + 3 * j:7 * nC + 3 * j + 3] = 1
    r0 = 2 * len(obs_uv); J[r0:r0 + n_ank, :7 * nC] = 1; r0 += n_ank
    for m, nr in enumerate(prior_f): J[r0 + m, 7 * ci[nr] + 6] = 1
    r0 += len(prior_f)
    if prior_h:
        for m, nr in enumerate(prior_h[2]): J[r0 + m, 7 * ci[nr]:7 * ci[nr] + 7] = 1
    # Gewichte der Spurpunkte robust (soft_l1 wirkt auf alle Residuen - Anker sind wenige, deshalb Spur-Sigma 1 px vs Anker 3 px ok)
    t0 = time.time(); r_start = resid(p0); ank0, info0 = anker_res(p0, roh=True)
    print(f"Start: Spur-RMS {np.sqrt(np.mean(r_start[:2 * len(obs_uv)] ** 2)) * a.spur_sigma:.2f} px, Anker-Kosten {0.5 * np.sum(ank0 ** 2):.1f}")
    sol = least_squares(resid, p0, jac_sparsity=J, method="trf", loss="soft_l1", f_scale=2.0, x_scale="jac", max_nfev=200, verbose=0)
    p = sol.x; rr = resid(p); ank, info = anker_res(p, roh=True)
    print(f"Ausgleich {time.time() - t0:.0f} s, {sol.nfev} Auswertungen: Spur-RMS {np.sqrt(np.mean(rr[:2 * len(obs_uv)] ** 2)) * a.spur_sigma:.2f} px, Anker-Kosten {0.5 * np.sum(ank ** 2):.1f}")
    print("Anker-Residuen (px Original):", ", ".join(f"{nr}/{n}:{v:.0f}" for nr, art, n, v in info))
    # Kameras im Modellrahmen -> Kam-Objekte
    kams_m = {}
    for nr, i in ci.items():
        km = SA.Kam.__new__(SA.Kam); km.__dict__.update(kams[nr].__dict__); km.R = SA.rot(p[7 * i:7 * i + 3]); km.t = p[7 * i + 3:7 * i + 6].copy(); km.fx = km.fy = float(p[7 * i + 6]); kams_m[nr] = km
    print("\nKameras (Standort m | Abstand | f original px | f/Prior):"); hz = []
    for nr in nrs:
        c = kams_m[nr].zentrum(); hz.append(c[2]); fp = prior_f.get(nr); fo = kams_m[nr].fx / kams_m[nr].fak
        print(f"   {nr}: {c.round(1).tolist()} | {np.hypot(c[0], c[1]):5.1f} m | f={fo:.0f} px | {('%.3f' % (kams_m[nr].fx / fp)) if fp else '-'}  (Start f={kams[nr].fx / kams[nr].fak:.0f})")
    hz = np.array(hz); print(f"   Kamerahoehen: Median {np.median(hz):.1f} m, {np.sum((hz > -1) & (hz < 6))} von {len(hz)} zwischen -1 und 6 m")
    P = p[7 * nC:].reshape(-1, 3); rxy = np.hypot(P[:, 0], P[:, 1]); kern = P[(rxy < 9.0) & (np.abs(P[:, 2]) < 120)]
    print(f"\nWolke: z {np.percentile(P[:, 2], 1):.1f}..{np.percentile(P[:, 2], 99.9):.1f} m; Kern {len(kern)} Punkte, hoechster {kern[:, 2].max():.1f} m")
    for z0 in range(-2, 62, 6):
        k = (kern[:, 2] >= z0) & (kern[:, 2] < z0 + 6)
        if k.sum() > 15: q = kern[k]; print(f"   z {z0:3d}..{z0 + 6:3d} m: {k.sum():4d} Pkt, x {np.percentile(q[:, 0], 2):6.1f}..{np.percentile(q[:, 0], 98):5.1f}  y {np.percentile(q[:, 1], 2):6.1f}..{np.percentile(q[:, 1], 98):5.1f}")
    print("\nTriangulierte Picks (Modellsystem, Meter):"); tri = {}; sammel = {}
    for nr, K in Ks.items():
        for n, uv in K.get("punkte", {}).items():
            if n.startswith("ecke_boden"): continue
            sammel.setdefault(n, []).append((kams_m[nr], kams[nr].bild(uv), nr))
    for n, lst in sorted(sammel.items()):
        if len(lst) < 2: continue
        X, sx, px = SA.triangulieren(kams_m, [(k, uv) for k, uv, _ in lst]); start = A.get(n, {}).get("xyz", [None] * 3)
        tri[n] = dict(xyz=X.round(2).tolist(), sigma=sx.round(2).tolist(), fotos=[f for _, _, f in lst], residuen_px=[round(v, 1) for v in px], anker_start=start)
        print(f"   {n:16s} x {X[0]:6.2f} y {X[1]:6.2f} z {X[2]:6.2f} +- {sx[2]:.2f} m  (Fotos {[f for _, _, f in lst]}, Residuen {[round(v) for v in px]} px; Anker-Start z {start[2]})")
    out = dict(sparse=a.sparse, methode="buendel_anker", fotos_sfm=nrs, fotos_mit_picks=sorted(Ks),
               transformation=dict(beschreibung="kein Aehnlichkeits-Nachlauf: Kameras/Punkte/Brennweiten direkt im Modellsystem ausgeglichen (Anker in der Ausgleichung)", s_sigma_prozent=float("nan"), t_sigma_m=[float("nan")] * 3,
                                   start_aehnlichkeit=dict(s=s, kosten=float(best.cost))),
               ausgleich=dict(spur_rms_px=float(np.sqrt(np.mean(rr[:2 * len(obs_uv)] ** 2)) * a.spur_sigma), anker_kosten=float(0.5 * np.sum(ank ** 2)), anker_kosten_start=float(0.5 * np.sum(ank0 ** 2)), n_spur=int(len(obs_uv)), nfev=int(sol.nfev),
                              prior_f=prior_f, prior_sigma_rel=a.prior_sigma),
               beobachtungen=[dict(foto=nr, art=art, name=n, residuum_px=round(v, 1)) for nr, art, n, v in info],
               kameras={nr: dict(standort=kams_m[nr].zentrum().round(2).tolist(), f_px_original=float(kams_m[nr].fx / kams_m[nr].fak), fak=kams_m[nr].fak, R=kams_m[nr].R.tolist(), t=kams_m[nr].t.tolist(),
                                 cx=kams_m[nr].cx, cy=kams_m[nr].cy, k=list(map(float, kams_m[nr].k)), f_start_original=float(kams[nr].fx / kams[nr].fak)) for nr in nrs},
               kamerahoehen=dict(median=float(np.median(hz)), auf_strassenniveau=int(np.sum((hz > -1) & (hz < 6))), n=len(hz)),
               wolke=dict(n=len(P), kern_n=len(kern), kern_zmax=float(kern[:, 2].max())), trianguliert=tri,
               annahmen=(dict(kamerahoehe=dict(h0=prior_h[0], sigma=prior_h[1], kameras=prior_h[2])) if prior_h else {}))
    if a.schreiben:
        pth = os.path.join(od, "messprotokoll", f"SFM-AUSRICHTUNG-{a.name}.json"); json.dump(out, open(pth, "w"), indent=1, ensure_ascii=False); print("\ngeschrieben:", pth)
        np.save(os.path.join(od, "sfm", f"punkte_modell_{a.name}.npy"), P); print("geschrieben:", os.path.join(od, "sfm", f"punkte_modell_{a.name}.npy"))

if __name__ == "__main__":
    main()
