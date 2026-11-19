# Punkt 8: trifft uns der Rollverschluss? Je Videobild Drehgeschwindigkeit (Winkel zum Nachbarbild desselben Clips / Bildabstand) gegen mittleren Rueckprojektionsfehler
import pycolmap, numpy as np, re, sys
from scipy.stats import spearmanr
r = pycolmap.Reconstruction(sys.argv[1]); clips = {}
for im in r.images.values():
    m = re.match(r"(video_frames_[^_]+(?:_[^_]+)*?)__vf_(\d+)", im.name)
    if m: clips.setdefault(m.group(1), []).append((int(m.group(2)), im))
fehler = {}
for im in r.images.values():
    e = [np.linalg.norm(np.asarray(r.cameras[im.camera_id].img_from_cam(im.cam_from_world() * r.points3D[p.point3D_id].xyz)) - p.xy) for p in im.points2D if p.has_point3D()]
    if e: fehler[im.name] = float(np.mean(e))
w, f, rest = [], [], [fehler[n] for n in fehler if "video_frames" not in n]
for c, L in clips.items():
    L.sort(key=lambda x: x[0])
    for (a, ia), (b, ib) in zip(L, L[1:]):
        if b - a > 3: continue
        Ra, Rb = ia.cam_from_world().rotation.matrix(), ib.cam_from_world().rotation.matrix(); ang = np.degrees(np.arccos(np.clip((np.trace(Ra @ Rb.T) - 1) / 2, -1, 1))) / (b - a)
        w.append(ang); f.append((fehler.get(ia.name, np.nan) + fehler.get(ib.name, np.nan)) / 2)
w, f = np.array(w), np.array(f); k = np.isfinite(f)
print(f"{len(clips)} Clips, {k.sum()} Nachbarpaare; Fehler Videobilder Median {np.median(f[k]):.2f} px, Fotos {np.median(rest):.2f} px; Rangkorrelation Drehung~Fehler {spearmanr(w[k], f[k])[0]:.2f}")
for lo, hi in ((0, 0.5), (0.5, 2), (2, 1e9)):
    m = k & (w >= lo) & (w < hi)
    if m.sum(): print(f"  Drehung {lo}-{hi if hi < 1e9 else 'mehr'} Grad je Bildschritt: {m.sum()} Paare, Fehler Median {np.median(f[m]):.2f} px")
