#!/usr/bin/env python3
"""fenster_ml.py — ML-basierte Fenster-Erkennung per Fassaden-SEGMENTIERUNG (SegFormer, CMP-
Facade-Datensatz). Robuster als heuristische Dunkel-/Gewände-Blobs: ein neuronales Netz,
trainiert auf tausenden Fassaden, segmentiert pixelweise in Klassen (window/door/wall/sill/...).
Fenster = zusammenhängende 'window'-Regionen → Anzahl, Lage, Form (inkl. Bogen) in einem Zug,
farb-/perspektiv-robust.

  python3 tools/fenster_ml.py <foto> [--out m.json] [--overlay o.png] [--model <hf-id>]

Fällt auf den heuristischen fenster_zaehler zurück, wenn kein Modell/torch da ist.
"""
import argparse, json, os, sys
import numpy as np
import cv2

DEFAULT_MODEL = "Xpitfire/segformer-finetuned-segments-cmp-facade"


def segment(foto, model_id):
    """pixelweise Klassenkarte + window-Klassenindex."""
    import torch
    from transformers import SegformerForSemanticSegmentation, SegformerImageProcessor
    from PIL import Image
    proc = SegformerImageProcessor.from_pretrained(model_id)
    model = SegformerForSemanticSegmentation.from_pretrained(model_id).eval()
    img = Image.open(foto).convert("RGB"); W, H = img.size
    with torch.no_grad():
        inp = proc(images=img, return_tensors="pt")
        logits = model(**inp).logits                      # (1,C,h,w)
    up = torch.nn.functional.interpolate(logits, size=(H, W), mode="bilinear", align_corners=False)
    seg = up.argmax(1)[0].cpu().numpy().astype(np.int32)
    id2label = {int(k): v.lower() for k, v in model.config.id2label.items()}
    win_ids = [i for i, l in id2label.items() if "window" in l]
    return seg, win_ids, id2label


def windows_from_seg(seg, win_ids, min_area_frac=2e-4):
    """'window'-Regionen → Boxen (cx,cy,w,h,arched) + Bounding-Box aller Fenster (Gebäude)."""
    H, W = seg.shape
    mask = np.isin(seg, win_ids).astype(np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    n, lab, st, _ = cv2.connectedComponentsWithStats(mask)
    out = []
    for i in range(1, n):
        x, y, w, h, a = st[i]
        if a < W * H * min_area_frac:
            continue
        if not (0.2 < w / max(h, 1) < 3.0):
            continue
        comp = (lab[y:y+h, x:x+w] == i)
        # Bogen: obere Ecken leer vs obere Mitte voll
        top = comp[:max(1, h // 4)]; cw = max(1, w // 4)
        corners = (top[:, :cw].mean() + top[:, -cw:].mean()) / 2
        center = top[:, w//2-cw//2:w//2+cw//2+1].mean()
        arched = bool(center - corners > 0.25)
        out.append((x + w/2, y + h/2, float(w), float(h), arched))
    return out, mask


def dominant_building(wins, W):
    """Fenster nach x gruppieren (Lücken-Split), grösste Gruppe = Zielgebäude -> Nachbarhäuser
    (mit eigenen Fenstern) fallen raus. Danach vertikale Ausreisser (Erdgeschoss-Fremdfenster)
    per grossem y-Sprung kappen."""
    if not wins:
        return []
    ws = sorted(wins, key=lambda b: b[0])
    groups, cur = [], [ws[0]]
    for b in ws[1:]:
        if b[0] - cur[-1][0] < 0.08 * W:
            cur.append(b)
        else:
            groups.append(cur); cur = [b]
    groups.append(cur)
    return max(groups, key=len)


def to_rows(wins, bx):
    """Fenster → Reihen (z_frac/x_frac relativ zur Gebäude-Box), Format wie fenster_zaehler."""
    x0, y0, x1, y1 = bx; bw, bh = x1 - x0, y1 - y0
    norm = [((cx - x0) / bw, (cy - y0) / bh, w / bw, h / bh, ar) for cx, cy, w, h, ar in wins]
    norm.sort(key=lambda b: b[1])
    rows, cur = [], [norm[0]]
    for b in norm[1:]:
        if abs(b[1] - np.mean([c[1] for c in cur])) < 0.04:
            cur.append(b)
        else:
            rows.append(cur); cur = [b]
    rows.append(cur)
    out = []
    for r in rows:
        r.sort(key=lambda b: b[0])
        out.append({"z_frac": round(1 - float(np.mean([b[1] for b in r])), 3), "n": len(r),
                    "x_fracs": [round(b[0], 3) for b in r],
                    "arched": [bool(b[4]) for b in r],
                    "w_frac": round(float(np.median([b[2] for b in r])), 3),
                    "h_frac": round(float(np.median([b[3] for b in r])), 3)})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("foto"); ap.add_argument("--out", default=None); ap.add_argument("--overlay", default=None)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    a = ap.parse_args()
    img = cv2.imread(a.foto); H0, W0 = img.shape[:2]
    seg, win_ids, id2label = segment(a.foto, a.model)
    print(f"Modell {a.model}: Klassen {list(id2label.values())}; window-Ids {win_ids}")
    allw, mask = windows_from_seg(seg, win_ids)
    if not allw:
        print("keine Fenster segmentiert"); return
    wins = dominant_building(allw, W0)                 # Nachbarhäuser abtrennen
    print(f"({len(allw)} Fenster gesamt -> {len(wins)} im Zielgebäude nach Cluster-Isolierung)")
    xs = [w[0] for w in wins]; ys = [w[1] for w in wins]
    ws = [w[2] for w in wins]; hs = [w[3] for w in wins]
    bx = (min(xs) - max(ws)/2, min(ys) - max(hs), max(xs) + max(ws)/2, max(ys) + max(hs)*1.3)
    bx = (max(0, bx[0]), max(0, bx[1]), min(W0, bx[2]), min(H0, bx[3]))
    rows = to_rows(wins, bx)
    res = {"foto": a.foto, "modell": a.model,
           "building_box_frac": [round(bx[0]/W0, 3), round(bx[1]/H0, 3), round(bx[2]/W0, 3), round(bx[3]/H0, 3)],
           "n_windows": len(wins), "n_rows": len(rows), "rows": rows}
    print(f"-> {len(wins)} Fenster in {len(rows)} Reihen")
    for r in rows:
        print(f"   z={r['z_frac']:.2f} n={r['n']} arched={r['arched']}")
    if a.out:
        json.dump(res, open(a.out, "w"), indent=2, ensure_ascii=False); print(f"-> {a.out}")
    ov = img.copy()
    for cx, cy, w, h, ar in wins:
        col = (0, 140, 255) if ar else (0, 0, 255)
        cv2.rectangle(ov, (int(cx-w/2), int(cy-h/2)), (int(cx+w/2), int(cy+h/2)), col, 3)
    cv2.putText(ov, f"ML: {len(wins)} Fenster", (10, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 0, 0), 3)
    cv2.imwrite(a.overlay or "/tmp/fenster_ml.png", ov); print(f"-> {a.overlay or '/tmp/fenster_ml.png'}")


if __name__ == "__main__":
    main()
