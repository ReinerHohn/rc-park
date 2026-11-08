#!/usr/bin/env python3
"""gs_kaufhaus_daten.py - Datensatz fuer Gaussian Splatting (gsplat) aus den K-Kameras des Kaufhauses.
Je K-Foto: Original aus fotos_dir, Verzeichnung k1 entfernt (wie foto_diff.foto_entzerren), auf Langseite --lang px verkleinert, Kamera (R,t,f,cx,cy) skaliert.
Modellrahmen = Meter (Transformation Wolke->Modell ist hier die Identitaet, SFM-AUSRICHTUNG-buendel.json).
Aufruf: venv-seg/bin/python -I tools/gs_kaufhaus_daten.py modelle/kaufhaus_null5/objekt.json --aus /media/oem/scan/rc-park_null/gs_kh [--lang 1000]
Ausgabe: DIR/daten.npz (bilder uint8 N,H,W,3 je Foto als Liste in kameras.json-Reihenfolge; nur gleiche Groesse stapelbar -> je Foto eigene Datei DIR/bild_<nr>.png) + DIR/kameras.json"""
import sys, os, json, glob, argparse, numpy as np, cv2
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fehlteile_finden as FF
ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--aus", required=True); ap.add_argument("--lang", type=int, default=1000); a = ap.parse_args()
obj = json.load(open(a.objekt)); root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(a.objekt))))
os.makedirs(a.aus, exist_ok=True); cams = {}
for p in sorted(glob.glob(os.path.join(os.path.dirname(os.path.abspath(a.objekt)), "messprotokoll", "K-*.json"))):
    nr = os.path.basename(p)[2:-5]; K = json.load(open(p))
    if "kamera" not in K: continue
    g = glob.glob(os.path.join(root, obj["fotos_dir"], nr + "_*"))
    if not g: continue
    im = cv2.imread(g[0]); kk = K["kamera"]; H, W = im.shape[:2]
    if [W, H] != list(kk["bild"]): print("Groesse passt nicht", nr, (W, H), kk["bild"]); continue
    im, k1 = FF.foto_entzerren(im, kk); s = a.lang / max(W, H); w, h = round(W * s), round(H * s)
    im = cv2.resize(im, (w, h), interpolation=cv2.INTER_AREA); cv2.imwrite(os.path.join(a.aus, f"bild_{nr}.png"), im)
    R, _ = cv2.Rodrigues(np.array(kk["rvec"])); cams[nr] = dict(R=R.tolist(), t=list(kk["t"]), f=kk["f_px"] * w / W, cx=float(kk.get("cx", W / 2)) * w / W, cy=float(kk.get("cy", H / 2)) * h / H, W=w, H=h, k1=k1)
json.dump(cams, open(os.path.join(a.aus, "kameras.json"), "w")); print(len(cams), "Kameras ->", a.aus)
