#!/usr/bin/env python3
"""kamera_bruecke.py - Bündelkamera (COLMAP-Export im Objektrahmen, z. B. sfm/kam_lot2.json) als Messkamera K-<nr> fuer foto_mass.py / foto_diff.py.

  kamera_bruecke.py OBJEKT.json --kameras KAM.json --bilder DIR --bild ip_IMG_6161.jpg --nr 6161
      -> modelle/<objekt>/messprotokoll/K-<nr>.json (typ kamera_bruecke_sfm, rahmen_verschiebung [0,0,0]) + Symlink <fotos_dir>/<nr>_<bild>
  kamera_bruecke.py OBJEKT.json --kameras KAM.json --kandidaten X Y Z [--n 12] [--achse_n nx ny]
      -> Liste der Bündelfotos, die den Punkt (Objektrahmen) im Bild zeigen, nach Blickrichtung sortiert (Dritt-Foto fuer Triangulation / Widerspruch).
Generisch (keine Objektnamen); Rahmen = Rahmen der Kameradatei (muss der Generatorrahmen sein, sonst falsche Meter)."""
import sys, os, json, argparse, numpy as np, cv2

ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--kameras", required=True); ap.add_argument("--bilder"); ap.add_argument("--bild"); ap.add_argument("--nr")
ap.add_argument("--kandidaten", nargs=3, type=float); ap.add_argument("--n", type=int, default=12); ap.add_argument("--achse_n", nargs=2, type=float); a = ap.parse_args()
obj = json.load(open(a.objekt)); root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(a.objekt)))); kam = json.load(open(a.kameras))

def proj(k, X):
    R = np.array(k["Rn"]); t = np.array(k["tn"]); x = R @ X + t
    if x[2] <= 0.1: return None, x[2]
    xn, yn = x[0] / x[2], x[1] / x[2]; k1 = float(k["params"][3]) if len(k.get("params", [])) > 3 else 0.0; r2 = xn * xn + yn * yn
    return (k["f"] * xn * (1 + k1 * r2) + k["cx"], k["f"] * yn * (1 + k1 * r2) + k["cy"]), x[2]

if a.kandidaten:
    X = np.array(a.kandidaten); rows = []
    for name, k in kam.items():
        uv, d = proj(k, X)
        if uv is None or not (0.05 * k["W"] < uv[0] < 0.95 * k["W"] and 0.05 * k["H"] < uv[1] < 0.95 * k["H"]): continue
        v = X - np.array(k["C"]); v /= np.linalg.norm(v); az = np.degrees(np.arctan2(v[1], v[0]))
        if a.achse_n: nn = np.array(a.achse_n + [0.0]); nn /= np.linalg.norm(nn); az = np.degrees(np.arccos(np.clip(-v @ nn, -1, 1))) * np.sign(nn[0] * -v[1] - nn[1] * -v[0])
        rows.append((name, round(float(d), 1), round(float(az), 1), [int(uv[0]), int(uv[1])]))
    rows.sort(key=lambda r: r[2]); step = max(1, len(rows) // a.n)
    print(f"{len(rows)} Fotos zeigen den Punkt; Auswahl ueber den Blickwinkel (Grad gegen die Achse, Abstand m, Pixel):")
    for r in rows[::step]: print(" ", r)
    sys.exit(0)

k = kam[a.bild]; od = os.path.join(root, os.path.dirname(obj["masstabelle"]), "messprotokoll"); os.makedirs(od, exist_ok=True)
rvec = cv2.Rodrigues(np.array(k["Rn"], float))[0].ravel().tolist()
K = dict(rvec=rvec, t=list(map(float, k["tn"])), f_px=float(k["f"]), cx=float(k["cx"]), cy=float(k["cy"]), bild=[int(k["W"]), int(k["H"])],
         k1=float(k["params"][3]) if len(k.get("params", [])) > 3 else 0.0, modell=k.get("modell", "SIMPLE_RADIAL"), standort_xyz=[round(float(c), 2) for c in k["C"]],
         brennweite_quelle=f"SfM-Buendel {a.kameras}", rms_px=None, rahmen_verschiebung=[0.0, 0.0, 0.0])
rec = dict(foto=a.nr, datei=a.bild, typ="kamera_bruecke_sfm", kamera=K,
           quelle=f"tools/kamera_bruecke.py: Pose/Brennweite/k1 aus {a.kameras} (Rahmen der Kameradatei = Generatorrahmen); Anker = SfM-Buendel, KEINE amtlichen Anker; Massstab sfm_buendel",
           datum=__import__("datetime").date.today().isoformat())
json.dump(rec, open(os.path.join(od, f"K-{a.nr}.json"), "w"), indent=1, ensure_ascii=False)
ziel = os.path.join(root, obj["fotos_dir"], f"{a.nr}_{a.bild}")
if not os.path.exists(ziel): os.symlink(os.path.join(os.path.abspath(a.bilder), a.bild), ziel)
print(f"K-{a.nr} geschrieben ({od}), Foto {ziel}")
