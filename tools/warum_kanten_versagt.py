#!/usr/bin/env python3
"""warum_kanten_versagt.py — BEWEIS, warum reine Kantendetektion ein Gebäude im Landschaftsfoto
NICHT sauber vermisst, und welcher Hebel es löst (ML-Szenen-Segmentierung).

Baut ein 4-Felder-Beweisblatt für EIN Foto:
  A  Original
  B  Canny-Kanten  (+ Zahl: wie viele starke Kanten gehören NICHT zum Gebäude)
  C  ADE20K-Semantik-Segmentierung (SegFormer): Himmel/Baum/Berg/Gebäude getrennt
  D  reine Gebäudemaske aus C  → saubere Silhouette → gemessene Breite/Höhe/Dachanteil

Kernaussage, die das Blatt belegt:
  - In B ersäuft die Fassadenstruktur in Tausenden Baum-/Schindel-/Berg-Kanten → kein robustes Raster.
  - Erst C/D trennen das Gebäude vom Hintergrund → DANN sind Silhouette & Dachanteil messbar.

Lauf:  /tmp/ml/bin/python tools/warum_kanten_versagt.py <foto> [--out blatt.png] [--model <hf-id>]
"""
import argparse
import numpy as np
import cv2

# ADE20K-Klassen-IDs (MIT 150 Klassen): die für Außen-Szenen relevanten
ADE = {"wall": 0, "building": 1, "sky": 2, "tree": 4, "road": 6, "grass": 9,
       "earth": 13, "house": 25, "field": 29, "path": 52, "mountain": 16,
       "hill": 68, "stairs": 53, "fence": 32, "signboard": 43}
GEBAEUDE = [ADE["building"], ADE["house"], ADE["wall"]]
HIMMEL = [ADE["sky"]]
NATUR = [ADE["tree"], ADE["grass"], ADE["mountain"], ADE["hill"], ADE["earth"], ADE["field"]]


def ade_segment(path, model_id):
    import torch
    from transformers import SegformerForSemanticSegmentation, SegformerImageProcessor
    from PIL import Image
    proc = SegformerImageProcessor.from_pretrained(model_id)
    model = SegformerForSemanticSegmentation.from_pretrained(model_id).eval()
    img = Image.open(path).convert("RGB"); W, H = img.size
    with torch.no_grad():
        inp = proc(images=img, return_tensors="pt")
        logits = model(**inp).logits
    up = torch.nn.functional.interpolate(logits, size=(H, W), mode="bilinear", align_corners=False)
    return up.argmax(1)[0].cpu().numpy().astype(np.int32)


def colorize(seg):
    rng = np.random.default_rng(7)
    lut = (rng.random((256, 3)) * 255).astype(np.uint8)
    for k, v in {"sky": (235, 206, 135), "tree": (40, 120, 40), "building": (30, 30, 200),
                 "house": (60, 60, 220), "wall": (90, 90, 230), "mountain": (110, 140, 150),
                 "road": (120, 120, 120), "grass": (90, 180, 90)}.items():
        lut[ADE[k]] = v
    return lut[np.clip(seg, 0, 255)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("foto")
    ap.add_argument("--out", default="/tmp/warum_kanten.png")
    ap.add_argument("--model", default="nvidia/segformer-b4-finetuned-ade-512-512")
    a = ap.parse_args()

    im = cv2.imread(a.foto); H, W = im.shape[:2]
    gray = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)

    # --- B: Canny + starke Hough-Linien, zählen wie viele AUSSERHALB der Gebäudemaske liegen ---
    edges = cv2.Canny(gray, 50, 150)
    canny_rgb = cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR)

    # --- C: ADE20K-Semantik ---
    seg = ade_segment(a.foto, a.model)
    seg_rgb = colorize(seg)[:, :, ::-1].copy()                      # zu BGR für cv2

    geb = np.isin(seg, GEBAEUDE).astype(np.uint8)
    sky = np.isin(seg, HIMMEL).astype(np.uint8)
    nat = np.isin(seg, NATUR).astype(np.uint8)
    # größte zusammenhängende Gebäudekomponente
    n, lab, stats, _ = cv2.connectedComponentsWithStats(
        cv2.morphologyEx(geb, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8)), 8)
    if n > 1:
        geb = (lab == 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))).astype(np.uint8)

    # --- Kennzahl: Anteil starker Kanten AUSSERHALB des Gebäudes (= Störkanten) ---
    edge_in = (edges > 0) & (geb > 0)
    edge_tot = (edges > 0).sum()
    frac_stoer = 1 - edge_in.sum() / max(1, edge_tot)

    # --- D: Gebäudemaske → Silhouette + Maße ---
    ys, xs = np.where(geb > 0)
    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    # Dach vs Wand INNERHALB der Maske: obere dunkle+texturierte Zone vs untere Wand
    colbot, coltop_wall = [], []
    roof_bound = []
    for x in range(x0, x1 + 1):
        col = np.where(geb[:, x] > 0)[0]
        if len(col) < 10:
            continue
        top, bot = col.min(), col.max()
        # Dach→Wand-Grenze = stärkster Hell-Anstieg in oberer Maskenhälfte
        seg_col = gray[top:bot, x].astype(float)
        if len(seg_col) > 8:
            gyc = np.gradient(cv2.GaussianBlur(seg_col.reshape(-1, 1), (1, 7), 0).ravel())
            mid = len(gyc)
            rb = top + int(np.argmax(gyc[: int(0.7 * mid)]))
            roof_bound.append(rb)
        colbot.append(bot)
    eave = float(np.median(roof_bound)) if roof_bound else (y0 + y1) / 2
    footy = float(np.percentile(colbot, 70)) if colbot else y1
    roof_frac = (eave - y0) / max(1, (footy - y0))

    mask_rgb = im.copy()
    mask_rgb[geb == 0] = (mask_rgb[geb == 0] * 0.25).astype(np.uint8)  # Hintergrund abdunkeln
    cv2.rectangle(mask_rgb, (x0, y0), (x1, int(footy)), (0, 255, 255), 2)
    cv2.line(mask_rgb, (x0, int(eave)), (x1, int(eave)), (0, 255, 0), 2)
    cv2.putText(mask_rgb, f"Dachanteil {roof_frac:.2f}  B/H {(x1-x0)/max(1,footy-y0):.2f}",
                (x0 + 5, int(footy) - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)

    # --- Beweisblatt zusammensetzen ---
    def lab_(img, t):
        img = img.copy(); cv2.rectangle(img, (0, 0), (W, 30), (0, 0, 0), -1)
        cv2.putText(img, t, (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2); return img
    cv2.putText(canny_rgb, f"Stoerkanten ausserhalb Gebaeude: {frac_stoer*100:.0f}%",
                (8, H - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 165, 255), 2)
    A = lab_(im, "A  Original")
    B = lab_(canny_rgb, "B  Canny-Kanten (reine Kantendetektion)")
    C = lab_(seg_rgb, "C  ML-Szenen-Segmentierung (SegFormer ADE20K)")
    D = lab_(mask_rgb, "D  reine Gebaeudemaske -> messbar")
    top = np.hstack([A, B]); bot = np.hstack([C, D])
    sheet = np.vstack([top, bot])
    cv2.imwrite(a.out, sheet)
    print(f"Foto {a.foto} ({W}x{H})")
    print(f"  Canny: {edge_tot} Kantenpixel, davon {frac_stoer*100:.0f}% AUSSERHALB des Gebaeudes (Baum/Berg/Himmel)")
    print(f"  ML-Maske: Gebaeude {geb.mean()*100:.0f}% der Pixel, Dachanteil {roof_frac:.2f}, B/H {(x1-x0)/max(1,footy-y0):.2f}")
    print(f"-> {a.out}")


if __name__ == "__main__":
    main()
