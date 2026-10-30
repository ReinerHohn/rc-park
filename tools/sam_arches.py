#!/usr/bin/env python3
"""sam_arches.py — saubere Bogen-Masken via SAM (Segment Anything), dann measure_arch
auf ALLE Bögen → volle Geometrie (Bogenzahl, Stich:Spann, Pfeiler:Spann, Feldteilung,
absolute Meter). Löst das Erkennungsproblem im unruhigen Natur-Foto.

Lauf (im venv mit torch):
  /tmp/samenv/bin/python tools/sam_arches.py --img daten/ravenna/fotos/rv_panorama.jpg \
      --ckpt /tmp/sam_vit_b.pth --span-m 20 --out /tmp/rv_sam.png
"""
import argparse, sys, os
import numpy as np, cv2
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from foto_metrologie import measure_arch


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--img", required=True)
    ap.add_argument("--ckpt", default="/tmp/sam_vit_b.pth")
    ap.add_argument("--model", default="vit_b")
    ap.add_argument("--span-m", type=float, default=0.0)
    ap.add_argument("--long", type=int, default=1536, help="Bild-Langseite für SAM (CPU)")
    ap.add_argument("--out", default="/tmp/rv_sam.png")
    a = ap.parse_args()

    import torch
    from segment_anything import sam_model_registry, SamAutomaticMaskGenerator
    img = cv2.imread(a.img)
    H0, W0 = img.shape[:2]
    s = a.long / max(H0, W0)
    img = cv2.resize(img, (int(W0*s), int(H0*s)))
    H, W = img.shape[:2]
    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    print(f"SAM {a.model} lädt … (CPU)")
    sam = sam_model_registry[a.model](checkpoint=a.ckpt)
    sam.to("cpu")
    gen = SamAutomaticMaskGenerator(sam, points_per_side=32,
                                    pred_iou_thresh=0.86, stability_score_thresh=0.90,
                                    min_mask_region_area=int(0.002*H*W))
    masks = gen.generate(rgb)
    print(f"SAM-Masken: {len(masks)}")

    # Masken → Bögen: measure_arch, nur Halbkreis + guter Fit + nicht randberührend
    arches = []
    for m in masks:
        seg = m["segmentation"].astype(np.uint8)
        cnts, _ = cv2.findContours(seg, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        if not cnts:
            continue
        c = max(cnts, key=cv2.contourArea)[:, 0, :]
        x, y, w, h = cv2.boundingRect(c.reshape(-1, 1, 2))
        if x <= 2 or x+w >= W-2 or w < 0.02*W:
            continue
        mm = measure_arch(c)
        if not mm or not mm["semicircle"] or mm["rms_frac"] > 0.03:
            continue
        # Öffnung ist dunkel (Durchsicht) — nicht ein heller Steinblock
        if rgb[seg > 0].mean() > 150:
            continue
        mm["segmentation"] = seg.astype(bool)
        arches.append(mm)
    # Dedupe (überlappende cx)
    arches.sort(key=lambda d: d["cx"]); dedup = []
    for d in arches:
        if not dedup or d["cx"] - dedup[-1]["cx"] > 0.4*d["span"]:
            dedup.append(d)
    arches = dedup
    print(f"Bögen (SAM + measure_arch): {len(arches)}")

    vis = img.copy()
    overlay = img.copy()
    for d in arches:
        if "segmentation" in d:
            overlay[d["segmentation"]] = (0, 180, 0)
    vis = cv2.addWeighted(overlay, 0.28, vis, 0.72, 0)   # SAM-Masken translucent grün
    for i, d in enumerate(arches):
        cx, cy, R, span = int(d["cx"]), int(d["cy"]), int(d["R"]), d["span"]
        cv2.ellipse(vis, (cx, cy), (R, R), 0, 180, 360, (255, 255, 0), 3)      # Bogen cyan/gelb
        cv2.line(vis, (int(cx-span/2), cy), (int(cx+span/2), cy), (0, 0, 255), 3)  # Spann rot
        cv2.putText(vis, f"R{R} S:S{R/span:.2f}", (cx-70, cy-R-8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
    cv2.putText(vis, f"{len(arches)} Boegen erkannt (SAM-Maske gruen, Rundbogen-Fit gelb, Spann rot)",
                (10, vis.shape[0]-15), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    cv2.imwrite(a.out, vis)

    if len(arches) < 2:
        print("zu wenige saubere Bögen"); return
    spans = np.array([d["span"] for d in arches])
    rs = np.array([d["R"]/d["span"] for d in arches])
    piers, pitches = [], []
    for i in range(len(arches)-1):
        pitch = arches[i+1]["cx"] - arches[i]["cx"]
        sp = (spans[i]+spans[i+1])/2
        if 1.0 < pitch/sp < 1.7:
            piers.append((pitch-sp)/sp); pitches.append(pitch/sp)

    def cmp(n, meas, soll, tol):
        e = abs(meas-soll)/soll; v = "PASS" if e < tol else ("WARN" if e < 2*tol else "FAIL")
        print(f"  {n:20s} Foto {meas:6.2f}  Modell {soll:6.2f}  Δ{e*100:4.0f}%  [{v}]")

    print("\n=== VOLLE GEOMETRIE (SAM) — Foto vs Modell ===")
    print(f"  Bogenzahl            Foto {len(arches):2d}      Modell  9")
    cmp("Stich:Spann", float(np.median(rs)), 0.50, 0.06)
    if piers:
        cmp("Pfeiler:Spann", float(np.median(piers)), 0.244, 0.20)
        cmp("Feldteilung:Spann", float(np.median(pitches)), 1.244, 0.15)
    if a.span_m:
        sc = a.span_m/float(np.median(spans))
        print(f"\n  --- absolute Meter (Spann={a.span_m} m gesetzt) ---")
        print(f"  Bogen-R        {np.median([d['R'] for d in arches])*sc:5.1f} m  (Modell 10)")
        if piers:
            print(f"  Pfeilerbreite  {np.median(piers)*np.median(spans)*sc:5.1f} m  (Modell 4.9)")
            print(f"  Feldteilung    {np.median(pitches)*np.median(spans)*sc:5.1f} m  (Modell 24.9)")
    print(f"-> {a.out}")


if __name__ == "__main__":
    main()
