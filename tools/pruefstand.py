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

# Messarten, die Struktur zaehlen/messen (Oeffnungen, Nischen, Elemente je Band): Merkmal nur anzahl|fassade + Foto-Zaehlprotokoll (Register CB)
STRUKTUR_TYPEN = {"flaeche_oeffnungen", "ebene_oeffnungen", "ebene_vorspruenge", "nischen_anzahl", "anzahl_im_band"}

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
    "foto_freiraum":   {"sieht": ["fassade", "freiraum"], "blind": ["absolut_hoehe", "anzahl", "schlankheit", "duennes_bauteil"],
                        "hinweis": "Sichtstrahlen Kamera->Punkt der dichten Fotowolke (fused.ply.vis) gegen das Modell (tools/freiraum_pruefen.py): Modellmaterial, durch das >= 3 Kameras sehen; "
                                   "sieht Durchgaenge/Arkaden/Nischen, blind hinter Glas/Jalousien und wo keine Kamera hinsieht (Scan2LoD3-Prinzip, Register 5.11.)"},
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
    def freiraum_offen(self, ordner, klasse="oeffnung", **k):
        """Flaeche (m2) gesehenen Freiraums OHNE Modelloeffnung (tools/freiraum_pruefen.py -> freiraum_fassaden.py --stl -> freiraum_oeffnungen.py, Ergebnisse in <ordner>).
        Gilt nur, wenn die Auswertung zu DIESEM Modell gehoert (Volumen gleich auf 0,5 %), sonst nan (= Pruefung faellt durch, Auswertung neu rechnen)."""
        d = ordner if os.path.isabs(ordner) else os.path.join(self.root, os.path.dirname(self.obj["masstabelle"]), ordner)
        try: fr = json.load(open(os.path.join(d, "freiraum.json"))); E = json.load(open(os.path.join(d, "elemente_freiraum.json")))
        except (OSError, ValueError): return float("nan")
        v = fr.get("modell_volumen_m3"); vm = abs(float(self.m.volume))
        if not v or abs(vm / v - 1) > 0.005: return float("nan")
        return float(sum((e["u1"] - e["u0"]) * (e["z1"] - e["z0"]) for F in E["fassaden"].values() for e in F["elemente"] if e["klasse"] == klasse and "freiraum_oeffnungen" in e.get("quelle", "")))
    def wasserdicht(self, **k): return 1.0 if self.m.is_watertight else 0.0
    def druck_teile_ueberhang(self, ordner, winkel=60.0, **k):
        """Groesster Ueberhang-Anteil (Flaeche mit Normale steiler als winkel nach unten / Gesamtflaeche, ohne Bettflaeche) ueber alle Druckteile aus
        tools/druck_teilung.py (<ordner>/teilung.json). Gilt nur fuer DIESES Modell (modell_volumen_m3 gleich auf 0,5 %); sonst (keine/alte Teilung)
        der Anteil des UNGETEILTEN Modells aufrecht = Pruefung faellt durch, bis die Teilung zum Modell passt."""
        d = ordner if os.path.isabs(ordner) else os.path.join(self.root, ordner)
        try:
            T = json.load(open(os.path.join(d, "teilung.json"))); v = T.get("modell_volumen_m3"); vm = abs(float(self.m.volume))
            if v and abs(vm / v - 1) <= 0.005: return float(T["max_ueberhang_anteil"])
        except (OSError, ValueError, KeyError): pass
        N = self.m.face_normals; C = self.m.triangles_center; A = self.m.area_faces; zb = self.m.bounds[0, 2]
        ov = (N[:, 2] < -np.cos(np.radians(90 - winkel))) & (C[:, 2] > zb + 0.05); return float(A[ov].sum() / A.sum())
    def wandstaerke(self, n=30000, quantil=1.0, grenze_m=0.0348, seed=0, **k):
        """Wandstaerke-Vorcheck (Druck): n Flaechenstichproben, Strahl entlang der Innennormalen bis zur naechsten Gegenflaeche (Moeller-Trumbore auf der GPU,
        torch; CPU-Rueckfall). Rueckgabe {pq = Quantil der Dicke (m), anteil_unter = Anteil Stichproben mit Dicke < grenze_m (Standard 0,4 mm in H0 1:87),
        ohne_treffer = Anteil ohne Gegenflaeche (offenes Netz)}. Spitzen (Kegel, Grate) liefern lokal kleine Dicken - deshalb Quantil statt Minimum."""
        import torch
        dev = "cuda" if torch.cuda.is_available() else "cpu"
        P, fi = trimesh.sample.sample_surface(self.m, n, seed=seed); Nn = self.m.face_normals[fi]
        T = torch.tensor(self.m.triangles, dtype=torch.float32, device=dev); v0, e1, e2 = T[:, 0], T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]
        O = torch.tensor(P - Nn * 1e-4, dtype=torch.float32, device=dev); D = torch.tensor(-Nn, dtype=torch.float32, device=dev); t_best = torch.full((len(P),), float("inf"), device=dev)
        for i in range(0, len(P), 1024):
            o, d = O[i:i + 1024, None, :], D[i:i + 1024, None, :]
            pv = torch.cross(d.expand(-1, len(T), -1), e2[None].expand(len(o), -1, -1), dim=2); det = (e1[None] * pv).sum(2)
            inv = 1.0 / torch.where(det.abs() < 1e-12, torch.full_like(det, 1e-12), det); tv = o - v0[None]
            uu = (tv * pv).sum(2) * inv; qv = torch.cross(tv, e1[None].expand(len(o), -1, -1), dim=2); vv = (d * qv).sum(2) * inv; tt = (e2[None] * qv).sum(2) * inv
            ok = (det.abs() > 1e-12) & (uu >= 0) & (vv >= 0) & (uu + vv <= 1) & (tt > 1e-5)
            t_best[i:i + 1024] = torch.where(ok, tt, torch.full_like(tt, float("inf"))).min(1).values
        t = t_best.cpu().numpy(); fin = np.isfinite(t)
        return {"pq": float(np.percentile(t[fin], quantil)) if fin.any() else float("nan"), "anteil_unter": float((t[fin] < grenze_m).mean()) if fin.any() else float("nan"), "ohne_treffer": float(1 - fin.mean())}
    def koerper_anzahl(self, **k): return float(len(self.m.split(only_watertight=False)))
    def nischen_anzahl(self, seite, z, halb, tiefe, schritt=0.05, min_b=0.3, max_b=2.0, mitte=0.0, wand=None, **k):
        """Zaehlt Rueckspruenge >= tiefe entlang einer Fassade (Strahlen von aussen), Breite min_b..max_b. mitte = Querkoordinate der Fenstermitte (Standard 0 = Turmachse)."""
        ax = 0 if seite[1] == "x" else 1; sgn = 1.0 if seite[0] == "+" else -1.0
        us = np.arange(-halb, halb + 1e-6, schritt) + mitte; org = np.zeros((len(us), 3)); org[:, ax] = sgn * 40.0; org[:, 1 - ax] = us; org[:, 2] = z
        dr = np.zeros_like(org); dr[:, ax] = -sgn
        loc, ir, _ = self.m.ray.intersects_location(org, dr, multiple_hits=False)
        d = np.full(len(us), np.nan); d[ir] = np.abs(loc[:, ax]); wall = np.nanmedian(d) if wand is None else wand; d = np.where(np.isnan(d), -1e3, d); rec = (wall - d) >= tiefe   # Durchblick (kein Treffer) = tiefe Nische; wand = Wandebene (|Tiefe|), sonst Median (versagt, wenn Oeffnungen > 50 % der Strecke)
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
        wand = np.nanpercentile(d, 15); relief = (d > wand + 0.03); anteil = np.array([relief[i][~np.isnan(d[i])].mean() if (~np.isnan(d[i])).any() else np.nan for i in range(len(zs))])   # Wandebene = tiefes Ende (p15), nicht Median: grosse Quader fuellen > 50 % des Fensters (Register CI)
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
    def ebene_abstand(self, o, n, z, u0, u1, vor=3.0, schritt=0.04, quantil=10.0, **k):
        """Lage der vordersten Flaeche hinter einer beliebigen Ebene (o = Punkt xy, n = Aussennormale xy, Modellkoordinaten; u entlang d = (-n_y, n_x); z ueber
        Boden im Pruefstandrahmen): Strahlen ab `vor` m vor der Ebene entlang -n, Rueckgabe = Quantil (Standard p10) der Trefferabstaende minus `vor`
        (0 = Flaeche in der Ebene, > 0 = dahinter, < 0 = davor; nan ohne Treffer). Reine Lage-/Abstandsmessung (z. B. Rueckwand, Dachueberstand), zaehlt nichts."""
        o = np.array(o, float); n = np.array(n, float); n = n / np.linalg.norm(n); d = np.array([-n[1], n[0]])
        us = np.arange(u0, u1 + 1e-6, schritt); org = np.zeros((len(us), 3)); org[:, :2] = o + vor * n + us[:, None] * d; org[:, 2] = z
        dr = np.zeros_like(org); dr[:, :2] = -n
        loc, ir, _ = self.m.ray.intersects_location(org, dr, multiple_hits=False)
        if not len(ir): return float("nan")
        return float(np.percentile((loc[:, :2] - org[ir, :2]) @ (-n), quantil) - vor)
    def ebene_vorspruenge(self, o, n, z, u0, u1, hoehe_min=0.3, vor=3.0, schritt=0.02, min_b=0.1, max_b=1.5, **k):
        """Zaehlt VORSPRUENGE (Konsolen, Lisenen, Pfosten) vor einer beliebigen Fassadenebene (o = Punkt xy, n = Aussennormale xy, Modellkoordinaten; u entlang
        d = (-n_y, n_x); z ueber Boden im Pruefstandrahmen): Strahlen ab `vor` m vor der Ebene entlang -n; Grund = p90 der Trefferabstaende (hinterste haeufige Flaeche);
        Vorsprung = Treffer >= hoehe_min vor dem Grund; gezaehlt werden Laeufe min_b..max_b, die den Streckenrand NICHT beruehren (angeschnittene Teile zaehlen nicht,
        wie 'teil' im Foto-Zaehlprotokoll). Gegenstueck zu ebene_oeffnungen (Runde 5, Balkonkonsolen). Rueckgabe {anzahl, breite_median, grund_abstand}."""
        o = np.array(o, float); n = np.array(n, float); n = n / np.linalg.norm(n); d = np.array([-n[1], n[0]])
        us = np.arange(u0, u1 + 1e-6, schritt); org = np.zeros((len(us), 3)); org[:, :2] = o + vor * n + us[:, None] * d; org[:, 2] = z
        dr = np.zeros_like(org); dr[:, :2] = -n
        loc, ir, _ = self.m.ray.intersects_location(org, dr, multiple_hits=False)
        t = np.full(len(us), np.nan); t[ir] = (loc[:, :2] - org[ir, :2]) @ (-n)
        if not np.isfinite(t).any(): return {"anzahl": 0.0, "breite_median": 0.0, "grund_abstand": float("nan")}
        grund = float(np.nanpercentile(t, 90)); vs = np.isfinite(t) & (t <= grund - hoehe_min)
        laeufe = []; run = 0; i0 = 0
        for i, v in enumerate(list(vs) + [False]):
            if v:
                if run == 0: i0 = i
                run += 1
            else:
                if run and min_b <= run * schritt <= max_b and i0 > 0 and i < len(us): laeufe.append(run * schritt)
                run = 0
        return {"anzahl": float(len(laeufe)), "breite_median": float(np.median(laeufe)) if laeufe else 0.0, "grund_abstand": grund - vor}
    def ebene_oeffnungen(self, o, n, z, u0, u1, tiefe=0.5, vor=3.0, schritt=0.04, min_b=0.3, max_b=8.0, rand=0.5, schief=0.1, **k):
        """Oeffnungen entlang einer beliebigen FASSADENEBENE (o = Punkt xy, n = Aussennormale xy, Modellkoordinaten; u = Strecke entlang d = (-n_y, n_x); z = Hoehe ueber
        Boden im Pruefstandrahmen). Strahlen starten `vor` m vor der Ebene entlang -n; Ebene = p10 der Trefferabstaende (vorderste haeufige Flaeche); offen = Treffer
        >= tiefe hinter der Ebene oder kein Treffer; gezaehlt werden Laeufe min_b..max_b. Randregel: ein Lauf, der den Ebenenrand beruehrt (<= `rand` m davor, nur Eckpfeiler)
        und dessen Rueckflaeche nicht parallel zur Ebene liegt (Abstandsspanne p95-p5 > `schief` m) oder nur aus Nicht-Treffern besteht, ist die Nachbarfassade/der Gebaeudeabschluss
        hinter der Ecke, kein Durchblick - ein echter Bogen hat eine ebene, parallele Rueckwand. Gewaehlt statt fester max_tiefe, weil die Nebenflaeche (2,3 m tief) und
        echte Bogenrueckwaende (3 m) sich in der Tiefe nicht trennen, in der Parallelitaet schon. Rueckgabe {anzahl, breite_median, breite_max, ebene_abstand}."""
        o = np.array(o, float); n = np.array(n, float); n = n / np.linalg.norm(n); d = np.array([-n[1], n[0]])
        us = np.arange(u0, u1 + 1e-6, schritt); org = np.zeros((len(us), 3)); org[:, :2] = o + vor * n + us[:, None] * d; org[:, 2] = z
        dr = np.zeros_like(org); dr[:, :2] = -n
        loc, ir, _ = self.m.ray.intersects_location(org, dr, multiple_hits=False)
        t = np.full(len(us), np.nan); t[ir] = (loc[:, :2] - org[ir, :2]) @ (-n)
        ebene = float(np.nanpercentile(t, 10)) if np.isfinite(t).any() else float("nan")
        offen = np.isnan(t) | (t > ebene + tiefe)
        laeufe = []; run = 0; i0 = 0
        for i, off in enumerate(list(offen) + [False]):
            if off:
                if run == 0: i0 = i
                run += 1
            else:
                if run and min_b <= run * schritt <= max_b:
                    s = t[i0:i]; am_rand = (us[i0] - u0 <= rand) or (u1 - us[i - 1] <= rand); ok = s[np.isfinite(s)]
                    kein_durchblick = ok.size == 0 or (np.percentile(ok, 95) - np.percentile(ok, 5) > schief)
                    if not (am_rand and kein_durchblick): laeufe.append(run * schritt)
                run = 0
        return {"anzahl": float(len(laeufe)), "breite_median": float(np.median(laeufe)) if laeufe else 0.0, "breite_max": float(max(laeufe)) if laeufe else 0.0, "ebene_abstand": ebene}
    def oeffnung_durchblick(self, seite, z, quer, pfosten, tiefe_min=1.0, **k):
        """Ist eine Oeffnung OFFEN (Durchblick in einen Innenraum) oder nur eine flache Nische? Strahl senkrecht auf die Flaeche bei (quer, z);
        Flaechenebene = Median der Treffer an den Pfosten quer +- pfosten. Rueckgabe {"tiefe": Abstand Ebene -> erster Treffer hinter der Oeffnung (m),
        "durchgehend": 1 wenn tiefe >= tiefe_min}. Register CD (Tuermchen-Arkaden waren 0,35-m-Nischen: Bogen doppelt/versetzt im Viewer)."""
        ax = 0 if seite[1] == "x" else 1; sgn = 1.0 if seite[0] == "+" else -1.0
        qs = np.array([quer, quer - pfosten, quer + pfosten]); org = np.zeros((3, 3)); org[:, ax] = sgn * 40.0; org[:, 1 - ax] = qs; org[:, 2] = z; dr = np.zeros_like(org); dr[:, ax] = -sgn
        loc, ir, _ = self.m.ray.intersects_location(org, dr, multiple_hits=False); d = np.full(3, np.nan); d[ir] = sgn * loc[:, ax]
        if not np.isfinite(d[1:]).any(): return {"tiefe": float("nan"), "durchgehend": 0.0}
        ebene = float(np.nanmedian(d[1:])); t = float(ebene - d[0]) if np.isfinite(d[0]) else 99.0
        return {"tiefe": t, "durchgehend": 1.0 if t >= tiefe_min else 0.0}
    def _band_fenster(self, koerper):
        """Hoehenfenster eines Bandes 'offen' aus dem Wolkenprofil des Objekts (profile_baender_<koerper>.json): unten Bandanfang - 0,2, oben Unterseite der
        naechsten auskragenden Platte - 0,03; quer = Profilachse. Damit misst eine Pruefung dasselbe Bauteil auch, wenn die Wolke die Baender anders schneidet (Register CG)."""
        od = os.path.join(self.root, os.path.dirname(self.obj["masstabelle"])); P = json.load(open(os.path.join(od, f"profile_baender_{koerper}.json")))
        B = P["baender"]; o = [b for b in B if b["klasse"] == "offen"][0]; deck = [b["z0"] for b in B if b["z0"] >= o["z1"] - 1e-6 and b["r"] >= o["r"] + 0.2]
        return o["z0"] - 0.2, (min(deck) if deck else o["z1"]) - 0.03, P.get("achse", {}).get("quer", 0.0)
    def oeffnung_form(self, seite, halb, quer=None, z0=None, z1=None, band_koerper=None, tiefe=0.2, frac=0.85, schritt=0.02, **k):
        """Bogenform einer Oeffnung: Breite bei frac der Oeffnungshoehe / Breite bei 30 %. Rundbogen (Halbkreis) ~0,75, flacher Segmentbogen ~1,0.
        Ebene = 90-%-Quantil der Treffer im Fenster; offen = kein Treffer oder >= tiefe dahinter. Register CF (Tuermchen 'kleine Boegelchen')."""
        if band_koerper: z0, z1, q_ = self._band_fenster(band_koerper); quer = q_ if quer is None else quer
        ax = 0 if seite[1] == "x" else 1; sgn = 1.0 if seite[0] == "+" else -1.0
        us = np.arange(quer - halb, quer + halb + 1e-6, schritt); zs = np.arange(z0, z1 + 1e-6, schritt); U, Z = np.meshgrid(us, zs)
        org = np.zeros((U.size, 3)); org[:, ax] = sgn * 40.0; org[:, 1 - ax] = U.ravel(); org[:, 2] = Z.ravel(); dr = np.zeros_like(org); dr[:, ax] = -sgn
        loc, ir, _ = self.m.ray.intersects_location(org, dr, multiple_hits=False); d = np.full(U.size, np.nan); d[ir] = sgn * loc[:, ax]; d = d.reshape(U.shape)
        ebene = np.nanpercentile(d, 90); offen = np.isnan(d) | (d < ebene - tiefe)
        iq = int(np.argmin(np.abs(us - quer))); col = offen[:, iq]
        if not col.any(): return {"verhaeltnis": 0.0, "hoehe": 0.0, "breite": 0.0}
        im = int(np.argmax(col)) if not col[len(col) // 2] else len(col) // 2
        a = im; b = im
        while a > 0 and col[a - 1]: a -= 1
        while b < len(col) - 1 and col[b + 1]: b += 1
        h = (b - a) * schritt
        def breite(zi):
            row = offen[zi]; l = r = iq
            if not row[iq]: return 0.0
            while l > 0 and row[l - 1]: l -= 1
            while r < len(row) - 1 and row[r + 1]: r += 1
            return (r - l) * schritt
        w_lo = breite(a + int(0.3 * (b - a))); w_hi = breite(a + int(frac * (b - a)))
        return {"verhaeltnis": float(w_hi / w_lo) if w_lo else 0.0, "hoehe": float(h), "breite": float(w_lo)}
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
    def nische_breite(self, seite, z, halb, tiefe, mitte=0.0, schritt=0.05, wand=None, **k):
        """Breite (m) des BREITESTEN zusammenhaengenden Rueckversprungs >= tiefe entlang einer Fassade bei Hoehe z (z. B. Bogenoeffnung, Durchgang)."""
        ax = 0 if seite[1] == "x" else 1; sgn = 1.0 if seite[0] == "+" else -1.0
        us = np.arange(-halb, halb + 1e-6, schritt) + mitte; org = np.zeros((len(us), 3)); org[:, ax] = sgn * 40.0; org[:, 1 - ax] = us; org[:, 2] = z
        dr = np.zeros_like(org); dr[:, ax] = -sgn
        loc, ir, _ = self.m.ray.intersects_location(org, dr, multiple_hits=False)
        d = np.full(len(us), np.nan); d[ir] = np.abs(loc[:, ax]); wall = np.nanmedian(d) if wand is None else wand; d = np.where(np.isnan(d), -1e3, d); rec = (wall - d) >= tiefe
        best, run = 0, 0
        for rr in list(rec) + [False]:
            if rr: run += 1
            else: best = max(best, run); run = 0
        return float(best * schritt)
    def oeffnung_oberkante(self, seite, quer, z0, z1, tiefe, schritt=0.05, **k):
        """Hoechste Hoehe z, bis zu der die Fassade bei Querlage 'quer' ab z0 DURCHGEHEND um >= tiefe zurueckspringt (Scheitel einer Toroeffnung)."""
        zs, d = self._front_profil(seite, quer, z0, z1, schritt=schritt); wall = np.nanmax(d); rec = (wall - np.where(np.isnan(d), -1e3, d)) >= tiefe
        if not rec[0]: return float("nan")
        n = 0
        while n < len(rec) and rec[n]: n += 1
        return float(zs[n - 1])
    def tiefe_bei(self, seite, z, quer, **k):
        """Tiefe |x| bzw. |y| der ersten Modellflaeche von aussen bei Hoehe z und Querlage quer (ein Strahl); nan ohne Treffer. Zwei Aufrufe liefern einen Vorsprung (Erker gegen Wand)."""
        ax = 0 if seite[1] == "x" else 1; sgn = 1.0 if seite[0] == "+" else -1.0
        org = np.zeros((1, 3)); org[0, ax] = sgn * 40.0; org[0, 1 - ax] = quer; org[0, 2] = z; dr = np.zeros((1, 3)); dr[0, ax] = -sgn
        loc, ir, _ = self.m.ray.intersects_location(org, dr, multiple_hits=False)
        return float(abs(loc[0, ax])) if len(ir) else float("nan")
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
    # 1b) Struktur-Lint (Register CB, 2026-11-03: 'zwei Boegen je Flaeche' kam aus der Wolke, getarnt als Merkmal 'schlankheit', Soll aus derselben Wolke):
    #     (i) Messarten, die ZAEHLEN/STRUKTUR messen, duerfen nur Merkmal anzahl|fassade tragen (sonst umgeht ein falsches Etikett die Quellen-Matrix);
    #     (ii) eine Pruefung auf anzahl|fassade darf nicht aus einer Datei stammen, die der Generator selbst liest (Selbstbezug = Modell besteht per Konstruktion);
    #     (iii) Struktur-Pruefungen brauchen ein Foto-Zaehlprotokoll (messprotokoll/Z-*.json, tools/foto_zaehlung.py), dessen Ergebnis im Soll liegt.
    gen_json = set(); ohne_zaehl = []
    try:
        gp = re.search(r"[\w./-]+\.py", obj.get("generator", "")); gp = os.path.join(root, gp.group(0)) if gp else None
        if gp and os.path.exists(gp): gen_json = set(re.findall(r"[\w.-]+\.json", open(gp).read()))
    except Exception: pass
    for p in tab["pruefungen"]:
        if p.get("status") == "widerspruch" and False: continue
        mk = max((k for k in tab.get("messungen", {}) if p["wert"] == k or p["wert"].startswith(k + "_")), key=len, default=None)
        typ = tab["messungen"][mk].get("typ") if mk else None
        if typ in STRUKTUR_TYPEN:
            if p.get("merkmal") not in ("anzahl", "fassade"): unzul.append((p["name"], f"Messart '{typ}' zaehlt/misst Struktur - Merkmal muss 'anzahl' oder 'fassade' sein, steht aber '{p.get('merkmal')}' (Etikettenumgehung der Quellen-Matrix)"))
            pid = os.path.basename(str(p.get("protokoll", ""))); zp = os.path.join(root, os.path.dirname(obj["masstabelle"]), "messprotokoll", pid.replace(".json", "") + ".json")
            if pid.startswith("Z-"):                                                          # Zaehlprotokoll angegeben: es MUSS existieren und zum Soll passen
                if not os.path.exists(zp): unzul.append((p["name"], f"Zaehlprotokoll {pid} fehlt"))
                else:
                    z = json.load(open(zp)); je = z.get("ergebnis", {}).get("je_flaeche")
                    if z.get("typ") != "zaehlung" or je is None: unzul.append((p["name"], f"Protokoll {pid} ist kein Zaehlprotokoll"))
                    elif p["wert"].endswith("_anzahl") and p.get("status") != "widerspruch" and not (p["soll"][0] <= je <= p["soll"][1]): unzul.append((p["name"], f"Soll {p['soll']} widerspricht dem Zaehlprotokoll {pid} (gezaehlt {je})"))
            else: ohne_zaehl.append(p["name"])
        if p.get("merkmal") in ("anzahl", "fassade") and os.path.basename(str(p.get("protokoll", ""))) in gen_json:
            unzul.append((p["name"], f"SELBSTBEZUG: Quelle '{p.get('protokoll')}' wird vom Generator selbst gelesen - Pruefung beweist nichts"))
    if ohne_zaehl and not unzul: print(f"  HINWEIS Altbestand: {len(ohne_zaehl)} Struktur-Pruefung(en) ohne Foto-Zaehlprotokoll (Z-*) - nachziehen: " + "; ".join(n[:50] for n in ohne_zaehl[:6]))
    if unzul:
        print("TABELLE UNZULAESSIG:"); [print(f"  - {n}: {g}") for n, g in unzul]; sys.exit(2)
    # masse.json: jedes Mass braucht eine Quelle, und die Quelle muss das Merkmal sehen koennen (gleiche Matrix wie fuer Pruefzeilen)
    mp = os.path.join(root, os.path.dirname(obj["masstabelle"]), "masse.json"); masse_bad = 0
    if os.path.exists(mp):
        mm = json.load(open(mp))["masse"]; schlecht = []
        for name, e in mm.items():
            if not e.get("quelle") or not e.get("quelltyp"): schlecht.append(f"{name}: ohne Quelle")
            elif e["quelltyp"] not in QUELLEN: schlecht.append(f"{name}: unbekannter Quelltyp '{e['quelltyp']}'")
        print(f"  MASSE {len(mm)} aus masse.json, alle mit Quelle" if not schlecht else "  MASSE OHNE BELEG: " + "; ".join(schlecht))
        masse_bad = len(schlecht)                                                # zaehlt in das Ergebnis (frueher ging die Zahl durch bad = 0 weiter unten verloren)
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
    zeilen, bad = [], masse_bad
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
    # Werkzeug-Nachweis: Kanten-Schleife muss einen Teilversatz finden und darf nichts erfinden (tools/kanten_nulltest.py, Register BX). Fehlt die Datei: nur Hinweis.
    kp = os.path.join(root, os.path.dirname(obj["masstabelle"]), "audit", "kanten_nulltest.json")
    if os.path.exists(kp):
        kn = json.load(open(kp))
        if kn.get("bestanden"): print(f"  OK      Kanten-Nulltest ({kn['stand']}): Teilversatz {kn['versatz_m']} m in {kn['gefunden_anteil']:.0%} der Fotos gefunden, Wiederholbarkeit {kn['rausch_max_px']} px - Grenze: {kn['grenze_der_methode'][:60]}")
        else: print(f"  FEHLER  Kanten-Nulltest NICHT bestanden ({kn['stand']}): gefunden {kn['gefunden_anteil']:.0%}, wiederholbar {kn['wiederholbar']} - Schleife nicht als Beleg verwenden"); bad += 1
    else: print("  UNGEPRUEFT Kanten-Schleife: audit/kanten_nulltest.json fehlt (tools/kanten_nulltest.py laufen lassen)")
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
    bericht_extra = a[a.index("--bericht") + 1] if "--bericht" in a else None          # Stufen-Tor (qualitaetsstufen): Bericht woandershin, Objektbericht/MASSNACHWEIS unberuehrt
    if bericht_extra:
        json.dump(ber, open(bericht_extra, "w"), indent=1); sys.exit(1 if bad else 0)
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
