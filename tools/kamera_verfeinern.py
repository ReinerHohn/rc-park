#!/usr/bin/env python3
"""kamera_verfeinern.py <objekt.json> <fassaden.json> <FOTO> [--gegen FOTO,FOTO,...] [--n 6] [--schreiben] - Kamera eines (nach)registrierten Fotos am MODELL nachziehen.

Warum (16.11.2026, Stufe `seiten`): ein automatisch geladenes Webfoto (Flickr ov_0005, zeigt die sonst ungesehene Ostseite) wurde vom SfM registriert, aber seine
SfM-Punkte liegen fast alle auf EINER Wand (Sued) -> Brennweite und Abstand sind schlecht bestimmt, auf der Ostwand lag die Projektion ~0,9 m daneben.
Automatik ohne Handpicks:
  1. Referenzfotos mit guter Kamera: --gegen oder die --n Kameras mit dem aehnlichsten Standort/Blick (K-Dateien).
  2. ALIKED + LightGlue zwischen dem Foto und jeder Referenz (GPU).
  3. Jeden Treffer der Referenz in 3D heben: Tiefenbild des MODELLS (STL) aus der Referenzkamera rendern (GPU), Tiefe am Treffer lesen (nicht an Tiefenkanten).
     So entstehen 2D-3D-Paare auf ALLEN Flaechen, die beide Fotos zeigen - auch auf der vom SfM ungesehenen Wand. (Erste Fassung schnitt mit den LoD2-Fassadenebenen:
     die liegen bis 0,75 m neben der echten Wand -> Ostpunkte fielen alle als Ausreisser heraus.)
  4. PnP mit RANSAC ueber mehrere Brennweiten, dann Feinausgleich (Drehung, Lage, Brennweite frei). Bericht: Inlier je Wand, Restfehler in px und m.
  --schreiben: K-<FOTO>.json 'kamera' ersetzen (alte bleibt als 'kamera_vorher'). Ohne Schalter nur Bericht.
Grenzen: so gut wie Modell und Referenzkamera; mindestens 2 Flaechenrichtungen mit je >= 15 Inliern,
sonst gilt die Kamera weiter als unsicher (rc 3).
"""
import sys, os, json, glob, argparse, numpy as np, cv2, torch, trimesh
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import render_kern as rk
from scipy.optimize import least_squares


def main():
    from lightglue import LightGlue, ALIKED
    from lightglue.utils import load_image, rbd
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("fassaden"); ap.add_argument("foto"); ap.add_argument("--gegen"); ap.add_argument("--n", type=int, default=6); ap.add_argument("--schreiben", action="store_true"); ap.add_argument("--stl", help="weitere STL (Nachbarobjekte im selben Rahmen), Komma-Liste"); a = ap.parse_args()
    od = os.path.dirname(os.path.abspath(a.objekt)); root = os.path.dirname(os.path.dirname(od)); obj = json.load(open(a.objekt)); fd = os.path.join(root, obj["fotos_dir"]); mp = os.path.join(od, "messprotokoll")
    ms = [trimesh.load(q_) for q_ in ([os.path.join(root, obj["stl"])] + (a.stl.split(",") if a.stl else []))]; mm = trimesh.util.concatenate(ms) if len(ms) > 1 else ms[0]; mm.apply_scale(float(obj.get("stl_massstab", 87)) / 1000.0)
    def kam(n):
        p = os.path.join(mp, "K-" + n + ".json")
        if not os.path.exists(p): return None
        k = json.load(open(p)).get("kamera"); return k if isinstance(k, dict) and "rvec" in k else None
    def pfad(n): g = glob.glob(os.path.join(fd, n + ".*")); return g[0] if g else None
    K0 = kam(a.foto); R0 = cv2.Rodrigues(np.array(K0["rvec"]))[0]; C0 = -R0.T @ np.array(K0["t"]); blick0 = R0[2]
    if a.gegen: refs = a.gegen.split(",")
    else:
        kand = []
        for p in glob.glob(os.path.join(mp, "K-*.json")):
            n = os.path.basename(p)[2:-5]; k = kam(n)
            if n == a.foto or k is None or not pfad(n): continue
            if n.startswith(("dl_", "neu__", "video")) and not k.get("vertrauen"): continue     # 16.11.2026: nur vertrauenswuerdige Referenzen (Buendelkameras eigener/Commons-Fotos oder schon nachgezogene) -
                                                                                               # sonst bestaetigt sich eine falsche Pose am eigenen Duplikat / an falsch verorteten Videobildern (ov_0005: 27 m vor dem Turm in der Luft)
            R = cv2.Rodrigues(np.array(k["rvec"]))[0]; C = -R.T @ np.array(k["t"]); kand.append((np.linalg.norm(C - C0) * (2.0 - float(R[2] @ blick0)), n))
        refs = [n for _, n in sorted(kand)[:a.n]]
    dev = "cuda"; ex = ALIKED(max_num_keypoints=4096).eval().to(dev); mt = LightGlue(features="aliked").eval().to(dev)
    def merk(n):
        im = load_image(pfad(n)); h, w = im.shape[1:]; s = min(1.0, 1600.0 / max(h, w)); f = ex.extract(im.to(dev), resize=int(max(h, w) * s)); return f, 1.0
    fA, _ = merk(a.foto); P2, P3, WN, RF = [], [], [], []
    for n in refs:
        k = kam(n)
        if k is None or not pfad(n): continue
        fB, _ = merk(n)
        with torch.no_grad(): m = rbd(mt({"image0": fA, "image1": fB}))["matches"].cpu().numpy()
        if len(m) < 20: print(f"  {n[-26:]}: {len(m)} Treffer"); continue
        xa = rbd(fA)["keypoints"].cpu().numpy()[m[:, 0]]; xb = rbd(fB)["keypoints"].cpu().numpy()[m[:, 1]]
        R = cv2.Rodrigues(np.array(k["rvec"]))[0]; C = -R.T @ np.array(k["t"]); x = (xb[:, 0] - k["cx"]) / k["f_px"]; y = (xb[:, 1] - k["cy"]) / k["f_px"]; k1 = float(k.get("k1") or 0); xu, yu = x.copy(), y.copy()
        for _ in range(4): q = 1 + k1 * (xu * xu + yu * yu); xu, yu = x / q, y / q
        D = np.stack([xu, yu, np.ones_like(xu)], 1) @ R                     # Weltstrahl je Treffer, Kamera-z-Anteil = 1
        hb, wb = int(round(2 * k["cy"])), int(round(2 * k["cx"])); sk = min(1.0, 1800.0 / max(hb, wb)); Wr, Hr = int(wb * sk), int(hb * sk)
        tiefe, fid = [np.asarray(v_) for v_ in rk.dreiecke_rastern(mm, R, np.array(k["t"]), k["f_px"] * sk, k["cx"] * sk, k["cy"] * sk, Wr, Hr)[:2]]      # Tiefenbild des MODELLS aus der Referenzkamera (GPU)
        ui = np.clip((xb[:, 0] * sk).astype(int), 0, Wr - 1); vi = np.clip((xb[:, 1] * sk).astype(int), 0, Hr - 1); best = tiefe[vi, ui].astype(np.float64); f_ = fid[vi, ui]; tr = f_ >= 0
        for du, dv in ((-2, 0), (2, 0), (0, -2), (0, 2)):                  # nicht an Tiefenkanten heben (Nachbarpixel muessen dieselbe Tiefe haben)
            tr &= np.abs(tiefe[np.clip(vi + dv, 0, Hr - 1), np.clip(ui + du, 0, Wr - 1)] - best) < 0.15
        nrm = mm.face_normals[np.where(tr, f_, 0)]; az = (np.round(np.degrees(np.arctan2(nrm[:, 1], nrm[:, 0])) / 90.0).astype(int) % 4); wand = np.where(tr, np.where(nrm[:, 2] > 0.5, 4, az), -1)   # Flaechenklasse: 4 Himmelsrichtungen, 4 = Dach
        ok = wand >= 0; X = C + best[ok, None] * D[ok]; P2.append(xa[ok]); P3.append(X); WN.append(wand[ok]); RF += [n] * int(ok.sum()); print(f"  {n[-26:]}: {len(m)} Treffer, {int(ok.sum())} auf dem Modell")
    if not P2: print("keine Paare"); return 2
    P2 = np.vstack(P2).astype(np.float64); P3 = np.vstack(P3).astype(np.float64); WN = np.concatenate(WN); im = cv2.imread(pfad(a.foto)); H, W = im.shape[:2]; cx, cy = W / 2, H / 2; best = None
    for f in np.geomspace(0.4 * max(W, H), 12 * max(W, H), 30):
        Km = np.array([[f, 0, cx], [0, f, cy], [0, 0, 1.0]]); ok, r, t, inl = cv2.solvePnPRansac(P3, P2, Km, None, reprojectionError=max(4.0, 0.004 * max(W, H)), iterationsCount=400, flags=cv2.SOLVEPNP_EPNP)
        if ok and inl is not None and (best is None or len(inl) > len(best[3])): best = (f, r, t, inl.ravel())
    if best is None or len(best[3]) < 30: print("PnP ohne tragfaehige Loesung"); return 3
    f, r, t, inl = best
    def res(p): pr, _ = cv2.projectPoints(P3[inl], p[:3], p[3:6], np.array([[p[6], 0, cx], [0, p[6], cy], [0, 0, 1.0]]), None); return (pr.reshape(-1, 2) - P2[inl]).ravel()
    s = least_squares(res, np.r_[r.ravel(), t.ravel(), f], loss="soft_l1", f_scale=3.0); p = s.x; err = np.sqrt((res(p) ** 2).reshape(-1, 2).sum(1)); R = cv2.Rodrigues(p[:3])[0]; C = -R.T @ p[3:6]; dist = float(np.median(np.linalg.norm(P3[inl] - C, axis=1)))
    je_wand = {int(w): int((WN[inl] == w).sum()) for w in np.unique(WN[inl])}; tragend = sum(1 for v in je_wand.values() if v >= 15)
    print(f"{a.foto}: {len(inl)} Inlier von {len(P2)}, je Wand {je_wand}, Rest Median {np.median(err):.1f} px = {np.median(err) * dist / p[6] * 100:.0f} cm an der Wand; f {K0['f_px']:.0f} -> {p[6]:.0f} px, Standort {np.round(C0, 1).tolist()} -> {np.round(C, 1).tolist()} ({np.linalg.norm(C - C0):.1f} m verschoben)")
    if tragend < 2: print("nur eine Wand mit >= 15 Inliern - Kamera bleibt unsicher, nicht geschrieben"); return 3
    if a.schreiben:
        kp = os.path.join(mp, "K-" + a.foto + ".json"); d = json.load(open(kp)); d["kamera_vorher"] = d["kamera"]
        d["kamera"] = dict(rvec=p[:3].tolist(), t=p[3:6].tolist(), f_px=float(p[6]), cx=cx, cy=cy, k1=0.0, standort=C.tolist(), quelle=f"kamera_verfeinern.py: {len(inl)} Inlier auf {tragend} Waenden gegen {sorted(set(RF))[:6]}, Rest {np.median(err):.1f} px", vertrauen=True, rest_px_median=float(np.median(err)), inlier_je_wand=je_wand)
        json.dump(d, open(kp, "w"), indent=1); print("geschrieben:", kp)
    return 0


if __name__ == "__main__":
    sys.exit(main())
