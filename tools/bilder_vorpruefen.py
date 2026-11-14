#!/usr/bin/env python3
"""bilder_vorpruefen.py - Fremdbilder (Commons, Web, Videobilder) vor der SfM pruefen: zeigt das Bild das Objekt? GPU (ALIKED+LightGlue,
gleiche Funktionen wie tools/video_suchen.py) gegen die eigenen Objektfotos; Treffer = >= --min-inlier RANSAC-Inlier (Fundamentalmatrix).
Lehre Schwabentor 2026-11-14: 206 Commons-Bilder lagen geladen herum, nur 49 waren von Hand ausgewaehlt; Innenraeume/Gemaelde stoeren die SfM.
  /media/oem/scan/venv-seg/bin/python -I tools/bilder_vorpruefen.py modelle/<objekt>/objekt.json <ordner_oder_bild>... --aus liste.json [--ref 24] [--min-inlier 60]
Kette (--kette 6): Nachbarbilder eines Treffers im selben Ordner, die ihn >= min-inlier treffen, zaehlen mit (Videostetigkeit).
Ausgabe: JSON {bild: {inlier, foto}} + Zusammenfassung; Bilder werden auf <= 1000 px (kurze Seite 720) verkleinert geprueft.
"""
import sys, os, json, glob, argparse, time
import numpy as np, cv2
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import video_suchen as VS


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("quellen", nargs="+"); ap.add_argument("--aus", required=True)
    ap.add_argument("--ref", type=int, default=24); ap.add_argument("--min-inlier", type=int, default=60)
    ap.add_argument("--kette", type=int, default=6, help="Videobilder: Nachbarbilder (<= N Schritte, gleicher Ordner) eines Treffers zaehlen, wenn sie ihn >= min-inlier treffen")
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
    # Kette (Lehre Schwabentor 2026-11-14): Drohnenbilder der Turmspitze (vf_004..007) haben 0 Inlier gegen Strassenfotos, ueberlappen aber
    # stark mit den Nachbarbildern vf_000..003 -> nur 1 von 80 Drohnenbildern kam durch. Stetigkeit im Video = Beleg fuer dasselbe Objekt.
    if a.kette > 0:
        from collections import defaultdict
        ordner = defaultdict(list)
        for p in bilder: ordner[os.path.dirname(p)].append(p)
        cache = {}
        def mk(p):
            if p not in cache:
                g = cv2.imread(p, cv2.IMREAD_GRAYSCALE); k = min(1.0, 720 / min(g.shape), 1000 / max(g.shape))
                g = cv2.resize(g, None, fx=k, fy=k, interpolation=cv2.INTER_AREA) if k < 1 else g; cache[p] = VS._merkmale(s, g)
            return cache[p]
        for d, L in ordner.items():
            L = sorted(L); schritt = {p: 0 for p in L if erg[p]["inlier"] >= a.min_inlier}; offen = list(schritt)
            while offen:
                q = offen.pop(); i = L.index(q)
                if schritt[q] >= a.kette: continue
                for j in (i - 1, i + 1):
                    if not 0 <= j < len(L) or L[j] in schritt: continue
                    P0, f0 = mk(L[j]); P1, f1 = mk(q)
                    with VS.torch.inference_mode() if hasattr(VS, "torch") else __import__("torch").inference_mode():
                        m = VS._LG["m"]({"image0": f0, "image1": f1})["matches"][0].cpu().numpy()
                    n = 0
                    if len(m) >= a.min_inlier:
                        F, msk = cv2.findFundamentalMat(P0[m[:, 0]], P1[m[:, 1]], cv2.FM_RANSAC, 3.0, 0.999); n = int(msk.sum()) if msk is not None else 0
                    if n >= a.min_inlier:
                        schritt[L[j]] = schritt[q] + 1; offen.append(L[j])
                        erg[L[j]].update(inlier_kette=n, kette_von=os.path.basename(q), kette_schritt=schritt[L[j]], inlier_direkt=erg[L[j]]["inlier"], inlier=a.min_inlier)
            cache.clear()
        print(f"Kette: {sum('kette_von' in e for e in erg.values())} Nachbarbilder dazu", flush=True)
    ja = [p for p, e in erg.items() if e["inlier"] >= a.min_inlier]
    json.dump(dict(objekt=op, min_inlier=a.min_inlier, referenz=[r[0] for r in R], treffer=len(ja), bilder=erg), open(a.aus, "w"), indent=1, ensure_ascii=False)
    print(f"{len(ja)} von {len(bilder)} zeigen das Objekt (>= {a.min_inlier} Inlier), {time.time() - t0:.0f} s -> {a.aus}")


if __name__ == "__main__":
    main()
