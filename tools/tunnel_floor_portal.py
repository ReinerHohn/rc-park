#!/usr/bin/env python3
"""tunnel_floor_portal.py — GLEISBETT (ganze Trasse) + PORTAL-GALERIE (Eingang) als Laser-Teile.

Aus der echten Trasse (mx,my,mz,is_tunnel):
  1) GLEISBETT = flaches Band (Breite --bw) entlang des Plan-Verlaufs; fällt in die Lichtraum-
     Löcher der Rippen (ruht auf deren Unterkante). Mittellinie + Rippen-Kreuzungen graviert
     -> Kork + N-Flexgleis exakt drauflegen. Bei Überlänge in Segmente geteilt.
  2) STEINSCHLAGGALERIE am Ostportal = flacher Kasten (Dach + 2 Seitenwände mit Öffnungen +
     Stirn-Portalrahmen), prototypgetreu fürs Höllental.

  python3 tools/tunnel_floor_portal.py --track daten/hoellental/hoellental_track.npy \
      --out modelle/hirschsprung_geruest/tunnel --gcode
"""
import argparse, os, sys, numpy as np, matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from terrain_eggcrate import rib_positions
from laser_relief_kit import glyph_strokes, svg_write, gcode_write
from scipy.ndimage import gaussian_filter


def resample(pts, step=2.0):
    out = [pts[0]]
    for i in range(len(pts)-1):
        a, b = pts[i], pts[i+1]; d = np.hypot(*(b-a)); n = max(1, int(d/step))
        for k in range(1, n+1): out.append(a + (b-a)*k/n)
    return np.array(out)


def ribbon(cl, bw):
    """Band-Polygon (Breite bw) entlang Mittellinie cl (Nx2)."""
    d = np.gradient(cl, axis=0); t = d/np.maximum(np.hypot(d[:, 0], d[:, 1])[:, None], 1e-9)
    n = np.column_stack([-t[:, 1], t[:, 0]])
    left = cl + n*bw/2; right = cl - n*bw/2
    return np.vstack([left, right[::-1], left[:1]])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--track", default="daten/hoellental/hoellental_track.npy")
    ap.add_argument("--dem", default="daten/hoellental/dgm025_full.npy")
    ap.add_argument("--mm", type=float, default=1.5625); ap.add_argument("--nscale", type=float, default=6.25)
    ap.add_argument("--r0", type=int, default=470); ap.add_argument("--r1", type=int, default=640)
    ap.add_argument("--c0", type=int, default=3310); ap.add_argument("--c1", type=int, default=3570)
    ap.add_argument("--vscale", type=float, default=0.85); ap.add_argument("--base", type=float, default=12.0)
    ap.add_argument("--bw", type=float, default=22.0, help="Gleisbett-Breite mm (N-Bett ~20-22)")
    ap.add_argument("--clear-w", type=float, default=30.0); ap.add_argument("--clear-h", type=float, default=36.0)
    ap.add_argument("--gal-len", type=float, default=48.0, help="Länge der Portal-Galerie mm")
    ap.add_argument("--thick", type=float, default=3.0); ap.add_argument("--bed-x", type=float, default=390)
    ap.add_argument("--gcode", action="store_true")
    ap.add_argument("--feed", type=float, default=300); ap.add_argument("--power", type=float, default=100)
    ap.add_argument("--passes", type=int, default=4); ap.add_argument("--eng-power", type=float, default=20)
    ap.add_argument("--out", default="/tmp/tunnel")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    # Rippen-Positionen (für Kreuzungs-Gravur) aus gleichem Fenster
    win = np.load(a.dem)[a.r0:a.r1, a.c0:a.c1].astype(float); win = np.where(win < -1000, np.nan, win)
    if np.isnan(win).any(): win = np.where(np.isnan(win), np.nanmin(win), win)
    Hf = gaussian_filter(win[::-1]-np.nanmin(win), 0.6)*a.nscale*a.vscale + a.base
    cell = a.mm; NY, NX = Hf.shape; Wx, Dy = NX*cell, NY*cell
    xpos, ypos = rib_positions(Hf, cell, 22, 18, 7.0)

    tr = np.load(a.track); cl = resample(tr[:, :2], 2.0)
    s = np.concatenate([[0], np.cumsum(np.hypot(np.diff(cl[:, 0]), np.diff(cl[:, 1])))])
    Ltot = s[-1]

    # --- GLEISBETT ---
    bett = ribbon(cl, a.bw)
    # Rippen-Kreuzungen als Quer-Ticks (Gravur) + Mittellinie
    eng = [cl]                                                # Mittellinie
    def crossings(coord_fn, vals):
        out = []
        for v in vals:
            f = coord_fn(cl)
            sign = f - v
            for i in range(len(sign)-1):
                if sign[i] == 0 or sign[i]*sign[i+1] < 0:
                    p = cl[i]; d = np.gradient(cl, axis=0)[i]; t = d/max(np.hypot(*d), 1e-9)
                    n = np.array([-t[1], t[0]]); out.append(np.array([p-n*a.bw/2, p+n*a.bw/2]))
        return out
    ticks = crossings(lambda c: c[:, 0], xpos) + crossings(lambda c: c[:, 1], ypos)
    eng += ticks
    # in Segmente (falls länger als Bett) — hier 1 Stück (356<390)
    segments = []
    if Ltot <= a.bed_x: segments = [(0, len(cl)-1)]
    else:
        step = a.bed_x*0.95; cut = list(np.searchsorted(s, np.arange(step, Ltot, step)))
        bnds = [0]+cut+[len(cl)-1]; segments = list(zip(bnds[:-1], bnds[1:]))

    bett_parts = []
    for si, (i0, i1) in enumerate(segments):
        seg_cl = cl[i0:i1+1]; poly = ribbon(seg_cl, a.bw)
        mn = poly.min(0); poly = poly - mn
        segeng = [seg_cl - mn] + [t - mn for t in ticks if (seg_cl[:, 0].min()-2 <= t[:, 0].mean() <= seg_cl[:, 0].max()+2)]
        segeng += glyph_strokes(f"GLEISBETT {si+1}", 4, a.bw+3, h=6)
        svg_write(f"{a.out}/gleisbett_{si+1}.svg", [poly], [], [], segeng, 0)
        if a.gcode: gcode_write(f"{a.out}/gleisbett_{si+1}.gcode", [poly], [], [], segeng, 0, a.feed, a.power, a.passes, a.eng_power)
        bett_parts.append(poly)

    # --- STEINSCHLAGGALERIE am Ostportal (letzter Tunnelpunkt) ---
    tun = tr[:, 3] > 0.5; pi = np.where(tun)[0][-1]
    GL, CW, CH, th = a.gal_len, a.clear_w, a.clear_h, a.thick
    # Seitenwand (talseitig) mit 3 Pfeiler-Öffnungen
    def wall_openings():
        op = int(3); pil = GL/(op*2+1)
        holes = []
        for k in range(op):
            x0 = pil*(2*k+1); holes.append([(x0, CH*0.18), (x0+pil, CH*0.18), (x0+pil, CH*0.82), (x0, CH*0.82), (x0, CH*0.18)])
        return holes
    wall = [(0, 0), (GL, 0), (GL, CH), (0, CH), (0, 0)]
    dach = [(0, 0), (GL, 0), (GL, CW+2*th), (0, CW+2*th), (0, 0)]
    # Stirn-Portalrahmen (Steinring) mit Lichtraum-Loch
    fr = 8.0
    stirn = [(0, 0), (CW+2*th+2*fr, 0), (CW+2*th+2*fr, CH+fr), (0, CH+fr), (0, 0)]
    stirn_hole = [(fr+th, 0), (fr+th+CW, 0), (fr+th+CW, CH), (fr+th, CH), (fr+th, 0)]
    panels = [("galerie_wand_tal", [wall], wall_openings(), "Seitenwand talseitig (Öffnungen)"),
              ("galerie_wand_berg", [wall], [], "Seitenwand bergseitig"),
              ("galerie_dach", [dach], [], "Galerie-Dach"),
              ("galerie_stirn", [stirn, stirn_hole], [], "Stirn/Portalrahmen (Lichtraum-Loch)")]
    for nm, polys, extra, desc in panels:
        allp = polys + extra; mn = np.vstack([np.array(p) for p in allp]).min(0)
        cuts = [np.array(p)-mn for p in allp]
        eg = glyph_strokes(nm.split("_")[-1][:6], 3, 3, h=5)
        svg_write(f"{a.out}/{nm}.svg", cuts, [], [], eg, 0)
        if a.gcode: gcode_write(f"{a.out}/{nm}.gcode", cuts, [], [], eg, 0, a.feed, a.power, a.passes, a.eng_power)

    # --- Vorschau Plan: Gelände + Trasse + Bett + Portal ---
    from matplotlib.colors import LightSource
    fig, ax = plt.subplots(figsize=(12, 12*Dy/Wx))
    ls = LightSource(315, 45)
    ax.imshow(ls.hillshade(Hf, dx=cell, dy=cell), cmap="gray", origin="lower", extent=[0, Wx, 0, Dy])
    ax.imshow(Hf, cmap="terrain", alpha=0.4, origin="lower", extent=[0, Wx, 0, Dy])
    for xr in xpos: ax.axvline(xr, color="saddlebrown", lw=0.4, alpha=0.5)
    for yr in ypos: ax.axhline(yr, color="saddlebrown", lw=0.4, alpha=0.5)
    bp = ribbon(cl, a.bw); ax.fill(bp[:, 0], bp[:, 1], fc="#555", ec="k", lw=0.6, alpha=0.8, label="Gleisbett (ganze Trasse)")
    ax.plot(cl[:, 0], cl[:, 1], "w--", lw=0.8)
    for t in ticks: ax.plot(t[:, 0], t[:, 1], "yellow", lw=0.8)
    ax.plot(tr[pi, 0], tr[pi, 1], "rs", ms=12); ax.annotate("PORTAL-GALERIE", (tr[pi, 0], tr[pi, 1]),
             color="red", fontsize=11, weight="bold", xytext=(tr[pi, 0]-130, tr[pi, 1]+25), arrowprops=dict(color="red", arrowstyle="->"))
    ax.set_xlim(0, Wx); ax.set_ylim(0, Dy); ax.set_aspect("equal"); ax.legend(loc="upper right")
    ax.set_title(f"GLEISBETT {a.bw:.0f}mm über ganze Trasse ({Ltot:.0f}mm) + Steinschlaggalerie am Ostportal\ngelb=Rippen-Kreuzung (fällt ins Lichtraum-Loch)")
    plt.tight_layout(); plt.savefig(f"{a.out}/_plan.png", dpi=105); plt.close(fig)

    man = [f"TUNNEL-KIT  Trasse {Ltot:.0f}mm, Gleisbett {a.bw:.0f}mm, Lichtraum {CW:.0f}x{CH:.0f}",
           f"Gleisbett: {len(bett_parts)} Segment(e) -> gleisbett_N.svg (fällt in die Rippen-Löcher, Mittellinie+Kreuzungen graviert)",
           f"Portal-Galerie (Ostportal {tr[pi,0]:.0f},{tr[pi,1]:.0f}): 4 Platten (Dach, 2 Wände, Stirnrahmen), Länge {GL:.0f}mm",
           "MONTAGE: Gleisbett in die Lichtraum-Löcher legen -> Kork+N-Flexgleis drauf. Galerie am Portal aufkleben, innen schwarz."]
    open(f"{a.out}/MANIFEST.txt", "w").write("\n".join(man)+"\n")
    print("\n".join(man)); print(f"\n-> {os.path.abspath(a.out)}/  (_plan.png + SVG" + (" + gcode" if a.gcode else "") + ")")


if __name__ == "__main__":
    main()
