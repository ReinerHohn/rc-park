#!/usr/bin/env python3
"""relief_vordergrund.py - VORDERGRUND aus einem Wandrelief nehmen (Schilder, Laternenkoepfe, Poller, Fahrzeugteile vor der Wand), 21.11.2026.

Anlass (Schwabentor w01, Lauf 1121s, Kontrollbild scratchpad tr/w01_trend_alt_neu.jpg): ein Verkehrsschild ('Einfahrt verboten' + Zusatzschild, etwa
0,6 x 0,9 m, z 1,65-2,75 m, u 1,75-2,6 m) haengt vor dem Quaderwerk, direkt UEBER dem Sockelband. Dichte Wolke UND lokale Feinrechnung (tiefe_lokal) haben es
als Flaeche (+8..+17 cm gegen Quader -1..-5 cm) -> ~+15 cm 'Buckel' im gebauten Relief.
VERSUCHT und verworfen (21.11.2026, Daten 1121s):
  - Mehrfoto-Parallaxe der entzerrten Einzelbilder: die Einzelbilder sind auf das NETZ projiziert (fassade_ortho, erster Strahltreffer) - das Schild ist im Netz,
    also steht es in allen Einzelbildern an derselben Stelle (< 3 px Versatz). Trennt nicht.
  - 'Tiefe ohne Feinbeleg' (grob vor der Feinrechnung in deren Loch): die Feinrechnung sieht das Schild selbst (f +11..+17 cm) - trennt nicht.
  - Glatt-Karte des Wandbilds (putz_wandbild): Schildrand/Schrift sind im 5-cm-Raster 'Struktur' wie Quader (Glattanteil 0,01) - trennt nicht.
  - Top-Hat mit waagerechter UND senkrechter Linienoeffnung: das Schild sitzt auf dem Sockelband, senkrecht durchlaufend -> nicht gefunden; dafuer Sockelstuecke.
  - SegFormer (gebaeude_segment) braucht die GPU - nicht in dieser Stufe.
KRITERIUM (Form im Relief, je Zeile gegen die Wand daneben):
  Wandniveau je Zelle = q-Perzentil (30 %) der Zeile ueber lang_u (1,5 m), nicht senkrecht geglaettet. Ein Sockelband, Gesims, Kaffgesims (waagerecht
  durchlaufend >= lang_u) bestimmt dort selbst das Perzentil und BLEIBT. Vorsprung = rel - Wandniveau.
  VORDERGRUND = zusammenhaengendes Stueck mit Vorsprung >= vor/2, dessen 90-%-Wert >= vor (10 cm) erreicht, KOMPAKT (Flaeche min_m2..max_m2, Breite <= max_b,
  Hoehe <= max_h, Breite < 40 % der Feldbreite) und NICHT naeher als rand_m (0,3 m) am linken/rechten/oberen Feldrand (Feldraender = Wandecken mit Eckquaderung, Anschluss an Nachbarwand;
  der untere Rand bleibt erlaubt: Poller, Fahrzeuge stehen auf dem Boden).
  BLEIBT: Lisene/Fallrohr (hoeher als max_h), Erker/Vorbau (> max_m2), Quaderrelief (Bossen gegen Fugen unter vor), alles am Feldrand.
  Die Zellen (+ 1 Zelle Rand) bekommen das Wandniveau (die Wand dahinter, glatt).

  vordergrund_maske(rel, ok, px, ...) -> (maske, niveau, info)
  vordergrund_weg(rel, ok, px, ...)   -> (rel_neu, maske, info)
ANNAHME: kompakte Bauteile mit >= 10 cm Vorsprung (Konsole, Wappen, Figur) baut der Generator aus Fotomassen (bauteile.py, Klipsteile), nicht das Netzrelief;
  hier wuerden sie auf Wandniveau gesetzt ('erhalten' = Rechtecke (i0, i1, j0, j1) in Zellen, die bleiben).
ANNAHME min_m2 = 0,3 m2 (groesser als ein Einzelquader): mit 0,02 m2 traf es am Schwabentor w01 einen echten vorstehenden Quader (0,15 m2) und Bandbuckel.
  Folge: kleiner Vordergrund (Laternenkopf, Poller < 0,3 m2) bleibt stehen - offen.
"""
import numpy as np


def vordergrund_maske(rel, ok, px, vor=0.10, lang_u=1.5, q=30.0, min_m2=0.3, max_m2=1.5, max_b=1.0, max_h=1.5, rand_m=0.3, erhalten=()):
    from scipy import ndimage as ndi
    rel = np.asarray(rel, np.float64); ok = np.asarray(ok, bool); H, W = rel.shape; info = dict(n=0, flaeche_m2=0.0, grund="")
    k = max(3, int(round(lang_u / px)))
    if ok.sum() < 50 or W < k: info["grund"] = "Feld schmaler als die Vergleichslinie oder zu wenig Zellen"; return np.zeros((H, W), bool), rel.copy(), info
    x = np.where(ok, rel, np.median(rel[ok]))                             # Loecher neutral (Median)
    niv = ndi.percentile_filter(x, q, size=(1, k), mode="nearest")          # je Zeile, NICHT senkrecht glaetten: sonst verschmiert die Oberkante eines Sockelbands in die Zeile darueber und verbindet ein aufsitzendes Schild mit dem Band
    vs = np.where(ok, x - niv, 0.0)
    erh = np.zeros((H, W), bool)
    for (i0, i1, j0, j1) in erhalten: erh[max(0, i0):i1, max(0, j0):j1] = True
    lab, n = ndi.label(ok & (vs >= 0.5 * vor), np.ones((3, 3))); m = np.zeros((H, W), bool); rand = []
    for kk, sl in enumerate(ndi.find_objects(lab), 1):
        if sl is None: continue
        c = lab[sl] == kk; f = c.sum() * px * px; h = (sl[0].stop - sl[0].start) * px; b = (sl[1].stop - sl[1].start) * px
        if f < min_m2 or f > max_m2 or b > max_b or h > max_h or b >= 0.4 * W * px: continue
        if np.percentile(vs[sl][c], 90) < vor or (erh[sl] & c).any(): continue
        if sl[1].start * px < rand_m or (W - sl[1].stop) * px < rand_m or sl[0].start * px < rand_m: rand.append(kk); continue
        m[sl] |= c
    if m.any(): m = ndi.binary_dilation(m, np.ones((3, 3), bool)) & ok & (vs > 0.0)
    info.update(n=int(ndi.label(m, np.ones((3, 3)))[1]) if m.any() else 0, flaeche_m2=round(float(m.sum() * px * px), 3), am_rand_behalten=len(rand))
    return m, niv, info


def vordergrund_weg(rel, ok, px, **kw):
    m, niv, info = vordergrund_maske(rel, ok, px, **kw); neu = np.array(rel, np.float64, copy=True); neu[m] = niv[m]; return neu, m, info
