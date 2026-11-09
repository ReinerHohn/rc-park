"""Drahtgitter ohne Sichtbarkeitstest ueber ein kalibriertes Foto legen (Dach/Hoehe, wo die Wolke fehlt). Aufruf: gitter_overlay.py KAM.json BILD SEG.json OUT.jpg [--zmin 14]"""
import sys, json, numpy as np, cv2, os
kam = json.load(open(sys.argv[1])); f = os.path.basename(sys.argv[2]); k = kam[f]; im = cv2.imread(sys.argv[2], cv2.IMREAD_COLOR | cv2.IMREAD_IGNORE_ORIENTATION)
zmin = float(sys.argv[sys.argv.index("--zmin") + 1]) if "--zmin" in sys.argv else -99; S = json.load(open(sys.argv[3]))["segmente"]; R = np.array(k["Rn"]); t = np.array(k["tn"]); s = im.shape[1] / k["W"]
def pr(p):
    X = R @ np.array(p) + t; x = X[0] / X[2]; y = X[1] / X[2]; f1 = 1 + k["params"][3] * (x * x + y * y); return (int((k["f"] * x * f1 + k["cx"]) * s), int((k["f"] * y * f1 + k["cy"]) * s)), X[2]
col = {0: (60, 60, 255), 1: (255, 125, 60), 2: (80, 200, 80), 3: (30, 150, 240)}
for sg in S:
    if max(sg[0][2], sg[1][2]) < zmin: continue
    for n in range(12):
        a = np.array(sg[0]) + (np.array(sg[1]) - np.array(sg[0])) * n / 12; b = np.array(sg[0]) + (np.array(sg[1]) - np.array(sg[0])) * (n + 1) / 12
        (p, za), (q, zb) = pr(a), pr(b)
        if za > 1 and zb > 1: cv2.line(im, p, q, col.get(sg[2], (0, 255, 255)), 4, cv2.LINE_AA)
cv2.imwrite(sys.argv[4], cv2.resize(im, (1200, int(1200 * im.shape[0] / im.shape[1]))))
