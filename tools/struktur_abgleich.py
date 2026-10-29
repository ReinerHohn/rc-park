#!/usr/bin/env python3
"""struktur_abgleich.py — HARTER 3D-STRUKTUR-Abgleich (nicht Farbe!). Vergleicht die FORM des
Modells gegen die LASER-Grundwahrheit (hofgut_struktur.obj aus nDOM): dominiert das Dach und zieht
es tief herunter? Maß = DACH-ANTEIL der Silhouette (viewpoint-robuste Breiten-über-Höhe-Analyse).

Dachanteil = (First_row .. Traufe_row) / (First_row .. Fuß_row), aus dem Breitenprofil der Silhouette:
unten ~konstante Breite (Wände), oben Verjüngung (Dachschrägen). Die Höhe, wo die Verjüngung beginnt,
ist die sichtbare Traufe. Modell muss den Laser-Dachanteil treffen, sonst = flacher Deckel = FAIL.

Lauf: /tmp/ml/bin/python tools/struktur_abgleich.py   (rendert beide via rv, analysiert via cv2)
"""
import json, os, subprocess, sys
import numpy as np
import cv2

MD = "modelle/hofgut_sternen"


def render(mesh, out, view="front,270,12"):
    subprocess.run(["/tmp/rv/bin/python", "tools/glb_render.py", mesh, out, view],
                   capture_output=True, text=True, env={**os.environ, "PYOPENGL_PLATFORM": "egl", "GLB_LIGHT": "0.8"})
    return f"{out}_{view.split(',')[0]}.png"


def rf_from_mask(mask):
    ys, xs = np.where(mask)
    if len(ys) < 50:
        return None, None
    y0, y1 = ys.min(), ys.max()
    width = np.array([mask[r].sum() for r in range(y0, y1 + 1)], float)
    width = cv2.GaussianBlur(width.reshape(-1, 1), (1, 9), 0).ravel()
    wmax = np.percentile(width, 92)                         # volle Wandbreite (robust gegen Fin-Spikes)
    # DACH = das sich VERJÜNGENDE Band (Breite < 0.85*wmax). Wände = volle Breite.
    # Dachanteil = Anteil der Höhe, der Dach ist. Traufe = unterste Dach-Zeile (von oben her zusammenhängend).
    is_roof = width < 0.85 * wmax
    rf = float(is_roof.mean())
    # sichtbare Traufe = erste Zeile von oben, ab der es dauerhaft Wand (voll breit) ist
    eave = y1
    for i in range(len(width)):
        if not is_roof[i] and (i + 5 >= len(width) or not is_roof[i:i + 5].any()):
            eave = y0 + i; break
    return rf, (y0, eave, y1)


def roof_fraction(png):                                        # RENDER: Gebäude dunkler als weißer BG
    g = cv2.cvtColor(cv2.imread(png), cv2.COLOR_BGR2GRAY)
    return rf_from_mask(g < 248)


def roof_fraction_maskpng(png):                                # ML-Maske: Gebäude = weiß
    g = cv2.imread(png, 0)
    return rf_from_mask(g > 127)


def main():
    # GRUNDWAHRHEIT = FOTO (g2-ML-Maske), nicht die wackelige Laser-Hülle → foto-verankert + stabil.
    foto_mask = "daten/hofgut_sternen/fotos/g2_mask.png"
    rf_l, bl = roof_fraction_maskpng(foto_mask)
    rp_m = render(f"{MD}/hofgut_massing.glb", "/tmp/sa_model", "q,315,16")   # 3/4 wie g2
    rf_m, bm = roof_fraction(rp_m)
    rp_l = foto_mask
    d = abs(rf_m - rf_l)
    score = max(0, round(100 * (1 - d / 0.30)))

    # Seite an Seite mit eingezeichneter Trauflinie
    def annot(png, b, lab):
        im = cv2.imread(png); g = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY); ys, xs = np.where(g < 248)
        im = im[max(0, ys.min() - 8):ys.max() + 8, max(0, xs.min() - 8):xs.max() + 8]
        y0, eave, y1 = b; off = max(0, ys.min() - 8)
        cv2.line(im, (0, eave - off), (im.shape[1], eave - off), (0, 165, 255), 2)
        cv2.putText(im, lab, (6, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 2)
        return cv2.resize(im, (int(im.shape[1] * 320 / im.shape[0]), 320))
    A = annot("daten/hofgut_sternen/fotos/g2.jpg", bl, f"FOTO g2 Dachanteil {rf_l:.2f}")
    B = annot(rp_m, bm, f"MODELL Dachanteil {rf_m:.2f}")
    W = A.shape[1] + B.shape[1] + 16
    c = np.full((340, W, 3), 255, np.uint8); c[0:320, :A.shape[1]] = A; c[0:320, A.shape[1] + 16:] = B
    cv2.putText(c, f"STRUKTUR-NAEHE {score}/100  (Traufe orange)", (6, 335), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
    cv2.imwrite("/tmp/struktur_abgleich.png", c)

    print("=== HARTER 3D-STRUKTUR-ABGLEICH (gegen FOTO g2 = foto-verankert, stabil) ===")
    print(f"  Foto-Dachanteil (Grundwahrheit g2): {rf_l:.2f}")
    print(f"  Modell-Dachanteil:                  {rf_m:.2f}")
    print(f"  Abweichung Δ={d:.2f}  ->  STRUKTUR-NÄHE {score}/100")
    print(f"  {'✓ Dach dominiert wie im Foto' if d < 0.12 else '✗ Dachanteil weicht vom Foto ab'}")
    print("-> /tmp/struktur_abgleich.png")
    json.dump({"laser_roof_frac": rf_l, "foto_roof_frac": rf_l, "model_roof_frac": rf_m,
               "delta": d, "score": score, "anker": "foto g2"},
              open(f"{MD}/struktur_score.json", "w"), indent=1)
    return d


if __name__ == "__main__":
    sys.exit(0 if main() is not None else 1)
