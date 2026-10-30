#!/usr/bin/env python3
"""foto_modell_vergleich.py — FAIRER Foto↔Modell-Vergleich (generisch).

Skaliert BEIDE Bilder auf dieselbe FASSADENHÖHE (Traufe→Boden) und stellt sie bodenbündig
nebeneinander — so sind Proportionen (Dachanteil, Geschosse) direkt vergleichbar, unabhängig
vom Rand/Crop. Traufe = Oberkante der (hellen) Putzfassade, Boden = unterste Bauwerkszeile.

  python3 tools/foto_modell_vergleich.py <foto> <render.png> <out.png> [foto_cropfrac x0,x1]
"""
import sys
import numpy as np
from PIL import Image, ImageDraw


def eave_ground(img):
    A = np.asarray(img.convert("RGB")); R, G, B = (A[:, :, i].astype(int) for i in range(3))
    cream = (R > 150) & (G > 140) & (R > B + 18) & ((R + G) > 1.9 * B)
    nonbg = (A < 245).any(2)
    ys = np.where(nonbg.any(1))[0]
    if not len(ys):
        return 0, img.height - 1
    bot = int(ys.max())
    cs = cream.sum(1)
    cy = np.where(cs > cs.max() * 0.5)[0] if cs.max() else []
    eave = int(cy.min()) if len(cy) else int(ys.min())
    return eave, bot


def tight_x(img):
    A = np.asarray(img.convert("RGB")); nb = (A < 245).any(2)
    xs = np.where(nb.any(0))[0]
    return img.crop((max(xs.min() - 5, 0), 0, min(xs.max() + 5, img.width), img.height)) if len(xs) else img


def main():
    foto = Image.open(sys.argv[1]).convert("RGB")
    ren = tight_x(Image.open(sys.argv[2]).convert("RGB"))
    out = sys.argv[3]
    if len(sys.argv) > 4:
        x0, x1 = [float(v) for v in sys.argv[4].split(",")]
        foto = foto.crop((int(x0 * foto.width), 0, int(x1 * foto.width), foto.height))
    TH = 600
    res = []
    for im in (foto, ren):
        e, b = eave_ground(im)
        s = TH / max(b - e, 10)
        res.append((im.resize((max(int(im.width * s), 1), int(im.height * s))), int(e * s), int(b * s)))
    canH = max(b for _, _, b in res) + 40
    panels = []
    for im, e2, b2 in res:
        c = Image.new("RGB", (im.width, canH), (255, 255, 255))
        c.paste(im, (0, (canH - 20) - b2))
        d = ImageDraw.Draw(c); d.line((0, (canH - 20) - b2 + e2, im.width, (canH - 20) - b2 + e2), fill=(0, 175, 0), width=2)
        panels.append(c)
    W = sum(p.width for p in panels) + 40
    cmp = Image.new("RGB", (W, canH), (255, 255, 255))
    cmp.paste(panels[0], (0, 0)); cmp.paste(panels[1], (panels[0].width + 40, 0))
    cmp.save(out)
    print(f"-> {out}  (Foto Trauf→Boden {res[0][2]-res[0][1]}px, Modell {res[1][2]-res[1][1]}px, beide auf {TH})")


if __name__ == "__main__":
    main()
