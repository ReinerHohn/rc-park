#!/usr/bin/env python3
"""fotos_sammeln.py - EIN SfM-Fotoordner aus allen Quellen (eigene Fotos + vorgepruefte Fremdbilder/Videobilder), Symlinks, ohne Dubletten.
Lehre Schwabentor 2026-11-14: Die dichte Wolke hatte 178 von > 450 verfuegbaren Bildern (Commons, Schlossberg, YouTube nie zusammengefuehrt).
  python3 -I tools/fotos_sammeln.py <ziel_ordner> --eigen <ordner> [--eigen ...] --geprueft <vorpruefung.json> [--geprueft ...] [--min-inlier 60]
Name im Ziel: <quelle>__<datei> (quelle = Ordnerpfad nach rc-park_daten/<objekt>/, '/' -> '_'), damit Herkunft sichtbar bleibt.
Dubletten (nicht eigene gegen eigene): 32x32-Graustufen-Vorschau (normiert), mittlere Abweichung < --dubl (6 Grauwerte) -> nur das groessere Bild bleibt.
Ausgabe: <ziel>/sammlung.json (Quelle, Inlier, Dubletten).
"""
import sys, os, json, glob, argparse
import numpy as np, cv2


def vorschau(p):
    g = cv2.imread(p, cv2.IMREAD_REDUCED_GRAYSCALE_4)
    if g is None: return None, 0
    h, w = g.shape; v = cv2.resize(g, (32, 32), interpolation=cv2.INTER_AREA).astype(np.float32); v = (v - v.mean()) / (v.std() + 1e-6) * 40
    return v, h * w


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("ziel"); ap.add_argument("--eigen", nargs="*", default=[]); ap.add_argument("--geprueft", nargs="*", default=[])
    ap.add_argument("--min-inlier", type=int, default=60); ap.add_argument("--dubl", type=float, default=6.0)
    a = ap.parse_args(); os.makedirs(a.ziel, exist_ok=True)
    kand = []                                                              # (pfad, quelle, inlier, eigen)
    for d in a.eigen:
        n_vor = len(kand)
        for p in sorted(glob.glob(os.path.join(d, "*"))):
            if p.lower().endswith((".jpg", ".jpeg", ".png")): kand.append((os.path.realpath(p), "eigen", None, True))
        if len(kand) == n_vor:                                             # 17.11.2026: leerer/fehlender --eigen-Ordner (Platte nicht eingehaengt, falscher Pfad) loeschte unten alle Verknuepfungen des Sammelordners und endete mit rc 0
            print(f"FEHLER: --eigen {d}: {'kein Bild (.jpg/.jpeg/.png)' if os.path.isdir(d) else 'Ordner fehlt'} - Sammelordner {a.ziel} bleibt UNVERAENDERT"); return 2
    for j in a.geprueft:
        for p, e in json.load(open(j))["bilder"].items():
            if e["inlier"] >= a.min_inlier: kand.append((os.path.realpath(p), os.path.dirname(p), e["inlier"], False))
    seen = {}; uniq = []
    for k in kand:
        if k[0] not in seen: seen[k[0]] = 1; uniq.append(k)
    V = []; G = []
    for p, *_ in uniq:
        v, n = vorschau(p); V.append(v); G.append(n)
    behalten = np.ones(len(uniq), bool); dubl = []
    ok = [i for i, v in enumerate(V) if v is not None]
    for i in [i for i in range(len(V)) if V[i] is None]: behalten[i] = False
    A = np.stack([V[i].ravel() for i in ok]) if ok else np.zeros((0, 1024))
    for x, i in enumerate(ok):
        if not behalten[i]: continue
        d = np.abs(A[x + 1:] - A[x]).mean(1)
        for y in np.flatnonzero(d < a.dubl):
            j = ok[x + 1 + y]
            if not behalten[j] or (uniq[i][3] and uniq[j][3]): continue   # eigene Serienbilder nie gegeneinander (SfM-Basis, Bestand)
            # eigene Fotos gewinnen immer; sonst das groessere Bild
            keep_i = uniq[i][3] or (not uniq[j][3] and G[i] >= G[j])
            weg, bleibt = (j, i) if keep_i else (i, j)
            behalten[weg] = False; dubl.append(dict(weg=uniq[weg][0], bleibt=uniq[bleibt][0], abw=round(float(d[y]), 2)))
            if weg == i: break
    if not behalten.any():                                                 # 17.11.2026: nichts zu sammeln (keine Quelle, kein Bild lesbar) = Fehler; die Verknuepfungen eines frueheren Laufs NICHT loeschen
        print(f"FEHLER: kein Bild zu sammeln ({len(uniq)} Kandidaten, davon lesbar {len(ok)}) - Sammelordner {a.ziel} bleibt UNVERAENDERT"); return 2
    for f in glob.glob(os.path.join(a.ziel, "*")):
        if os.path.islink(f): os.remove(f)
    liste = []
    for i, (p, q, n, eig) in enumerate(uniq):
        if not behalten[i]: continue
        qn = "eigen" if eig else q.split("/rc-park_daten/")[-1].split("/", 1)[-1].replace("/", "_") or "fremd"
        nm = f"{qn}__{os.path.basename(p)}"
        if os.path.lexists(os.path.join(a.ziel, nm)):                      # 15.11. Kaufhaus: gleicher Dateiname in zwei Unterordnern derselben Quelle -> Nummer anhaengen
            b, e = os.path.splitext(nm); k = 2
            while os.path.lexists(os.path.join(a.ziel, f"{b}_{k}{e}")): k += 1
            nm = f"{b}_{k}{e}"
        os.symlink(p, os.path.join(a.ziel, nm)); liste.append(dict(name=nm, pfad=p, quelle=qn, inlier=n))
    from collections import Counter
    json.dump(dict(bilder=liste, dubletten=dubl, je_quelle=Counter(x["quelle"] for x in liste)), open(os.path.join(a.ziel, "sammlung.json"), "w"), indent=1, ensure_ascii=False)
    print(f"{len(liste)} Bilder ({len(dubl)} Dubletten entfernt) -> {a.ziel}")
    for q, n in Counter(x["quelle"] for x in liste).most_common(): print(f"  {n:4d}  {q}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
