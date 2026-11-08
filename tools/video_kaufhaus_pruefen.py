#!/usr/bin/env python3
"""video_kaufhaus_pruefen.py - Zeigt ein Video-Clip das Objekt? (Vorab-Filter fuer fremde Videos; Nutzer 7.11.)
  /media/oem/scan/venv-seg/bin/python -I tools/video_kaufhaus_pruefen.py FRAMES_DIR REF_FOTOS_DIR [--n-ref 12] [--min-inlier 25] [--aus x.json]
Je Frame SIFT-Matches (Lowe 0,75) + RANSAC-Homographie gegen die Referenzfotos; Frame 'zeigt Objekt' bei >= min-inlier Inliern gegen mind. ein Referenzfoto.
Grobes Vorurteil (Homographie gilt nur fuer ebene Fassade) - KEINE Hoehen-/Lagebestimmung; Ausgabe: Treffer je Frame, Zusammenfassung. Nur Lesen."""
import sys, os, glob, json, argparse, cv2, numpy as np
ap = argparse.ArgumentParser(); ap.add_argument("frames"); ap.add_argument("ref"); ap.add_argument("--n-ref", type=int, default=12); ap.add_argument("--min-inlier", type=int, default=25); ap.add_argument("--aus"); a = ap.parse_args()
sift = cv2.SIFT_create(2000); bf = cv2.BFMatcher()
refs = sorted(glob.glob(os.path.join(a.ref, "*.jp*g")) + glob.glob(os.path.join(a.ref, "*.JPG")))
refs = [refs[i] for i in np.linspace(0, len(refs) - 1, min(a.n_ref, len(refs))).astype(int)]
def feat(p, w=960):
    im = cv2.imread(p, cv2.IMREAD_GRAYSCALE)
    if im is None: return None
    s = w / im.shape[1]; im = cv2.resize(im, None, fx=s, fy=s) if s < 1 else im
    return sift.detectAndCompute(im, None)
R = [(os.path.basename(p), feat(p)) for p in refs]
fr = sorted(glob.glob(os.path.join(a.frames, "*.jpg"))); res = []
for p in fr:
    k = feat(p, 960)
    if k is None or k[1] is None: res.append(dict(frame=os.path.basename(p), best=0)); continue
    best = 0; bn = ""
    for nm, (kr, dr) in [(n, f) for n, f in R if f and f[1] is not None]:
        m = [x[0] for x in bf.knnMatch(k[1], dr, k=2) if len(x) == 2 and x[0].distance < 0.75 * x[1].distance]
        if len(m) < a.min_inlier: continue
        H, mask = cv2.findHomography(np.float32([k[0][x.queryIdx].pt for x in m]), np.float32([kr[x.trainIdx].pt for x in m]), cv2.RANSAC, 5.0)
        n = int(mask.sum()) if mask is not None else 0
        if n > best: best, bn = n, nm
    res.append(dict(frame=os.path.basename(p), best=best, ref=bn))
tr = [r for r in res if r["best"] >= a.min_inlier]
print(f"{a.frames}: {len(res)} Frames, {len(tr)} zeigen das Objekt ({100*len(tr)/max(1,len(res)):.1f} %)")
if a.aus: json.dump(dict(n=len(res), treffer=len(tr), frames=res), open(a.aus, "w"), indent=1)
