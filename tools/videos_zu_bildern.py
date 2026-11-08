#!/usr/bin/env python3
"""videos_zu_bildern.py <videoordner> <ausordner> [fps=2] [min_schaerfe=60]
Alle Videos eines Ordners -> scharfe Einzelbilder vid_<clip>_<nn>.jpg (ffmpeg dreht nach Metadaten selbst).
Schaerfe = Laplace-Varianz; je Clip werden unscharfe Bilder verworfen. Manifest manifest.json."""
import sys, os, glob, json, subprocess, tempfile, shutil
import cv2
vd, out = sys.argv[1], sys.argv[2]; fps = float(sys.argv[3]) if len(sys.argv) > 3 else 2.0; ms = float(sys.argv[4]) if len(sys.argv) > 4 else 60.0
os.makedirs(out, exist_ok=True); man = []; roh = 0
for v in sorted(glob.glob(os.path.join(vd, "*.MOV")) + glob.glob(os.path.join(vd, "*.mp4"))):
    clip = os.path.splitext(os.path.basename(v))[0]; t = tempfile.mkdtemp(dir=out)
    subprocess.run(["ffmpeg", "-v", "error", "-i", v, "-vf", f"fps={fps}", "-q:v", "2", os.path.join(t, "f_%03d.jpg")], check=True)
    for f in sorted(glob.glob(os.path.join(t, "*.jpg"))):
        roh += 1; s = cv2.Laplacian(cv2.imread(f, cv2.IMREAD_GRAYSCALE), cv2.CV_64F).var()
        if s >= ms:
            dst = os.path.join(out, f"vid_{clip}_{os.path.basename(f)[2:]}"); os.replace(f, dst); man.append({"file": os.path.basename(dst), "clip": clip, "schaerfe": round(s, 1)})
    shutil.rmtree(t)
json.dump({"fps": fps, "min_schaerfe": ms, "roh": roh, "frames": man}, open(os.path.join(out, "manifest.json"), "w"), indent=1)
print(f"{len(man)} scharfe Bilder von {roh} Rohbildern -> {out}")
