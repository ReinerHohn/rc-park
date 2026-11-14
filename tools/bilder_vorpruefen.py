#!/usr/bin/env python3
"""bilder_vorpruefen.py - Fremdbilder (Commons, Web, Videobilder) vor der SfM pruefen: zeigt das Bild das Objekt? GPU (ALIKED+LightGlue,
gleiche Funktionen wie tools/video_suchen.py) gegen die eigenen Objektfotos; Treffer = >= --min-inlier RANSAC-Inlier (Fundamentalmatrix).
Lehre Schwabentor 2026-11-14: 206 Commons-Bilder lagen geladen herum, nur 49 waren von Hand ausgewaehlt; Innenraeume/Gemaelde stoeren die SfM.
  /media/oem/scan/venv-seg/bin/python -I tools/bilder_vorpruefen.py modelle/<objekt>/objekt.json <ordner_oder_bild>... --aus liste.json [--ref 24] [--min-inlier 60]
Ausgabe: JSON {bild: {inlier, foto}} + Zusammenfassung; Bilder werden auf <= 1000 px (kurze Seite 720) verkleinert geprueft.
"""
import sys, os, json, glob, argparse, time
import numpy as np, cv2
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import video_suchen as VS


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("quellen", nargs="+"); ap.add_argument("--aus", required=True)
    ap.add_argument("--ref", type=int, default=24); ap.add_argument("--min-inlier", type=int, default=60)
    a = ap.parse_args(); t0 = time.time(); op = os.path.abspath(a.objekt); obj = json.load(open(op))
    root = os.path.dirname(os.path.dirname(os.path.dirname(op))); fd = obj["fotos_dir"]; fd = fd if os.path.isabs(fd) else os.path.join(root, fd)
    fotos = sorted(glob.glob(os.path.join(fd, "*.jpg")) + glob.glob(os.path.join(fd, "*.jpeg")) + glob.glob(os.path.join(fd, "*.png")))
    R = VS.sift_ref(fotos[::max(1, len(fotos) // a.ref)][:a.ref]); s = VS._sift(2048)
    bilder = []
    for q in a.quellen:
        bilder += [q] if os.path.isfile(q) else sorted(p for p in glob.glob(os.path.join(q, "**", "*"), recursive=True) if p.lower().endswith((".jpg", ".jpeg", ".png", ".webp")))
    print(f"{len(R)} Referenzfotos, {len(bilder)} Bilder (GPU {VS.DEV})", flush=True)
    erg = {}
    for p in bilder:
        g = cv2.imread(p, cv2.IMREAD_GRAYSCALE)
        if g is None: erg[p] = dict(inlier=0, foto=None, fehler="nicht lesbar"); continue
        k = min(1.0, 720 / min(g.shape), 1000 / max(g.shape)); g = cv2.resize(g, None, fx=k, fy=k, interpolation=cv2.INTER_AREA) if k < 1 else g
        n, ref = VS.treffer(g, R, None, s, a.min_inlier); erg[p] = dict(inlier=int(n), foto=ref)
    ja = [p for p, e in erg.items() if e["inlier"] >= a.min_inlier]
    json.dump(dict(objekt=op, min_inlier=a.min_inlier, referenz=[r[0] for r in R], treffer=len(ja), bilder=erg), open(a.aus, "w"), indent=1, ensure_ascii=False)
    print(f"{len(ja)} von {len(bilder)} zeigen das Objekt (>= {a.min_inlier} Inlier), {time.time() - t0:.0f} s -> {a.aus}")


if __name__ == "__main__":
    main()
