#!/usr/bin/env python3
"""stadtmesh_vergleich.py - Stadtmesh (Pruefreferenz, Typ 19) und aktuelles Modell-STL aus derselben Richtung rendern (Auftrag G4, Schritt 5).

Painter-Algorithmus (cv2), orthografisch, Licht fest; Mesh mit Texturfarbe | Modell grau, 2 Zeilen (zwei Blickrichtungen).
Modell-STL wird wie in tools/foto_render_seite.py massstabsgerecht (stl_massstab, mm) in Meter zurueckgerechnet, xy-Mitte der Huelle auf die
xy-Mitte der Stadt-LoD2-Grundrisse im Modellrahmen gelegt, z-Minimum = 0 (Modell hat 'zentrierung: achse': Lage nur auf wenige dm genau - reiner Sichtvergleich).

  /media/oem/scan/venv-seg/bin/python -I tools/stadtmesh_vergleich.py modelle/<objekt>/objekt.json
"""
import argparse, json, os, sys
import numpy as np, cv2, trimesh


def render(m, az_deg, el_deg, mitte, scale, W, H, farben=None, grau=False):
    az, el = np.radians(az_deg), np.radians(el_deg)
    r = np.array([np.cos(az), np.sin(az), 0.0]); u = np.array([-np.sin(az) * np.sin(el), np.cos(az) * np.sin(el), np.cos(el)])   # Bild rechts / oben
    v = np.cross(r, u)                                                                       # Blickrichtung zur Szene: -v... (Tiefe)
    V = np.asarray(m.vertices) - mitte; px = V @ r * scale + W / 2; py = H * 0.62 - V @ u * scale; dep = V @ v
    Fc = np.asarray(m.faces); tri = np.stack([px[Fc], py[Fc]], -1); zf = dep[Fc].mean(1)
    n = np.cross(V[Fc[:, 1]] - V[Fc[:, 0]], V[Fc[:, 2]] - V[Fc[:, 0]]); nl = np.linalg.norm(n, axis=1, keepdims=True); n = n / np.maximum(nl, 1e-12)
    n[(n @ v) > 0] *= -1                                                                     # Normale zum Betrachter (Mesh nicht orientiert)
    lit = np.clip(n @ np.array([0.4, -0.5, 0.75]) * 0.6 + 0.45, 0.2, 1.0)
    img = np.full((H, W, 3), 238, np.uint8)
    for i in np.argsort(-zf):                                                                # entfernt zuerst
        if grau: c = np.array([170, 170, 170]) * lit[i]
        else:
            c = np.asarray(m.visual.vertex_colors)[Fc[i], :3].mean(0) * (0.55 + 0.45 * lit[i])
        cv2.fillConvexPoly(img, np.round(tri[i]).astype(np.int32), tuple(int(x) for x in c[::-1]), cv2.LINE_AA)
    return img


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--hoch", type=int, default=760)
    a = ap.parse_args()
    od = os.path.dirname(os.path.abspath(a.objekt)); obj = json.load(open(a.objekt)); ar = os.path.join(od, "audit", "referenz_stadtmesh")
    mesh = trimesh.load(os.path.join(ar, "mesh.ply")); mesh.visual.vertex_colors = mesh.visual.vertex_colors
    stl = trimesh.load(obj["stl"]); stl.apply_scale(float(obj.get("stl_massstab", 87)) / 1000.0)
    c = stl.bounds.mean(0); stl.apply_translation([-c[0], -c[1], -stl.bounds[0, 2]])
    sj = os.path.join(od, "stadt_lod2.json"); P = np.array([p for g in json.load(open(sj))["stadt"]["gebaeude"] for f in g["flaechen"] if f["typ"] == "Boden" for p in f["lokal"]])
    stl.apply_translation([(P[:, 0].min() + P[:, 0].max()) / 2, (P[:, 1].min() + P[:, 1].max()) / 2, 0])
    mitte = np.array([(P[:, 0].min() + P[:, 0].max()) / 2, (P[:, 1].min() + P[:, 1].max()) / 2, 0.0])
    ext = float(np.hypot(*np.ptp(np.asarray(mesh.vertices)[:, :2], axis=0))); H = a.hoch; W = int(H * 1.0); zmax = max(stl.bounds[1, 2], mesh.bounds[1, 2])
    scale = min(H * 0.8 / (zmax + 8), W * 0.9 / ext)
    rows = []
    for az, el in ((-90, 12), (-20, 20)):                                                    # Blick von Sued (az -90: Betrachter bei -y) und von SSO-schraeg
        # Betrachter-Rechtsvektor r=(cos az, sin az): az=0 -> von Westen auf Osten schauen? -> hier nur Kennung der Zeile, Blickrichtung steht im Bild
        L = render(mesh, az, el, mitte, scale, W, H); R = render(stl, az, el, mitte, scale, W, H, grau=True)
        cv2.putText(L, f"Stadtmesh 2025 (Pruefreferenz) az{az} el{el}", (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2); cv2.putText(R, f"Modell-STL {os.path.basename(obj['stl'])}", (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)
        rows.append(np.hstack([L, R]))
    out = os.path.join(ar, "vergleich.jpg"); cv2.imwrite(out, np.vstack(rows), [cv2.IMWRITE_JPEG_QUALITY, 88]); print(out)


if __name__ == "__main__":
    main()
