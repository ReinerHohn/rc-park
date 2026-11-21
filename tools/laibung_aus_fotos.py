#!/usr/bin/env python3
"""laibung_aus_fotos.py - LAIBUNGSTIEFE von Fenstern aus der seitlich sichtbaren Laibung in Schraegfotos (21.11.2026 spaet, Kettenstufe 'bauplan' nach nischen_fenster).

Anlass (Schwabentor f00, Nutzer/Koordinator: "im Foto 113231 dunkle, tief zurueckliegende Oeffnungen, im Modell feine Rillen"): der Ebenen-Sweep misst im Fenster
nichts (Laden ohne Textur: 70 % der 'guten' Zellen +1,8..+2,4 m VOR der Wand; ausserdem endet sein Bereich 0,4 m hinter der Wand), darum stand dort ANNAHME 0,12 m.
GEOMETRIE (KERNMETHODE: Masse aus Fotokanten + SfM-Kameras, >= 3 Fotos): das Einzelfoto-Ortho (fassade_ortho --einzeln) legt jedes Foto auf die Modellflaeche s(u,z)
(relief_fNN.png). Ein Wandpunkt u in der Oeffnung zeigt, was der Kamerastrahl dahinter trifft: den Laden (Ebene w = -T) oder - auf der von der Kamera ABGEWANDTEN
Seite - die Laibung. Die Ladenkante b erscheint im Ortho bei
      u_obs = b - k (T + s),   k = (u_kante - C_u) / C_w   (C = Kamerazentrum in Wandkoordinaten, s < 0 = Modellflaeche hinter der Wand)
also  y := u_obs + k s = b - k T  ->  Gerade in k, Steigung -T (genutzt EXAKT ohne Cw >> T: Y = C_u + kappa C_w = b - kappa T, kappa = (u_obs - C_u)/(C_w - s)). Je Foto: Kante = staerkster Hell-Dunkel-Sprung (Median ueber die Zeilen zwischen Sohlbank+0,3 und
Kaempfer-0,1) auf der abgewandten Seite (k > 0: rechts, dunkel -> hell; k < 0: links). Gemeinsame Ausgleichsgerade (T gemeinsam, Hinterkante je Seite),
zwei Runden Ausreisser > 3 MAD (mind. 3 cm) heraus, Bootstrap-Streuung.
22.11.2026 (Kettenlauf 1121v, KREISFALL): die Einzelfoto-Orthos liegen auf dem Modell des vorigen Laufs; hat das den Fensterkasten schon, klebt die Kante an dessen
Naht (T 4,68 statt 0,8). Darum Vorrang: das Suchfeld wird DIREKT aus dem Foto auf eine flache Ebene abgetastet (foto_feld; Sichtpruefung aus dem Einzelortho ausserhalb
des Kastens), das Ortho ist nur Rueckfall (--ohne_foto erzwingt ihn). Test: tools/test_kette_kreis_orthos.py.
Gilt nur mit >= --min_fotos Fotos, k-Spanne >= --k_spanne, 0 < T < 3 m und Streuung <= 25 % von T; sonst bleibt der Eintrag unveraendert.
Ausgabe: fenster_auto.json (je gemessenem Fenster 'laibung' {tiefe_ab_wand, fotos, k_spanne, streuung} und 'tiefe' = Laibung ab Nischengrund bzw. Wand,
'tiefe_quelle'), Bericht laibung_aus_fotos.json, Bild laibung_<fid>.jpg (y gegen k je Fenster).
Aufruf: laibung_aus_fotos.py <fenster_auto.json> <fassade_fein-ordner> <objekt.json> [--nur f00] [--aus ordner]
rc 0 = mindestens ein Fenster gemessen, 3 = keins (nichts geaendert).
"""
import sys, os, json, glob, argparse, numpy as np


def kamera_zentrum(K):
    """Kamerazentrum (Modellrahmen) aus einer K-Datei (foto_mass/foto_kalibrieren: rvec, t) - wie fassade_ortho (Cw = -R^T t - rahmen_verschiebung)."""
    import cv2
    R, _ = cv2.Rodrigues(np.array(K["rvec"], float)); return -R.T @ np.array(K["t"], float) - np.asarray(K.get("rahmen_verschiebung", [0, 0, 0]), float)


def bereich(q, k_sign, zk):
    """Suchfeld (ua, ue, za, ze) fuer die Ladenkante auf der von der Kamera abgewandten Seite oder None."""
    za, ze = q["z0"] + 0.3, zk - 0.1
    if ze - za < 0.2: return None
    ua, ue = (q["u0"] + 0.02, q["u1"] + 0.25) if k_sign > 0 else (q["u0"] - 0.25, q["u1"] - 0.02)   # ganze Breite: bei starker Schraege wandert die Kante ueber die Mitte
    return ua, ue, za, ze


def kante_im_feld(A, ua, c, k_sign, R=None):
    """Staerkster Dunkel->Hell-Sprung nach aussen im Feld A (Zeilen z absteigend, Spalten u ab ua; 0 = kein Foto). R = Relief im selben Feld (mm + 10 m) oder None.
    Liefert (u_obs, Spalte, staerke) oder None. 22.11.2026 (Kettenlauf 1121v): Pixel nahe 'kein Foto' (schwarzer Verdeckungsstreifen hinter der Modell-Laibung)
    und Spalten an Relief-Stufen (Projektionsnaht am schon gebauten Fensterkasten) sind keine Kanten - beide gaben dort den staerksten Sprung (T 4,68 m)."""
    from scipy import ndimage as ndi
    import warnings
    A = A.astype(np.float32); leer = ndi.binary_dilation(A == 0, iterations=5)
    if (~leer).mean() < 0.5: return None
    gr = ndi.gaussian_filter1d(ndi.gaussian_filter(A, 1.5), 1.0, axis=1, order=1) * k_sign     # dunkel -> hell nach aussen
    gr[leer] = np.nan
    if R is not None and R.shape == A.shape:
        R = R.astype(np.float32); R[R == 0] = np.nan
        with np.errstate(invalid="ignore"): stufe = np.abs(np.diff(R, axis=1)) > 20.0            # > 2 cm Modellsprung zwischen Nachbarspalten
        naht = np.zeros(A.shape, bool); naht[:, 1:] |= stufe; naht[:, :-1] |= stufe
        gr[ndi.binary_dilation(naht, structure=np.ones((1, 7), bool))] = np.nan                  # +-3 Pixel um die Naht
    ok = np.isfinite(gr).sum(axis=0) >= max(3, 0.3 * gr.shape[0])                                 # Spalte braucht genug gueltige Zeilen
    if not ok.any(): return None
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning); p = np.nanmedian(gr, axis=0)
    p[~ok] = np.nan
    if not np.isfinite(p).any(): return None
    j = int(np.nanargmax(p)); return ua + (j + 0.5) * c, j, float(p[j])


def kante_messen(g, rel, rast, q, k_sign, zk):
    """Ladenkante im Einzelfoto-Ortho g (Graubild, 0 = kein Foto) auf der von der Kamera abgewandten Seite. Liefert (u_obs, s_dort, staerke) oder None.
    NUR Rueckfall: liegt das Ortho auf einem Modell, das den Fensterkasten schon hat, fehlt der Bildstreifen der Modell-Laibung (siehe foto_feld)."""
    u0, z1, c = rast; b = bereich(q, k_sign, zk)
    if b is None: return None
    ua, ue, za, ze = b
    i0, i1 = int(round((z1 - ze) / c)), int(round((z1 - za) / c)); j0, j1 = int(round((ua - u0) / c)), int(round((ue - u0) / c))
    if i0 < 0 or j0 < 0 or i1 > g.shape[0] or j1 > g.shape[1]: return None
    Rf = rel[i0:i1, j0:j1] if rel is not None and rel.shape[:2] == g.shape[:2] else None
    r = kante_im_feld(g[i0:i1, j0:j1], ua, c, k_sign, Rf)
    if r is None: return None
    u_obs, j, st = r; s = 0.0
    if rel is not None:
        R_ = rel[i0:i1, j0 + max(j - 2, 0):j0 + j + 3]; R_ = R_[R_ > 0]
        if R_.size: s = float(np.median(R_)) / 1000.0 - 10.0
    return u_obs, s, st


def foto_feld(im, kk, geo, b, c, s_ref):
    """22.11.2026: Suchfeld b = (ua, ue, za, ze) DIREKT aus dem Foto (Graubild im) auf die flache Ebene w = s_ref abgetastet (Lochkamera + k1 wie fassade_ortho).
    Grund (Kettenlauf 1121v): das Einzelfoto-Ortho der Kette liegt auf dem Modell des VORIGEN Laufs; hat das den Fensterkasten schon (Relief -0,54 statt -0,15),
    faellt der Bildstreifen der Modell-Laibung aus dem Ortho und die Ladenkante klebt an der Kastenkante - die Messung haengt vom eigenen Vorergebnis ab (Kreis).
    Auf einer Ebene ist jeder Pixel ein Strahl; die Formel Y = C_u + kappa C_w bleibt exakt (s = s_ref). Rueckgabe Feld (0 = ausserhalb des Fotos) oder None."""
    import cv2
    o, d, n = geo; ua, ue, za, ze = b
    uu = ua + c * (np.arange(int(round((ue - ua) / c))) + 0.5); zz = ze - c * (np.arange(int(round((ze - za) / c))) + 0.5)
    U, Z = np.meshgrid(uu, zz); xy = o[None, None, :] + U[..., None] * d + s_ref * n
    X = np.dstack([xy, Z]).reshape(-1, 3) + np.asarray(kk.get("rahmen_verschiebung", [0, 0, 0]), float)
    R, _ = cv2.Rodrigues(np.array(kk["rvec"], float)); Xc = X @ R.T + np.array(kk["t"], float); z = Xc[:, 2]
    if (z <= 1).any(): return None
    H, W = im.shape[:2]; f = float(kk["f_px"]); cx, cy = float(kk.get("cx", W / 2)), float(kk.get("cy", H / 2)); k1 = float(kk.get("k1") or 0.0)
    xn, yn = Xc[:, 0] / z, Xc[:, 1] / z; sk = 1 + k1 * (xn * xn + yn * yn); px, py = f * xn * sk + cx, f * yn * sk + cy
    mpp = float(np.median(z)) / f; sig = min(0.4 * c / max(mpp, 1e-4), 6.0)                          # Zelle groesser als Fotopixel -> vorher glaetten (wie fassade_ortho)
    x0, x1, y0, y1 = int(max(px.min() - 3 * sig - 2, 0)), int(min(px.max() + 3 * sig + 3, W)), int(max(py.min() - 3 * sig - 2, 0)), int(min(py.max() + 3 * sig + 3, H))
    if x1 - x0 < 4 or y1 - y0 < 4: return None
    S = im[y0:y1, x0:x1].astype(np.float32)
    if sig >= 1.0: S = cv2.GaussianBlur(S, (0, 0), sig)
    m = (px >= 0) & (px <= W - 1) & (py >= 0) & (py <= H - 1)
    v = cv2.remap(S, (px - x0).reshape(U.shape).astype(np.float32), (py - y0).reshape(U.shape).astype(np.float32), cv2.INTER_LINEAR)
    v = np.clip(v, 1, 255); v[~m.reshape(U.shape)] = 0; return v.astype(np.uint8)


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def foto_datei(obj, name, objekt_pfad=None):
    """Fotodatei wie fassade_ortho (<fotos_dir>/<name>.* oder <name>_*) oder None; fotos_dir relativ zum Repo des Werkzeugs bzw. des Objekts (modelle/<obj>/objekt.json)."""
    fd = obj.get("fotos_dir") if isinstance(obj, dict) else None
    if not fd: return None
    wurzeln = [ROOT] + ([os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(objekt_pfad))))] if objekt_pfad else [])
    for w in wurzeln:
        pf = sorted(glob.glob(os.path.join(w, fd, name + ".*")) or glob.glob(os.path.join(w, fd, name + "_*")))
        if pf: return pf[0]
    return None


def ring_s(rel, rast, q):
    """Bezugsebene s_ref fuer foto_feld: Median der Modellflaeche im Ring um den Fensterkasten (0 ohne Relief). Jede Ebene ist geometrisch gleich gut (Strahl), der Ring nur fuer die Sicht."""
    if rel is None: return 0.0
    u0, z1, c = rast; i0, i1 = max(int((z1 - q["z1"]) / c), 0), max(int((z1 - q["z0"]) / c), 0); j0, j1 = max(int((q["u0"] - 0.3 - u0) / c), 0), max(int((q["u1"] + 0.3 - u0) / c), 0)
    R = rel[i0:i1, j0:j1].astype(np.float32)
    if R.size == 0: return 0.0
    uu = u0 + c * (np.arange(j0, j0 + R.shape[1]) + 0.5); ring = (uu < q["u0"] - 0.05) | (uu > q["u1"] + 0.05); v = R[:, ring]; v = v[v > 0]
    return round(float(np.median(v)) / 1000.0 - 10.0, 3) if v.size else 0.0


def verdeckt(g, rast, q, b, max_leer=0.2):
    """Sichtpruefung aus dem Einzelfoto-Ortho (Sichtbarkeit gegen das Modell, Nachbarn): im Ring AUSSERHALB des Fensterkastens > 20 % 'kein Foto' -> verdeckt.
    Innerhalb des Kastens zaehlt Schwarz nicht (das ist nur die Modell-Laibung des vorigen Baus)."""
    u0, z1, c = rast; ua, ue, za, ze = b
    i0, i1 = int(round((z1 - ze) / c)), int(round((z1 - za) / c)); j0, j1 = int(round((ua - u0) / c)), int(round((ue - u0) / c))
    if i0 < 0 or j0 < 0 or i1 > g.shape[0] or j1 > g.shape[1]: return True
    uu = ua + c * (np.arange(j1 - j0) + 0.5); ring = (uu < q["u0"] - 0.05) | (uu > q["u1"] + 0.05)
    if not ring.any(): return False
    return float((g[i0:i1, j0:j1][:, ring] == 0).mean()) > max_leer


def seite_k(q, Cu, Cw):
    """(Vorzeichen der abgewandten Seite, k) oder None (Kamera vor dem Fenster / zu nah)."""
    if Cw < 2.0: return None
    k_r, k_l = (q["u1"] - Cu) / Cw, (q["u0"] - Cu) / Cw
    if k_r > 0 and k_l > 0: return 1, k_r
    if k_r < 0 and k_l < 0: return -1, k_l
    return None                                                              # Kamera vor dem Fenster: beide Laibungen verdeckt/klein


def fenster_messen(bilder, kam, rel, rast, q, a, felder=None):
    """Alle Fotos fuer ein Fenster q -> dict(tiefe_ab_wand, fotos, k_spanne, streuung, punkte) oder dict(fehler).
    felder: {foto: (Feld, ua, s_ref)} aus foto_feld (Vorrang, unabhaengig vom gebauten Modell); sonst Rueckfall Einzelfoto-Ortho."""
    zk = (q.get("bogen") or {}).get("kaempfer") or q["z1"]; P = []; felder = felder or {}
    for name, g in bilder:
        if name not in kam: continue
        Cu, Cw = kam[name]; sk = seite_k(q, Cu, Cw)
        if sk is None: continue
        sg, k = sk
        if name in felder:
            A_, ua_, s_ref = felder[name]; r = kante_im_feld(A_, ua_, rast[2], sg); r = None if r is None else (r[0], s_ref, r[2]); qu = "foto"
        else: r = kante_messen(g, rel, rast, q, sg, zk); qu = "ortho"
        if r is None: continue
        P.append(dict(foto=name, seite="rechts" if sg > 0 else "links", k=round(k, 4), u_obs=round(r[0], 3), s=round(r[1], 3), staerke=round(r[2], 2), quelle=qu))
    if not P: return dict(fehler="kein Foto zeigt eine Laibung", punkte=[])
    st = np.array([p["staerke"] for p in P]); P = [p for p in P if p["staerke"] >= a.staerke_rel * np.median(st)]
    for p in P:                                                              # EXAKT (ohne Naeherung Cw >> T): Y = C_u + kappa C_w = b_seite - kappa T, kappa = (u_obs - C_u)/(C_w - s)
        Cu, Cw = kam[p["foto"]]; ka = (p["u_obs"] - Cu) / (Cw - p["s"]); p["kappa"] = round(ka, 5); p["Y"] = round(Cu + ka * Cw, 4)
    seiten = [x for x in ("rechts", "links") if sum(p["seite"] == x for p in P) >= 2]
    Q = [p for p in P if p["seite"] in seiten]
    if len(Q) < a.min_fotos or not seiten: return dict(fehler=f"weniger als {a.min_fotos} Fotos mit Laibung", punkte=P)
    ka = np.array([p["kappa"] for p in Q]); Y = np.array([p["Y"] for p in Q]); S = np.array([seiten.index(p["seite"]) for p in Q])
    if max(np.ptp(np.abs(ka[S == i])) for i in range(len(seiten))) < a.k_spanne: return dict(fehler=f"Blickschraege-Spanne < {a.k_spanne}", punkte=P)

    def fit(m):                                                              # gemeinsame Tiefe T, je Seite eigene Hinterkante b
        A = np.column_stack([-ka[m]] + [(S[m] == i).astype(float) for i in range(len(seiten))]); x, *_ = np.linalg.lstsq(A, Y[m], rcond=None); return x, Y - np.column_stack([-ka] + [(S == i).astype(float) for i in range(len(seiten))]) @ x
    m = np.ones(len(Q), bool); x, r = fit(m)
    for _ in range(2):                                                       # Ausreisser (Kabel, Naht, falsche Kante): > 3 x MAD, mindestens 3 cm
        mad = float(np.median(np.abs(r[m]))); m2 = np.abs(r) <= max(3 * 1.4826 * mad, 0.03)
        if m2.sum() < a.min_fotos or (m2 == m).all(): break
        m = m2; x, r = fit(m)
    rng = np.random.default_rng(0); bs = []; idx = np.flatnonzero(m)
    for _ in range(200):
        i_ = rng.choice(idx, len(idx)); mm = np.zeros(len(Q), bool); mm[i_] = True
        if all((S[mm] == i).any() for i in range(len(seiten))) and mm.sum() >= 2: bs.append(fit(mm)[0][0])
    best = dict(seite="+".join(seiten), tiefe_ab_wand=round(float(x[0]), 3), kante_hinten={sd: round(float(x[1 + i]), 3) for i, sd in enumerate(seiten)}, fotos=int(m.sum()),
                ausreisser=[Q[i]["foto"] for i in np.flatnonzero(~m)], k_spanne=[round(float(np.abs(ka[m]).min()), 3), round(float(np.abs(ka[m]).max()), 3)],
                streuung=round(float(np.std(bs)), 3) if bs else None, rest_m=round(float(np.median(np.abs(r[m]))), 3))
    if best is None: return dict(fehler=f"weniger als {a.min_fotos} Fotos je Seite oder k-Spanne < {a.k_spanne}", punkte=P)
    T, sd = best["tiefe_ab_wand"], best["streuung"]
    if not (0.0 < T < 3.0) or sd is None or sd > 0.25 * T: return dict(best, fehler=f"unplausibel: T {T} m, Streuung {sd}", punkte=P)
    return dict(best, punkte=P)


def bild(pfad, erg):
    """Je Fenster Y gegen |kappa| (Punkte, Ausreisser grau) und die Geraden je Seite - Steigung = Laibungstiefe."""
    import cv2
    W_, H_ = 360, 260; tafeln = []
    for name, e in erg:
        im = np.full((H_, W_, 3), 255, np.uint8); P = [p for p in e.get("punkte", []) if "kappa" in p]
        if P:
            ka = np.array([abs(p["kappa"]) for p in P]); Y = np.array([p["Y"] if p["seite"] == "rechts" else -p["Y"] for p in P])   # links gespiegelt: beide fallen mit T
            y0, y1 = Y.min() - 0.05, Y.max() + 0.05; X = lambda v: int(20 + v / (ka.max() + 0.05) * (W_ - 40)); Yp = lambda v: int(H_ - 25 - (v - y0) / (y1 - y0 + 1e-9) * (H_ - 50))
            for p, a_, b_ in zip(P, ka, Y): cv2.circle(im, (X(a_), Yp(b_)), 3, (170, 170, 170) if p["foto"] in e.get("ausreisser", []) else ((200, 0, 0) if p["seite"] == "rechts" else (0, 150, 0)), -1)
            for sd, b in (e.get("kante_hinten") or {}).items():
                sg = 1 if sd == "rechts" else -1; T = e["tiefe_ab_wand"]; cv2.line(im, (X(0), Yp(sg * b)), (X(ka.max()), Yp(sg * b - ka.max() * T)), (0, 0, 220), 1)
        cv2.putText(im, name[:44], (5, 14), 0, 0.4, (0, 0, 0), 1)
        cv2.putText(im, (f"T {e['tiefe_ab_wand']:.2f} m +-{e['streuung']}, {e['fotos']} Fotos" if "tiefe_ab_wand" in e else "") + (" " + e["fehler"][:30] if "fehler" in e else ""), (5, 30), 0, 0.4, (0, 0, 160), 1)
        cv2.putText(im, "|kappa| ->  Y (rechts blau, links gruen gespiegelt)", (5, H_ - 6), 0, 0.35, (90, 90, 90), 1); tafeln.append(im)
    if tafeln: cv2.imwrite(pfad, np.hstack(tafeln))


def main():
    import cv2
    ap = argparse.ArgumentParser(); ap.add_argument("fenster"); ap.add_argument("fein"); ap.add_argument("objekt"); ap.add_argument("--nur", nargs="*"); ap.add_argument("--aus")
    ap.add_argument("--min_fotos", type=int, default=3, help="Formfamilie/Masse aus >= 3 Fotos (CLAUDE.md)")
    ap.add_argument("--k_spanne", type=float, default=0.1, help="Spanne der Blickschraege |k| ueber die Fotos (sonst ist die Steigung nicht bestimmt)")
    ap.add_argument("--staerke_rel", type=float, default=0.4, help="Fotos mit Kantensprung < 40 %% des Medians (verdeckt, unscharf) zaehlen nicht")
    ap.add_argument("--ohne_foto", action="store_true", help="nur Einzelfoto-Orthos (alter Weg; haengt vom Fensterkasten des gebauten Modells ab)")
    a = ap.parse_args()
    aus = a.aus or os.path.dirname(os.path.abspath(a.fenster)); os.makedirs(aus, exist_ok=True)
    try: obj = json.load(open(a.objekt))
    except Exception: obj = {}
    J = json.load(open(a.fenster)); FF = {F["id"]: F for F in json.load(open(os.path.join(a.fein, "fassaden.json")))["fassaden"]}
    mp = os.path.join(os.path.dirname(os.path.abspath(a.objekt)), "messprotokoll")
    bericht = {}; n_ok = 0
    for fid, F in J.items():
        if not isinstance(F, dict) or not F.get("fenster") or (a.nur and fid not in a.nur): continue
        ed = os.path.join(a.fein, f"ortho_{fid}_einzeln")
        if fid not in FF or not os.path.isdir(ed): bericht[fid] = "keine Einzelfoto-Orthos"; continue
        rs = FF[fid]["raster"]; rast = (rs["u0"], rs["z1"], rs["zelle"]); o = np.array(FF[fid]["o"], float); d = np.array(FF[fid]["d"], float); n = np.array(FF[fid]["n"], float)
        rp = os.path.join(a.fein, f"relief_{fid}.png"); rel = cv2.imread(rp, cv2.IMREAD_UNCHANGED) if os.path.exists(rp) else None
        kam, bilder, KK = {}, [], {}
        for p in sorted(glob.glob(os.path.join(ed, "*.png"))):
            name = os.path.basename(p)[:-4]; kf = os.path.join(mp, f"K-{name}.json")
            if not os.path.exists(kf): continue
            K = json.load(open(kf)).get("kamera")
            if not isinstance(K, dict) or "rvec" not in K: continue
            C = kamera_zentrum(K); kam[name] = (float((C[:2] - o) @ d), float((C[:2] - o) @ n))
            g = cv2.imread(p, cv2.IMREAD_GRAYSCALE)
            if g is not None: bilder.append((name, g)); KK[name] = K
        felder = [{} for _ in F["fenster"]]
        if not a.ohne_foto:                                                  # 22.11.2026: Vorrang Foto direkt auf flacher Ebene (unabhaengig vom Fensterkasten des vorigen Baus)
            sref = [ring_s(rel, rast, q) for q in F["fenster"]]
            for name, g in bilder:
                pf = foto_datei(obj, name, a.objekt)
                if pf is None: continue
                im = None
                for qi, q in enumerate(F["fenster"]):
                    sk = seite_k(q, *kam[name]); zk = (q.get("bogen") or {}).get("kaempfer") or q["z1"]
                    b = bereich(q, sk[0], zk) if sk else None
                    if b is None or verdeckt(g, rast, q, b): continue
                    if im is None: im = cv2.imread(pf, cv2.IMREAD_GRAYSCALE)
                    if im is None: break
                    A_ = foto_feld(im, KK[name], (o, d, n), b, rast[2], sref[qi])
                    if A_ is not None and (A_ == 0).mean() <= 0.1: felder[qi][name] = (A_, b[0], sref[qi])
                del im
        L = []; tafel = []
        for qi, q in enumerate(F["fenster"]):
            e = fenster_messen(bilder, kam, rel, rast, q, a, felder[qi]); e["kasten"] = [q["u0"], q["u1"], q["z0"], q["z1"]]; L.append(e); tafel.append((f"{fid} u {q['u0']:+.2f}..{q['u1']:+.2f}", e))
            if "fehler" in e: print(f"{fid} u {q['u0']:+.2f}: keine Laibung - {e['fehler']}"); continue
            t0 = float((q.get("nische") or {}).get("tiefe") or 0.0); T = e["tiefe_ab_wand"]
            if T <= t0 + 0.02: e["fehler"] = f"Laibung {T} m nicht hinter dem Nischengrund {t0} m"; print(f"{fid}: {e['fehler']}"); continue
            q["laibung"] = {k: e[k] for k in ("seite", "tiefe_ab_wand", "fotos", "k_spanne", "streuung", "rest_m")}
            q["tiefe"] = round(T - t0, 3); q["tiefe_quelle"] = f"Fotos: Laibung in Schraegsicht ({e['fotos']} Fotos, Tiefe ab Wand {T:.2f} +- {e['streuung']:.2f} m, tools/laibung_aus_fotos.py)"
            n_ok += 1; print(f"{fid} u {q['u0']:+.2f}: LAIBUNG {T:.2f} m ab Wand (+-{e['streuung']:.2f}, {e['fotos']} Fotos, |k| {e['k_spanne']}) -> Fenster {q['tiefe']:.2f} m hinter dem Nischengrund")
        bericht[fid] = L; bild(os.path.join(aus, f"laibung_{fid}.jpg"), tafel)
    json.dump(bericht, open(os.path.join(aus, "laibung_aus_fotos.json"), "w"), indent=1, ensure_ascii=False)
    # 22.11.2026: Zusammenfassung je Fassade als letzte Zeile - das Kettenlog zeigt nur die letzten Zeilen (1121v: nur f02/f03 sichtbar, f00 'T 4,68' verborgen)
    print("JE FASSADE: " + ", ".join(f"{f}: {sum('fehler' not in e for e in L)}/{len(L)} gemessen" + (" [" + "; ".join(f"T {e['tiefe_ab_wand']}" if 'fehler' not in e else e['fehler'][:40] for e in L) + "]")
                                     for f, L in bericht.items() if isinstance(L, list)))
    if not n_ok: print("keine Laibung gemessen"); return 3
    json.dump(J, open(os.path.join(aus, os.path.basename(a.fenster)), "w"), indent=1); print(f"-> {n_ok} Laibungen gemessen"); return 0


if __name__ == "__main__": sys.exit(main())
