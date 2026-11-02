#!/usr/bin/env python3
"""pruefstand.py - GENERISCHER Abnahme-Pruefstand: misst ein STL gegen die Masstabelle eines Objekts.

  /media/oem/scan/venv-seg/bin/python -W ignore -I tools/pruefstand.py modelle/<objekt>/objekt.json [--stl pfad] [--md]
Exit 0 = alle Pruefungen bestanden, 1 = Fehlschlag, 2 = Tabelle unzulaessig (Quelle blind fuer Merkmal, Formelfehler).

Die Tabelle (masstabelle.json) enthaelt KEINEN Code: nur benannte Messungen (generische Messer unten), Pruefungen mit
Sollbereich + Quelle + Quelltyp + Merkmalstyp, offene Beobachtungen. Dieser Pruefstand kennt, was jede Quelle sehen kann
(QUELLEN). Eine Pruefung, deren Quelle fuer ihr Merkmal blind ist, wird ABGELEHNT (Exit 2) - das war die Wurzel des
Martinstor-Fehlers (Nadelhoehe aus Laser DOM1). Masse immer in Metern, STL wird auf Massstab/Mitte/Boden normiert.
"""
import sys, os, re, json, numpy as np, trimesh
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Was eine Quelle beweisen kann (Erfahrung dieses Projekts; Begruendung in modelle/METHODE_MASSTABELLE.md)
QUELLEN = {
    # laser_dom1: 1-m-Zellmaxima. Zusaetzlich praktisch blind fuer den FUSSABDRUCK steiler Helmflaechen (> ~75 Grad): Zellzahl und Schnitt
    # dort um Faktor 2 zu klein (Register AR, Foto 061 + Wolke vs DOM1) - Flaechenpruefungen am Helm nur unterhalb der Traufe oder am Peak.
    "laser_dom1":      {"sieht": ["hoehe_flaeche", "anzahl"],                            "blind": ["duennes_bauteil", "schlankheit", "fassade", "absolut_hoehe", "verhaeltnis", "grundriss"],
                        "hinweis": "1-m-Raster, interpoliert, nur von oben; Strukturen < ~3 m verschmiert, Nadeln unsichtbar. BLIND auch fuer Grundriss mit "
                                   "Vorspruengen < ~1 m (Gesims, Erker): die Flaeche ueber Hoehe faellt dann 15-20 % zu klein aus (Martinstor 2026-11-01, Register O/P)"},
    "laser_punkte":    {"sieht": ["hoehe_flaeche", "grundriss", "anzahl", "schlankheit"], "blind": ["duennes_bauteil", "fassade"],
                        "hinweis": "Rohpunkte >= 8/m2: Kegel ja, Nadel 0,1 m kaum"},
    "lod2":            {"sieht": ["grundriss", "hoehe_flaeche"],                          "blind": ["duennes_bauteil", "schlankheit", "fassade", "absolut_hoehe", "verhaeltnis"],
                        "hinweis": "amtlicher Grundriss + Traufe/First, keine Aufbauten/Details"},
    "foto_verhaeltnis":{"sieht": ["schlankheit", "verhaeltnis", "anzahl", "fassade"],   "blind": ["absolut_hoehe", "grundriss"],
                        "hinweis": "nur Verhaeltnisse (+-5-10 %), absolute Masse nur mit bekanntem Massstab"},
    "foto_vollbild":   {"sieht": ["duennes_bauteil", "schlankheit", "verhaeltnis", "anzahl", "fassade"], "blind": ["absolut_hoehe", "grundriss"],
                        "hinweis": "Vollaufloesung, Massstab aus Modell oder Dokument -> Werte grob, Richtung sicher"},
    "foto_kalibriert": {"sieht": ["absolut_hoehe", "hoehe_flaeche", "fassade", "verhaeltnis", "anzahl", "schlankheit", "duennes_bauteil", "grundriss"], "blind": [],
                        "hinweis": "Kamera aus amtlichen Ankern (LoD2/DOM1), Pixel->Meter auf bekannter Ebene; +-0,1-0,3 m je Mass, +-1 m systematisch in der Hoehe (Ankerhoehen)"},
    "sfm_bodenanker":  {"sieht": ["absolut_hoehe", "hoehe_flaeche", "verhaeltnis", "schlankheit", "duennes_bauteil", "grundriss"], "blind": ["anzahl", "fassade"],
                        "hinweis": "COLMAP-Netz je Fassadenseite (tools/sfm_ausrichten.py), 7 Parameter aus LoD2-Eckkanten in >= 4 Fotos, Hoehenlage aus ANNAHME Strassenkamera "
                                   "1,7 +- 0,6 m; Massstab +-2-3 %, Hoehe +-0,7 m systematisch; sieht keine Fassadenzaehlung (Punkte, keine Semantik). Register AH"},
    "dokument":        {"sieht": ["absolut_hoehe", "anzahl", "grundriss"],               "blind": ["schlankheit", "duennes_bauteil", "fassade"],
                        "hinweis": "Bauforschung/Denkmalamt/Wikipedia; Bezugshoehe oft unklar (60 vs 65 m)"},
    "modell":          {"sieht": ["druck"], "blind": [], "hinweis": "Druckbarkeit, keine Realitaetsaussage"},
}

# ----------------------------------------------------------------------------- generische Messer (alle in Metern)
class Messer:
    def __init__(self, m, obj=None, root=None): self.m = m; self.obj = obj; self.root = root
    def silhouettenbreite_zone(self, z_von, z_bis, schritt, kamera, foto, seite="beide", **k):
        """Mittlere Silhouettenbreite ueber eine Hoehenzone - muss zur Quelle passen: ein Sollwert aus einem Zonenmittel
        darf nicht gegen eine Einzelhoehe geprueft werden (2026-11-01: 12,60 gegen Soll 11,1-11,9 war genau dieser Fehler)."""
        w = [self.silhouettenbreite(z, kamera, foto, seite=seite) for z in np.arange(z_von, z_bis + 1e-9, schritt)]
        w = [x for x in w if not np.isnan(x)]
        return float(np.mean(w)) if w else float("nan")
    def silhouettenbreite(self, z, kamera, foto, seite="beide", **k):
        """Breite der Modellsilhouette in Metern auf Hoehe z, gesehen durch eine kalibrierte Kamera (gleiche Rechnung wie tools/foto_breitenprofil.py).
        Sollwert dazu ist der FOTO-Wert - so wird eine Fotomessung zur dauerhaften Pruefung, ohne das Foto im Pruefstand zu brauchen."""
        import sys as _s, cv2, glob
        _s.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import foto_breitenprofil as FB
        K = json.load(open(os.path.join(self.root, os.path.dirname(self.obj["masstabelle"]), "messprotokoll", kamera + ".json")))["kamera"]
        R, t, C, f, cx, cy = FB.strahlen_setup(K); W, H = K["bild"]
        import render_kern as RK
        if not hasattr(self, "_sz"):
            P, _ = trimesh.sample.sample_surface(self.m, 2500000, seed=0); self._sz = RK.Szene(np.asarray(P)); self._mcache = {}
        # Die Maske haengt NUR von der Kamera ab, nicht von der Hoehe - je Kamera einmal rendern statt je Hoehe
        # (eine Zone mit 10 Hoehen rechnete die identische Maske zehnmal; Pruefstand 4,8 s -> siehe Register W).
        if kamera not in self._mcache: self._mcache[kamera] = self._sz.maske_np(R, t, f, cx, cy, W, H)
        M = self._mcache[kamera]
        l, r = FB.halbbreite(M, R, t, f, cx, cy, C, z, FB.quer_richtung(C, z))
        # Muss zur Fotomessung passen: ist dort eine Seite verdeckt, wird die freie verdoppelt - am Modell genauso.
        if seite == "links": return float(2 * l) if not np.isnan(l) else float("nan")
        if seite == "rechts": return float(2 * r) if not np.isnan(r) else float("nan")
        return float(l + r) if not (np.isnan(l) or np.isnan(r)) else float("nan")
    def _polys(self, z):
        s = self.m.section(plane_origin=[0, 0, z], plane_normal=[0, 0, 1])
        if s is None: return []
        p, T = s.to_2D()                                   # to_2D verschiebt/dreht die Ebene: Schwerpunkte zurueck in Modellkoordinaten
        self._T = T; return [(T[:2, :2] @ np.array(g.centroid.coords[0]) + T[:2, 3], g) for g in p.polygons_full]
    def _bounds3(self, g):
        b = g.bounds; T = self._T; pts = np.array([[b[0], b[1]], [b[2], b[1]], [b[2], b[3]], [b[0], b[3]]]) @ T[:2, :2].T + T[:2, 3]
        return pts[:, 0].min(), pts[:, 1].min(), pts[:, 0].max(), pts[:, 1].max()
    @staticmethod
    def _diam(g): return 2 * np.sqrt(g.area / np.pi)
    def hoehe_max(self, **k): return float(self.m.extents[2])
    def lokales_max_abseits(self, zmin, ax, ay, **k):
        v = self.m.vertices; s = (v[:, 2] > zmin) & (np.abs(v[:, 0]) > ax) & (np.abs(v[:, 1]) > ay)
        return float(v[s, 2].max()) if s.any() else float("nan")
    def _flaechenpunkte(self):
        """Dichte Punkte AUF der Modelloberflaeche (Kanten <= 0,3 m unterteilt): Kegel/Zylinder haben nur Ringe als Ecken - Eckpunkte allein
        verfehlen Spitzen und schraege Flaechen (Register AX: 'Eckturm-Kegelspitze' mass jahrelang einen Eckquader)."""
        if not hasattr(self, "_fp"):
            v, fa = self._unterteilt(); self._fp = np.vstack([v, v[fa].mean(1)])
        return self._fp
    def _unterteilt(self):
        """Kanten <= 0,3 m unterteilt - einmal je Modell (teuer, ~2 s); _flaechenpunkte und hypso_ueber teilen sich das Ergebnis (bitgleich zur getrennten Rechnung)."""
        if not hasattr(self, "_sub"): self._sub = trimesh.remesh.subdivide_to_size(self.m.vertices, self.m.faces, max_edge=0.3, max_iter=14)
        return self._sub
    def max_z_im_bereich(self, x0, x1, y0, y1, zmax=1e9, **k):
        """Hoechster Oberflaechenpunkt innerhalb eines Grundriss-Rechtecks unterhalb zmax (z. B. Eckturm-Kegelspitze, ohne den Schaft darueber)."""
        v = self._flaechenpunkte(); s = (v[:, 0] >= x0) & (v[:, 0] <= x1) & (v[:, 1] >= y0) & (v[:, 1] <= y1) & (v[:, 2] < zmax)
        return float(v[s, 2].max()) if s.any() else 0.0
    def _im_bereich(self, x0, x1, y0, y1, z0, z1):
        V = self.m.vertices; return V[(V[:, 0] >= x0) & (V[:, 0] <= x1) & (V[:, 1] >= y0) & (V[:, 1] <= y1) & (V[:, 2] >= z0) & (V[:, 2] <= z1)]
    def min_im_bereich(self, x0, x1, y0, y1, z0, z1, achse="x", **k):
        """Kleinster Wert einer Achse unter den Eckpunkten im Quader (z. B. Nordwand-Lage = min x bei |y| < 2,5)."""
        Q = self._im_bereich(x0, x1, y0, y1, z0, z1); return float(Q[:, "xyz".index(achse)].min()) if len(Q) else float("nan")
    def mitte_im_bereich(self, x0, x1, y0, y1, z0, z1, achse="y", **k):
        """Mitte (min+max)/2 einer Achse im Quader - Lage eines Bauteils (z. B. Eckturm y)."""
        Q = self._im_bereich(x0, x1, y0, y1, z0, z1); a = "xyz".index(achse); return float((Q[:, a].min() + Q[:, a].max()) / 2) if len(Q) else float("nan")
    def kreis_durchmesser_im_bereich(self, x0, x1, y0, y1, z0, z1, **k):
        """Durchmesser eines runden Bauteils aus einem Kreisfit (kleinste Quadrate) an die Eckpunkte im Quader - auch wenn nur die
        freie Vorderseite im Quader liegt (Eckturm vor der Wand)."""
        Q = self._im_bereich(x0, x1, y0, y1, z0, z1)
        if len(Q) < 6: return float("nan")
        X = Q[:, :2]; A = np.c_[2 * X[:, 0], 2 * X[:, 1], np.ones(len(X))]; b = (X ** 2).sum(1); c = np.linalg.lstsq(A, b, rcond=None)[0]
        return float(2 * np.sqrt(max(c[2] + c[0] ** 2 + c[1] ** 2, 0.0)))
    def schnitt_ausdehnung(self, z, x0, x1, y0, y1, achse="y", **k):
        """Ausdehnung der SCHNITTKONTUR bei z (trimesh.section) innerhalb eines xy-Fensters - z. B. Sehne eines runden Eckturms
        knapp vor der Wandebene; robuster als Eckpunkt-Fits an groben Zylindern."""
        sec = self.m.section(plane_origin=(0, 0, z), plane_normal=(0, 0, 1))
        if sec is None: return float("nan")
        Q = np.asarray(sec.vertices); Q = Q[(Q[:, 0] >= x0) & (Q[:, 0] <= x1) & (Q[:, 1] >= y0) & (Q[:, 1] <= y1)]
        a = "xyz".index(achse); return float(Q[:, a].max() - Q[:, a].min()) if len(Q) >= 2 else float("nan")
    def schnitt_mitte(self, z, x0, x1, y0, y1, achse="x", **k):
        """Mitte (min+max)/2 der Schnittkontur bei z im xy-Fenster - Achse eines Bauteils, auch wenn das Netz dort keine Eckpunkte hat (Kegel)."""
        sec = self.m.section(plane_origin=(0, 0, z), plane_normal=(0, 0, 1))
        if sec is None: return float("nan")
        Q = np.asarray(sec.vertices); Q = Q[(Q[:, 0] >= x0) & (Q[:, 0] <= x1) & (Q[:, 1] >= y0) & (Q[:, 1] <= y1)]
        a = "xyz".index(achse); return float((Q[:, a].min() + Q[:, a].max()) / 2) if len(Q) >= 2 else float("nan")
    def ausdehnung_im_bereich(self, x0, x1, y0, y1, z0, z1, **k):
        """x-/y-Ausdehnung aller Punkte in einem Quader (z. B. Durchmesser eines Anbaus, der im Schnitt mit dem Rumpf verschmilzt)."""
        v = self.m.vertices; s = (v[:, 0] >= x0) & (v[:, 0] <= x1) & (v[:, 1] >= y0) & (v[:, 1] <= y1) & (v[:, 2] >= z0) & (v[:, 2] <= z1)
        if not s.any(): return {"x": 0.0, "y": 0.0, "punkte": 0.0}
        q = v[s]; return {"x": float(q[:, 0].max() - q[:, 0].min()), "y": float(q[:, 1].max() - q[:, 1].min()), "punkte": float(s.sum())}
    def querschnitte_abseits(self, z, ax, ay, **k):
        ps = [(c, g) for c, g in self._polys(z) if abs(c[0]) > ax and abs(c[1]) > ay]
        return {"anzahl": float(len(ps)), "durchmesser": float(np.mean([self._diam(g) for _, g in ps])) if ps else float("nan")}
    def breite_achse(self, z, r, **k):
        ps = [g for c, g in self._polys(z) if np.hypot(*c) < r]; return max([self._diam(g) for g in ps], default=0.0)
    def knauf_achse(self, z0, z1, dz, r, **k):
        zs = np.arange(z0, z1, dz); ws = [self.breite_achse(z, r) for z in zs]; i = int(np.argmax(ws))
        return {"breite": float(ws[i]), "z": float(zs[i])}
    def wasserdicht(self, **k): return 1.0 if self.m.is_watertight else 0.0
    def koerper_anzahl(self, **k): return float(len(self.m.split(only_watertight=False)))
    def nischen_anzahl(self, seite, z, halb, tiefe, schritt=0.05, min_b=0.3, max_b=2.0, **k):
        """Zaehlt Rueckspruenge >= tiefe entlang einer Fassade (Strahlen von aussen), Breite min_b..max_b."""
        ax = 0 if seite[1] == "x" else 1; sgn = 1.0 if seite[0] == "+" else -1.0
        us = np.arange(-halb, halb + 1e-6, schritt); org = np.zeros((len(us), 3)); org[:, ax] = sgn * 40.0; org[:, 1 - ax] = us; org[:, 2] = z
        dr = np.zeros_like(org); dr[:, ax] = -sgn
        loc, ir, _ = self.m.ray.intersects_location(org, dr, multiple_hits=False)
        d = np.full(len(us), np.nan); d[ir] = np.abs(loc[:, ax]); wall = np.nanmedian(d); d = np.where(np.isnan(d), -1e3, d); rec = (wall - d) >= tiefe   # Durchblick (kein Treffer) = tiefe Nische
        n, run = 0, 0
        for rr in list(rec) + [False]:
            if rr: run += 1
            else:
                if min_b / schritt <= run <= max_b / schritt: n += 1
                run = 0
        return float(n)
    def relief_mitte(self, seite, z0, z1, halb, schwelle=0.08, schritt=0.1, richtung="vor", **k):
        """Mitte eines aus der Wand HERAUSTRETENDEN Fassadenmerkmals (Uhr: Stundenmarken/Rahmen; Tafel): Strahlen von aussen auf ein Raster
        (quer x z), Wand je Zeile = Median der Trefferabstaende, Relief = Zellen >= schwelle vor der Wand (richtung 'vor'; 'zurueck' = Nischen,
        'beide'). Zeilen, in denen mehr als die Haelfte der Zellen heraustritt (durchlaufende Gesimse/Giebelbaender), zaehlen nicht.
        Rueckgabe {"z", "quer", "radius", "anzahl"}: Kreisfit (kleinste Quadrate) an die Reliefzellen - fuer ringfoermige Merkmale die Mitte,
        sonst naeherungsweise der Schwerpunkt. nan, wenn < 8 Zellen."""
        ax = 0 if seite[1] == "x" else 1; sgn = 1.0 if seite[0] == "+" else -1.0
        us = np.arange(-halb, halb + 1e-6, schritt); zs = np.arange(z0, z1 + 1e-6, schritt); U, Z = np.meshgrid(us, zs)
        org = np.zeros((U.size, 3)); org[:, ax] = sgn * 40.0; org[:, 1 - ax] = U.ravel(); org[:, 2] = Z.ravel(); dr = np.zeros_like(org); dr[:, ax] = -sgn
        loc, ir, _ = self.m.ray.intersects_location(org, dr, multiple_hits=False)
        d = np.full(U.size, np.nan); d[ir] = sgn * loc[:, ax]; d = d.reshape(U.shape)
        aussen = np.abs(us) > 0.7 * halb                                                   # Wand je Zeile aus den Randspalten (dort steht selten ein Merkmal; Giebel/Rahmen mittig verfaelschen den Zeilenmedian nicht)
        wand = np.nanmedian(np.where(aussen[None, :], d, np.nan), axis=1, keepdims=True); diff = d - wand   # > 0 = vor der Wand (naeher am Strahlursprung)
        rel = (diff >= schwelle) if richtung == "vor" else ((diff <= -schwelle) if richtung == "zurueck" else (np.abs(diff) >= schwelle))
        if richtung == "vor": rel &= (rel.mean(axis=1, keepdims=True) <= 0.5)           # durchlaufende Baender (Gesimse) ausblenden; Nischen (Scheibe) ganz lassen
        if rel.sum() < 8: return {"z": float("nan"), "quer": float("nan"), "radius": float("nan"), "anzahl": float(rel.sum())}
        X = np.c_[U[rel], Z[rel]]; A = np.c_[2 * X[:, 0], 2 * X[:, 1], np.ones(len(X))]; c = np.linalg.lstsq(A, (X ** 2).sum(1), rcond=None)[0]
        r = float(np.sqrt(max(c[2] + c[0] ** 2 + c[1] ** 2, 0.0)))
        # z/quer = Schwerpunkt der Reliefzellen (fuer gefuellte Scheiben/Tafeln exakt), z_kreis = Kreisfit (fuer Ringe/Markenkraenze)
        return {"z": float(X[:, 1].mean()), "quer": float(X[:, 0].mean()), "z_kreis": float(c[1]), "radius": r, "anzahl": float(rel.sum())}
    def tuerm_radius(self, seite, z, quer, achse_tief, band=0.6, schritt=0.05, **k):
        """Aussenradius eines Rundkoerpers neben der Achse (Ecktuermchen): Strahlen von aussen (Seite -x/+x/-y/+y) auf Hoehe z in einem schmalen
        Streifen quer +- band; erster Treffer = Aussenkante; Radius = Abstand der Kante von der Tuermchenachse (achse_tief, Betrag). Entspricht
        der Wolken-Aussenkante (p97 der Tiefe in der Tuermchenzone). nan ohne Treffer."""
        ax = 0 if seite[1] == "x" else 1; sgn = 1.0 if seite[0] == "+" else -1.0
        qs = np.arange(quer - band, quer + band + 1e-6, schritt); org = np.zeros((len(qs), 3)); org[:, ax] = sgn * 40.0; org[:, 1 - ax] = qs; org[:, 2] = z
        dr = np.zeros_like(org); dr[:, ax] = -sgn
        loc, ir, _ = self.m.ray.intersects_location(org, dr, multiple_hits=False)
        if len(loc) == 0: return float("nan")
        return float(np.percentile(np.abs(loc[:, ax]), 90) - abs(achse_tief))               # p90 der Treffer = Aussenkante (Pfeiler zwischen Oeffnungen), wie p97 in der Wolke
    rand_radius = tuerm_radius                                                           # generischer Name (jeder Koerper neben der Achse)
    def _front_profil(self, seite, quer, z0, z1, schritt=0.05, band=0.0):
        """Tiefe der ersten Modellflaeche je z (Strahlen von aussen) entlang einer senkrechten Linie bei quer (+- band gemittelt)."""
        ax = 0 if seite[1] == "x" else 1; sgn = 1.0 if seite[0] == "+" else -1.0
        zs = np.arange(z0, z1 + 1e-6, schritt); qs = np.arange(quer - band, quer + band + 1e-6, max(schritt, 0.05)) if band > 0 else np.array([quer])
        Q, Z = np.meshgrid(qs, zs); org = np.zeros((Q.size, 3)); org[:, ax] = sgn * 40.0; org[:, 1 - ax] = Q.ravel(); org[:, 2] = Z.ravel(); dr = np.zeros_like(org); dr[:, ax] = -sgn
        loc, ir, _ = self.m.ray.intersects_location(org, dr, multiple_hits=False); d = np.full(Q.size, np.nan); d[ir] = sgn * loc[:, ax]
        return zs, np.nanmedian(d.reshape(Q.shape), axis=1)
    def relief_periode(self, seite, quer, z0, z1, band=0.75, schritt=0.025, max_periode=2.0, **k):
        """Periode (m) des Reliefs an einer Kante (Eckquader): wie die Wolkenmessung (wolke_baender.py) der ANTEIL hervortretender Zellen je
        5-cm-Hoehenschicht in einem Band quer +- band; Autokorrelation; Periode = KLEINSTER Peak mit >= 50 % der Staerke des staerksten
        (Grundperiode statt Oberschwingung). nan ohne Relief."""
        zs, D = self._front_profil(seite, quer, z0, z1, schritt, band=0.0) if band <= 0 else (None, None)
        ax = 0 if seite[1] == "x" else 1; sgn = 1.0 if seite[0] == "+" else -1.0
        zs = np.arange(z0, z1 + 1e-6, schritt); qs = np.arange(quer - band, quer + band + 1e-6, schritt)
        Q, Z = np.meshgrid(qs, zs); org = np.zeros((Q.size, 3)); org[:, ax] = sgn * 40.0; org[:, 1 - ax] = Q.ravel(); org[:, 2] = Z.ravel(); dr = np.zeros_like(org); dr[:, ax] = -sgn
        loc, ir, _ = self.m.ray.intersects_location(org, dr, multiple_hits=False); d = np.full(Q.size, np.nan); d[ir] = sgn * loc[:, ax]; d = d.reshape(Q.shape)
        wand = np.nanmedian(d); relief = (d > wand + 0.03); anteil = np.array([relief[i][~np.isnan(d[i])].mean() if (~np.isnan(d[i])).any() else np.nan for i in range(len(zs))])
        ok = ~np.isnan(anteil)
        if ok.sum() < 20 or np.nanstd(anteil) < 0.02: return float("nan")
        x = anteil.copy(); x[~ok] = np.nanmean(anteil); x = x - x.mean(); ac = np.correlate(x, x, "full")[len(x) - 1:]; ac = ac / max(ac[0], 1e-9); n = int(max_periode / schritt)
        cand = [(i * schritt, ac[i]) for i in range(2, min(len(ac) - 1, n)) if ac[i] > ac[i - 1] and ac[i] >= ac[i + 1] and ac[i] > 0]
        if not cand: return float("nan")
        st = max(c[1] for c in cand); return float(min(c[0] for c in cand if c[1] >= 0.5 * st))
    def front_linearitaet(self, seite, z0, z1, quer=0.0, band=0.5, schritt=0.1, **k):
        """Geradlinigkeit einer Dach-/Wandflaeche: groesste Abweichung (m) der Modellfront von der Ausgleichsgeraden ueber z0..z1 (Hoecker, Knicke)."""
        zs, d = self._front_profil(seite, quer, z0, z1, schritt, band); ok = ~np.isnan(d)
        if ok.sum() < 5: return float("nan")
        A = np.c_[zs[ok], np.ones(ok.sum())]; c, *_ = np.linalg.lstsq(A, d[ok], rcond=None)
        return float(np.abs(d[ok] - A @ c).max())
    def flaeche_oeffnungen(self, seite, z, quer0, quer1, tiefe=0.2, schritt=0.04, min_b=0.12, **k):
        """Oeffnungen entlang einer Flaeche auf Hoehe z zwischen quer0..quer1: Laeufe, in denen die erste Flaeche >= tiefe hinter der Flaechenebene
        (Median der Treffer) liegt oder kein Treffer kommt. Rueckgabe {"anzahl", "breite_median", "breite_max"}."""
        ax = 0 if seite[1] == "x" else 1; sgn = 1.0 if seite[0] == "+" else -1.0
        qs = np.arange(quer0, quer1 + 1e-6, schritt); org = np.zeros((len(qs), 3)); org[:, ax] = sgn * 40.0; org[:, 1 - ax] = qs; org[:, 2] = z; dr = np.zeros_like(org); dr[:, ax] = -sgn
        loc, ir, _ = self.m.ray.intersects_location(org, dr, multiple_hits=False); d = np.full(len(qs), np.nan); d[ir] = sgn * loc[:, ax]
        ebene = np.nanpercentile(d, 90) if np.isfinite(d).any() else np.nan; offen = np.isnan(d) | (d < ebene - tiefe)
        laeufe = []; run = 0
        for o in list(offen) + [False]:
            if o: run += 1
            else:
                if run * schritt >= min_b: laeufe.append(run * schritt)
                run = 0
        return {"anzahl": float(len(laeufe)), "breite_median": float(np.median(laeufe)) if laeufe else 0.0, "breite_max": float(max(laeufe)) if laeufe else 0.0}
    def z_nischen_ende(self, seite, z0, z1, dz, halb, tiefe, min_b=0.3, max_b=2.5, **k):
        """Oberkante eines Zinnenkranzes o. ae.: kleinste Hoehe ab z0, ab der die Fassade keine Nischen (Scharten) mehr zeigt (nischen_anzahl == 0
        in zwei aufeinanderfolgenden Schichten). Robust gegen darueber liegende Daecher - misst das Ende der Scharten, nicht den hoechsten Punkt."""
        letzte = None; gesehen = False
        for z in np.arange(z0, z1 + 1e-6, dz):
            n = self.nischen_anzahl(seite, float(z), halb, tiefe, min_b=min_b, max_b=max_b)
            if n > 0: gesehen = True
            if gesehen and n == 0 and letzte == 0: return float(z - dz)
            letzte = n
        return float("nan")
    def anzahl_im_band(self, z, achse, lo, hi, quer_max, **k):
        """Zaehlt Querschnitte bei z, deren Schwerpunkt auf 'achse' (x|y) zwischen lo..hi liegt und quer < quer_max (z. B. Zinnen einer Seite)."""
        a = 0 if achse == "x" else 1
        return float(sum(1 for c, _ in self._polys(z) if lo <= c[a] <= hi and abs(c[1 - a]) < quer_max))
    def relief_breite(self, seite, z, halb, hoehe_min, schritt=0.05, art="vor", max_luecke=0.0, **k):
        """Breite des laengsten zusammenhaengenden Vorsprungs (art=vor) oder Ruecksprungs (art=rueck) >= hoehe_min entlang einer Fassade bei z (Uhrnische, Rahmen)."""
        ax = 0 if seite[1] == "x" else 1; sgn = 1.0 if seite[0] == "+" else -1.0
        us = np.arange(-halb, halb + 1e-6, schritt); org = np.zeros((len(us), 3)); org[:, ax] = sgn * 40.0; org[:, 1 - ax] = us; org[:, 2] = z
        dr = np.zeros_like(org); dr[:, ax] = -sgn
        loc, ir, _ = self.m.ray.intersects_location(org, dr, multiple_hits=False)
        d = np.full(len(us), np.nan); d[ir] = np.abs(loc[:, ax]); k = max(3, int(0.15 * len(us)))
        wall = np.nanmedian(np.r_[d[:k], d[-k:]])                       # Wand = Rand des Messbereichs (das Relief selbst darf den Median nicht stellen)
        dev = (d - wall) if art == "vor" else (wall - d) if art == "rueck" else np.abs(d - wall); vor = dev >= hoehe_min
        idx = np.nonzero(vor)[0]
        if len(idx) == 0: return 0.0
        best = 0; start = idx[0]; prev = idx[0]                      # Laeufe, die durch Luecken <= max_luecke (z. B. Stundenmarken) unterbrochen sind, zusammenfassen
        for i in list(idx[1:]) + [None]:
            if i is None or (i - prev - 1) * schritt > max_luecke: best = max(best, prev - start + 1); start = i
            prev = i if i is not None else prev
        return float(best * schritt)
    def ausdehnung_streifen(self, z, achse="y", quer_max=2.0, **k):
        """Ausdehnung des Querschnitts entlang 'achse' innerhalb eines Streifens |quer| < quer_max durch die Achse (blendet Ecktuermchen/Erker aus)."""
        from shapely.geometry import box
        a = 0 if achse == "x" else 1; T = getattr(self, "_T", None); ps = self._polys(z); T = self._T
        lo_, hi_ = np.inf, -np.inf
        for _, g in ps:
            b = g.bounds; pts = np.array([[b[0], b[1]], [b[2], b[3]]]) @ T[:2, :2].T + T[:2, 3]        # Modellkoordinaten des Polygons (nur Translation relevant)
            off = T[:2, 3]; strip = box(-quer_max - off[0], -1e3, quer_max - off[0], 1e3) if a == 1 else box(-1e3, -quer_max - off[1], 1e3, quer_max - off[1])
            q = g.intersection(strip)
            if q.is_empty: continue
            qb = q.bounds; lo_ = min(lo_, qb[a] + off[a]); hi_ = max(hi_, qb[a + 2] + off[a])
        return float(hi_ - lo_) if hi_ > lo_ else 0.0
    def z_bei_breite(self, z0, z1, dz, r, schwelle, achse="y", richtung="auf", quer_max=2.0, **k):
        """Erste Hoehe (aufsteigend), bei der die Ausdehnung des Querschnitts nahe der Achse die Schwelle UEBER- (schwelle>0) bzw. UNTERschreitet (schwelle<0):
        z. B. Dachansatz (Breite springt ueber 7 m) oder First (Breite faellt unter 3,5 m)."""
        zs = np.arange(z0, z1, dz); zs = zs[::-1] if richtung == "ab" else zs
        for z in zs:
            b = self.ausdehnung_streifen(z, achse, quer_max)
            if (schwelle > 0 and b >= schwelle) or (schwelle < 0 and 0 < b <= -schwelle): return float(z)
        return float("nan")
    def querschnitt_flaeche(self, z, **k):
        """Echte Summe der Querschnittsflaechen bei z (m2). NICHT mit der Laser-Hypsometrie vergleichbar (die rastert) - dafuer hypso_ueber."""
        return float(sum(g.area for _, g in self._polys(z)))
    def hypso_ueber(self, z, drehung=98.0, dx=-1.0, dy=-1.0, radius=9.0, raster=1.0, N=60, **k):
        """Wie die Laser-Hypsometrie: Modellpunkte auf ein 1-m-Raster projizieren und Zellen zaehlen, deren Hoehe > z ist (im Umkreis um die Spitze).
        Nur so sind Modell und DOM1 vergleichbar - die Rasterung addiert je nach Umfang 15-25 Zellen gegenueber der echten Flaeche."""
        if not hasattr(self, "_hp"):
            v, fa = self._unterteilt(); self._hp = v[fa].mean(1)
        import render_kern as RK
        return RK.hypso(self._hp, z, drehung, dx, dy, radius, raster, N)
        x = (c * P[:, 0] - s_ * P[:, 1] + dx) / raster; y = (s_ * P[:, 0] + c * P[:, 1] + dy) / raster; N = 60
        ix = np.floor(x + N / 2).astype(int); iy = np.floor(N / 2 - y).astype(int)
        ok = (ix >= 0) & (ix < N) & (iy >= 0) & (iy < N); H = np.zeros((N, N)); np.maximum.at(H, (iy[ok], ix[ok]), P[ok, 2])
        pk = np.unravel_index(np.argmax(H), H.shape); yy, xx = np.mgrid[:N, :N]
        return float(((H > z) & (np.hypot(yy - pk[0], xx - pk[1]) <= radius / raster)).sum()) * raster ** 2
    def grundriss_rechteck(self, z, r=None, **k):
        ps = self._polys(z)
        if r is not None: ps = [(c, g) for c, g in ps if np.hypot(*c) < r]
        if not ps: return {"flaeche": float("nan"), "x": float("nan"), "y": float("nan")}
        b = np.array([self._bounds3(g) for _, g in ps]); x = b[:, 2].max() - b[:, 0].min(); y = b[:, 3].max() - b[:, 1].min()
        return {"flaeche": float(x * y), "x": float(x), "y": float(y)}

def lade_modell(stl, massstab, einheit_mm, zentrierung="huelle"):
    """zentrierung: 'huelle' = x/y auf Huellbox-Mitte (Scans), 'achse' = Koordinaten lassen (Generator baut um die Achse 0,0;
    Anbauten wie ein Eckturm wuerden die Huellbox-Mitte und damit alle Achsmessungen verschieben). z immer auf Boden 0."""
    m = trimesh.load(stl)
    if einheit_mm: m.apply_scale(massstab / 1000.0)
    c = m.bounds.mean(0) if zentrierung == "huelle" else np.zeros(3)
    m.apply_translation([-c[0], -c[1], -m.bounds[0, 2]]); return m

def auswerten(ausdruck, werte):
    try: return float(eval(ausdruck, {"__builtins__": {}}, dict(werte)))
    except Exception as e: raise ValueError(f"Formel '{ausdruck}': {e}")

def messen(tab, m, obj=None, root=None):
    M = Messer(m, obj, root); werte = dict(tab.get("konstanten", {})); offen = dict(tab["messungen"])
    for _ in range(len(offen) + 1):                                   # Messungen duerfen auf andere verweisen ("z": "tuermchen_spitze - 2")
        for name in list(offen):
            spec = dict(offen[name]); typ = spec.pop("typ")
            try: args = {k: (auswerten(v[1:], werte) if isinstance(v, str) and v.startswith("=") else v) for k, v in spec.items()}   # "=formel" verweist auf andere Messungen
            except ValueError: continue
            r = getattr(M, typ)(**args)
            if isinstance(r, dict):
                for k, v in r.items(): werte[f"{name}_{k}"] = v
            else: werte[name] = r
            del offen[name]
    if offen: raise ValueError(f"Messungen nicht aufloesbar: {list(offen)}")
    return werte

def massnachweis(obj, tab, zeilen, root, el, seiten_foto):
    """Schreibt modelle/<objekt>/MASSNACHWEIS.md: was ist womit belegt, was ist Annahme, was Widerspruch - automatisch, nach jedem Lauf."""
    import datetime
    L = [f"# Massnachweis {obj['name']} (automatisch aus masstabelle.json, {datetime.date.today()})", "",
         "Status je Mass: **OK** = Istwert im Sollbereich der Quelle; **WIDERSPRUCH** = Quellen uneins (nicht gemittelt); **FEHLER** = Modell verletzt die Quelle.",
         "Massstab: *dokument/lod2/laser* = absolut; *foto_intern* = bekanntes Mass im selben Foto; *modell* = zirkulaer (nur Richtung belastbar).", "",
         "| Merkmal | Ist | Soll | Quelltyp | Massstab | Status | Quelle |", "|---|---|---|---|---|---|---|"]
    for ok, p, v in zeilen:
        st = "OK" if ok is True else ("WIDERSPRUCH" if ok else "FEHLER")
        L.append(f"| {p['name']} | {v:.2f} | {p['soll'][0]:g}..{p['soll'][1]:g} | {p['quelltyp']} | {p.get('massstab', '-')} | {st} | {p['quelle'].replace('|', '/')} |")
    qt = {}
    for ok, p, v in zeilen: qt.setdefault(p["quelltyp"], []).append(ok is True)
    L += ["", "## Belegt durch", ""] + [f"- **{k}**: {sum(v)} von {len(v)} Pruefungen gruen ({QUELLEN[k]['hinweis']})" for k, v in qt.items()]
    ann = [e for e in el if str(e.get("quelle", "")).startswith("ANNAHME")]
    if el: L += ["", f"## Elemente des Generators: {len(el)} belegt, {len(ann)} Annahmen", ""] + [f"- {e['seite_name']}: {e['element']} - {e['quelle']}" for e in el]
    sides = sorted({e["seite_name"] for e in el if e.get("seite") in ("+x", "-x", "+y", "-y")}) if el else []
    if sides: L += ["", "## Seiten", ""] + [f"- {sn}: {'Fotos vorhanden' if sn in seiten_foto else 'KEIN FOTO - ungeprueft'}" for sn in sides]
    w = [p for ok, p, v in zeilen if ok == "widerspruch"]
    if w: L += ["", "## Offene Widersprueche", ""] + [f"- {p['name']}: {p.get('widerspruch', '')}" for p in w]
    b = tab.get("beobachtungen_offen", [])
    if b: L += ["", "## Beobachtungen ohne Pruefung", ""] + [f"- {x['datum']} {x['wer']}: {x['text']} -> {x.get('naechster_schritt', '')}" for x in b]
    L += ["", "## Grenze", "", "Offene Daten (Laser 1 m, Fotos +-5-10 %, Dokumente mit unklarer Bezugshoehe) beweisen keine Masse auf den Zentimeter.",
          "Dieser Nachweis sagt je Mass, welche Quelle es stuetzt und wie belastbar der Massstab ist; mehr ist ehrlich nicht moeglich."]
    open(os.path.join(root, os.path.dirname(obj["masstabelle"]), "MASSNACHWEIS.md"), "w").write("\n".join(L) + "\n")

def main():
    a = sys.argv[1:]; md = "--md" in a; a = [x for x in a if x != "--md"]
    obj = json.load(open(a[0])); root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(a[0]))))
    stl = a[a.index("--stl") + 1] if "--stl" in a else os.path.join(root, obj["stl"])
    tab = json.load(open(os.path.join(root, obj["masstabelle"])))
    # 1) Tabellen-Lint: Quelle muss das Merkmal sehen koennen
    unzul = []
    for p in tab["pruefungen"]:
        q = QUELLEN.get(p.get("quelltyp"))
        if q is None: unzul.append((p["name"], f"unbekannter Quelltyp '{p.get('quelltyp')}'"))
        elif p.get("merkmal") in q["blind"]: unzul.append((p["name"], f"Quelle '{p['quelltyp']}' ist BLIND fuer '{p['merkmal']}' ({q['hinweis']})"))
        elif p.get("merkmal") not in q["sieht"]: unzul.append((p["name"], f"Merkmal '{p.get('merkmal')}' fuer Quelle '{p['quelltyp']}' nicht freigegeben"))
    if unzul:
        print("TABELLE UNZULAESSIG:"); [print(f"  - {n}: {g}") for n, g in unzul]; sys.exit(2)
    # masse.json: jedes Mass braucht eine Quelle, und die Quelle muss das Merkmal sehen koennen (gleiche Matrix wie fuer Pruefzeilen)
    mp = os.path.join(root, os.path.dirname(obj["masstabelle"]), "masse.json")
    if os.path.exists(mp):
        mm = json.load(open(mp))["masse"]; schlecht = []
        for name, e in mm.items():
            if not e.get("quelle") or not e.get("quelltyp"): schlecht.append(f"{name}: ohne Quelle")
            elif e["quelltyp"] not in QUELLEN: schlecht.append(f"{name}: unbekannter Quelltyp '{e['quelltyp']}'")
        print(f"  MASSE {len(mm)} aus masse.json, alle mit Quelle" if not schlecht else "  MASSE OHNE BELEG: " + "; ".join(schlecht))
        if schlecht: bad += len(schlecht)
    zirk = [p["name"] for p in tab["pruefungen"] if p.get("massstab") == "modell" and p.get("merkmal") not in ("verhaeltnis", "anzahl", "druck")]
    if zirk:
        print("MASSSTAB AUS DEM MODELL (zirkulaer - belegt Richtung, nicht Zahl):"); [print(f"  - {n}") for n in zirk]
        # Sobald es fuer ein Merkmal eine modellfreie Messung gibt, gehoert die zirkulaere Zeile ersetzt (sonst taeuscht sie Widersprueche vor).
        frei = {p.get("merkmal") for p in tab["pruefungen"] if p.get("massstab") in ("dokument", "lod2", "laser", "foto_intern", "foto_kalibriert")}
        ersetzbar = [p["name"] for p in tab["pruefungen"] if p.get("massstab") == "modell" and p.get("merkmal") in frei]
        if ersetzbar: print("  ERSETZBAR (modellfreie Quelle fuer dasselbe Merkmal vorhanden): " + "; ".join(ersetzbar))
    # 2) Messen + Pruefen
    bad = 0
    m = lade_modell(stl, obj.get("stl_massstab", 1), obj.get("stl_einheit_mm", True), obj.get("zentrierung", "huelle")); werte = messen(tab, m, obj, root)
    zeilen, bad = [], 0
    for p in tab["pruefungen"]:
        v = auswerten(p["wert"], werte); lo, hi = p["soll"]; ok = (not np.isnan(v)) and lo <= v <= hi
        if not ok and p.get("status") == "widerspruch": ok = "widerspruch"
        bad += 0 if ok else 1
        zeilen.append((ok, p, v))
    print(f"Pruefstand {obj['name']}  ({stl})")
    for ok, p, v in zeilen:
        print(f"  {'OK    ' if ok is True else 'WIDERS' if ok else 'FEHLER'}  {p['name']:56s} {v:8.2f}  Soll {p['soll'][0]:g}..{p['soll'][1]:g}   [{p['quelltyp']}: {p['quelle'][:70]}]")
    # Element-Belege (Mechanik F9/F5): jedes Element des Generators braucht eine Quelle; Annahmen und unfotografierte Seiten werden gezeigt
    ep = os.path.join(root, obj["elemente"]) if obj.get("elemente") else None
    if ep and os.path.exists(ep):
        el = json.load(open(ep)); seiten_foto = {v.get("seite") for v in obj.get("fotos", {}).values()}; ann = []
        for e in el:
            q = e.get("quelle", "")
            if not q: print(f"  FEHLER  Element OHNE BELEG: {e['seite_name']}: {e['element']}  (Lehre F9: erfundenes Feature)"); bad += 1
            elif q.startswith("ANNAHME"): ann.append(f"{e['seite_name']}: {e['element']}")
        for sn in sorted({e["seite_name"] for e in el if e["seite"] in ("+x", "-x", "+y", "-y")}):
            if sn not in seiten_foto: print(f"  UNGEPRUEFT Seite {sn}: kein Foto dieser Seite in objekt.json (Lehre F5: Mehrflaechen-Audit)")
        print(f"  ELEMENTE {len(el)} belegt" + (f", davon ANNAHMEN {len(ann)}: " + "; ".join(ann) if ann else ""))
    for b in tab.get("beobachtungen_offen", []):
        print(f"  OFFEN   {b['datum']} {b['wer']}: {b['text'][:90]}  -> {b.get('naechster_schritt', '')[:60]}")
    nw = sum(1 for ok, _, _ in zeilen if ok == "widerspruch")
    for ok, p, v in zeilen:
        if ok == "widerspruch": print(f"  WIDERSPRUCH offen: {p['name']}: {p.get('widerspruch', '')[:110]}")
    print("ERGEBNIS:", "alle Pruefungen bestanden" if not bad else f"{bad} Pruefung(en) FEHLGESCHLAGEN - Modell NICHT freigeben",
          f"| {nw} Widerspruch/Widersprueche offen | {len(tab.get('beobachtungen_offen', []))} Beobachtung(en) ohne Pruefung")
    ber = {"stl": stl, "werte": {k: (None if isinstance(v, float) and np.isnan(v) else v) for k, v in werte.items()},
           "pruefungen": [{"name": p["name"], "wert": None if np.isnan(v) else v, "soll": p["soll"], "ok": ok is True, "status": "widerspruch" if ok == "widerspruch" else ("ok" if ok else "fehler")} for ok, p, v in zeilen], "bestanden": bad == 0}
    out = os.path.join(root, os.path.dirname(obj["masstabelle"]), "pruefbericht.json")
    if os.path.exists(out) and "--stl" not in a:                       # Aenderungs-Diff: was hat sich seit dem letzten Lauf bewegt?
        alt = json.load(open(out)).get("werte", {}); ge = []
        for k, v in ber["werte"].items():
            if k in alt and alt[k] is not None and v is not None and abs(v - alt[k]) > max(0.01, 0.01 * abs(alt[k])): ge.append(f"{k} {alt[k]:.2f}->{v:.2f}")
        print("GEAENDERT seit letztem Lauf:", ", ".join(ge) if ge else "nichts", "  (Pruefen: nur die beabsichtigte Eigenschaft? Lehre F8/F3)")
    json.dump(ber, open(out, "w"), indent=1)
    massnachweis(obj, tab, zeilen, root, el if ep and os.path.exists(ep) else [], seiten_foto if ep and os.path.exists(ep) else set())
    if md:
        print("\n| Merkmal | Ist | Soll | Quelle | Quelltyp | Status |\n|---|---|---|---|---|---|")
        for ok, p, v in zeilen: print(f"| {p['name']} | {v:.2f} | {p['soll'][0]:g}..{p['soll'][1]:g} | {p['quelle']} | {p['quelltyp']} | {'OK' if ok is True else 'WIDERSPRUCH' if ok else 'FEHLER'} |")
    sys.exit(1 if bad else 0)

if __name__ == "__main__":
    main()
