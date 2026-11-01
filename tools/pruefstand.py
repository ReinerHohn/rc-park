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

# Was eine Quelle beweisen kann (Erfahrung dieses Projekts; Begruendung in modelle/METHODE_MASSTABELLE.md)
QUELLEN = {
    "laser_dom1":      {"sieht": ["hoehe_flaeche", "grundriss", "anzahl"],              "blind": ["duennes_bauteil", "schlankheit", "fassade", "absolut_hoehe", "verhaeltnis"],
                        "hinweis": "1-m-Raster, nur von oben; Strukturen < ~3 m verschmiert, Nadeln unsichtbar"},
    "laser_punkte":    {"sieht": ["hoehe_flaeche", "grundriss", "anzahl", "schlankheit"], "blind": ["duennes_bauteil", "fassade"],
                        "hinweis": "Rohpunkte >= 8/m2: Kegel ja, Nadel 0,1 m kaum"},
    "lod2":            {"sieht": ["grundriss", "hoehe_flaeche"],                          "blind": ["duennes_bauteil", "schlankheit", "fassade", "absolut_hoehe", "verhaeltnis"],
                        "hinweis": "amtlicher Grundriss + Traufe/First, keine Aufbauten/Details"},
    "foto_verhaeltnis":{"sieht": ["schlankheit", "verhaeltnis", "anzahl", "fassade"],   "blind": ["absolut_hoehe", "grundriss"],
                        "hinweis": "nur Verhaeltnisse (+-5-10 %), absolute Masse nur mit bekanntem Massstab"},
    "foto_vollbild":   {"sieht": ["duennes_bauteil", "schlankheit", "verhaeltnis", "anzahl", "fassade"], "blind": ["absolut_hoehe", "grundriss"],
                        "hinweis": "Vollaufloesung, Massstab aus Modell oder Dokument -> Werte grob, Richtung sicher"},
    "dokument":        {"sieht": ["absolut_hoehe", "anzahl", "grundriss"],               "blind": ["schlankheit", "duennes_bauteil", "fassade"],
                        "hinweis": "Bauforschung/Denkmalamt/Wikipedia; Bezugshoehe oft unklar (60 vs 65 m)"},
    "modell":          {"sieht": ["druck"], "blind": [], "hinweis": "Druckbarkeit, keine Realitaetsaussage"},
}

# ----------------------------------------------------------------------------- generische Messer (alle in Metern)
class Messer:
    def __init__(self, m): self.m = m
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
    def max_z_im_bereich(self, x0, x1, y0, y1, zmax=1e9, **k):
        """Hoechster Punkt innerhalb eines Grundriss-Rechtecks unterhalb zmax (z. B. Eckturm am Sockel, ohne den Schaft darueber)."""
        v = self.m.vertices; s = (v[:, 0] >= x0) & (v[:, 0] <= x1) & (v[:, 1] >= y0) & (v[:, 1] <= y1) & (v[:, 2] < zmax)
        return float(v[s, 2].max()) if s.any() else 0.0
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
        d = np.full(len(us), np.nan); d[ir] = np.abs(loc[:, ax]); wall = np.nanmedian(d); rec = (wall - d) >= tiefe
        n, run = 0, 0
        for rr in list(rec) + [False]:
            if rr: run += 1
            else:
                if min_b / schritt <= run <= max_b / schritt: n += 1
                run = 0
        return float(n)
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
        d = np.full(len(us), np.nan); d[ir] = np.abs(loc[:, ax]); wall = np.nanmedian(d); dev = (d - wall) if art == "vor" else (wall - d) if art == "rueck" else np.abs(d - wall); vor = dev >= hoehe_min
        idx = np.nonzero(vor)[0]
        if len(idx) == 0: return 0.0
        best = 0; start = idx[0]; prev = idx[0]                      # Laeufe, die durch Luecken <= max_luecke (z. B. Stundenmarken) unterbrochen sind, zusammenfassen
        for i in list(idx[1:]) + [None]:
            if i is None or (i - prev - 1) * schritt > max_luecke: best = max(best, prev - start + 1); start = i
            prev = i if i is not None else prev
        return float(best * schritt)
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

def messen(tab, m):
    M = Messer(m); werte = dict(tab.get("konstanten", {})); offen = dict(tab["messungen"])
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
    # 2) Messen + Pruefen
    m = lade_modell(stl, obj.get("stl_massstab", 1), obj.get("stl_einheit_mm", True), obj.get("zentrierung", "huelle")); werte = messen(tab, m)
    zeilen, bad = [], 0
    for p in tab["pruefungen"]:
        v = auswerten(p["wert"], werte); lo, hi = p["soll"]; ok = (not np.isnan(v)) and lo <= v <= hi
        if not ok and p.get("status") == "widerspruch": ok = "widerspruch"
        bad += 0 if ok else 1
        zeilen.append((ok, p, v))
    print(f"Pruefstand {obj['name']}  ({stl})")
    for ok, p, v in zeilen:
        print(f"  {'OK    ' if ok is True else 'WIDERS' if ok else 'FEHLER'}  {p['name']:56s} {v:8.2f}  Soll {p['soll'][0]:g}..{p['soll'][1]:g}   [{p['quelltyp']}: {p['quelle'][:70]}]")
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
    if md:
        print("\n| Merkmal | Ist | Soll | Quelle | Quelltyp | Status |\n|---|---|---|---|---|---|")
        for ok, p, v in zeilen: print(f"| {p['name']} | {v:.2f} | {p['soll'][0]:g}..{p['soll'][1]:g} | {p['quelle']} | {p['quelltyp']} | {'OK' if ok is True else 'WIDERSPRUCH' if ok else 'FEHLER'} |")
    sys.exit(1 if bad else 0)

if __name__ == "__main__":
    main()
