"""LIMAP-Prototyp auswerten (venv-limap): limap_proto_zeigen.py OUTDIR PREFIX [--spur 3]. Schreibt Linien (npy) + Overlay auf 2 Fotos (gruen = Spurlaenge >= 5, gelb >= 3) + Frontansicht."""
import sys, os, numpy as np, cv2, pycolmap, limap.scene as S
from pathlib import Path
out = Path(sys.argv[1]); pre = sys.argv[2]; sp = int(sys.argv[sys.argv.index("--spur") + 1]) if "--spur" in sys.argv else 3
h = S.HolisticReconstruction(); h.read(str(out / "lim" / "geometry_guided_final_model")); sr = h.structure_recon; ids = sorted(sr.line3D_ids()); A = []; T = []
for i in ids: l = sr.line(i); A.append([l.start, l.end]); T.append(len(l.track.elements))
A = np.array(A, float); T = np.array(T); print("Linien", len(A), "Spur>=2:", int((T >= 2).sum()), ">=3:", int((T >= 3).sum()), ">=5:", int((T >= 5).sum()), "Laenge median %.2f" % np.median(np.linalg.norm(A[:, 1] - A[:, 0], axis=1)))
np.save(pre + "_linien.npy", A); np.save(pre + "_spur.npy", T); rec = pycolmap.Reconstruction(out / "sparse")
for iid in list(rec.images)[:3]:
    im = rec.images[iid]; cam = rec.cameras[im.camera_id]; img = cv2.imread(str(out / "images" / im.name)); R = np.array(im.cam_from_world().rotation.matrix()); t = np.array(im.cam_from_world().translation); f, cx, cy = cam.params[0], cam.params[2], cam.params[3]
    for (a, b), tr in zip(A, T):
        if tr < sp: continue
        P = a + (b - a) * np.linspace(0, 1, 20)[:, None]; Xc = P @ R.T + t
        if (Xc[:, 2] < 1).any(): continue
        uv = np.c_[f * Xc[:, 0] / Xc[:, 2] + cx, f * Xc[:, 1] / Xc[:, 2] + cy]; cv2.line(img, tuple(uv[0].astype(int)), tuple(uv[-1].astype(int)), (0, 200, 0) if tr >= 5 else (0, 220, 255), 2, cv2.LINE_AA)
    cv2.imwrite("%s_foto_%s" % (pre, im.name), img)
print("fertig")
