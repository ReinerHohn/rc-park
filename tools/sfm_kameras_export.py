#!/usr/bin/env python3
"""sfm_kameras_export.py <sparse/N> <T.npz> <aus.json> - COLMAP-Kameras in den Netzrahmen legen (Aehnlichkeit R,s,t aus iphone_ausrichten.py): je Bild R (Welt->Kamera), t, C (Zentrum, m), f, cx, cy, W, H.
Grundlage fuer Foto-Terme im Fit (Regel 9d)."""
import sys, json, numpy as np, pycolmap
r = pycolmap.Reconstruction(sys.argv[1]); T = np.load(sys.argv[2]); R, s, t = T["R"], float(T["s"]), T["t"]; out = {}
for im in r.images.values():
    if not im.has_pose: continue
    cam = im.camera; M = im.cam_from_world().matrix()                                   # 3x4: x_cam = Rc X + tc  (SfM-Rahmen)
    Rc, tc = M[:, :3], M[:, 3]; C = -Rc.T @ tc; Cn = s * R @ C + t                      # Zentrum im Netzrahmen
    Rn = Rc @ R.T                                                                       # x_cam = Rn (X_n - t)/s + tc ... -> Welt(Netz)->Kamera: Rn X_n + (tc - Rn t)/... skaliert
    tn = (tc - Rn @ t / s) * s if False else tc * s - Rn @ t                           # x_cam*s = Rn X_n + tn  (Kameraraum um s skaliert; Projektion unveraendert)
    p = cam.params; mdl = cam.model.name
    f = float(p[0]); cx, cy = (float(p[1]), float(p[2])) if mdl in ("SIMPLE_RADIAL", "SIMPLE_PINHOLE", "RADIAL") else (float(p[2]), float(p[3]))
    out[im.name] = dict(Rn=Rn.tolist(), tn=tn.tolist(), C=Cn.tolist(), f=f, cx=cx, cy=cy, W=int(cam.width), H=int(cam.height), modell=mdl, params=[float(x) for x in p])
json.dump(out, open(sys.argv[3], "w")); print(len(out), "Kameras")
