#!/usr/bin/env python3
"""modell_zerlegen.py <sparse-modell> [--aus <ordner>] [--min-punkte 15] [--min-bilder 3]

Fund 20.11.2026 (Martinstor, FlexGlue-Nacht): der globale Mapper schreibt Bildgruppen, die KEINEN gemeinsamen 3D-Punkt haben, in EIN Modell
(Verbindung nur ueber Bildpaare im Ansichtsgraphen, deren Spuren spaeter als Ausreisser fielen). Ihre gegenseitige Lage ist dann beliebig -
das sah aus wie 'Seiten verklebt' (Sued 18 % neben der wahren Lage), war aber ein Modell aus unverbundenen Stuecken.
Dieses Werkzeug zerlegt ein Modell nach Punkt-Zusammenhang: zwei Bilder gelten als verbunden ab --min-punkte gemeinsamen 3D-Punkten.
Ausgabe: je Stueck ein Untermodell <aus>/<k>/ (groesstes zuerst) + Liste. Ohne --aus nur Bericht. rc 3 = Modell zerfaellt in mehrere Stuecke ab --min-bilder."""
import sys, os, argparse, collections


def stuecke(r, min_punkte=15):
    nm = list(r.images); par = {i: i for i in nm}
    def f(x):
        while par[x] != x: par[x] = par[par[x]]; x = par[x]
        return x
    E = collections.Counter()
    for p in r.points3D.values():
        ids = sorted({e.image_id for e in p.track.elements})
        for x in range(len(ids)):
            for y in range(x + 1, len(ids)): E[(ids[x], ids[y])] += 1
    for (a, b), c in E.items():
        if c >= min_punkte: par[f(a)] = f(b)
    K = collections.defaultdict(list)
    for i in nm: K[f(i)].append(i)
    return sorted(K.values(), key=len, reverse=True)


def main(argv=None):
    import pycolmap
    ap = argparse.ArgumentParser(); ap.add_argument("modell"); ap.add_argument("--aus"); ap.add_argument("--min-punkte", type=int, default=15); ap.add_argument("--min-bilder", type=int, default=3)
    a = ap.parse_args(argv); r = pycolmap.Reconstruction(a.modell); S = [s for s in stuecke(r, a.min_punkte) if len(s) >= a.min_bilder]
    print(f"ZERLEGEN: {len(r.images)} Bilder -> {len(S)} Stuecke ab {a.min_bilder} Bildern: " + ", ".join(str(len(s)) for s in S[:12]))
    if a.aus:
        for k, s in enumerate(S):
            t = pycolmap.Reconstruction(r); weg = set(t.images) - set(s)
            for fid in {t.images[i].frame_id for i in weg}: t.deregister_frame(fid)       # pycolmap 4.2: Bilder haengen an Frames; entfernt auch ihre Beobachtungen
            d = os.path.join(a.aus, str(k)); os.makedirs(d, exist_ok=True); t.write(d)
    return 3 if len(S) > 1 else 0


if __name__ == "__main__": sys.exit(main())
