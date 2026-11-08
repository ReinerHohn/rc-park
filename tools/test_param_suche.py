#!/usr/bin/env python3
"""test_param_suche.py - BEWEIS (bekannte Wahrheit) fuer param_suche.py (2026-11-04).
Je Wahrheit w*: Generator mit <param> = w* -> Pruefbilder (Render mit der echten Kamera inkl. k1, test_foto_diff.foto_rendern) fuer N Fotos ->
param_suche.py --bilder sucht den Wert. Bestanden, wenn |gefunden - w*| <= --tol fuer JEDE Wahrheit (mind. zwei, damit kein fester Hang
zu einem Wert durchgeht).
  /media/oem/scan/venv-seg/bin/python -W ignore -I tools/test_param_suche.py modelle/<obj>/objekt.json --bauteil rumpf_lod2 --param first_versatz_m \
      --wahr -0.8,0.4 --werte -2:1:0.5 [--fotos 6] [--tol 0.15]
"""
import sys, os, json, argparse, subprocess, tempfile, numpy as np, cv2, trimesh
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import param_suche as PS, test_foto_diff as TF, fehlteile_finden as FF


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--bauteil", required=True); ap.add_argument("--param", required=True)
    ap.add_argument("--wahr", required=True); ap.add_argument("--werte", required=True); ap.add_argument("--fotos", type=int, default=6); ap.add_argument("--tol", type=float, default=0.15)
    ap.add_argument("--arbeit"); a = ap.parse_args()
    objp = os.path.abspath(a.objekt); obj = json.load(open(objp)); od = os.path.dirname(objp); root = PS.ROOT
    fotos = PS.fotos_waehlen(od, a.fotos); wd = a.arbeit or tempfile.mkdtemp(prefix="test_param_suche_", dir="/media/oem/scan/rc-park_null"); os.makedirs(wd, exist_ok=True)
    erg = {}; wahr = [float(x) for x in a.wahr.split(",")]
    ordner = {w: os.path.join(wd, f"wahr{w:+.2f}") for w in wahr}
    for w in wahr: os.makedirs(os.path.join(ordner[w], "bilder"), exist_ok=True)
    stls = {w: PS.bauen(obj, a.bauteil, a.param, w, f"_wahr_{os.path.basename(od)}_{w:+.3f}.stl", os.path.join(ordner[w], "elemente.json"), "test_param_suche Wahrheit") for w in wahr}
    def _bild(wn):                                                                                  # Pruefbilder aller Wahrheiten x Fotos PARALLEL (2026-11-04; je Bild eigener Zufallsstrom -> bitgleich zur Reihenfolge)
        w, nr = wn; K = json.load(open(FF.k_datei(objp, obj, root, nr))); kk = K["kamera"]; W, H = kk["bild"]
        R, t, f, _, _ = FF.kamera_laden(K, obj, nr, root, W, H); m, _ = TF.modell(obj, os.path.join(root, stls[w]), kk)
        cv2.imwrite(os.path.join(ordner[w], "bilder", f"{nr}.jpg"), FF.foto_verzerren(TF.foto_rendern(m, R, t, f, float(kk.get("cx", W / 2)), float(kk.get("cy", H / 2)), W, H, np.random.default_rng(0)), kk), [cv2.IMWRITE_JPEG_QUALITY, 95])
    auftr = [(w, nr) for w in wahr for nr in fotos]
    with ThreadPoolExecutor(PS.arbeiter_zahl(len(auftr), gb_je=0.8 if TF._gpu() else 3.8, reserve_gb=1.5)) as ex: list(ex.map(_bild, auftr))   # RAM gemessen je Render: CPU 3,6 GB, GPU 1,35 GB Prozess (davon ~0,7 CUDA einmalig)
    for w in wahr: os.remove(os.path.join(root, stls[w]))
    if TF._gpu(): import torch; torch.cuda.empty_cache()                                         # Grafikspeicher fuer die param_suche-Arbeiter freigeben (Raster-Zwischenspeicher)
    for w in wahr:                                                                                  # Suchen nacheinander: jede bemisst ihren Pool selbst nach dem ganzen freien RAM
        d = ordner[w]; bd = os.path.join(d, "bilder")
        r = subprocess.run([PS.PY, "-I", os.path.join(PS.TOOLS, "param_suche.py"), objp, "--bauteil", a.bauteil, "--param", a.param, "--werte=" + a.werte, "--fein",
                            "--fotoliste", ",".join(fotos), "--bilder", bd, "--aus", os.path.join(d, "suche"), "--fd=--tiefen aus"], cwd=root, capture_output=True, text=True)
        print(r.stdout[-900:]); pf = os.path.join(d, "suche", f"param_suche_{a.bauteil}_{a.param}.json")
        if r.returncode != 0 or not os.path.exists(pf): raise SystemExit("param_suche fehlgeschlagen: " + (r.stderr or "")[-600:])
        e = json.load(open(pf)); erg[w] = dict(gefunden=e["bester_wert"], fehler=round(e["bester_wert"] - w, 3), zustand=e["zustand"], streuung=e["streuung_fotos"], ok=abs(e["bester_wert"] - w) <= a.tol and e["zustand"] == "ok")
    ok = len(erg) >= 2 and all(v["ok"] for v in erg.values())
    res = dict(bauteil=a.bauteil, param=a.param, fotos=fotos, tol=a.tol, ergebnisse={f"{k:+.2f}": v for k, v in erg.items()}, bestanden=ok, arbeit=wd)
    json.dump(res, open(os.path.join(od, "audit", f"test_param_suche_{a.param}.json"), "w"), indent=1); print(json.dumps(res, ensure_ascii=False))
    print("BEWEIS param_suche:", "BESTANDEN" if ok else "NICHT BESTANDEN"); sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
