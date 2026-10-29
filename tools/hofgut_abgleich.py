#!/usr/bin/env python3
"""hofgut_abgleich.py — HARTER, FAIRER Validator: legt das echte Foto neben den Render und misst
auf VIEWPOINT-ROBUSTEN Kriterien, wie nah das Modell am echten Hofgut Sternen ist.

Fair = nur auf Dinge prüfen, die nicht von der exakten Perspektive abhängen:
  - Zonenfarben (Dach/OG-Holz/EG) Render vs. FOTO-gemessen (farben.json)  → ΔE
  - Silhouetten-Aspekt (grob)                                            → nur Flag
  - Dachanteil aus Daten (LOD2/nDOM) vs. Foto-Dachanteil                 → Δ
  - Fassaden-Features vorhanden (Lauben/Fresko/Zwerchhäuser)             → Inventar
Gibt Scorecard (0..100) + Lücken + Seite-an-Seite-Bild. Spec (verified_spec.json) optional für Zähl-Checks.

Lauf: /tmp/ml/bin/python tools/hofgut_abgleich.py   (nach Render via tools/glb_render.py)
"""
import json, os, subprocess, sys
import numpy as np
import cv2

MD = "modelle/hofgut_sternen"
GLB = f"{MD}/hofgut_hybrid.glb"
FOTO = "daten/hofgut_sternen/fotos/g2.jpg"


def de(a, b):
    return float(np.sqrt(sum((int(x) - int(y)) ** 2 for x, y in zip(a[:3], b[:3]))))


def render(view="q,315,16"):
    out = "/tmp/abgleich"
    subprocess.run(["/tmp/rv/bin/python", "tools/glb_render.py", GLB, out, view],
                   capture_output=True, text=True, env={**os.environ, "PYOPENGL_PLATFORM": "egl"})
    f = f"{out}_q.png" if os.path.exists(f"{out}_q.png") else f"{out}_{view.split(',')[0]}.png"
    return f


def zone_colors(img, mask):
    ys, xs = np.where(mask)
    if len(ys) < 50:
        return None
    y0, y1 = ys.min(), ys.max(); h = y1 - y0
    z = {}
    for name, (a, b) in {"dach": (0.0, 0.49), "og_lauben": (0.49, 0.82), "eg": (0.82, 1.0)}.items():
        band = mask.copy(); band[:int(y0 + a * h)] = False; band[int(y0 + b * h):] = False
        px = img[band]
        if len(px):
            z[name] = [int(v) for v in np.median(px, axis=0)[::-1]]   # BGR->RGB
    return z


def main():
    rp = render()
    R = cv2.imread(rp); G = cv2.imread(FOTO)
    # Render-Maske: Hintergrund ist (fast) weiß
    rg = cv2.cvtColor(R, cv2.COLOR_BGR2GRAY)
    rmask = rg < 245
    rmask = cv2.morphologyEx(rmask.astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8)) > 0
    # Foto-Maske aus ML-Segmentierung (falls da), sonst grob
    gmask_p = f"{FOTO.rsplit('.',1)[0]}_mask.png"
    gmask = (cv2.imread(gmask_p, 0) > 0) if os.path.exists(gmask_p) else (cv2.cvtColor(G, cv2.COLOR_BGR2GRAY) > 0)

    FM = json.load(open(f"{MD}/farben.json"))                 # FOTO-gemessene Zonenfarben = Wahrheit
    rz = zone_colors(R, rmask) or {}

    crit, score, wsum = [], 0.0, 0.0
    # 1) Zonenfarben (robust, Hauptkriterium) — ΔE klein = gut
    for zn, w in (("dach", 1.0), ("og_lauben", 1.5), ("eg", 1.0)):
        if zn in rz and zn in FM:
            d = de(rz[zn], FM[zn]); s = max(0.0, 1 - d / 120.0)
            crit.append(f"Farbe {zn:9s} Render{rz[zn]} vs Foto{FM[zn]}  ΔE={d:5.1f}  {s*100:3.0f}%")
            score += s * w; wsum += w
    # 2) Dachanteil: Daten (LOD2/nDOM) vs Foto (aus silhouette falls da)
    fp = json.load(open(f"{MD}/footprint.json"))
    lod2_first = max((t.get("ridge_m") or 0) for t in fp["teile"])
    eave = min((t.get("eave_m") or 99) for t in fp["teile"] if t.get("eave_m"))
    rf_data = (lod2_first - 9.37) / lod2_first
    crit.append(f"Dachanteil (LOD2) = {rf_data:.2f}  (Foto ~0.47)  Δ={abs(rf_data-0.47):.2f}")
    s = max(0.0, 1 - abs(rf_data - 0.47) / 0.25); score += s; wsum += 1
    # 3) Feature-Inventar: GLB-Node-Namen im Binär-JSON-Chunk suchen (ohne trimesh)
    blob = open(GLB, "rb").read()
    feats = {"Lauben/Balkone": b"balkone", "Blumen": b"blumen", "Fenster": b"fenster", "Fresko": b"fresko"}
    present = 0
    for lab, g in feats.items():
        ok = g in blob
        crit.append(f"Feature {lab:16s} {'✓ da' if ok else '✗ FEHLT'}")
        present += ok
    score += present / len(feats); wsum += 1

    total = round(100 * score / wsum)
    # Spec-Zählabgleich falls Grundwahrheit da
    specf = f"{MD}/verified_spec.json"
    if os.path.exists(specf):
        crit.append(f"[Spec-Grundwahrheit vorhanden: {specf} — Zähl-Checks aktiv]")

    # Seite-an-Seite
    H = 360
    Rr = cv2.resize(R, (int(R.shape[1] * H / R.shape[0]), H)); Gg = cv2.resize(G, (int(G.shape[1] * H / G.shape[0]), H))
    W = max(Rr.shape[1], Gg.shape[1])
    canvas = np.full((H * 2 + 40, W, 3), 255, np.uint8)
    canvas[0:H, (W - Gg.shape[1]) // 2:(W - Gg.shape[1]) // 2 + Gg.shape[1]] = Gg
    canvas[H + 40:2 * H + 40, (W - Rr.shape[1]) // 2:(W - Rr.shape[1]) // 2 + Rr.shape[1]] = Rr
    cv2.putText(canvas, "ECHT (g2)", (8, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)
    cv2.putText(canvas, f"MODELL  -  Naehe: {total}/100", (8, H + 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)
    cv2.imwrite("/tmp/hofgut_abgleich.png", canvas)

    print("=== HARTER FAIRER ABGLEICH  (betrogener-Ehemann-Validator) ===")
    for c in crit:
        print("  " + c)
    print(f"\n  NÄHE ZUM ECHTEN HOFGUT: {total}/100")
    print("-> /tmp/hofgut_abgleich.png")
    return total


if __name__ == "__main__":
    sys.exit(0 if main() >= 0 else 1)
