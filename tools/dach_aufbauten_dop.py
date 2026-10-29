#!/usr/bin/env python3
"""dach_aufbauten_dop.py — Gauben- & Kaminpositionen aus dem DOP-LUFTBILD (20 cm, schärfer als Laser)
messen und exakt auf die Fassade mappen. DOP = bestes Dach-PLAN. Transform DOP-px → UTM → Modell-Frame
(massing_frame) → Fassaden-x-Anteil. Schreibt dach_aufbauten.json {kamine_x_frac, gauben_x_frac}.

Lauf: /tmp/ml/bin/python tools/dach_aufbauten_dop.py --name hofgut_sternen
"""
import argparse, json, os
import numpy as np
import cv2

DOP = "daten/ravenna/dop/dop20rgb_32_429_5306_2_bw/dop20rgb_32_430_5307_1_bw_2025.tif"


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--name", required=True); a = ap.parse_args()
    md = f"modelle/{a.name}"
    tfw = open(os.path.splitext(DOP)[0] + ".tfw").read().split()
    px, _, _, py, oxc, oyc = [float(x) for x in tfw]; E0, N0 = oxc - px / 2, oyc + (-py) / 2  # py<0
    dop = cv2.imread(DOP)
    fr = json.load(open(f"{md}/massing_frame.json")); fp = json.load(open(f"{md}/footprint.json"))
    o = np.array(fp["origin_utm"][:2]); front = fr["front"]
    ang = -fr["rot_angle"]; Rm = np.array([[np.cos(ang), -np.sin(ang)], [np.sin(ang), np.cos(ang)]])
    ctr = np.array(fr["ctr"]); flip = fr["flip"]; shift = np.array(fr["shift"])
    fx0, fx1 = front["x0"], front["x1"]

    def dop_px_to_frac(c, r):
        E = E0 + c * px; N = N0 - r * (-py)                 # py negativ
        loc = np.array([E - o[0], N - o[1]]); p = (loc - ctr) @ Rm.T
        if flip:
            p = p * np.array([1.0, -1.0])
        p = p - shift
        return (p[0] - fx0) / (fx1 - fx0), p[1]             # x-Anteil + y (Tiefe)

    # Footprint-Maske im DOP (Hauptkörper) → Dachbereich
    mask = np.zeros(dop.shape[:2], np.uint8)
    for t in fp["teile"]:
        if cv2.contourArea(np.array(t["ring_xy_m"], np.float32)) <= 40:
            continue
        ring = np.array(t["ring_xy_m"]) + o
        c = np.round((ring[:, 0] - E0) / px).astype(np.int32); r = np.round((N0 - ring[:, 1]) / (-py)).astype(np.int32)
        cv2.fillPoly(mask, [np.c_[c, r]], 1)
    mb = mask > 0
    ys, xs = np.where(mb); y0, y1, x0b, x1b = ys.min(), ys.max(), xs.min(), xs.max()
    gray = cv2.cvtColor(dop, cv2.COLOR_BGR2GRAY); mpp = px  # 0.2 m/px

    # Aufbauten = HELLE Flecken auf dem (dunklen) Dach (Kaminköpfe, Velux/Gaubendächer)
    bright = ((gray > 150) & mb).astype(np.uint8)
    bright = cv2.morphologyEx(bright, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    n, lab, st, cen = cv2.connectedComponentsWithStats(bright, 8)
    kamine, gauben = [], []
    for i in range(1, n):
        area = st[i, cv2.CC_STAT_AREA] * mpp * mpp
        if area < 0.4 or area > 10:
            continue
        cx, cy = cen[i]; xf, yd = dop_px_to_frac(cx, cy)
        if not (0.0 <= xf <= 1.0):
            continue
        w, h = st[i, cv2.CC_STAT_WIDTH], st[i, cv2.CC_STAT_HEIGHT]
        (kamine if area < 1.6 and 0.6 < w / max(1, h) < 1.7 else gauben).append(round(float(xf), 3))
    kamine, gauben = sorted(set(kamine)), sorted(set(gauben))
    out = {"quelle": "DOP-Luftbild 20 cm (schaerfer als Laser) -> Fassaden-x-Anteil via massing_frame",
           "kamine_x_frac": kamine, "gauben_x_frac": gauben,
           "n_kamine": len(kamine), "n_gauben": len(gauben)}
    json.dump(out, open(f"{md}/dach_aufbauten.json", "w"), indent=1, ensure_ascii=False)

    ov = dop[max(0, y0 - 20):y1 + 20, max(0, x0b - 20):x1b + 20].copy()
    ov = cv2.resize(ov, None, fx=2, fy=2)
    print(json.dumps(out, indent=1, ensure_ascii=False))
    print(f"-> {md}/dach_aufbauten.json")


if __name__ == "__main__":
    main()
