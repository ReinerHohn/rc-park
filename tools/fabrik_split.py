#!/usr/bin/env python3
import math
"""fabrik_split.py — Bauteil-Split für die Fertigung: klassifiziert jede Farbgruppe eines
Gebäudemodells in LASERCUT (große gerade Wandflächen) vs 3D-DRUCK (Dach + filigrane Teile)
und rechnet den Aufwand in einem Zielmaßstab (Default H0 = 1:87) aus den echten Meshes.

  python3 tools/fabrik_split.py <modell_dir> <prefix> [--scale 87]

Annahmen (oben im Skript, anpassbar) — alles als Spanne, klar deklariert.
"""
import argparse, glob, os
import numpy as np
import trimesh

# Wand-Gruppen (flach, gerade) -> Laser. Alles andere (Dach, Fenster, Deko ...) -> Druck.
LASER_KEYS = ("fassade", "eg_sockel", "giebel", "waende", "wand")

# Fertigungs-Annahmen
LASER_SPEED_MM_S = 7.0        # 3mm Pappel/Sperrholz, S9 5,5W, mehrere Durchgänge -> effektiv langsam
LASER_SETUP_MIN = 4.0         # Rüsten je Platte (Material legen, Fokus, Start)
PRINT_RATE_G_H = 10.0         # kleine Detailteile @0.4-Düse, realistischer Schnitt (nicht Max-Flow)
PLA_G_PER_CM3 = 1.24
SHELL_CM = 0.07               # Schale netto (Vorder+Rückseite in mesh.area -> konservativ), cm
ASSEMBLY_MIN_PER_PART = 3.5   # Kleben/Einpassen je Einzelteil (Mittel)


def front_silhouette_area_m2(m):
    """Fläche der zur Fassade (-Y) zeigenden Flächen = Laser-Panelfläche (Löcher bereits drin)."""
    n = m.face_normals
    t = m.triangles[n[:, 1] < -0.3][:, :, [0, 2]]      # zur -Y zeigende Flächen, auf XZ
    if not len(t):
        return 0.0
    v1 = t[:, 1] - t[:, 0]; v2 = t[:, 2] - t[:, 0]
    return float(np.abs(v1[:, 0] * v2[:, 1] - v1[:, 1] * v2[:, 0]).sum() / 2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mdir"); ap.add_argument("prefix"); ap.add_argument("--scale", type=float, default=87.0)
    a = ap.parse_args()
    s = 1.0 / a.scale
    files = sorted(glob.glob(f"{a.mdir}/{a.prefix}_*.stl"))
    laser, prnt = [], []
    for f in files:
        nm = os.path.basename(f)[len(a.prefix) + 1:-4]
        try:
            m = trimesh.load(f, process=False)
        except Exception:
            continue
        if not hasattr(m, "faces") or not len(m.faces):
            continue
        ext = m.extents
        is_laser = any(k in nm for k in LASER_KEYS)
        if is_laser:
            area = front_silhouette_area_m2(m)                 # m²
            cutlen = 4.6 * math.sqrt(max(area, 1e-4))          # Umriss + Fensterlöcher (Heuristik), m
            laser.append((nm, area, cutlen, ext))
        else:
            prnt.append((nm, m.area, ext))                     # Fläche (m²) -> Schalen-Materialschätzung

    # --- LASER ---
    la_area_cm2 = sum(x[1] for x in laser) * s * s * 1e4
    la_cut_cm = sum(x[2] for x in laser) * s * 1e2
    la_time_min = la_cut_cm * 10 / LASER_SPEED_MM_S / 60 + len(laser) * LASER_SETUP_MIN
    # --- DRUCK (Schale: Fläche_H0 × Wandstärke) ---
    pr_area_cm2 = sum(x[1] for x in prnt) * s * s * 1e4
    pr_vol_cm3 = pr_area_cm2 * SHELL_CM
    pr_fil_g = pr_vol_cm3 * PLA_G_PER_CM3
    pr_time_h = pr_fil_g / PRINT_RATE_G_H
    # --- MONTAGE ---
    nparts = len(laser) + len(prnt)
    asm_h = nparts * ASSEMBLY_MIN_PER_PART / 60

    print(f"=== {a.prefix}  @ 1:{a.scale:.0f} (H0) ===  {len(files)} Gruppen")
    print(f"\nLASERCUT (gerade Wandflächen): {len(laser)} Platten")
    for nm, area, cl, ext in laser:
        print(f"  {nm:12s} Panel {area*s*s*1e4:6.1f} cm²  ~{ext[0]*s*100:.1f}×{ext[2]*s*100:.1f} cm")
    print(f"  -> Sheet gesamt ~{la_area_cm2:.0f} cm² (≈{la_area_cm2/623:.1f}× A6), Schnittlänge ~{la_cut_cm:.0f} cm")
    print(f"  -> Laserzeit ~{la_time_min:.0f} min")
    print(f"\n3D-DRUCK (Dach + Filigran): {len(prnt)} Gruppen")
    pr_sorted = sorted(prnt, key=lambda x: -x[1])
    for nm, ar, ext in pr_sorted[:10]:
        print(f"  {nm:12s} Fläche {ar*s*s*1e4:6.1f} cm²  ~{ext[0]*s*100:.1f}×{ext[2]*s*100:.1f} cm")
    print(f"  -> Volumen ~{pr_vol_cm3:.1f} cm³, Filament ~{pr_fil_g:.0f} g, Druckzeit ~{pr_time_h:.1f} h")
    print(f"\nMONTAGE: {nparts} Teile × {ASSEMBLY_MIN_PER_PART:.0f} min ~{asm_h:.1f} h")
    print(f"\nGESAMT (grob): Laser {la_time_min/60:.1f} h + Druck {pr_time_h:.1f} h (parallel/Maschine) + Montage {asm_h:.1f} h")
    print(f"  Material: ~{la_area_cm2:.0f} cm² Platte + ~{pr_fil_g:.0f} g Filament")


if __name__ == "__main__":
    import math  # noqa
    main()
