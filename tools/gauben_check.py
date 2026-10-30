#!/usr/bin/env python3
"""gauben_check.py — prüft die GAUBEN-REGELMÄSSIGKEIT (gleiche x-Abstände) Modell vs. Foto.

Diese Prüfung fehlte: Checker zählten Gauben + prüften Lage, aber NIE ob die x-Abstände GLEICH sind.
Ungleiche Abstände (Rhythmus) fallen dem Auge sofort auf, hatten aber keine Metrik → rutschten durch.
Messung: dunkle Gaubenfenster im grünen Dach segmentieren → x-Mitten sortieren → Variationskoeffizient
(CV = std/mean) der aufeinanderfolgenden Abstände. Regelmäßig ⇔ CV klein. PASS wenn Modell regelmäßig.

Lauf: /tmp/rv/bin/python tools/gauben_check.py   (optional --cv 0.15)
"""
import os, sys, importlib.util
os.environ["PYOPENGL_PLATFORM"] = "egl"
import numpy as np
from PIL import Image
from scipy import ndimage

ROOT = "/home/md/git/rc-park"
PHOTO = f"{ROOT}/daten/kaufhaus_freiburg/fotos/kh_jm3289.jpg"
CVMAX = 0.15
if "--cv" in sys.argv:
    CVMAX = float(sys.argv[sys.argv.index("--cv")+1])


def dormer_xs(a):
    """x-Mitten der dunklen Gaubenfenster innerhalb des grünen Dachs (Bruchteile 0..1)."""
    H, W = a.shape[:2]
    r, g, b = a[:, :, 0].astype(int), a[:, :, 1].astype(int), a[:, :, 2].astype(int)
    green = (g >= r-8) & (g > b+4) & (g > 55) & (g < 205)
    green = ndimage.binary_opening(green, iterations=2)
    grows = np.where(green.mean(1) > 0.06)[0]
    if len(grows) < 5:
        return []
    gtop, gbot = grows.min(), grows.max()
    dark = (r < 95) & (g < 95) & (b < 95)
    sub = np.zeros_like(dark); sub[gtop:gbot] = dark[gtop:gbot]
    sub = ndimage.binary_opening(sub, iterations=2)
    lbl, n = ndimage.label(sub)
    xs = []
    for i in range(1, n+1):
        ys2, xs2 = np.where(lbl == i)
        if len(xs2) > H*W*0.0006:
            xs.append(xs2.mean()/W)
    return sorted(xs)


def gap_cv(xs):
    if len(xs) < 3:
        return None
    gaps = np.diff(xs)
    return float(np.std(gaps)/np.mean(gaps))


def render_model():
    d = os.path.join(ROOT, "tools"); argv = sys.argv; sys.argv = ["x"]
    spec = importlib.util.spec_from_file_location("od", os.path.join(d, "overlay_diff.py"))
    od = importlib.util.module_from_spec(spec); spec.loader.exec_module(od); sys.argv = argv
    return np.asarray(od.render().convert("RGB"))


def _model_img():
    """Modellbild: entweder vorgerendertes PNG (--model <png>, empfohlen) oder frisch rendern."""
    if "--model" in sys.argv:
        return np.asarray(Image.open(sys.argv[sys.argv.index("--model")+1]).convert("RGB"))
    return render_model()


def main():
    px = dormer_xs(np.asarray(Image.open(PHOTO).convert("RGB")))
    mx = dormer_xs(_model_img())
    pcv, mcv = gap_cv(px), gap_cv(mx)
    print(f"FOTO   Gauben x-Mitten {[round(x,2) for x in px]}  n={len(px)}  Abstands-CV={pcv if pcv is None else round(pcv,3)}")
    print(f"MODELL Gauben x-Mitten {[round(x,2) for x in mx]}  n={len(mx)}  Abstands-CV={mcv if mcv is None else round(mcv,3)}")
    if mcv is None:
        print("MODELL: zu wenige Gauben erkannt → FAIL"); sys.exit(1)
    verdict = "PASS" if mcv <= CVMAX else "FAIL"
    print(f"Modell-Abstands-CV {mcv:.3f} (max {CVMAX}) → {verdict}" + ("  (ungleichmäßige x-Abstände!)" if verdict == "FAIL" else ""))
    sys.exit(0 if verdict == "PASS" else 1)


if __name__ == "__main__":
    main()
