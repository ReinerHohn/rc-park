#!/usr/bin/env python3
"""kante_3d.py - Linienhafte Kante (Rippe, Bogen, Gesimslinie, Rahmen) aus 2 kalibrierten Fotos als 3D-Kurve messen (Glied 2+4 der Methode MESSEN_DANN_BAUEN).

Aufruf:
  kante_3d.py OBJ.json --kamA K-6171 --kamB K-6259 --wege "x,y,z;x,y,z;x,y,z" --aus DIR --name N
      [--farbe gold|dunkel|kante] [--sigA 6] [--sigB 1.5] [--rand_ende 3] [--n_aus 24] [--achse_n nx ny] [--viaA "x,y;x,y"] [--tiefe_pm 1.0]
Ablauf: Wegpunkte (3D, z. B. aus foto_mass.py --tri; mindestens Anfang und Ende, Mitte haelt die Verfolgung auf der richtigen Kante) werden in beide
Kameras projiziert; je Foto verfolgt ein Minimalkostenpfad (skimage) die Kante zwischen den Wegpunkten (Kosten aus --farbe: gold = Gelbanteil,
dunkel = Dunkelheit, kante = Gradient). Die Querform kommt aus Foto A (saubere, grosse Aufnahme); je Pixel von A wird die TIEFE entlang des Strahls
dort gesucht, wo die projizierte Strahlposition dem Pfad in Foto B am naechsten ist; Tiefen ausreisserfest (Medianfilter 9, > 0,08 m verworfen, die letzten
--rand_ende Punkte verworfen = Endhaken) mit Spline geglaettet. Ende = gemessener letzter Wegpunkt wird angehaengt.
Ausgabe: DIR/kante_<name>.json (pfad_xyz, optional pfad_uvz mit --achse_n [u = n um -90 Grad], abstand_wegpunkte_m, tiefenrest_median_m, n_verworfen),
  DIR/kante_<name>_A.jpg / _B.jpg (Pfad ueber dem Foto-Ausschnitt).
Grenzen: nur Kanten mit Kontrast und >= ~8 px Breite in Foto B; Foto B mit aehnlichem Massstab/Blickwinkel waehlen; Wegpunkt-Gegenprobe (3. Kamera) bleibt
Pflicht (Strahlabstand allein beweist nichts); Pfad kann an Kreuzungen auf die falsche Kante springen (Bild ansehen!). Reine Geometrie/CPU."""
import sys, os, json, glob, importlib.util
import numpy as np, cv2
from skimage.graph import route_through_array
from scipy.signal import medfilt
from scipy.interpolate import UnivariateSpline, splprep, splev

_sp = importlib.util.spec_from_file_location("epilinie", os.path.join(os.path.dirname(os.path.abspath(__file__)), "epilinie.py"))
EPI = importlib.util.module_from_spec(_sp); _sp.loader.exec_module(EPI)


def kosten(im, modus, sig):
    f = im.astype(np.float32)
    if modus == "gold": s = np.clip((f[..., 2] + f[..., 1]) / 2 - f[..., 0], 0, None) / 255.0
    elif modus == "dunkel": s = 1.0 - cv2.cvtColor(im, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0
    else:
        g = cv2.GaussianBlur(cv2.cvtColor(im, cv2.COLOR_BGR2GRAY), (0, 0), 1.2).astype(np.float32); s = cv2.magnitude(cv2.Sobel(g, cv2.CV_32F, 1, 0), cv2.Sobel(g, cv2.CV_32F, 0, 1))
    s = cv2.GaussianBlur(s, (0, 0), sig); return 1.0 / (0.02 + s / (s.max() + 1e-6)) ** 2


def pfad(K, im, wege, modus, sig, rand=120, via=None):
    px = [EPI.projekt(K, np.array(p)) for p in wege]
    if any(p is None for p in px): sys.exit("Wegpunkt hinter der Kamera")
    if via: px = [px[0]] + [tuple(v) for v in via] + [px[-1]]   # --viaA: von Hand auf der Rippe gesetzte Pixel (nur Foto A), Reihenfolge Anfang->Ende
    H, W = im.shape[:2]; xs = [p[0] for p in px]; ys = [p[1] for p in px]
    x0, y0, x1, y1 = max(int(min(xs)) - rand, 0), max(int(min(ys)) - rand, 0), min(int(max(xs)) + rand, W), min(int(max(ys)) + rand, H)
    c = kosten(im[y0:y1, x0:x1], modus, sig); out = []
    for a, b in zip(px[:-1], px[1:]):
        p, _ = route_through_array(c, (int(a[1] - y0), int(a[0] - x0)), (int(b[1] - y0), int(b[0] - x0)), fully_connected=True, geometric=True)
        out += [(cc + x0, rr + y0) for rr, cc in p]
    return np.array(out, float)


def main():
    a = sys.argv[1:]
    if len(a) < 7 or a[0].startswith("-"): sys.exit(__doc__)
    opt = lambda n, d: a[a.index(n) + 1] if n in a else d
    obj = json.load(open(a[0])); root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(a[0])))); od = os.path.join(root, os.path.dirname(obj["masstabelle"]))
    kidA, kidB = opt("--kamA", None), opt("--kamB", None); wege = [tuple(float(v) for v in w.split(",")) for w in opt("--wege", "").split(";") if w]
    if not kidA or not kidB or len(wege) < 2: sys.exit("--kamA, --kamB und >= 2 --wege noetig")
    aus, name, modus = opt("--aus", "."), opt("--name", "kante"), opt("--farbe", "gold"); sigA, sigB = float(opt("--sigA", 6)), float(opt("--sigB", 1.5))
    rand_ende, n_aus, pm = int(opt("--rand_ende", 3)), int(opt("--n_aus", 24)), float(opt("--tiefe_pm", 1.0)); os.makedirs(aus, exist_ok=True)
    img = lambda kid: cv2.imread(glob.glob(os.path.join(root, obj["fotos_dir"], kid[2:] + "_*"))[0])
    KA, KB = EPI.kam(od, kidA), EPI.kam(od, kidB); imA, imB = img(kidA), img(kidB)
    via = [tuple(float(v) for v in q.split(",")) for q in opt("--viaA", "").split(";") if q]
    pA, pB = pfad(KA, imA, wege, modus, sigA, via=via), pfad(KB, imB, wege, modus, sigB)
    dw = [float(np.linalg.norm(np.array(w) - KA["c"])) for w in wege]; t0, t1 = max(min(dw) - pm, 0.5), max(dw) + pm
    uv = pA[::12]; ts = []
    for q in uv:
        c0, d0 = EPI.strahl(KA, q); best = None
        for t in np.arange(t0, t1, 0.02):
            p = EPI.projekt(KB, c0 + d0 * t)
            if p is None: continue
            dd = float(np.min(np.hypot(pB[:, 0] - p[0], pB[:, 1] - p[1])))
            if best is None or dd < best[0]: best = (dd, t)
        ts.append(best[1])
    ts = np.array(ts); s = np.arange(len(ts), dtype=float); gut = np.abs(ts - medfilt(ts, 9)) < 0.08
    if rand_ende: gut[-rand_ende:] = False
    sp = UnivariateSpline(s[gut], ts[gut], k=3, s=gut.sum() * 0.02 ** 2); tg = sp(s)
    P = np.array([EPI.strahl(KA, q)[0] + EPI.strahl(KA, q)[1] * t for q, t in zip(uv, tg)]); P = np.vstack([P[:-rand_ende] if rand_ende else P, np.array(wege[-1])])
    wt = np.ones(len(P)); wt[0] = wt[-1] = 30.0; tck, _ = splprep(P.T, w=wt, s=len(P) * 0.0004);   # Endpunkte gewichtet: Anfang/Ende bleiben auf den gemessenen Wegpunkten
    Q = np.array(splev(np.linspace(0, 1, n_aus), tck)).T
    rest = float(np.median(np.abs(sp(s[gut]) - ts[gut]))); dists = [round(float(np.min(np.linalg.norm(Q - np.array(w), axis=1))), 3) for w in wege]
    res = dict(name=name, kamA=kidA, kamB=kidB, wege=[list(w) for w in wege], pfad_xyz=Q.round(3).tolist(), abstand_wegpunkte_m=dists,
               tiefenrest_median_m=round(rest, 3), n_verworfen=int((~gut).sum()), n_punkte=int(len(ts)), farbe=modus)
    if "--achse_n" in a:
        n_ = np.array([float(v) for v in a[a.index("--achse_n") + 1:a.index("--achse_n") + 3]]); n_ /= np.linalg.norm(n_); u_ = np.array([n_[1], -n_[0]])
        res["pfad_uvz"] = [[round(float(p[:2] @ u_), 3), round(float(p[:2] @ n_), 3), round(float(p[2]), 3)] for p in Q]
    json.dump(res, open(os.path.join(aus, f"kante_{name}.json"), "w"), indent=1)
    for tag, im, pf in (("A", imA, pA), ("B", imB, pB)):
        c = im.copy(); [cv2.circle(c, (int(x), int(y)), 3, (255, 0, 255), -1) for x, y in pf]
        x0, y0 = max(int(pf[:, 0].min()) - 60, 0), max(int(pf[:, 1].min()) - 60, 0); c = c[y0:int(pf[:, 1].max()) + 60, x0:int(pf[:, 0].max()) + 60]; h = 700
        cv2.imwrite(os.path.join(aus, f"kante_{name}_{tag}.jpg"), cv2.resize(c, (int(c.shape[1] * h / c.shape[0]), h)), [cv2.IMWRITE_JPEG_QUALITY, 88])
    print(f"{name}: {len(ts)} Punkte, verworfen {res['n_verworfen']}, Tiefenrest Median {rest:.3f} m, Abstand der Kurve zu den Wegpunkten {dists} m -> {aus}/kante_{name}.json")


if __name__ == "__main__":
    main()
