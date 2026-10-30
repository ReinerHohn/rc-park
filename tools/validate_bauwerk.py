#!/usr/bin/env python3
"""validate_bauwerk.py — validiert ein BAUWERK-Modell gegen die Realität.

Für Gelände misst man Höhen-RMS (tools/validate_modell.py). Für ein BAUWERK ist
„gut" etwas anderes: stimmt die ARCHITEKTUR? Hier konkret für eine Bogenreihen-
Staumauer die Kern-Eigenschaft, an der v5 scheiterte: hat das Modell wirklich die
richtige Zahl OFFENER Bögen (Durchsichten) — oder ist es eine massive Wand?

Misst aus dem face-on-Render automatisch:
  * erkannte Bögen (Öffnungen)          -> Soll N (Default 13)
  * Öffnungs-Anteil (Durchsicht)        -> gesund 0.12..0.55 (0 = massive Wand!)
  * Seitenverhältnis L:H                -> Soll aus Maßen (143:25)
und legt Modell NEBEN das echte Foto (Mensch-Urteil + Beleg).

  python3 tools/validate_bauwerk.py --render daten/linach/bm_face.png \\
      --photo daten/linach/fotos/237.jpg --n 13 --L 143 --H 25
"""
import argparse, sys, numpy as np, trimesh
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.image as mpimg


def analyse_geom(stl, n_exp, L, H, tol_open=(0.12, 0.55), front_depth=2.5):
    """Öffnung GEOMETRISCH via Voxel: hat die LUFTSEITEN-FRONT an (x,z) Material?
    Kein Front-Material = Durchsicht/Bogen. Massive Wand = überall Front = 0 offen."""
    mesh = trimesh.load(stl, force="mesh")
    (x0, y0, z0), (x1, y1, z1) = mesh.bounds
    Lm, Hm = x1 - x0, z1 - z0
    pad = 0.06 * Lm
    from scipy.stats import binned_statistic_2d
    np.random.seed(0)                                      # reproduzierbar
    pts, _ = trimesh.sample.sample_surface(mesh, 400000)   # Oberflächen-Punkte (maßrobust)
    xb = np.arange(x0 + pad, x1 - pad, 0.5)
    zb = np.arange(z0 + 0.12*Hm, z0 + 0.92*Hm, 0.5)
    # frontnächste Materialtiefe (min y) je (x,z)-Zelle; NaN = gar kein Material
    miny, _, _, _ = binned_statistic_2d(pts[:, 0], pts[:, 2], pts[:, 1],
                                        statistic="min", bins=[xb, zb])
    openmap = np.zeros_like(miny, dtype=bool)
    for k in range(miny.shape[1]):                    # je Höhen-Zeile relativ zu den Pfeilern
        col = miny[:, k]
        good = np.isfinite(col)
        if good.sum() < 3:
            openmap[:, k] = True; continue
        ref = np.percentile(col[good], 10)            # Pfeiler = frontnächstes Material
        openmap[:, k] = ~good | (col > ref + front_depth)   # tiefer als Pfeiler = Durchsicht
    openness = openmap.mean()

    # Bögen zählen: x-Säule = Bogen, wenn über >40 % der Band-Höhe Durchsicht
    col_open = openmap.mean(axis=1) > 0.40
    d = np.diff(col_open.astype(int))
    n_arch = int((d == 1).sum()) + (1 if col_open[0] else 0)

    aspect = Lm / Hm; aspect_real = L / H
    def verd(ok): return "PASS" if ok else "FAIL"
    v_n = verd(abs(n_arch - n_exp) <= 1)
    v_o = verd(tol_open[0] <= openness <= tol_open[1])
    v_a = verd(abs(aspect/aspect_real - 1) < 0.25)
    print(f"  [{v_n}] offene Bögen (geometrisch): {n_arch}   (Soll {n_exp})")
    print(f"  [{v_o}] Durchsicht-Anteil: {openness:.2f}   "
          f"(gesund {tol_open[0]}..{tol_open[1]}; 0 = massive Wand)")
    print(f"  [{v_a}] Maße L×H {Lm:.0f}×{Hm:.0f} m  L:H {aspect:.1f} (Soll {aspect_real:.1f})")
    order = {"PASS": 0, "FAIL": 1}
    overall = max([v_n, v_o, v_a], key=lambda v: order[v])
    return overall, dict(n_arch=n_arch, openness=openness, aspect=aspect)


def composite(render, photo, out):
    fig, ax = plt.subplots(2, 1, figsize=(10, 6))
    ax[0].imshow(mpimg.imread(render)); ax[0].set_title("MODELL (face-on)", fontsize=10)
    if photo:
        ax[1].imshow(mpimg.imread(photo)); ax[1].set_title("REALITÄT (Foto)", fontsize=10)
    for a in ax: a.set_axis_off()
    fig.tight_layout(); fig.savefig(out, dpi=110); plt.close(fig)
    print("  Vergleich ->", out)


def main():
    ap = argparse.ArgumentParser(description="Bauwerk-Modell gegen Realität validieren")
    ap.add_argument("--stl", required=True, help="Bauwerk-Mesh (STL) — Geometrie-Check")
    ap.add_argument("--render", default="", help="face-on-Render fürs Foto-Vergleichsbild")
    ap.add_argument("--photo", default="", help="Referenz-Foto (optional, für Vergleich)")
    ap.add_argument("--n", type=int, default=13, help="erwartete Bogen-Anzahl")
    ap.add_argument("--L", type=float, default=143.0)
    ap.add_argument("--H", type=float, default=25.0)
    ap.add_argument("--open-lo", type=float, default=0.12, help="min gesunde Durchsicht "
                    "(Staumauer ~0.12, Viadukt ~0.45)")
    ap.add_argument("--open-hi", type=float, default=0.55, help="max gesunde Durchsicht "
                    "(Staumauer ~0.55, Viadukt ~0.80)")
    ap.add_argument("--out", default="/tmp/bauwerk_vergleich.png")
    a = ap.parse_args()
    print(f"=== BAUWERK-VALIDIERUNG  {a.stl} ===")
    overall, m = analyse_geom(a.stl, a.n, a.L, a.H, tol_open=(a.open_lo, a.open_hi))
    if a.render:
        composite(a.render, a.photo, a.out)
    print(f"  GESAMT: {overall}")
    sys.exit(0 if overall == "PASS" else 2)


if __name__ == "__main__":
    main()
