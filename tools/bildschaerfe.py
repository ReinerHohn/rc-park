#!/usr/bin/env python3
"""bildschaerfe.py - robustes Schaerfemass fuer Handy-/Eingangsfotos (2026-11-06, Register-Eintrag siehe VERSUCHSREGISTER).

Problem: Laplace-Varianz ueber das GANZE Bild ist auf glatten Flaechen (roter Putz, Himmel) klein, obwohl das Foto scharf ist.
Mass hier (alles auf Breite --breite px, Standard 1500):
  kachel_q   = 90.-Perzentil der Laplace-Varianz ueber Kacheln (8x6): ein scharfes Foto hat mindestens einige texturierte scharfe Kacheln,
               ein verwackeltes/unscharfes hat ueberall wenig (auch wo Textur ist)
  kante_rel  = Verhaeltnis 99.-Perzentil Gradientenbetrag / 99.-Perzentil Gradientenbetrag nach 2x2-Glaettung (Kantenschaerfe unabhaengig vom Kontrast:
               scharfe Kanten verlieren durch Glaettung viel Gradient (Verhaeltnis hoch), schon unscharfe kaum (-> nahe 1))
  global_lap = alte Laplace-Varianz (nur zum Vergleich)
Urteil (Schwellen = ANNAHME, an Sichtprobe kalibriert, siehe --help): 'scharf' wenn kachel_q >= --min-kachel ODER kante_rel >= --min-kante;
'pruefen' dazwischen (Sichtprobe, NICHT automatisch verwerfen); 'unscharf' wenn beides deutlich darunter.
  /media/oem/scan/venv-seg/bin/python -I tools/bildschaerfe.py ORDNER_ODER_BILDER... --json out.json [--kontakt kontakt.jpg]
"""
import sys, os, json, glob, argparse
import numpy as np, cv2


def schaerfe(img_bgr_or_gray, breite=1500, kacheln=(8, 6)):
    g = img_bgr_or_gray if img_bgr_or_gray.ndim == 2 else cv2.cvtColor(img_bgr_or_gray, cv2.COLOR_BGR2GRAY)
    h, w = g.shape
    if w != breite: g = cv2.resize(g, (breite, int(round(h * breite / w))), interpolation=cv2.INTER_AREA)
    g = g.astype(np.float32)
    lap = cv2.Laplacian(g, cv2.CV_32F)
    H, W = g.shape; kx, ky = kacheln; v = []
    for j in range(ky):
        for i in range(kx):
            t = lap[j * H // ky:(j + 1) * H // ky, i * W // kx:(i + 1) * W // kx]; v.append(float(t.var()))
    gx = cv2.Sobel(g, cv2.CV_32F, 1, 0, ksize=3); gy = cv2.Sobel(g, cv2.CV_32F, 0, 1, ksize=3); gm = np.hypot(gx, gy)
    gs = cv2.blur(g, (2, 2)); sx = cv2.Sobel(gs, cv2.CV_32F, 1, 0, ksize=3); sy = cv2.Sobel(gs, cv2.CV_32F, 0, 1, ksize=3); sm = np.hypot(sx, sy)
    a, b = float(np.percentile(gm, 99.5)), float(np.percentile(sm, 99.5))
    return dict(kachel_q=float(np.percentile(v, 90)), kachel_max=float(max(v)), kante_rel=a / max(b, 1e-6), kante_abs=a, global_lap=float(lap.var()))


def urteil(m, min_kachel=150.0, min_kante=1.25):
    if m["kachel_q"] >= min_kachel or m["kante_rel"] >= min_kante: return "scharf"
    if m["kachel_q"] >= 0.4 * min_kachel or m["kante_rel"] >= 0.9 * min_kante: return "pruefen"
    return "unscharf"


def kontaktbogen(pfade, texte, ziel, spalten=6, kachel=(320, 240)):
    zeilen = (len(pfade) + spalten - 1) // spalten; B = np.zeros((zeilen * kachel[1], spalten * kachel[0], 3), np.uint8)
    for k, (p, t) in enumerate(zip(pfade, texte)):
        im = cv2.imread(p)
        if im is None: continue
        im = cv2.resize(im, kachel); cv2.putText(im, t, (4, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1, cv2.LINE_AA)
        r, c = divmod(k, spalten); B[r * kachel[1]:(r + 1) * kachel[1], c * kachel[0]:(c + 1) * kachel[0]] = im
    cv2.imwrite(ziel, B, [cv2.IMWRITE_JPEG_QUALITY, 85])


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pfade", nargs="+"); ap.add_argument("--json"); ap.add_argument("--kontakt")
    ap.add_argument("--min-kachel", type=float, default=150.0, help="ANNAHME: Laplace-Varianz 90.-Perz. der Kacheln")
    ap.add_argument("--min-kante", type=float, default=1.25, help="ANNAHME: Kantenschaerfe-Verhaeltnis")
    a = ap.parse_args(argv); fs = []
    for p in a.pfade: fs += sorted(glob.glob(os.path.join(p, "*.jpg"))) if os.path.isdir(p) else [p]
    out = {}
    for f in fs:
        im = cv2.imread(f, cv2.IMREAD_REDUCED_GRAYSCALE_2)
        if im is None: continue
        m = schaerfe(im); m["urteil"] = urteil(m, a.min_kachel, a.min_kante); out[f] = m
        print(f"{os.path.basename(f):16s} kachel_q={m['kachel_q']:8.1f} kante_rel={m['kante_rel']:5.2f} global={m['global_lap']:7.1f} {m['urteil']}")
    if a.json: json.dump(out, open(a.json, "w"), indent=1)
    if a.kontakt: kontaktbogen(list(out), [f"{os.path.basename(f)[-10:-4]} q{m['kachel_q']:.0f} k{m['kante_rel']:.2f}" for f, m in out.items()], a.kontakt)
    return 0


if __name__ == "__main__": sys.exit(main())
