#!/usr/bin/env python3
"""kanten_feld3d_pruefen.py - S10 Teil B Bewertung (2)+(3): Holdout-Kreuzansicht des 3D-Kantenfelds und Bogen-Test.

Holdout-Fotos gehen NICHT in das Feld ein (kanten_feld3d.py --ohne-fotos). Hier: Feldpunkte in das Holdout-Foto projizieren (Sichtbarkeit nur ueber dessen Tiefenkarte),
gegen dessen weiche Kantenkarte (Mittel der Pipelines >= 0,5, Skelett) messen:
  Praezision      = Anteil projizierter Feldpixel <= TOL px von einem Karten-Skelettpixel
  Vollstaendigkeit= Anteil Karten-Skelettpixel im Bewertungsbereich <= TOL px von einem Feldpixel
  kosten_lr       = foto_diff._kosten_param_lr (gleiche Formel wie die STL-Bewertung; Kantenbild hier = Karten-Skelett, Bereich = Wolkenschale projiziert; NICHT direkt mit den
                    STL-Werten (Mittel Carving -0,0083) vergleichbar, daher Kontrollen: um 0,5 m versetztes Feld, Zufallsrichtung)
Bogen-Test: Kreisboegen aus kanten_kurven.json gegen die erwarteten Arkadenboegen (Mitte u/Radius/Scheitel/Wandnormale), plus Flaechenbild der Feldpunkte nahe der Fassadenebene.
Aufruf: kanten_feld3d_pruefen.py --dicht D --karten K --feld FELDDIR --fotos 001,024 [--fassade ELEMENTE.json f02 --bogen-u -6.6 -2.3 1.85 6.2 --bogen-scheitel 4.4]
"""
import os, sys, json, argparse
import numpy as np, cv2, torch
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import kanten_feld3d as KF
TOL = 3.0; KAP = 8.0


def projiziere(P, cam, D):
    Km, R, t, C, W, H = cam; Pc = P @ R.T + t; z = Pc[:, 2]; ok = z > 0.5
    u = Pc[:, 0] / np.maximum(z, 1e-3) * Km[0, 0] + Km[0, 2]; v = Pc[:, 1] / np.maximum(z, 1e-3) * Km[1, 1] + Km[1, 2]
    ok &= (u >= 0) & (u < W - 1) & (v >= 0) & (v < H - 1); ui = np.clip(np.round(u).astype(int), 0, W - 1); vi = np.clip(np.round(v).astype(int), 0, H - 1)
    if D is not None: dm = D[vi, ui]; ok &= (dm > 0) & (z <= dm + KF.TAU_ABS + KF.TAU_REL * z)
    return ui[ok], vi[ok]


def dmin(D):
    D = np.where(D > 0, D, np.inf).astype(np.float32); m = -cv2.dilate(-np.where(np.isinf(D), -1e9, -D), np.ones((3, 3), np.uint8)) if False else None
    Dt = torch.tensor(D)[None, None]; r = -torch.nn.functional.max_pool2d(-Dt, 3, 1, 1)[0, 0].numpy(); r[np.isinf(r)] = 0; return r


def main():
    from skimage.morphology import skeletonize
    import foto_diff as FD, freiraum_pruefen as FP
    ap = argparse.ArgumentParser(); ap.add_argument("--dicht", required=True); ap.add_argument("--karten", required=True); ap.add_argument("--feld", required=True); ap.add_argument("--fotos", required=True)
    ap.add_argument("--datei", default="feld_punkte.npz"); ap.add_argument("--pipelines", default="p1,p2,p3,p4"); ap.add_argument("--fassade", nargs=2, metavar=("ELEMENTE_JSON", "ID")); ap.add_argument("--bogen-u", nargs="*", type=float, default=[]); ap.add_argument("--bogen-scheitel", type=float)
    a = ap.parse_args(); K = json.load(open(os.path.join(a.dicht, "kameras_unverzerrt.json"))); d = np.load(os.path.join(a.feld, a.datei)); P = d["P"].astype(np.float64); rng = np.random.default_rng(0)
    X = FP.ply_lesen(os.path.join(a.dicht, "fused.ply")); X = X[(X > P.min(0) - 1).all(1) & (X < P.max(0) + 1).all(1)]
    erg = {}; pipes = a.pipelines.split(",")
    for nr in a.fotos.split(","):
        cam = KF.kamera(K[nr]) + ((K[nr]["W"], K[nr]["H"]),); cam = (cam[0], cam[1], cam[2], cam[3], K[nr]["W"], K[nr]["H"]); W, H = cam[4], cam[5]
        D = dmin(KF.depth_lesen(os.path.join(a.dicht, "stereo", "depth_maps", f"{K[nr]['bild']}.geometric.bin")))
        kart = np.mean([cv2.imread(os.path.join(a.karten, p, f"{nr}.png"), 0).astype(np.float32) for p in pipes], 0) / 255.0
        # Bewertungsbereich: Wolke projiziert, geschlossen (unabhaengig vom Feld)
        ux, vx = projiziere(X, cam, D); M = np.zeros((H, W), np.uint8); M[vx, ux] = 1; M = cv2.morphologyEx(cv2.dilate(M, np.ones((9, 9), np.uint8)), cv2.MORPH_CLOSE, np.ones((25, 25), np.uint8)) > 0
        fk = skeletonize(kart >= 0.5) & M
        def maske(Q):
            ui, vi = projiziere(Q, cam, D); m = np.zeros((H, W), bool); m[vi, ui] = True; return cv2.dilate(m.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0
        mk = maske(P); r = dict(n_feldpixel=int(mk.sum()), n_karte_skelett=int(fk.sum()), bereich_px=int(M.sum()))
        dF = cv2.distanceTransform((~fk).astype(np.uint8), cv2.DIST_L2, 5); dM = cv2.distanceTransform((~mk).astype(np.uint8), cv2.DIST_L2, 5)
        r["praezision"] = round(float((dF[mk] <= TOL).mean()), 3) if mk.any() else None; r["vollstaendigkeit"] = round(float((dM[fk] <= TOL).mean()), 3) if fk.any() else None
        kp, lr = FD._kosten_param_lr(mk & M, fk, M, KAP); r["kosten_lr"] = lr
        for nm, Q in (("versatz_0.5m", P + 0.5 * rng.normal(size=(1, 3)) / 1.0), ("zufall_0.5m", P + rng.normal(0, 0.5, P.shape))):
            m2 = maske(Q); k2, l2 = FD._kosten_param_lr(m2 & M, fk, M, KAP); r["lr_" + nm] = l2; r["praez_" + nm] = round(float((dF[m2] <= TOL).mean()), 3) if m2.any() else None
        erg[nr] = r; print(nr, r, flush=True)
        img = cv2.imread(os.path.join(a.dicht, "images", K[nr]["bild"])); ov = (img * 0.55).astype(np.uint8); ov[cv2.dilate(fk.astype(np.uint8), np.ones((2, 2), np.uint8)) > 0] = (0, 255, 255); ov[mk] = (0, 0, 255)
        cv2.imwrite(os.path.join(a.feld, f"holdout_{nr}" + ("" if a.datei == "feld_punkte.npz" else "_" + a.datei[12:-4]) + ".jpg"), ov, [cv2.IMWRITE_JPEG_QUALITY, 90])
    mean = lambda k: round(float(np.mean([v[k] for v in erg.values() if v.get(k) is not None])), 5)
    erg["mittel"] = {k: mean(k) for k in ("praezision", "vollstaendigkeit", "kosten_lr", "lr_versatz_0.5m", "lr_zufall_0.5m", "praez_versatz_0.5m", "praez_zufall_0.5m")}; print("MITTEL", erg["mittel"])
    json.dump(erg, open(os.path.join(a.feld, "holdout_ergebnis" + ("" if a.datei == "feld_punkte.npz" else "_" + a.datei[12:-4]) + ".json"), "w"), indent=1)
    if a.fassade:                                                                                    # Bogentest
        F = json.load(open(a.fassade[0]))["fassaden"][a.fassade[1]]; o = np.array(F["o"]); dv = np.array(F["d"]); nv = np.array(F["n"])
        uz = lambda Q: np.c_[(Q[:, :2] - o) @ dv, Q[:, 2], (Q[:, :2] - o) @ nv]
        B = json.load(open(os.path.join(a.feld, "kanten_kurven.json")))["boegen"]; rows = []
        for b in B:
            m = np.array(b["mitte"]); mu = uz(m[None])[0]; n3 = np.array(b["normale"]); wn = abs(n3[:2] @ nv) / max(1e-9, np.hypot(*n3[:2])) if np.hypot(*n3[:2]) > 1e-6 else 0
            ph = np.radians(b["winkel_von"] + np.linspace(0, b["winkel_umfang"], 60)); pts = m + b["radius_m"] * (np.cos(ph)[:, None] * np.array(b["e1"]) + np.sin(ph)[:, None] * np.array(b["e2"]))
            q = uz(pts); rows.append(dict(u=round(float(mu[0]), 2), z=round(float(mu[1]), 2), t=round(float(mu[2]), 2), r=b["radius_m"], scheitel_z=round(float(q[:, 1].max()), 2), umfang=b["winkel_umfang"],
                                         n_punkte=b["n"], wandnormal=round(float(abs(n3 @ np.r_[nv, 0])), 2)))
        t_ = [r for r in rows if r["wandnormal"] > 0.9 and 1.2 < r["r"] < 6]
        treffer = []
        for ub in a.bogen_u:
            hit = [r for r in t_ if abs(r["u"] - ub) < 0.8 and (a.bogen_scheitel is None or abs(r["scheitel_z"] - a.bogen_scheitel) < 0.6)]; treffer.append(dict(u_erwartet=ub, gefunden=bool(hit), kandidaten=hit))
        json.dump(dict(boegen_alle_fassadenparallel=t_, treffer=treffer, n_boegen_gesamt=len(B)), open(os.path.join(a.feld, "bogentest.json"), "w"), indent=1); print("BOGENTEST", [(t["u_erwartet"], t["gefunden"]) for t in treffer], "fassadenparallele Boegen", len(t_), "von", len(B))
        S = uz(P); m = (np.abs(S[:, 2]) < 1.0); S = S[m]; sc = 60; u0, u1, z0, z1 = -12, 12, 0, 9; im = np.zeros(((z1 - z0) * sc, (u1 - u0) * sc, 3), np.uint8)
        for u, z, t in S:
            x = int((u - u0) * sc); y = int((z1 - z) * sc)
            if 0 <= x < im.shape[1] and 0 <= y < im.shape[0]: cv2.circle(im, (x, y), 1, (255, 255, 255), -1)
        for ub in a.bogen_u:
            if a.bogen_scheitel: cv2.ellipse(im, (int((ub - u0) * sc), int((z1 - (a.bogen_scheitel - 1.6)) * sc)), (int(2.1 * sc), int(1.6 * sc)), 0, 180, 360, (0, 200, 0), 1)
        cv2.imwrite(os.path.join(a.feld, "fassade_kantenfeld.png"), im)


if __name__ == "__main__": main()
