#!/usr/bin/env python3
"""hofgut_sternen.py — Detail-3D des Hofgut Sternen (Höllsteig/Ravennaschlucht) aus der
Vermesser-Pipeline: LOD2 liefert Grundriss+Höhen (belegt), die FOTOS (g1–g4) die Fassade.

Maße (m) — Herkunft markiert:
  Gesamthöhe First  17,5   [LOD2 measuredHeight 17,46/17,63 — amtlich]
  Traufe             9,0   [LOD2 Dach-Unterkante 9,37 ~ Foto Dachanteil ~50% — PASS]
  Fassadenlänge     40     [LOD2 Hauptfront ~40 m + Foto]; Tiefe 13 [LOD2]
  Sockel/EG 0..3 / 1.OG 3..6 / 2.OG 6..9  [Foto: 3 Ebenen je ~3 m]
  Balkonvorsprung  1,3     [Foto]; Gauben unten 7 / oben 6 [Foto gezählt]; Kamine 3 [Foto]

GROB→FEIN: baut FARBIGES GLB (weiße Wand, dunkles Holz/Dach, Fenster, Blumen) + Teil-STL.
Verfeinerung Schritt für Schritt gegen g4 (Fresko, EG-Arkade, feinere Gauben) oben drauf.
"""
import argparse, os
import numpy as np
import trimesh


def box(x0, y0, z0, dx, dy, dz):
    b = trimesh.creation.box(extents=(dx, dy, dz))
    b.apply_translation((x0 + dx / 2, y0 + dy / 2, z0 + dz / 2))
    return b


def hip_roof(Lf, D, z_eave, z_ridge, inset, overh=0.7):
    """Krüppelwalmdach als Mesh (Front -y, Rück +y). inset = Firstverkürzung je Seite."""
    o = overh; E = z_eave
    A = (-o, -o, E); B = (Lf + o, -o, E); C = (Lf + o, D + o, E); Dd = (-o, D + o, E)
    R0 = (inset, D / 2, z_ridge); R1 = (Lf - inset, D / 2, z_ridge)
    V = [A, B, C, Dd, R0, R1]
    F = [(0, 1, 5), (0, 5, 4), (2, 3, 4), (2, 4, 5), (0, 4, 3), (1, 2, 5)]
    return trimesh.Trimesh(vertices=np.array(V, float), faces=np.array(F), process=True)


def shed_dormer(x, y_slope, z_slope, w=2.0, proj=1.8, h=1.5):
    """Schleppgaube: Rückkante auf der Dachlinie, ragt nach vorn(-y)+oben. Front + Pultdach + Seiten."""
    yf = y_slope - proj; zt = z_slope + h; zb = z_slope - 0.3; xl, xr = x - w / 2, x + w / 2
    V = [(xl, yf, zb), (xr, yf, zb), (xr, yf, zt), (xl, yf, zt),
         (xl, y_slope, z_slope + 0.2), (xr, y_slope, z_slope + 0.2),
         (xl, y_slope, z_slope + h + 0.2), (xr, y_slope, z_slope + h + 0.2)]
    F = [(0, 1, 2), (0, 2, 3), (3, 2, 7), (3, 7, 6), (0, 3, 6), (0, 6, 4),
         (1, 5, 7), (1, 7, 2), (0, 4, 5), (0, 5, 1)]
    return trimesh.Trimesh(vertices=np.array(V, float), faces=np.array(F), process=True)


def big_dormer(x, y_slope, z_slope, w=3.6, proj=1.5, h=1.9, gh=1.1):
    """GROSSES Zwerchhaus (Giebelgaube) an der Traufe: Giebel-Frontwand + Satteldach + dunkles
    Fenster. Gibt (Körper, Fenster). (Foto g4: wenige grosse statt vieler kleiner Gauben!)"""
    yf = y_slope - proj; zb = z_slope - 0.5; zt = zb + h; apex = zt + gh; xl, xr = x - w / 2, x + w / 2
    yb = y_slope
    V = [(xl, yf, zb), (xr, yf, zb), (xr, yf, zt), (xl, yf, zt), (x, yf, apex),            # Front 0-4
         (xl, yb, zb), (xr, yb, zb), (xr, yb, zt), (xl, yb, zt), (x, yb, apex)]            # Rück 5-9
    F = [(0, 1, 2), (0, 2, 3), (3, 2, 4),           # Front Rechteck + Giebeldreieck
         (5, 7, 6), (5, 8, 7), (8, 9, 7),           # Rück
         (0, 3, 8), (0, 8, 5), (1, 6, 7), (1, 7, 2),  # Seitenwände
         (3, 8, 9), (3, 9, 4), (2, 4, 9), (2, 9, 7),  # 2 Dachschrägen
         (0, 5, 6), (0, 6, 1)]                       # Boden
    body = trimesh.Trimesh(vertices=np.array(V, float), faces=np.array(F), process=True)
    win = box(x - w * 0.36, yf - 0.08, zb + 0.45, w * 0.72, 0.1, h - 0.8)
    return body, win


def skylight(x, y_slope, z_slope, w=0.85, h=1.1):
    """flaches Dachflächenfenster (Velux), liegt ~bündig auf der Schräge (dunkel)."""
    return box(x - w / 2, y_slope - 0.06, z_slope, w, 0.12, h)


def gaden(x0, y, z, length, height=0.95):
    """Schwarzwald-GADEN-Brüstung: SOLIDES dunkles Holz-Füllpaneel + Hand-/Fußleiste + senkrechte
    Rippen (Foto g4: breite geschlossene Holzbrüstung, NICHT dünne Pfosten) — das prägende Element."""
    parts = [box(x0, y - 0.05, z + 0.08, length, 0.1, height - 0.2),          # geschlossenes Füllpaneel
             box(x0, y - 0.11, z + height - 0.14, length, 0.18, 0.15),        # Handlauf (kräftig)
             box(x0, y - 0.11, z, length, 0.18, 0.13)]                        # Fußleiste
    for xi in np.arange(x0 + 0.25, x0 + length, 0.55):                        # senkrechte Rippen (Relief)
        parts.append(box(xi - 0.03, y - 0.13, z + 0.1, 0.06, 0.06, height - 0.24))
    return trimesh.util.concatenate(parts)


def window_row(Lf, z0, z1, n, wd=0.95, y=0.0):
    """Reihe ECHTER Fenster: dunkle Scheibe + heller Rahmen (Sturz/Sohlbank/Jamben) + Kreuzstock.
    Gibt (glas, rahmen)."""
    glass, fr = [], []; h = z1 - z0
    for x in np.linspace(Lf * 0.07, Lf * 0.93, n):
        xl, xr = x - wd / 2, x + wd / 2
        glass.append(box(xl, y - 0.05, z0, wd, 0.1, h))
        fr.append(box(xl - 0.07, y - 0.11, z1 - 0.02, wd + 0.14, 0.13, 0.11))     # Sturz
        fr.append(box(xl - 0.07, y - 0.11, z0 - 0.06, wd + 0.14, 0.14, 0.1))      # Sohlbank
        fr.append(box(xl - 0.07, y - 0.11, z0, 0.08, 0.13, h))                    # Jambe links
        fr.append(box(xr - 0.01, y - 0.11, z0, 0.08, 0.13, h))                    # Jambe rechts
        fr.append(box(xl, y - 0.13, (z0 + z1) / 2 - 0.03, wd, 0.06, 0.06))        # Kämpfer (quer)
        fr.append(box(x - 0.03, y - 0.13, z0, 0.06, 0.06, h))                     # Mittelpfosten
    return trimesh.util.concatenate(glass), trimesh.util.concatenate(fr)


def flower_boxes(x0, y, z, length, h_rail=0.95):
    """ÜPPIGE Geranien über die ganze Brüstung (Foto g4): durchlaufender Blütenwulst, überhängend."""
    parts, x = [], x0
    while x < x0 + length:
        seg = min(0.6, x0 + length - x)
        parts.append(box(x + 0.02, y - 0.22, z + h_rail - 0.1, seg * 0.96, 0.36, 0.3))     # Blütenwulst OBEN am Handlauf
        parts.append(box(x - 0.01, y - 0.28, z + h_rail - 0.34, seg * 1.02, 0.3, 0.3))     # überhängend nach unten (Holz darunter bleibt sichtbar)
        x += seg
    return trimesh.util.concatenate(parts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--Lf", type=float, default=40.0); ap.add_argument("--D", type=float, default=13.0)
    ap.add_argument("--eave", type=float, default=9.0); ap.add_argument("--ridge", type=float, default=17.5)
    ap.add_argument("--socle", type=float, default=3.0); ap.add_argument("--floor", type=float, default=3.0)
    ap.add_argument("--balc-proj", type=float, default=1.3); ap.add_argument("--n-axes", type=int, default=13)
    ap.add_argument("--dormers-low", type=int, default=7); ap.add_argument("--dormers-up", type=int, default=6)
    ap.add_argument("--chimneys", type=int, default=3); ap.add_argument("--inset", type=float, default=5.0)
    ap.add_argument("--outdir", default="modelle/hofgut_sternen")
    a = ap.parse_args()
    Lf, D, E, Rz, S, Fl, bp, N = a.Lf, a.D, a.eave, a.ridge, a.socle, a.floor, a.balc_proj, a.n_axes

    sockel = box(0, 0, 0, Lf, D, S)
    waende = box(0, 0, S, Lf, D, E - S)
    dach = hip_roof(Lf, D, E, Rz, a.inset)

    balkone, blumen = [], []
    for zf in (S, S + Fl):                                   # Gaden-Galerien auf 1.OG + 2.OG
        balkone.append(box(0.6, -bp, zf - 0.18, Lf - 1.2, bp + 0.1, 0.18))     # auskragender Holzboden
        balkone.append(gaden(0.6, -bp, zf, Lf - 1.2))                          # solide Holzbrüstung
        blumen.append(flower_boxes(0.6, -bp, zf, Lf - 1.2))                    # üppige Geranien
    balkone = trimesh.util.concatenate(balkone); blumen = trimesh.util.concatenate(blumen)

    # Fassadenfenster (echt, mit Rahmen): EG + 1.OG + 2.OG hinter den Galerien
    fglass, fframe = [], []
    for z0, z1 in [(0.9, 2.1), (S + 0.5, S + 1.9), (S + Fl + 0.5, S + Fl + 1.9)]:
        g, fr = window_row(Lf, z0, z1, N); fglass.append(g); fframe.append(fr)

    # DACH: wenige GROSSE Zwerchhäuser (an der Traufe) + flache Velux — NICHT viele kleine Gauben (Foto g4)
    dz = E + 0.13 * (Rz - E); dy = (D / 2) * (dz - E) / (Rz - E)
    bodies = []
    for x in np.array([0.24, 0.55, 0.82]) * Lf:
        b, w_ = big_dormer(x, dy, dz); bodies.append(b); fglass.append(w_)
    vz = E + 0.5 * (Rz - E); vy = (D / 2) * (vz - E) / (Rz - E)
    fglass += [skylight(x, vy, vz) for x in np.array([0.18, 0.40, 0.63, 0.86]) * Lf]
    gauben = trimesh.util.concatenate(bodies)
    fenster = trimesh.util.concatenate(fglass)
    fensterrahmen = trimesh.util.concatenate(fframe)

    kamine = trimesh.util.concatenate(
        [box(x - 0.5, D / 2 - 0.5, Rz - 1.0, 1.0, 1.0, 3.0) for x in np.linspace(Lf * 0.25, Lf * 0.8, a.chimneys)])

    COL = {"sockel": [206, 198, 184, 255], "waende": [240, 234, 222, 255], "balkone": [74, 50, 32, 255],
           "dach": [50, 44, 40, 255], "gauben": [78, 54, 36, 255], "kamine": [112, 100, 90, 255],
           "fenster": [40, 40, 46, 255], "blumen": [188, 52, 58, 255], "fensterrahmen": [238, 233, 223, 255]}
    parts = {"sockel": sockel, "waende": waende, "balkone": balkone, "fenster": fenster,
             "fensterrahmen": fensterrahmen, "blumen": blumen, "dach": dach, "gauben": gauben, "kamine": kamine}
    os.makedirs(a.outdir, exist_ok=True)
    sc = trimesh.Scene()
    for nm, m in parts.items():
        m.visual.face_colors = COL[nm]; m.export(f"{a.outdir}/hofgut_{nm}.stl")
        sc.add_geometry(m, geom_name=nm)
    trimesh.util.concatenate(list(parts.values())).export(f"{a.outdir}/hofgut_detail.stl")
    sc.export(f"{a.outdir}/hofgut_sternen.glb")
    ext = sc.bounds[1] - sc.bounds[0]
    print(f"Hofgut Sternen (grob+farbig): L×B×H = {ext[0]:.1f}×{ext[1]:.1f}×{ext[2]:.1f} m")
    print(f"  Teile: {', '.join(parts)} | {N} Achsen, Gauben {a.dormers_low}+{a.dormers_up}, Kamine {a.chimneys}")
    print(f"-> {a.outdir}/hofgut_sternen.glb (+ Teil-STL + hofgut_detail.stl)")


if __name__ == "__main__":
    main()
