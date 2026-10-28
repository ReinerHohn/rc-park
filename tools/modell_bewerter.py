#!/usr/bin/env python3
"""modell_bewerter.py — OBJEKTIVE Bewertung: Modell-Render vs. echtes Foto → Score 0..1.

Vergleicht die Struktur (kein Pixel-Identisch): Kanten-Profile über Höhe (Geschoss-/
Trauf-/Gauben-Lage) + Breite (Achsrhythmus) + Grobraster. Damit lässt sich die
Qualitäts-Ratsche messen und ein Optimier-Loop fahren (Score maximieren, nie verschlechtern).

  python3 tools/modell_bewerter.py --render r.png --ref foto.jpg --ref-crop 0.30,0.04,0.99,0.80
"""
import argparse
import numpy as np
import cv2


def autocrop_white(img, thr=245):
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    mask = g < thr
    ys, xs = np.where(mask)
    if len(xs) == 0:
        return img
    return img[ys.min():ys.max()+1, xs.min():xs.max()+1]


def prep(img, N=360):
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    g = cv2.resize(g, (N, N))
    e = cv2.Canny(g, 50, 150)
    return g, e


def zncc(a, b):
    a = a - a.mean(); b = b - b.mean()
    d = (np.linalg.norm(a)*np.linalg.norm(b))
    return float(a @ b / d) if d > 1e-9 else 0.0


def score(render_path, ref_path, ref_crop=None, out_vis=""):
    R = cv2.imread(render_path); F = cv2.imread(ref_path)
    R = autocrop_white(R)
    if ref_crop:
        h, w = F.shape[:2]; x0, y0, x1, y1 = ref_crop
        F = F[int(y0*h):int(y1*h), int(x0*w):int(x1*w)]
    gR, eR = prep(R); gF, eF = prep(F)
    from scipy.ndimage import uniform_filter1d
    def prof(e, ax):
        p = e.mean(axis=ax); return uniform_filter1d(p.astype(float), 9)
    ch = zncc(prof(eR, 1), prof(eF, 1))        # Höhenprofil (Zeilen) = Geschoss-/Trauflage
    cv = zncc(prof(eR, 0), prof(eF, 0))        # Breitenprofil (Spalten) = Achsrhythmus
    # Grobraster 24x24 der Kantendichte
    def grid(e, k=24):
        return cv2.resize(e.astype(float), (k, k)).ravel()
    cg = zncc(grid(eR), grid(eF))
    s = 0.40*max(0, ch) + 0.30*max(0, cv) + 0.30*max(0, cg)
    if out_vis:
        vis = np.hstack([cv2.resize(F, (360, 360)), cv2.resize(R, (360, 360)),
                         cv2.cvtColor(np.hstack([cv2.resize(eF, (180, 360)), cv2.resize(eR, (180, 360))]), cv2.COLOR_GRAY2BGR)])
        cv2.putText(vis, f"score {s:.3f}  H{ch:.2f} B{cv:.2f} G{cg:.2f}", (10, 25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        cv2.imwrite(out_vis, vis)
    return dict(score=round(s, 3), hoehe=round(ch, 3), breite=round(cv, 3), raster=round(cg, 3))


def validate_orientation(render_path, ref_path, ref_crop=None, h_min=0.5, b_min=0.78):
    """ORIENTIERUNGS-GATE: fängt vertikalen Flip (Höhe<0), 180° und Schräglage (Breite↓).
    Vergleicht die (ausgerichtete) Fassade gegen die Referenz. PASS nur wenn beides ok."""
    r = score(render_path, ref_path, ref_crop)
    flip = r["hoehe"] < h_min
    skew = r["breite"] < b_min
    r["flip_vertikal"] = bool(flip)
    r["schraeg"] = bool(skew)
    r["PASS"] = bool(not flip and not skew)
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--render", required=True)
    ap.add_argument("--ref", required=True)
    ap.add_argument("--ref-crop", default="", help="x0,y0,x1,y1 Anteile")
    ap.add_argument("--vis", default="")
    ap.add_argument("--validate", action="store_true", help="Orientierungs-Gate (Flip/Schräg) → PASS/FAIL")
    a = ap.parse_args()
    rc = tuple(float(v) for v in a.ref_crop.split(",")) if a.ref_crop else None
    if a.validate:
        print(validate_orientation(a.render, a.ref, rc))
    else:
        print(score(a.render, a.ref, rc, a.vis))


if __name__ == "__main__":
    main()
