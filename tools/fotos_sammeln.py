#!/usr/bin/env python3
"""fotos_sammeln.py - EIN SfM-Fotoordner aus allen Quellen (eigene Fotos + vorgepruefte Fremdbilder/Videobilder), Symlinks, ohne Dubletten.
Lehre Schwabentor 2026-11-14: Die dichte Wolke hatte 178 von > 450 verfuegbaren Bildern (Commons, Schlossberg, YouTube nie zusammengefuehrt).
  python3 -I tools/fotos_sammeln.py <ziel_ordner> --eigen <ordner> [--eigen ...] --geprueft <vorpruefung.json> [--geprueft ...] [--min-inlier 60]
Name im Ziel: <quelle>__<datei> (quelle = Ordnerpfad nach rc-park_daten/<objekt>/, '/' -> '_'), damit Herkunft sichtbar bleibt.
Dubletten (nicht eigene gegen eigene): 32x32-Graustufen-Vorschau (normiert), mittlere Abweichung < --dubl (6 Grauwerte) -> nur das groessere Bild bleibt.
Ausgabe: <ziel>/sammlung.json (Quelle, Inlier, Dubletten, fremd_in_eigen).
FREMDQUELLEN IM --eigen-ORDNER (22.11.2026, schwabentor-1122): fotos_dir_quelle zeigte auf einen ALTEN Sammelordner (schwab_auto/fotos, 16.11.) - 311 von 504 'eigenen'
Bildern waren Videobilder/Commons/Online-Fotos. Als eigen__<basename(realpath)> verloren sie die Quelle (vf_014 aus zwei Clips -> _2/_3), liefen nicht durch die
Vorpruefung (Videobilder mit eingeblendeter Schrift = config-7-Paare) und nicht durch die Dublettenpruefung. Jetzt (herkunft()): ein Bild im --eigen-Ordner ist FREMD, wenn
  (a) der --eigen-Ordner eine sammlung.json hat und sie fuer das Bild eine Quelle != eigen nennt, oder
  (b) der Verknuepfungsname eine fruehere Sammel-Quelle traegt ('<quelle>__...', quelle != eigen), oder
  (c) ein Glied des echten Pfads unter rc-park_daten/<objekt>/ ein Fremdquellordner ist (FREMD_GLIED: video_frames, commons, online, netz, mapillary, ...).
Fremde Bilder zaehlen wie Fremdquellen: mit --geprueft nur, wenn die Vorpruefung sie mit >= --min-inlier fuehrt (Quelle = ihr echter Ordner, z. B.
video_frames_<clip>__vf_NNN), sonst fallen sie weg (gemeldet); ohne --geprueft bleiben sie ungeprueft, aber mit echter Quelle. gesamtkette.py gibt die Ordner aus
fremde_ordner() an die Vorpruefung. --trocken: nur zaehlen, Ziel bleibt unveraendert.
"""
import sys, os, re, json, glob, argparse
from collections import Counter

FREMD_GLIED = re.compile(r"^(video_frames|video_kand|commons|online\d*|netz|mapillary|openverse|flickr|youtube|web)(_|$)", re.I)   # ANNAHME: Ordnernamen der Fremdquellen unter rc-park_daten/<objekt>/


def quelle_aus_pfad(p):
    """Quellname wie fuer Fremdquellen: Ordnerpfad nach rc-park_daten/<objekt>/, '/' -> '_'."""
    return os.path.dirname(p).split("/rc-park_daten/")[-1].split("/", 1)[-1].replace("/", "_") or "fremd"


def herkunft(d):
    """--eigen-Ordner d -> Liste (realpath, fremd: bool, grund). Siehe Kopf (a)-(c)."""
    sj = {}
    if os.path.isfile(os.path.join(d, "sammlung.json")):
        try: sj = {x["name"]: x.get("quelle") for x in json.load(open(os.path.join(d, "sammlung.json"))).get("bilder", [])}
        except Exception: sj = {}
    aus = []
    for p in sorted(glob.glob(os.path.join(d, "*"))):
        if not p.lower().endswith((".jpg", ".jpeg", ".png")): continue
        n = os.path.basename(p); r = os.path.realpath(p); grund = None
        if sj.get(n) and sj[n] != "eigen": grund = f"sammlung.json: {sj[n]}"
        elif os.path.islink(p) and "__" in n and n.split("__")[0] != "eigen": grund = f"Sammelname {n.split('__')[0]}"
        elif "/rc-park_daten/" in r and any(FREMD_GLIED.match(g) for g in r.split("/rc-park_daten/")[-1].split("/")[1:-1]): grund = "Fremdquellordner " + quelle_aus_pfad(r)
        aus.append((r, grund is not None, grund))
    return aus


def fremde_ordner(eigen_dirs):
    """Echte Ordner der Fremdbilder in den --eigen-Ordnern (fuer die Vorpruefung der Kette)."""
    return sorted({os.path.dirname(r) for d in eigen_dirs if os.path.isdir(d) for r, f, _ in herkunft(d) if f})
import numpy as np, cv2


def vorschau(p):
    g = cv2.imread(p, cv2.IMREAD_REDUCED_GRAYSCALE_4)
    if g is None: return None, 0
    h, w = g.shape; v = cv2.resize(g, (32, 32), interpolation=cv2.INTER_AREA).astype(np.float32); v = (v - v.mean()) / (v.std() + 1e-6) * 40
    return v, h * w


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("ziel"); ap.add_argument("--eigen", nargs="*", default=[]); ap.add_argument("--geprueft", nargs="*", default=[])
    ap.add_argument("--min-inlier", type=int, default=60); ap.add_argument("--dubl", type=float, default=6.0)
    ap.add_argument("--trocken", action="store_true", help="nur Herkunft/Vorpruefung zaehlen, Ziel unveraendert")
    a = ap.parse_args(); a.trocken or os.makedirs(a.ziel, exist_ok=True)
    kand = []                                                              # (pfad, quelle, inlier, eigen)
    fie = {}                                                               # Fremdbilder im --eigen-Ordner: realpath -> grund
    for d in a.eigen:
        n_vor = len(kand); n_bild = 0
        for r, fremd, grund in herkunft(d):
            n_bild += 1
            if fremd: fie[r] = grund
            else: kand.append((r, "eigen", None, True))
        if n_bild == 0:                                             # 17.11.2026: leerer/fehlender --eigen-Ordner (Platte nicht eingehaengt, falscher Pfad) loeschte unten alle Verknuepfungen des Sammelordners und endete mit rc 0
            print(f"FEHLER: --eigen {d}: {'kein Bild (.jpg/.jpeg/.png)' if os.path.isdir(d) else 'Ordner fehlt'} - Sammelordner {a.ziel} bleibt UNVERAENDERT"); return 2
    gep = {}
    for j in a.geprueft:
        for p, e in json.load(open(j))["bilder"].items():
            gep.setdefault(os.path.realpath(p), (p, e["inlier"]))
            if e["inlier"] >= a.min_inlier: kand.append((os.path.realpath(p), os.path.dirname(p), e["inlier"], False))
    fie_bil = dict(gesamt=len(fie), je_quelle=dict(Counter(quelle_aus_pfad(r) for r in fie)), nicht_vorgeprueft=0, unter_min_inlier=0, ungeprueft_behalten=0)
    for r in fie:                                                          # Fremdbilder aus dem --eigen-Ordner: wie Fremdquellen (oben schon ueber --geprueft, falls stimmig)
        if not a.geprueft: kand.append((r, os.path.dirname(r), None, False)); fie_bil["ungeprueft_behalten"] += 1
        elif r not in gep: fie_bil["nicht_vorgeprueft"] += 1
        elif gep[r][1] < a.min_inlier: fie_bil["unter_min_inlier"] += 1
    n_eig = sum(1 for k in kand if k[3])
    if fie:
        print(f"ACHTUNG: {len(fie)} von {len(fie) + n_eig} 'eigenen' Bildern sind Fremdquellen -> als Fremdquelle behandelt: "
              + ", ".join(f"{q} {n}" for q, n in Counter(quelle_aus_pfad(r) for r in fie).most_common())
              + f" | ohne Vorpruefung {fie_bil['nicht_vorgeprueft']}, unter {a.min_inlier} Inliern {fie_bil['unter_min_inlier']}, ungeprueft behalten {fie_bil['ungeprueft_behalten']}")
    if a.trocken:
        print(json.dumps(dict(eigen=n_eig, fremd_in_eigen=fie_bil), ensure_ascii=False)); return 0
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
    json.dump(dict(bilder=liste, dubletten=dubl, fremd_in_eigen=fie_bil, je_quelle=Counter(x["quelle"] for x in liste)), open(os.path.join(a.ziel, "sammlung.json"), "w"), indent=1, ensure_ascii=False)
    print(f"{len(liste)} Bilder ({len(dubl)} Dubletten entfernt) -> {a.ziel}")
    for q, n in Counter(x["quelle"] for x in liste).most_common(): print(f"  {n:4d}  {q}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
