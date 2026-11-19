#!/usr/bin/env python3
"""wolke_gruppen_pruefen.py <objekt.json> <SFM-AUSRICHTUNG.json> <sparse-ordner> [--radius 80] [--ueber 6] [--min-anteil 0.25] [--min-punkte 40] [--schreiben]

TOR: setzt eine BILDGRUPPE (Videoclip bzw. Quelle vor '__') Punkte dorthin, wo nichts stehen kann?
Anlass Martinstor 19.11.2026 (Nutzer: "diese Haeuserzeile ist im voellig falschen Massstab"): ein Fernclip (16 Kameras, 150 m entfernt) stellte eine Haeuserzeile schief und
zu gross in die dichte Wolke, 25-60 m hoch neben dem Turm. Gelaende- und Inseltor hatten die Gruppe gemeldet, aber nur ueber ihre KAMERAS. Hier wird die GEOMETRIE geprueft,
die eine Gruppe erzeugt - das faengt auch Kameras, die in zwei Mapper-Laeufen gleich falsch stehen (der Konsens-Schnitt prueft nur Wiederholbarkeit).
Verfahren (nur duenne Wolke + LoD2, Sekunden):
  1. duenne Punkte ins Modellsystem (X_m = R^T (X_sfm - t) / s aus der Ausrichtung).
  2. Hoehenkarte aus LoD2: je 2-m-Zelle die groesste LoD2-Hoehe im Umkreis 10 m (Gebaeude daneben zaehlen mit - Fassade, Dachueberstand, Lagefehler).
  3. Ein Punkt ist UNMOEGLICH, wenn er > --ueber m ueber dieser Karte liegt (dort steht laut Kataster nichts so Hohes) oder > 4 m unter dem Gelaende.
     Punkte weiter als 10 m von jedem LoD2-Gebaeude werden nicht bewertet (Karte unbekannt).
  4. Je Gruppe nur die Punkte, die ueberwiegend (>= 70 % der Spur) von dieser Gruppe stammen. Gruppe AUFFAELLIG, wenn >= --min-anteil davon unmoeglich sind (und >= --min-punkte).
Ausgabe: audit/wolke_gruppen.json {gruppen, ausschliessen: [Bildnamen]} (--schreiben); tools/wolke_neu_fusionieren.py nimmt die Liste aus der dichten Wolke.
rc 0 = keine Gruppe auffaellig, rc 3 = mindestens eine. GRENZEN: braucht LoD2 und eine Ausrichtung, deren Massstab stimmt (bei falschem Massstab sind ALLE Gruppen auffaellig ->
dann meldet das Tor 'Ausrichtung pruefen' statt Gruppen auszuschliessen); echte hohe Bauteile ohne LoD2 (Kran, Mast, Baum) koennen eine kleine Gruppe treffen (ANNAHME Schwelle 25 %)."""
import sys, os, json, argparse, collections
import numpy as np

T = os.path.dirname(os.path.abspath(__file__))


def gruppe(name):
    return name.split("__vf_")[0] if "__vf_" in name else name.split("__")[0]


def hoehenkarte(L, zelle=2.0, umkreis=10.0):
    """L = LoD2-Flaechenpunkte (N,3) im Modellsystem -> (x0, y0, zelle, Karte der groessten Hoehe im Umkreis; NaN = kein Gebaeude in der Naehe)."""
    x0, y0 = L[:, 0].min() - umkreis, L[:, 1].min() - umkreis; nx = int((L[:, 0].max() + umkreis - x0) / zelle) + 1; ny = int((L[:, 1].max() + umkreis - y0) / zelle) + 1
    K = np.full((ny, nx), -np.inf); ix = ((L[:, 0] - x0) / zelle).astype(int); iy = ((L[:, 1] - y0) / zelle).astype(int); np.maximum.at(K, (iy, ix), L[:, 2])
    r = int(round(umkreis / zelle)); M = K.copy()
    for dy in range(-r, r + 1):                                                    # groesster Wert im Umkreis (runde Maske), ohne scipy
        for dx in range(-r, r + 1):
            if dx * dx + dy * dy > r * r or (dx == 0 and dy == 0): continue
            S = np.full_like(K, -np.inf); ys = slice(max(0, dy), ny + min(0, dy)); yq = slice(max(0, -dy), ny + min(0, -dy)); xs = slice(max(0, dx), nx + min(0, dx)); xq = slice(max(0, -dx), nx + min(0, -dx))
            S[ys, xs] = K[yq, xq]; M = np.maximum(M, S)
    M[~np.isfinite(M)] = np.nan
    return x0, y0, zelle, M


def bewerten(P, spur_gruppen, karte, ueber=6.0, unter=-4.0, min_anteil=0.25, min_punkte=40, eigen_anteil=0.7):
    """P (N,3) Modellmeter; spur_gruppen = je Punkt Counter {gruppe: n}. Rueckgabe (gruppen-dict, anteil_gesamt)."""
    x0, y0, z_, M = karte; ix = ((P[:, 0] - x0) / z_).astype(int); iy = ((P[:, 1] - y0) / z_).astype(int)
    drin = (ix >= 0) & (iy >= 0) & (ix < M.shape[1]) & (iy < M.shape[0]); H = np.full(len(P), np.nan); H[drin] = M[iy[drin], ix[drin]]
    bewertbar = np.isfinite(H); unm = bewertbar & ((P[:, 2] > H + ueber) | (P[:, 2] < unter))
    G = collections.defaultdict(lambda: [0, 0])
    for i in np.where(bewertbar)[0]:
        c = spur_gruppen[i]; n = sum(c.values()); g, k = max(c.items(), key=lambda kv: kv[1])
        if k >= eigen_anteil * n: G[g][0] += 1; G[g][1] += int(unm[i])
    aus = {g: dict(punkte=n, unmoeglich=u, anteil=round(u / n, 3), auffaellig=bool(n >= min_punkte and u / n >= min_anteil)) for g, (n, u) in G.items() if n}
    return aus, float(unm.sum() / max(1, bewertbar.sum())), bewertbar, unm


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("ausrichtung"); ap.add_argument("sparse"); ap.add_argument("--radius", type=float, default=80.0)
    ap.add_argument("--ueber", type=float, default=6.0); ap.add_argument("--min-anteil", type=float, default=0.25); ap.add_argument("--min-punkte", type=int, default=40); ap.add_argument("--schreiben", action="store_true")
    a = ap.parse_args(argv); import cv2, pycolmap
    sys.path.insert(0, T); from sfm_lod2_ausrichten import lod2_ziel
    obj = json.load(open(a.objekt)); od = os.path.dirname(os.path.abspath(a.objekt)); tr = json.load(open(a.ausrichtung))["transformation"]
    s = tr["s"]; R = cv2.Rodrigues(np.array(tr["rvec"], float))[0]; t = np.array(tr["t"], float)
    L = lod2_ziel(obj, a.radius)[0]; karte = hoehenkarte(L)
    r = pycolmap.Reconstruction(a.sparse); id2g = {im.image_id: gruppe(im.name) for im in r.images.values()}; namen = collections.defaultdict(list)
    for im in r.images.values(): namen[gruppe(im.name)].append(im.name)
    P = []; SG = []
    for p in r.points3D.values():
        P.append(p.xyz); SG.append(collections.Counter(id2g[e.image_id] for e in p.track.elements if e.image_id in id2g))
    P = ((np.array(P) - t) @ R) / s
    G, ant, bewertbar, unm = bewerten(P, SG, karte, a.ueber, min_anteil=a.min_anteil, min_punkte=a.min_punkte)
    # Einzelfoto-Quellen (kein Videoclip): nicht die ganze Quelle verwerfen, sondern je BILD pruefen - Anteil unmoeglicher unter allen Punkten, die das Bild sieht.
    clip = {g for g, nn in namen.items() if any("__vf_" in n for n in nn)}; je_bild = collections.defaultdict(lambda: [0, 0]); id2n = {im.image_id: im.name for im in r.images.values()}
    for i, p in enumerate(r.points3D.values()):
        if not bewertbar[i]: continue
        for e in p.track.elements:
            if e.image_id in id2n: je_bild[id2n[e.image_id]][0] += 1; je_bild[id2n[e.image_id]][1] += int(unm[i])
    bild_auff = sorted(n for n, (k, u) in je_bild.items() if gruppe(n) not in clip and k >= 30 and u / k >= a.min_anteil)
    for g in list(G):
        if g not in clip and G[g]["auffaellig"]: G[g]["auffaellig"] = False; G[g]["hinweis"] = "Einzelfoto-Quelle: je Bild geprueft"
    auff = sorted(g for g, v in G.items() if v["auffaellig"]); n_gr = sum(1 for v in G.values() if v["punkte"] >= a.min_punkte)
    for g, v in sorted(G.items(), key=lambda kv: -kv[1]["anteil"])[:12]:
        print(f"  {g[:40]:40s} {v['unmoeglich']:6d} von {v['punkte']:6d} eigenen Punkten unmoeglich ({100 * v['anteil']:.0f} %)" + ("  <-- GRUPPE" if v["auffaellig"] else ""))
    alle_falsch = (n_gr >= 3 and len(auff) > 0.5 * n_gr) or ant > 0.06               # die meisten Gruppen oder > 6 % ALLER Punkte 'unmoeglich' = nicht die Gruppen sind falsch, sondern Massstab/Lage der Ausrichtung
    # (ANNAHME 6 %: Martinstor 19.11. richtige Ausrichtung 1,8 %, auf der Seite liegende 11,3 % - dort waeren drei gute Drohnenclips verworfen worden)
    aus = [] if alle_falsch else sorted(set(n for g in auff for n in namen[g]) | set(bild_auff))
    if bild_auff: print(f"  Einzelfotos mit >= {100 * a.min_anteil:.0f} % unmoeglichen Punkten: {len(bild_auff)} ({', '.join(x[:28] for x in bild_auff[:6])}{' ...' if len(bild_auff) > 6 else ''})")
    print(f"Wolken-Gruppen-Tor: {100 * ant:.1f} % der bewertbaren Punkte liegen > {a.ueber:.0f} m ueber der LoD2-Hoehe ihrer Umgebung oder unter dem Gelaende; {len(auff)} von {n_gr} Gruppen auffaellig")
    if alle_falsch: print("WARNUNG: mehr als die Haelfte der Gruppen oder > 6 % aller Punkte auffaellig - das ist kein Gruppenfehler, sondern Massstab/Lage der AUSRICHTUNG (nichts ausgeschlossen, Ausrichtung pruefen).")
    elif auff or bild_auff: print(f"WARNUNG: Bildgruppe(n)/Einzelfotos setzen Geometrie an unmoegliche Stellen: {', '.join(auff) or '-'} - {len(aus)} Bilder aus der dichten Wolke nehmen (audit/wolke_gruppen.json, tools/wolke_neu_fusionieren.py).")
    if a.schreiben:
        os.makedirs(os.path.join(od, "audit"), exist_ok=True)
        json.dump(dict(ausrichtung=os.path.basename(a.ausrichtung), anteil_unmoeglich=round(ant, 4), ausrichtung_verdaechtig=bool(alle_falsch), gruppen=G, auffaellig=auff, einzelfotos=bild_auff, ausschliessen=aus), open(os.path.join(od, "audit", "wolke_gruppen.json"), "w"), indent=1, ensure_ascii=False)
    return 3 if (auff or bild_auff or alle_falsch) else 0


if __name__ == "__main__": sys.exit(main())
