#!/usr/bin/env python3
"""druckbar_export.py — druckbare STL aus den Segment-STLs: Feindetail raus (→ Textur/Bemalung),
Rest vereinigen/verbinden, auf Druckmaßstab skalieren, Druckbarkeit prüfen (watertight, Wandstärke,
freischwebende Teile). Läuft in System-python3 (hat trimesh + manifold3d).

Lauf: python3 tools/druckbar_export.py [--scale 50] [--union]
"""
import sys, glob, os
import numpy as np, trimesh

ROOT = "/home/md/git/rc-park"
MDIR = f"{ROOT}/modelle/kaufhaus_freiburg"
SCALE = 1/50.
if "--scale" in sys.argv:
    SCALE = 1/float(sys.argv[sys.argv.index("--scale")+1])
# NUR-TEXTUR (nicht drucken → bemalt/Farbdruck): Waben-Bleiruten (0-mm-Stege) + Dach-Oberflächenmuster
# (Biberschwanz-Reihen + Rauten-Glasur) = reines Oberflächendekor, gehört auf die glatte Fläche als Farbe
TEXTURE_ONLY = {"sprossen", "dachmuster", "dachrauten"}
NOZZLE = 0.4
WALLMIN = 0.8                           # mm druckbar


def main():
    files = sorted(glob.glob(f"{MDIR}/khm_*.stl"))
    keep = []
    dropped = []
    for f in files:
        nm = os.path.basename(f).replace("khm_", "").replace(".stl", "")
        if nm in TEXTURE_ONLY:
            dropped.append(nm); continue
        keep.append((nm, trimesh.load(f, process=True)))
    asm = trimesh.util.concatenate([m for _, m in keep])
    asm.apply_scale(SCALE)
    out = f"{MDIR}/kaufhaus_druck_1zu{int(round(1/SCALE))}.stl"
    asm.export(out)
    ext = asm.extents*1000                        # mm
    print(f"Druck-STL: {out}")
    print(f"  Segmente behalten: {len(keep)}   nur-Textur weg: {sorted(dropped)}")
    print(f"  Bauraum @1:{int(round(1/SCALE))}: {ext.round(0)} mm  (B×T×H, Düse {NOZZLE}, druckbar ab {WALLMIN} mm)")
    print(f"  Faces gesamt: {len(asm.faces)}")
    # FREISCHWEBENDE TEILE: physische Verbundenheit grob über Voxel-Komponenten (im Druckmaßstab)
    pitch = max(1.5, ext.min()/40)
    try:
        vox = asm.voxelized(pitch=pitch).fill()
        from scipy import ndimage
        lbl, n = ndimage.label(vox.matrix)
        sizes = ndimage.sum(np.ones_like(lbl), lbl, range(1, n+1)) if n else []
        big = int((sizes > sizes.max()*0.01).sum()) if n else 0
        print(f"  Voxel-Verbund (pitch {pitch:.1f} mm): {n} Komponenten, davon {big} nennenswert")
        print(f"    → {'OK: alles 1 Stück' if big <= 1 else f'WARNUNG: {big} getrennte Blöcke (freischwebend?)'}")
    except Exception as e:
        print(f"  (Voxel-Check übersprungen: {e})")
    # thin-feature-Hinweis je Segment
    print("  dünnste Teile (mm im Druckmaßstab, <", WALLMIN, "= kritisch):")
    for nm, m in keep:
        comps = m.split(only_watertight=False)
        thin = min([c.extents.min() for c in comps])*SCALE*1000 if len(comps) else m.extents.min()*SCALE*1000
        if thin < WALLMIN:
            print(f"    {nm:<14} {thin:.2f} mm  ({len(comps)} Teile)")


if __name__ == "__main__":
    main()
