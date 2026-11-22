"""lage_gps_pruefen.py - Ausrichtung gegen das EXIF-GPS der eigenen Fotos pruefen (allgemein, je Objekt). Der Fit kennt das GPS nicht -> unabhaengiger Beleg.

Lehre Schwabentor 2026-11-14: Die LoD2-Ausrichtung lag 1,8-fach zu klein, 134 Grad verdreht und auf dem Nachbarhaus; der Wandfit allein war mehrdeutig.
Das GPS (Kamera-Median 29 m daneben; GPS-Fit Drehung 134-136 Grad, Massstab 1,84) und die Muensterturm-Fotos (178 statt 310 m) haetten es sofort gezeigt.

Eingang: objekt.json (rahmen), messprotokoll/SFM-AUSRICHTUNG-<name>.json (kameras.<foto>.standort im Modellsystem), Fotos aus objekt.json fotos_dir.
Optional --lage modul.py:funktion  = Korrekturfunktion X_modell -> X_modell (z. B. modelle/schwabentor/sfm/variante_i.py:lage_i) zum Pruefen einer Variante.
Pruefungen (Telefon-GPS streut in Gassen 10-30 m, darum nur grobe Fehler):
  1. Abstand Median(Kameras) <-> Median(GPS), nur Torfotos (GPS < --nah m vom Rahmen)  -> WARNUNG ab --max_abstand (15 m)
  2. Aehnlichkeitsfit Kamera -> GPS (getrimmt, Bootstrap): Drehung und Massstab; WARNUNG, wenn das 90-%-Band 0 Grad bzw. 1,0 ausschliesst
     UND |Drehung| > --max_dreh (15 Grad) bzw. |Massstab-1| > --max_skala (0,15)
  3. Fernfotos (GPS > --nah m): Entfernungsverhaeltnis GPS/Modell und Richtungsfehler (Massstab-/Drehhinweis mit langem Hebel) - nur Geotags, die unter dem freien
     Fit stimmen, gleiche Geotags = ein Beleg, ab 3 unabhaengigen Belegen (22.11.2026, fernfotos_pruefen)
Rueckgabe: 0 = passt ODER nicht geprueft (unter 10 GPS-Fotos; Hinweis), 3 = Lage widerspricht dem GPS, 4 = Fotos nicht gefunden. Ausgabe audit/lage_gps.json.
17.11.2026 (Durchsicht): "zu wenig GPS" war am rc nicht von "passt" zu unterscheiden. Der rc bleibt 0 (sonst koennte kein Objekt ohne GPS-Fotos - Commons, Video - je die Lage-Tore
der Kette bestehen), aber: Ausgabezeile "NICHT GEPRUEFT (GPS-Tor)" und in lage_gps.json `geprueft: false`, `ergebnis: "nicht geprueft: ..."`; bei einem Urteil `geprueft: true`.
Wer den Lagebeleg braucht, liest `geprueft` - rc 0 allein ist KEIN unabhaengiger Beleg der Lage.
Aufruf: /media/oem/scan/venv-seg/bin/python -I tools/lage_gps_pruefen.py modelle/<objekt>/objekt.json modelle/<objekt>/messprotokoll/SFM-AUSRICHTUNG-<name>.json
        [--fotos DIR] [--lage modul.py:funktion] [--nah 100] [--max_abstand 15] [--max_dreh 15] [--max_skala 0.15]   (oder `tools/py tools/lage_gps_pruefen.py ...`)
"""
import math, sys, os, json, glob, argparse, importlib.util
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gps_ausrichtung import gps_exif
from bilder_holen import wgs84_zu_utm


def fit2d(a, b):
    """Aehnlichkeit b ~ s R a + t (2D, ohne Spiegelung)."""
    ma, mb = a.mean(0), b.mean(0); a0, b0 = a - ma, b - mb; U, S, Vt = np.linalg.svd(a0.T @ b0)
    d = np.sign(np.linalg.det(Vt.T @ U.T)); D = np.diag([1, d]); R = Vt.T @ D @ U.T
    s = (S * np.diag(D)).sum() / max((a0 ** 2).sum(), 1e-12); return s, R, mb - s * R @ ma


def winkel(R): return float(np.degrees(np.arctan2(R[1, 0], R[0, 0])))


FERN_REST_M, FERN_REST_REL, FERN_MIN_N, GPS_GLEICH_M = 10.0, 0.10, 3, 0.5


def fernfotos_pruefen(MU, G, s, R, t, fern, namen, max_skala, max_dreh, warn):
    """Pruefung 3 (langer Hebel): Entfernungsverhaeltnis GPS/Modell und Richtungsfehler der Fernfotos (GPS > --nah m), aber NUR mit Geotags, die zur Kamerageometrie
    des Modells passen. 22.11.2026 (schwabentor-1122, vereinte Seiten 0+1, GPS-Fit +8 Grad x1,09 innerhalb der Grenzen): das Tor fiel allein an 'Fernfotos (n 5):
    x4,45, 22 Grad' durch. Die 5 waren: eigen__IMG_20261106_113015/17/18/19 - VIER Fotos mit DEMSELBEN Geotag 272 m entfernt (Handy-GPS eingefroren/alter Fix), waehrend
    113025-033 Sekunden spaeter vom selben Standort 72-79 m melden und das Modell alle bei 61 m fuehrt; und eigen__od_08 (GPS 1,9 km, Kamera im Modell 75 km weit, z 34 km
    = falsch registrierte Kamera). Kein einziges davon war ein Lagebeleg; der robuste Konsens-Fit hatte sie schon als falsche Geotags verworfen, Pruefung 3 nahm sie trotzdem.
    Jetzt: ein Fernfoto zaehlt nur, wenn sein GPS unter dem FREIEN Aehnlichkeitsfit (s, R, t aus Pruefung 2) passt (Rest < max(10 m, 10 % der GPS-Entfernung)).
    Diese Auswahl ist von der zu pruefenden Ausrichtung UNABHAENGIG (freier Fit: eine falsch gedrehte/skalierte Lage aendert die Reste nicht) - eine falsche Lage faellt
    darum weiter durch, wenn stimmige Fernfotos da sind. Gleiche Geotags (< 0,5 m) zaehlen als EIN Beleg; unter 3 unabhaengigen Belegen: kein Urteil (Hinweis),
    dann entscheidet Pruefung 2. Grenzen (max_skala, max_dreh) UNVERAENDERT. Rueckgabe dict fuer lage_gps.json (oder None ohne Fernfotos); haengt Warnungen an warn."""
    if fern.sum() == 0: return None
    rg = np.hypot(*G.T); rest = np.hypot(*(MU @ R.T * s + t - G).T)
    stimmig = fern & (rest < np.maximum(FERN_REST_M, FERN_REST_REL * rg))
    verworfen = [dict(foto=namen[i], gps_m=round(float(rg[i]), 1), modell_m=round(float(np.hypot(*MU[i])), 1), rest_freier_fit_m=round(float(rest[i]), 1),
                      gleicher_geotag=int((np.hypot(*(G - G[i]).T) < GPS_GLEICH_M).sum())) for i in np.flatnonzero(fern & ~stimmig)]
    gruppen = {}                                                                         # gleicher Geotag = ein Beleg (Serie am selben Fix)
    for i in np.flatnonzero(stimmig): gruppen.setdefault(tuple(np.round(G[i] / GPS_GLEICH_M).astype(int)), []).append(i)
    fe = dict(n=int(fern.sum()), n_stimmig=int(stimmig.sum()), n_unabhaengig=len(gruppen), verworfen=verworfen, bewertet=False)
    if verworfen: print(f"   Fernfotos verworfen ({len(verworfen)}, GPS passt nicht zur Kamerageometrie - falscher Geotag oder falsch registrierte Kamera): "
                        + ", ".join(f"{v['foto']} (GPS {v['gps_m']:.0f} m, Modell {v['modell_m']:.0f} m, {v['gleicher_geotag']}x gleicher Geotag)" for v in verworfen[:6]))
    if len(gruppen) < FERN_MIN_N:
        print(f"3 Fernfotos (n {fe['n']}, stimmig {fe['n_stimmig']}, unabhaengig {len(gruppen)} < {FERN_MIN_N}): kein Urteil mit langem Hebel - Pruefung 2 entscheidet"); return fe
    q, d = [], []
    for ix in gruppen.values():
        ix = np.array(ix); rm = np.hypot(*MU[ix].T)
        q.append(np.median(rg[ix] / np.maximum(rm, 1e-6)))
        d.append(np.median((np.degrees(np.arctan2(MU[ix, 1], MU[ix, 0]) - np.arctan2(G[ix, 1], G[ix, 0])) + 180) % 360 - 180))
    fe.update(bewertet=True, entfernung_gps_durch_modell=float(np.median(q)), richtungsfehler_grad=float(np.median(d)))
    print(f"3 Fernfotos (n {fe['n']}, stimmig {fe['n_stimmig']}, unabhaengig {len(gruppen)}): Entfernung GPS/Modell {fe['entfernung_gps_durch_modell']:.2f}, Richtungsfehler {fe['richtungsfehler_grad']:.0f} Grad")
    if abs(fe["entfernung_gps_durch_modell"] - 1) > max_skala: warn.append(f"Fernfotos: Entfernung x{fe['entfernung_gps_durch_modell']:.2f}")
    if abs(fe["richtungsfehler_grad"]) > max_dreh: warn.append(f"Fernfotos: Richtung {fe['richtungsfehler_grad']:.0f} Grad daneben")
    return fe


def urteil(namen, MU, G, nah_m=100.0, max_abstand=15.0, max_dreh=15.0, max_skala=0.15):
    """Lage-Urteil aus Kamerastandorten MU (UTM relativ zur Rahmenmitte, n x 2) und Foto-GPS G (gleiches System): (rc 0/3, dict fuer lage_gps.json). Ohne Datei-IO (testbar)."""
    erg = {}
    nah = np.hypot(*G.T) < nah_m; fern = ~nah
    warn = []
    d_med = float(np.hypot(*(np.median(MU[nah], 0) - np.median(G[nah], 0)))) if nah.sum() >= 5 else None
    if d_med is not None:
        print(f"1 Kamera-Median <-> GPS-Median (Torfotos, n {int(nah.sum())}): {d_med:.1f} m (Grenze {max_abstand})")
        if d_med > max_abstand: warn.append(f"Kamera-Median {d_med:.1f} m vom GPS-Median")
    _dm = np.hypot(*(MU - np.median(MU, 0)).T); w = _dm <= np.percentile(_dm, 75)   # 15.11.: Start nur mit dem Kamerakern - einzelne km-weit versetzte Kameras (globaler Mapper) kippten den Fit (Drehung -140 Grad, Massstab 0,016 bei richtiger Lage)
    for _ in range(5):
        if w.sum() < 3 or not np.isfinite(MU[w]).all():                       # 15.11.: Absturz (SVD) statt Urteil bei entarteter Lage -> als Widerspruch werten
            print("WARNUNG: GPS-Fit nicht moeglich (zu wenige vertraegliche Kameras) - Lage widerspricht dem GPS"); erg["ergebnis"] = "fit nicht moeglich"; erg["geprueft"] = True
            return 3, erg
        try: s, R, t = fit2d(MU[w], G[w])
        except np.linalg.LinAlgError:
            print("WARNUNG: GPS-Fit konvergiert nicht - Lage widerspricht dem GPS"); erg["ergebnis"] = "fit konvergiert nicht"; erg["geprueft"] = True      # 17.11.2026: hier blieb die lage_gps.json eines frueheren Laufs liegen
            return 3, erg
        res = np.hypot(*(MU @ R.T * s + t - G).T); w = res < max(np.percentile(res, 80), 15)
    # 18.11.2026 (Kaufhaus gk2h: 42 von 110 Geotags falsch - alte/Commons-Fotos; das 80-%-Trimmen liess sie im Fit -> Massstab 0,80, obwohl 68 Fotos mit 2,4 m Rest passen):
    # robuster Konsens-Fit (RANSAC, Inlier < 10 m); gilt, wenn >= 40 % und >= 10 Fotos zustimmen, sonst bleibt der getrimmte Fit. Grenzen (max_dreh, max_skala) UNVERAENDERT.
    rng = np.random.default_rng(0); best = None; n_ = len(G)
    for _ in range(3000):
        i3 = rng.choice(n_, 2, replace=False)
        if np.hypot(*(G[i3[0]] - G[i3[1]])) < 10 or np.hypot(*(MU[i3[0]] - MU[i3[1]])) < 1e-6: continue
        try: s_, R_, t_ = fit2d(MU[i3], G[i3])
        except np.linalg.LinAlgError: continue
        inl = np.hypot(*(MU @ R_.T * s_ + t_ - G).T) < 10.0
        if best is None or inl.sum() > best.sum(): best = inl
    erg["ransac"] = None
    if best is not None and best.sum() >= max(10, 0.4 * n_):
        for _ in range(3): s, R, t = fit2d(MU[best], G[best]); res = np.hypot(*(MU @ R.T * s + t - G).T); best = res < 10.0
        if best.sum() >= max(10, 0.4 * n_):
            w = best; erg["ransac"] = dict(inlier=int(best.sum()), von=int(n_)); print(f"   robuster Konsens-Fit: {int(best.sum())} von {n_} Geotags stimmen ueberein (< 10 m) - die anderen gelten als falsche Geotags")
    s, R, t = fit2d(MU[w], G[w]); res = np.hypot(*(MU @ R.T * s + t - G).T)
    ys, ss = [], []
    iw = np.flatnonzero(w)
    for _ in range(400):
        i = rng.choice(iw, len(iw)); s_, R_, _ = fit2d(MU[i], G[i]); ys.append(winkel(R_)); ss.append(s_)
    yb = np.percentile(ys, [5, 50, 95]); sb = np.percentile(ss, [5, 50, 95])
    print(f"2 GPS-Fit: Drehung {winkel(R):.1f} Grad (90 %: {yb[0]:.1f} .. {yb[2]:.1f}), Massstab {s:.3f} (90 %: {sb[0]:.3f} .. {sb[2]:.3f}), Rest Median {np.median(res[w]):.1f} m")
    if (yb[0] > 0 or yb[2] < 0) and abs(yb[1]) > max_dreh: warn.append(f"Drehung {yb[1]:.0f} Grad gegen GPS")
    if (sb[0] > 1 or sb[2] < 1) and abs(sb[1] - 1) > max_skala: warn.append(f"Massstab {sb[1]:.2f} gegen GPS")
    fe = fernfotos_pruefen(MU, G, s, R, t, fern, namen, max_skala, max_dreh, warn)
    erg.update(geprueft=True, median_abstand_m=d_med, gps_fit=dict(drehung_grad=winkel(R), drehung_90=[float(yb[0]), float(yb[2])], massstab=float(s),
               massstab_90=[float(sb[0]), float(sb[2])], rest_median_m=float(np.median(res[w]))), fernfotos=fe, warnungen=warn)
    if warn:
        print("WARNUNG: Lage widerspricht dem GPS: " + "; ".join(warn) + " - Ausrichtung pruefen (Zielgebaeude am Foto, Massstab), NICHT modellieren."); return 3, erg
    print("Lage passt zum GPS."); return 0, erg


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("objekt"); ap.add_argument("ausrichtung", help="messprotokoll/SFM-AUSRICHTUNG-<name>.json")
    ap.add_argument("--fotos", default="", help="Fotoordner (Standard objekt.json fotos_dir)")
    ap.add_argument("--lage", default="", help="modul.py:funktion - Korrektur der Modellkoordinaten pruefen")
    ap.add_argument("--nah", type=float, default=100.0); ap.add_argument("--max_abstand", type=float, default=15.0)
    ap.add_argument("--max_dreh", type=float, default=15.0); ap.add_argument("--max_skala", type=float, default=0.15)
    a = ap.parse_args()
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    obj = json.load(open(a.objekt)); od = os.path.dirname(os.path.abspath(a.objekt)); r = obj["rahmen"]
    m0 = np.array(r["mitte_utm"], float); xh = np.array(r["xhat_utm"], float); yh = np.array(r["yhat_utm"], float)
    fd = a.fotos or obj.get("fotos_dir", ""); fd = fd if os.path.isabs(fd) else os.path.join(repo, fd)
    kam = json.load(open(a.ausrichtung))["kameras"]
    korr = None
    if a.lage:
        pf, fn = a.lage.split(":"); sp = importlib.util.spec_from_file_location("lage_mod", pf); md = importlib.util.module_from_spec(sp)
        sys.path.insert(0, os.path.dirname(os.path.abspath(pf))); sp.loader.exec_module(md); korr = getattr(md, fn)
    namen, M, G = [], [], []; gefunden = 0
    for nr, k in kam.items():
        kand = [nr] + ([nr.split("__", 1)[1]] if "__" in nr else [])          # 15.11.: Gesamtkette benennt eigen__IMG_... (Quellpraefix) -> auch ohne Praefix suchen
        hit = [p for n_ in kand for p in glob.glob(os.path.join(fd, glob.escape(n_) + ".*")) + glob.glob(os.path.join(fd, glob.escape(n_) + "_*")) + glob.glob(os.path.join(fd, "*__" + glob.escape(n_) + ".*"))
               if p.lower().endswith((".jpg", ".jpeg"))]   # Kaufhaus: 122 -> 122_<quelle>.jpg
        gefunden += bool(hit); g = gps_exif(hit[0]) if hit else None
        if not g: continue
        try:
            if not all(math.isfinite(float(x)) for x in g) or (abs(float(g[0])) < 1e-6 and abs(float(g[1])) < 1e-6): continue   # 15.11. Kaufhaus: EXIF-GPS NaN/0,0 liess den Fit abstuerzen
        except Exception: continue
        namen.append(nr); M.append(k["standort"]); G.append(np.array(wgs84_zu_utm(*g)) - m0)
    erg = dict(werkzeug="lage_gps_pruefen.py", ausrichtung=a.ausrichtung, lage=a.lage or None, n_kameras=len(kam), n_gps=len(G))
    if len(G) < 10:
        erg["fotos_gefunden"] = gefunden
        if gefunden < 0.5 * len(kam):                                          # 15.11.: Tor bestand STUMM, weil die Fotos nicht gefunden wurden (v2: 0 von 494) -> laut scheitern
            print(f"FEHLER: nur {gefunden} von {len(kam)} Kamerafotos in {fd} gefunden - GPS-Tor NICHT geprueft (--fotos setzen)"); erg["ergebnis"] = "fotos nicht gefunden"; erg["geprueft"] = False
            os.makedirs(os.path.join(od, "audit"), exist_ok=True); json.dump(erg, open(os.path.join(od, "audit", "lage_gps.json"), "w"), indent=1); return 4
        print(f"NICHT GEPRUEFT (GPS-Tor): nur {len(G)} Fotos mit GPS ({gefunden} Fotos gefunden, Rest ohne GPS-EXIF; noetig 10) - KEIN Urteil ueber die Lage, das ist kein 'bestanden' (rc 0 nur als Hinweis)"); erg["ergebnis"] = "nicht geprueft: zu wenig GPS"; erg["geprueft"] = False
        os.makedirs(os.path.join(od, "audit"), exist_ok=True); json.dump(erg, open(os.path.join(od, "audit", "lage_gps.json"), "w"), indent=1); return 0
    M = np.array(M, float)
    if korr is not None: M = np.asarray(korr(M), float)
    MU = M[:, 0:1] * xh + M[:, 1:2] * yh; G = np.array(G)                                   # Modell -> UTM relativ zur Rahmenmitte
    rc, teil = urteil(namen, MU, G, a.nah, a.max_abstand, a.max_dreh, a.max_skala); erg.update(teil)
    os.makedirs(os.path.join(od, "audit"), exist_ok=True); json.dump(erg, open(os.path.join(od, "audit", "lage_gps.json"), "w"), indent=1, ensure_ascii=False)
    return rc


if __name__ == "__main__":
    sys.exit(main())
