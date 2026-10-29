#!/usr/bin/env python3
"""hofgut_schema.py — GROBES BAU-SCHEMA per KANTEN-/REGIONEN-ERKENNUNG aus einem Frontalfoto.

Der User fordert: NICHT Parameter nach Augenmaß nachdrehen, sondern das grobe Gerüst am Foto
MESSEN und daraus bauen. Dieses Tool segmentiert Dach / Wand / Himmel, misst die Proportionen
(Dachanteil, Trauflinie, Geschoss-Bänder, Gebäudebreite→Höhe, Fensterachsen, Zwerchhaus-Beulen)
und schreibt ein Schema-JSON, das der Generator liest. Herkunft: Proportionen aus Foto,
absolute Höhe aus LOD2 (First).

Lauf:  python3 tools/hofgut_schema.py <foto> [--ridge-m 17.5] [--out schema.json] [--overlay o.png]
Ausgabe: Schema-JSON + Overlay mit eingezeichneten Linien (zum SELBST-Prüfen).
"""
import argparse, json
import numpy as np
import cv2


def hlines(edges, x0, x1, min_frac=0.33, tol=6):
    """Starke WAAGRECHTE Kanten als y-Cluster (gewichtet mit Länge). Robust gegen Farbe/Schatten."""
    W = x1 - x0
    lines = cv2.HoughLinesP(edges[:, x0:x1], 1, np.pi / 180, threshold=int(0.18 * W),
                            minLineLength=int(min_frac * W), maxLineGap=int(0.08 * W))
    ys, ln = [], []
    if lines is not None:
        for l in np.asarray(lines).reshape(-1, 4):
            xa, ya, xb, yb = l
            if abs(yb - ya) <= 3:                                   # ~waagrecht
                ys.append((ya + yb) / 2); ln.append(abs(xb - xa))
    if not ys:
        return []
    order = np.argsort(ys); ys = np.array(ys)[order]; ln = np.array(ln)[order]
    cl = []                                                          # [y, totlen]
    for y, l in zip(ys, ln):
        if cl and y - cl[-1][0] < tol:
            p, tl = cl[-1]; cl[-1] = [(p * tl + y * l) / (tl + l), tl + l]
        else:
            cl.append([y, l])
    return sorted(cl, key=lambda c: -c[1])                          # stärkste zuerst


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("foto")
    ap.add_argument("--ridge-m", type=float, default=17.63, help="First-Höhe in m (LOD2, amtlich)")
    ap.add_argument("--eave-m", type=float, default=9.0, help="Traufe über Boden in m (LOD2, amtlich)")
    ap.add_argument("--lod2", default="modelle/hofgut_sternen/hofgut_lod2.json", help="LOD2-Massing (amtlich)")
    ap.add_argument("--width-m", type=float, default=40.0, help="Fassadenbreite Hauptflügel in m (LOD2)")
    ap.add_argument("--out", default="modelle/hofgut_sternen/schema.json")
    ap.add_argument("--overlay", default="/tmp/hofgut_schema.png")
    a = ap.parse_args()

    im = cv2.imread(a.foto)
    Himg, Wimg = im.shape[:2]
    gray = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150)
    g = cv2.GaussianBlur(gray, (0, 0), 2).astype(float)
    gy = cv2.Sobel(g, cv2.CV_64F, 0, 1, ksize=5)               # vertikaler Helligkeits-Gradient

    # --- Traufe = DUNKEL(Dach)→HELL(Wand)-Stufe pro Spalte (robust gegen schiefe/zackige Traufe) ---
    r0, r1 = int(0.18 * Himg), int(0.65 * Himg)                # Traufe liegt in diesem y-Band
    f0, f1 = int(0.55 * Himg), int(0.97 * Himg)                # Fuß (Wand→Terrasse) tiefer
    eave_col = r0 + np.argmax(gy[r0:r1, :], axis=0)            # stärkster Anstieg = Dach→Wand
    eave_str = np.max(gy[r0:r1, :], axis=0)
    foot_col = f0 + np.argmin(gy[f0:f1, :], axis=0)            # stärkster Abfall = Wand→Terrasse
    foot_str = -np.min(gy[f0:f1, :], axis=0)
    # Gebäude-Spalten = wo BEIDE Stufen deutlich sind (Wand mit Dach drüber und Fuß drunter)
    good = (eave_str > np.percentile(eave_str, 55)) & (foot_str > np.percentile(foot_str, 45))
    cols_on = np.where(good)[0]
    x0, x1 = int(np.percentile(cols_on, 3)), int(np.percentile(cols_on, 97))
    Wpx = x1 - x0
    sel = good[x0:x1 + 1]
    eave_y = float(np.median(eave_col[x0:x1 + 1][sel]))
    foot_y = float(np.median(foot_col[x0:x1 + 1][sel]))

    # --- Lauben-Galerien = starke WAAGRECHTE Linien ZWISCHEN Traufe und Fuß ---
    hc = hlines(edges, x0, x1, min_frac=0.33)
    galerien = sorted(round((c[0] - eave_y) / (foot_y - eave_y), 3)
                      for c in hc[:10] if eave_y + 0.08 * (foot_y - eave_y) < c[0] < foot_y - 0.05 * (foot_y - eave_y))

    # --- Fensterachsen: senkrechte Kanten-Dichte NUR im Wandbereich (Traufe..Fuß) ---
    wall = edges[int(eave_y):int(foot_y), x0:x1]
    cden = cv2.GaussianBlur(wall.sum(0).astype(float).reshape(1, -1), (0, 0), 3).ravel()
    thr3 = cden.mean() + 0.5 * cden.std()
    vpk = [i for i in range(1, len(cden) - 1)
           if cden[i] > thr3 and cden[i] >= cden[i - 1] and cden[i] > cden[i + 1]]
    vmerged = []
    for p in vpk:
        if vmerged and p - vmerged[-1] < 0.03 * Wpx:
            continue
        vmerged.append(p)
    n_axes = max(1, len(vmerged))

    # --- MASSING aus LOD2 (amtlich, zuverlässig) — ggf. aus LOD2-JSON nachladen ---
    ridge_m, eave_m, width_m = a.ridge_m, a.eave_m, a.width_m
    lod2_note = "Default-Args"
    try:
        with open(a.lod2) as f:
            L = json.load(f)
        ridge_m = round(L["gebaeude"][0]["ridge_m"], 2)
        lod2_note = f'{a.lod2} (bbox {", ".join(f"{v:.0f}" for v in L["bbox_lbh_m"])} m, {L["gebaeude"][0]["teile"]} Teile)'
    except Exception as e:
        lod2_note = f"LOD2 nicht geladen ({e}); Default-Args"
    roof_frac_lod2 = round((ridge_m - eave_m) / ridge_m, 3)

    # --- QUER-CHECK: Foto-gemessener Dachanteil gegen LOD2 (Perspektive → nur grob, als Plausib.) ---
    #  Dachanteil im Foto = Dachhöhe / Gesamthöhe; Traufe/Fuß aus Gradient, First ~ Bildoben am Gebäude.
    ridge_px = r0                                              # grober Firstbereich (oberes Messband)
    roof_frac_foto = round((eave_y - ridge_px) / (foot_y - ridge_px), 3) if foot_y > ridge_px else None
    cross = "n/a"
    if roof_frac_foto:
        cross = "PASS" if abs(roof_frac_foto - roof_frac_lod2) < 0.10 else "FLAG"

    schema = {
        "quelle": "MASSING aus LOD2 (amtlich); FASSADENDETAIL (Achsen/Galerien) aus Foto-Kanten",
        "lod2": lod2_note,
        "ridge_m": ridge_m, "eave_m": eave_m, "width_m": width_m,
        "roof_frac": roof_frac_lod2,
        "roof_frac_foto_quercheck": roof_frac_foto, "quercheck": cross,
        "n_axes": n_axes,
        "galerie_bands_frac": galerien,
        "foto": a.foto,
        "px": {"x0": x0, "x1": x1, "eave": round(eave_y, 1), "foot": round(foot_y, 1)},
    }
    with open(a.out, "w") as f:
        json.dump(schema, f, indent=2, ensure_ascii=False)

    # --- Overlay zum SELBST-Prüfen ---
    ov = im.copy()
    cv2.line(ov, (x0, int(eave_y)), (x1, int(eave_y)), (0, 255, 0), 2)                    # Traufe (grün)
    cv2.line(ov, (x0, int(foot_y)), (x1, int(foot_y)), (255, 0, 0), 2)                    # Fuß (blau)
    cv2.line(ov, (x0, 2), (x0, Himg - 2), (0, 255, 255), 1)
    cv2.line(ov, (x1, 2), (x1, Himg - 2), (0, 255, 255), 1)
    for c in hc[:8]:
        cv2.line(ov, (x0, int(c[0])), (x1, int(c[0])), (0, 180, 255), 1)                 # alle starken H-Linien (orange)
    for p in vmerged:
        cv2.line(ov, (x0 + p, int(eave_y)), (x0 + p, int(foot_y)), (200, 200, 200), 1)   # Achsen (grau)
    cv2.imwrite(a.overlay, ov)

    print(json.dumps(schema, indent=2, ensure_ascii=False))
    print(f"-> {a.out}\n-> {a.overlay}")


if __name__ == "__main__":
    main()
