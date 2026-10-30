#!/usr/bin/env python3
"""dach_optimieren.py — autonome Varianten-Schleife mit dem OVERLAY-IoU als Zielfunktion.
Variiert Dach-Sweep (ROOF_SWEEP) + First-Länge/Spitzigkeit (ROOF_INSET), baut Massing+Hybrid neu,
rendert PERSPEKTIV-KORREKT aus der Foto-Pose und maximiert die Silhouetten-IoU gegen die Foto-Maske.
Beste Variante wird angewandt. Pose kommt aus overlay_score.json (vorher overlay_bewerter laufen).

Lauf: /tmp/ml/bin/python tools/dach_optimieren.py --name hofgut_sternen --foto hf_front
"""
import argparse, json, os, subprocess, itertools
import numpy as np
import cv2


def build(sweep, inset):
    env = {**os.environ, "ROOF_SWEEP": str(sweep), "ROOF_INSET": str(inset)}
    subprocess.run(["/tmp/rv/bin/python", "tools/hofgut_massing.py"], capture_output=True, env=env)
    subprocess.run(["/tmp/rv/bin/python", "tools/hofgut_hybrid.py"], capture_output=True, env=env)


def render(glb, out, az, el):
    subprocess.run(["/tmp/rv/bin/python", "tools/glb_render.py", glb, out, f"q,{az},{el}"],
                   capture_output=True, env={**os.environ, "PYOPENGL_PLATFORM": "egl", "GLB_LIGHT": "0.6"})
    return f"{out}_q.png"


def iou(png, fm, fb):
    g = cv2.cvtColor(cv2.imread(png), cv2.COLOR_BGR2GRAY); m = (g < 248).astype(np.uint8)
    ys, xs = np.where(m)
    if len(ys) < 50:
        return 0.0
    mb = (xs.min(), ys.min(), xs.max(), ys.max())
    fx0, fy0, fx1, fy1 = fb
    mc = cv2.resize(m[mb[1]:mb[3], mb[0]:mb[2]], (fx1 - fx0, fy1 - fy0), interpolation=cv2.INTER_NEAREST) > 0
    fc = fm[fy0:fy1, fx0:fx1] > 0
    return (mc & fc).sum() / max(1, (mc | fc).sum())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True); ap.add_argument("--foto", default="hf_front")
    ap.add_argument("--sweeps", default="0.35,0.45,0.60"); ap.add_argument("--insets", default="0.28,0.45,0.62")
    a = ap.parse_args()
    md = f"modelle/{a.name}"; glb = f"{md}/hofgut_hybrid.glb"
    fm = (cv2.imread(f"daten/{a.name}/fotos/{a.foto}_mask.png", 0) > 127).astype(np.uint8)
    ys, xs = np.where(fm); fb = (xs.min(), ys.min(), xs.max(), ys.max())
    sc = json.load(open(f"{md}/overlay_score.json")); az, el = sc["pose_az"], sc["pose_el"]

    print(f"Zielfunktion: Overlay-IoU gegen {a.foto} aus Pose az{az}/el{el}")
    print("sweep | inset | IoU")
    best = (-1, None, None)
    for sw, ins in itertools.product([float(x) for x in a.sweeps.split(",")],
                                     [float(x) for x in a.insets.split(",")]):
        build(sw, ins)
        val = iou(render(glb, f"/tmp/opt_{sw}_{ins}", az, el), fm, fb)
        print(f"  {sw:.2f} | {ins:.2f} | {val:.3f}")
        if val > best[0]:
            best = (val, sw, ins)
    val, sw, ins = best
    print(f"\n>> BESTE DACH-VARIANTE: sweep={sw} inset={ins}  (IoU {val:.3f}, {round(100*val)}/100)")
    build(sw, ins)                                              # anwenden
    json.dump({"roof_sweep": sw, "roof_inset": ins, "iou": round(val, 3)},
              open(f"{md}/best_roof.json", "w"), indent=1)
    print(f"-> angewandt + {md}/best_roof.json; overlay_bewerter neu laufen lassen für das Overlay")


if __name__ == "__main__":
    main()
