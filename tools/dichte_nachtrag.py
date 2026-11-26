#!/usr/bin/env python3
"""dichte_nachtrag.py <voll-sparse> <dicht-ordner> <bilder-ordner> <aus-ordner> --zelle x0 x1 y0 y1 --ausrichtung SFM-AUSRICHTUNG.json [--min_punkte 20]

NACHTRAG VERWORFENER BILDER (Nutzer 26.11.2026, Schwabentor): dicht_bildwahl.py verwirft Bilder, die nur das Nebenhaus sehen (Zylinder um den Turm).
Messung: 39 Bilder, die die Nordzelle (x 5-10, y 5-20) sehen = 25 % der Beobachtungen (9 729 von 38 576), fehlen in der Dichtrechnung.
Dieses Werkzeug rechnet NUR fuer diese Bilder Tiefenkarten nach (GPU, PatchMatch) und baut einen Arbeitsordner, den tools/kachelfusion.py wie ein dichtes
Verzeichnis liest (alte Tiefenkarten als Symlinks + neue):
  1. Bilder des vollen Modells, die in <dicht>/stereo/patch-match.cfg FEHLEN und >= --min_punkte Sparse-Punkte (Spur >= 3) in der Zelle sehen (Modellrahmen).
  2. Modell = alte Bilder + diese (Rest abgemeldet), undistort_images (1600 px wie die Standardstufe) in <aus>.
  3. patch-match.cfg nur mit den neuen Bildern als Bezug (Quellen __auto__, 20), PatchMatch auf der GPU (photometrisch + Filter, window_step 2 wie 'schnell').
  4. <aus>/stereo/depth_maps/normal_maps: neue Karten + Symlinks auf die alten.
Voraussetzung: gleiche Kameras/Posen wie <dicht> (Entzerrung ist deterministisch je Kamera; Beleg: Pruefung Abmessung der alten Karten gegen die neuen Bilder, sonst Abbruch).
Verwandt: tools/dicht_bildwahl.py (verwirft), tools/dicht_modell.py (Standard-Dichtrechnung), tools/kachelfusion.py (liest <aus> als Arbeitsordner), tools/dichte_diagnose.py.
Vorlaeufer: keiner - die verworfenen Bilder wurden nie auf ihren Beitrag zu duennen Zellen geprueft.
"""
import os, sys, json, argparse
import numpy as np


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("voll"); ap.add_argument("dicht"); ap.add_argument("bilder"); ap.add_argument("aus")
    ap.add_argument("--zelle", type=float, nargs=4, required=True, metavar=("X0", "X1", "Y0", "Y1")); ap.add_argument("--ausrichtung", required=True)
    ap.add_argument("--min_punkte", type=int, default=20); ap.add_argument("--max_bilder", type=int, default=80); ap.add_argument("--nur_planen", action="store_true"); ap.add_argument("--window_step", type=int, default=2, help="PatchMatch window_step (2 = jeder zweite Pixel wie schnell, 1 = jeder Pixel)"); ap.add_argument("--praefix", help="nur Bilder, deren Name so beginnt (z. B. IMG_20261126 = neue Handyfotos)")
    a = ap.parse_args()
    import cv2, pycolmap
    T = json.load(open(a.ausrichtung))["transformation"]; s = T["s"]; R = cv2.Rodrigues(np.array(T["rvec"]))[0]; t = np.array(T["t"])
    alt = [l.strip() for l in open(os.path.join(a.dicht, "stereo", "patch-match.cfg")) if l.strip() and not l.startswith("__")]
    rec = pycolmap.Reconstruction(a.voll); x0, x1, y0, y1 = a.zelle; cnt = {}
    for p in rec.points3D.values():
        if p.track.length() < 3: continue
        m = (p.xyz - t) @ R / s
        if x0 <= m[0] < x1 and y0 <= m[1] < y1 and 0.5 < m[2] < 20:
            for e in p.track.elements: cnt[rec.images[e.image_id].name] = cnt.get(rec.images[e.image_id].name, 0) + 1
    neu = sorted((n for n, c in cnt.items() if n not in set(alt) and c >= a.min_punkte and (not a.praefix or n.startswith(a.praefix))), key=lambda n: -cnt[n])[:a.max_bilder]
    print(f"Bilder in der Zelle {len(cnt)}, davon nicht in der Dichtrechnung mit >= {a.min_punkte} Punkten: {len(neu)} (Summe Punkte {sum(cnt[n] for n in neu)})", flush=True)
    os.makedirs(a.aus, exist_ok=True); json.dump({"neu": neu, "punkte": {n: cnt[n] for n in neu}}, open(os.path.join(a.aus, "nachtrag.json"), "w"), indent=1)
    if a.nur_planen or not neu: return 0
    keep = set(alt) | set(neu); name2id = {im.name: i for i, im in rec.images.items()}
    for n, i in name2id.items():
        if n not in keep and rec.images[i].has_pose: rec.deregister_frame(rec.images[i].frame_id)
    sin = os.path.join(a.aus, "sparse_in"); os.makedirs(sin, exist_ok=True); rec.write(sin)
    uo = pycolmap.UndistortCameraOptions(); uo.max_image_size = 1600
    pycolmap.undistort_images(a.aus, sin, a.bilder, output_type="COLMAP", undistort_options=uo)
    # Beleg: gleiche Entzerrung wie die alte Dichtrechnung (Bildgroesse eines alten Bildes)
    from PIL import Image
    n0 = alt[0]; g_neu = Image.open(os.path.join(a.aus, "images", n0)).size; g_alt = Image.open(os.path.join(a.dicht, "images", n0)).size
    if g_neu != g_alt: print(f"ABBRUCH: Entzerrung weicht ab {g_neu} gegen {g_alt} bei {n0}"); return 4
    pm = os.path.join(a.aus, "stereo", "patch-match.cfg"); open(pm, "w").write("".join(f"{n}\n__auto__, 20\n" for n in neu))
    po = pycolmap.PatchMatchOptions(); po.max_image_size = 1600; po.gpu_index = "0"; po.geom_consistency = False; po.filter = True; po.window_step = a.window_step
    pycolmap.patch_match_stereo(a.aus, options=po)
    for x in ("depth_maps", "normal_maps"):
        for n in alt:
            for art in ("photometric",):
                f = os.path.join(a.dicht, "stereo", x, f"{n}.{art}.bin"); z = os.path.join(a.aus, "stereo", x, f"{n}.{art}.bin")
                if os.path.exists(f) and not os.path.exists(z): os.symlink(os.path.realpath(f), z)
    nn = sum(os.path.exists(os.path.join(a.aus, "stereo", "depth_maps", f"{n}.photometric.bin")) for n in neu)
    print(f"FERTIG {nn}/{len(neu)} neue Tiefenkarten in {a.aus}", flush=True); return 0 if nn else 3


if __name__ == "__main__":
    sys.exit(main())
