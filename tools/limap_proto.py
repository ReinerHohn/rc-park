"""LIMAP-Prototyp Stufe 2 (venv-limap): limap_proto.py OUTDIR [--detektor lsd]  (nach limap_proto_vor.py)"""
import sys, os, logging, numpy as np
from pathlib import Path
out = Path(sys.argv[1]); DET = sys.argv[sys.argv.index("--detektor") + 1] if "--detektor" in sys.argv else "lsd"
import pycolmap; 
from limap.runners import GeometryGuidedLineReconstructionOptions as O, line_reconstruction_with_depth_maps
from limap.scene.depth_readers import BaseDepthReader
class R(BaseDepthReader):
    def read(self, fn): return np.load(fn.replace(".jpg", ".jpg.npy") if not fn.endswith(".npy") else fn)
logging.basicConfig(level=logging.INFO); rec = pycolmap.Reconstruction(out / "sparse"); print("Rekonstruktion:", rec.summary() if hasattr(rec, "summary") else len(rec.images), flush=True)
rd = {i: R(str(out / "depth" / (im.name + ".npy"))) for i, im in rec.images.items()}
o = O(); o.max_image_dim = None; o.skip_exists = False; o.run_bundle_adjustment = False; o.n_visible_views = 3
o.line_detection.detector_method = DET; o.line_detection.extractor_method = None; o.line_detection.compute_descinfo = False
o._line_detection.detector_method = DET; o._line_detection.extractor_method = None; o._line_detection.compute_descinfo = False; o._fitting.n_jobs = 1
Cc = {i: -np.array(im.cam_from_world().rotation.matrix()).T @ np.array(im.cam_from_world().translation) for i, im in rec.images.items()}      # Kamerazentren; Nachbarn = alle anderen, nach Abstand (kleiner Ausschnitt, keine hloc-Triangulation)
nb = {i: [j for j in sorted(Cc, key=lambda j: np.linalg.norm(Cc[j] - Cc[i])) if j != i][:10] for i in Cc}
print(line_reconstruction_with_depth_maps(o, out / "images", out / "sparse", out / "lim", rd, neighbors=nb))
