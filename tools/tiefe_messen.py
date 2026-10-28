#!/usr/bin/env python3
"""tiefe_messen.py — GEBÄUDETIEFE per ANALYSE-DURCH-SYNTHESE am Schrägfoto (generell).

Idee (nutzt die VALIDIERTEN Werkzeuge): die Tiefe D ist der Wert, bei dem das aus einem Schrägfoto
gefittete Modell am besten passt. Für jedes Kandidaten-D: Modell neu bauen → Kamera (az,el,fov) ans
Schrägfoto fitten (Score-Minimierung) → bester Rest-Score. Das D mit dem KLEINSTEN Rest-Score = Tiefe.
Gebäude-Crop kommt generell aus fassade_gitter (grünes Dach), nicht hardcodiert.

Lauf: /tmp/rv/bin/python tools/tiefe_messen.py [schraegfoto]
"""
import os, sys, json, subprocess, importlib.util
os.environ["PYOPENGL_PLATFORM"] = "egl"
import numpy as np, trimesh
from PIL import Image

ROOT = "/home/md/git/rc-park"
FOTO = sys.argv[1] if len(sys.argv) > 1 else f"{ROOT}/daten/kaufhaus_freiburg/fotos/kh_front2025b.jpg"
d = os.path.join(ROOT, "tools")
sys.argv = ["x"]
spec = importlib.util.spec_from_file_location("od", os.path.join(d, "overlay_diff.py")); od = importlib.util.module_from_spec(spec); spec.loader.exec_module(od)
spec2 = importlib.util.spec_from_file_location("kf", os.path.join(d, "kamera_fit.py")); kf = importlib.util.module_from_spec(spec2); spec2.loader.exec_module(kf)

MASS = f"{ROOT}/modelle/kaufhaus_freiburg/kaufhaus_mass.json"
GLB = f"{ROOT}/modelle/kaufhaus_freiburg/kaufhaus_measured.glb"


def green_bbox(rgb):
    from scipy import ndimage
    r, g, b = rgb[:, :, 0].astype(int), rgb[:, :, 1].astype(int), rgb[:, :, 2].astype(int)
    m = (g >= r-8) & (g > b+4) & (g > 60) & (g < 205)
    m = ndimage.binary_opening(m, iterations=4)          # erst öffnen (Nachbarn weg) ...
    m = ndimage.binary_closing(m, iterations=12)         # ... dann schließen
    lbl, n = ndimage.label(m)
    if n == 0:
        return None
    sizes = ndimage.sum(np.ones_like(lbl), lbl, range(1, n+1))
    big = 1+int(np.argmax(sizes))
    ys, xs = np.where(lbl == big)
    return xs.min(), ys.min(), xs.max()-xs.min(), ys.max()-ys.min()


def set_D(val):
    j = json.load(open(MASS)); j.setdefault("features_verfeinert_m", {}); j["tiefe_m"] = val
    json.dump(j, open(MASS, "w"))
    subprocess.run(["python3", f"{ROOT}/tools/kaufhaus_measured.py"], capture_output=True, cwd=ROOT)


def best_cam_score(op_ref, skin_ref, ts):
    best = 1e9
    for az in (248, 254, 260):                      # Schräg (nach rechts fliehende Front)
        for el in (8, 14, 20):
            for fov in (26, 32):
                rd = kf.render_cam(ts, az, el, fov)
                op_m, _ = od.cell_feats(rd, od.NX, od.NY)
                diff = np.abs(op_ref-op_m); valid = np.ones((od.NY, od.NX), bool)
                valid[od.NY-od.GROUND_ROWS:, :] = False; valid[skin_ref > 0.12] = False
                s = float(diff[valid].mean())
                best = min(best, s)
    return best


def main():
    full = np.asarray(Image.open(FOTO).convert("RGB")); H, W = full.shape[:2]
    gx, gy, gw, gh = green_bbox(full)                # generell: Gebäude aus grünem Dach
    bx0, bx1 = gx, gx+gw; by0, by1 = max(0, gy-int(gh*0.3)), min(H, gy+gh+int(gh*4.5))
    pc = Image.fromarray(full[by0:by1, bx0:bx1])
    op_ref, skin_ref = od.cell_feats(pc, od.NX, od.NY)
    orig = json.load(open(MASS)).get("tiefe_m", None)
    print(f"Schrägfoto {os.path.basename(FOTO)} — Gebäude-Crop aus grünem Dach")
    print("Tiefen-Sweep (Analyse-durch-Synthese): D → bester Kamera-Rest-Score")
    res = []
    for D in (7.0, 9.0, 11.0, 13.0, 15.0):
        set_D(D); ts = trimesh.load(GLB)
        s = best_cam_score(op_ref, skin_ref, ts)
        res.append((D, s)); print(f"  D={D:4.1f} m -> Score={s:.4f}")
    Dbest, sbest = min(res, key=lambda t: t[1])
    # Feinsuche um das Minimum
    for D in (Dbest-1, Dbest+1):
        if 6 <= D <= 16:
            set_D(D); ts = trimesh.load(GLB); s = best_cam_score(op_ref, skin_ref, ts)
            res.append((D, s))
    Dbest, sbest = min(res, key=lambda t: t[1])
    # zurücksetzen auf gemessene Tiefe
    set_D(round(Dbest, 1))
    print(f"\nGEMESSENE TIEFE D ≈ {Dbest:.1f} m  (Rest-Score {sbest:.4f})")
    print(f"(Beleg-Recherche Denkmaldatenbank: Haustiefe „knapp 11 m\" → Gegencheck)")


if __name__ == "__main__":
    main()
