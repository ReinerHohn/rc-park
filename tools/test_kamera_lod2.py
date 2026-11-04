#!/usr/bin/env python3
"""test_kamera_lod2.py - BEWEIS (synthetisch, bekannte Wahrheit) fuer kamera_lod2_nachfuehren.py. Generisch: jedes Objekt mit LoD2 und einer K-Kamerapose.
Bild = LoD2-Szene (Maleralgorithmus, Flaechen nach Normale schattiert) + Stoerkanten (Fenster in Waenden, Pflasterlinien, Zufallslinien, Rauschen) wie in
vollen Strassenfotos. Pruefungen je Stoerung (Drehung Grad, Brennweite %, Lage m):
  T1 wahre Kamera -> Tor bestanden;  T2 gestoerte Kamera -> Tor durchgefallen;  T3 Nachfuehrung aus der Stoerung -> Bildfehler p90 der LoD2-Kanten <= 0,4 % der langen Seite (Pose allein ist bei einer Wand mehrdeutig),
  UND Tor bestanden; T4 das Tor nimmt nie eine Kamera mit groesserem Bildfehler an (FALSCH_ANGENOMMEN).
  /media/oem/scan/venv-seg/bin/python -W ignore -I tools/test_kamera_lod2.py modelle/<objekt>/objekt.json --foto 018 [--seeds 0 1] [--stl ...]
Ergebnis: audit/test_kamera_lod2.json + audit/test_kamera_lod2_<foto>.jpg (Bild mit wahren Kanten); Exit 0 nur wenn alle Pflichtfaelle bestehen.
"""
import sys, os, json, glob, argparse, types, numpy as np, cv2, trimesh
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kamera_lod2_nachfuehren as KL


def bild_rendern(polys, K, W, H, rng):
    R, _ = cv2.Rodrigues(np.array(K["rvec"], float)); t = np.array(K["t"], float); f, cx, cy = K["f_px"], K["cx"], K["cy"]
    img = np.full((H, W), 175, np.float32); img[: H // 3] = 205                                         # Himmel heller
    gy = np.linspace(0, 1, H)[:, None]; img[H // 2:] = 120 + 20 * gy[H // 2:]                              # Boden
    for _ in range(int(W / 6)):                                                                           # Pflaster/Zufallslinien unten
        y = int(rng.uniform(H * 0.55, H)); x = int(rng.uniform(0, W)); L_ = int(rng.uniform(20, 120)); a = rng.uniform(-0.3, 0.3)
        cv2.line(img, (x, y), (int(x + L_ * np.cos(a)), int(y + L_ * np.sin(a))), float(rng.uniform(80, 160)), 1)
    tief = []
    for typ, Q, _ in polys:
        Xc = Q @ R.T + t
        if (Xc[:, 2] < 1).any(): continue
        uv = np.c_[f * Xc[:, 0] / Xc[:, 2] + cx, f * Xc[:, 1] / Xc[:, 2] + cy]
        n = np.cross(Q[1] - Q[0], Q[2] - Q[0]); n /= max(np.linalg.norm(n), 1e-9)
        tief.append((float(Xc[:, 2].mean()), uv, n, typ, Q))
    for z, uv, n, typ, Q in sorted(tief, key=lambda x: -x[0]):
        g = rng.uniform(70, 210) * (0.65 + 0.35 * abs(n @ np.array([0.4, -0.5, 0.75])))   # eigene Albedo je Flaeche (vorher nur Schattierung: Wandfuss = Bodengrau, Nachbarwand gleich hell -> Kante ohne Kontrast, Diagnose 2026-11-04)
        cv2.fillPoly(img, [np.round(uv * 4).astype(np.int32)], float(g), lineType=cv2.LINE_AA, shift=2)
        if typ == "WallSurface" and abs(n[2]) < 0.3 and len(uv) >= 3:                                    # Fenster als Stoerkanten IN der Wand (~15 % Flaeche, auf die Wand beschnitten)
            maske = np.zeros(img.shape, np.uint8); cv2.fillPoly(maske, [np.round(uv).astype(np.int32)], 1); A = float(maske.sum())
            if A > 2000:
                lo, hi = uv.min(0), uv.max(0); a_ = hi - lo; fen = img.copy(); flaeche = 0.0
                while flaeche < 0.15 * A:
                    p = lo + rng.random(2) * a_; s_ = np.array([rng.uniform(0.01, 0.025), rng.uniform(0.02, 0.04)]) * max(a_)
                    cv2.rectangle(fen, tuple((p - s_).astype(int)), tuple((p + s_).astype(int)), float(g - rng.uniform(30, 60)), -1); flaeche += 4 * s_[0] * s_[1]
                img = np.where(maske > 0, fen, img)
    img += rng.normal(0, 5, img.shape); img = cv2.GaussianBlur(img, (0, 0), 0.8)
    return cv2.cvtColor(np.clip(img, 0, 255).astype(np.uint8), cv2.COLOR_GRAY2BGR)


def stoeren(K, dreh, df, dl, rng):
    R, _ = cv2.Rodrigues(np.array(K["rvec"], float)); ax = rng.normal(size=3); ax /= np.linalg.norm(ax)
    dR, _ = cv2.Rodrigues(ax * np.radians(dreh)); Rn = dR @ R; C = -R.T @ np.array(K["t"], float); d = rng.normal(size=3); d[2] *= 0.3; d /= np.linalg.norm(d); Cn = C + d * dl
    return dict(K, rvec=cv2.Rodrigues(Rn)[0].ravel().tolist(), t=(-Rn @ Cn).tolist(), f_px=K["f_px"] * (1 + df))


def bildabw(Ka, Kb, Pk, sel):
    """Bildabstand (px) der sichtbaren LoD2-Kantenpunkte unter Kamera a gegen Kamera b: Median, 90. Perzentil."""
    ua, _ = KL.projiziere(Pk[sel, :3], Ka["rvec"], np.array(Ka["t"]), Ka["f_px"], 0.0, Ka["cx"], Ka["cy"]); ub, _ = KL.projiziere(Pk[sel, :3], Kb["rvec"], np.array(Kb["t"]), Kb["f_px"], 0.0, Kb["cx"], Kb["cy"])
    d = np.linalg.norm(ua - ub, axis=1); return float(np.median(d)), float(np.percentile(d, 90))


def fehler(Ka, Kb):
    Ra, _ = cv2.Rodrigues(np.array(Ka["rvec"], float)); Rb, _ = cv2.Rodrigues(np.array(Kb["rvec"], float))
    dr = float(np.degrees(np.arccos(np.clip((np.trace(Ra @ Rb.T) - 1) / 2, -1, 1)))); Ca = -Ra.T @ np.array(Ka["t"]); Cb = -Rb.T @ np.array(Kb["t"])
    return dr, abs(Ka["f_px"] / Kb["f_px"] - 1), float(np.linalg.norm(Ca - Cb))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--foto", required=True); ap.add_argument("--stl"); ap.add_argument("--seeds", type=int, nargs="*", default=[0, 1])
    ap.add_argument("--stoerungen", default="0.5,0.03,0.3;1,0.05,0.5;2,0.1,1;4,0.15,2", help="Drehung Grad, Brennweite rel., Lage m; Faelle mit ;"); a = ap.parse_args()
    objp = os.path.abspath(a.objekt); obj = json.load(open(objp)); od = os.path.dirname(objp); root = os.path.dirname(os.path.dirname(od))
    K = json.load(open(os.path.join(od, "messprotokoll", f"K-{a.foto}.json"))); K = K.get("kamera_vor_lod2") or K["kamera"]
    m = trimesh.load(a.stl or os.path.join(root, obj["stl"])); m.apply_scale(obj.get("stl_massstab", 87) / 1000.0)
    c = m.bounds.mean(0) if obj.get("zentrierung", "huelle") == "huelle" else np.zeros(3)                    # gleicher Werkzeugrahmen wie kamera_lod2_nachfuehren.py
    T_ = np.array(K.get("rahmen_verschiebung", [-c[0], -c[1], -m.bounds[0, 2]]), float)
    polys = KL.lod2_szene(obj, od, 70.0, T_); Pk = KL.kanten(polys, 0.1); mesh = KL.flaechen_netz(polys)
    W, H = K["bild"]; s = min(1.0, 1400 / max(W, H)); W, H = int(W * s), int(H * s)
    Ks = dict(K, f_px=K["f_px"] * s, cx=K.get("cx", K["bild"][0] / 2) * s, cy=K.get("cy", K["bild"][1] / 2) * s, k1=0.0, bild=[W, H])
    opt = types.SimpleNamespace(px=1400, tol=0.005, kappe=0.03, sigma_dreh=3.0, sigma_lage=2.0, sigma_f=0.15, min_treffer=0.4, min_kontrast=0.15)
    faelle = [tuple(float(x) for x in c.split(",")) for c in a.stoerungen.split(";")]; erg = []; alle_ok = True
    for seed in a.seeds:
        rng = np.random.default_rng(seed); im = bild_rendern(polys, Ks, W, H, rng); sel_w = KL.sichtbar(Pk, mesh, Ks["rvec"], Ks["t"], Ks["f_px"], 0.0, Ks["cx"], Ks["cy"], W, H)
        if seed == a.seeds[0]: cv2.imwrite(os.path.join(od, "audit", f"test_kamera_lod2_{a.foto}.jpg"), im)
        r1, _, _ = KL.nachfuehren(dict(Ks, rvec=Ks["rvec"]), im, Pk, mesh, types.SimpleNamespace(**{**vars(opt), "sigma_dreh": 1e-3, "sigma_lage": 1e-3, "sigma_f": 1e-4}))
        e = dict(seed=seed, fall="wahr", tor=r1.get("ok"), treffer=r1.get("treffer"), zufall=r1.get("zufall")); erg.append(e); print(e, flush=True); alle_ok &= bool(r1.get("ok"))
        for (dr, df, dl) in faelle:
            Kg = stoeren(Ks, dr, df, dl, rng)
            r2, _, _ = KL.nachfuehren(Kg, im, Pk, mesh, types.SimpleNamespace(**{**vars(opt), "sigma_dreh": 1e-3, "sigma_lage": 1e-3, "sigma_f": 1e-4}))
            r3, Kn, _ = KL.nachfuehren(Kg, im, Pk, mesh, opt)
            fr, ff, fl = fehler(Kn, Ks) if Kn else (np.nan, np.nan, np.nan)
            pa, p90 = bildabw(Kn, Ks, Pk, sel_w) if Kn else (np.inf, np.inf)
            zur = bool(Kn) and p90 <= 0.004 * max(W, H) and r3.get("ok")                                 # BILDfehler entscheidet (Wand allein: Drehung/Lage tauschbar, gleiches Bild)
            e = dict(seed=seed, stoerung=[dr, df, dl], T2_tor_gestoert=r2.get("ok"), T3_zurueck=zur, bild_median_px=round(pa, 2), bild_p90_px=round(p90, 2), grenze_p90_px=round(0.004 * max(W, H), 1),
                     rest_dreh_grad=round(fr, 3), rest_f=round(ff, 4), rest_lage_m=round(fl, 3), tor_nachher=r3.get("ok"))
            if r3.get("ok") and not zur: alle_ok = False; e["FALSCH_ANGENOMMEN"] = True                     # Tor nimmt falsche Kamera an = schlimmster Fall, immer Pflicht
            erg.append(e); print(e, flush=True)
            if dr <= 1.0: alle_ok &= (not r2.get("ok")) and zur                                           # Pflicht: kleine Stoerungen zurueckholen
    json.dump(dict(foto=a.foto, bestanden=alle_ok, faelle=erg, pflicht="wahr besteht; Stoerung <= 1 Grad/5 %/0,5 m faellt vorher durch und wird zurueckgeholt (Bild-p90 <= 0,4 % der langen Seite); Tor darf NIE eine falsche Kamera annehmen"), open(os.path.join(od, "audit", "test_kamera_lod2.json"), "w"), indent=1)
    print("BEWEIS kamera_lod2:", "BESTANDEN" if alle_ok else "NICHT BESTANDEN"); sys.exit(0 if alle_ok else 1)


if __name__ == "__main__":
    main()
