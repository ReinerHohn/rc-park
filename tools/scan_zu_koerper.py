#!/usr/bin/env python3
"""scan_zu_koerper.py — beliebiges Objekt aus einer Punktwolke/einem Scan-Mesh -> sauberer Schichtkoerper (STL, Meter).

Kein Gebaeudetyp noetig: das Objekt wird in waagerechte Schichten geschnitten, je Schicht wird der Grundriss
des Objekts gemessen (Dichte -> Kontur -> vereinfachtes Polygon), die Schichten werden zu einem geschlossenen
Koerper gestapelt. Von oben nach unten wird dem Objekt gefolgt, damit Nachbarn nicht mit hereinwachsen.
Ergebnis danach durch tools/h0_druckfertig.py (Massstab 1:87, Teile) schicken.

Nutzung:
  scan_zu_koerper.py scan.ply ausgabe.stl --hoehe-m 45.9 --box xmin xmax ymin ymax zmin zmax
        [--aufrecht R.npy mu.npy | --up ux uy uz] [--schicht-m 0.5] [--pixel-m 0.2] [--wachstum-m 0.4] [--basis-prozent 1]
--box: grober Quader um das Objekt (Mesh-Koordinaten, darf Nachbarn enthalten).
--hoehe-m: echte Hoehe vom Fuss bis zur Spitze (z.B. aus LOD2); legt den Massstab des Scans fest.
"""
import argparse, json
import numpy as np
import cv2
import trimesh


def lade_punkte(pfad):
    m = trimesh.load(pfad, process=False)
    v = np.asarray(m.vertices, dtype=np.float64)
    if len(getattr(m, "faces", [])) > 0:   # Mesh: Flaeche dicht abtasten, sonst entstehen Luecken zwischen den Eckpunkten
        s, _ = trimesh.sample.sample_surface(m, max(400000, 20 * len(v)))
        v = np.vstack([v, np.asarray(s, dtype=np.float64)])
    return v


def aufrecht_aus_up(p, up):
    up = np.asarray(up, float); up /= np.linalg.norm(up)
    h = np.array([1., 0, 0]) if abs(up[0]) < 0.9 else np.array([0, 1., 0])
    ex = h - up * (h @ up); ex /= np.linalg.norm(ex); ey = np.cross(up, ex)
    R = np.array([ex, ey, up]); mu = p.mean(0)
    return R, mu


def polygon_aus_maske(mask, px, x0, y0):
    cs, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cs:
        return None
    c = max(cs, key=cv2.contourArea)
    c = cv2.approxPolyDP(c, 1.2, True)[:, 0, :].astype(float)
    if len(c) < 3:
        return None
    return np.c_[x0 + c[:, 0] * px, y0 + c[:, 1] * px]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("scan"); ap.add_argument("ausgabe")
    ap.add_argument("--hoehe-m", type=float, required=True)
    ap.add_argument("--box", type=float, nargs=6, required=True)
    ap.add_argument("--aufrecht", nargs=2, metavar=("R.npy", "MU.npy"))
    ap.add_argument("--up", type=float, nargs=3)
    ap.add_argument("--schicht-m", type=float, default=0.5)
    ap.add_argument("--pixel-m", type=float, default=0.2)
    ap.add_argument("--wachstum-m", type=float, default=0.4, help="wie weit der Umriss pro Schicht nach aussen wachsen darf")
    ap.add_argument("--min-punkte", type=int, default=3, help="Zelle zaehlt als belegt ab so vielen Punkten je Schicht")
    ap.add_argument("--schliessen-m", type=float, default=1.2, help="Luecken in den Oberflaechenpunkten schliessen (Meter)")
    ap.add_argument("--max-radius-m", type=float, default=7.0, help="Objektradius um die Achse; was weiter weg liegt (Nachbarn) wird ignoriert")
    ap.add_argument("--stuetzen", type=float, default=0.5, help="Schicht mit weniger als diesem Anteil der Flaeche darueber gilt als Scan-Loch -> Umriss darueber durchziehen (0 = aus)")
    ap.add_argument("--basis-prozent", type=float, default=1.0)
    a = ap.parse_args()

    p = lade_punkte(a.scan)
    c = np.array(a.box).reshape(3, 2)
    p = p[((p >= c[:, 0]) & (p <= c[:, 1])).all(1)]
    if a.aufrecht:
        R, mu = np.load(a.aufrecht[0]), np.load(a.aufrecht[1])
    else:
        R, mu = aufrecht_aus_up(p, a.up or [0, -1, 0])
    q = (p - mu) @ R.T
    z = q[:, 2]
    z0, z1 = np.percentile(z, a.basis_prozent), z.max()
    s = a.hoehe_m / (z1 - z0)                       # Meter pro Scan-Einheit
    q = q * s; z = (z - z0) * s
    print(f"{len(q)} Punkte, Hoehe {z.max():.1f} m (soll {a.hoehe_m}), 1 Einheit = {s:.2f} m")

    px = a.pixel_m
    hoch = q[z > 0.8 * a.hoehe_m]
    achse = np.median(hoch[:, :2], axis=0) if len(hoch) > 50 else np.median(q[:, :2], axis=0)
    print("Achse (m):", achse.round(2))
    x0, x1 = np.percentile(q[:, 0], [0.5, 99.5]); y0, y1 = np.percentile(q[:, 1], [0.5, 99.5])
    nx, ny = int((x1 - x0) / px) + 1, int((y1 - y0) / px) + 1
    schichten = []                                  # (z_unten, z_oben, polygon)
    zs = np.arange(a.hoehe_m - a.schicht_m, -1e-6, -a.schicht_m)   # von oben nach unten
    letzte = None
    vorher = None
    for zt in zs:
        sel = q[(z >= zt) & (z < zt + a.schicht_m)]
        if len(sel) < 50:
            # Luecke im Scan: Umriss der Schicht darueber uebernehmen (Gebaeude sind in der Hoehe durchgehend)
            if letzte is not None:
                schichten.append((zt, zt + a.schicht_m, letzte))
            continue
        H, _, _ = np.histogram2d(sel[:, 0], sel[:, 1], bins=[nx, ny], range=[[x0, x0 + nx * px], [y0, y0 + ny * px]])
        H = H.T
        mask = (H >= a.min_punkte).astype(np.uint8) * 255
        k = max(3, int(a.schliessen_m / px) | 1)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))
        # Nachbarn abschneiden: nur eine Scheibe um die Objektachse, davon der Block, der die Achse enthaelt
        yy, xx = np.mgrid[0:ny, 0:nx]
        scheibe = ((xx * px + x0 - achse[0]) ** 2 + (yy * px + y0 - achse[1]) ** 2) <= a.max_radius_m ** 2
        mask = (mask * scheibe).astype(np.uint8)
        n, lab, st, _ = cv2.connectedComponentsWithStats(mask)
        if n > 1:
            k = None
            if vorher is not None:
                # der Schicht darueber folgen: Block mit der groessten Ueberlappung (Umriss darueber leicht aufgeweitet)
                g = max(1, int(a.wachstum_m / px))
                dil = cv2.dilate(vorher, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * g + 1, 2 * g + 1)))
                ueb = [(int(((lab == j) & (dil > 0)).sum()), j) for j in range(1, n)]
                best = max(ueb)
                if best[0] > 0:
                    k = best[1]
            if k is None:
                ax_px = (int((achse[1] - y0) / px), int((achse[0] - x0) / px))
                k = lab[ax_px] if lab[ax_px] > 0 else 1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA]))
            mask = ((lab == k) * 255).astype(np.uint8)
        cs, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        mask = np.zeros_like(mask); cv2.drawContours(mask, cs, -1, 255, -1)
        vorher = mask.copy()
        poly = polygon_aus_maske(mask, px, x0, y0)
        if poly is None or cv2.contourArea(((poly - [x0, y0]) / px).astype(np.float32)) < 4:
            if letzte is not None:
                schichten.append((zt, zt + a.schicht_m, letzte))
            continue
        letzte = poly
        schichten.append((zt, zt + a.schicht_m, poly))
    gestuetzt = 0
    if a.stuetzen > 0 and schichten:
        flaeche = lambda poly: float(cv2.contourArea(poly.astype(np.float32)))
        gut = schichten[0][2]
        for i, (zb, zt_, poly) in enumerate(schichten):
            if flaeche(poly) < a.stuetzen * flaeche(gut):
                schichten[i] = (zb, zt_, gut); gestuetzt += 1
            else:
                gut = poly
    print(len(schichten), "Schichten,", gestuetzt, "davon gestuetzt (Scan-Loch)")
    if __import__("os").environ.get("DBG"):
        for zb, zt_, poly in schichten[::4]: print(round(zb,1), round(float(cv2.contourArea(poly.astype(np.float32))),1))

    from shapely.geometry import Polygon
    teile = []; verworfen = 0
    for zb, zt_, poly in schichten:
        g = Polygon(poly).buffer(0)
        if g.geom_type != "Polygon":                 # ungueltiger Umriss -> groesstes Stueck, sonst Huelle
            g = max(g.geoms, key=lambda x: x.area) if hasattr(g, "geoms") and len(g.geoms) else Polygon(poly).convex_hull
        try:
            t = trimesh.creation.extrude_polygon(g, zt_ - zb + 0.02)
        except Exception:
            try:
                t = trimesh.creation.extrude_polygon(g.convex_hull, zt_ - zb + 0.02)
            except Exception:
                verworfen += 1; continue
        t.apply_translation([0, 0, zb]); teile.append(t)
    if verworfen:
        print("WARNUNG: Schichten verworfen:", verworfen)
    koerper = trimesh.boolean.union(teile, engine="manifold")
    koerper.export(a.ausgabe)
    ex = koerper.extents
    bericht = {"hoehe_m": round(float(ex[2]), 2), "breite_m": round(float(ex[0]), 2), "tiefe_m": round(float(ex[1]), 2),
               "wasserdicht": bool(koerper.is_watertight), "schichten": len(schichten), "gestuetzt": gestuetzt, "meter_pro_einheit": round(float(s), 3)}
    json.dump(bericht, open(a.ausgabe.rsplit(".", 1)[0] + ".bericht.json", "w"), indent=1)
    print(bericht)


if __name__ == "__main__":
    main()
