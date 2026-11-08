#!/usr/bin/env python3
"""dicht_fusion.py <arbeitsordner> <aus.ply> [min_pixel=8] [max_reproj=1.0] [max_tiefenfehler=0.01]
Nur die Fusion (CPU) mit STRENGEREN Optionen als iphone_dicht.py (Standard min_num_pixels=5): ein Punkt bleibt nur, wenn >= min_pixel Tiefenkarten ihn
bestaetigen. Gegen Ausreisser-Spiesse durch Glas/Fenster (Nutzer 8.11.). Tiefenkarten (stereo/) muessen im Arbeitsordner liegen."""
import sys, time, pycolmap
w, out = sys.argv[1:3]; mp = int(sys.argv[3]) if len(sys.argv) > 3 else 8; mr = float(sys.argv[4]) if len(sys.argv) > 4 else 1.0; md = float(sys.argv[5]) if len(sys.argv) > 5 else 0.01
o = pycolmap.StereoFusionOptions(); o.min_num_pixels = mp; o.max_reproj_error = mr; o.max_depth_error = md; t = time.time()
pycolmap.stereo_fusion(out, w, output_type="PLY", options=o); print("fusion", round(time.time() - t), "s ->", out, flush=True)
