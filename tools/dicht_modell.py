#!/usr/bin/env python3
"""dicht_modell.py <sparse-ordner> <bilder-ordner> <aus-ordner> [--ohne unstabil.txt] [--stufe schnell|fein|grob] [--ohne-bildwahl]

Dichte Wolke fuer EIN beliebiges SfM-Modell (z.B. ein Seiten-Teilmodell aus tools/seiten_erkennen.py), gleiche Einstellungen wie die Stufe 'dicht' in
tools/pipeline_objekt.py (dort stehen Messungen und Begruendungen): Bildwahl (tools/dicht_bildwahl.py) -> Entzerren 1600 px -> PatchMatch (GPU; schnell = fotometrisch,
window_step 2) -> Fusion (schnell: min_num_pixels 8; passt sie nicht in 60 % des freien RAM: tools/teilfusion.py). Ergebnis <aus>/fused.ply.
Vorhandene Tiefenkarten werden wiederverwendet. GPU ~6 GB (JOB_GPU_MB=6500), RAM nach Bildzahl (100 Bilder ~4 GB)."""
import sys, os, glob, argparse, subprocess
T = os.path.dirname(os.path.abspath(__file__))


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("sparse"); ap.add_argument("bilder"); ap.add_argument("aus"); ap.add_argument("--ohne"); ap.add_argument("--stufe", default="schnell", choices=["schnell", "fein", "grob"]); ap.add_argument("--ohne-bildwahl", action="store_true")
    a = ap.parse_args(argv); import pycolmap; sys.path.insert(0, T); import gpu_buchung as GB
    os.makedirs(a.aus, exist_ok=True); sparse = a.sparse; wahl = os.path.join(a.aus, "sparse_dicht")
    if not a.ohne_bildwahl and a.stufe != "grob":
        if not os.path.isdir(wahl):
            r = subprocess.run([sys.executable, "-I", os.path.join(T, "dicht_bildwahl.py"), a.sparse, wahl] + (["--ohne", a.ohne] if a.ohne else []), capture_output=True, text=True); print((r.stdout + r.stderr).strip()[-400:], flush=True)
        if os.path.isdir(wahl) and os.path.isfile(os.path.join(wahl, "images.bin")): sparse = wahl
    GROB, FEIN = a.stufe == "grob", a.stufe == "fein"; n = pycolmap.Reconstruction(sparse).num_reg_images(); dm = os.path.join(a.aus, "stereo", "depth_maps")
    for k in glob.glob(os.path.join(a.aus, "stereo", "*_maps", "*.bin")):
        if os.path.getsize(k) < 2048: os.remove(k)
    fertig = os.path.isdir(dm) and len(glob.glob(os.path.join(dm, "*.photometric.bin"))) >= n and (not FEIN or len(glob.glob(os.path.join(dm, "*.geometric.bin"))) >= n)
    print(f"dichte Wolke: {n} Bilder, Stufe {a.stufe}" + (" (Tiefenkarten aus Cache)" if fertig else ""), flush=True)
    if not fertig:
        uo = pycolmap.UndistortCameraOptions(); uo.max_image_size = 1600; pycolmap.undistort_images(a.aus, sparse, a.bilder, output_type="COLMAP", undistort_options=uo)
        po = pycolmap.PatchMatchOptions(); po.max_image_size = 800 if GROB else 1600; po.gpu_index = "0"; po.geom_consistency = FEIN; po.filter = True
        if a.stufe == "schnell": po.window_step = 2
        pycolmap.patch_match_stereo(a.aus, options=po)
    fo = pycolmap.StereoFusionOptions(); fo.max_image_size = 800 if GROB else 1600
    if a.stufe == "schnell": fo.min_num_pixels = 8
    try: frei = int([l for l in open("/proc/meminfo") if l.startswith("MemAvailable")][0].split()[1]) / 1048576
    except Exception: frei = 8.0
    nf = len([l for l in open(os.path.join(a.aus, "stereo", "fusion.cfg")) if l.strip()]); bedarf = nf * (0.012 if GROB else 0.045); GB.frei(); ziel = os.path.join(a.aus, "fused.ply")
    print(f"Fusion: {nf} Bilder, Bedarf ~{bedarf:.1f} GB, frei {frei:.1f} GB", flush=True)
    if bedarf > 0.6 * frei:
        rc = subprocess.call([sys.executable, "-I", os.path.join(T, "teilfusion.py"), a.aus, ziel, "--max_image_size", str(fo.max_image_size), "--min_num_pixels", str(fo.min_num_pixels), "--input_type", "geometric" if FEIN else "photometric"])
        if rc: return rc
    else: pycolmap.stereo_fusion(ziel, a.aus, options=fo, input_type="geometric" if FEIN else "photometric", output_type="ply")
    print("FERTIG", ziel, os.path.getsize(ziel) if os.path.isfile(ziel) else 0, "Byte", flush=True); return 0 if os.path.isfile(ziel) and os.path.getsize(ziel) > 1000 else 3


if __name__ == "__main__": sys.exit(main())
