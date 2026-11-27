#!/usr/bin/env python3
"""runpod_paket.py <sparse> <bilder> <aus-ordner> [--name handy_teil] [--mini 20 --box X0 X1 Y0 Y1 --ausrichtung SFM-AUSRICHTUNG.json] [--nur_planen]

MINIMAL-DATENPAKET fuer eine dichte Wolke in der Cloud (Runpod, Nutzer 27.11.2026: lokal scheiterte die Fusion am RAM, 15 GB).
PatchMatch + Fusion brauchen NUR: das SfM-Modell (cameras/images/points3D/frames/rigs.bin) und die Rohbilder der registrierten Bilder;
die Entzerrung (undistort_images) laeuft in der Cloud (deterministisch je Kamera, spart Upload: entzerrte Bilder waeren groesser).
NICHT noetig: db.db (2,9 GB, nur Merkmale/Paare fuer SfM), lg.npz, Tiefenkarten, nicht registrierte Bilder.
Pruefungen VOR dem Paketieren (Abbruch rc 4): jedes registrierte Bild existiert, Bildgroesse == Kamera (width/height) - sonst bricht Undistort in der
Cloud ab (Vorfall 27.11. 00:03: Wasserzeichen-Streifen abgeschnitten, Hoehe 1425 statt 1500).
--mini N: nur die N Bilder, die die meisten Sparse-Punkte (Spur >= 3) in --box (Modellmeter, Rahmen aus --ausrichtung) sehen; Rest abgemeldet (Mini-Test).
Ausgabe: <aus>/<name>/{sparse,bilder,paket.json} und <aus>/<name>.tar.zst + .sha256 (tar mit zstd -T0 -1; JPG komprimiert kaum).
Verwandt: tools/cloud/runpod_dicht.sh (entpackt und rechnet), tools/cloud/runpod_dicht.py (Rechenkern), tools/dicht_modell.py (lokale Dichtstufe, gleiche Optionen),
tools/dichte_nachtrag.py (gleiche Bildauswahl-Logik je Zelle).
Vorlaeufer: tools/cloud/vast.sh hoch (laedt ganze Ordner am gleichen absoluten Pfad hoch, ungetestet) - hier stattdessen ein Paket mit Pruefsumme.
"""
import os, sys, json, shutil, argparse, hashlib, subprocess, time


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""): h.update(b)
    return h.hexdigest()


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("sparse"); ap.add_argument("bilder"); ap.add_argument("aus"); ap.add_argument("--name", default="handy_teil")
    ap.add_argument("--mini", type=int, default=0); ap.add_argument("--box", type=float, nargs=4, metavar=("X0", "X1", "Y0", "Y1")); ap.add_argument("--ausrichtung")
    ap.add_argument("--zmin", type=float, default=0.5); ap.add_argument("--zmax", type=float, default=20.0); ap.add_argument("--nur_planen", action="store_true")
    a = ap.parse_args(argv)
    import numpy as np, pycolmap
    from PIL import Image
    rec = pycolmap.Reconstruction(a.sparse)
    reg = {i: im for i, im in rec.images.items() if im.has_pose}
    print(f"Modell {a.sparse}: {len(reg)} registrierte Bilder, {rec.num_points3D()} Punkte", flush=True)
    if a.mini:
        if not (a.box and a.ausrichtung): print("ABBRUCH: --mini braucht --box und --ausrichtung"); return 2
        import cv2
        T = json.load(open(a.ausrichtung))["transformation"]; s = T["s"]; R = cv2.Rodrigues(np.array(T["rvec"]))[0]; t = np.array(T["t"])
        x0, x1, y0, y1 = a.box; cnt = {}
        for p in rec.points3D.values():
            if p.track.length() < 3: continue
            m = (p.xyz - t) @ R / s
            if x0 <= m[0] < x1 and y0 <= m[1] < y1 and a.zmin < m[2] < a.zmax:
                for e in p.track.elements: cnt[e.image_id] = cnt.get(e.image_id, 0) + 1
        wahl = sorted(cnt, key=cnt.get, reverse=True)[:a.mini]
        print(f"Mini: {len(cnt)} Bilder sehen die Box, gewaehlt {len(wahl)} (Punkte je Bild {cnt[wahl[0]] if wahl else 0}..{cnt[wahl[-1]] if wahl else 0})", flush=True)
        if len(wahl) < 3: print("ABBRUCH: zu wenige Bilder in der Box"); return 3
        for i in list(reg):
            if i not in set(wahl): rec.deregister_frame(rec.images[i].frame_id)
        reg = {i: rec.images[i] for i in wahl}
    # Pruefung Bild <-> Kamera
    fehl, falsch, groessen = [], [], {}
    for i, im in reg.items():
        p = os.path.join(a.bilder, im.name)
        if not os.path.isfile(p): fehl.append(im.name); continue
        w, h = Image.open(p).size; c = rec.cameras[im.camera_id]
        if (w, h) != (c.width, c.height): falsch.append(f"{im.name}: Bild {w}x{h}, Kamera {c.width}x{c.height}")
        groessen[f"{w}x{h}"] = groessen.get(f"{w}x{h}", 0) + 1
    print(f"Bildgroessen: {groessen}; fehlend {len(fehl)}, Groesse falsch {len(falsch)}", flush=True)
    for z in (fehl[:5] + falsch[:5]): print("  ", z)
    if fehl or falsch: print("ABBRUCH: Bilder passen nicht zum Modell (Undistort wuerde in der Cloud abbrechen)"); return 4
    roh = sum(os.path.getsize(os.path.join(a.bilder, im.name)) for im in reg.values())
    print(f"Bilder {len(reg)}, {roh / 1e6:.0f} MB roh", flush=True)
    if a.nur_planen: return 0
    d = os.path.join(a.aus, a.name); shutil.rmtree(d, ignore_errors=True); os.makedirs(os.path.join(d, "bilder")); os.makedirs(os.path.join(d, "sparse"))
    rec.write(os.path.join(d, "sparse"))
    for im in reg.values():
        z = os.path.join(d, "bilder", im.name); os.makedirs(os.path.dirname(z), exist_ok=True)
        shutil.copy2(os.path.realpath(os.path.join(a.bilder, im.name)), z)   # Symlinks aufloesen
    meta = {"erstellt": time.strftime("%F %T"), "quelle_sparse": os.path.abspath(a.sparse), "quelle_bilder": os.path.abspath(a.bilder), "bilder": len(reg),
            "bildgroessen": groessen, "roh_mb": round(roh / 1e6, 1), "pycolmap": pycolmap.__version__, "mini": a.mini, "box": a.box, "ausrichtung": a.ausrichtung,
            "sparse_sha256": {f: sha256(os.path.join(d, "sparse", f)) for f in sorted(os.listdir(os.path.join(d, "sparse")))}}
    json.dump(meta, open(os.path.join(d, "paket.json"), "w"), indent=1)
    tz = os.path.join(a.aus, a.name + ".tar.zst")
    rc = subprocess.call(["tar", "-I", "zstd -T0 -1", "-cf", tz, "-C", a.aus, a.name])
    if rc: print("ABBRUCH: tar/zstd rc", rc); return rc
    open(tz + ".sha256", "w").write(f"{sha256(tz)}  {os.path.basename(tz)}\n")
    print(f"FERTIG {tz} {os.path.getsize(tz) / 1e6:.0f} MB (Upload bei 8,5 GB/h ~{os.path.getsize(tz) / 8.5e9 * 60:.1f} min, ANNAHME Messung 20.11.)", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
