"""Stabilitaetskarten fuer alle kalibrierten Fotos (GPU, sequentiell) -> OUTDIR/<foto>.png (uint8 = Laufanteil*255, Breite 1500). Aufruf: stabil_alle.py KAM.json BILDER OUTDIR
24.11.2026 DRAHTMASKE (tools/drahtmasken.py, OHNE_DRAHTMASKE=1 aus): Oberleitung/Spanndraehte -> Karte dort 0, der Kanten-Sweep sieht auf Drahtpixeln keine Kante.
Vorhandene Karten werden nur wiederverwendet, wenn OUTDIR/drahtmaske.json denselben Drahtmasken-Stand traegt (sonst alle neu)."""
import sys, os, json, time, cv2; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import kanten_stabil as KS, numpy as np
import code_stand
kam = json.load(open(sys.argv[1])); bd = sys.argv[2]; od = sys.argv[3]; os.makedirs(od, exist_ok=True); t0 = time.time(); n = 0
DRAHT = os.environ.get("OHNE_DRAHTMASKE", "0") != "1"
st = code_stand.code_stand("drahtmaske.py") if DRAHT else None; sj = os.path.join(od, "drahtmaske.json")
try: alt = json.load(open(sj)).get("detektor")
except Exception: alt = None
neu_alle = alt != st and any(f.endswith(".png") for f in os.listdir(od))
if neu_alle: print(f"Stabilkarten mit Drahtmasken-Stand {alt}, jetzt {st} -> alle neu", flush=True)
if neu_alle and os.path.exists(sj): os.remove(sj)                       # Marke erst nach dem Lauf neu (Abbruch mittendrin = beim naechsten Mal wieder alle)
if DRAHT: import drahtmasken as DMK
n_draht = 0
for f in sorted(kam):
    o = os.path.join(od, os.path.splitext(f)[0] + ".png")
    if (os.path.exists(o) and not neu_alle) or not os.path.exists(os.path.join(bd, f)): continue
    im = cv2.imread(os.path.join(bd, f), cv2.IMREAD_COLOR | cv2.IMREAD_IGNORE_ORIENTATION)
    if im is None: continue
    v, _ = KS.stabilkarte(im); k = np.clip(v * 255, 0, 255).astype(np.uint8)
    if DRAHT:
        m = DMK.maske_fuer(os.path.join(bd, f), im, rand_px=3)
        if m is not None and m.any():
            k[cv2.resize(m, (k.shape[1], k.shape[0]), interpolation=cv2.INTER_NEAREST) > 0] = 0; n_draht += 1
    cv2.imwrite(o, k); n += 1
    if n % 20 == 0: print(n, "%.0fs" % (time.time() - t0), flush=True)
json.dump(dict(detektor=st), open(sj, "w"))
print("fertig", n, f"(Drahtmaske in {n_draht} Karten)" if DRAHT else "(ohne Drahtmaske)")
