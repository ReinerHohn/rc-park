#!/usr/bin/env python3
"""seiten_erkennen.py <db.db> <bilder_ordner> --aus <seiten.json> [--db-aus <kopie.db>] [--min-bilder 12] [--min-paare 20] [--stichprobe 24] [--schwelle 0.45] [--referenz eigen__] [--objekt objekt.json] [--trocken]

SEITENERKENNUNG vor dem Mapper (Nutzer 19.11.2026: "Die Seitenverwechslung wird ein haeufiges Problem sein - jedes Gebaeude hat mehrere Seiten").
Problem: gleich aussehende Seiten (Turm: Uhr, Ecktuermchen, Helm) geben bestaetigte Bildpaare; der Mapper klappt die Rueckseite auf die Vorderseite
(Martinstor alt, Schwabentor 15.11., Martinstor 19.11.). Zwei Mapper-Laeufe verkleben GLEICH - der Konsens-Schnitt erkennt das nicht.
Verfahren (ohne Vorwissen, ohne Kamerastandorte):
  1. GEMEINSCHAFTEN im Paar-Graphen (Louvain, Kantengewicht = bestaetigte Zuordnungen >= 30): Bilder einer Seite haengen untereinander stark zusammen,
     Seiten untereinander schwach. Martinstor: Gruppe 0 = 63 gepruefte Bilder 'Nebenhaus rechts' / 0 'links', Gruppe 1 = 0 / 7, Gruppe 3 = 0 / 12.
  2. Je Gruppenpaar mit >= --min-paare Verbindungen: Stichprobe der Paare durch den gelernten Paar-Pruefer (tools/doppelgaenger_paare.py, MIT).
     ECHT, wenn >= 10 % der Stichprobe eindeutig gleich sind (p_gleich >= 0,8); VERWECHSELT, wenn fast kein Paar gleich aussieht (90. Perzentil < 0,5);
     sonst 'unklar' (gemeldet, nicht geloescht). Martinstor: verwechselt p90 0,42 und 0 % eindeutig; echt 25 / 47 / 65 % eindeutig. Der Median trennt NICHT (siehe urteil()).
  2b. --objekt: haben Fotos GPS im EXIF, bekommt jede Bildgruppe mit >= 3 solchen Fotos eine STANDRICHTUNG um die Objektmitte. Zwei Gruppen > 120 Grad auseinander =
     verwechselt, < 60 Grad = echt. Das entscheidet 'unklare' und vom Pruefer nicht gesehene (schwache) Verbindungen; ein klares 'echt' des Pruefers ueberstimmt es NICHT
     (Handy-GPS in der Strassenschlucht ist zu grob, siehe Kommentar im Code). Ohne GPS bleibt alles wie in 2.
  3. --db-aus: Kopie der Datenbank, in der ALLE Paare zwischen verwechselten Gruppen geloescht sind (matches + two_view_geometries).
     Dazu: Gruppen-Zusammenhang ohne die geloeschten Verbindungen; Teile ohne ein einziges Objektfoto (--referenz Namensanfang) = FREMD (anderes Bauwerk aus
     Stadtrundgang-Videos) -> ihre Paare werden ebenfalls geloescht (sie kosteten am Martinstor 35 min Mapper-Zeit ohne Nutzen), Liste in seiten.json 'fremd'.
  4. --durchblick / RCPARK_SEITEN_DURCHBLICK=1 (Stufe Durchblick/Umgebung, 22.11.2026): in verwechselten/unklaren/ungeprueften Verbindungen bleiben EINZELNE Paare mit
     >= 200 nicht-statischen Inliern ueber >= 12/64 Bildzellen (Uebereck-/Umgebungsfotos; Verwechslung findet nur Uhr/Helm, max 122 Inlier am Martinstor), auch gegen
     Regel 2b; GPS-Veto je Paar. Liste 'durchblick' in seiten.json (urteil 'durchblick' + Messwerte). Einblendungen (gleiche Bildstelle) zaehlen nie. Siehe Kommentar unten.
Ausgabe seiten.json: gemeinschaft je Bild, verbindungen (paare, p_median, urteil), seiten (Zusammenhangsteile mit Objektfotos), fremd, geloeschte_paare.
rc 0 = nichts verwechselt, rc 3 = mindestens eine Verwechslung gefunden (und bei --db-aus bereinigt).
GRENZEN: der Pruefer ist je Paar unsicher (echte Paare Median nur 0,57-0,89) - deshalb Abstimmung je Gruppenpaar, nie Einzelpaar-Filter. Eine Gruppe, die selbst beide
Seiten mischt (Durchgang durch einen Torbogen), wird nicht getrennt (--aufloesung 2.0 trennt die am Martinstor; Beleg: Mapper-Lauf mit Aufloesung 1.0 blieb verklebt,
Rueckseiten-Gruppe 6 Grad statt 180 Grad Blickrichtung gegen die Vorderseite). Zwei getrennte Seiten ohne echte Verbindung ergeben zwei Modelle - Vereinen ist ein eigener Schritt."""
import sys, os, json, argparse, sqlite3, shutil, collections, random
import numpy as np

T = os.path.dirname(os.path.abspath(__file__)); MAXID = 2147483647


def quelle(name):
    return name.split("__vf_")[0] if "__vf_" in name else name.split("__")[0]


def gemeinschaften(kanten, knoten, saat=1, aufloesung=2.0):
    """kanten = [(a, b, gewicht)] -> Liste von Mengen, groesste zuerst (Louvain, fester Zufallskeim = wiederholbar)."""
    import networkx as nx
    G = nx.Graph(); G.add_nodes_from(knoten); G.add_weighted_edges_from(kanten)
    return sorted((set(c) for c in nx.community.louvain_communities(G, weight="weight", seed=saat, resolution=aufloesung)), key=lambda c: (-len(c), min(c)))


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


def urteil(p, hoch=0.8, min_hoch=0.10, p90_falsch=0.5):
    """p = p_gleich der Stichprobe einer Gruppenverbindung. ECHT, wenn es eindeutig gleiche Paare GIBT (>= min_hoch der Paare ueber hoch): bei einer echten Verbindung
    sind immer einige Paare leicht (aehnlicher Standort). VERWECHSELT, wenn fast kein Paar gleich aussieht (90. Perzentil < p90_falsch). Sonst unklar (nichts loeschen).
    Der Median taugt nicht: echte Paare aus Video/Drohne liegen oft bei 0,4-0,6 (Martinstor 19.11.2026: verwechselt 0,33, echt Drohne<->Strasse 0,38)."""
    p = np.asarray(p, float)
    if len(p) < 6: return "unklar"
    if (p >= hoch).mean() >= min_hoch: return "echt"
    return "verwechselt" if np.percentile(p, 90) < p90_falsch else "unklar"


def richtung(mitte, gps):
    """Standrichtung (Grad, 0 = Nord, im Uhrzeigersinn) und Abstand (m) eines Fotostandorts (breite, laenge) von der Objektmitte (breite, laenge)."""
    import math
    dn = (gps[0] - mitte[0]) * 111320.0; do = (gps[1] - mitte[1]) * 111320.0 * math.cos(math.radians(mitte[0]))
    return math.degrees(math.atan2(do, dn)) % 360.0, math.hypot(dn, do)


def gruppen_richtung(az, min_fotos=3, min_buendel=0.7):
    """Mittlere Standrichtung einer Bildgruppe aus den GPS-Fotos (Kreismittel) oder None, wenn zu wenige Fotos oder rundum verteilt (Buendelung < min_buendel)."""
    if len(az) < min_fotos: return None
    w = np.radians(az); c, s_ = np.cos(w).mean(), np.sin(w).mean(); r = float(np.hypot(c, s_))
    return (float(np.degrees(np.arctan2(s_, c)) % 360.0), r) if r >= min_buendel else None


def urteil_gps(ra, rb, gegen=120.0, gleich=60.0):
    """Zwei Gruppen mit GPS-Richtung: > gegen Grad auseinander = sie koennen nicht dieselbe Wand zeigen (verwechselt); < gleich Grad = echt; dazwischen/ohne GPS None.
    Grenzen wie tools/lg_in_db_anhaengen.py (Schwabentor 15.11.2026: Paare nur bis 110 Grad, ueber 120 Grad loeschen)."""
    if ra is None or rb is None: return None
    d = abs((ra[0] - rb[0] + 180.0) % 360.0 - 180.0)
    return "verwechselt" if d > gegen else ("echt" if d < gleich else None)


# FERNSICHT (22.11.2026, Vergleich schwabentor-1120 gegen 1122): 10 Fotos aus ~320 m (eigen__IMG_20261106_110741..111237, zwei Standorte, GPS 319-325 m) waren
# in 1120 registriert und trugen dort Drehung/Massstab (Modell 322-326 m, Richtung < 1 Grad daneben; Hebel 320 m statt 25-m-Kamerakranz). In 1122 bildeten sie
# Gruppe 22 (12 Bilder), deren einzige Verbindung 0<->22 der Pruefer 'unklar' nannte (p90 0,60, aus der Ferne sieht man zwei Turmseiten zugleich); --streng
# schnitt sie ab -> eigene 'Seite' unter 30 Bildern -> kein Modell -> die Ausrichtung hatte nur noch das Nah-GPS (systematisch +9,4 Grad / x0,867 verzerrt).
# Regel: eine Gruppe, deren GPS-Fotos ueberwiegend weit weg stehen (>= FERN_M, mehrere verschiedene Geotags = kein eingefrorener Ortsstempel), zeigt das GANZE
# Bauwerk; sie ist keine 'Seite'. --streng behaelt darum ihre staerkste 'unklare' Verbindung (nur EINE, damit sie keine zwei Seiten verbruecken kann); ein
# 'verwechselt' des Pruefers bleibt geloescht. Die GPS-Standrichtung (2b) wertet Fernsicht-Gruppen nicht (aus der Ferne sieht man mehrere Seiten).
FERN_M = 100.0            # ANNAHME wie lage_gps_pruefen (nah_m 100 m = Torfotos; Fernfotos dahinter tragen den Massstab)
FERN_MAX_M = 5000.0       # weiter weg: Ortsmarke/falscher Geotag (eigen__od_08 GPS 1,9 km, Modell 84 km)
FERN_ANTEIL = 0.6         # ANNAHME: so viele der GPS-Fotos der Gruppe muessen fern sein
FERN_MIN_ORTE = 2         # verschiedene Geotags (auf ~1 m gerundet) - 4 Fotos mit DEMSELBEN Geotag 272 m waren eingefroren (1122e, 113015-19)


def fernsicht_gruppen(gps_je_gruppe, mitte, fern_m=FERN_M, fern_max_m=FERN_MAX_M, anteil=FERN_ANTEIL, min_orte=FERN_MIN_ORTE, min_fotos=3):
    """gps_je_gruppe = {gruppe: [(breite, laenge), ...]}, mitte = (breite, laenge) -> Menge der Fernsicht-Gruppen."""
    aus = set()
    for k, qs in gps_je_gruppe.items():
        if len(qs) < min_fotos: continue
        d = np.array([richtung(mitte, q)[1] for q in qs]); f = (d >= fern_m) & (d <= fern_max_m)
        orte = {(round(q[0], 5), round(q[1], 5)) for q, j in zip(qs, f) if j}
        if f.sum() >= min_fotos and f.mean() >= anteil and len(orte) >= min_orte: aus.add(k)
    return aus


def fernsicht_behalten(verb, fern, quer=None):
    """Je Fernsicht-Gruppe die 'unklare' Verbindung mit den meisten Paaren -> Menge (a, b), die --streng NICHT loescht. Markiert sie in verb ('fernsicht_behalten').
    quer = {(a, b): [Paare >= --min-inlier]}: hat die Gruppe KEINE vom Pruefer gesehene Verbindung (Gruppe unter --min-bilder, Verbindung unter --min-paare), gilt ihre
    staerkste UNGEPRUEFTE Verbindung (neuer Eintrag in verb, urteil 'ungeprueft'). Grund 23.11.2026 (Kette 1122q): die 10 Fernfotos 110741-111237 bildeten Gruppe 26 mit
    11 Bildern (< 12) -> der Pruefer sah sie nie -> keine 'unklare' Verbindung -> --streng schnitt sie ab (Teil 3, 11 Bilder, kein Modell) -> lage_frueh nur mit Nah-GPS
    +9,9 Grad x0,902 (1122o mit Fernfotos +1,2 Grad x0,980). Weiterhin nur EINE Verbindung je Fernsicht-Gruppe; eine Gruppe mit 'echt'/'verwechselt'-Urteil bekommt keine."""
    beh = set()
    for k in sorted(fern):
        kand = [v for v in verb if k in (v["a"], v["b"]) and v["urteil"] == "unklar"]
        if not kand:
            if quer is None or any(k in (v["a"], v["b"]) for v in verb): continue   # Pruefer/GPS hat die Gruppe gesehen ('echt' traegt schon, 'verwechselt' bleibt geloescht)
            uq = sorted(((kk, len(vv)) for kk, vv in quer.items() if k in kk and vv), key=lambda t: (-t[1], t[0]))
            if not uq: continue
            (x, y), n = uq[0]; verb.append(dict(a=x, b=y, paare=n, p_median=None, urteil="ungeprueft", fernsicht_behalten=True)); beh.add((x, y)); continue
        v = max(kand, key=lambda v: v["paare"]); v["fernsicht_behalten"] = True; beh.add((v["a"], v["b"]))
    return beh


# DURCHBLICK / UEBERECK (22.11.2026, schwabentor-1122, Nutzer: "Ich habe doch Fotos von ueberall her gemacht. Muesst ihr das nicht zusammenfinden?").
# Befund an den Paarbildern (tools/versuche/durchblick_paare_1122.py, /media/oem/rcdaten/tmp/durchblick/): die vermuteten Bruecken 9-14, 14-19, 7-14, 9-13 waren
# KEIN Durchblick durch den Bogen, sondern die eingeblendete Schrift eines Urlaubsvideos ("Urlaub Schwarzwald ... Schwabentor", Datum) - alle Paare COLMAP-config 7
# (WATERMARK), Zuordnungen an derselben Bildstelle (Versatz < 4 px), 0 von 222 Querpaaren behalten nach Abzug >= 15 echte Inlier. 0-1 = echte Fassadenverwechslung
# (Uhr/Helm, Inlier <= 44). Die ECHTE Bruecke lag woanders: der Nutzer ging um die Turmecke (Fotos 11:39:28-11:41:45): Gruppe 1 (Teil 1) -> Gruppe 27 (5 Bilder,
# eigener Teil) -> Gruppe 12 (Teil 0) mit 300 / 545 / 268 bestaetigten Inliern auf Quadern, Brunnensaeule, Nachbarhaus und Boden. --streng warf sie weg, weil der
# Pruefer kleine Gruppen (< --min-bilder) und schwache Verbindungen (< --min-paare) nie sieht und alles Ungepruefte loescht.
# KRITERIUM je PAAR (nicht je Gruppenverbindung): Verwechslung aehnlicher Seiten findet nur die wiederholten, entworfenen Bauteile (Uhr, Helm, Fenster); verschiedene
# Quader-, Pflaster- und Nachbarhausflaechen passen nicht Stein fuer Stein. Gemessen: groesste Inlierzahl eines Querpaares zwischen verschiedenen Bildteilen
# Martinstor-1120 (bekannte Verwechslung, alle 4491 Paare) 122, Schwabentor 0<->1 ohne Einblendung 93; echte Eckpaare 268-545.
DURCH_MIN_INLIER = 200   # ANNAHME: > 1,6 x groesstes Verwechslungs-/unklar-Paar (Martinstor 122, davon 'verwechselt' max 88), < kleinstes gesehenes Eckpaar 268
DURCH_MIN_ZELLEN = 12    # ANNAHME: Inlier in >= 12 von 64 Rasterzellen JEDES Bildes (Schrift/Logo/Uhr belegt 3-9)
DURCH_STATISCH = 0.002   # Zuordnung an (fast) derselben Bildstelle = Einblendung/Wasserzeichen; Anteil der Bildgroesse (4 px bei 2000 px)
DURCH_MAX_STATISCH = 0.10  # ANNAHME: mehr als 10 % statische Zuordnungen = Paar teilweise Einblendung (schwabentor-1122 9-24: 25-33 %, echte Paare 0-6 %) -> abgelehnt
DURCH_GPS_GEGEN = 120.0  # wie urteil_gps: Standorte beider Fotos > 120 Grad um die Objektmitte auseinander = koennen nicht dieselbe Flaeche sehen -> Paar abgelehnt
# BRUECKE ERWEITERN (22.11.2026, schwabentor-1122 Eck-Kopplung): an einer Gruppenverbindung, die >= 1 starkes Paar bestaetigt, haengen die Teile sonst nur an diesen
# wenigen Paaren (Ecke G27 -> G12: 3 Paare, EIN Teil-0-Bild) - der globale Mapper knickte Teil 1 dort um 25 Grad. Die schwaecheren Paare DERSELBEN Verbindung kommen mit
# denselben Pruefungen (Zellen, statischer Anteil, GPS-Veto) zurueck, Mindestzahl = die Kantenschwelle des Graphen (--min-inlier, 30). Nur bestaetigte Verbindungen:
# Martinstor hat keine (groesstes Querpaar 122) -> unveraendert getrennt.


def paar_staerke(p0, p1, wh0, wh1, statisch=DURCH_STATISCH, raster=8):
    """p0, p1 = bestaetigte Zuordnungen (N x 2, Pixel), wh = (breite, hoehe) -> dict(n, statisch, n_eff, zellen0, zellen1). Statische Zuordnungen (Einblendung) zaehlen nicht."""
    p0 = np.asarray(p0, float).reshape(-1, 2); p1 = np.asarray(p1, float).reshape(-1, 2)
    st = np.linalg.norm(p0 - p1, axis=1) < statisch * max(max(wh0), max(wh1)); q0, q1 = p0[~st], p1[~st]
    def zellen(q, wh):
        if not len(q): return 0
        gx = np.clip((q[:, 0] / wh[0] * raster).astype(int), 0, raster - 1); gy = np.clip((q[:, 1] / wh[1] * raster).astype(int), 0, raster - 1)
        return int(len(set(zip(gx.tolist(), gy.tolist()))))
    return dict(n=int(len(p0)), statisch=int(st.sum()), n_eff=int(len(q0)), zellen0=zellen(q0, wh0), zellen1=zellen(q1, wh1))


def durchblick_ok(m, gps_dw=None, min_inlier=DURCH_MIN_INLIER, min_zellen=DURCH_MIN_ZELLEN, gegen=DURCH_GPS_GEGEN):
    """(urteil, grund): 'durchblick' = Paar zeigt dieselbe Flaeche (viele nicht-statische Inlier ueber das ganze Bild), sonst 'abgelehnt'."""
    if m["n_eff"] < min_inlier: return "abgelehnt", f"n_eff {m['n_eff']} < {min_inlier}" + (f" (statisch {m['statisch']} = Einblendung)" if m["statisch"] > m["n_eff"] else "")
    if m["statisch"] > DURCH_MAX_STATISCH * max(m["n"], 1): return "abgelehnt", f"Einblendung: statisch {m['statisch']} von {m['n']}"
    if min(m["zellen0"], m["zellen1"]) < min_zellen: return "abgelehnt", f"Zellen {min(m['zellen0'], m['zellen1'])} < {min_zellen}"
    if gps_dw is not None and gps_dw > gegen: return "abgelehnt", f"GPS-Standorte {gps_dw:.0f} Grad auseinander"
    return "durchblick", "ok"


def durchblick_stufe(db, nm, g, falsch, gruppen_ok, mitte=None, bilder=None, min_inlier=DURCH_MIN_INLIER, bruecke_min=None):
    """Stufe 'Durchblick/Umgebung' fuer Verbindungen in falsch (verwechselt/unklar/ungeprueft unter --streng): jedes Paar mit >= min_inlier bestaetigten Zuordnungen
    zwischen zwei Gruppen aus gruppen_ok (Bildteile mit Objektfotos) wird einzeln gemessen. -> Liste dict(pair_id, a, b, ga, gb, n, n_eff, ..., urteil, grund).
    mitte + bilder: EXIF-GPS beider Fotos (15-300 m) als Veto gegen Paare von gegenueberliegenden Standorten."""
    wh = {i: (w, h) for i, w, h in db.execute("select i.image_id, c.width, c.height from images i join cameras c on c.camera_id = i.camera_id")}
    bruecke_min = min_inlier if bruecke_min is None else bruecke_min; gps = {}
    def standort(i):
        if i not in gps:
            gps[i] = None
            if mitte and bilder:
                from paarvorwahl import gps_aus_exif
                q = gps_aus_exif(os.path.join(bilder, nm[i]))
                if q is not None:
                    w, d = richtung(mitte, q); gps[i] = w if 15.0 <= d <= 300.0 else None
        return gps[i]
    def kp(i):
        r, c, d = db.execute("select rows, cols, data from keypoints where image_id = ?", (i,)).fetchone(); return np.frombuffer(d, np.float32).reshape(r, c)[:, :2]
    aus = []
    for pid, r, c, dat in db.execute("select pair_id, rows, cols, data from two_view_geometries where rows >= ?", (min_inlier,)).fetchall():
        x, y = pid // MAXID, pid % MAXID; k = tuple(sorted((g[x], g[y])))
        if k not in falsch or g[x] not in gruppen_ok or g[y] not in gruppen_ok: continue
        ij = np.frombuffer(dat, np.uint32).reshape(r, c); m = paar_staerke(kp(x)[ij[:, 0]], kp(y)[ij[:, 1]], wh[x], wh[y])
        wa, wb = standort(x), standort(y); dw = abs((wa - wb + 180.0) % 360.0 - 180.0) if wa is not None and wb is not None else None
        u, grund = durchblick_ok(m, dw, min_inlier=min_inlier)
        aus.append(dict(pair_id=int(pid), a=nm[x], b=nm[y], ga=g[x], gb=g[y], **m, gps_dw=None if dw is None else round(dw), urteil=u, grund=grund))
    bruecken = {tuple(sorted((d["ga"], d["gb"]))) for d in aus if d["urteil"] == "durchblick"}
    if bruecken and bruecke_min < min_inlier:                                          # BRUECKE ERWEITERN: schwaechere Paare bestaetigter Verbindungen
        for pid, r, c, dat in db.execute("select pair_id, rows, cols, data from two_view_geometries where rows >= ? and rows < ?", (bruecke_min, min_inlier)).fetchall():
            x, y = pid // MAXID, pid % MAXID; k = tuple(sorted((g[x], g[y])))
            if k not in bruecken: continue
            ij = np.frombuffer(dat, np.uint32).reshape(r, c); m = paar_staerke(kp(x)[ij[:, 0]], kp(y)[ij[:, 1]], wh[x], wh[y])
            wa, wb = standort(x), standort(y); dw = abs((wa - wb + 180.0) % 360.0 - 180.0) if wa is not None and wb is not None else None
            u, grund = durchblick_ok(m, dw, min_inlier=bruecke_min)
            aus.append(dict(pair_id=int(pid), a=nm[x], b=nm[y], ga=g[x], gb=g[y], **m, gps_dw=None if dw is None else round(dw), urteil=u, grund=grund, bruecke=True))
    return aus


def durchblick_einbauen(a, db, nm, g, C, quer_alle, falsch, ref, verb):
    """EIN Aufruf aus main(): Gruppen der Bildteile mit Objektfotos bestimmen, Stufe rechnen, Zaehler je Verbindung in verb eintragen. -> (liste, behaltene pair_ids)."""
    S0 = teile(len(C), [k for k in quer_alle if k not in falsch]); ok = {k for s in S0 if sum(ref(k) for k in s) > 0 for k in s}
    mitte = None; oj = a.objekt or a.fernsicht
    if oj:
        sys.path.insert(0, T); from netz_fotos_holen import geo; mitte = geo(json.load(open(oj)))
    sys.path.insert(0, T); d = durchblick_stufe(db, nm, g, falsch, ok, mitte=mitte, bilder=a.bilder, bruecke_min=a.min_inlier)
    beh = {x["pair_id"] for x in d if x["urteil"] == "durchblick"}; z = collections.Counter(tuple(sorted((x["ga"], x["gb"]))) for x in d if x["urteil"] == "durchblick")
    for v in verb:
        if z.get((v["a"], v["b"])): v["durchblick_paare"] = z[(v["a"], v["b"])]
    nb = sum(1 for x in d if x.get("bruecke") and x["urteil"] == "durchblick")
    print(f"DURCHBLICK/UMGEBUNG: {len(d) - sum(1 for x in d if x.get('bruecke'))} starke Paare (>= {DURCH_MIN_INLIER} Inlier) in verwechselten/unklaren Verbindungen gemessen, {len(beh)} behalten "
          f"(davon {nb} schwaechere Bruecken-Paare >= {a.min_inlier} an bestaetigten Verbindungen; Gruppenpaare {dict(sorted(z.items()))}); abgelehnt: {collections.Counter(x['grund'].split(' ')[0] for x in d if x['urteil'] != 'durchblick')}", flush=True)
    return d, beh


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("db"); ap.add_argument("bilder"); ap.add_argument("--aus", required=True); ap.add_argument("--db-aus"); ap.add_argument("--min-bilder", type=int, default=12)
    ap.add_argument("--min-paare", type=int, default=20); ap.add_argument("--min-inlier", type=int, default=30); ap.add_argument("--stichprobe", type=int, default=24); ap.add_argument("--schwelle", type=float, default=0.45)
    ap.add_argument("--referenz", default="eigen__", help="Namensanfang der Objektfotos (Sammelordner tools/fotos_sammeln.py)"); ap.add_argument("--trocken", action="store_true", help="nur Gruppen und Verbindungen zaehlen, kein Pruefer")
    ap.add_argument("--aufloesung", type=float, default=2.0, help="Louvain-Aufloesung: groesser = kleinere Gruppen. 1.0 liess am Martinstor eine Gruppe am Tordurchgang gemischt (Nahaufnahmen BEIDER Seiten), 2.0 trennt sie")
    ap.add_argument("--streng", action="store_true", help="nur bestaetigte Verbindungen behalten: auch 'unklare' und ungepruefte schwache Verbindungen zwischen Gruppen loeschen (Verklebung laeuft sonst ueber Umwege, Martinstor 19.11.2026)")
    ap.add_argument("--pruefer-aus", help="Pruefer-Ergebnisse (p je Verbindung) aus einer frueheren seiten.json derselben Datenbank uebernehmen statt neu zu rechnen (Cache)")
    ap.add_argument("--masken", help="Ordner mit Vordergrund-Masken (tools/handy_masken.py; <bildname>.png, 0 = Person/Fahrzeug): der Paar-Pruefer sieht den Vordergrund grau (Martinstor 21.11.2026: Person auf beiden Torseiten = falsche Bruecke)"); ap.add_argument("--objekt", help="objekt.json: mit Objektmitte + EXIF-GPS der Fotos entscheidet die STANDRICHTUNG je Bildgruppe vor dem Pruefer (Nutzer 19.11.2026: kuenftig GPS im EXIF; muss auch ohne gehen)")
    ap.add_argument("--durchblick", action="store_true", help="Stufe Durchblick/Umgebung (auch RCPARK_SEITEN_DURCHBLICK=1): einzelne Paare verwechselter/unklarer/ungepruefter Verbindungen mit >= 200 nicht-statischen Inliern ueber >= 12/64 Bildzellen bleiben (Uebereck-/Umgebungsfotos); GPS-Veto bei --objekt/--fernsicht")
    ap.add_argument("--durchblick-getrennt", action="store_true", help="wie --durchblick (auch RCPARK_SEITEN_DURCHBLICK=getrennt), aber die Brueckenpaare vereinen die Teile NICHT: nur Liste 'durchblick' + Paare in --db-aus fuer tools/seiten_eck_koppeln.py (Kette)")
    ap.add_argument("--fernsicht", help="objekt.json: NUR die Fernsicht-Regel (Gruppen mit GPS-Fotos >= 100 m behalten unter --streng ihre staerkste unklare Verbindung), ohne GPS-Richtungs-Urteil (--objekt)")
    a = ap.parse_args(argv); db = sqlite3.connect(f"file:{a.db}?mode=ro", uri=True); nm = dict(db.execute("select image_id, name from images"))
    K = [(pid // MAXID, pid % MAXID, rows) for pid, rows in db.execute("select pair_id, rows from two_view_geometries where rows >= ?", (a.min_inlier,))]
    C = gemeinschaften(K, list(nm), aufloesung=a.aufloesung); g = {i: k for k, c in enumerate(C) for i in c}; gross = [k for k, c in enumerate(C) if len(c) >= a.min_bilder]
    quer_alle = {tuple(sorted((g[pid // MAXID], g[pid % MAXID]))) for (pid,) in db.execute("select pair_id from two_view_geometries") if g[pid // MAXID] != g[pid % MAXID]}
    quer = collections.defaultdict(list)
    for x, y, r in K:
        if g[x] != g[y]: quer[tuple(sorted((g[x], g[y])))].append((x, y, r))
    print(f"{len(nm)} Bilder, {len(K)} Paare >= {a.min_inlier}: {len(C)} Gemeinschaften, {len(gross)} mit >= {a.min_bilder} Bildern")
    kand = sorted(k for k, v in quer.items() if len(v) >= a.min_paare and k[0] in gross and k[1] in gross); rnd = random.Random(0); proben = []
    for k in kand:
        v = sorted(quer[k]); rnd.shuffle(v); proben += [(k, nm[x], nm[y]) for x, y, _ in v[:a.stichprobe]]
    print(f"{len(kand)} Gruppenpaare mit >= {a.min_paare} Verbindungen -> {len(proben)} Paare fuer den Pruefer", flush=True)
    verb = []
    alt = {(v["a"], v["b"]): v for v in json.load(open(a.pruefer_aus))["verbindungen"] if v.get("p")} if a.pruefer_aus else None
    if alt is not None and json.load(open(a.pruefer_aus)).get("groessen") != [len(c) for c in C]: sys.exit("FEHLER --pruefer-aus: Gemeinschaften passen nicht zur Datenbank (andere Bilder/Paare) - Pruefer neu laufen lassen")
    if alt is not None: verb = [dict(a=k[0], b=k[1], paare=len(quer[k]), geprueft=len(alt[k]["p"]), p_median=alt[k]["p_median"], p90=alt[k]["p90"], anteil_hoch=alt[k]["anteil_hoch"], p=alt[k]["p"], urteil=urteil(alt[k]["p"])) for k in kand if k in alt]
    elif a.trocken: verb = [dict(a=k[0], b=k[1], paare=len(quer[k]), p_median=None, urteil="ungeprueft") for k in kand]
    else:
        sys.path.insert(0, T); from doppelgaenger_paare import pruefen
        erg = pruefen(a.bilder, [(x, y) for _, x, y in proben], melden=200, masken=a.masken); P = collections.defaultdict(list)
        for (k, _, _), e in zip(proben, erg):
            if e[2] is not None: P[k].append(e[2])
        for k in kand:
            pm = float(np.median(P[k])) if P[k] else 1.0
            verb.append(dict(a=k[0], b=k[1], paare=len(quer[k]), geprueft=len(P[k]), p_median=round(pm, 3), p90=round(float(np.percentile(P[k], 90)), 3) if P[k] else None,
                             anteil_hoch=round(float((np.array(P[k]) >= 0.8).mean()), 3) if P[k] else None, p=[round(x, 3) for x in P[k]], urteil=urteil(P[k])))
    gr = {}; fern = set()
    if a.fernsicht and not a.objekt:                                               # nur die Fernsicht-Regel (Kette: sfm_seiten_vorstufe mit RCPARK_SEITEN_OBJEKT)
        sys.path.insert(0, T); from paarvorwahl import gps_aus_exif; from netz_fotos_holen import geo
        mitte = geo(json.load(open(a.fernsicht))); gq = collections.defaultdict(list)
        if mitte:
            for i, n in nm.items():
                q = gps_aus_exif(os.path.join(a.bilder, n))
                if q is not None: gq[g[i]].append(q)
            fern = fernsicht_gruppen(gq, mitte)
    if a.objekt:                                                                   # GPS-Anker: staerkste Stimme, wo vorhanden
        sys.path.insert(0, T); from paarvorwahl import gps_aus_exif; from netz_fotos_holen import geo
        mitte = geo(json.load(open(a.objekt))); az = collections.defaultdict(list); n_gps = 0; gq = collections.defaultdict(list)
        if mitte:
            for i, n in nm.items():
                q = gps_aus_exif(os.path.join(a.bilder, n))
                if q is None: continue
                w, d = richtung(mitte, q); gq[g[i]].append(q)
                if 15.0 <= d <= 300.0: az[g[i]].append(w); n_gps += 1             # naeher als 15 m: Richtung unbestimmt (GPS-Fehler 5-15 m); weiter als 300 m: Ortsmarke statt Standort
            fern = fernsicht_gruppen(gq, mitte)
            gr = {k: gruppen_richtung(v) for k, v in az.items() if k not in fern}; gr = {k: v for k, v in gr.items() if v}
            for v in verb:
                u = urteil_gps(gr.get(v["a"]), gr.get(v["b"]))
                if gr.get(v["a"]) and gr.get(v["b"]): v["gps_richtung"] = [round(gr[v["a"]][0]), round(gr[v["b"]][0])]
                # GPS ueberstimmt NIE ein klares 'echt' des Pruefers: in der Strassenschlucht liegt Handy-GPS 5-15 m daneben, bei 20 m Abstand zum Turm sind das zig Grad
                # (Schwabentor 19.11.2026: Gruppen 2/4 laut GPS 199 Grad auseinander, im GPS-gepruefte Modell 60 Grad, Pruefer 54 % eindeutig gleich).
                if u and u != v["urteil"] and v["urteil"] != "echt": v["urteil_pruefer"] = v["urteil"]; v["urteil"] = u; v["quelle"] = "gps"
                elif u == "verwechselt" and v["urteil"] == "echt": v["hinweis"] = "GPS-Richtungen widersprechen dem Pruefer (GPS ungenau?) - nicht geloescht"
            # Gruppenpaare mit Verbindungen, die der Pruefer NICHT sah (weniger als --min-paare): GPS entscheidet sie trotzdem
            for k, vq in quer.items():
                if k in kand: continue
                if urteil_gps(gr.get(k[0]), gr.get(k[1])) == "verwechselt": verb.append(dict(a=k[0], b=k[1], paare=len(vq), p_median=None, urteil="verwechselt", quelle="gps", gps_richtung=[round(gr[k[0]][0]), round(gr[k[1]][0])]))
        print(f"GPS-Anker: {n_gps} Fotos mit Standort 15-300 m um die Objektmitte, {len(gr)} Bildgruppen mit Standrichtung; {sum(1 for v in verb if v.get('quelle') == 'gps')} Verbindungen durch GPS entschieden" if mitte else "GPS-Anker: objekt.json ohne Objektmitte (koordinate_utm) - uebersprungen")
    falsch = {(v["a"], v["b"]) for v in verb if v["urteil"] == "verwechselt"}
    if a.streng:                                                                   # nur BESTAETIGTE Verbindungen behalten: alles zwischen zwei Gruppen, was nicht 'echt' ist, faellt weg
        echt = {(v["a"], v["b"]) for v in verb if v["urteil"] == "echt"} | fernsicht_behalten(verb, fern, quer); falsch = {k for k in quer_alle if k not in echt}
        if fern: print(f"FERNSICHT: Gruppen {sorted(fern)} (GPS-Fotos >= {FERN_M:.0f} m) - behaltene Verbindung(en): {sorted((v['a'], v['b']) for v in verb if v.get('fernsicht_behalten'))}")
    # Zusammenhang der Gruppen ohne die verwechselten Verbindungen (kleine Gruppen und ungepruefte schwache Verbindungen zaehlen als echt)
    ref = lambda k: sum(1 for i in C[k] if nm[i].startswith(a.referenz))
    durch = []; behalten = set()
    if a.durchblick or a.durchblick_getrennt or os.environ.get("RCPARK_SEITEN_DURCHBLICK", "0") in ("1", "getrennt"):   # Stufe Durchblick/Umgebung: einzelne starke Paare verwechselter/unklarer Verbindungen behalten
        durch, behalten = durchblick_einbauen(a, db, nm, g, C, quer_alle, falsch, ref, verb)
    # --durchblick-getrennt (Kette, 23.11.2026): Brueckenpaare messen, in seiten.json 'durchblick' melden und in --db-aus BEHALTEN (das Eckmodell der Stufe
    # tools/seiten_eck_koppeln.py braucht sie), aber die Teile NICHT darueber vereinen - ein Mapper ueber die duenne Bruecke knickte 1122 Teil 1 um 16-25 Grad
    # (lage-seiten.md 22.11.); gekoppelt wird erst nach den Teilmodellen ueber das Eckmodell.
    getrennt = a.durchblick_getrennt or os.environ.get("RCPARK_SEITEN_DURCHBLICK", "") == "getrennt"
    S = teile(len(C), [k for k in quer_alle if k not in falsch] + ([] if getrennt else [tuple(sorted((d["ga"], d["gb"]))) for d in durch if d["urteil"] == "durchblick"]))
    seiten = [s for s in S if sum(ref(k) for k in s) > 0]; fremd_g = {k for s in S if sum(ref(k) for k in s) == 0 for k in s}; fremd = sorted(nm[i] for k in fremd_g for i in C[k])
    for v in sorted(verb, key=lambda v: v.get("p90") if v.get("p90") is not None else 9)[:40]:
        print(f"  Gruppe {v['a']:3d} ({len(C[v['a']]):4d} Bilder) <-> {v['b']:3d} ({len(C[v['b']]):4d}): {v['paare']:5d} Paare, p_gleich Median {v['p_median']}, 90 % unter {v.get('p90')}, eindeutig gleich {v.get('anteil_hoch')}  {v['urteil'].upper() if v['urteil'] != 'echt' else 'echt'}" + (f"  [GPS {v['gps_richtung'][0]} / {v['gps_richtung'][1]} Grad]" if v.get("gps_richtung") else ""))
    for n, s in enumerate(seiten[:6]):
        q = collections.Counter(quelle(nm[i]) for k in s for i in C[k]); print(f"  Teil {n}: {sum(len(C[k]) for k in s)} Bilder in {len(s)} Gruppen ({', '.join(f'{x[-14:]} {c}' for x, c in q.most_common(4))})")
    geloescht = 0
    if a.db_aus and (not a.trocken or alt is not None):
        shutil.copyfile(a.db, a.db_aus); d2 = sqlite3.connect(a.db_aus); weg = []
        for (pid,) in d2.execute("select pair_id from two_view_geometries"):
            x, y = pid // MAXID, pid % MAXID; k = tuple(sorted((g[x], g[y])))
            if (k in falsch and pid not in behalten) or g[x] in fremd_g or g[y] in fremd_g: weg.append((pid,))
        d2.executemany("delete from two_view_geometries where pair_id = ?", weg); d2.executemany("delete from matches where pair_id = ?", weg); d2.commit(); d2.close(); geloescht = len(weg)
    json.dump(dict(db=os.path.abspath(a.db), gemeinschaft={nm[i]: k for i, k in g.items()}, groessen=[len(c) for c in C], verbindungen=verb, verwechselt=[list(k) for k in sorted(falsch)],
                   seiten=[dict(gruppen=s, bilder=sum(len(C[k]) for k in s)) for s in seiten], fremd=fremd, geloeschte_paare=geloescht, schwelle=a.schwelle, fernsicht=sorted(fern),
                   durchblick=[{k: v for k, v in x.items() if k != "pair_id"} for x in durch if x["urteil"] == "durchblick"],
                   durchblick_abgelehnt=len(durch) - len(behalten), durchblick_getrennt=bool(durch) and getrennt), open(a.aus, "w"), indent=1)
    print(f"Seitenerkennung: {len(falsch)} verwechselte Gruppenverbindung(en), {sum(1 for v in verb if v['urteil'] == 'unklar')} unklar; {len(seiten)} Teil(e) mit Objektfotos, {len(fremd)} fremde Bilder"
          + (f"; {geloescht} Paare geloescht -> {a.db_aus}" if a.db_aus and not a.trocken else ""))
    if falsch: print("WARNUNG SEITENVERWECHSLUNG: Bildgruppen zeigen aehnliche, aber verschiedene Seiten - ihre Paare duerfen nicht in den Mapper (bereinigte Datenbank nehmen).")
    gr = [s for s in seiten if sum(len(C[k]) for k in s) >= a.min_bilder]
    if len(gr) > 1: print(f"WARNUNG: {len(gr)} Bildteile mit Objektfotos ohne echte Verbindung untereinander - der Mapper liefert getrennte Modelle (Seiten vereinen noetig).")
    return 3 if falsch else 0


if __name__ == "__main__": sys.exit(main())
