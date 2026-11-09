"""Stabilitaetskarten fuer alle kalibrierten Fotos (GPU, sequentiell) -> OUTDIR/<foto>.png (uint8 = Laufanteil*255, Breite 1500). Aufruf: stabil_alle.py KAM.json BILDER OUTDIR"""
import sys, os, json, time, cv2; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import kanten_stabil as KS, numpy as np
kam = json.load(open(sys.argv[1])); bd = sys.argv[2]; od = sys.argv[3]; os.makedirs(od, exist_ok=True); t0 = time.time(); n = 0
for f in sorted(kam):
    o = os.path.join(od, os.path.splitext(f)[0] + ".png")
    if os.path.exists(o) or not os.path.exists(os.path.join(bd, f)): continue
    im = cv2.imread(os.path.join(bd, f), cv2.IMREAD_COLOR | cv2.IMREAD_IGNORE_ORIENTATION)
    if im is None: continue
    v, _ = KS.stabilkarte(im); cv2.imwrite(o, np.clip(v * 255, 0, 255).astype(np.uint8)); n += 1
    if n % 20 == 0: print(n, "%.0fs" % (time.time() - t0), flush=True)
print("fertig", n)
