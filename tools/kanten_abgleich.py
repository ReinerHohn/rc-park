#!/usr/bin/env python3
"""kanten_abgleich.py — ZENTRALE automatische Kanten-Gate: Struktur-Kanten Foto↔Modell je Region.

Prinzip (gehärtet): die markanten Kanten eines Bauwerks sind die GRENZEN zwischen Farbzonen
(Wand↔Gold-Zier↔dunkle Öffnung↔Dach), NICHT die Grautonkanten (die ersaufen in Textur wie Waben/
Schuppen). Also: beide Bilder in Zonen klassifizieren → Zonengrenzen = Strukturkanten → je Region
fein ausrichten (Shift-Suche) → Recall/Precision + Overlay. Wo ROT ohne Gelb: Kante im Foto, die dem
Modell FEHLT. Läuft über die GANZE Fassade (Regionen-Sweep) → nichts rutscht durch.

Lauf:
  Sweep:   python3 tools/kanten_abgleich.py --sweep <foto.jpg> <modell_render.png> [out_dir]
  Einzeln: python3 tools/kanten_abgleich.py <foto_crop.png> <modell_crop.png> [out.png]
"""
import sys, os
import numpy as np
from PIL import Image
from scipy import ndimage


def classify(a):
    """Pixel → Zone: 0 bg/Himmel, 1 Wand(rot), 2 Zier(gold), 3 Öffnung(dunkel), 4 Dach(grün)."""
    r, g, b = a[:, :, 0].astype(int), a[:, :, 1].astype(int), a[:, :, 2].astype(int)
    lab = np.zeros(a.shape[:2], np.uint8)
    dark = (r < 95) & (g < 100) & (b < 115)
    green = (g >= r-5) & (g > b+6) & (g > 55)
    gold = (r > 120) & (g > 100) & (r > b+25) & (g > b+12) & ~green
    red = (r > g+14) & (r > b+8) & (r > 60)
    bg = (r > 200) & (g > 200) & (b > 200)
    lab[red] = 1; lab[green] = 4; lab[gold] = 2; lab[dark] = 3; lab[bg] = 0
    return lab


def struct_edges(lab):
    """Zonengrenzen = Strukturkanten (Label wechselt zum Nachbarn)."""
    e = np.zeros_like(lab, bool)
    e[:-1] |= lab[:-1] != lab[1:]
    e[:, :-1] |= lab[:, :-1] != lab[:, 1:]
    e &= (lab != 0)                                  # Grenzen am Himmel/bg ignorieren
    return e


def best_shift(ref, mov, frac=0.08):
    """kleine Translationssuche: Shift von mov, der die Kanten-Überdeckung mit ref maximiert."""
    H, W = ref.shape; sy = int(H*frac); sx = int(W*frac); best = (0, 0, -1)
    rd = ndimage.distance_transform_edt(~ref)
    for dy in range(-sy, sy+1, max(1, sy//6)):
        for dx in range(-sx, sx+1, max(1, sx//6)):
            m = np.roll(np.roll(mov, dy, 0), dx, 1)
            score = float((m & (rd <= 3)).sum()) / max(1, m.sum())
            if score > best[2]:
                best = (dy, dx, score)
    return best[0], best[1]


def compare(pc, mc, size=(300, 400), tol=4):
    pe = struct_edges(classify(np.asarray(pc.convert("RGB").resize(size))))
    me = struct_edges(classify(np.asarray(mc.convert("RGB").resize(size))))
    dy, dx = best_shift(pe, me)
    me = np.roll(np.roll(me, dy, 0), dx, 1)
    pd = ndimage.distance_transform_edt(~pe); md = ndimage.distance_transform_edt(~me)
    recall = float((pe & (md <= tol)).sum())/max(1, pe.sum())
    prec = float((me & (pd <= tol)).sum())/max(1, me.sum())
    H, W = size[1], size[0]; ov = (np.asarray(pc.convert("L").resize(size))[:, :, None]//3).repeat(3, 2).astype(np.uint8)
    ov[pe] = [255, 40, 40]; ov[me] = [40, 220, 40]; ov[pe & (md <= tol)] = [240, 240, 40]
    return recall, prec, Image.fromarray(ov), (pe & (md > tol))


def tight_building(img, is_model):
    a = np.asarray(img.convert("RGB"))
    if is_model:
        g = a.sum(2); ys, xs = np.where(g < 720)              # nicht-weiß
    else:
        lab = classify(a); ys, xs = np.where(ndimage.binary_opening(lab == 4, iterations=2))  # grünes Dach
        if len(xs) < 20:
            ys, xs = np.where(lab != 0)
    if len(xs) < 20:
        return img
    x0, x1 = xs.min(), xs.max()
    # nach unten bis zur untersten roten Zeile (Fassade) erweitern
    lab = classify(a); red = lab == 1
    rr = np.where(red[:, x0:x1].mean(1) > 0.15)[0]
    y0 = ys.min(); y1 = rr.max() if len(rr) else ys.max()
    return img.crop((x0, y0, x1, y1))


REGIONS = {                                                   # Bruchteile der Gebäude-BBox (x0,y0,x1,y1)
    "Dach+Gauben": (0.06, 0.0, 0.94, 0.34),
    "Statuen+Baldachine": (0.12, 0.30, 0.88, 0.50),
    "Fenster": (0.12, 0.44, 0.88, 0.63),
    "Balkon": (0.08, 0.60, 0.92, 0.72),
    "Arkade": (0.04, 0.70, 0.96, 0.99),
    "Erker-links": (0.0, 0.18, 0.18, 0.68),
    "Erker-rechts": (0.82, 0.18, 1.0, 0.68),
}


def main():
    if "--sweep" in sys.argv:
        i = sys.argv.index("--sweep"); foto, modell = sys.argv[i+1], sys.argv[i+2]
        outdir = sys.argv[i+3] if len(sys.argv) > i+3 else "/tmp/kanten_sweep"
        os.makedirs(outdir, exist_ok=True)
        pb = tight_building(Image.open(foto), False); mb = tight_building(Image.open(modell), True)
        PW, PH = pb.size; MW, MH = mb.size
        print(f"{'Region':<22}{'Recall':>8}{'Prec':>7}  Urteil")
        rows = []
        for name, (x0, y0, x1, y1) in REGIONS.items():
            pc = pb.crop((int(PW*x0), int(PH*y0), int(PW*x1), int(PH*y1)))
            mc = mb.crop((int(MW*x0), int(MH*y0), int(MW*x1), int(MH*y1)))
            rec, pre, ov, _ = compare(pc, mc)
            v = "PASS" if rec >= 0.6 else ("ok" if rec >= 0.45 else "WARN fehlende Kanten")
            ov.save(f"{outdir}/{name}.png")
            print(f"{name:<22}{rec:>8.2f}{pre:>7.2f}  {v}")
            rows.append((name, rec))
        worst = min(rows, key=lambda r: r[1])
        print(f"\nOverlays: {outdir}/   schwächste Region: {worst[0]} (Recall {worst[1]:.2f})")
    else:
        fp, mp = sys.argv[1], sys.argv[2]
        out = sys.argv[3] if len(sys.argv) > 3 else "/tmp/kanten_overlay.png"
        rec, pre, ov, _ = compare(Image.open(fp), Image.open(mp)); ov.save(out)
        print(f"Recall {rec:.2f}  Precision {pre:.2f}  → {out}  ({'PASS' if rec>=0.6 else 'WARN'})")


if __name__ == "__main__":
    main()
