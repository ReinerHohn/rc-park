#!/usr/bin/env python3
"""gebaeude_segment.py — Schritt ① der Bau-Pipeline: GEBÄUDE per ML-Szenen-Segmentierung vom
Hintergrund (Bäume/Berg/Himmel/Straße) freistellen (SegFormer ADE20K), damit DANACH überhaupt
sauber gemessen werden kann. Generisch für jedes Landschafts-Gebäudefoto.

Liefert:
  - <stem>_mask.png     binäre Gebäudemaske (größte Komponente)
  - <stem>_silhouette.json  { x0,x1,top,bottom (px), aspect_w_h, roof_bumps_x_frac[], ... }
  - <stem>_seg.png      eingefärbte Semantik (zum Prüfen)

roof_bumps = lokale Hochpunkte der oberen Silhouette = Zwerchhäuser/Kamine → Gauben-X-Positionen.

Lauf:  /tmp/ml/bin/python tools/gebaeude_segment.py <foto> [--model <hf-id>] [--outdir DIR]
"""
import argparse, json, os
import numpy as np
import cv2

ADE = {"wall": 0, "building": 1, "sky": 2, "tree": 4, "road": 6, "grass": 9,
       "earth": 13, "mountain": 16, "house": 25, "field": 29, "hill": 68, "path": 52}
GEBAEUDE = [ADE["building"], ADE["house"], ADE["wall"]]


_MODEL = {}


def _load(model_id):
    if model_id not in _MODEL:
        import torch
        from transformers import SegformerForSemanticSegmentation, SegformerImageProcessor
        _MODEL[model_id] = (SegformerImageProcessor.from_pretrained(model_id),
                            SegformerForSemanticSegmentation.from_pretrained(model_id).eval(), torch)
    return _MODEL[model_id]


def ade_segment(path, model_id):
    from PIL import Image
    proc, model, torch = _load(model_id)                       # Modell nur EINMAL laden (Batch)
    img = Image.open(path).convert("RGB"); W, H = img.size
    with torch.no_grad():
        logits = model(**proc(images=img, return_tensors="pt")).logits
    up = torch.nn.functional.interpolate(logits, size=(H, W), mode="bilinear", align_corners=False)
    return up.argmax(1)[0].cpu().numpy().astype(np.int32)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("foto", nargs="+", help="ein oder MEHRERE Fotos (verschiedene Perspektiven)")
    ap.add_argument("--model", default="nvidia/segformer-b4-finetuned-ade-512-512")
    ap.add_argument("--outdir", default=None)
    a = ap.parse_args()
    results = []
    for foto in a.foto:
        try:
            results.append(process(foto, a.model, a.outdir))
        except Exception as e:
            print(f"[skip] {foto}: {e}")
    print(f"\n=== {len(results)} Ansichten extrahiert ===")
    for r in results:
        print(f"  {os.path.basename(r['foto']):18s} Geb {r['geb_pixel_frac']*100:4.0f}%  "
              f"B/H {r['aspect_w_h']:.2f}  Dach-Hochpunkte {r['roof_bumps_x_frac']}")


def process(foto, model_id, outdir=None):
    stem = os.path.splitext(os.path.basename(foto))[0]
    outdir = outdir or os.path.dirname(foto)

    im = cv2.imread(foto); H, W = im.shape[:2]
    seg = ade_segment(foto, model_id)

    geb = np.isin(seg, GEBAEUDE).astype(np.uint8)
    geb = cv2.morphologyEx(geb, cv2.MORPH_CLOSE, np.ones((11, 11), np.uint8))
    geb = cv2.morphologyEx(geb, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    n, lab, stats, _ = cv2.connectedComponentsWithStats(geb, 8)
    if n > 1:
        geb = (lab == 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))).astype(np.uint8)

    ys, xs = np.where(geb > 0)
    x0, x1, top, bot = int(xs.min()), int(xs.max()), int(ys.min()), int(ys.max())
    Wpx, Hpx = x1 - x0, bot - top

    # obere Silhouette pro Spalte (Dach-/Firstlinie) → Hochpunkte = Zwerchhäuser/Kamine
    sil = np.full(x1 - x0 + 1, np.nan)
    for i, x in enumerate(range(x0, x1 + 1)):
        col = np.where(geb[:, x] > 0)[0]
        if len(col):
            sil[i] = col.min()
    sil = cv2.GaussianBlur(sil.reshape(-1, 1).astype(np.float32), (1, 9), 0).ravel()
    h_above = (np.nanmedian(sil) - sil)                       # wie weit die Silhouette über dem Median hochragt
    thr = 0.18 * (np.nanmedian(sil) - np.nanmin(sil) + 1e-6)
    bumps, i = [], 1
    while i < len(h_above) - 1:
        if h_above[i] > thr and h_above[i] >= h_above[i - 1] and h_above[i] > h_above[i + 1]:
            bumps.append(i); i += max(1, int(0.04 * Wpx))
        else:
            i += 1
    roof_bumps = [round(b / Wpx, 3) for b in bumps]

    mask = (geb * 255).astype(np.uint8)
    cv2.imwrite(f"{outdir}/{stem}_mask.png", mask)

    # Semantik eingefärbt
    rng = np.random.default_rng(7); lut = (rng.random((256, 3)) * 255).astype(np.uint8)
    for k, v in {"sky": (135, 206, 235), "tree": (40, 120, 40), "building": (200, 30, 30),
                 "house": (220, 60, 60), "wall": (230, 90, 90), "mountain": (150, 140, 110),
                 "road": (120, 120, 120), "grass": (90, 180, 90)}.items():
        lut[ADE[k]] = v
    cv2.imwrite(f"{outdir}/{stem}_seg.png", lut[np.clip(seg, 0, 255)][:, :, ::-1])

    sil_json = {
        "foto": foto, "img_wh": [W, H],
        "x0": x0, "x1": x1, "top": top, "bottom": bot,
        "width_px": Wpx, "height_px": Hpx,
        "aspect_w_h": round(Wpx / max(1, Hpx), 3),
        "roof_bumps_x_frac": roof_bumps,
        "geb_pixel_frac": round(float(geb.mean()), 3),
        "quelle": f"SegFormer ADE20K ({model_id}); groesste Gebaeudekomponente",
    }
    with open(f"{outdir}/{stem}_silhouette.json", "w") as f:
        json.dump(sil_json, f, indent=2, ensure_ascii=False)
    print(f"-> {stem}: mask+silhouette+seg (B/H {sil_json['aspect_w_h']}, Geb {sil_json['geb_pixel_frac']*100:.0f}%)")
    return sil_json


if __name__ == "__main__":
    main()
