#!/usr/bin/env python3
"""element_compare.py — FORM-Abgleich pro Bauteil: legt Foto-Ausschnitt NEBEN Modell-Ausschnitt.

Lücke, die das aufdeckt: proportion_check misst nur Höhen, der Inventar-Juror nur Vollständigkeit
— die genaue FORM eines Elements (z.B. Fensterkopf gerundet vs. GESTUFT) fällt durch beide. Darum
jeden Loop die markanten Bauteile paarweise ZOOMEN und mit eigenen Augen vergleichen.

Aufruf: /tmp/rv/bin/python tools/element_compare.py <foto> <modell> <out.png> \
          name:fx0,fy0,fx1,fy1:mx0,my0,mx1,my1  [weitere ...]
Boxen als Bruchteile 0..1 der jeweiligen Bildbreite/-höhe.
"""
import sys
from PIL import Image, ImageDraw


def crop(img, box):
    w, h = img.size; x0, y0, x1, y1 = box
    return img.crop((int(w*x0), int(h*y0), int(w*x1), int(h*y1)))


def main():
    photo = Image.open(sys.argv[1]).convert("RGB")
    model = Image.open(sys.argv[2]).convert("RGB")
    out_path = sys.argv[3]
    specs = sys.argv[4:]
    CELL = 360; rows = []
    for sp in specs:
        name, fb, mb = sp.split(":")
        fbox = [float(v) for v in fb.split(",")]; mbox = [float(v) for v in mb.split(",")]
        pc = crop(photo, fbox); mc = crop(model, mbox)
        ph = CELL; pc = pc.resize((int(pc.width*ph/pc.height), ph)); mc = mc.resize((int(mc.width*ph/mc.height), ph))
        row = Image.new("RGB", (pc.width+mc.width+16, ph+26), (245, 245, 245))
        row.paste(pc, (0, 26)); row.paste(mc, (pc.width+16, 26))
        d = ImageDraw.Draw(row); d.text((4, 6), f"{name}:  FOTO | MODELL", fill=(0, 0, 0))
        rows.append(row)
    W = max(r.width for r in rows); H = sum(r.height for r in rows)+8*len(rows)
    out = Image.new("RGB", (W, H), (255, 255, 255)); y = 0
    for r in rows:
        out.paste(r, (0, y)); y += r.height+8
    out.save(out_path); print(f"-> {out_path}")


if __name__ == "__main__":
    main()
