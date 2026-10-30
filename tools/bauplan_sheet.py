#!/usr/bin/env python3
"""bauplan_sheet.py — UNGEFÄHRER BAUPLAN aus vorhandenen Daten: GRUNDRISS (LOD2-Footprint, amtlich) +
AUFRISS (LOD2-Höhen Traufe/First + foto-gemessene Fensterachsen + Fassadenbänder). Alles in Metern.
Genau „mit Grundriss + freigestelltem Objekt schon ungefähr einen Bauplan". Keine Perspektive nötig
(Grundriss ist amtlich, Höhen aus LOD2, Achsen aus Foto-Kanten).

Lauf: /tmp/ml/bin/python tools/bauplan_sheet.py --name hofgut_sternen
"""
import argparse, json, os
import numpy as np
import cv2


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--name", required=True); a = ap.parse_args()
    md = f"modelle/{a.name}"
    fp = json.load(open(f"{md}/footprint.json")); o = np.array(fp["origin_utm"][:2])
    teile = fp["teile"]
    fac = json.load(open(f"{md}/facade_mass.json")) if os.path.exists(f"{md}/facade_mass.json") else {}
    n_axes = fac.get("n_axes", 11)
    main = int(np.argmax([cv2.contourArea(np.array(t["ring_xy_m"], np.float32)) for t in teile]))
    eave = teile[main].get("eave_m", 9.37); ridge = teile[main].get("ridge_m", 17.46)
    # Hauptflügel-Frontbreite = längste Kante
    mr = np.array(teile[main]["ring_xy_m"])
    d = np.linalg.norm(np.diff(np.vstack([mr, mr[:1]]), 0), axis=1); front_w = float(sorted(d)[-1])

    S = 1200; px = 9                                         # 9 px/m, A-Blatt
    sheet = np.full((S, S, 3), 255, np.uint8)
    def T(txt, p, sc=0.5, col=(0, 0, 0)): cv2.putText(sheet, txt, p, cv2.FONT_HERSHEY_SIMPLEX, sc, col, 1)

    # --- GRUNDRISS (oben) ---
    allr = np.vstack([np.array(t["ring_xy_m"]) for t in teile]); gx0, gy0 = allr.min(0)
    ox, oy = 60, 70
    T("GRUNDRISS (LOD2, amtlich)  -  Masse in m", (ox, 40), 0.6)
    for i, t in enumerate(teile):
        r = (np.array(t["ring_xy_m"]) - [gx0, gy0]) * px
        pts = np.c_[ox + r[:, 0], oy + (allr[:, 1].max() - allr[:, 1].min()) * px - r[:, 1]].astype(np.int32)
        col = (210, 180, 140) if i == main else (225, 225, 225)
        cv2.fillPoly(sheet, [pts], col); cv2.polylines(sheet, [pts], True, (60, 60, 60), 1)
        T(f"T{i}", tuple(pts.mean(0).astype(int)), 0.4, (90, 90, 90))
    bw = (allr[:, 0].max() - allr[:, 0].min()); bd = (allr[:, 1].max() - allr[:, 1].min())
    T(f"{bw:.0f} m", (ox + int(bw * px / 2) - 20, oy - 8), 0.5)
    T(f"{bd:.0f} m", (ox + int(bw * px) + 8, oy + int(bd * px / 2)), 0.5)

    # --- AUFRISS Hauptfassade (unten) ---
    ay = 560; aw = front_w * px; ah = ridge * px
    T("AUFRISS Hauptfassade  -  Hoehen LOD2, Achsen Foto", (ox, ay - 20), 0.6)
    base = ay + int(ah)
    # Wand bis Traufe
    cv2.rectangle(sheet, (ox, base - int(eave * px)), (ox + int(aw), base), (235, 228, 214), -1)
    # EG-Sockel (Stein) bis ~46%
    egh = eave * 0.46
    cv2.rectangle(sheet, (ox, base - int(egh * px)), (ox + int(aw), base), (200, 192, 178), -1)
    # Dach-Dreieck Traufe->First
    tip = (ox + int(aw / 2), base - int(ridge * px))
    cv2.fillPoly(sheet, [np.array([[ox, base - int(eave * px)], [ox + int(aw), base - int(eave * px)], tip])], (150, 140, 125))
    cv2.rectangle(sheet, (ox, base - int(ah)), (ox + int(aw), base), (60, 60, 60), 1)
    # Galerie-Linie + Fensterachsen
    gal = eave * 0.5
    cv2.line(sheet, (ox, base - int(gal * px)), (ox + int(aw), base - int(gal * px)), (40, 40, 160), 1)
    for k in range(n_axes):
        xx = ox + int(aw * (k + 0.5) / n_axes)
        cv2.rectangle(sheet, (xx - 4, base - int(eave * px) + 6), (xx + 4, base - int(gal * px) - 6), (120, 120, 120), 1)
    # Maße
    T(f"First {ridge:.1f} m", (ox + int(aw) + 8, base - int(ridge * px)), 0.45, (0, 0, 160))
    T(f"Traufe {eave:.1f} m", (ox + int(aw) + 8, base - int(eave * px)), 0.45, (0, 0, 160))
    T(f"EG {egh:.1f} m", (ox + int(aw) + 8, base - int(egh * px)), 0.45, (0, 0, 160))
    T(f"Front {front_w:.1f} m  -  {n_axes} Fensterachsen", (ox, base + 24), 0.5)

    cv2.imwrite(f"{md}/bauplan_sheet.png", sheet)
    print(f"BAUPLAN: Grundriss {bw:.0f}x{bd:.0f} m, Hauptflügel-Front {front_w:.1f} m, "
          f"Traufe {eave} m, First {ridge} m, {n_axes} Achsen")
    print(f"-> {md}/bauplan_sheet.png")


if __name__ == "__main__":
    main()
