"""LIMAP (BSD-3) 3D-Liniensegmente aus dem dichten COLMAP-Ergebnis (entzerrte Fotos 1600 px + MVS-Tiefenkarten).
Aufruf (venv-limap): limap_lauf.py <dicht_dir> <out_dir> [detektor=lsd]
Tiefenkarten statt Wolke-Rendering: sind je Pixel schon organisiert und konsistent zu den Kameras (Rahmen = COLMAP-Rahmen, nach Netzrahmen: + rahmen_verschiebung)."""
import sys, os, logging; from pathlib import Path
import numpy as np, pycolmap
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
from limap.runners import GeometryGuidedLineReconstructionOptions as O, line_reconstruction_with_depth_maps
from limap.scene.depth_readers import BaseDepthReader
logging.basicConfig(level=logging.INFO)
import tiefen_kameras as TK
def lies_bin(p):
    D = np.ascontiguousarray(TK.lies_tiefe(p), dtype=np.float64); D[~(D > 0)] = np.inf; return D     # limap erwartet inf (nicht 0) fuer ungueltig; 0 -> Segfault in estimate_line3d_robust
class R(BaseDepthReader):
    def read(self, fn): return lies_bin(fn)
dicht, out = Path(sys.argv[1]), Path(sys.argv[2]); det = sys.argv[3] if len(sys.argv) > 3 else "lsd"
rec = pycolmap.Reconstruction(dicht / "sparse")
rd = {i: R(str(dicht / "stereo" / "depth_maps" / (im.name + ".geometric.bin"))) for i, im in rec.images.items()}
o = O(); o.max_image_dim = None; o.skip_exists = False; o.run_bundle_adjustment = False; o.n_visible_views = 3
o.line_detection.detector_method = det; o.line_detection.extractor_method = None; o.line_detection.compute_descinfo = False
o._line_detection.detector_method = det; o._line_detection.extractor_method = None; o._line_detection.compute_descinfo = False
o._fitting.n_jobs = 1
print(line_reconstruction_with_depth_maps(o, dicht / "images", dicht / "sparse", out, rd))
