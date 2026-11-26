#!/usr/bin/env python3
"""kachelfusion.py <dicht-ordner> <aus.ply> --ausrichtung SFM-AUSRICHTUNG.json [--kachel 12] [--radius 60] [--max_bilder 120] [--min_num_pixels 3]

KACHELFUSION (Nutzer 26.11.2026, Schwabentor): Tiefenkarten sind da (PatchMatch), die FUSION zu einer Wolke verliert Punkte, wenn sie in
Blickziel-Teilen laeuft (tools/teilfusion.py: nur Punkte, deren Bezugsbild zum Kern gehoert; Nachbarn je Teil begrenzt). Messung 26.11.: Nordzelle
hinter dem Tor 34 392 Punkte bisher, 174 126 bei EINER Fusion der 120 meistsehenden Bilder (gleiche Tiefenkarten).
Hier: RAUMKACHELN im Modellrahmen (waagerecht, jede Hoehe). Je Kachel nimmt die Fusion die Bilder, die die meisten Sparse-Punkte der Kachel (Spur >= 3) sehen,
bis --max_bilder (RAM: ~45 MB je Bild); behalten werden NUR Punkte, die in der Kachel liegen -> jede Flaeche genau einmal, aber mit ALLEN ihren Bildern.
Schreibt <aus.ply> (SfM-Rahmen wie fused.ply) und <aus.ply>.kacheln.json (je Kachel Bilder, Punkte, Sekunden). Ueberschreibt nie fused.ply.
Voraussetzung: <dicht>/stereo/depth_maps + normal_maps, <dicht>/sparse (undistort), <dicht>/images. Danach dieselben Nachfilter wie fused.ply (Drahtmaske, Quellfilter).
Verwandt: tools/teilfusion.py (Blickziel-Teile, wird ersetzt), tools/dicht_modell.py (ruft Fusion), tools/dichte_diagnose.py (misst vorher/nachher je Zelle).
Vorlaeufer: teilfusion.py - verlor je Teil bis 93 % der Punkte (Teil 3: 3,49 Mio -> 245 000), weil Bezugsbild-Filter + begrenzte Nachbarn.
"""
import os, sys, json, time, shutil, argparse
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("dicht"); ap.add_argument("aus"); ap.add_argument("--ausrichtung", required=True)
    ap.add_argument("--kachel", type=float, default=12.0); ap.add_argument("--radius", type=float, default=60.0); ap.add_argument("--max_bilder", type=int, default=120)
    ap.add_argument("--min_num_pixels", type=int, default=3); ap.add_argument("--max_image_size", type=int, default=1600); ap.add_argument("--min_sparse", type=int, default=30)
    ap.add_argument("--input_type", default="photometric"); ap.add_argument("--tmp", default="/media/oem/rcdaten/tmp/kachelfusion"); ap.add_argument("--nur", type=int, default=0, help="Test: nur die ersten N Kacheln")
    a = ap.parse_args()
    import cv2, pycolmap, teilfusion as TF
    T = json.load(open(a.ausrichtung))["transformation"]; s = T["s"]; R = cv2.Rodrigues(np.array(T["rvec"]))[0]; t = np.array(T["t"])
    rec = pycolmap.Reconstruction(os.path.join(a.dicht, "sparse"))
    xyz = []; spur = []
    for p in rec.points3D.values():
        if p.track.length() >= 3: xyz.append(p.xyz); spur.append([e.image_id for e in p.track.elements])
    M = (np.array(xyz) - t) @ R / s
    ki = np.floor(M[:, :2] / a.kachel).astype(int); kachel = {}
    for n, k in enumerate(map(tuple, ki)):
        if np.hypot((k[0] + .5) * a.kachel, (k[1] + .5) * a.kachel) <= a.radius: kachel.setdefault(k, []).append(n)
    ks = sorted(k for k, v in kachel.items() if len(v) >= a.min_sparse)
    if a.nur: ks = ks[:a.nur]
    print(f"Kacheln {a.kachel:g} m im Umkreis {a.radius:g} m: {len(ks)} (von {len(kachel)} mit Punkten)", flush=True)
    shutil.rmtree(a.tmp, ignore_errors=True); os.makedirs(os.path.join(a.tmp, "stereo"))
    for x in ("images", "sparse"): os.symlink(os.path.abspath(os.path.join(a.dicht, x)), os.path.join(a.tmp, x))
    for x in ("depth_maps", "normal_maps"): os.symlink(os.path.abspath(os.path.join(a.dicht, "stereo", x)), os.path.join(a.tmp, "stereo", x))
    names = {i: im.name for i, im in rec.images.items()}; teile = []; alle = []; t00 = time.time()
    for q, k in enumerate(ks):
        zeit = time.time(); cnt = {}
        for n in kachel[k]:
            for i in spur[n]: cnt[i] = cnt.get(i, 0) + 1
        top = sorted(cnt, key=cnt.get, reverse=True)[:a.max_bilder]
        open(os.path.join(a.tmp, "stereo", "fusion.cfg"), "w").write("\n".join(names[i] for i in top) + "\n")
        out = os.path.join(a.tmp, "k.ply")
        if os.path.exists(out): os.remove(out)
        fo = pycolmap.StereoFusionOptions(); fo.max_image_size = a.max_image_size; fo.min_num_pixels = a.min_num_pixels
        pycolmap.stereo_fusion(out, a.tmp, options=fo, input_type=a.input_type, output_type="ply")
        P = TF.ply_lesen(out); X = np.c_[P["x"], P["y"], P["z"]].astype(float); m = (X - t) @ R / s
        ok = (np.floor(m[:, 0] / a.kachel).astype(int) == k[0]) & (np.floor(m[:, 1] / a.kachel).astype(int) == k[1])
        alle.append(P[ok]); teile.append({"kachel": [k[0] * a.kachel, k[1] * a.kachel], "sparse": len(kachel[k]), "bilder": len(top), "punkte_fusion": int(len(P)), "punkte_kachel": int(ok.sum()), "sekunden": int(time.time() - zeit)})
        print(f"[{q + 1}/{len(ks)}] Kachel x {k[0] * a.kachel:.0f} y {k[1] * a.kachel:.0f}: {len(top)} Bilder, {int(ok.sum())} Punkte, {int(time.time() - zeit)} s", flush=True)
    G = np.concatenate(alle) if alle else np.zeros(0, TF.DT); TF.ply_schreiben(a.aus, G)
    json.dump({"kachel_m": a.kachel, "radius_m": a.radius, "max_bilder": a.max_bilder, "min_num_pixels": a.min_num_pixels, "punkte": int(len(G)), "sekunden": int(time.time() - t00), "kacheln": teile},
              open(a.aus + ".kacheln.json", "w"), indent=1)
    shutil.rmtree(a.tmp, ignore_errors=True); print("FERTIG", a.aus, len(G), "Punkte", flush=True); return 0


if __name__ == "__main__":
    sys.exit(main())
