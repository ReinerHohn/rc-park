#!/usr/bin/env python3
"""dach_params_ndom.py — Dach-FORM-Parameter direkt aus dem LASER (nDOM = DOM1-DGM1) messen:
First-Höhe, Trauf-Höhe (Dach-Unterkante am Gebäuderand), First-LÄNGE (→ Walm-Inset/Spitzigkeit).
Das ist die BESTE Datenquelle fürs Dach. Schreibt roof_params.json für das Massing.

Lauf: /tmp/ml/bin/python tools/dach_params_ndom.py --name hofgut_sternen
"""
import argparse, json, os
import numpy as np
import cv2

DOM = "daten/ravenna/dom1/dom1_32_429_5306_2_bw/dom1_32_430_5307_1_bw_2017.tif"
DGM = "daten/ravenna/dgm1_32_429_5306_2_bw/dgm1_32_430_5307_1_bw_2017.xyz"


def grid(xyz, E0, N0, n):
    d = np.loadtxt(xyz); G = np.full((n, n), np.nan, np.float32)
    c = np.round(d[:, 0] - 0.5 - E0).astype(int); r = np.round(N0 - 0.5 - d[:, 1]).astype(int)
    ok = (c >= 0) & (c < n) & (r >= 0) & (r < n); G[r[ok], c[ok]] = d[ok, 2]
    return G


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--name", required=True); a = ap.parse_args()
    md = f"modelle/{a.name}"
    tfw = open(os.path.splitext(DOM)[0] + ".tfw").read().split()
    px, _, _, py, oxc, oyc = [float(x) for x in tfw]; E0, N0 = oxc - px / 2, oyc - py / 2
    D = cv2.imread(DOM, cv2.IMREAD_UNCHANGED).astype(np.float32); n = D.shape[0]
    nd = cv2.medianBlur((D - grid(DGM, E0, N0, n)).astype(np.float32), 3)

    fp = json.load(open(f"{md}/footprint.json")); o = np.array(fp["origin_utm"][:2])
    mask = np.zeros((n, n), np.uint8)
    for t in fp["teile"]:
        if cv2.contourArea(np.array(t["ring_xy_m"], np.float32)) <= 40:
            continue                                        # nur Hauptkörper (wie Massing)
        ring = np.array(t["ring_xy_m"]) + o
        c = np.round(ring[:, 0] - 0.5 - E0).astype(np.int32); r = np.round(N0 - 0.5 - ring[:, 1]).astype(np.int32)
        cv2.fillPoly(mask, [np.c_[c, r]], 1)
    mb = mask > 0
    H = np.where(mb & np.isfinite(nd), nd, np.nan)

    ridge_z = float(np.nanpercentile(H, 98))
    # Trauf-Höhe = Dach-Unterkante am Rand: nDOM auf dem Footprint-RAND (erodiert-subtrahiert)
    rand = (mb & ~(cv2.erode(mask, np.ones((3, 3), np.uint8)) > 0))
    eave_z = float(np.nanpercentile(H[rand], 55)) if rand.any() else ridge_z * 0.55
    # First-LÄNGE: Zellen nahe First → Ausdehnung entlang Hauptachse / Gebäudelänge
    ridge_cells = mb & (H > ridge_z - 1.5)
    ys, xs = np.where(ridge_cells); ay, ax = np.where(mb)
    if len(xs) > 5:
        pts = np.c_[xs, ys].astype(float); c0 = pts.mean(0)
        u, s, vt = np.linalg.svd(pts - c0); axis = vt[0]
        proj = (pts - c0) @ axis; ridge_len = float(proj.max() - proj.min())
        bpts = np.c_[ax, ay].astype(float); bproj = (bpts - c0) @ axis
        build_len = float(bproj.max() - bproj.min())
        ridge_frac = np.clip(ridge_len / max(1, build_len), 0.05, 0.9)
    else:
        ridge_frac = 0.4
    inset_frac = float(np.clip((1 - ridge_frac) / 2, 0.1, 0.45))

    out = {"quelle": "Laser nDOM (DOM1-DGM1) — beste Dach-Datenquelle",
           "ridge_m": round(ridge_z, 2), "roof_eave_m": round(eave_z, 2),
           "ridge_laenge_frac": round(float(ridge_frac), 2), "inset_frac": round(inset_frac, 2),
           "neigung_hinweis": f"First {ridge_z:.1f} m, Dach-Unterkante {eave_z:.1f} m -> Dachhöhe {ridge_z-eave_z:.1f} m"}
    json.dump(out, open(f"{md}/roof_params.json", "w"), indent=1, ensure_ascii=False)
    print(json.dumps(out, indent=1, ensure_ascii=False))
    print(f"-> {md}/roof_params.json")


if __name__ == "__main__":
    main()
