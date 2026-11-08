#!/usr/bin/env python3
"""fenster_fit.py - parametrisches Fenster (Fassadenebene, 2 cm/px) per CMA-ES an ausgerichtete Wolken-Ortho-Ausschnitte fitten.
  venv-seg/bin/python -I tools/fenster_fit.py <fenster_ausgerichtet.npy> --aus fit.json [--png fit.png]
Modell (px, Fensterkoordinaten): Glasflaeche = Rechteck [xl,xr]x[yt,yb] mit Schulterbogen (Stich s) an den beiden aeusseren Lichtern,
2 senkrechte Sprossen (m1,m2), Riegel aussen (to) und Mitte (tm), Stabbreite b. Fitness = mittlere Helligkeit der Stabpixel - mittlere Helligkeit der Glaspixel
(Staebe hell, Glas dunkel). Reine Messung an der Wolke (nicht Foto-Diff), Rauschen -> Mehrfachstart. ANNAHME: drei Lichter, Riegelhoehe aussen != Mitte (am Bild gesehen,
Anzahl nicht als Sollwert: Fotozaehlung offen)."""
import argparse, json, numpy as np, cv2, cma
NAMEN = ["xl", "xr", "yt", "yb", "s", "m1", "m2", "to", "tm", "b"]
def maske(p, h, w):
    xl, xr, yt, yb, s, m1, m2, to, tm, b = p; yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    ins = (xx > xl) & (xx < xr) & (yy > yt) & (yy < yb)
    # Schulterbogen: aeussere Lichter oben begrenzt durch Viertelkreis-aehnliche Kurve der Hoehe s
    L = (xx < m1); R = (xx > m2); u = np.where(L, (m1 - xx) / max(m1 - xl, 1), (xx - m2) / max(xr - m2, 1)); sh = s * np.clip(1 - u, 0, 1) ** 2
    ins &= ~((L | R) & (yy < yt + s - sh * 0 - (s - s * (1 - u) ** 2 if False else 0) * 0) & (yy < yt + s * (u ** 2) * 0 + s * (1 - (1 - u) ** 2)))
    stab = np.zeros_like(ins)
    for m in (m1, m2): stab |= (np.abs(xx - m) < b / 2)
    stab |= (np.abs(yy - to) < b / 2) & (L | R); stab |= (np.abs(yy - tm) < b / 2) & (xx >= m1) & (xx <= m2)
    stab &= ins; return ins, stab
def fitness(p, img, occ=None):
    ins, stab = maske(p, *img.shape); glas = ins & ~stab
    if occ is not None: stab = stab & occ; glas = glas & occ     # nur GEMESSENE Zellen (kein Inpainting)
    if stab.sum() < 80 or glas.sum() < 500: return 1e3
    return -(img[stab].mean() - img[glas].mean()) + 0.002 * (abs(p[1] - p[0] - 99) + 0)
if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("npy"); ap.add_argument("--aus", required=True); ap.add_argument("--png"); ap.add_argument("--belegt", help="npy (n,h,w) bool: gemessene Zellen je Fenster"); a = ap.parse_args()
    al = np.load(a.npy); h, w = al.shape[1:]; bl = np.load(a.belegt) if a.belegt else None
    if bl is not None: m_ = np.where(bl, al, np.nan); med = np.nan_to_num(np.nanmedian(m_, 0), nan=0).astype(np.float32); occ_med = bl.mean(0) > 0.5
    else: med = np.median(al, 0).astype(np.float32); occ_med = None
    x0 = np.array([17, 112, 8, 112, 28, 50, 82, 56, 36, 4], float); sg = np.array([5, 5, 6, 6, 8, 4, 4, 6, 6, 1.2])
    lo = [5, 90, 0, 95, 0, 35, 65, 20, 10, 2]; hi = [30, 117, 30, 135, 60, 65, 100, 90, 70, 8]
    erg = []
    def lauf(img, seed, occ=None):
        es = cma.CMAEvolutionStrategy(x0 + np.random.default_rng(seed).normal(0, 1, 10) * sg * 0.5, 0.35, dict(bounds=[lo, hi], CMA_stds=list(sg), seed=seed + 1, verbose=-9, maxiter=250, popsize=24))
        while not es.stop(): X = es.ask(); es.tell(X, [fitness(np.array(x), img, occ) for x in X])
        return es.result.xbest, es.result.fbest
    best = [lauf(med, s, occ_med) for s in range(8)]; best.sort(key=lambda t: t[1]); xs = np.array([b[0] for b in best]); fs = [round(b[1], 3) for b in best]
    print("Typfenster (Median) beste Fitness je Start:", fs); print("Streuung der Parameter (Std ueber die 4 besten Starts):", dict(zip(NAMEN, np.round(xs[:4].std(0), 2))))
    out = dict(typ=dict(zip(NAMEN, np.round(xs[0], 2).tolist())), fitness=fs, zelle_m=0.02, einzel=[])
    for k, img in enumerate(al):
        x, f = min((lauf(img.astype(np.float32), s, None if bl is None else bl[k]) for s in range(3)), key=lambda t: t[1]); out["einzel"].append(dict(nr=k, p=dict(zip(NAMEN, np.round(x, 2).tolist())), fitness=round(f, 3)))
        print(k, round(f, 3), dict(zip(NAMEN, np.round(x, 1))))
    json.dump(out, open(a.aus, "w"), indent=1)
    if a.png:
        ins, stab = maske(xs[0], h, w); v = cv2.cvtColor(np.clip(med, 0, 255).astype(np.uint8), cv2.COLOR_GRAY2BGR); v2 = v.copy(); v2[stab] = (0, 255, 255); v2[ins & ~stab] = (v2[ins & ~stab] * 0.6 + np.array([120, 0, 0]) * 0.4).astype(np.uint8)
        cv2.imwrite(a.png, cv2.resize(np.hstack([v, v2]), None, fx=4, fy=4, interpolation=cv2.INTER_NEAREST))
