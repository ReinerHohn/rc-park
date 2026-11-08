#!/usr/bin/env python3
"""test_kanten_pipelines.py - synthetischer Beweis der vier Kantenkarten-Pipelines (S10 Teil A) mit BEKANNTEN Kanten.

Szene (gerendert): Fassade mit Ziegel-/Steinstruktur, Dach mit Schuppen, Fenster mit Rahmen, Rundbogenoeffnungen, Gesimsband, Pilaster,
Schlagschatten (KEINE wahre Kante), Rauschen, Unschaerfe, JPEG. Das Gesimsband hat dieselbe Helligkeit L wie die Wand, aber anderen Farbton
(Farbgrenze gleicher Helligkeit). Wahre Kanten = Grenzen der Regionen-Karte (Geometrie/Material), NICHT Textur und NICHT Schatten.
Zwei Szenen (A: Rot/Gold, Schatten von links oben; B: Gegenprobe mit anderen Farben, Rastern, Schatten von rechts) - alle Schwellen fest VOR dem Lauf:
  Kantenpixel = Karte >= 0,5, auf 1 px ausgeduennt; Toleranz 2 px; Abstimmung k aus 4 mit 2 px Zustimmungsradius; weiche Abstimmung = Mittel der 4 Karten >= 0,5.
Kennzahlen: Praezision (Anteil der Kantenpixel nahe einer wahren Kante), Vollstaendigkeit (Anteil wahrer Kantenpixel nahe einer Kantenpixel),
plus Teilkennzahlen: Vollst. Farbband (Farbgrenze gleicher Helligkeit), Vollst. Boegen, Fehlalarm Schatten (Anteil der Schattenkanten-Pixel, die als Kante gemeldet werden; kleiner = besser),
Fehlalarm Textur (Anteil Kantenpixel im Wandinneren weit weg von jeder wahren Kante).
Aufruf (venv-seg):  test_kanten_pipelines.py --aus ORDNER [--szenen A,B] [--pipelines p1,p2,p3,p4]
Ausgabe: <aus>/szene_<S>.png (Bild), gt_<S>.png, karten_<S>_<p>.png, blatt_<S>.jpg (Bild | 4 Karten | Abstimmungen), ergebnis.json
"""
import argparse, json, os, sys
import numpy as np, cv2

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kanten_pipelines as KP

TOL = 2.0
SCHWELLE = 0.5
W, H = 1200, 800


def _lab2bgr(L, a, b):
    return cv2.cvtColor(np.array([[[L, a, b]]], np.float32), cv2.COLOR_Lab2BGR)[0, 0]


def szene(name):
    """-> (bgr uint8, label int32 (Regionen), schattenkante bool, farbband bool-Kantenmaske, bogenkante bool)"""
    if name == "A":
        rng = np.random.RandomState(11)
        wand = _lab2bgr(48, 38, 22); band = _lab2bgr(48, 6, 45); dach = _lab2bgr(32, 4, 8); pil = _lab2bgr(54, 30, 20)
        glas = _lab2bgr(14, 0, 0); rahm = _lab2bgr(78, 3, 6); innen = _lab2bgr(18, 3, 3); himmel = _lab2bgr(88, -2, -4)
        nfen, nbog, strukt, schat = 5, 3, "ziegel", (-1, -1)
    else:
        rng = np.random.RandomState(29)
        wand = _lab2bgr(66, -6, 10); band = _lab2bgr(66, 14, 18); dach = _lab2bgr(40, -3, -4); pil = _lab2bgr(72, -5, 8)
        glas = _lab2bgr(22, 2, -5); rahm = _lab2bgr(90, 0, 3); innen = _lab2bgr(24, 0, 0); himmel = _lab2bgr(80, -4, -8)
        nfen, nbog, strukt, schat = 4, 2, "quader", (1, -1)
    lab = np.zeros((H, W), np.int32)                    # 0 Himmel 1 Wand 2 Dach 3 Band 4 Pilaster 5.. Fenster/Boegen
    fassade = (80, 330, W - 80, H - 60)
    x0, y0, x1, y1 = fassade
    cv2.fillPoly(lab, [np.array([(x0 - 20, y0), (W // 2, 95), (x1 + 20, y0)], np.int32)], 2)   # Dach
    cv2.rectangle(lab, (x0, y0), (x1, y1), 1, -1)
    cv2.rectangle(lab, (x0, y0), (x1, y0 + 46), 3, -1)                                          # Gesimsband
    for px in (x0, x1 - 40, W // 2 - 20):
        cv2.rectangle(lab, (px, y0 + 46), (px + 40, y1), 4, -1)                                 # Pilaster
    rid = 10; elem = {}
    rng2 = np.random.RandomState(3)
    # Fenster in oberer Reihe (Rahmen + Glas), Boegen unten
    ys = y0 + 110
    xs = np.linspace(x0 + 110, x1 - 110, nfen)
    for x in xs:
        if abs(x - W // 2) < 70: continue
        cv2.rectangle(lab, (int(x) - 38, ys), (int(x) + 38, ys + 130), rid, -1); rid += 1       # Rahmen
        cv2.rectangle(lab, (int(x) - 28, ys + 10), (int(x) + 28, ys + 120), rid, -1); rid += 1  # Glas
    bog_ids = []
    xb = np.linspace(x0 + 190, x1 - 190, nbog)
    for x in xb:
        r = 52; yb = y1 - 150
        cv2.rectangle(lab, (int(x) - r, yb), (int(x) + r, y1), rid, -1)
        cv2.ellipse(lab, (int(x), yb), (r, r), 0, 180, 360, rid, -1)
        bog_ids.append(rid); rid += 1
    ids_fenster_rahmen = [i for i in range(10, rid) if i not in bog_ids]
    # Farbe + Struktur
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    img = np.zeros((H, W, 3), np.float32)

    def fuellen(m, col, tex=None):
        c = np.ones((H, W, 3), np.float32) * np.array(col, np.float32)[None, None]
        if tex is not None: c = c * tex[..., None]
        img[m] = c[m]
    if strukt == "ziegel":
        zeile = (yy // 9).astype(int); vers = (zeile % 2) * 11
        spalte = ((xx + vers) // 22).astype(int)
        f = 0.88 + 0.2 * rng.rand(H // 9 + 2, W // 11 + 4)[zeile % (H // 9 + 2), spalte % (W // 11 + 4)]
        fuge = (((yy % 9) < 1.5) | (((xx + vers) % 22) < 1.5)); f = np.where(fuge, 0.62, f)
        textur_wand = f.astype(np.float32)
    else:
        zeile = (yy // 40).astype(int); vers = (zeile % 2) * 30
        spalte = ((xx + vers) // 60).astype(int)
        f = 0.94 + 0.12 * rng.rand(H // 40 + 2, W // 30 + 4)[zeile % (H // 40 + 2), spalte % (W // 30 + 4)]
        fuge = (((yy % 40) < 2.5) | (((xx + vers) % 60) < 2.5)); f = np.where(fuge, 0.80, f)
        textur_wand = f.astype(np.float32)
    schuppe = (0.82 + 0.22 * (0.5 + 0.5 * np.sin(xx / 5.0 + 1.7 * np.sin(yy / 9.0)) * np.sin(yy / 6.0 + xx / 40.0))).astype(np.float32)
    fuellen(lab == 0, himmel * 1.0)
    # Himmelsverlauf
    img[lab == 0] *= (1.0 - 0.08 * yy[lab == 0] / H)[:, None]
    fuellen(lab == 1, wand, textur_wand)
    fuellen(lab == 2, dach, schuppe)
    fuellen(lab == 3, band, 0.97 + 0.06 * rng.rand(H, W).astype(np.float32))
    fuellen(lab == 4, pil, (0.95 + 0.1 * rng.rand(H, W)).astype(np.float32))
    for i in range(10, rid):
        if i in bog_ids: fuellen(lab == i, innen, (0.9 + 0.2 * rng.rand(H, W)).astype(np.float32))
        else:
            k = (i - 10)
            fuellen(lab == i, rahm if k % 2 == 0 else glas)
    # Schlagschatten: Streifen schraeg ueber die Fassade (Mehrfach-Region), Schattenkante = Rand des Streifens
    sx, sy = schat
    t = (xx * (-sy) + yy * sx) * 0.0 + (xx * 0.62 * sx * -1 + yy * 0.78 * -1 * sy * -1)
    nrm = (xx - W / 2) * 0.8 * (1 if sx < 0 else -1) + (yy - H / 2) * 0.6
    sch = nrm > 70                                         # Halbebene im Schatten
    sch &= (lab != 0)
    schatt = np.where(sch, 0.60, 1.0).astype(np.float32)
    schatt = cv2.GaussianBlur(schatt, (0, 0), 1.6)
    img *= schatt[..., None]
    # Schattenkante (Maske) = wo sch wechselt, nur im Bauwerk
    sk = (cv2.dilate(sch.astype(np.uint8), np.ones((3, 3), np.uint8)) != cv2.erode(sch.astype(np.uint8), np.ones((3, 3), np.uint8))) & (lab != 0)
    out = np.clip(img, 0, 1)
    out = cv2.GaussianBlur(out, (0, 0), 0.9)
    out = np.clip(out + rng.randn(H, W, 3).astype(np.float32) * 0.012, 0, 1)
    bgr = (out * 255).astype(np.uint8)
    ok, enc = cv2.imencode(".jpg", bgr, [cv2.IMWRITE_JPEG_QUALITY, 85]); bgr = cv2.imdecode(enc, 1)
    # wahre Kanten
    def grenze(l):
        d = np.zeros(l.shape, bool)
        d[:, 1:] |= l[:, 1:] != l[:, :-1]; d[1:, :] |= l[1:, :] != l[:-1, :]
        return d
    gt = grenze(lab)
    gt_band = grenze((lab == 3).astype(np.int32)) & gt
    gt_bogen = np.zeros_like(gt)
    for i in bog_ids: gt_bogen |= grenze((lab == i).astype(np.int32))
    return bgr, gt, dict(schatten=sk, band=gt_band, bogen=gt_bogen, label=lab)


def skelett(p, s=SCHWELLE):
    from skimage.morphology import skeletonize
    return skeletonize(p >= s)


def naehe(maske, tol=TOL):
    """Distanz zu naechstem True-Pixel <= tol."""
    if not maske.any(): return np.zeros(maske.shape, bool)
    d = cv2.distanceTransform((~maske).astype(np.uint8), cv2.DIST_L2, 3)
    return d <= tol


def bewerten(kante, gt, extra, wandinnen):
    """kante, gt bool. -> dict Kennzahlen"""
    nk = naehe(gt); ng = naehe(kante)
    n = max(1, kante.sum()); g = max(1, gt.sum())
    r = dict(praezision=float((kante & nk).sum() / n), vollstaendigkeit=float((gt & ng).sum() / g), n_kante=int(kante.sum()),
             voll_band=float((extra["band"] & ng).sum() / max(1, extra["band"].sum())),
             voll_bogen=float((extra["bogen"] & ng).sum() / max(1, extra["bogen"].sum())),
             fehlalarm_schatten=float((extra["schatten"] & ~nk & ng).sum() / max(1, (extra["schatten"] & ~nk).sum())),
             fehlalarm_textur=float((kante & wandinnen).sum() / n))
    p, v = r["praezision"], r["vollstaendigkeit"]
    r["f1"] = float(2 * p * v / max(1e-9, p + v))
    return r


def abstimmung(skels, k):
    """Kantenpixel (Vereinigung der Skelette), bei denen >= k Pipelines innerhalb 2 px ein Skelettpixel haben."""
    nah = [naehe(s) for s in skels]
    cnt = sum(n.astype(int) for n in nah)
    uni = np.zeros_like(skels[0])
    for s in skels: uni |= s
    return uni & (cnt >= k)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--aus", required=True); ap.add_argument("--szenen", default="A,B"); ap.add_argument("--pipelines", default="p1,p2,p3,p4")
    a = ap.parse_args(argv); os.makedirs(a.aus, exist_ok=True)
    pipes = a.pipelines.split(","); erg = {}
    for sn in a.szenen.split(","):
        bgr, gt, ex = szene(sn)
        cv2.imwrite(os.path.join(a.aus, f"szene_{sn}.png"), bgr); cv2.imwrite(os.path.join(a.aus, f"gt_{sn}.png"), gt.astype(np.uint8) * 255)
        lab = ex["label"]
        wand_innen = (~naehe(gt, 6.0)) & (lab != 0)                  # weit (> 6 px) von jeder wahren Kante: reine Flaeche -> Kante dort = Textur/Rauschen
        wand_innen &= ~naehe(ex["schatten"], 6.0)                    # Schatten gesondert gezaehlt
        karten = {}; skels = {}
        for p in pipes:
            k = KP.KARTEN[p](bgr); karten[p] = k; KP.speichern(k, os.path.join(a.aus, f"karten_{sn}_{p}.png")); skels[p] = skelett(k)
        res = {}
        for p in pipes: res[p] = bewerten(skels[p], gt, ex, wand_innen)
        sl = [skels[p] for p in pipes]
        for k in (2, 3, 4):
            if len(sl) >= k: res[f"stimme_k{k}"] = bewerten(abstimmung(sl, k), gt, ex, wand_innen)
        mitt = np.mean([karten[p] for p in pipes], 0); KP.speichern(mitt, os.path.join(a.aus, f"karten_{sn}_mittel.png"))
        res["weich_mittel"] = bewerten(skelett(mitt), gt, ex, wand_innen)
        erg[sn] = res
        # Sichtblatt
        t = lambda x: cv2.cvtColor((np.clip(x, 0, 1) * 255).astype(np.uint8), cv2.COLOR_GRAY2BGR)
        sm = lambda x: cv2.resize(x, (W // 2, H // 2), interpolation=cv2.INTER_AREA)
        def lab_(x, s): y = x.copy(); cv2.putText(y, s, (6, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 255), 2); return y
        tiles = [lab_(sm(bgr), f"Szene {sn}"), lab_(sm(t(gt.astype(np.float32))), "wahre Kanten")]
        for p in pipes: tiles.append(lab_(sm(t(karten[p])), f"{p} {KP.NAMEN[p]}  P{res[p]['praezision']:.2f} V{res[p]['vollstaendigkeit']:.2f}"))
        tiles.append(lab_(sm(t(mitt)), f"weich Mittel P{res['weich_mittel']['praezision']:.2f} V{res['weich_mittel']['vollstaendigkeit']:.2f}"))
        k3 = abstimmung(sl, 3); tiles.append(lab_(sm(t(cv2.dilate(k3.astype(np.float32), np.ones((2, 2))))), f"k=3 P{res['stimme_k3']['praezision']:.2f} V{res['stimme_k3']['vollstaendigkeit']:.2f}"))
        while len(tiles) % 3: tiles.append(np.zeros_like(tiles[0]))
        blatt = np.vstack([np.hstack(tiles[i:i + 3]) for i in range(0, len(tiles), 3)])
        cv2.imwrite(os.path.join(a.aus, f"blatt_{sn}.jpg"), blatt)
        print(f"== Szene {sn}")
        for k, v in res.items():
            print(f"{k:13s} P {v['praezision']:.3f} V {v['vollstaendigkeit']:.3f} F1 {v['f1']:.3f}  Band {v['voll_band']:.2f} Bogen {v['voll_bogen']:.2f}  Schatten {v['fehlalarm_schatten']:.3f} Textur {v['fehlalarm_textur']:.3f}  n={v['n_kante']}")
    json.dump(erg, open(os.path.join(a.aus, "ergebnis.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
