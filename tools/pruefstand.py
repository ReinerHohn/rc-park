#!/usr/bin/env python3
"""pruefstand.py - GENERISCHER Abnahme-Pruefstand: misst ein STL gegen die Masstabelle eines Objekts.

  /media/oem/scan/venv-seg/bin/python -W ignore -I tools/pruefstand.py modelle/<objekt>/objekt.json [--stl pfad] [--md]
Exit 0 = alle Pruefungen bestanden, 1 = Fehlschlag, 2 = Tabelle unzulaessig (Quelle blind fuer Merkmal, Formelfehler).

Die Tabelle (masstabelle.json) enthaelt KEINEN Code: nur benannte Messungen (generische Messer unten), Pruefungen mit
Sollbereich + Quelle + Quelltyp + Merkmalstyp, offene Beobachtungen. Dieser Pruefstand kennt, was jede Quelle sehen kann
(QUELLEN). Eine Pruefung, deren Quelle fuer ihr Merkmal blind ist, wird ABGELEHNT (Exit 2) - das war die Wurzel des
Martinstor-Fehlers (Nadelhoehe aus Laser DOM1). Masse immer in Metern, STL wird auf Massstab/Mitte/Boden normiert.
"""
import sys, os, json, numpy as np, trimesh

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
        p, _ = s.to_2D(); return [(np.array(g.centroid.coords[0]), g) for g in p.polygons_full]
    @staticmethod
    def _diam(g): return 2 * np.sqrt(g.area / np.pi)
    def hoehe_max(self, **k): return float(self.m.extents[2])
    def lokales_max_abseits(self, zmin, ax, ay, **k):
        v = self.m.vertices; s = (v[:, 2] > zmin) & (np.abs(v[:, 0]) > ax) & (np.abs(v[:, 1]) > ay)
        return float(v[s, 2].max()) if s.any() else float("nan")
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
    def grundriss_rechteck(self, z, **k):
        ps = self._polys(z)
        if not ps: return {"flaeche": float("nan"), "x": float("nan"), "y": float("nan")}
        b = np.array([g.bounds for _, g in ps]); x = b[:, 2].max() - b[:, 0].min(); y = b[:, 3].max() - b[:, 1].min()
        return {"flaeche": float(x * y), "x": float(x), "y": float(y)}

def lade_modell(stl, massstab, einheit_mm):
    m = trimesh.load(stl)
    if einheit_mm: m.apply_scale(massstab / 1000.0)
    c = m.bounds.mean(0); m.apply_translation([-c[0], -c[1], -m.bounds[0, 2]]); return m

def auswerten(ausdruck, werte):
    try: return float(eval(ausdruck, {"__builtins__": {}}, dict(werte)))
    except Exception as e: raise ValueError(f"Formel '{ausdruck}': {e}")

def messen(tab, m):
    M = Messer(m); werte = dict(tab.get("konstanten", {})); offen = dict(tab["messungen"])
    for _ in range(len(offen) + 1):                                   # Messungen duerfen auf andere verweisen ("z": "tuermchen_spitze - 2")
        for name in list(offen):
            spec = dict(offen[name]); typ = spec.pop("typ")
            try: args = {k: (auswerten(v, werte) if isinstance(v, str) and k != "seite" else v) for k, v in spec.items()}
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
    m = lade_modell(stl, obj.get("stl_massstab", 1), obj.get("stl_einheit_mm", True)); werte = messen(tab, m)
    zeilen, bad = [], 0
    for p in tab["pruefungen"]:
        v = auswerten(p["wert"], werte); lo, hi = p["soll"]; ok = (not np.isnan(v)) and lo <= v <= hi; bad += 0 if ok else 1
        zeilen.append((ok, p, v))
    print(f"Pruefstand {obj['name']}  ({stl})")
    for ok, p, v in zeilen:
        print(f"  {'OK    ' if ok else 'FEHLER'}  {p['name']:56s} {v:8.2f}  Soll {p['soll'][0]:g}..{p['soll'][1]:g}   [{p['quelltyp']}: {p['quelle'][:70]}]")
    for b in tab.get("beobachtungen_offen", []):
        print(f"  OFFEN   {b['datum']} {b['wer']}: {b['text'][:90]}  -> {b.get('naechster_schritt', '')[:60]}")
    print("ERGEBNIS:", "alle Pruefungen bestanden" if not bad else f"{bad} Pruefung(en) FEHLGESCHLAGEN - Modell NICHT freigeben",
          f"| {len(tab.get('beobachtungen_offen', []))} Beobachtung(en) ohne Pruefung")
    ber = {"stl": stl, "werte": {k: (None if isinstance(v, float) and np.isnan(v) else v) for k, v in werte.items()},
           "pruefungen": [{"name": p["name"], "wert": None if np.isnan(v) else v, "soll": p["soll"], "ok": bool(ok)} for ok, p, v in zeilen], "bestanden": bad == 0}
    out = os.path.join(root, os.path.dirname(obj["masstabelle"]), "pruefbericht.json"); json.dump(ber, open(out, "w"), indent=1)
    if md:
        print("\n| Merkmal | Ist | Soll | Quelle | Quelltyp | Status |\n|---|---|---|---|---|---|")
        for ok, p, v in zeilen: print(f"| {p['name']} | {v:.2f} | {p['soll'][0]:g}..{p['soll'][1]:g} | {p['quelle']} | {p['quelltyp']} | {'OK' if ok else 'FEHLER'} |")
    sys.exit(1 if bad else 0)

if __name__ == "__main__":
    main()
