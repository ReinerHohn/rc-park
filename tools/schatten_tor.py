#!/usr/bin/env python3
"""schatten_tor.py - SCHATTIERUNGS-MASS (Hinweis, KEIN Tor): passt die Schattierung des Modells unter dem Licht DIESES Fotos zum Foto?
(Recherche 17.11.2026, Schritt 4 / F1; Vorlage tools/feinteil_tor.py)

Warum: foto_diff vergleicht Kantenlinien grob, feinteil_tor Richtungshistogramme der Feinstruktur. Ein Relief, das stimmt, muss im Foto auch HELL/DUNKEL an denselben
Stellen sein (Lambert): Steinwoelbung, Gesimsunterkante im Schatten, Fensterleibung. Brei (Netzrauschen) hat Feinstruktur, aber keine zum Licht passende Schattierung.
Je Foto (gleiche Kamera, gleiche Maske fuer alle verglichenen STL):
  1. Modell rastern (feinteil_tor.masken -> foto_diff): Normalenbild (Kamerarahmen), Silhouette, Verdecker, Graubild. Arbeitsaufloesung --ppm.
  2. Bandpass (Gauss --fein minus Gauss --grob, m) von Foto-Grau und Normalenkanaelen. Lichtrichtung l (3 Werte) JE STL per kleinsten Quadraten:
     band(grau) ~ sum_k l_k band(N_k) (Albedo lokal konstant). Dann Lambert-Bild max(0, N . l/|l|) (eigene Schatten), wieder Bandpass.
  3. Je Kachel (--kachel m) Korrelation Foto <-> Lambert-Bandpass; Note = Mittel der Kachelkorrelationen (Kacheln mit >= 60 % Maske und Foto-Feinenergie).
Kontrollen (--kontrolle): Wiederholung des ersten STL (bitgleich) und FALSCHES PAAR (Bild des naechsten Fotos auf diese Kamera) -> muss schlechter sein.
Aufruf: /media/oem/scan/venv-seg/bin/python -W ignore -I tools/schatten_tor.py modelle/<objekt>/objekt.json --fotos a,b --stl A.stl,B.stl [--namen a,b] [--aus j.json] [--bilder DIR] [--kontrolle]
Bereich: Vereinigung der Silhouetten ALLER STL (erodiert 0,1 m) ohne Verdecker - fuer alle gleich.
ERGEBNIS 17.11.2026 (kaufhaus_gk, 9 Fotos wie feinteil_tor): Noten nur 0,02-0,17. grob3 > gk Runde 3 9/9, grob3 > grob3 0,5 m verschoben 8/9, falsches Paar schlechter 8/9,
Wiederholung bitgleich 9/9 - ABER gk Runde 3 > Brei (Runde 2) nur 6/9 (0,034 / 0,031). Kriterium (>= 8/9 gegen Brei) VERFEHLT -> nicht in bauen_abnehmen.sh, nur Versuchswerkzeug.
Vermutung: Albedo (Fenster, Malerei, Gold) dominiert das Feinband; Schlagschatten (Gesimse) nicht modelliert.
"""
import sys, os, json, argparse, numpy as np, cv2
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _band(x, s1, s2): return cv2.GaussianBlur(x, (0, 0), s1) - cv2.GaussianBlur(x, (0, 0), s2)


def licht_und_lambert(g_b, N, M, s1, s2):
    """g_b: Bandpass Foto, N: Normalen (H,W,3), M: Maske -> (l, Lambert-Bandpass)"""
    Nb = np.stack([_band(N[..., k], s1, s2) for k in range(3)], -1)
    A = Nb[M]; y = g_b[M]; l = np.linalg.lstsq(A, y, rcond=None)[0]
    ln = l / max(np.linalg.norm(l), 1e-12); L = np.clip((N * ln).sum(-1), 0, None).astype(np.float32); L[~M] = float(np.median(L[M])) if M.any() else 0
    return l, _band(L, s1, s2)


def kachel_korr(a, b, M, kpx, min_anteil=0.6, min_e=None):
    H, W = M.shape; v = []; Kmap = np.full((H // kpx, W // kpx), np.nan)
    for i in range(H // kpx):
        for j in range(W // kpx):
            sl = (slice(i * kpx, (i + 1) * kpx), slice(j * kpx, (j + 1) * kpx)); m = M[sl]
            if m.mean() < min_anteil: continue
            x = a[sl][m]; y = b[sl][m]
            if x.std() < 1e-6 or y.std() < 1e-6 or (min_e is not None and x.std() < min_e): continue
            r = float(np.corrcoef(x, y)[0, 1]); v.append(r); Kmap[i, j] = r
    return (float(np.mean(v)) if len(v) >= 4 else None), len(v), Kmap


def foto_messen(objekt, nr, stls, p, bild_falsch=None, bilder=None, namen=None):
    import feinteil_tor as FT
    ms = []
    for s in stls: ms.append(FT.masken(objekt, nr, s, dmed_fix=(ms[0]["dmed"] if ms else None)))
    m0 = ms[0]; H, W = m0["sil"].shape; r = min(1.0, p["ppm"] / m0["ppm"]); ppm = m0["ppm"] * r
    def kl(x, interp=cv2.INTER_AREA): return cv2.resize(x, None, fx=r, fy=r, interpolation=interp) if r < 1 else x
    U = np.zeros((H, W), bool); O = np.zeros((H, W), bool)
    for m in ms: U |= m["sil"]; O |= m["occ"]
    er = max(1, int(round(0.1 * m0["ppm"]))) | 1; M = kl(((cv2.erode(U.astype(np.uint8), np.ones((er, er), np.uint8)) > 0) & ~O).astype(np.uint8), cv2.INTER_NEAREST) > 0
    s1, s2 = max(0.7, p["fein"] * ppm), max(2.0, p["grob"] * ppm); kpx = max(8, int(round(p["kachel"] * ppm)))
    def foto_b(gray): return _band(kl(gray.astype(np.float32) / 255.0), s1, s2)
    gb = foto_b(m0["grau"]); e_min = 0.25 * float(np.median(np.abs(gb[M]))) if M.any() else None
    erg = {}; bilder_l = []
    for i, m in enumerate(ms):
        N = np.nan_to_num(m["nrm"].astype(np.float32)); N[~m["sil"]] = 0; N = np.stack([kl(N[..., k]) for k in range(3)], -1)
        l, Lb = licht_und_lambert(gb, N, M & (np.abs(N).sum(-1) > 0), s1, s2)
        note, n, K = kachel_korr(gb, Lb, M, kpx, min_e=e_min); erg[(namen or stls)[i]] = dict(note=None if note is None else round(note, 4), kacheln=n, licht=[round(float(v), 4) for v in l]); bilder_l.append((Lb, K))
    if bild_falsch is not None:
        gf = foto_b(cv2.resize(bild_falsch, (W, H), interpolation=cv2.INTER_AREA))
        N = np.nan_to_num(ms[0]["nrm"].astype(np.float32)); N[~ms[0]["sil"]] = 0; N = np.stack([kl(N[..., k]) for k in range(3)], -1)
        _, Lb = licht_und_lambert(gf, N, M & (np.abs(N).sum(-1) > 0), s1, s2); nf, _, _ = kachel_korr(gf, Lb, M, kpx, min_e=e_min)
        erg["_falsches_paar_" + (namen or stls)[0]] = dict(note=None if nf is None else round(nf, 4))
    if bilder:
        os.makedirs(bilder, exist_ok=True)
        def vis(x):
            s = np.percentile(np.abs(x[M]), 98) if M.any() else 1; v = np.clip(x / max(s, 1e-9) * 127 + 128, 0, 255).astype(np.uint8); v = cv2.cvtColor(v, cv2.COLOR_GRAY2BGR); v[~M] //= 3; return v
        reihe = [vis(gb)] + [vis(Lb) for Lb, _ in bilder_l]
        for j, t_ in enumerate(["Foto Bandpass"] + [f"{n_}: {erg[n_]['note']}" for n_ in (namen or stls)]): cv2.putText(reihe[j], t_, (10, 40), 0, 1.1, (0, 0, 255), 3)
        o = np.hstack(reihe); fx = min(1.0, 3000.0 / o.shape[1]); cv2.imwrite(os.path.join(bilder, f"schatten_{nr[:40]}.jpg"), cv2.resize(o, None, fx=fx, fy=fx, interpolation=cv2.INTER_AREA), [cv2.IMWRITE_JPEG_QUALITY, 85])
    return erg


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--fotos", required=True); ap.add_argument("--stl", required=True); ap.add_argument("--namen")
    ap.add_argument("--aus"); ap.add_argument("--bilder"); ap.add_argument("--kontrolle", action="store_true")
    ap.add_argument("--ppm", type=float, default=60.0); ap.add_argument("--fein", type=float, default=0.02); ap.add_argument("--grob", type=float, default=0.25); ap.add_argument("--kachel", type=float, default=1.0)
    a = ap.parse_args(argv); p = dict(ppm=a.ppm, fein=a.fein, grob=a.grob, kachel=a.kachel)
    stls = a.stl.split(","); namen = a.namen.split(",") if a.namen else None; fotos = a.fotos.split(","); obj = json.load(open(a.objekt)); od = os.path.dirname(os.path.abspath(a.objekt))
    root = os.path.dirname(os.path.dirname(od)); import glob
    def bild(nr): q = glob.glob(os.path.join(root, obj["fotos_dir"], nr + ".*")); return cv2.imread(q[0], cv2.IMREAD_GRAYSCALE) if q else None
    if a.kontrolle: stls = stls + [stls[0]]; namen = (namen or a.stl.split(",")) + ["_wiederholung"]
    alle = {}
    for i, nr in enumerate(fotos):
        try:
            alle[nr] = foto_messen(a.objekt, nr, stls, p, bild_falsch=bild(fotos[(i + 1) % len(fotos)]) if a.kontrolle else None, bilder=a.bilder, namen=namen)
            print(nr[:40], {k: v["note"] for k, v in alle[nr].items()}, flush=True)
        except Exception as e:
            print(nr[:40], "FEHLER", repr(e)[:200], flush=True)
    nm = namen or stls; mittel = {n_: (float(np.mean([alle[f][n_]["note"] for f in alle if alle[f].get(n_, {}).get("note") is not None])) if alle else None) for n_ in nm}
    print("Mittel:", {k: (round(v, 4) if v is not None else None) for k, v in mittel.items()})
    if a.aus: json.dump(dict(fotos=alle, mittel=mittel, parameter=p, stl=stls), open(a.aus, "w"), indent=1)
    return 0 if alle else 2


if __name__ == "__main__":
    sys.exit(main())
