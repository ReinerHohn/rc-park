#!/usr/bin/env python3
"""hofgut_sternen.py — Detail-3D des Hofgut Sternen (Höllsteig/Ravennaschlucht) aus der
Vermesser-Pipeline: LOD2 liefert Grundriss+Höhen (belegt), die FOTOS liefern die Fassade.

Maße (m) — Herkunft markiert:
  Gesamthöhe First  17,5   [LOD2  measuredHeight 17,46/17,63 — amtlich]
  Traufe             9,0   [LOD2 Dach-Unterkante 9,37 ~ Foto Dachanteil ~50% — PASS]
  Grund-z         713,5    [LOD2 GroundSurface]
  Fassadenlänge     40     [LOD2 Hauptfront-Lauf ~40 m + Foto]
  Tiefe             13     [LOD2 Hauptteil]
  Sockel 0..3 / 1.OG 3..6 / 2.OG 6..9  [Foto: 3 Ebenen, je ~3 m]
  Balkonvorsprung  1,3     [Foto]
  Gauben unten 7 / oben 6  [Foto g1/g2/g4 gezählt]
  Kamine            3      [Foto]

Baut farbige Teil-STL (Sockel/Wände/Balkone/Dach/Gauben/Kamine) + Gesamt-STL.
"""
import argparse, os
import numpy as np
import trimesh


def box(x0, y0, z0, dx, dy, dz):
    b = trimesh.creation.box(extents=(dx, dy, dz))
    b.apply_translation((x0 + dx / 2, y0 + dy / 2, z0 + dz / 2))
    return b


def hip_roof(Lf, D, z_eave, z_ridge, inset, overh=0.6):
    """Walm-/Krüppelwalmdach als Mesh (Front -y, Rück +y). inset = Firstverkürzung je Seite."""
    o = overh
    E = z_eave
    # Traufrechteck (mit Überstand)
    A = (-o, -o, E); B = (Lf + o, -o, E); C = (Lf + o, D + o, E); Dd = (-o, D + o, E)
    R0 = (inset, D / 2, z_ridge); R1 = (Lf - inset, D / 2, z_ridge)
    V = [A, B, C, Dd, R0, R1]
    F = [(0, 1, 5), (0, 5, 4),       # Front-Schräge
         (2, 3, 4), (2, 4, 5),       # Rück-Schräge
         (0, 4, 3),                  # linker Walm
         (1, 2, 5)]                  # rechter Walm
    return trimesh.Trimesh(vertices=np.array(V, float), faces=np.array(F), process=True)


def shed_dormer(x, y_slope, z_slope, w=2.0, proj=1.8, h=1.7):
    """Schleppgaube: sitzt mit der Rückkante auf der Dachlinie (y_slope,z_slope) und ragt
    nach vorn (-y) + oben heraus. Front-Wand + zwei Seiten + flaches Pultdach."""
    yf = y_slope - proj               # Front-Wand weiter außen (-y)
    zt = z_slope + h                  # Front-Oberkante
    zb = z_slope - 0.3                # Front-Unterkante (etwas unter die Dachlinie)
    xl, xr = x - w / 2, x + w / 2
    V = [(xl, yf, zb), (xr, yf, zb), (xr, yf, zt), (xl, yf, zt),          # Front 0-3
         (xl, y_slope, z_slope + 0.2), (xr, y_slope, z_slope + 0.2),     # Dachlinie 4-5
         (xl, y_slope, z_slope + h + 0.2), (xr, y_slope, z_slope + h + 0.2)]  # Rück-Oberkante 6-7
    F = [(0, 1, 2), (0, 2, 3),        # Front
         (3, 2, 7), (3, 7, 6),        # Pultdach
         (0, 3, 6), (0, 6, 4),        # Seite links
         (1, 5, 7), (1, 7, 2),        # Seite rechts
         (0, 4, 5), (0, 5, 1)]        # Boden
    return trimesh.Trimesh(vertices=np.array(V, float), faces=np.array(F), process=True)


def railing(x0, y, z, length, height=1.0, posts=None):
    """Balkonbrüstung: untere+obere Leiste + Pfosten (als dünne Kästen)."""
    parts = [box(x0, y, z + height - 0.12, length, 0.08, 0.12),
             box(x0, y, z + 0.0, length, 0.08, 0.12)]
    n = posts or max(2, int(length / 1.1))
    for xi in np.linspace(x0, x0 + length, n):
        parts.append(box(xi - 0.03, y, z, 0.06, 0.08, height))
    return trimesh.util.concatenate(parts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--Lf", type=float, default=40.0)
    ap.add_argument("--D", type=float, default=13.0)
    ap.add_argument("--eave", type=float, default=9.0)
    ap.add_argument("--ridge", type=float, default=17.5)
    ap.add_argument("--socle", type=float, default=3.0)
    ap.add_argument("--floor", type=float, default=3.0)
    ap.add_argument("--balc-proj", type=float, default=1.3)
    ap.add_argument("--dormers-low", type=int, default=7)
    ap.add_argument("--dormers-up", type=int, default=6)
    ap.add_argument("--chimneys", type=int, default=3)
    ap.add_argument("--inset", type=float, default=5.0)
    ap.add_argument("--outdir", default="modelle/hofgut_sternen")
    a = ap.parse_args()
    Lf, D, E, Rz = a.Lf, a.D, a.eave, a.ridge

    sockel = box(0, 0, 0, Lf, D, a.socle)
    waende = box(0, 0, a.socle, Lf, D, E - a.socle)
    dach = hip_roof(Lf, D, E, Rz, a.inset)

    # durchlaufende Balkone an der Front (-y) auf 1.OG- und 2.OG-Niveau
    balkone = []
    for zf in (a.socle, a.socle + a.floor):
        deck = box(1.0, -a.balc_proj, zf - 0.15, Lf - 2.0, a.balc_proj, 0.15)
        rail = railing(1.0, -a.balc_proj, zf, Lf - 2.0, height=1.0)
        balkone += [deck, rail]
    balkone = trimesh.util.concatenate(balkone)

    # Gauben: zwei Reihen in der Front-Dachschräge
    def row(n, frac):
        z = E + frac * (Rz - E)
        # y-Position auf der Front-Schräge: von Traufe(y≈0,z=E) zu First(y=D/2,z=Rz)
        y_slope = (D / 2) * (z - E) / (Rz - E)
        xs = np.linspace(Lf * 0.12, Lf * 0.88, n)
        return [shed_dormer(x, y_slope, z) for x in xs]
    gauben = trimesh.util.concatenate(row(a.dormers_low, 0.22) + row(a.dormers_up, 0.55))

    # Kamine auf dem First
    kamine = []
    for x in np.linspace(Lf * 0.25, Lf * 0.8, a.chimneys):
        kamine.append(box(x - 0.5, D / 2 - 0.5, Rz - 1.0, 1.0, 1.0, 3.0))
    kamine = trimesh.util.concatenate(kamine)

    os.makedirs(a.outdir, exist_ok=True)
    parts = {"sockel": sockel, "waende": waende, "balkone": balkone,
             "dach": dach, "gauben": gauben, "kamine": kamine}
    for nm, m in parts.items():
        m.export(f"{a.outdir}/hofgut_{nm}.stl")
    full = trimesh.util.concatenate(list(parts.values()))
    full.export(f"{a.outdir}/hofgut_detail.stl")
    ext = full.bounds[1] - full.bounds[0]
    print(f"Detail-Modell: {len(full.vertices)} V / {len(full.faces)} F   "
          f"L×B×H = {ext[0]:.1f}×{ext[1]:.1f}×{ext[2]:.1f} m")
    print(f"  Teile: {', '.join(parts)}")
    print(f"  Gauben {a.dormers_low}+{a.dormers_up}, Kamine {a.chimneys}, "
          f"Balkone 2× (Vorsprung {a.balc_proj} m)")
    print(f"-> {a.outdir}/hofgut_detail.stl (+ Teil-STL)")


if __name__ == "__main__":
    main()
