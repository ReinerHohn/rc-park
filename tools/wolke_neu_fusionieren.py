#!/usr/bin/env python3
"""wolke_neu_fusionieren.py <objekt.json> <pipe-ordner> [--stufe schnell|fein] - dichte Wolke OHNE die unplausiblen Kameras neu fusionieren.

Warum (Schwabentor 15.11.2026): eine Geisterwand (Haufen auf der Strasse, Grundriss-Tor rc 3) kam aus Bildern eines Videoclips, deren Kameras unter dem
Gelaende standen. tools/kamera_plausibel.py schreibt diese Bilder nach audit/kamera_plausibel.json ('ausschliessen'). Hier: fusion.cfg ohne sie neu
schreiben, stereo_fusion (CPU, Minuten; Tiefenkarten bleiben), alte fused.ply -> fused_alle.ply, dann die VORHANDENE Ausrichtung auf die neue Wolke
anwenden (X_m = R^T (X_sfm - t) / s, keine neue LoD2-Suche) -> sfm/punkte_modell_<name>.npy + punkte_farben_<name>.npy.
  /media/oem/scan/venv-colmap/bin/python -I tools/wolke_neu_fusionieren.py modelle/<obj>/objekt.json /media/oem/scan/rc-park_daten/<obj>/pipe
Danach die Tore wiederholen (gesamtkette.py --ab tore bzw. wolke_grundriss_pruefen.py). rc 2 = nichts auszuschliessen.
"""
import sys, os, json, shutil, numpy as np


def ply_lesen(p):
    with open(p, "rb") as f:
        kopf = b""
        while not kopf.endswith(b"end_header\n"): kopf += f.readline()
        n = int([l for l in kopf.decode().splitlines() if l.startswith("element vertex")][0].split()[-1])
        props = [l.split()[1:] for l in kopf.decode().splitlines() if l.startswith("property")]
        dt = np.dtype([(nm, {"float": "<f4", "uchar": "u1", "double": "<f8"}[t]) for t, nm in props]); return np.frombuffer(f.read(n * dt.itemsize), dtype=dt, count=n)


def main():
    import pycolmap
    from scipy.spatial.transform import Rotation as Rot
    objp, pipe = os.path.abspath(sys.argv[1]), sys.argv[2]; od = os.path.dirname(objp); name = os.path.basename(od)
    stufe = sys.argv[sys.argv.index("--stufe") + 1] if "--stufe" in sys.argv else "schnell"
    aus = set(json.load(open(os.path.join(od, "audit", "kamera_plausibel.json")))["ausschliessen"]); D = os.path.join(pipe, "dicht"); cfg = os.path.join(D, "stereo", "fusion.cfg")
    alle = [l.strip() for l in open(cfg) if l.strip()] if os.path.exists(cfg) else sorted(os.listdir(os.path.join(D, "images")))
    bleibt = [b for b in alle if os.path.splitext(b)[0] not in aus]; print(f"Fusion: {len(alle)} Bilder, {len(alle) - len(bleibt)} ausgeschlossen (Kameras unter Gelaende), {len(bleibt)} bleiben")
    if len(bleibt) == len(alle): return 2
    if not os.path.exists(cfg + ".alle"): open(cfg + ".alle", "w").write("\n".join(alle) + "\n")
    open(cfg, "w").write("\n".join(bleibt) + "\n"); f = os.path.join(D, "fused.ply")
    if os.path.exists(f) and not os.path.exists(os.path.join(D, "fused_alle.ply")): shutil.move(f, os.path.join(D, "fused_alle.ply"))
    fo = pycolmap.StereoFusionOptions(); fo.max_image_size = 1600
    if stufe == "schnell": fo.min_num_pixels = 8
    pycolmap.stereo_fusion(f, D, options=fo, input_type="geometric" if stufe == "fein" else "photometric", output_type="ply")
    T = json.load(open(os.path.join(od, "messprotokoll", f"SFM-AUSRICHTUNG-{name}.json")))["transformation"]; s = T["s"]; R = Rot.from_rotvec(T["rvec"]).as_matrix(); t = np.array(T["t"])
    V = ply_lesen(f); X = np.c_[V["x"], V["y"], V["z"]].astype(float); Pm = ((X - t) / s) @ R
    np.save(os.path.join(od, "sfm", f"punkte_modell_{name}.npy"), Pm.astype(np.float32)); np.save(os.path.join(od, "sfm", f"punkte_farben_{name}.npy"), np.c_[V["red"], V["green"], V["blue"]].astype(np.uint8))
    print(f"neue Wolke: {len(Pm)} Punkte, z p1 {np.percentile(Pm[:, 2], 1):.1f} .. p99 {np.percentile(Pm[:, 2], 99):.1f} m -> sfm/punkte_modell_{name}.npy"); return 0


if __name__ == "__main__":
    sys.exit(main())
