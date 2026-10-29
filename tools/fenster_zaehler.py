#!/usr/bin/env python3
"""fenster_zaehler.py — VOLLAUTOMATISCHE Fenster-Erkennung & -Zählung aus einem Frontalfoto.

Robust für GITTER (traufständig) UND PYRAMIDE (Treppengiebel): findet JEDES Fenster als
eigenen dunklen Blob (Glas ist dunkel auf heller Wand), nicht per Spalten-Projektion. Deshalb
kann es — anders als fassade_messen._axis_peaks (nimmt N vertikale Achsen an) — eine gestufte
Giebel-Anordnung mit je Reihe anderer Anzahl/Position erfassen.

Pipeline (reines OpenCV, kein KI-Juror, deterministisch):
  1. Fassade segmentieren: grösste helle+pinke zusammenhängende Fläche -> Bounding-Box (Gebäude)
  2. innerhalb: dunkle Blobs (Glas) per adaptiver Schwelle + Morphologie
  3. Blobs filtern (Grösse/Seitenverhältnis/Füllgrad), Arkadenbögen (zu gross) raus
  4. in Reihen clustern (nach z), je Reihe x-Positionen -> volle Anordnung
  5. Ausgabe JSON (Fraktionen der Gebäude-Box) + Beweis-Overlay (Boxen + Zähler)

  python3 tools/fenster_zaehler.py <foto> [--box x0,y0,x1,y1 frac] [--out m.json] [--overlay o.png]
"""
import argparse, json
import numpy as np
import cv2


def facade_box(img):
    """grösste helle Putzwand-Fläche OHNE Himmel = Fassade -> (x0,y0,x1,y1) in Pixeln.
    Himmel ist auch hell+entsättigt, berührt aber den oberen Bildrand und spannt breit —
    deshalb Komponenten verwerfen, die die obersten Zeilen berühren."""
    H, Wd = img.shape[:2]
    B, R = img[:, :, 0].astype(int), img[:, :, 2].astype(int)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    Hh, S, V = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]
    warm = R >= B - 3                                             # Himmel ist bläulich (B>R) -> raus
    white = (V > 135) & (S < 70) & warm                          # warme weisse Putzwand (kein Himmel)
    pink = ((Hh < 14) | (Hh > 166)) & (S > 25) & (S < 130) & (V > 110) & warm   # rosa Sandstein
    wall = ((white | pink).astype(np.uint8)) * 255
    wall = cv2.morphologyEx(wall, cv2.MORPH_CLOSE, np.ones((25, 25), np.uint8))  # Bänder/Fenster überbrücken
    n, lab, stats, _ = cv2.connectedComponentsWithStats(wall)
    if n < 2:
        return 0, 0, Wd, H
    i = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))          # grösste warm-weisse Fläche = Fassade
    x, y, w, h = stats[i, :4]
    return int(x), int(y), int(x + w), int(y + h)


def detect_windows(crop, thr=None, close_k=5, min_af=3e-4, max_af=0.035,
                   ar_lo=0.25, ar_hi=2.4, min_fill=0.32):
    """dunkle Fenster-Blobs -> Liste (cx,cy,w,h) in Pixeln. thr aus zentraler Region (robust
    gegen Himmel/Boden), close_k reconnektiert durch Himmel-Spiegelung/Sprossen fragmentierte
    Scheiben zu EINER Öffnung, min_af/max_af Flächen-, ar_*/min_fill Form-Grenzen.
    Wide Bänder (Schriftzug/Gesims, aspect gross) und Arkade (zu gross) fallen so raus."""
    g = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    H, W = g.shape
    if thr is None:
        c = g[int(0.15 * H):int(0.75 * H), int(0.25 * W):int(0.75 * W)]
        thr = max(70, int(c.mean() - 0.7 * c.std()))
    dark = (g < thr).astype(np.uint8) * 255
    dark = cv2.morphologyEx(dark, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    dark = cv2.morphologyEx(dark, cv2.MORPH_CLOSE, np.ones((close_k, close_k), np.uint8))
    n, lab, stats, cent = cv2.connectedComponentsWithStats(dark)
    area_img = H * W
    out = []
    for i in range(1, n):
        x, y, w, h, a = stats[i]
        if a < area_img * min_af or a > area_img * max_af:       # zu klein (Schrift) / zu gross (Arkade)
            continue
        ar = w / max(h, 1)
        if ar < ar_lo or ar > ar_hi:                             # keine extremen Striche/Bänder
            continue
        if a / (w * h) < min_fill:                               # Füllgrad (kein L/Ast)
            continue
        out.append((x + w / 2, y + h / 2, w, h))
    return out, dark


def dominant_cluster(wins, W, H):
    """Fenster-Blobs nach x gruppieren (Lücken-Split), grösste Gruppe = das Zielgebäude —
    trennt Nachbarhaus/Schilder automatisch ab. Danach vertikale Ausreisser (Stühle/Boden
    unter dem Gebäude) per y-Lücke verwerfen."""
    if not wins:
        return []
    xs = sorted(wins, key=lambda b: b[0])
    groups, cur = [], [xs[0]]
    for b in xs[1:]:
        if b[0] - cur[-1][0] < 0.06 * W:            # gleiche x-Nachbarschaft
            cur.append(b)
        else:
            groups.append(cur); cur = [b]
    groups.append(cur)
    return max(groups, key=len)                      # dominante x-Gruppe = das Zielgebäude


def is_arched(gray, box, thr):
    """Rundbogen-Fenster erkennen: obere Ecken des dunklen Glases fehlen (gerundet), Mitte voll.
    box=(cx,cy,w,h) in gray-Pixeln. Vergleicht Dunkel-Füllung obere Ecken vs oberer Mittelstreifen."""
    cx, cy, w, h = box
    x0, y0 = int(cx - w / 2), int(cy - h / 2)
    reg = gray[max(0, y0):int(cy + h / 2), max(0, x0):int(cx + w / 2)]
    if reg.size == 0 or reg.shape[0] < 8 or reg.shape[1] < 8:
        return False
    dark = reg < thr
    hh, ww = dark.shape
    top = dark[:max(1, hh // 4)]                       # oberes Viertel
    cw = max(1, ww // 4)
    corners = (top[:, :cw].mean() + top[:, -cw:].mean()) / 2
    center = top[:, ww // 2 - cw // 2: ww // 2 + cw // 2 + 1].mean()
    return (center - corners) > 0.26                   # Mitte deutlich voller als Ecken = Bogen


def merge_boxes(wins):
    """benachbarte/überlappende Blobs zu EINER Fensteröffnung vereinen: fängt Sprossen-geteilte
    Scheiben (nah nebeneinander) UND Doppel-Detektion (gestapelt/überlappend) ab. Union-Find
    über Boxen, die sich überlappen oder bei hoher vertikaler Überlappung einen kleinen
    horizontalen Spalt haben."""
    if not wins:
        return []
    B = [[cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2] for (cx, cy, w, h) in wins]
    n = len(B); par = list(range(n))

    def find(i):
        while par[i] != i:
            par[i] = par[par[i]]; i = par[i]
        return i

    def near(a, b):
        ox = min(a[2], b[2]) - max(a[0], b[0]); oy = min(a[3], b[3]) - max(a[1], b[1])
        if ox > 0 and oy > 0:
            return True                                           # echte Überlappung
        hb = min(a[3] - a[1], b[3] - b[1])
        if oy > 0.5 * hb and -ox < 0.35 * min(a[2] - a[0], b[2] - b[0]):   # Sprossenspalt
            return True
        return False

    for i in range(n):
        for j in range(i + 1, n):
            if near(B[i], B[j]):
                par[find(i)] = find(j)
    groups = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(B[i])
    out = []
    for g in groups.values():
        x0 = min(b[0] for b in g); y0 = min(b[1] for b in g)
        x1 = max(b[2] for b in g); y1 = max(b[3] for b in g)
        out.append(((x0 + x1) / 2, (y0 + y1) / 2, x1 - x0, y1 - y0))
    return out


def cluster_rows(wins, H, tol=0.035):
    """Fenster nach z (cy) in Reihen gruppieren (tol = Anteil der Höhe)."""
    if not wins:
        return []
    ws = sorted(wins, key=lambda b: b[1])
    rows, cur = [], [ws[0]]
    for b in ws[1:]:
        if abs(b[1] - np.mean([c[1] for c in cur])) < tol * H:
            cur.append(b)
        else:
            rows.append(cur); cur = [b]
    rows.append(cur)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("foto"); ap.add_argument("--box", default=None, help="x0,y0,x1,y1 (Fraktion)")
    ap.add_argument("--out", default=None); ap.add_argument("--overlay", default=None)
    a = ap.parse_args()
    img = cv2.imread(a.foto); H0, W0 = img.shape[:2]
    if a.box:
        f = [float(t) for t in a.box.split(",")]
        x0, y0, x1, y1 = (int(f[0] * W0), int(f[1] * H0), int(f[2] * W0), int(f[3] * H0))
        crop = img[y0:y1, x0:x1]; wins, dark = detect_windows(crop)
    else:
        # VOLLAUTOMATISCH: alle Fenster-Blobs im Bild, dann dominantes Cluster (= das Gebäude)
        allw, dark = detect_windows(img)
        wins = dominant_cluster(allw, W0, H0)
        if wins:
            xs = [b[0] for b in wins]; ys = [b[1] for b in wins]
            hs = [b[3] for b in wins]; ws = [b[2] for b in wins]
            pad = 2.0 * np.median(hs)
            x0 = max(0, int(min(xs) - max(ws))); x1 = min(W0, int(max(xs) + max(ws)))
            y0 = max(0, int(min(ys) - pad)); y1 = min(H0, int(max(ys) + 2.2 * pad))
        else:
            x0, y0, x1, y1 = 0, 0, W0, H0
        crop = img[y0:y1, x0:x1]; ch = crop.shape[0]
        # PASS 2: im Gebäude-Crop fein erkennen. min_fill niedrig (Giebelfenster sind durch
        # Himmel-Spiegelung fragmentiert -> Füllgrad ~0.3), aspect<2.3 killt Schrift-/Gesims-
        # Bänder, Fläche 0.08-1.5 % killt winzige Reste & grosse Schattenbänder.
        # close KLEIN (3): schliesst nur Pixelrauschen. Grösser würde die Body-Fenster mit dem
        # breiten Schattenband darunter verschmelzen -> Blob > max_af -> fälschlich verworfen.
        wins, dark = detect_windows(crop, close_k=3, min_af=8e-4, max_af=0.015,
                                    ar_lo=0.3, ar_hi=2.3, min_fill=0.28)
        # Arkade (grosse Bögen im EG, reichen bis zum Boden) verwerfen: Unterkante im untersten 10 %
        wins = [b for b in wins if (b[1] + b[3] / 2) < 0.90 * ch]
    wins = merge_boxes(wins)                     # Sprossen-Scheiben & Doppel-Detektion vereinen
    H, W = crop.shape[:2]
    # Rundbogen-Erkennung je Fenster (datengetrieben, kein Augenmaß)
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    cc = gray[int(0.15 * H):int(0.75 * H), int(0.25 * W):int(0.75 * W)]
    athr = max(70, int(cc.mean() - 0.7 * cc.std()))
    arched = {id(b): is_arched(gray, b, athr) for b in wins}
    rows = cluster_rows(wins, H)

    rows_out = []
    for r in sorted(rows, key=lambda r: np.mean([b[1] for b in r])):
        r = sorted(r, key=lambda b: b[0])
        zc = float(np.mean([b[1] for b in r])) / H
        rows_out.append({"z_frac": round(float(1 - zc), 3), "n": len(r),
                         "x_fracs": [round(float(b[0]) / W, 3) for b in r],
                         "arched": [bool(arched.get(id(b), False)) for b in r],
                         "w_frac": round(float(np.median([b[2] for b in r])) / W, 3),
                         "h_frac": round(float(np.median([b[3] for b in r])) / H, 3)})
    res = {"foto": a.foto, "building_box_frac": [round(x0 / W0, 3), round(y0 / H0, 3),
                                                 round(x1 / W0, 3), round(y1 / H0, 3)],
           "n_windows": len(wins), "n_rows": len(rows_out), "rows": rows_out}
    print(f"Fassade-Box {res['building_box_frac']}  ->  {len(wins)} Fenster in {len(rows_out)} Reihen")
    for rr in rows_out:
        print(f"  z={rr['z_frac']:.2f}  n={rr['n']}  x={rr['x_fracs']}")
    if a.out:
        json.dump(res, open(a.out, "w"), indent=2); print(f"-> {a.out}")

    ov = crop.copy()
    for k, r in enumerate(sorted(rows, key=lambda r: np.mean([b[1] for b in r]))):
        for (cx, cy, w, h) in r:
            cv2.rectangle(ov, (int(cx - w / 2), int(cy - h / 2)), (int(cx + w / 2), int(cy + h / 2)), (0, 0, 255), 3)
        ry = int(np.mean([b[1] for b in r]))
        cv2.putText(ov, f"R{k+1}:{len(r)}", (6, ry), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (0, 180, 0), 3)
    cv2.putText(ov, f"total {len(wins)} windows", (6, 34), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (255, 0, 0), 3)
    op = a.overlay or "/tmp/fenster_overlay.png"
    cv2.imwrite(op, ov); print(f"-> {op}")


if __name__ == "__main__":
    main()
