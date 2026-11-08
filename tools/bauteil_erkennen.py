#!/usr/bin/env python3
"""bauteil_erkennen.py - Quader-Relief -> Bauteile mit freien Massen (Schritt 2 'Quader -> Bauteile', Nutzer 6.11.).
oeffnungen(): Segmentbogen-Oeffnungen (Rechteck bis Kaempfer zk + Kreissegment bis Scheitel zs, wie baukasten_gen.segmentbogen) aus der Tiefenkarte M (Zeilen z, Spalten u; s nach aussen, nan = leer).
Mass je Oeffnung: u0,u1 (max. Breite), zk (Kaempfer = Hoehe, ab der die Breite abnimmt), zs (Scheitel = Hoehe, wo die Oeffnung schliesst), tiefe (Median s der Rueckwand), Zahl beobachteter Zeilen.
Nur aus Zeilen mit Wolke (nan zaehlt nie als Oeffnung); Oeffnung = zusammenhaengender u-Lauf mit s < tiefe_schwelle (ANNAHME -1,0 m gegenueber der Wand). Ergebnis ist Messung, ANZAHL entscheidet das Foto (Regel 9)."""
import numpy as np


def _laeufe(m):
    d = np.diff(np.r_[0, m.astype(int), 0]); a, e = np.nonzero(d == 1)[0], np.nonzero(d == -1)[0]; return list(zip(a, e))


def oeffnungen(M, u0, zz0, g, schwelle=-1.0, min_breite=1.0, zmax=6.0, variante='fit', skip=40, leer_ist_offen=False, boden=0.6):
    nz = M.shape[0]; zz = zz0 + (np.arange(nz) + 0.5) * g; uu = lambda i: u0 + i * g
    zeilen = {}                                                                         # je Zeile Laeufe mit Oeffnung (nur beobachtete Zellen)
    for z in range(nz):
        if zz[z] > zmax: break
        zeilen[z] = [(a, e) for a, e in _laeufe((~np.isfinite(M[z]) | (M[z] < schwelle)) if leer_ist_offen else (np.isfinite(M[z]) & (M[z] < schwelle))) if (e - a) * g >= 0.1 and a > 0 and e < M.shape[1] and np.isfinite(M[z, a - 1]) and np.isfinite(M[z, e]) and M[z, a - 1] >= schwelle and M[z, e] >= schwelle]   # Raender nur mit beobachteter Wandzelle (Luecke ist keine Kante)
    # Zeilen mit Oeffnungslaeufen zu Oeffnungen verketten (Ueberlappung in u)
    offen = []; fertig = []
    for z in sorted(zeilen):
        neu = []
        for a, e in zeilen[z]:
            for o in offen:
                if min(e, o["rows"][-1][1]) - max(a, o["rows"][-1][0]) > 0.5 * (e - a) and 0 < z - o["z"][-1] <= skip: o["rows"].append((a, e)); o["z"].append(z); neu.append(o); break
            else: neu.append(dict(rows=[(a, e)], z=[z]))
        fertig += [o for o in offen if o not in neu]; offen = neu
    fertig += offen; out = []
    merged = []                                                                          # Bruchstuecke derselben Oeffnung (Luecke > skip Zeilen dazwischen): gleiche Raender (+-0,15 m) -> zusammenfuehren
    for o in sorted(fertig, key=lambda o: o["z"][0]):
        for m_ in merged:
            ma, me = np.median([r[0] for r in m_["rows"]]), np.median([r[1] for r in m_["rows"]]); oa, oe = np.median([r[0] for r in o["rows"]]), np.median([r[1] for r in o["rows"]])
            if abs(ma - oa) * g < 0.15 and abs(me - oe) * g < 0.15: m_["rows"] += o["rows"]; m_["z"] += o["z"]; break
        else: merged.append(dict(rows=list(o["rows"]), z=list(o["z"])))
    fertig = merged
    for o in fertig:
        if max((e - a) * g for a, e in o['rows']) < min_breite: continue
        if leer_ist_offen and zz[min(o['z'])] - g / 2 > boden: continue                      # Loch ohne Wolke zaehlt nur, wenn es bis zum Boden reicht (Arkade), sonst Schatten/Verdeckung
        W = np.array([(e - a) * g for a, e in o["rows"]]); zs_ = zz[o["z"]]; wmax = W.max()
        zk = float(zs_[np.argmax(W >= 0.97 * wmax)] if False else zs_[np.nonzero(W >= 0.97 * wmax)[0].max()])      # hoechste Zeile mit voller Breite = Kaempfer
        a = np.array([r[0] for r in o["rows"]])[W >= 0.97 * wmax]; e = np.array([r[1] for r in o["rows"]])[W >= 0.97 * wmax]
        zs = float(zs_[-1] + g / 2); tiefe = float(np.nanmedian(np.where(np.isfinite(M[o["z"][0]:o["z"][-1] + 1]), M[o["z"][0]:o["z"][-1] + 1], np.nan)[(M[o["z"][0]:o["z"][-1] + 1] < schwelle)]))
        r = dict(u0=float(uu(np.median(a))), u1=float(uu(np.median(e))), zk=zk, zs=zs, tiefe=tiefe, zeilen=len(o["z"]), z_unten=float(zs_[0] - g / 2))
        if variante == 'fit': r.update(_fit(o, zz, g, uu, r))
        out.append(r)
    return sorted(out, key=lambda r: r["u0"])


def _fit(o, zz, g, uu, r0):
    """Kleinste Quadrate (robust) auf Zeilenrand links/rechts: Segmentbogen wie baukasten_gen.segmentbogen: Breite 2w bis Kaempfer zk, darueber Kreissegment bis Scheitel zs.
    Parameter c (Mitte), w (halbe Breite), zk, zs. Nur Zeilen mit beobachteten Raendern (siehe oeffnungen)."""
    from scipy.optimize import least_squares
    z = zz[o["z"]]; L = np.array([uu(a) for a, e in o["rows"]]); Rr = np.array([uu(e) for a, e in o["rows"]])
    def halb(zv, w, zk, zs):
        h = max(zs - zk, 1e-3); R = (w * w + h * h) / (2 * h); zc = zs - R
        return np.where(zv <= zk, w, np.sqrt(np.clip(R * R - (zv - zc) ** 2, 0, None)))
    def res(p):
        c, w, zk, zs = p; hw = halb(z, w, zk, zs); in_ = z < zs                              # Zeilen oberhalb des Scheitels existieren nicht; Zeile gilt, wenn z < zs
        return np.r_[(L - (c - hw)), (Rr - (c + hw))]
    p0 = [0.5 * (r0["u0"] + r0["u1"]), 0.5 * (r0["u1"] - r0["u0"]), r0["zk"], r0["zs"]]
    lo, hi = np.array([-50, 0.3, 0.2, 0.5]), np.array([50, 5, 8, 10]); p0 = list(np.clip(p0, lo + 1e-6, hi - 1e-6))
    f = least_squares(res, p0, loss="soft_l1", f_scale=0.03, bounds=(lo, hi))
    c, w, zk, zs = f.x; n_, k_ = len(f.fun), 4
    try:                                                                                 # Unsicherheit je Parameter (1 sigma, Kovarianz aus der Jacobi-Matrix): ohne Zeilen am Bogenansatz ist zk NICHT bestimmbar
        s2 = float(np.sum(f.fun ** 2)) / max(n_ - k_, 1); cov = np.linalg.pinv(f.jac.T @ f.jac) * s2; sg = np.sqrt(np.diag(cov))
    except Exception: sg = np.full(4, np.inf)
    # Beobachtungsprobe: gibt es Zeilen unter UND ueber dem Kaempfer (+-0,3 m)? Sonst unbestimmt (Jacobi allein merkt es nicht immer)
    unten = int(np.sum((z > zk - 0.3) & (z <= zk))); oben = int(np.sum((z > zk) & (z < zk + 0.3)))
    best = bool(sg[2] <= 0.03 and unten >= 8 and oben >= 8)
    return dict(u0=float(c - w), u1=float(c + w), zk=float(zk), zs=float(zs), fit_rest_cm=float(np.median(np.abs(f.fun)) * 100), sigma_zk_cm=float(sg[2] * 100), sigma_w_cm=float(sg[1] * 100), zk_bestimmt=best, zeilen_um_zk=(unten, oben))
