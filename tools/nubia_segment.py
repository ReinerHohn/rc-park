#!/usr/bin/env python3
"""Stufe 3: SegFormer-B4 (ADE20k) auf den Miniaturen (CPU): Klassenanteile je Bild als Inhaltshinweis."""
import json, sys, numpy as np, torch
from PIL import Image
from transformers import SegformerForSemanticSegmentation, SegformerImageProcessor
AUS = "/media/oem/TOSHIBA EXT/rc-park_auslagern/nubia_sortierung"
torch.set_num_threads(20)
M = "nvidia/segformer-b4-finetuned-ade-512-512"
proc = SegformerImageProcessor.from_pretrained(M)
mod = SegformerForSemanticSegmentation.from_pretrained(M).eval()
id2 = mod.config.id2label
inv = [r for r in json.load(open(AUS + "/inventar_roh.json")) if r["ok"] and r["typ"] == "quelle"]
seen = {}
for r in inv: seen.setdefault(r["md5"], r)
out = {}
for n, r in enumerate(seen.values()):
    im = Image.open(f"{AUS}/cache/{r['key']}.jpg").convert("RGB")
    with torch.no_grad():
        x = proc(images=im, return_tensors="pt", size={"height": 384, "width": 384})
        lg = mod(**x).logits[0]
    lab = lg.argmax(0).numpy()
    h = lab.shape[0]
    fr = {}
    for i in np.unique(lab):
        fr[id2[int(i)]] = round(float((lab == i).mean()), 4)
    # obere / untere Bildhaelfte Himmel
    sky = [k for k, v in id2.items() if v == "sky"][0]
    fr["_sky_oben"] = round(float((lab[: h // 3] == int(sky)).mean()), 4)
    out[r["md5"]] = fr
    if n % 50 == 0: print(n, flush=True)
json.dump(out, open(AUS + "/segment.json", "w"))
print("fertig")
