#!/usr/bin/env python3
"""zier_pruefen.py - Zierteile EINZELN gegen das Foto pruefen: Silhouetten-IoU im Ausschnitt (2026-11-05).

Warum: der Fassaden-Kantenvergleich (foto_diff, Glaettung 0,18 m) sieht Figurdetails nicht (Stufe 'Figuren als Netz': +0,004, nicht unterscheidbar).
Je Ausschnitt (zier_ausschnitt.py): Modell MIT und OHNE Zierteil per Strahl (Embree, CPU - stoert keinen GPU-Job) aus der Buendelkamera des Ausschnittfotos
rendern; Zierteil-Silhouette = Pixel, an denen das Modell mit Zierteil naeher ist. Foto-Silhouette = rembg (MIT, u2net Apache-2.0) auf dem Ausschnitt.
Kennzahl IoU (und Anteile Modell-ohne-Foto / Foto-ohne-Modell). Mehrere Varianten (--stl NAME=pfad) gegeneinander, z. B. TripoSR-Netz gegen Kegelstumpf.

  /media/oem/scan/venv-seg/bin/python -I tools/zier_pruefen.py <objekt.json> <ausschnitte.json> --ohne <stl> --stl netz=<stl> --stl kegel=<stl> [--aus DIR]
"""
import os, sys, json, glob, argparse, subprocess
import numpy as np, cv2, trimesh
TOOLS = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(TOOLS); sys.path.insert(0, TOOLS)
import fehlteile_finden as FF
PY_TSR = "/media/oem/scan/venv-tsr/bin/python"


def strahlen(K, R, t, f, cx, cy, k1, x0, y0, x1, y1, schritt):
    """Strahlen (Ursprung, Richtung) fuer Pixel des Ausschnitts; k1 per Fixpunkt rueckgaengig (Bild verzerrt -> Lochkamera)."""
    xs, ys = np.meshgrid(np.arange(x0, x1, schritt), np.arange(y0, y1, schritt)); u = (xs - cx) / f; v = (ys - cy) / f; uu, vv = u.copy(), v.copy()
    for _ in range(5): r2 = uu * uu + vv * vv; uu, vv = u / (1 + k1 * r2), v / (1 + k1 * r2)
    d = np.stack([uu, vv, np.ones_like(uu)], -1) @ R; d /= np.linalg.norm(d, axis=-1, keepdims=True); C = -R.T @ t
    return xs.shape, np.repeat(C[None], d.size // 3, 0), d.reshape(-1, 3)


def tiefe(netz, o, d):
    RI = trimesh.ray.ray_pyembree.RayMeshIntersector if hasattr(trimesh.ray, "ray_pyembree") else trimesh.ray.ray_triangle.RayMeshIntersector
    loc, ir, _ = RI(netz).intersects_location(o, d, multiple_hits=False); z = np.full(len(o), np.inf); z[ir] = np.linalg.norm(loc - o[ir], axis=1); return z


def laden(p, obj, tr):
    m = trimesh.load(p); m.apply_scale(obj.get("stl_massstab", 87) / 1000.0); m.apply_translation(tr); return m


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("ausschnitte"); ap.add_argument("--ohne", required=True); ap.add_argument("--stl", action="append", required=True)
    ap.add_argument("--schritt", type=int, default=2); ap.add_argument("--aus"); a = ap.parse_args(argv)
    obj = json.load(open(a.objekt)); A = json.load(open(a.ausschnitte)); aus = a.aus or os.path.join(os.path.dirname(os.path.abspath(a.ausschnitte)), "pruefung"); os.makedirs(aus, exist_ok=True)
    var = dict(s.split("=", 1) for s in a.stl); erg = []
    # Foto-Silhouetten mit rembg (venv-tsr), einmal fuer alle Ausschnitte
    mdir = os.path.join(aus, "rembg"); os.makedirs(mdir, exist_ok=True); fehlt = [e["datei"] for e in A["ausschnitte"] if not os.path.exists(os.path.join(mdir, os.path.basename(e["datei"])))]
    if fehlt:
        code = "import sys,rembg,PIL.Image as I,os\ns=rembg.new_session()\nfor p in sys.argv[2:]:\n    I.open(p).convert('RGB') and rembg.remove(I.open(p).convert('RGB'),session=s).split()[-1].save(os.path.join(sys.argv[1],os.path.basename(p)))"
        subprocess.run([PY_TSR, "-c", code, mdir] + fehlt, check=True, env=dict(os.environ, U2NET_HOME="/media/oem/scan/hf_cache/u2net"))
    for e in A["ausschnitte"]:
        nr = e["foto"]; K = json.load(open(FF.k_datei(a.objekt, obj, ROOT, nr))); kk = K["kamera"]; pf = glob.glob(os.path.join(ROOT, obj["fotos_dir"], nr + "_*"))[0]
        H, W = cv2.imread(pf).shape[:2]; R, t, f, _, _ = FF.kamera_laden(K, obj, nr, ROOT, W, H); tr = np.asarray(kk.get("rahmen_verschiebung", [0, 0, 0]), float)
        x0, y0, x1, y1 = e["box_px"]; sh, o, d = strahlen(K, np.asarray(R), np.asarray(t, float).ravel(), f, float(kk.get("cx", W / 2)), float(kk.get("cy", H / 2)), float(kk.get("k1") or 0.0), x0, y0, x1, y1, a.schritt)
        z0 = tiefe(laden(a.ohne, obj, tr), o, d)
        fm = cv2.imread(os.path.join(mdir, os.path.basename(e["datei"])), cv2.IMREAD_GRAYSCALE); fm = cv2.resize(fm, (sh[1], sh[0]), interpolation=cv2.INTER_AREA) > 127
        z_ = dict(element=os.path.basename(e["datei"]), foto=nr, foto_px=int(fm.sum())); bilder = [cv2.resize(cv2.imread(e["datei"]), (sh[1], sh[0]))]
        for name, p in var.items():
            z1 = tiefe(laden(p, obj, tr), o, d); ms = (z1 < z0 - 0.05).reshape(sh)
            i_ = (ms & fm).sum(); u_ = (ms | fm).sum(); z_[name] = dict(iou=round(float(i_ / max(1, u_)), 3), modell_ohne_foto=round(float((ms & ~fm).sum() / max(1, ms.sum())), 3), foto_ohne_modell=round(float((fm & ~ms).sum() / max(1, fm.sum())), 3))
            b = np.zeros(sh + (3,), np.uint8); b[fm & ms] = (0, 200, 0); b[ms & ~fm] = (0, 0, 255); b[fm & ~ms] = (0, 220, 255); cv2.putText(b, f"{name} {z_[name]['iou']:.2f}", (3, 15), 0, 0.5, (255, 255, 255), 1); bilder.append(b)
        erg.append(z_); cv2.imwrite(os.path.join(aus, z_["element"]), np.hstack(bilder))
        print(f"  {z_['element']} (Foto {nr}): " + ", ".join(f"{k} IoU {v['iou']}" for k, v in z_.items() if isinstance(v, dict)), flush=True)
    json.dump(dict(varianten=var, ohne=a.ohne, ergebnisse=erg), open(os.path.join(aus, "zier_pruefung.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
