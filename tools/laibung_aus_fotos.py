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
Gilt nur mit >= --min_fotos Fotos, k-Spanne >= --k_spanne, 0 < T < 3 m und Streuung <= 25 % von T; sonst bleibt der Eintrag unveraendert.
Ausgabe: fenster_auto.json (je gemessenem Fenster 'laibung' {tiefe_ab_wand, fotos, k_spanne, streuung} und 'tiefe' = Laibung ab Nischengrund bzw. Wand,
'tiefe_quelle'), Bericht laibung_aus_fotos.json, Bild laibung_<fid>.jpg (y gegen k je Fenster).
Aufruf: laibung_aus_fotos.py <fenster_auto.json> <fassade_fein-ordner> <objekt.json> [--nur f00] [--aus ordner]
rc 0 = mindestens ein Fenster gemessen, 3 = keins (nichts geaendert).
"""
import sys, os, json, glob, argparse, numpy as np


def kamera_zentrum(K):
    """Kamerazentrum (Modellrahmen) aus einer K-Datei (foto_mass/foto_kalibrieren: rvec, t) - wie foto_mass.strahl_ebene."""
    import cv2
    R, _ = cv2.Rodrigues(np.array(K["rvec"], float)); return -R.T @ np.array(K["t"], float)


def kante_messen(g, rel, rast, q, k_sign, zk):
    """Ladenkante im Einzelfoto-Ortho g (Graubild, 0 = kein Foto) auf der von der Kamera abgewandten Seite. Liefert (u_obs, s_dort, staerke) oder None."""
    u0, z1, c = rast; m = (q["u0"] + q["u1"]) / 2
    za, ze = q["z0"] + 0.3, zk - 0.1
    if ze - za < 0.2: return None
    ua, ue = (q["u0"] + 0.02, q["u1"] + 0.25) if k_sign > 0 else (q["u0"] - 0.25, q["u1"] - 0.02)   # ganze Breite: bei starker Schraege wandert die Kante ueber die Mitte
    i0, i1 = int(round((z1 - ze) / c)), int(round((z1 - za) / c)); j0, j1 = int(round((ua - u0) / c)), int(round((ue - u0) / c))
    if i0 < 0 or j0 < 0 or i1 > g.shape[0] or j1 > g.shape[1]: return None
    A = g[i0:i1, j0:j1].astype(np.float32)
    if (A > 0).mean() < 0.9: return None
    from scipy import ndimage as ndi
    gr = ndi.gaussian_filter1d(ndi.gaussian_filter(A, 1.5), 1.0, axis=1, order=1) * k_sign     # dunkel -> hell nach aussen
    gr[A == 0] = np.nan
    p = np.nanmedian(gr, axis=0)
    if not np.isfinite(p).any(): return None
    j = int(np.nanargmax(p)); u_obs = ua + (j + 0.5) * c
    s = 0.0
    if rel is not None:
        R_ = rel[i0:i1, j0 + max(j - 2, 0):j0 + j + 3]; R_ = R_[R_ > 0]
        if R_.size: s = float(np.median(R_)) / 1000.0 - 10.0
    return u_obs, s, float(p[j])


def fenster_messen(bilder, kam, rel, rast, q, a):
    """Alle Fotos fuer ein Fenster q -> dict(tiefe_ab_wand, fotos, k_spanne, streuung, punkte) oder dict(fehler)."""
    zk = (q.get("bogen") or {}).get("kaempfer") or q["z1"]; P = []
    for name, g in bilder:
        if name not in kam: continue
        Cu, Cw = kam[name]
        if Cw < 2.0: continue
        k_r, k_l = (q["u1"] - Cu) / Cw, (q["u0"] - Cu) / Cw
        if k_r > 0 and k_l > 0: sg, k = 1, k_r
        elif k_r < 0 and k_l < 0: sg, k = -1, k_l
        else: continue                                                       # Kamera vor dem Fenster: beide Laibungen verdeckt/klein
        r = kante_messen(g, rel, rast, q, sg, zk)
        if r is None: continue
        P.append(dict(foto=name, seite="rechts" if sg > 0 else "links", k=round(k, 4), u_obs=round(r[0], 3), s=round(r[1], 3), staerke=round(r[2], 2)))
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
    a = ap.parse_args()
    aus = a.aus or os.path.dirname(os.path.abspath(a.fenster)); os.makedirs(aus, exist_ok=True)
    J = json.load(open(a.fenster)); FF = {F["id"]: F for F in json.load(open(os.path.join(a.fein, "fassaden.json")))["fassaden"]}
    mp = os.path.join(os.path.dirname(os.path.abspath(a.objekt)), "messprotokoll")
    bericht = {}; n_ok = 0
    for fid, F in J.items():
        if not isinstance(F, dict) or not F.get("fenster") or (a.nur and fid not in a.nur): continue
        ed = os.path.join(a.fein, f"ortho_{fid}_einzeln")
        if fid not in FF or not os.path.isdir(ed): bericht[fid] = "keine Einzelfoto-Orthos"; continue
        rs = FF[fid]["raster"]; rast = (rs["u0"], rs["z1"], rs["zelle"]); o = np.array(FF[fid]["o"], float); d = np.array(FF[fid]["d"], float); n = np.array(FF[fid]["n"], float)
        rp = os.path.join(a.fein, f"relief_{fid}.png"); rel = cv2.imread(rp, cv2.IMREAD_UNCHANGED) if os.path.exists(rp) else None
        kam, bilder = {}, []
        for p in sorted(glob.glob(os.path.join(ed, "*.png"))):
            name = os.path.basename(p)[:-4]; kf = os.path.join(mp, f"K-{name}.json")
            if not os.path.exists(kf): continue
            K = json.load(open(kf)).get("kamera")
            if not isinstance(K, dict) or "rvec" not in K: continue
            C = kamera_zentrum(K); kam[name] = (float((C[:2] - o) @ d), float((C[:2] - o) @ n))
            g = cv2.imread(p, cv2.IMREAD_GRAYSCALE)
            if g is not None: bilder.append((name, g))
        L = []; tafel = []
        for q in F["fenster"]:
            e = fenster_messen(bilder, kam, rel, rast, q, a); e["kasten"] = [q["u0"], q["u1"], q["z0"], q["z1"]]; L.append(e); tafel.append((f"{fid} u {q['u0']:+.2f}..{q['u1']:+.2f}", e))
            if "fehler" in e: print(f"{fid} u {q['u0']:+.2f}: keine Laibung - {e['fehler']}"); continue
            t0 = float((q.get("nische") or {}).get("tiefe") or 0.0); T = e["tiefe_ab_wand"]
            if T <= t0 + 0.02: e["fehler"] = f"Laibung {T} m nicht hinter dem Nischengrund {t0} m"; print(f"{fid}: {e['fehler']}"); continue
            q["laibung"] = {k: e[k] for k in ("seite", "tiefe_ab_wand", "fotos", "k_spanne", "streuung", "rest_m")}
            q["tiefe"] = round(T - t0, 3); q["tiefe_quelle"] = f"Fotos: Laibung in Schraegsicht ({e['fotos']} Fotos, Tiefe ab Wand {T:.2f} +- {e['streuung']:.2f} m, tools/laibung_aus_fotos.py)"
            n_ok += 1; print(f"{fid} u {q['u0']:+.2f}: LAIBUNG {T:.2f} m ab Wand (+-{e['streuung']:.2f}, {e['fotos']} Fotos, |k| {e['k_spanne']}) -> Fenster {q['tiefe']:.2f} m hinter dem Nischengrund")
        bericht[fid] = L; bild(os.path.join(aus, f"laibung_{fid}.jpg"), tafel)
    json.dump(bericht, open(os.path.join(aus, "laibung_aus_fotos.json"), "w"), indent=1, ensure_ascii=False)
    if not n_ok: print("keine Laibung gemessen"); return 3
    json.dump(J, open(os.path.join(aus, os.path.basename(a.fenster)), "w"), indent=1); print(f"-> {n_ok} Laibungen gemessen"); return 0


if __name__ == "__main__": sys.exit(main())
