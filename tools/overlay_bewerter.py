#!/usr/bin/env python3
"""overlay_bewerter.py — PERSPEKTIV-GENAUER Overlay-Bewerter: legt das 3D-Modell aus der Kamera-
Perspektive des Fotos halbtransparent drüber und bewertet die Übereinstimmung.

Kamera-Pose automatisch per SILHOUETTEN-FIT: das Gebäude ist freigestellt (ML-Maske), also wird
az/el durchsucht und die gerenderte Modell-Silhouette per IoU gegen die Foto-Maske optimiert
(bbox-aligniert → skalen-/lage-invariant). Beste Pose → Overlay + Score + Band-Abgleich (Traufe/
Galerie), damit man Element für Element sieht, wo es passt.

Lauf: /tmp/ml/bin/python tools/overlay_bewerter.py --name hofgut_sternen --foto hf_front \
        --glb modelle/hofgut_sternen/hofgut_hybrid.glb
"""
import argparse, json, os, subprocess
import numpy as np
import cv2


def render(glb, out, az, el, light="0.6"):
    subprocess.run(["/tmp/rv/bin/python", "tools/glb_render.py", glb, out, f"q,{az},{el}"],
                   capture_output=True, text=True, env={**os.environ, "PYOPENGL_PLATFORM": "egl", "GLB_LIGHT": light})
    return f"{out}_q.png"


def model_mask(png):
    im = cv2.imread(png); g = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
    m = (g < 248).astype(np.uint8)
    ys, xs = np.where(m)
    if len(ys) < 50:
        return None, None, None
    return im, m, (xs.min(), ys.min(), xs.max(), ys.max())


def iou_bboxaligned(mm, mb, fm, fb):
    """IoU nach bbox-Angleich (Modell-Silhouette auf Foto-bbox skaliert) — Formtreue, skaleninvariant."""
    mx0, my0, mx1, my1 = mb; fx0, fy0, fx1, fy1 = fb
    mc = mm[my0:my1, mx0:mx1]; fc = fm[fy0:fy1, fx0:fx1]
    W, H = fx1 - fx0, fy1 - fy0
    mcr = cv2.resize(mc, (W, H), interpolation=cv2.INTER_NEAREST) > 0
    fcr = fc > 0
    inter = (mcr & fcr).sum(); union = (mcr | fcr).sum()
    return inter / max(1, union), mcr, fcr


def h_bands(mask):
    """waagrechte Struktur: wo verjüngt sich die Silhouette (Dach) / wo volle Breite (Wand)."""
    ys, xs = np.where(mask); y0, y1 = ys.min(), ys.max()
    w = np.array([mask[r].sum() for r in range(y0, y1 + 1)], float)
    w = cv2.GaussianBlur(w.reshape(-1, 1), (1, 9), 0).ravel()
    wmax = np.percentile(w, 92)
    eave = next((i for i in range(len(w)) if w[i] >= 0.8 * wmax), 0)
    return eave / max(1, (y1 - y0))                                 # Traufe als Höhenanteil


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True); ap.add_argument("--foto", default="hf_front")
    ap.add_argument("--glb", default=None)
    ap.add_argument("--az", default="270,285,300,315,330"); ap.add_argument("--el", default="6,12,18")
    a = ap.parse_args()
    md = f"modelle/{a.name}"; glb = a.glb or f"{md}/hofgut_hybrid.glb"
    foto = cv2.imread(f"daten/{a.name}/fotos/{a.foto}.jpg")
    fmask = cv2.imread(f"daten/{a.name}/fotos/{a.foto}_mask.png", 0)
    if fmask is None:
        raise SystemExit("erst gebaeude_segment.py (Maske fehlt)")
    fm = (fmask > 127).astype(np.uint8); ys, xs = np.where(fm); fb = (xs.min(), ys.min(), xs.max(), ys.max())

    # SILHOUETTEN-FIT: beste Kamera-Pose suchen
    best = (-1, None, None, None)
    for az in [int(x) for x in a.az.split(",")]:
        for el in [int(x) for x in a.el.split(",")]:
            rp = render(glb, f"/tmp/ob_{az}_{el}", az, el)
            im, mm, mb = model_mask(rp)
            if mm is None:
                continue
            iou, mcr, fcr = iou_bboxaligned(mm, mb, fm, fb)
            if iou > best[0]:
                best = (iou, az, el, (im, mm, mb))
    iou, az, el, (im, mm, mb) = best

    # Overlay bauen: Modell (Farbe) auf Foto-bbox skalieren + halbtransparent drüber
    mx0, my0, mx1, my1 = mb; fx0, fy0, fx1, fy1 = fb; W, H = fx1 - fx0, fy1 - fy0
    mcrop = im[my0:my1, mx0:mx1]; mmc = (mm[my0:my1, mx0:mx1] > 0)
    mcrop = cv2.resize(mcrop, (W, H)); mmc = cv2.resize(mmc.astype(np.uint8), (W, H)) > 0
    ov = foto.copy()
    roi = ov[fy0:fy1, fx0:fx1]
    roi[mmc] = (0.45 * roi[mmc] + 0.55 * mcrop[mmc]).astype(np.uint8)
    # Konturen: Foto-Gebäude (grün) vs Modell (magenta) → Element-Abgleich sichtbar
    cnt_f, _ = cv2.findContours(fm[fy0:fy1, fx0:fx1], cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cnt_m, _ = cv2.findContours(mmc.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cv2.drawContours(roi, cnt_f, -1, (0, 230, 0), 2); cv2.drawContours(roi, cnt_m, -1, (230, 0, 230), 2)

    eave_f = h_bands(fm); eave_m = h_bands(mm)
    score = round(100 * iou)
    cv2.putText(ov, f"OVERLAY-BEWERTER  IoU {iou:.2f} ({score}/100)  Pose az{az}/el{el}",
                (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 3)
    cv2.putText(ov, f"gruen=Foto  magenta=Modell  Traufe Foto {eave_f:.2f} / Modell {eave_m:.2f}",
                (10, 58), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)
    cv2.imwrite(f"{md}/overlay_bewerter.png", ov)
    json.dump({"foto": a.foto, "pose_az": az, "pose_el": el, "iou": round(iou, 3), "score": score,
               "eave_frac_foto": round(eave_f, 3), "eave_frac_modell": round(eave_m, 3)},
              open(f"{md}/overlay_score.json", "w"), indent=1)
    print(f"=== PERSPEKTIV-OVERLAY-BEWERTER ({a.foto}) ===")
    print(f"  beste Pose az{az}/el{el}  -  Silhouetten-IoU {iou:.2f}  ->  {score}/100")
    print(f"  Traufe-Höhenanteil: Foto {eave_f:.2f} vs Modell {eave_m:.2f}")
    print(f"-> {md}/overlay_bewerter.png (gruen=Foto, magenta=Modell)")


if __name__ == "__main__":
    main()
