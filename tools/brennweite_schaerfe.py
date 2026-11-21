#!/usr/bin/env python3
"""brennweite_schaerfe.py <sparse-modell> [--aus bericht.json] [--liste datei.txt] [--sperrliste datei.txt --vereinen liste.txt ...] [--weich 4] [--unbestimmt 10]

WIE SCHARF BESTIMMT EIN FOTO SEINE BRENNWEITE? (21.11.2026, Nutzerauftrag: "Methode, wie wir Einzelfotos ohne Brennweite rausfiltern".)
Befund davor: zwischen zwei Mapper-Laeufen (global/global, global/schrittweise, schrittweise/schrittweise) wandern fast nur EINZELFOTOS; ihre Brennweite faellt je Lauf 2-6 %
anders aus. Ursache ist keine Mapper-Eigenheit, sondern die Aufnahme: aus der Ferne / frontal auf eine flache Wand sind "laengere Brennweite" und "weiter weg" im Bild fast
nicht zu unterscheiden. Ob ein Foto so ist, laesst sich AM FERTIGEN MODELL je Kamera messen, ohne zweiten Lauf und ohne EXIF:
  1. Je Kamera (alle Bilder mit dieser Kamera gemeinsam) die 3D-Punkte, die von >= 3 ANDEREN Bildern getragen werden (Spur >= 4) und jetzt <= 4 px abweichen.
  2. Brennweite in 25 Stufen von 0,70 bis 1,43 x Modellwert setzen, je Stufe die Kameralage neu ausgleichen (PnP), Rest-Abweichung in Pixeln merken.
  3. SCHAERFE = Breite des Bereichs, in dem der Rest hoechstens 10 % ueber dem Minimum liegt (in % der Brennweite). Schmal = die Punkte legen die Brennweite fest;
     breit oder bis an den Rand offen = unbestimmt. Dazu LAGE-SPANNE: wie weit die Kamera ueber diesen Bereich wandert (% der Szenengroesse) - das ist die erwartete Streuung.
Urteil je Kamera: scharf (< --weich %), weich, unbestimmt (>= --unbestimmt % oder offen), zu_wenig (< 15 Punkte).
Verwendung: 'unbestimmt' (+ 'zu_wenig') nicht zum Messen nehmen (Kanten-Sweep, Wandbild, Massstab) - Liste --liste, gleiche Rolle wie unstabil.txt des Konsens-Mappers.
rc 0. Rechenzeit Sekunden.
"""
import sys, os, json, argparse, collections
import numpy as np


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("modell"); ap.add_argument("--aus"); ap.add_argument("--liste"); ap.add_argument("--weich", type=float, default=4.0); ap.add_argument("--unbestimmt", type=float, default=10.0)
    ap.add_argument("--sperrliste", help="Sperrliste fuers Messen schreiben: unbestimmt + zu_wenig, vereinigt mit den Listen aus --vereinen (Kette: sfm/sperrliste_messen.txt fuer tools/dicht_bildwahl.py --ohne)")
    ap.add_argument("--vereinen", nargs="*", default=[], help="vorhandene Namenslisten (eine Zeile je Bild), die in die Sperrliste eingehen, z. B. konsens_arbeit/unstabil.txt; sie werden nicht veraendert"); a = ap.parse_args()
    import pycolmap, cv2
    r = pycolmap.Reconstruction(a.modell); KS = np.geomspace(0.70, 1.43, 25); G = collections.defaultdict(list); Z = np.array([0.0, 0, 0]); alle = []
    for im in r.images.values():
        w = im.cam_from_world() if callable(im.cam_from_world) else im.cam_from_world; R = w.rotation.matrix(); t = np.array(w.translation); cam = r.cameras[im.camera_id]; f = float(cam.params[0]); X, xy = [], []
        for p in im.points2D:
            if p.has_point3D() and r.points3D[p.point3D_id].track.length() >= 4: X.append(r.points3D[p.point3D_id].xyz); xy.append(p.xy)
        alle.append(-R.T @ t)
        if len(X) < 15: G[im.camera_id].append((im.name, None)); continue
        X = np.array(X); xn = np.array(cam.cam_from_img(np.array(xy)))[:, :2]; pc = (R @ X.T).T + t; gut = (pc[:, 2] > 0) & (np.linalg.norm(pc[:, :2] / pc[:, 2:3] - xn, axis=1) * f <= 4.0)
        G[im.camera_id].append((im.name, (X[gut], xn[gut], cv2.Rodrigues(R)[0], t.reshape(3, 1), f)) if gut.sum() >= 15 else (im.name, None))
    alle = np.array(alle); gr = float(np.linalg.norm(np.percentile(alle, 95, 0) - np.percentile(alle, 5, 0))) or 1.0; E = []
    for cid, L in G.items():
        D = [d for _, d in L if d is not None]; namen = [os.path.basename(n) for n, _ in L]
        if not D: E.append(dict(kamera=int(cid), bilder=namen, punkte=0, urteil="zu_wenig")); continue
        rms = np.zeros(len(KS)); C = np.zeros((len(KS), len(D), 3)); n_p = sum(len(d[0]) for d in D)
        for i, k in enumerate(KS):
            se = 0.0
            for j, (X, xn, rv, tv, f) in enumerate(D):
                ok, rv2, tv2 = cv2.solvePnP(X.astype(np.float64), (xn / k).astype(np.float64), np.eye(3), None, rv.copy(), tv.copy(), True, cv2.SOLVEPNP_ITERATIVE); R2 = cv2.Rodrigues(rv2)[0]
                pc = (R2 @ X.T).T + tv2.ravel(); se += float((np.linalg.norm(pc[:, :2] / pc[:, 2:3] - xn / k, axis=1) ** 2).sum()) * (f * k) ** 2; C[i, j] = -R2.T @ tv2.ravel()
            rms[i] = np.sqrt(se / n_p)
        m = int(np.argmin(rms)); gz = rms <= rms[m] * 1.10; lo = m
        while lo > 0 and gz[lo - 1]: lo -= 1
        hi = m
        while hi < len(KS) - 1 and gz[hi + 1]: hi += 1
        offen = lo == 0 or hi == len(KS) - 1; breite = float((KS[hi] / KS[lo] - 1) * 100 + (KS[1] / KS[0] - 1) * 100); spanne = float(np.median(np.linalg.norm(C[hi] - C[lo], axis=1)) / gr * 100)
        u = "unbestimmt" if offen or breite >= a.unbestimmt else ("weich" if breite >= a.weich else "scharf")
        E.append(dict(kamera=int(cid), bilder=namen, punkte=int(n_p), k_best=round(float(KS[m]), 3), rest_px=round(float(rms[m]), 2), breite_proz=round(breite, 1), offen=bool(offen), lage_spanne_proz=round(spanne, 2), urteil=u))
    z = collections.Counter(e["urteil"] for e in E); nb = collections.Counter()
    for e in E: nb[e["urteil"]] += len(e["bilder"])
    print(f"{len(E)} Kameras / {sum(nb.values())} Bilder: " + ", ".join(f"{k} {z[k]} Kameras ({nb[k]} Bilder)" for k in ("scharf", "weich", "unbestimmt", "zu_wenig")))
    q = lambda n: "video" if "vf_" in n else n.split("__")[0]; Q = collections.defaultdict(collections.Counter)
    for e in E: Q[q(e["bilder"][0])][e["urteil"]] += len(e["bilder"])
    for k, c in sorted(Q.items(), key=lambda t: -sum(t[1].values()))[:8]: print(f"  {k[:22]:22s} " + "  ".join(f"{u} {c[u]}" for u in ("scharf", "weich", "unbestimmt", "zu_wenig")))
    if a.aus: json.dump(dict(modell=a.modell, kameras=E), open(a.aus, "w"), indent=1)
    gesperrt = sorted({n for e in E if e["urteil"] in ("unbestimmt", "zu_wenig") for n in e["bilder"]})
    if a.liste: open(a.liste, "w").write("".join(n + "\n" for n in gesperrt))
    if a.sperrliste: n_alle, n_fremd = sperrliste_schreiben(a.sperrliste, gesperrt, a.vereinen); print(f"Sperrliste fuers Messen: {n_alle} Bilder ({len(gesperrt)} unbestimmt/zu wenig Punkte + {n_fremd} weitere aus {len(a.vereinen)} Liste(n)) -> {a.sperrliste}")
    return 0


def sperrliste_schreiben(ziel, namen, listen=()):
    """Sperrliste = namen VEREINIGT mit den Zeilen der vorhandenen Dateien in `listen` (z. B. konsens_arbeit/unstabil.txt) - die Quelllisten bleiben unveraendert.
    -> (Zahl gesamt, Zahl der Namen, die nur aus den anderen Listen kommen). Fehlende Dateien zaehlen als leer."""
    alle = set(namen)
    for p in listen:
        if os.path.isfile(p): alle |= {os.path.basename(z.strip()) for z in open(p) if z.strip()}
    open(ziel, "w").write("".join(n + "\n" for n in sorted(alle))); return len(alle), len(alle - set(namen))


if __name__ == "__main__": sys.exit(main())
