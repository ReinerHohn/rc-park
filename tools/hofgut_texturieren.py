#!/usr/bin/env python3
"""hofgut_texturieren.py — echte Oberfläche auf die KORREKTE Struktur: DOP-Luftbild (georeferenziert)
auf das vereinte Dach des Hybrid-Modells mappen. DOP ist das reale Dach von oben (20 cm) → das graue
Dach bekommt die echte Schindel-/Gauben-Textur. Transform model→UTM→DOP-px (massing_frame-Inverse),
DOP per Homographie in den Modell-Frame warpen → planare Top-Down-UV aufs Dach.

Lauf: /tmp/rv/bin/python tools/hofgut_texturieren.py
"""
import json, os
import numpy as np
import cv2
import trimesh
from PIL import Image

MD = "modelle/hofgut_sternen"
DOP = "daten/ravenna/dop/dop20rgb_32_429_5306_2_bw/dop20rgb_32_430_5307_1_bw_2025.tif"


def main():
    fr = json.load(open(f"{MD}/massing_frame.json")); fp = json.load(open(f"{MD}/footprint.json"))
    o = np.array(fp["origin_utm"][:2])
    ang = -fr["rot_angle"]; Rm = np.array([[np.cos(ang), -np.sin(ang)], [np.sin(ang), np.cos(ang)]])
    ctr = np.array(fr["ctr"]); flip = fr["flip"]; shift = np.array(fr["shift"])
    tfw = open(os.path.splitext(DOP)[0] + ".tfw").read().split()
    px, _, _, py, oxc, oyc = [float(x) for x in tfw]; E0, N0 = oxc - px / 2, oyc + (-py) / 2
    dop = cv2.imread(DOP)

    def model_to_dop(mx, my):                                  # Inverse des massing-Transforms → DOP-Pixel
        p1 = np.array([mx, my]) + shift
        if flip:
            p1 = p1 * np.array([1.0, -1.0])
        loc = p1 @ Rm + ctr
        E, N = loc[0] + o[0], loc[1] + o[1]
        return (E - E0) / px, (N0 - N) / (-py)

    sc = trimesh.load(f"{MD}/hofgut_hybrid.glb")
    roof = sc.geometry["daecher"]
    (x0, y0, _), (x1, y1, _) = roof.bounds[0], roof.bounds[1]
    # DOP per Homographie in den Modell-Frame (Top-Down) warpen → Textur W×H
    W, H = 1024, int(1024 * (y1 - y0) / (x1 - x0))
    src = np.float32([model_to_dop(x0, y1), model_to_dop(x1, y1), model_to_dop(x1, y0), model_to_dop(x0, y0)])
    dst = np.float32([[0, 0], [W, 0], [W, H], [0, H]])
    Mh = cv2.getPerspectiveTransform(src, dst)
    tex = cv2.warpPerspective(dop, Mh, (W, H))
    cv2.imwrite(f"{MD}/dach_textur.png", tex)
    teximg = Image.fromarray(cv2.cvtColor(tex, cv2.COLOR_BGR2RGB))

    # planare Top-Down-UV aufs Dach (x,y → u,v)
    V = roof.vertices
    uv = np.c_[(V[:, 0] - x0) / (x1 - x0), (V[:, 1] - y0) / (y1 - y0)]
    roof.visual = trimesh.visual.TextureVisuals(uv=uv, image=teximg)
    sc.geometry["daecher"] = roof
    sc.export(f"{MD}/hofgut_tex.glb")
    print(f"-> {MD}/hofgut_tex.glb (Dach = echtes DOP-Luftbild) + dach_textur.png")


if __name__ == "__main__":
    main()
