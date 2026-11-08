#!/usr/bin/env python3
"""Test handy_masken: (1) Klassenableitung exakt (kein 'carpet' fuer 'car'), (2) Maskenlogik, (3) 3 Bilder echt durch GPU, Format/Konvention pruefen."""
import sys, os, glob, json, tempfile, subprocess
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import handy_masken as H
lab = {0: "wall", 12: "person, individual", 20: "car, auto", 28: "carpet, carpeting", 41: "box", 86: "awning, sunshade", 114: "tent, collapsible shelter", 88: "booth, cubicle", 127: "bicycle, bike", 1: "building, edifice"}
ids = H.klassen_ids(lab); assert set(ids) == {12, 20, 41, 114, 88, 127}, ids
assert 86 in H.klassen_ids(lab, True)
seg = np.zeros((100, 100), int); seg[40:50, 40:50] = 12
m = H.maske_aus_seg(seg, ids, 0); assert m.dtype == np.uint8 and set(np.unique(m)) == {0, 255} and (m == 0).sum() == 100
assert (H.maske_aus_seg(seg, ids, 5) == 0).sum() > 100
assert H.serie_von("h_c_07.jpg", "/x/y") == "c"
src = "/media/oem/scan/rc-park_null/kaufhaus_handy2k/bilder"; fs = sorted(glob.glob(src + "/*.jpg"))[:3]
if fs:
    with tempfile.TemporaryDirectory() as t:
        d = os.path.join(t, "in"); os.makedirs(d)
        for f in fs: os.symlink(f, os.path.join(d, os.path.basename(f)))
        r = subprocess.run(["/media/oem/scan/venv-seg/bin/python", "-W", "ignore", "-I", os.path.join(os.path.dirname(os.path.abspath(__file__)), "handy_masken.py"), d, "--ausgabe", t + "/out", "--batch", "2"], capture_output=True, text=True)
        assert r.returncode == 0, r.stderr[-800:]
        import cv2
        for f in fs:
            p = os.path.join(t, "out", "a", os.path.splitext(os.path.basename(f))[0] + ".png"); mk = cv2.imread(p, cv2.IMREAD_UNCHANGED); im = cv2.imread(f)
            assert mk.shape == im.shape[:2] and mk.dtype == np.uint8 and set(np.unique(mk)) <= {0, 255}
        b = json.load(open(t + "/out/a/bericht.json")); assert len(b["maskiert_anteil"]) == 3
print("test_handy_masken: bestanden")
