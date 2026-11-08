#!/usr/bin/env python3
"""Kontaktbogen 6x4 Miniaturen mit Dateinamen. Aufruf: nubia_kontaktbogen.py AUS_JPG_PREFIX liste.txt  (Zeilen: key<TAB>beschriftung)"""
import sys, os
from PIL import Image, ImageDraw, ImageFont
CACHE = "/media/oem/TOSHIBA EXT/rc-park_auslagern/nubia_sortierung/cache"
def bogen(eintraege, ziel_prefix, titel="", spalten=6, zeilen=4, kw=300, kh=300):
    font = ImageFont.load_default()
    n = spalten * zeilen
    seiten = []
    for s in range(0, max(len(eintraege), 1), n):
        W, H = spalten * kw, zeilen * (kh + 28) + 24
        bild = Image.new("RGB", (W, H), (20, 20, 20))
        dr = ImageDraw.Draw(bild)
        dr.text((6, 6), f"{titel}  Blatt {s // n + 1}/{(len(eintraege) + n - 1) // n}", fill=(255, 255, 0), font=font)
        for i, (key, text) in enumerate(eintraege[s:s + n]):
            x, y = (i % spalten) * kw, 24 + (i // spalten) * (kh + 28)
            try:
                im = Image.open(f"{CACHE}/{key}.jpg"); im.thumbnail((kw - 4, kh))
                bild.paste(im, (x + 2 + (kw - 4 - im.width) // 2, y + (kh - im.height) // 2))
            except Exception:
                pass
            dr.text((x + 3, y + kh + 2), text[:46], fill=(230, 230, 230), font=font)
            dr.text((x + 3, y + kh + 13), text[46:92], fill=(180, 180, 180), font=font)
        p = f"{ziel_prefix}_{s // n + 1:02d}.jpg"
        bild.save(p, quality=82); seiten.append(p)
    return seiten
