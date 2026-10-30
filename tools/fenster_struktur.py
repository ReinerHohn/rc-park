#!/usr/bin/env python3
"""fenster_struktur.py — STRUKTUR-REGULARISIERUNG von Fenster-Erkennungen (Abstands-/Formen-Fix).

Nimmt rohe Fenster-Boxen (von JEDEM Detektor: MaskFormer-Instanzen / SegFormer / YOLO) und macht
daraus eine saubere regelmaessige Anordnung — der in der Facade-Parsing-Literatur beschriebene
Alignment-/Strukturschritt (ar5iv 2604.09260): erkannte Boxen auf gemeinsame Reihen/Spalten +
Symmetrie schnappen. Behebt genau 'Abstaende passen nicht' + 'Formen stimmen nicht'.

  import fenster_struktur as FS; layout = FS.regularize(boxes, img_w, img_h)
"""
import numpy as np


def _cluster(vals, tol):
    vals = sorted(vals); groups = [[vals[0]]]
    for v in vals[1:]:
        if v - np.mean(groups[-1]) < tol:
            groups[-1].append(v)
        else:
            groups.append([v])
    return [float(np.mean(g)) for g in groups]


def dominant(boxes, img_w):
    """groesste x-Nachbarschaft = Zielgebaeude (Nachbarn raus). WICHTIG: nur bei GROSSEN Luecken
    trennen (echter Nachbarabstand), NICHT bei normalen Fensterabstaenden — sonst zerschneidet es
    breite regulaere Fassaden in einzelne Spalten."""
    if len(boxes) <= 2:
        return boxes
    cx = sorted(boxes, key=lambda b: (b[0] + b[2]) / 2)
    cen = [(b[0] + b[2]) / 2 for b in cx]
    gaps = [cen[i + 1] - cen[i] for i in range(len(cen) - 1)]
    med = np.median([g for g in gaps if g > 1]) if gaps else img_w
    thr = max(0.13 * img_w, 3.0 * med)                    # Luecke >> typischer Fensterabstand
    groups, cur = [], [cx[0]]
    for i, b in enumerate(cx[1:]):
        if gaps[i] < thr:
            cur.append(b)
        else:
            groups.append(cur); cur = [b]
    groups.append(cur)
    return max(groups, key=len)


def regularize(boxes, img_w, img_h, mirror=True):
    boxes = dominant(boxes, img_w)
    if not boxes:
        return {"n_windows": 0, "rows": []}
    B = np.array(boxes, float)
    cx = (B[:, 0] + B[:, 2]) / 2; cy = (B[:, 1] + B[:, 3]) / 2
    ws = B[:, 2] - B[:, 0]; hs = B[:, 3] - B[:, 1]
    # Ausreisser-Boxen (viel zu gross = merged mehrere Fenster) verwerfen
    mw0, mh0 = np.median(ws), np.median(hs)
    keep = (ws < 2.2 * mw0) & (hs < 2.8 * mh0) & (ws > 0.4 * mw0)
    B = B[keep]; cx, cy, ws, hs = cx[keep], cy[keep], ws[keep], hs[keep]
    if len(B) == 0:
        return {"n_windows": 0, "rows": []}
    bx0, bx1 = B[:, 0].min(), B[:, 2].max(); by0, by1 = B[:, 1].min(), B[:, 3].max()
    axis = (bx0 + bx1) / 2; mh = float(np.median(hs)); mw = float(np.median(ws))

    order = np.argsort(cy); rows_idx, cur = [], [order[0]]
    for i in order[1:]:
        if cy[i] - np.mean([cy[j] for j in cur]) < 0.6 * mh:
            cur.append(i)
        else:
            rows_idx.append(cur); cur = [i]
    rows_idx.append(cur)

    rows = []
    for ridx in rows_idx:
        ys = float(np.mean([cy[i] for i in ridx])); xs = sorted(float(cx[i]) for i in ridx)
        rh = float(np.median([hs[i] for i in ridx])); arched = rh > 1.4 * mh
        if mirror:
            ds = sorted(abs(x - axis) for x in xs); placed = []; n = len(xs)
            if n % 2 == 1:
                placed.append(axis); ds = ds[1:]
            for k in range(0, len(ds) - 1, 2):
                d = (ds[k] + ds[k + 1]) / 2; placed += [axis - d, axis + d]
            if len(ds) % 2 == 1:
                placed += [axis - ds[-1], axis + ds[-1]]
            xs = sorted(placed)
        rows.append({"y": ys, "xs": xs, "arched": arched, "h": rh})

    allx = [x for r in rows for x in r["xs"]]
    cols = _cluster(allx, 0.6 * mw) if allx else []
    bw = max(bx1 - bx0, 1); bh = max(by1 - by0, 1); out_rows = []
    for r in sorted(rows, key=lambda r: r["y"]):
        snapped = sorted(set(round(min(cols, key=lambda c: abs(c - x)), 1) for x in r["xs"])) if cols else sorted(set(r["xs"]))
        out_rows.append({"z_frac": round(1 - (r["y"] - by0) / bh, 3), "n": len(snapped),
                         "x_fracs": [round((x - bx0) / bw, 3) for x in snapped],
                         "arched": [r["arched"]] * len(snapped),
                         "w_frac": round(mw / bw, 3), "h_frac": round(r["h"] / bh, 3)})
    return {"building_box_frac": [round(bx0 / img_w, 3), round(by0 / img_h, 3),
                                  round(bx1 / img_w, 3), round(by1 / img_h, 3)],
            "n_windows": sum(r["n"] for r in out_rows), "n_rows": len(out_rows), "rows": out_rows}
