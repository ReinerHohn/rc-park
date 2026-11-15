#!/usr/bin/env python3
"""kette_insel_pruefen.py <objekt.json> <sparse-ordner> [--anteil 0.05] [--gruppe 4] [--anker eigen] - Bildketten OHNE Fremdstuetze finden (Insel-Ketten).

Lehre Schwabentor v3 15.11.2026: der Drohnenclip NW-Mt7ryZ8c fliegt vom Tor ~500 m ueber die Stadt bis hinter das Muenster. Nur das erste Bild sieht das Tor.
Der Mapper haengte die restlichen 22 Bilder als Kette an dieses eine Bild; ihr Massstab ist dabei zusammengefallen (Flugweg 27 m statt ~500 m). Folge: eine
Miniaturstadt aus 18 000 Punkten schwebt in 25-32 m Hoehe um den Turm (der "schwebende Faecher" der dichten Wolke). kamera_plausibel.py (unter Gelaende)
und dicht_bildwahl.py (Objektzylinder) sehen das nicht - die falschen Punkte liegen ja IM Objektzylinder.
Pruefung: je Bild der Anteil seiner 3D-Punkte, die auch ein Bild einer ANDEREN Quelle sieht (Quelle = Namensteil vor '__vf_' bzw. vor '__').
Anteil < --anteil = Bild haengt nur an der eigenen Kette, Lage und Massstab sind nicht unabhaengig belegt. >= --gruppe solche Bilder einer Quelle = rc 3.
Quellen aus --anker (Standard 'eigen': eigene Fotos mit GPS, die lage_gps_pruefen.py belegt) werden nur als Hinweis gezaehlt, nie ausgeschlossen.
Schreibt audit/kette_insel.json ('ausschliessen': Bildnamen ohne Endung; wolke_neu_fusionieren.py nimmt sie mit heraus).
  /media/oem/scan/venv-colmap/bin/python -I tools/kette_insel_pruefen.py modelle/<obj>/objekt.json /media/oem/scan/rc-park_daten/<obj>/pipe/dicht/sparse
"""
import sys, os, json, collections


def main():
    a = sys.argv[1:]
    if len(a) < 2: sys.exit(__doc__)
    import pycolmap
    opt = lambda n, d: a[a.index(n) + 1] if n in a else d
    anteil, gruppe, anker = float(opt("--anteil", 0.05)), int(opt("--gruppe", 4)), set(opt("--anker", "eigen").split(","))
    od = os.path.dirname(os.path.abspath(a[0])); r = pycolmap.Reconstruction(a[1])
    quelle = lambda n: n.split("__vf_")[0] if "__vf_" in n else (n.split("__")[0] if "__" in n else "eigen")
    src = {i: quelle(im.name) for i, im in r.images.items()}
    fremd_pt = {pid: len({src[e.image_id] for e in p.track.elements}) > 1 for pid, p in r.points3D.items()}
    je = collections.defaultdict(list); werte = {}
    for i, im in r.images.items():
        ids = [p.point3D_id for p in im.points2D if p.has_point3D()]; n = len(ids); f = sum(fremd_pt[q] for q in ids)
        name = os.path.splitext(im.name)[0]; werte[name] = dict(punkte=n, fremd=f); je[src[i]].append((name, n, f))
    aus, gruppen, hinweis = [], {}, {}
    for q, l in sorted(je.items()):
        insel = sorted(nm for nm, n, f in l if f < anteil * max(n, 1))
        if not insel: continue
        if q in anker: hinweis[q] = len(insel); print(f"  {q[:50]:50s} {len(insel):3d} von {len(l):3d} ohne Fremdstuetze - Ankerquelle, nur Hinweis"); continue
        aus += insel; mark = ""
        if len(insel) >= gruppe: gruppen[q] = len(insel); mark = "  <-- INSEL-KETTE"
        print(f"  {q[:50]:50s} {len(insel):3d} von {len(l):3d} ohne Fremdstuetze{mark}")
    print(f"{len(aus)} von {len(src)} Bildern ohne Fremdstuetze (Anteil < {anteil:.0%}); Insel-Ketten: {len(gruppen)}")
    os.makedirs(os.path.join(od, "audit"), exist_ok=True)
    json.dump(dict(werkzeug="kette_insel_pruefen.py", sparse=a[1], anteil=anteil, n=len(src), gruppen=gruppen, hinweis_anker=hinweis, ausschliessen=sorted(aus),
                   werte={k: werte[k] for k in sorted(aus)}), open(os.path.join(od, "audit", "kette_insel.json"), "w"), indent=1)
    return 3 if gruppen else 0


if __name__ == "__main__":
    sys.exit(main())
