"""lage_gps_pruefen.py - Ausrichtung gegen das EXIF-GPS der eigenen Fotos pruefen (allgemein, je Objekt). Der Fit kennt das GPS nicht -> unabhaengiger Beleg.

Lehre Schwabentor 2026-11-14: Die LoD2-Ausrichtung lag 1,8-fach zu klein, 134 Grad verdreht und auf dem Nachbarhaus; der Wandfit allein war mehrdeutig.
Das GPS (Kamera-Median 29 m daneben; GPS-Fit Drehung 134-136 Grad, Massstab 1,84) und die Muensterturm-Fotos (178 statt 310 m) haetten es sofort gezeigt.

Eingang: objekt.json (rahmen), messprotokoll/SFM-AUSRICHTUNG-<name>.json (kameras.<foto>.standort im Modellsystem), Fotos aus objekt.json fotos_dir.
Optional --lage modul.py:funktion  = Korrekturfunktion X_modell -> X_modell (z. B. modelle/schwabentor/sfm/variante_i.py:lage_i) zum Pruefen einer Variante.
Pruefungen (Telefon-GPS streut in Gassen 10-30 m, darum nur grobe Fehler):
  1. Abstand Median(Kameras) <-> Median(GPS), nur Torfotos (GPS < --nah m vom Rahmen)  -> WARNUNG ab --max_abstand (15 m)
  2. Aehnlichkeitsfit Kamera -> GPS (getrimmt, Bootstrap): Drehung und Massstab; WARNUNG, wenn das 90-%-Band 0 Grad bzw. 1,0 ausschliesst
     UND |Drehung| > --max_dreh (15 Grad) bzw. |Massstab-1| > --max_skala (0,15)
  3. Fernfotos (GPS > --nah m): Entfernungsverhaeltnis GPS/Modell und Richtungsfehler (Massstab-/Drehhinweis mit langem Hebel)
Rueckgabe: 0 ok / zu wenig GPS (Hinweis), 3 = Lage widerspricht dem GPS. Ausgabe audit/lage_gps.json.
"""
import sys, os, json, glob, argparse, importlib.util
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
    namen, M, G = [], [], []
    for nr, k in kam.items():
        hit = [p for p in glob.glob(os.path.join(fd, nr + ".*")) + glob.glob(os.path.join(fd, nr + "_*")) if p.lower().endswith((".jpg", ".jpeg"))]   # Kaufhaus: 122 -> 122_<quelle>.jpg
        g = gps_exif(hit[0]) if hit else None
        if not g: continue
        namen.append(nr); M.append(k["standort"]); G.append(np.array(wgs84_zu_utm(*g)) - m0)
    erg = dict(werkzeug="lage_gps_pruefen.py", ausrichtung=a.ausrichtung, lage=a.lage or None, n_kameras=len(kam), n_gps=len(G))
    if len(G) < 10:
        print(f"HINWEIS: nur {len(G)} Fotos mit GPS - keine Pruefung"); erg["ergebnis"] = "zu wenig GPS"
        os.makedirs(os.path.join(od, "audit"), exist_ok=True); json.dump(erg, open(os.path.join(od, "audit", "lage_gps.json"), "w"), indent=1); return 0
    M = np.array(M, float)
    if korr is not None: M = np.asarray(korr(M), float)
    MU = M[:, 0:1] * xh + M[:, 1:2] * yh; G = np.array(G)                                   # Modell -> UTM relativ zur Rahmenmitte
    nah = np.hypot(*G.T) < a.nah; fern = ~nah
    warn = []
    d_med = float(np.hypot(*(np.median(MU[nah], 0) - np.median(G[nah], 0)))) if nah.sum() >= 5 else None
    if d_med is not None:
        print(f"1 Kamera-Median <-> GPS-Median (Torfotos, n {int(nah.sum())}): {d_med:.1f} m (Grenze {a.max_abstand})")
        if d_med > a.max_abstand: warn.append(f"Kamera-Median {d_med:.1f} m vom GPS-Median")
    w = np.ones(len(G), bool)
    for _ in range(5):
        s, R, t = fit2d(MU[w], G[w]); res = np.hypot(*(MU @ R.T * s + t - G).T); w = res < max(np.percentile(res, 80), 15)
    rng = np.random.default_rng(0); ys, ss = [], []
    iw = np.flatnonzero(w)
    for _ in range(400):
        i = rng.choice(iw, len(iw)); s_, R_, _ = fit2d(MU[i], G[i]); ys.append(winkel(R_)); ss.append(s_)
    yb = np.percentile(ys, [5, 50, 95]); sb = np.percentile(ss, [5, 50, 95])
    print(f"2 GPS-Fit: Drehung {winkel(R):.1f} Grad (90 %: {yb[0]:.1f} .. {yb[2]:.1f}), Massstab {s:.3f} (90 %: {sb[0]:.3f} .. {sb[2]:.3f}), Rest Median {np.median(res[w]):.1f} m")
    if (yb[0] > 0 or yb[2] < 0) and abs(yb[1]) > a.max_dreh: warn.append(f"Drehung {yb[1]:.0f} Grad gegen GPS")
    if (sb[0] > 1 or sb[2] < 1) and abs(sb[1] - 1) > a.max_skala: warn.append(f"Massstab {sb[1]:.2f} gegen GPS")
    fe = None
    if fern.sum() >= 3:
        rm = np.hypot(*MU[fern].T); rg = np.hypot(*G[fern].T)
        dw = (np.degrees(np.arctan2(MU[fern, 1], MU[fern, 0]) - np.arctan2(G[fern, 1], G[fern, 0])) + 180) % 360 - 180
        fe = dict(n=int(fern.sum()), entfernung_gps_durch_modell=float(np.median(rg / np.maximum(rm, 1e-6))), richtungsfehler_grad=float(np.median(dw)))
        print(f"3 Fernfotos (n {fe['n']}): Entfernung GPS/Modell {fe['entfernung_gps_durch_modell']:.2f}, Richtungsfehler {fe['richtungsfehler_grad']:.0f} Grad")
        if abs(fe["entfernung_gps_durch_modell"] - 1) > a.max_skala: warn.append(f"Fernfotos: Entfernung x{fe['entfernung_gps_durch_modell']:.2f}")
        if abs(fe["richtungsfehler_grad"]) > a.max_dreh: warn.append(f"Fernfotos: Richtung {fe['richtungsfehler_grad']:.0f} Grad daneben")
    erg.update(median_abstand_m=d_med, gps_fit=dict(drehung_grad=winkel(R), drehung_90=[float(yb[0]), float(yb[2])], massstab=float(s),
               massstab_90=[float(sb[0]), float(sb[2])], rest_median_m=float(np.median(res[w]))), fernfotos=fe, warnungen=warn)
    os.makedirs(os.path.join(od, "audit"), exist_ok=True); json.dump(erg, open(os.path.join(od, "audit", "lage_gps.json"), "w"), indent=1, ensure_ascii=False)
    if warn:
        print("WARNUNG: Lage widerspricht dem GPS: " + "; ".join(warn) + " - Ausrichtung pruefen (Zielgebaeude am Foto, Massstab), NICHT modellieren."); return 3
    print("Lage passt zum GPS."); return 0


if __name__ == "__main__":
    sys.exit(main())
