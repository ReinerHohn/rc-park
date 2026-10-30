#!/usr/bin/env python3
"""pack_beds.py — viele kleine STL-Teile auf möglichst wenige Druckbetten packen.

Shelf-Packing (First-Fit-Decreasing nach Tiefe): legt die Teile flach nebeneinander
in Reihen, bis das Bett (bed-x × bed-y) voll ist, dann neues Bett. Jedes Bett wird als
EIN zusammengefügtes STL ausgegeben -> ein Druckjob statt vieler. Spart den Heiz-/Homing-/
Purge-Overhead je Einzelteil (bei 86 Teilen ~Stunden). Teile behalten ihre z-Lage (liegen flach).

  python3 tools/pack_beds.py --in /tmp/skinlean --out /tmp/beds --bed-x 250 --bed-y 210 --gap 3
"""
import argparse, glob, os, sys, numpy as np, trimesh


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True, help="Ordner mit STL-Teilen")
    ap.add_argument("--out", default="/tmp/beds")
    ap.add_argument("--bed-x", type=float, default=250); ap.add_argument("--bed-y", type=float, default=210)
    ap.add_argument("--gap", type=float, default=3.0, help="Abstand zwischen Teilen mm")
    ap.add_argument("--glob", default="*.stl")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    for f in glob.glob(f"{a.out}/bed_*.stl"): os.remove(f)

    items = []
    for f in sorted(glob.glob(os.path.join(a.inp, a.glob))):
        m = trimesh.load(f, process=False)
        m.apply_translation(-m.bounds[0])                 # auf Ursprung (min=0)
        w, d, h = m.extents
        if w > a.bed_x or d > a.bed_y:                     # quer stellen falls so passt
            if d <= a.bed_x and w <= a.bed_y:
                m.apply_transform(trimesh.transformations.rotation_matrix(np.pi/2, [0,0,1]))
                m.apply_translation(-m.bounds[0]); w, d, h = m.extents
        items.append((f, m, w, d))
    items.sort(key=lambda t: t[3], reverse=True)          # tiefste zuerst (ordentliche Reihen)

    beds = []; cur = []; x = a.gap; y = a.gap; rowh = 0.0; skipped = []
    for f, m, w, d in items:
        if w > a.bed_x or d > a.bed_y: skipped.append(os.path.basename(f)); continue
        if x + w + a.gap > a.bed_x:                        # neue Reihe
            x = a.gap; y += rowh + a.gap; rowh = 0.0
        if y + d + a.gap > a.bed_y:                        # neues Bett
            beds.append(cur); cur = []; x = a.gap; y = a.gap; rowh = 0.0
        mm = m.copy(); mm.apply_translation([x, y, 0]); cur.append(mm)
        x += w + a.gap; rowh = max(rowh, d)
    if cur: beds.append(cur)

    man = []
    for i, bed in enumerate(beds):
        merged = trimesh.util.concatenate(bed)
        fn = f"{a.out}/bed_{i:02d}.stl"; merged.export(fn)
        e = merged.extents
        man.append(f"  bed_{i:02d}: {len(bed)} Teile, {e[0]:.0f}x{e[1]:.0f}x{e[2]:.0f} mm")
    print(f"{len(items)-len(skipped)} Teile -> {len(beds)} Betten ({a.out}/)")
    print("\n".join(man))
    if skipped: print(f"!! {len(skipped)} zu groß, übersprungen: {skipped[:6]}")
    open(f"{a.out}/BEDS.txt", "w").write("\n".join(man) + "\n")


if __name__ == "__main__":
    main()
