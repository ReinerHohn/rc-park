#!/usr/bin/env python3
"""foto_modell_homografie.py — PERSPEKTIV-GENAUER Bewerter Realität gegen Modell für (nahezu)
planare Fassaden OHNE EXIF-Intrinsics.

Die Giebelfassade ist eine Ebene (y=0). Eine HOMOGRAPHIE bildet Fassaden-Ebenen-Koordinaten
(x=Breite, z=Höhe in Metern) auf die Foto-Pixel ab — und erfasst damit die echte Kamera-
Perspektive inkl. der vertikalen Stauchung (Platz-Wurmblick). Keine Brennweite nötig.

Korrespondenzen AUTOMATISCH aus der Fassaden-Silhouette (Punkte, deren 3D-Lage aus LOD2 bekannt
ist): Giebelspitze (Finial), Trauf-Ecken (wo der Giebel in voller Breite ansetzt), Fuss-Ecken.
Dann wird die Modell-VEKTORGEOMETRIE (Treppengiebel-Umriss, Fenster, Arkade — in Fassaden-Metern)
durch H aufs Foto projiziert und rot überlagert; so wird JEDE echte Abweichung (Stufenhöhe,
Fensterlage) messbar statt vom Perspektivfehler überdeckt.

  python3 tools/foto_modell_homografie.py --config bauwerke/kornhaus.json --foto <f> \
      --box x0,y0,x1,y1 --out overlay.png
"""
import argparse, json, os, sys
import numpy as np
import cv2
sys.path.insert(0, os.path.dirname(__file__))
import giebelhaus_generator as G


def facade_silhouette(img, box):
    """saubere Kornhaus-Silhouette über den ROSA SANDSTEIN (robust auch bei bläulichem Weiss-
    abgleich): Eckquader/Gurtbänder/Stufen-Abdeckungen/Gewände/Finial umrahmen das Gebäude.
    Rosa stark schliessen -> grösste Fläche -> deren CONVEX HULL = Fassaden-Umriss."""
    H0, W0 = img.shape[:2]
    x0, y0, x1, y1 = [int(b) for b in box]
    sub = img[y0:y1, x0:x1]
    hsv = cv2.cvtColor(sub, cv2.COLOR_BGR2HSV); Hh, S, V = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]
    pink = (((Hh < 15) | (Hh > 165)) & (S > 25) & (S < 170) & (V > 90)).astype(np.uint8) * 255
    pink = cv2.morphologyEx(pink, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))       # Rauschen weg
    # ALLE Sandstein-Komponenten ab Mindestgrösse zusammen hüllen (Giebel-Zier + Body-Zier sind
    # getrennte Blobs; der gemeinsame Convex Hull = voller Fassaden-Umriss Finial..Arkade)
    n, lab, st, _ = cv2.connectedComponentsWithStats(pink)
    keep = np.zeros_like(pink)
    big = sorted(st[1:, 4], reverse=True)[:1] or [0]
    for i in range(1, n):
        if st[i, 4] > max(400, 0.01 * big[0]):
            keep[lab == i] = 255
    cnts, _ = cv2.findContours(keep, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    hull = cv2.convexHull(np.vstack(cnts)) if cnts else None
    m = np.zeros_like(pink)
    if hull is not None:
        cv2.fillConvexPoly(m, hull, 255)
    full = np.zeros((H0, W0), np.uint8); full[y0:y1, x0:x1] = (m > 0).astype(np.uint8)
    return full


def corners_from_silhouette(mask, W, eave, ridge, finial_h=0.9):
    """Finial-Spitze, Trauf-Ecken (oberste Zeile voller Breite), Fuss-Ecken -> 2D/3D-Paare."""
    ys, xs = np.where(mask)
    y_top, y_bot = int(ys.min()), int(ys.max())
    widths = {}
    for y in range(y_top, y_bot + 1):
        xr = np.where(mask[y])[0]
        if len(xr):
            widths[y] = (int(xr.min()), int(xr.max()))
    bl, br = widths[y_bot]                        # Fuss-Ecken = zuverlässig (Arkadenbasis)
    bw = br - bl
    # Fassaden-Seitenkanten sind nahezu senkrecht (frontal) -> Trauf-Ecken an die Fuss-x binden,
    # Breite gegen die BASIS messen (nicht gegen max -> robust gegen Nachbar-Kontamination)
    eave_y = next((y for y in range(y_top, y_bot + 1)
                   if y in widths and min(widths[y][1], br) - max(widths[y][0], bl) >= 0.85 * bw),
                  y_top + (y_bot - y_top) // 2)
    # Finial-Spitze: oberster Punkt im zentralen Drittel (Seiten-Ausreisser ignorieren)
    cl, cr = bl + bw // 3, br - bw // 3
    ytops = [y for y in range(y_top, y_bot + 1) if y in widths
             and widths[y][1] >= cl and widths[y][0] <= cr]
    fy = ytops[0]; frow = np.where(mask[fy])[0]; fx = int(frow[(frow >= cl) & (frow <= cr)].mean())
    img2d = np.array([[fx, fy],                  # Finial
                      [bl, eave_y], [br, eave_y], # Trauf-Ecken (an Fuss-x gebunden)
                      [bl, y_bot], [br, y_bot]], float)   # Fuss-Ecken
    mdl3d = np.array([[W / 2, ridge + finial_h],
                      [0, eave], [W, eave],
                      [0, 0.0], [W, 0.0]], float)
    return img2d, mdl3d, dict(eave_y=int(eave_y), y_top=y_top, y_bot=y_bot, base_w=int(bw))


def model_facade_polylines(gh):
    """Modell-Vektorgeometrie in Fassaden-(x,z)-Metern: Treppengiebel-Umriss, Fenster, Arkade."""
    polys = []
    out = G.stepped_gable_outline(gh.W, gh.z_body, gh.peak, gh.nsteps, gh.inset)
    polys.append(np.array(out.exterior.coords))
    for cx, zc, w, h, arched in gh.window_specs():
        polys.append(np.array([(cx - w / 2, zc - h / 2), (cx + w / 2, zc - h / 2),
                               (cx + w / 2, zc + h / 2), (cx - w / 2, zc + h / 2),
                               (cx - w / 2, zc - h / 2)]))
    for xc, aw, spring, apex in gh.arcade_openings():
        p = [(xc - aw / 2, 0)]
        for k in range(0, 11):
            ang = np.pi * k / 10
            p.append((xc + aw / 2 * np.cos(ang), spring + (apex - spring) * np.sin(ang)))
        p.append((xc - aw / 2, 0)); polys.append(np.array(p))
    return polys


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True); ap.add_argument("--foto", required=True)
    ap.add_argument("--box", required=True, help="x0,y0,x1,y1 Fraktion (Kornhaus eingrenzen)")
    ap.add_argument("--corners", default=None,
                    help="EINMAL-Kalibrierung: 5 Fraktion-Paare fx,fy,... für "
                         "Finial, Trauf-L, Trauf-R, Fuss-L, Fuss-R (sonst Auto aus Silhouette)")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    cfg = json.load(open(a.config)); gh = G.Giebelhaus(cfg)
    img = cv2.imread(a.foto); H0, W0 = img.shape[:2]
    f = [float(t) for t in a.box.split(",")]
    box = (f[0] * W0, f[1] * H0, f[2] * W0, f[3] * H0)

    mask = facade_silhouette(img, box)
    mdl3d = np.array([[gh.W / 2, gh.peak + 0.9], [0, gh.z_body], [gh.W, gh.z_body],
                      [0, 0.0], [gh.W, 0.0]], float)
    if a.corners:
        c = [float(t) for t in a.corners.split(",")]
        img2d = np.array([[c[2 * i] * W0, c[2 * i + 1] * H0] for i in range(5)], float)
        info = {"mode": "manuell kalibriert"}
    else:
        img2d, _, info = corners_from_silhouette(mask, gh.W, gh.z_body, gh.peak)
        info["mode"] = "auto (Silhouette)"
    # Homographie Fassaden-Ebene (x,z) -> Foto-Pixel
    Hmat, _ = cv2.findHomography(mdl3d, img2d, cv2.RANSAC, 5.0)
    proj = cv2.perspectiveTransform(mdl3d.reshape(-1, 1, 2), Hmat).reshape(-1, 2)
    rms = float(np.sqrt(((proj - img2d) ** 2).sum(1).mean()))

    ov = img.copy()
    for poly in model_facade_polylines(gh):
        pp = cv2.perspectiveTransform(poly.reshape(-1, 1, 2).astype(float), Hmat).reshape(-1, 2)
        cv2.polylines(ov, [pp.astype(np.int32)], False, (0, 0, 255), 3)
    for (u, v) in img2d:
        cv2.circle(ov, (int(u), int(v)), 10, (0, 200, 0), -1)      # genutzte Korrespondenzen
    cv2.putText(ov, f"Homographie-RMS={rms:.1f}px (Passpunkte)", (30, 60),
                cv2.FONT_HERSHEY_SIMPLEX, 1.4, (0, 90, 0), 3)
    # eng auf Fassade zuschneiden
    ys, xs = np.where(mask)
    pad = 60; cr = ov[max(0, ys.min() - pad):ys.max() + pad, max(0, xs.min() - pad):xs.max() + pad]
    cv2.imwrite(a.out, cr)
    print(f"Passpunkte-RMS = {rms:.1f} px   [{info.get('mode', '')}]")
    print(f"-> {a.out}")


if __name__ == "__main__":
    main()
