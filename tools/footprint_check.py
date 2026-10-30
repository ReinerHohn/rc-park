#!/usr/bin/env python3
"""footprint_check.py — PFLICHT-Gegenprüfung: stimmt der verwendete Grundriss (LOD2-Teile / aus Foto
freigestelltes Gebäude) mit DOP + Laser-nDOM überein, oder ist versehentlich ein FREMDTEIL (Nachbar,
Vorgebäude) drin? Für JEDEN Grundriss-Teil: Laser-Bauhöhe (nDOM) vs LOD2-First + Abstand zum Hauptteil.

Flaggt: Teil ohne Laser-Bauhöhe (kein Hochbau da = Phantom), oder weit detachiert (Fremdgebäude).
Zeichnet Teile nummeriert aufs DOP-Orthofoto zum SELBST-Prüfen.

Lauf: /tmp/ml/bin/python tools/footprint_check.py --name hofgut_sternen
"""
import argparse, json, math, os
import numpy as np
import cv2

DOM_DEF = "daten/ravenna/dom1/dom1_32_429_5306_2_bw/dom1_32_430_5307_1_bw_2017.tif"
DGM_DEF = "daten/ravenna/dgm1_32_429_5306_2_bw/dgm1_32_430_5307_1_bw_2017.xyz"
DOP_DEF = "daten/ravenna/dop/dop20rgb_32_429_5306_2_bw/dop20rgb_32_430_5307_1_bw_2025.tif"


def grid_from_xyz(xyz, E0, N0, n):
    d = np.loadtxt(xyz); G = np.full((n, n), np.nan, np.float32)
    c = np.round(d[:, 0] - 0.5 - E0).astype(int); r = np.round(N0 - 0.5 - d[:, 1]).astype(int)
    ok = (c >= 0) & (c < n) & (r >= 0) & (r < n); G[r[ok], c[ok]] = d[ok, 2]
    return G


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--dom", default=DOM_DEF); ap.add_argument("--dgm", default=DGM_DEF); ap.add_argument("--dop", default=DOP_DEF)
    ap.add_argument("--min-h", type=float, default=3.0, help="Mindest-nDOM-Höhe für echten Hochbau")
    ap.add_argument("--detach-m", type=float, default=40.0, help="Abstand ab dem ein Teil als Fremdgebäude gilt")
    a = ap.parse_args()
    md = f"modelle/{a.name}"

    tfw = open(os.path.splitext(a.dom)[0] + ".tfw").read().split()
    px, _, _, py, oxc, oyc = [float(x) for x in tfw]; E0, N0 = oxc - px / 2, oyc - py / 2
    D = cv2.imread(a.dom, cv2.IMREAD_UNCHANGED).astype(np.float32); n = D.shape[0]
    nd = D - grid_from_xyz(a.dgm, E0, N0, n)

    fp = json.load(open(f"{md}/footprint.json")); o = np.array(fp["origin_utm"][:2])
    teile = fp["teile"]
    areas = [cv2.contourArea(np.array(t["ring_xy_m"], np.float32)) for t in teile]
    main = int(np.argmax(areas))
    mc = (np.array(teile[main]["ring_xy_m"])).mean(0)

    # DOP-Crop + Overlay
    tfw2 = open(os.path.splitext(a.dop)[0] + ".tfw").read().split()
    px2, _, _, py2, ox2, oy2 = [float(x) for x in tfw2]; E02, N02 = ox2 - px2 / 2, oy2 - py2 / 2
    dop = cv2.imread(a.dop)
    rows, flags = [], []
    allc = []
    for i, t in enumerate(teile):
        ring = np.array(t["ring_xy_m"]) + o
        cc = np.round((ring[:, 0] - E02) / px2).astype(np.int32); rr = np.round((N02 - ring[:, 1]) / -py2).astype(np.int32)
        allc.append(np.c_[cc, rr])
        # nDOM über dem Teil
        cc2 = np.round(ring[:, 0] - 0.5 - E0).astype(np.int32); rr2 = np.round(N0 - 0.5 - ring[:, 1]).astype(np.int32)
        m = np.zeros((n, n), np.uint8); cv2.fillPoly(m, [np.c_[cc2, rr2]], 1)
        vals = nd[m > 0]; vals = vals[np.isfinite(vals)]
        med = float(np.median(vals)) if len(vals) else 0.0
        dist = math.hypot(*(np.array(t["ring_xy_m"]).mean(0) - mc))
        flag = []
        if med < a.min_h:
            flag.append("KEIN HOCHBAU (nDOM<%.1f)" % a.min_h)
        if dist > a.detach_m:
            flag.append("DETACHIERT %.0fm = Fremdgebäude?" % dist)
        rows.append((i, t.get("ridge_m"), med, int(m.sum()), dist, " + ".join(flag) or "OK"))
        if flag:
            flags.append(i)

    allpts = np.vstack(allc); x0, y0 = allpts.min(0); x1, y1 = allpts.max(0)
    pad = 30; crop = dop[max(0, y0 - pad):y1 + pad, max(0, x0 - pad):x1 + pad].copy()
    for i, pts in enumerate(allc):
        p = pts - [max(0, x0 - pad), max(0, y0 - pad)]
        col = (0, 0, 255) if i in flags else (0, 220, 0)
        cv2.polylines(crop, [p], True, col, 2)
        cv2.putText(crop, str(i), tuple(p.mean(0).astype(int)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, col, 2)
    crop = cv2.resize(crop, None, fx=2, fy=2)
    cv2.imwrite(f"{md}/footprint_check.png", crop)

    print(f"=== FOOTPRINT-GEGENPRÜFUNG {a.name} (gegen DOP + Laser-nDOM) ===")
    print("Teil | LOD2-First | nDOM-med | Fläche | Abstand | Verdikt")
    for i, first, med, area, dist, verd in rows:
        print(f"  {i}  |   {str(first):5}  |  {med:5.1f}  |  {area:4d}  | {dist:5.1f}m | {verd}")
    print(f"\n{'⚠️ VERDÄCHTIG: Teile ' + str(flags) if flags else '✅ alle Teile laser-bestätigt, keiner detachiert'}")
    print(f"-> {md}/footprint_check.png (Teile nummeriert aufm DOP; rot=verdächtig)")


if __name__ == "__main__":
    main()
