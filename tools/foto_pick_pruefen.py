#!/usr/bin/env python3
"""foto_pick_pruefen.py - PFLICHT vor jedem Buendel: Picks (gruen) und projizierte Anker (blau, aus der Einzelkamera) ins Foto zeichnen, mit Namen.
  foto_pick_pruefen.py modelle/<objekt>/objekt.json <foto> <ausgabe.jpg> [--bundle]   (--bundle: Kamera aus dem Buendel statt Einzelloesung)"""
import sys, os, json, glob, numpy as np, cv2
objp, nr, out = sys.argv[1:4]; obj = json.load(open(objp)); root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(objp))))
od = os.path.join(root, os.path.dirname(obj["masstabelle"])); A = json.load(open(os.path.join(od, "anker3d.json")))["anker"]; K = json.load(open(os.path.join(od, "messprotokoll", f"K-{nr}.json")))
kam = K["kamera_bundle"] if "--bundle" in sys.argv and "kamera_bundle" in K else K["kamera"]
im = cv2.imread(glob.glob(os.path.join(root, obj["fotos_dir"], nr + "_*"))[0]); R, _ = cv2.Rodrigues(np.array(kam["rvec"])); t = np.array(kam["t"]); f = kam["f_px"]
def proj(X): Xc = X @ R.T + t; return np.c_[f * Xc[:, 0] / Xc[:, 2] + kam["cx"], f * Xc[:, 1] / Xc[:, 2] + kam["cy"]]
for n, p in K["punkte"].items():
    q = proj(np.array([A[n]["xyz"]]))[0]; cv2.circle(im, (int(p[0]), int(p[1])), 12, (0, 255, 0), 3); cv2.circle(im, (int(q[0]), int(q[1])), 12, (255, 0, 0), 3)
    cv2.line(im, (int(p[0]), int(p[1])), (int(q[0]), int(q[1])), (0, 0, 255), 2); cv2.putText(im, n, (int(p[0]) + 14, int(p[1]) - 6), 0, 0.9, (0, 255, 0), 2)
for n, pts in K.get("linien", {}).items():
    for p in pts: cv2.drawMarker(im, (int(p[0]), int(p[1])), (0, 200, 255), cv2.MARKER_CROSS, 24, 3)
    xy = A[n]["xyz"][:2]; l2 = proj(np.array([[xy[0], xy[1], 0.0], [xy[0], xy[1], 40.0]])); cv2.line(im, tuple(l2[0].astype(int)), tuple(l2[1].astype(int)), (255, 0, 255), 2)
cv2.imwrite(out, im); print("ANSEHEN:", out, "(gruen Pick, blau Anker projiziert, rot Residuum, magenta LoD2-Kante)")
