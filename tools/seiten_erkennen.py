#!/usr/bin/env python3
"""seiten_erkennen.py <db.db> <bilder_ordner> --aus <seiten.json> [--db-aus <kopie.db>] [--min-bilder 12] [--min-paare 20] [--stichprobe 24] [--schwelle 0.45] [--referenz eigen__] [--trocken]

SEITENERKENNUNG vor dem Mapper (Nutzer 19.11.2026: "Die Seitenverwechslung wird ein haeufiges Problem sein - jedes Gebaeude hat mehrere Seiten").
Problem: gleich aussehende Seiten (Turm: Uhr, Ecktuermchen, Helm) geben bestaetigte Bildpaare; der Mapper klappt die Rueckseite auf die Vorderseite
(Martinstor alt, Schwabentor 15.11., Martinstor 19.11.). Zwei Mapper-Laeufe verkleben GLEICH - der Konsens-Schnitt erkennt das nicht.
Verfahren (ohne Vorwissen, ohne Kamerastandorte):
  1. GEMEINSCHAFTEN im Paar-Graphen (Louvain, Kantengewicht = bestaetigte Zuordnungen >= 30): Bilder einer Seite haengen untereinander stark zusammen,
     Seiten untereinander schwach. Martinstor: Gruppe 0 = 63 gepruefte Bilder 'Nebenhaus rechts' / 0 'links', Gruppe 1 = 0 / 7, Gruppe 3 = 0 / 12.
  2. Je Gruppenpaar mit >= --min-paare Verbindungen: Stichprobe der Paare durch den gelernten Paar-Pruefer (tools/doppelgaenger_paare.py, MIT).
     Median p_gleich < --schwelle = VERWECHSLUNG (Martinstor: verwechselt 0,32; echt 0,57 / 0,75 / 0,89; ANNAHME Schwelle 0,45, 'unklar' bis 0,55 wird gemeldet, nicht geloescht).
  3. --db-aus: Kopie der Datenbank, in der ALLE Paare zwischen verwechselten Gruppen geloescht sind (matches + two_view_geometries).
     Dazu: Gruppen-Zusammenhang ohne die geloeschten Verbindungen; Teile ohne ein einziges Objektfoto (--referenz Namensanfang) = FREMD (anderes Bauwerk aus
     Stadtrundgang-Videos) -> ihre Paare werden ebenfalls geloescht (sie kosteten am Martinstor 35 min Mapper-Zeit ohne Nutzen), Liste in seiten.json 'fremd'.
Ausgabe seiten.json: gemeinschaft je Bild, verbindungen (paare, p_median, urteil), seiten (Zusammenhangsteile mit Objektfotos), fremd, geloeschte_paare.
rc 0 = nichts verwechselt, rc 3 = mindestens eine Verwechslung gefunden (und bei --db-aus bereinigt).
GRENZEN: der Pruefer ist je Paar unsicher (echte Paare Median nur 0,57-0,89) - deshalb Abstimmung je Gruppenpaar, nie Einzelpaar-Filter. Eine Gruppe, die selbst beide
Seiten mischt (Durchgang durch einen Torbogen), wird nicht getrennt. Zwei getrennte Seiten ohne echte Verbindung ergeben zwei Modelle - Vereinen ist ein eigener Schritt."""
import sys, os, json, argparse, sqlite3, shutil, collections, random
import numpy as np

T = os.path.dirname(os.path.abspath(__file__)); MAXID = 2147483647


def quelle(name):
    return name.split("__vf_")[0] if "__vf_" in name else name.split("__")[0]


def gemeinschaften(kanten, knoten, saat=1):
    """kanten = [(a, b, gewicht)] -> Liste von Mengen, groesste zuerst (Louvain, fester Zufallskeim = wiederholbar)."""
    import networkx as nx
    G = nx.Graph(); G.add_nodes_from(knoten); G.add_weighted_edges_from(kanten)
    return sorted((set(c) for c in nx.community.louvain_communities(G, weight="weight", seed=saat)), key=lambda c: (-len(c), min(c)))


def teile(n, verbunden):
    """Zusammenhangsteile der Gruppen 0..n-1 ueber die Paare in verbunden."""
    par = list(range(n))
    def f(x):
        while par[x] != x: par[x] = par[par[x]]; x = par[x]
        return x
    for a, b in verbunden: par[f(a)] = f(b)
    aus = collections.defaultdict(list)
    for i in range(n): aus[f(i)].append(i)
    return sorted(aus.values(), key=lambda v: (-len(v), v[0]))


def urteil(p_median, schwelle, unklar=0.10):
    return "verwechselt" if p_median < schwelle else ("unklar" if p_median < schwelle + unklar else "echt")


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("db"); ap.add_argument("bilder"); ap.add_argument("--aus", required=True); ap.add_argument("--db-aus"); ap.add_argument("--min-bilder", type=int, default=12)
    ap.add_argument("--min-paare", type=int, default=20); ap.add_argument("--min-inlier", type=int, default=30); ap.add_argument("--stichprobe", type=int, default=24); ap.add_argument("--schwelle", type=float, default=0.45)
    ap.add_argument("--referenz", default="eigen__", help="Namensanfang der Objektfotos (Sammelordner tools/fotos_sammeln.py)"); ap.add_argument("--trocken", action="store_true", help="nur Gruppen und Verbindungen zaehlen, kein Pruefer")
    a = ap.parse_args(argv); db = sqlite3.connect(f"file:{a.db}?mode=ro", uri=True); nm = dict(db.execute("select image_id, name from images"))
    K = [(pid // MAXID, pid % MAXID, rows) for pid, rows in db.execute("select pair_id, rows from two_view_geometries where rows >= ?", (a.min_inlier,))]
    C = gemeinschaften(K, list(nm)); g = {i: k for k, c in enumerate(C) for i in c}; gross = [k for k, c in enumerate(C) if len(c) >= a.min_bilder]
    quer = collections.defaultdict(list)
    for x, y, r in K:
        if g[x] != g[y]: quer[tuple(sorted((g[x], g[y])))].append((x, y, r))
    print(f"{len(nm)} Bilder, {len(K)} Paare >= {a.min_inlier}: {len(C)} Gemeinschaften, {len(gross)} mit >= {a.min_bilder} Bildern")
    kand = sorted(k for k, v in quer.items() if len(v) >= a.min_paare and k[0] in gross and k[1] in gross); rnd = random.Random(0); proben = []
    for k in kand:
        v = sorted(quer[k]); rnd.shuffle(v); proben += [(k, nm[x], nm[y]) for x, y, _ in v[:a.stichprobe]]
    print(f"{len(kand)} Gruppenpaare mit >= {a.min_paare} Verbindungen -> {len(proben)} Paare fuer den Pruefer", flush=True)
    verb = []
    if a.trocken: verb = [dict(a=k[0], b=k[1], paare=len(quer[k]), p_median=None, urteil="ungeprueft") for k in kand]
    else:
        sys.path.insert(0, T); from doppelgaenger_paare import pruefen
        erg = pruefen(a.bilder, [(x, y) for _, x, y in proben], melden=200); P = collections.defaultdict(list)
        for (k, _, _), e in zip(proben, erg):
            if e[2] is not None: P[k].append(e[2])
        for k in kand:
            pm = float(np.median(P[k])) if P[k] else 1.0; verb.append(dict(a=k[0], b=k[1], paare=len(quer[k]), geprueft=len(P[k]), p_median=round(pm, 3), urteil=urteil(pm, a.schwelle)))
    falsch = {(v["a"], v["b"]) for v in verb if v["urteil"] == "verwechselt"}
    # Zusammenhang der Gruppen ohne die verwechselten Verbindungen (kleine Gruppen und ungepruefte schwache Verbindungen zaehlen als echt)
    S = teile(len(C), [k for k in quer if k not in falsch]); ref = lambda k: sum(1 for i in C[k] if nm[i].startswith(a.referenz))
    seiten = [s for s in S if sum(ref(k) for k in s) > 0]; fremd_g = {k for s in S if sum(ref(k) for k in s) == 0 for k in s}; fremd = sorted(nm[i] for k in fremd_g for i in C[k])
    for v in sorted(verb, key=lambda v: v["p_median"] if v["p_median"] is not None else 9)[:14]:
        print(f"  Gruppe {v['a']:3d} ({len(C[v['a']]):4d} Bilder) <-> {v['b']:3d} ({len(C[v['b']]):4d}): {v['paare']:5d} Paare, p_gleich Median {v['p_median']}  {v['urteil'].upper() if v['urteil'] != 'echt' else 'echt'}")
    for n, s in enumerate(seiten[:6]):
        q = collections.Counter(quelle(nm[i]) for k in s for i in C[k]); print(f"  Teil {n}: {sum(len(C[k]) for k in s)} Bilder in {len(s)} Gruppen ({', '.join(f'{x[-14:]} {c}' for x, c in q.most_common(4))})")
    geloescht = 0
    if a.db_aus and not a.trocken:
        shutil.copyfile(a.db, a.db_aus); d2 = sqlite3.connect(a.db_aus); weg = []
        for (pid,) in d2.execute("select pair_id from two_view_geometries"):
            x, y = pid // MAXID, pid % MAXID; k = tuple(sorted((g[x], g[y])))
            if k in falsch or g[x] in fremd_g or g[y] in fremd_g: weg.append((pid,))
        d2.executemany("delete from two_view_geometries where pair_id = ?", weg); d2.executemany("delete from matches where pair_id = ?", weg); d2.commit(); d2.close(); geloescht = len(weg)
    json.dump(dict(db=os.path.abspath(a.db), gemeinschaft={nm[i]: k for i, k in g.items()}, groessen=[len(c) for c in C], verbindungen=verb, verwechselt=[list(k) for k in sorted(falsch)],
                   seiten=[dict(gruppen=s, bilder=sum(len(C[k]) for k in s)) for s in seiten], fremd=fremd, geloeschte_paare=geloescht, schwelle=a.schwelle), open(a.aus, "w"), indent=1)
    print(f"Seitenerkennung: {len(falsch)} verwechselte Gruppenverbindung(en), {sum(1 for v in verb if v['urteil'] == 'unklar')} unklar; {len(seiten)} Teil(e) mit Objektfotos, {len(fremd)} fremde Bilder"
          + (f"; {geloescht} Paare geloescht -> {a.db_aus}" if a.db_aus and not a.trocken else ""))
    if falsch: print("WARNUNG SEITENVERWECHSLUNG: Bildgruppen zeigen aehnliche, aber verschiedene Seiten - ihre Paare duerfen nicht in den Mapper (bereinigte Datenbank nehmen).")
    gr = [s for s in seiten if sum(len(C[k]) for k in s) >= a.min_bilder]
    if len(gr) > 1: print(f"WARNUNG: {len(gr)} Bildteile mit Objektfotos ohne echte Verbindung untereinander - der Mapper liefert getrennte Modelle (Seiten vereinen noetig).")
    return 3 if falsch else 0


if __name__ == "__main__": sys.exit(main())
