#!/usr/bin/env python3
"""seiten_eck_koppeln.py <db_mapper> <seiten.json> <fotos> --teil N=<modell> [--teil M=<modell> ...] --aus <ordner>   (erster --teil = Teil A, Bezugsrahmen)

TEILE UEBER BRUECKEN-ZWISCHENMODELLE KOPPELN (22.11.2026, erst schwabentor-1122, dann verallgemeinert; Nutzer: "Ich will es jetzt generalisiert geloest.").
WANN: nur wenn die Bilder NICHT von selbst ein Modell ergeben. Reihenfolge in der Kette: (1) normaler Weg - ein Modell aus allen Bildern; (2) zerfaellt es in Teile
(seiten_erkennen/sfm_seiten_modelle), sucht seiten_erkennen --durchblick bestaetigte Brueckenpaare zwischen den Gruppen; (3) erst wenn die Klappung (seiten_vereinen)
einen Teil NICHT anbindet, koppelt diese Stufe ueber die Brueckenpaare; (4) sonst GPS-Weg / Fotoluecke. Ein zusammenhaengendes Modell (ein Teil) wird nie veraendert
(rc 2, kein Ergebnis; Test). Befund 1122: der GLOBALE Mapper ueber alle Bilder knickte Teil 1 an der Bruecke um 25 Grad, ein Anbau mit --input_path registrierte 0 Bilder.
ABLAUF (beliebig viele Teile, Bruecken jeder Art):
  1. KNOTEN = alle Teilmodelle. BRUECKEN = Durchblick-Paare (seiten.json 'durchblick', urteil 'durchblick', inkl. 'Bruecke erweitern'), die nicht ganz in einem Teil liegen.
     Zusammenhangsstuecke der Brueckenpaare (ueber gemeinsame Bilder), die >= 2 Teile beruehren, sind KANDIDATEN; Stuecke an nur einem Teil zaehlen nicht (1122: Paare
     zwischen Videobildern ausserhalb aller Teile zogen sonst 124 Bilder in 3 getrennte Modelle).
  2. ZWISCHENMODELL je Kandidat: Brueckenbilder + NACHBAR_TIEFE Schritte starker Nachbarn (je NACHBARN_JE_BILD, >= NACHBAR_MIN Inlier), schrittweiser COLMAP-Mapper.
     SCHWELLE abs_pose_min_num_inliers NICHT frei gewaehlt: der Reihe nach SCHWELLEN (30 = COLMAP-Standard, 20, 15, 12, 10); genommen wird die STRENGSTE, bei der ein Modell
     >= MIN_BILDER_TEIL Bilder aus >= 2 beruehrten Teilen enthaelt. Die naechst lockerere Schwelle wird zur SENSITIVITAET mitgerechnet: Kopplung (Drehung, Massstab,
     Versatz) bei beiden Schwellen im Stufen-JSON ('sensitivitaet'). 1122 (Handliste 44 Bilder): 30 und 15 zerfielen, 12 verband; mit der Nachbarregel hier: 20
     verbindet, 15 ergibt dieselbe Kopplung (Sensitivitaet 0). Untergrenze 10: ANNAHME (P3P braucht 4; < 10 Inlier je Bild nicht von Fehlregistrierung zu trennen).
     NACHMATCHEN (RCPARK_ECK_NACHMATCHEN, Standard an): vor dem Mapper die Zwischenmodell-Bilder + EXIF-Zeitnachbarn (Rundgang, ZEIT_FENSTER_S) mit ALIKED+LightGlue
     paarweise nachmatchen (tools/bruecke_nachmatchen.py, an SIFT angehaengt, SIFT-Indizes unveraendert -> Kopplung ueber SIFT-Punkte bleibt gueltig). Gescheitert ->
     SIFT-Datenbank. Selbsttest Martinstor k=3: 0,83 -> 0,21 Grad, Lage 0,14 -> 0,024 m.
     DUENNE BRUECKE MERKEN (23.11.2026, Befund 1122t): registriert das Modell der strengsten verbindenden Schwelle NICHT alle Listenbilder der beruehrten Teile, ist die
     Bruecke dort duenn -> die Leiter geht weiter; genommen wird die strengste Schwelle mit den MEISTEN registrierten Teil-Bildern (Gleichstand -> strengere), die
     naechst lockerere bleibt Sensitivitaet ('bruecke_duenn' im JSON). Kopplungsgrenzen bleiben unberuehrt.
     TEILKAMERAS (23.11.2026, RCPARK_ECK_TEILKAMERAS, Standard an; Kopf 'TEILKAMERAS' unten): dritte Variante - Mapper mit den Kameras (Intrinsik) der Teilmodelle, fest.
     WIEDERHOLBARKEIT (Stabilitaetsmass): WIEDERHOLUNGEN Laeufe mit je WEGLASSEN der Nicht-Brueckenbilder weg -> Streuung der Kantenlage im JSON ('wiederholbarkeit').
  3. KOPPLUNG Zwischenmodell -> jeder beruehrte Teil ueber GEMEINSAME 3D-PUNKTE (gleicher Bildpunkt gemeinsamer Bilder), robuste Sim3 (sim3_robust.sim3_meter, Schwelle
     SCHWELLE_REL x Ausdehnung). Stimmig nur bei >= MIN_PUNKTE stimmigen Punkten, Anteil >= MIN_ANTEIL, Rest <= REST_REL x Ausdehnung, Massstab Haelften-Probe <= MASS_REL
     (sonst 'Massstab nicht belegt'); Hebel = Ausdehnung der gemeinsamen Punkte / Ausdehnung des Teils. Begruendung 1122: Ecke->A 96 % stimmig, Rest 0,34 %, Ecke->B
     96 %, 0,21 %; Zufall / andere Flaeche -> keine Sim3; 8 % Verformung -> Anteil 53 % (Test).
     KANTE i-j = zwei stimmige Kopplungen desselben Zwischenmodells; Guete = min(stimmig x Hebel).
     LEITER je Kante (22.11.2026, tools/bruecke_hebel.leiter, RCPARK_ECK_LEITER=0 aus): gemeinsamer Ausgleich (tiefengewichtet) -> Urteil stark/duenn/zu duenn ->
     bei nicht 'stark' gefuehrtes Nachmessen (Kandidatenpaare aus der Naeherung, ALIKED+LightGlue, Epipolarband, direkte Spuren A<->B) -> Ausgleich mit direkten
     Spuren, nur wenn diese die Naeherung bestaetigen; Lot der Teile = PRUEFUNG ('leiter.lot_pruefung'). Belege und Schwellen: bruecke_hebel-Kopf, lage-seiten.md.
  4. STAERKSTER SPANNBAUM ab Teil A (Prim, groesste Guete zuerst) -> Lage jedes erreichten Teils im Rahmen von A. Jede weitere Kante schliesst einen KREIS = unabhaengige
     Pruefung: Kreisschlussfehler (Drehung Grad, Massstab, Versatz relativ zur Ausdehnung) gegen 3 x sigma, sigma = Wurzel der Quadratsumme der Kopplungsreste und
     Haelften-Proben aller Kanten im Kreis (ANNAHME: Rest = 1 sigma). Widerspruch -> alle Teile des Kreises (ausser A) und was nur durch sie erreicht wird: NICHT gekoppelt.
  5. Ausgabe <aus>/eck.json: teile{N: ok, M_nach_A (4x4), weg, massstab_unsicher}, kanten, kreise, zwischenmodelle, fotoluecken (Teil + gewuenschte Verbindung).
     rc 0 = mindestens ein Teil gekoppelt, 2 = nichts zu koppeln (ein Teil / keine Bruecke / kein Zwischenmodell), 3 = Kandidaten, aber keine stimmige Kopplung.
Danach (sfm_seiten_modelle): Blick-Tor + GPS-Seiten-Tor (Veto); wand_dicke/Grundriss als Tore der Kette nach der Ausrichtung."""
import os, sys, json, argparse, sqlite3, subprocess, shutil, numpy as np
T = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, T)
from sim3_robust import sim3_meter, umeyama, matrix, anwenden

MAXID = 2147483647
NACHBAR_MIN = 200        # wie DURCH_MIN_INLIER: nur starke Nachbarpaare ziehen Bilder ins Zwischenmodell
NACHBARN_JE_BILD = int(os.environ.get("RCPARK_ECK_NACHBARN", "5"))     # ANNAHME: je Bild die 5 staerksten Nachbarn, zwei Schritte weit; alle Nachbarn >= 200 = 196 Bilder (1122, > 10 min), ein Schritt = 14 Bilder (nur 2 Teil-0-Bilder)
NACHBAR_TIEFE = int(os.environ.get("RCPARK_ECK_TIEFE", "2"))
SCHWELLEN = (30, 20, 15, 12, 10)   # abs_pose_min_num_inliers: strengste verbindende gewinnt (Kopf 2)
MIN_BILDER_TEIL = 3
MIN_PUNKTE = 100
MIN_ANTEIL = 0.8
REST_REL = 0.005         # Rest-Median (tiefenbezogen) hoechstens 0,5 % - EICHUNG unten
# EICHUNG 22.11.2026 (tools/versuche/eck_rest_eichung.py, /media/oem/rcdaten/tmp/durchblick/eichung_rest.json; 20 richtige Kopplungen aus Selbsttests Martinstor_gk +
# Kaufhaus_gk, k = 3/5/10, mit/ohne Nachmatchen, je gegen falsche Faelle am selben Paar):
#   richtig: Rest 0,12-0,59 %, Anteil 0,77-0,98, Trend (Rest fern/nah) 0,29-2,6;  Spiegel (Seitenverwechslung): Rest 0,32-0,94 %, Anteil 0,28-0,72 -> alle abgelehnt;
#   Zufall: keine Sim3. Der REST trennt richtig/falsch NICHT (Bereiche ueberlappen), der ANTEIL trennt (0,72 | 0,77; Grenze 0,80 lehnt 4 richtige ab, keine falsche an).
#   Grenze 0,5 % bleibt: 0,63 % (1122 mit Nachmatchen) liegt ueber ALLEN richtigen Faellen (max 0,59 %) und im Spiegelbereich -> nicht sicher -> abgelehnt.
#   VERFORMUNG EINES TEILS ueber seine Laenge (Massstabsverlauf 2/5 %, Biegung 1/3 Grad) besteht die Kopplung meist (16/20 bzw. 13/20): die gemeinsamen Punkte
#   decken nur einen Teil des Teils ab, lokal ist die Verformung fast eine Aehnlichkeit. Das kann KEINE Kopplungspruefung sehen -> unabhaengige Tore noetig
#   (Kreisschluss, Innenflaechen, GPS-Veto, Grundriss). Ein Trend-Kriterium (Rest waechst mit Abstand) trennt in den Daten ebenfalls nicht (richtig bis 2,6).
SCHWELLE_REL = 0.02      # Inlier-Schwelle der Sim3: 2 % der Ausdehnung
MASS_REL = 0.02          # Massstab-Unsicherheit (Haelften-Probe) hoechstens 2 % - ANNAHME seit 6a01c48d6 (22.11.), NICHT geeicht (Stand 23.11., unveraendert):
# Eichdaten /media/oem/rcdaten/tmp/durchblick/eichung_rest.json (20 richtige Kopplungen): Haelften 0,14-2,96 %, Median 0,54 %; 1 von 20 nur an dieser Grenze abgelehnt.
# Spiegel 0,01-2,17 % (Median 0,29 %) -> die Haelften-Probe trennt richtig/Spiegel NICHT; sie misst einen MASSSTABSVERLAUF zwischen Eckmodell und Teil (systematisch,
# Bootstrap 1122t Teil 1 2,31 +- 0,06 %), kein Rauschen. Grosser Hebel macht sie empfindlicher (lange Strecke), nicht wertlos.
# TEILKAMERAS (23.11.2026, Befund 1122t, Proben /media/oem/rcdaten/tmp/bruecke_sued_agent): der Eck-Mapper verfeinert die Brennweite JEDES Bildes neu - mit 35 statt
# 127 Bildern landen Netzfotos 8-18 % neben dem Teilmodell (netz_commons_geo__120: 2978 vs 3514 px, commons_orig2__104: 1926 vs 2110), Handyfotos +-3 %. Falsche
# Brennweite = tiefenabhaengige Verzerrung: Massstab Eck->Teil 1 faellt mit der Tiefe (Quintile 0,1249 -> 0,1214 bei Tiefe 4,2 -> 6,9) -> Haelften 2,3 %. Dieselben 35
# Bilder mit den Kameras der Teilmodelle (fest): Teil 1 Haelften 0,07 %, Rest 0,09 % (vorher 0,32 %), Kamerazentren 0,33 % statt 4,2 % der Tiefe. Das Eckmodell
# muss dieselbe Kamerageometrie haben wie die Teile, die es koppelt - sonst misst die Kopplung die Kameraabweichung statt der Lage.
TEILKAMERAS = os.environ.get("RCPARK_ECK_TEILKAMERAS", "1") != "0"
# KAMERA-PROBE (23.11.2026): Sim3 aus den Punkten muss auch die KAMERAZENTREN der gemeinsamen Bilder treffen: Median |M*C_eck - C_teil| / (s * Median-Tiefe) <= KAM_REL.
# ROT-PROBE ohne sie: eine Wand ist fast ihr eigenes Spiegelbild - der gespiegelte Teil 1 (1122t, Teilkameras) bestand Anteil 0,815 / Rest 0,30 %; in den Selbsttests
# bestanden 2 weitere Spiegel. Spiegel bringt die Kameras auf die andere Wandseite. EICHUNG (b2_kam_eich, Selbsttests Martinstor/Kaufhaus + 1122t, 119 Paare):
# alle 93 angenommenen richtigen Kopplungen 0,33-3,9 % (Median 1,3 %); alle 119 Spiegel 117-265 %. KAM_REL = 0,2: ANNAHME in der Luecke (5x ueber richtig, 6x unter Spiegel).
KAM_REL = 0.2
KREIS_SIGMA = 3.0
WIEDERHOLUNGEN = int(os.environ.get("RCPARK_ECK_WIEDERHOLUNGEN", "3"))   # Stabilitaetsmass: Laeufe mit weggelassenen Bildern
NACHMATCHEN = os.environ.get("RCPARK_ECK_NACHMATCHEN", "1") != "0"   # Brueckenbilder mit ALIKED+LightGlue nachmatchen (tools/bruecke_nachmatchen.py, GPU)
ZEIT_FENSTER_S = float(os.environ.get("RCPARK_ECK_ZEITFENSTER", "30"))  # ANNAHME: eigene Fotos (EXIF-Zeit) bis 30 s um ein Brueckenbild = Rundgang-Nachbarn
WEGLASSEN = 0.2          # ANNAHME: je Wiederholung 20 % der Nicht-Brueckenbilder weg (Bruecke selbst bleibt)
COLMAP = os.environ.get("RCPARK_COLMAP", "/media/oem/scan/colmap-build/prefix/bin/colmap")
NACHMATCH_VRAM_MB = int(os.environ.get("RCPARK_ECK_VRAM_MB", "4500"))
# GLEICHE EINGABE = GLEICHES ERGEBNIS (23.11.2026, Befund Kippeln 1122r 'vereint' / 1122s 'nicht vereint', tools/test_seiten_eck_koppeln.py):
#  (1) Der COLMAP-Mapper oeffnet die Datenbank schreibend - jeder Eck-Mapper-Lauf setzte die Aenderungszeit von db_mapper.db neu (1122r 11:41:57, 1122s 14:14:48,
#      Inhalt/Groesse gleich). sfm_seiten_modelle bindet die Teilmodelle an (Groesse, Aenderungszeit) der DB -> der NAECHSTE Kettenlauf hielt die Eingabe fuer geaendert,
#      rechnete die Teilmodelle neu (globaler Mapper, nicht deterministisch: Teil 1 127 -> 125 Bilder) und die Haelften-Probe von Teil 1 sprang 1,8 % -> 2,2 % (Grenze 2 %),
#      der Rest von Teil 0 0,47 % -> 0,54 % (Grenze 0,5 %) - mit JEDEM der 31 Eckmodelle beider Laeufe (Kreuzprobe), Bootstrap-Streuung der Probe nur +-0,1 %.
#      Daher: alle Mapper laufen auf einer KOPIE (sqlite-Backup, Quelle nur lesend), die Eingabe-DB wird vor/nach verglichen ('eingabe_db' im JSON).
#  (2) Eck-Mapper mit festem Keim und einem Faden: 1122r/1122s lieferten aus derselben Bildliste verschiedene Eckmodelle (lg-Variante: Schwelle 30 verband einmal, einmal nicht).
MAPPER_KEIM = int(os.environ.get("RCPARK_ECK_KEIM", "0"))              # --Mapper.random_seed (COLMAP -1 = zufaellig)
MAPPER_FAEDEN = int(os.environ.get("RCPARK_ECK_MAPPER_FAEDEN", "1"))   # ANNAHME: 1 Faden = reproduzierbar (Ceres/RANSAC mehrfaedig reihenfolgeabhaengig); Eckmodelle 35-47 Bilder; 0 = --faeden
NAMEN = {}               # Teil -> registrierte Bildnamen (main)


def ausdehnung(X):
    X = np.asarray(X, float); return float(np.percentile(np.linalg.norm(X - np.median(X, 0), axis=1), 90)) if len(X) else 0.0


def winkel(R): return float(np.degrees(np.arccos(np.clip((np.trace(R) - 1) / 2, -1, 1))))


def zerlegen(M):
    """4x4 Sim3 -> (s, R, t)."""
    M = np.asarray(M, float); s = float(np.cbrt(np.linalg.det(M[:3, :3]))); return s, M[:3, :3] / s, M[:3, 3]


def punkte(rE, rZ, mit_tiefe=False):
    """Gemeinsame 3D-Punkte (Bildname + Keypoint-Index gemeinsamer Bilder, in beiden Modellen trianguliert) -> (X_eck, X_ziel, gemeinsame Bilder[, Tiefe im Eckmodell])."""
    E = {im.name: im for im in rE.images.values() if im.has_pose}; Z = {im.name: im for im in rZ.images.values() if im.has_pose}; pe, pz, td, ges = [], [], [], set(); ns = sorted(set(E) & set(Z))
    for n in ns:
        a_, b_ = E[n].points2D, Z[n].points2D; c = E[n].projection_center()
        for k in range(min(len(a_), len(b_))):
            if a_[k].has_point3D() and b_[k].has_point3D() and (a_[k].point3D_id, b_[k].point3D_id) not in ges:
                ges.add((a_[k].point3D_id, b_[k].point3D_id)); x = rE.points3D[a_[k].point3D_id].xyz; pe.append(x); pz.append(rZ.points3D[b_[k].point3D_id].xyz); td.append(np.linalg.norm(x - c))
    aus = (np.array(pe).reshape(-1, 3), np.array(pz).reshape(-1, 3), ns)
    return aus + (np.array(td),) if mit_tiefe else aus


def kamera_probe(M, kameras, tiefe):
    """KAMERA-PROBE (Kopf KAM_REL): kameras = (C_eck, C_teil) der gemeinsamen Bilder. -> Median-Abweichung relativ zur Median-Tiefe (im Teil-Massstab) oder None."""
    if kameras is None or tiefe is None or len(kameras[0]) == 0: return None
    s1 = float(np.cbrt(np.linalg.det(M[:3, :3]))); CX, CY = (np.asarray(k, float).reshape(-1, 3) for k in kameras)
    return float(np.median(np.linalg.norm(anwenden(M, CX) - CY, axis=1)) / max(abs(s1) * float(np.median(tiefe)), 1e-12))


def kopplung_pruefen(X, Y, ausd, ausd_ziel=None, tiefe=None, fitter=None, gewicht=None, kameras=None):
    """Sim3 X -> Y (X im Zwischenmodell, Y im Teilmodell; ausd = Ausdehnung des Zwischenmodells, ausd_ziel = des Teils fuer den Hebel). -> (M, pruefung, ok, grund).
    FEHLERMASS (22.11.2026, Selbsttest Martinstor): mit 'tiefe' (Abstand Punkt - beobachtende Kamera im Zwischenmodell) wird der Rest RELATIV ZUR TIEFE gemessen (= Blickstrahl-
    Winkel, 2 % ~ 1,1 Grad). Relativ zur Ausdehnung bestrafte es ferne, schlecht triangulierte Punkte: ein nachweislich RICHTIGES Zwischenmodell stimmte gegen das Ursprungs-
    modell nur zu 82 % (Teil A 65 %) - abgelehnt; tiefenbezogen 89-98 % (1122: 93 %). Grenzen (Anteil, Rest, Haelften) unveraendert."""
    if len(X) < MIN_PUNKTE: return None, dict(punkte=len(X)), False, f"nur {len(X)} gemeinsame Punkte (< {MIN_PUNKTE})"
    f = sim3_meter(X, Y, schwelle_m=float("inf"), min_anteil=0.0)                   # grobe Lage fuer den Massstab der Schwelle im Zielrahmen
    s_ = float(np.cbrt(abs(np.linalg.det(f["M"][:3, :3])))) if f else 1.0
    f = sim3_meter(X, Y, schwelle_m=SCHWELLE_REL * ausd * s_, min_anteil=0.0)
    if f is None: return None, dict(punkte=len(X)), False, "keine Sim3"
    M = f["M"]; inl = f["inlier"]; mass = "ausdehnung"
    def fit(m):                                                                        # m: Maske/Indizes der verwendeten Punkte
        if gewicht is not None: from sim3_robust import umeyama_w; return umeyama_w(X[m], Y[m], np.asarray(gewicht)[m])
        return (fitter or umeyama)(X[m], Y[m])
    if (fitter is not None or gewicht is not None) and inl.sum() >= 3: M = matrix(*fit(inl))
    if tiefe is not None and len(tiefe) == len(X):
        mass = "tiefe"
        for _ in range(5):                                                             # tiefenbezogene Inlier, Umeyama neu, bis stabil
            s1 = float(np.cbrt(np.linalg.det(M[:3, :3]))); r = np.linalg.norm(anwenden(M, X) - Y, axis=1) / (s1 * np.maximum(tiefe, 1e-12)); inl = r <= SCHWELLE_REL
            if inl.sum() < 3: break
            M = matrix(*fit(inl))
        s1 = float(np.cbrt(np.linalg.det(M[:3, :3]))); r = np.linalg.norm(anwenden(M, X) - Y, axis=1) / (s1 * np.maximum(tiefe, 1e-12)); inl = r <= SCHWELLE_REL
        rest_rel = float(np.median(r[inl])) if inl.any() else 1.0
    else: rest_rel = f["rest_median_m"] / max(ausd * s_, 1e-12)
    n_in = int(inl.sum()); ant = n_in / len(X); i_ = np.flatnonzero(inl)
    if n_in < 3: return None, dict(punkte=len(X)), False, "keine Sim3"
    Q = X[i_]; _, _, Vt = np.linalg.svd(Q - Q.mean(0), full_matrices=False); u = (Q - Q.mean(0)) @ Vt[0]
    hs = [fit(i_[w])[0] for w in (u < np.median(u), u >= np.median(u)) if w.sum() >= 3]
    hael = float(abs(hs[0] - hs[1]) / np.mean(hs)) if len(hs) == 2 else 1.0
    pr = dict(punkte=len(X), stimmig=n_in, anteil=round(ant, 3), rest_rel=round(rest_rel, 5), fehlermass=mass, massstab_haelften_rel=round(hael, 4))
    if ausd_ziel: pr["hebel"] = round(ausdehnung(Y[i_]) / max(ausd_ziel, 1e-12), 3)
    kam = kamera_probe(M, kameras, tiefe)
    if kam is not None: pr["kameras_rel"] = round(kam, 4)
    gr = [x for x, schlecht in ((f"Anteil stimmig {ant:.0%} < {MIN_ANTEIL:.0%}", ant < MIN_ANTEIL), (f"stimmig {n_in} < {MIN_PUNKTE}", n_in < MIN_PUNKTE),
                                (f"Rest {rest_rel:.2%} > {REST_REL:.1%}", rest_rel > REST_REL), (f"Massstab nicht belegt (Haelften {hael:.1%} > {MASS_REL:.0%})", hael > MASS_REL),
                                (f"Kameras widersprechen ({(kam or 0):.0%} der Tiefe > {KAM_REL:.0%}; Spiegel/andere Seite?)", kam is not None and kam > KAM_REL)) if schlecht]
    return M, pr, not gr, "; ".join(gr) or "stimmig"


def nachbarn(db):
    c = sqlite3.connect(f"file:{db}?immutable=1", uri=True); nm = {i: n for i, n in c.execute("select image_id, name from images")}; nb = {}
    for pid, r in c.execute("select pair_id, rows from two_view_geometries where rows >= ?", (NACHBAR_MIN,)):
        a, b = nm.get(pid // MAXID), nm.get(pid % MAXID)
        if a and b: nb.setdefault(a, []).append((r, b)); nb.setdefault(b, []).append((r, a))
    return nb


def kandidaten(sj, teil_von, db):
    """Bruecken-Zusammenhangsstuecke, die >= 2 Teile beruehren. teil_von: Bildname -> Teil. -> [dict(paare, teile, bilder)] (bilder = Bruecke + Nachbarn)."""
    br = [d for d in (sj.get("durchblick") or []) if d.get("urteil") == "durchblick" and not (d["a"] in teil_von and teil_von.get(d["a"]) == teil_von.get(d["b"]))]
    eltern = {}
    def wurzel(x):
        while eltern.setdefault(x, x) != x: x = eltern[x]
        return x
    for d in br: eltern[wurzel(d["a"])] = wurzel(d["b"])
    stuecke = {}
    for d in br: stuecke.setdefault(wurzel(d["a"]), []).append(d)
    aus = []; nb = None
    for paare in stuecke.values():
        kern = {d["a"] for d in paare} | {d["b"] for d in paare}; teile = sorted({teil_von[x] for x in kern if x in teil_von})
        if len(teile) < 2: continue
        if nb is None: nb = nachbarn(db)
        bil = set(kern); rand = set(kern)
        for _ in range(NACHBAR_TIEFE):                                                 # Nachbarn der Nachbarn: das Zwischenmodell braucht >= 3 Bilder je Teil mit vielen Punkten
            neu = {x for k in rand for _, x in sorted(nb.get(k, []), reverse=True)[:NACHBARN_JE_BILD]} - bil; bil |= neu; rand = neu
        aus.append(dict(paare=paare, teile=teile, bilder=sorted(bil)))
    return aus


def eckbilder(sj, A, B, db):
    """Kompatibel (zwei Teile): -> (Brueckenpaare, Bilder) der Stuecke zwischen A und B."""
    tv = {**{n: 0 for n in A}, **{n: 1 for n in B}}; ks = kandidaten(sj, tv, db)
    return [d for k in ks for d in k["paare"]], sorted({x for k in ks for x in k["bilder"]})


def mapper(liste, db, fotos, aus, faeden, schwelle, kameras_fest=False):
    os.makedirs(aus, exist_ok=True); lp = os.path.join(aus, "bilder.txt"); open(lp, "w").write("\n".join(liste) + "\n"); sp = os.path.join(aus, "sparse")
    if os.path.isdir(sp): shutil.move(sp, sp + ".alt_" + str(int(os.path.getmtime(sp))))
    os.makedirs(sp); cmd = [COLMAP, "mapper", "--database_path", db, "--image_path", fotos, "--output_path", sp, "--Mapper.image_list_path", lp,
                            "--Mapper.num_threads", str(MAPPER_FAEDEN if MAPPER_FAEDEN > 0 else faeden), "--Mapper.random_seed", str(MAPPER_KEIM),
                            "--Mapper.ba_use_gpu", "0", "--Mapper.abs_pose_min_num_inliers", str(schwelle), "--Mapper.abs_pose_min_inlier_ratio", "0.1"]
    if kameras_fest: cmd += ["--Mapper.ba_refine_focal_length", "0", "--Mapper.ba_refine_extra_params", "0", "--Mapper.ba_refine_principal_point", "0"]   # TEILKAMERAS
    from sfm_seiten_modelle import CUDA_LIBS                                            # die COLMAP-Binaerdatei braucht die CUDA-Bibliotheken (auch ausserhalb der Kette)
    env = dict(os.environ, LD_LIBRARY_PATH=":".join(CUDA_LIBS + [x for x in [os.environ.get("LD_LIBRARY_PATH", "")] if x]))
    with open(os.path.join(aus, "mapper.log"), "w") as lg: rc = subprocess.call(cmd, stdout=lg, stderr=subprocess.STDOUT, env=env)
    return rc, sorted(os.path.join(sp, d) for d in os.listdir(sp) if os.path.isfile(os.path.join(sp, d, "images.bin")))


def teilkameras_setzen(db, bilder, R, ersatz=None):
    """TEILKAMERAS: Kamera-Parameter der Bilder in der ARBEITS-DB (nie der Ketten-DB) durch die des Teilmodells ersetzen, das das Bild registriert.
    Teilt sich eine DB-Kamera Bilder mehrerer Teile mit verschiedenen Werten, gilt der Teil mit den meisten dieser Bilder (Gleichstand: kleinere Teilnummer) -> 'konflikte'.
    Kamera nur ersetzt bei gleichem Modell und gleicher Bildgroesse. ERSATZ (Rekonstruktion, i. d. R. das SIFT-Eckmodell): Bilder in KEINEM Teil (Zeitnachbarn, neue
    Fotos) bekommen dessen verfeinerte Intrinsik statt des DB-Startwerts (mit festen Kameras sonst falsche Schaetzbrennweite); Teile haben Vorrang.
    -> (alte Zeilen [(camera_id, params)] zum Zuruecksetzen, info)"""
    c = sqlite3.connect(db)
    try:
        cam = {n: i for n, i in c.execute("select name, camera_id from images")}; zeile = {i: (m, w, h, p) for i, m, w, h, p in c.execute("select camera_id, model, width, height, params from cameras")}
    except sqlite3.Error as ex: c.close(); return [], dict(gesetzt=0, grund=f"DB ohne Kameratabelle ({str(ex)[:80]})")
    wahl = {}                                                                          # camera_id -> {teil: [params...]}
    Q = dict(R, **({"eck": ersatz} if ersatz is not None else {}))
    for n in bilder:
        for t in sorted(R) + (["eck"] if ersatz is not None else []):
            try:
                im = next((x for x in Q[t].images.values() if x.name == n and x.has_pose), None)
                if im is None or n not in cam: continue
                k = Q[t].cameras[im.camera_id]; m, w, h, _ = zeile[cam[n]]
                if int(k.model.value if hasattr(k.model, "value") else k.model) != m or int(k.width) != w or int(k.height) != h: continue
                wahl.setdefault(cam[n], {}).setdefault(t, []).append(np.asarray(k.params, np.float64))
            except Exception: continue
            break
    alt, konf = [], 0
    for i, je in wahl.items():
        t = max(je, key=lambda x: (x != "eck", len(je[x]), -x if x != "eck" else 0)); p = je[t][0]
        konf += any(not np.allclose(q, p) for tt in je for q in je[tt])
        alt.append((i, zeile[i][3])); c.execute("update cameras set params=? where camera_id=?", (p.tobytes(), i))
    c.commit(); c.close()
    ohne = sum(1 for n in bilder if n in cam and cam[n] not in wahl); vom_eck = sum(1 for je in wahl.values() if set(je) == {"eck"})
    return alt, dict(gesetzt=len(alt), konflikte=konf, bilder_ohne_teilkamera=ohne, kameras_aus_eckmodell=vom_eck)


def teilkameras_zurueck(db, alt):
    c = sqlite3.connect(db); c.executemany("update cameras set params=? where camera_id=?", [(p, i) for i, p in alt]); c.commit(); c.close()


def schwelle_waehlen(treffer, voll):
    """DUENNE BRUECKE MERKEN: treffer = [(schwelle, modell, registrierte Teil-Bilder)] in Leiter-Reihenfolge, voll = Listenbilder der beruehrten Teile.
    -> (Index der Wahl, Index der Sensitivitaet oder None, fertig). Wahl = strengste mit den meisten registrierten Bildern; fertig, sobald die Wahl voll ist und die naechste
    Schwelle als Sensitivitaet gerechnet wurde (ohne Luecke wie bisher: erste Treffer-Schwelle + eine lockerere)."""
    if not treffer: return None, None, False
    n = [x[2] for x in treffer]; w = n.index(max(n)); sens = w + 1 if w + 1 < len(treffer) else None
    return w, sens, bool(n[w] >= voll and sens is not None)


def db_fingerabdruck(db):
    """(Groesse, Aenderungszeit ns) - dasselbe Merkmal, an das sfm_seiten_modelle/_stand die Teilmodelle bindet."""
    st = os.stat(db); return [st.st_size, st.st_mtime_ns]


def arbeits_db(db, aus):
    """Konsistente Kopie der Ketten-DB fuer alle Mapper dieser Stufe (sqlite-Backup, Quelle nur lesend; WAL-Inhalt eingeschlossen). -> Pfad"""
    ziel = os.path.join(aus, "db_eck_arbeit.db")
    for x in (ziel, ziel + "-wal", ziel + "-shm"):
        if os.path.exists(x): os.remove(x)
    src = sqlite3.connect(f"file:{os.path.abspath(db)}?mode=ro", uri=True); dst = sqlite3.connect(ziel)
    try: src.backup(dst)
    finally: dst.close(); src.close()
    return ziel


def kamerazentren(rE, rZ, ns):
    """Projektionszentren der gemeinsamen Bilder ns in beiden Modellen -> (C_eck, C_teil) fuer die KAMERA-PROBE; None, wenn das Modell keine Posen liefert."""
    try:
        E = {im.name: im for im in rE.images.values()}; Z = {im.name: im for im in rZ.images.values()}
        return np.array([E[n].projection_center() for n in ns]), np.array([Z[n].projection_center() for n in ns])
    except Exception: return None


def koppeln(m, teile, R, P, ausd_teil):
    """Zwischenmodell m an alle Teile koppeln. -> (info, {teil: (M_teil_von_E, pruefung)} nur stimmige, alle pruefungen)."""
    import pycolmap
    rE = pycolmap.Reconstruction(m); ausd = ausdehnung([p.xyz for p in rE.points3D.values()]); gut, alle = {}, {}
    for t in teile:
        X, Y, ns, td = punkte(rE, R[t], mit_tiefe=True)
        if len(ns) < MIN_BILDER_TEIL: alle[t] = dict(bilder=len(ns), grund=f"nur {len(ns)} gemeinsame Bilder"); continue
        M, pr, ok, g = kopplung_pruefen(X, Y, ausd, ausd_teil[t], tiefe=td, kameras=kamerazentren(rE, R[t], ns)); pr.update(bilder=len(ns), grund=g); alle[t] = pr
        if ok: gut[t] = (M, pr)
    return dict(modell=m, ausdehnung=round(ausd, 4)), gut, alle


def zwischenmodell(k, i, db, fotos, aus, faeden, R, ausd_teil):
    """Varianten: SIFT (Kettendatenbank), NACHMATCHEN (ALIKED+LightGlue), TEILKAMERAS (Intrinsik der Teile fest; Bilder ohne Teil: aus dem SIFT-Eckmodell). Wahl: variante_waehlen.
    Alle im JSON ('varianten'), Unterschied der Kantenlage zur gewaehlten als Stabilitaetsangabe. -> dict wie _zwischen."""
    vs = {"sift": _zwischen(k, f"{i}", db, fotos, aus, faeden, R, ausd_teil, False)}
    if NACHMATCHEN: vs["nachmatchen"] = _zwischen(k, f"{i}lg", db, fotos, aus, faeden, R, ausd_teil, True)
    if TEILKAMERAS:
        er = None
        try: import pycolmap; er = pycolmap.Reconstruction(vs["sift"]["modell"]) if vs["sift"].get("modell") else None
        except Exception: er = None
        alt, info = teilkameras_setzen(db, k["bilder"], R, ersatz=er)
        if alt:
            try: vs["teilkameras"] = dict(_zwischen(k, f"{i}tk", db, fotos, aus, faeden, R, ausd_teil, False, kameras_fest=True), teilkameras=info)
            finally: teilkameras_zurueck(db, alt)
        else: vs["teilkameras"] = dict(grund="keine Teilkameras gesetzt", teilkameras=info)
    if len(vs) == 1: return vs["sift"]
    wahl = variante_waehlen({v: z.get("_gut", {}) for v, z in vs.items()}); z = dict(vs[wahl])
    kurz = lambda zz: {x: zz.get(x) for x in ("bilder", "schwelle", "modell", "kopplungen", "nachmatchen", "zeitnachbarn", "teilkameras", "bruecke_duenn", "grund") if x in zz}
    gw = vs[wahl].get("_gut", {})
    z["varianten"] = dict(gewaehlt=wahl, **{v: kurz(zz) for v, zz in vs.items()},
                          unterschied={v: vergleich(gw, zz.get("_gut", {}), ausd_teil) or "nicht beide gekoppelt" for v, zz in vs.items() if v != wahl})
    return z


VORRANG = ("teilkameras", "nachmatchen", "sift")   # bei gleich vielen stimmig gekoppelten Teilen: gleiche Kamerageometrie wie die Teile zuerst (Kopf TEILKAMERAS)


def variante_waehlen(gut_je):
    """gut_je: {variante: {teil: (M, pruefung)}} -> Name. Eine Variante ausser 'sift' zaehlt nur mit >= 2 stimmig gekoppelten Teilen (sonst keine Kante); gewaehlt wird die
    mit den meisten, bei Gleichstand nach VORRANG. Ohne Teilkameras wie bisher: Nachmatchen, wenn >= 2 und >= SIFT."""
    wert = lambda v: len(gut_je[v]) if (v == "sift" or len(gut_je[v]) >= 2) else -1
    return max((v for v in gut_je), key=lambda v: (wert(v), -VORRANG.index(v) if v in VORRANG else -99))


def _zwischen(k, i, db, fotos, aus, faeden, R, ausd_teil, nachmatchen, kameras_fest=False):
    """Schwelle nach schwelle_waehlen (strengste verbindende, bei duenner Bruecke die mit den meisten Teil-Bildern) + Sensitivitaet + Wiederholbarkeit. -> dict"""
    import pycolmap
    erg = dict(teile=k["teile"], brueckenpaare=len(k["paare"]), bilder=len(k["bilder"]), versuche=[]); treffer = []
    if nachmatchen:                                                                   # mehr und breiter verteilte Zuordnungen im Brueckenbereich (Kette: SIFT)
        zeit = zeitnachbarn(k, fotos); k = dict(k, bilder=sorted(set(k["bilder"]) | zeit)); erg.update(bilder=len(k["bilder"]), zeitnachbarn=len(zeit))
        lo = os.path.join(aus, f"zwischen{i}_lg"); os.makedirs(lo, exist_ok=True); lp = os.path.join(lo, "bilder.txt"); open(lp, "w").write("\n".join(k["bilder"]) + "\n")
        rc = subprocess.call([os.path.join(T, "py"), os.path.join(T, "bruecke_nachmatchen.py"), db, fotos, lp, "--aus", lo, "--vram-mb", str(NACHMATCH_VRAM_MB), "--faeden", str(faeden)],
                             stdout=open(os.path.join(lo, "log.txt"), "w"), stderr=subprocess.STDOUT)
        if rc == 0 and os.path.isfile(os.path.join(lo, "db.db")): db = os.path.join(lo, "db.db"); erg["nachmatchen"] = dict(rc=0, db=db)
        else: erg["nachmatchen"] = dict(rc=rc, grund="Nachmatchen gescheitert/gesperrt - SIFT-Datenbank", log=os.path.join(lo, "log.txt"))
    voll = sum(len(set(k["bilder"]) & NAMEN[t]) for t in k["teile"]); w_ = s_ = None
    for s in SCHWELLEN:
        rc, mods = mapper(k["bilder"], db, fotos, os.path.join(aus, f"zwischen{i}_s{s}"), faeden, s, kameras_fest=kameras_fest); best = None
        for m in mods:
            E = {im.name for im in pycolmap.Reconstruction(m).images.values() if im.has_pose}; je = {t: len(E & NAMEN[t]) for t in k["teile"]}
            n2 = sum(v >= MIN_BILDER_TEIL for v in je.values())
            if n2 >= 2 and (best is None or (n2, sum(je.values())) > best[0]): best = ((n2, sum(je.values())), m, je)
        erg["versuche"].append(dict(schwelle=s, modelle=len(mods), bilder_je_teil=best[2] if best else None))
        if best: treffer.append((s, best[1], sum(best[2].values())))
        w_, s_, fertig = schwelle_waehlen(treffer, voll)
        if fertig: break
    if not treffer: erg["grund"] = f"kein Zwischenmodell mit >= {MIN_BILDER_TEIL} Bildern aus >= 2 Teilen (Schwellen {list(SCHWELLEN)})"; return erg
    if w_ > 0 or treffer[w_][2] < voll:                                                # DUENNE BRUECKE: strengste verbindende Schwelle liess Teil-Bilder der Liste aus
        erg["bruecke_duenn"] = dict(listenbilder_teile=voll, registriert={t[0]: t[2] for t in treffer}, gewaehlt=treffer[w_][0],
                                    grund=f"bei Schwelle {treffer[0][0]} nur {treffer[0][2]}/{voll} Teil-Bilder im Eckmodell" + (f" -> Schwelle {treffer[w_][0]}: {treffer[w_][2]}" if w_ else ""))
    s0, m0 = treffer[w_][:2]; info, gut, alle = koppeln(m0, k["teile"], R, None, ausd_teil); erg.update(schwelle=s0, kopplungen={str(t): v for t, v in alle.items()}, **info); erg["_gut"] = gut
    if s_ is not None:
        _, gut1, _ = koppeln(treffer[s_][1], k["teile"], R, None, ausd_teil)
        erg["sensitivitaet"] = dict(schwelle=treffer[s_][0], vergleich=vergleich(gut, gut1, ausd_teil) or "zu wenige stimmige Kopplungen bei der lockereren Schwelle")
    else: erg["sensitivitaet"] = dict(schwelle=None, vergleich="keine lockerere Schwelle verbindet")
    # WIEDERHOLBARKEIT (Stabilitaetsmass): WIEDERHOLUNGEN Laeufe mit je WEGLASSEN der Nicht-Brueckenbilder zufaellig weggelassen (feste Keime) -> Streuung der Kantenlage
    kern = {d["a"] for d in k["paare"]} | {d["b"] for d in k["paare"]}; rest = [b for b in k["bilder"] if b not in kern]; wd = []
    for w in range(WIEDERHOLUNGEN if len(gut) >= 2 else 0):
        rng = np.random.default_rng(w); weg = set(rng.choice(rest, int(len(rest) * WEGLASSEN), replace=False)) if rest else set()
        _, mods = mapper([b for b in k["bilder"] if b not in weg], db, fotos, os.path.join(aus, f"zwischen{i}_wdh{w}"), faeden, s0, kameras_fest=kameras_fest); gw = {}
        for m in mods:
            _, g_, _ = koppeln(m, k["teile"], R, None, ausd_teil)
            if len(g_) > len(gw): gw = g_
        wd.append(vergleich(gut, gw, ausd_teil) or [dict(kante=None, grund="Wiederholung koppelt nicht")])
    if wd:
        flach = [x for v in wd for x in v]
        erg["wiederholbarkeit"] = dict(laeufe=len(wd), weggelassen=WEGLASSEN, je_lauf=wd, gekoppelt=sum(all(x.get("kante") for x in v) for v in wd),
                                       max=dict(drehung_grad=max((x.get("drehung_grad", 0) for x in flach if x.get("kante")), default=None),
                                                massstab_rel=max((x.get("massstab_rel", 0) for x in flach if x.get("kante")), default=None),
                                                versatz_rel=max((x.get("versatz_rel", 0) for x in flach if x.get("kante")), default=None)))
    return erg


def vergleich(g0, g1, ausd_teil):
    """Kantenlagen zweier Kopplungssaetze desselben Zwischenstuecks vergleichen -> [dict(kante, drehung_grad, massstab_rel, versatz_rel)] (Versatz relativ zur Ausdehnung von Teil i)."""
    ts = sorted(set(g0) & set(g1)); out = []
    for x in ts[1:]:
        D = (g0[ts[0]][0] @ np.linalg.inv(g0[x][0])) @ np.linalg.inv(g1[ts[0]][0] @ np.linalg.inv(g1[x][0])); s, Rr, t = zerlegen(D)
        out.append(dict(kante=[ts[0], x], drehung_grad=round(winkel(Rr), 3), massstab_rel=round(abs(s - 1), 4), versatz_rel=round(float(np.linalg.norm(t)) / max(ausd_teil[ts[0]], 1e-12), 4)))
    return out


def exif_zeit(pfad):
    try:
        from PIL import Image; import datetime
        v = Image.open(pfad).getexif().get_ifd(0x8769).get(36867) or Image.open(pfad).getexif().get(306)
        return datetime.datetime.strptime(v, "%Y:%m:%d %H:%M:%S").timestamp() if v else None
    except Exception: return None


def zeitnachbarn(k, fotos):
    """Bilder mit EXIF-Aufnahmezeit bis ZEIT_FENSTER_S um ein Brueckenbild (ein Rundgang ist eine Kette) - auch ohne Paar in der Kettenliste; nur Bilder mit EXIF-Zeit."""
    kern = {d["a"] for d in k["paare"]} | {d["b"] for d in k["paare"]}; tz = {}
    for n in os.listdir(fotos):
        if n.lower().endswith((".jpg", ".jpeg", ".png")):
            z = exif_zeit(os.path.join(fotos, n))
            if z is not None: tz[n] = z
    kz = [tz[n] for n in kern if n in tz]
    return {n for n, z in tz.items() if any(abs(z - x) <= ZEIT_FENSTER_S for x in kz)} - set(k["bilder"])


def spannbaum(teile, kanten, a):
    """Prim ab a ueber die groesste Guete. kanten: [dict(i, j, M_i_von_j, guete, sigma)]. -> (lage {teil: M_a_von_teil}, weg {teil: [kantenindex]}, Baumkanten-Indizes)."""
    lage = {a: np.eye(4)}; weg = {a: []}; baum = set()
    while True:
        best = None
        for n, k in enumerate(kanten):
            for x, y, M in ((k["i"], k["j"], k["M"]), (k["j"], k["i"], np.linalg.inv(k["M"]))):   # M: j -> i
                if x in lage and y not in lage and (best is None or k["guete"] > best[0]): best = (k["guete"], n, x, y, M)
        if best is None: return lage, weg, baum
        _, n, x, y, M = best; lage[y] = lage[x] @ M; weg[y] = weg[x] + [n]; baum.add(n)


def kreise_pruefen(kanten, lage, weg, baum, ausd_teil):
    """Jede Nicht-Baumkante zwischen zwei erreichten Teilen = Kreis. -> [dict(kante, teile, drehung_grad, massstab_rel, versatz_rel, grenze, ok)]"""
    aus = []
    for n, k in enumerate(kanten):
        if n in baum or k["i"] not in lage or k["j"] not in lage: continue
        D = np.linalg.inv(lage[k["i"]] @ k["M"]) @ lage[k["j"]]; s, R, t = zerlegen(D)          # j -> j um den Kreis
        im_kreis = sorted(set(weg[k["i"]]) ^ set(weg[k["j"]]) | {n}); sig = float(np.sqrt(sum(kanten[m]["sigma"] ** 2 for m in im_kreis))); g = KREIS_SIGMA * sig
        f = dict(drehung_grad=round(winkel(R), 3), massstab_rel=round(abs(s - 1), 4), versatz_rel=round(float(np.linalg.norm(t)) / max(ausd_teil[k["j"]], 1e-12), 4))
        ok = np.radians(f["drehung_grad"]) <= g and f["massstab_rel"] <= g and f["versatz_rel"] <= g
        teile = sorted({kanten[m]["i"] for m in im_kreis} | {kanten[m]["j"] for m in im_kreis})
        aus.append(dict(kante=n, kanten=im_kreis, teile=teile, grenze=round(g, 4), ok=bool(ok), **f))
    return aus


LEITER = os.environ.get("RCPARK_ECK_LEITER", "1") != "0"   # 22.11.2026 Eskalationsleiter je Kante (tools/bruecke_hebel.py); 0 = Stand vor der Leiter
_LOT = {}


def leiter_kante(z, i, j, Mi, Mj, pi, pj, R, a):
    """Kante i-j des Zwischenmodells z durch die Leiter (bruecke_hebel.leiter): -> dict(M (j -> i), leiter{stufe, urteil, stufen, lot_pruefung, fotoauftrag})."""
    import pycolmap, bruecke_hebel as BH
    for t in (i, j):
        if t not in _LOT:
            try: _LOT[t] = BH.lot_modell(R[t], a.fotos, cache=os.path.join(a.aus, f"lot_teil{t}.json"))
            except Exception as ex: _LOT[t] = dict(oben=None, hinweis=str(ex)[:200])
    lot = (_LOT[i]["oben"], _LOT[j]["oben"]) if _LOT[i].get("oben") and _LOT[j].get("oben") and all(_LOT[t].get("quelle") == "fluchtpunkte" for t in (i, j)) else None
    wd = ((z.get("wiederholbarkeit") or {}).get("max") or {}).get("drehung_grad")
    rd = json.load(open(a.radar)) if getattr(a, "radar", None) and os.path.isfile(a.radar) else None
    lt = BH.leiter(BH.Modell(pycolmap.Reconstruction(z["modell"])), BH.Modell(R[i]), BH.Modell(R[j]), Mi, Mj, pi, pj, a.fotos, os.path.join(a.aus, f"leiter_{i}_{j}"), lot=lot, wdh_grad=wd,
                   radar=rd, teile=(i, j))
    M = lt.pop("M"); return dict(M=M, leiter=json.loads(json.dumps(lt, default=lambda o: o.tolist() if hasattr(o, "tolist") else str(o))))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0]); [ap.add_argument(k) for k in ("db", "seiten", "fotos")]; ap.add_argument("--aus", required=True)
    ap.add_argument("--teil", action="append", required=True, help="N=<modell>, erster = Teil A"); ap.add_argument("--faeden", type=int, default=max(1, (os.cpu_count() or 2) // 2))
    ap.add_argument("--radar", default=os.environ.get("RCPARK_ECK_RADAR"), help="Schwachstellen-Radar (tools/verbund_schwachstellen.py, verbund_schwachstellen/1) fuer das Urteil der Leiter")
    a = ap.parse_args(argv); os.makedirs(a.aus, exist_ok=True)
    tl = [(int(x.split("=", 1)[0]), x.split("=", 1)[1]) for x in a.teil]; A = tl[0][0]
    def ende(rc, urteil, **kw):
        d = dict(rc=rc, ok=rc == 0, urteil=urteil, teil_a=A, **kw); json.dump(d, open(os.path.join(a.aus, "eck.json"), "w"), indent=1, ensure_ascii=False)
        print(("ECK-KOPPLUNG: " if rc == 0 else "ECK-KOPPLUNG NICHT: ") + urteil); return rc
    if len(tl) < 2: return ende(2, "nur ein Teil - nichts zu koppeln (zusammenhaengendes Modell bleibt unveraendert)")
    import pycolmap
    R, teil_von, ausd_teil = {}, {}, {}
    for t, p in tl:
        r = pycolmap.Reconstruction(p); ns = {im.name for im in r.images.values() if im.has_pose}; R[t] = r; NAMEN[t] = ns
        for n in ns: teil_von.setdefault(n, t)
        ausd_teil[t] = ausdehnung([q.xyz for q in r.points3D.values()])
    ks = kandidaten(json.load(open(a.seiten)), teil_von, a.db)
    luecke = lambda erreicht, extra={}: [dict(teil=t, verbindung=extra.get(t) or f"Fotos, die Teil {t} und einen gekoppelten Teil gemeinsam zeigen (Uebergang um die Ecke, Schritte <= 30 Grad)")
                                         for t, _ in tl if t not in erreicht]
    if not ks: return ende(2, "keine bestaetigten Brueckenpaare zwischen den Teilen (seiten.json 'durchblick')", fotoluecken=luecke({A}))
    zw, kanten = [], []
    fa0 = db_fingerabdruck(a.db); dba = arbeits_db(a.db, a.aus)                       # Mapper nur auf der Kopie (Kopf: GLEICHE EINGABE = GLEICHES ERGEBNIS)
    try: zk = [zwischenmodell(k, i, dba, a.fotos, a.aus, a.faeden, R, ausd_teil) for i, k in enumerate(ks)]
    finally:
        for x in (dba, dba + "-wal", dba + "-shm"):
            if os.path.exists(x): os.remove(x)
    fa1 = db_fingerabdruck(a.db); edb = dict(pfad=os.path.abspath(a.db), unveraendert=fa0 == fa1, vorher=fa0, nachher=fa1, mapper_keim=MAPPER_KEIM, mapper_faeden=MAPPER_FAEDEN)
    if fa0 != fa1: print(f"WARNUNG ECK-KOPPLUNG: Eingabe-DB {a.db} hat sich waehrend der Stufe geaendert ({fa0} -> {fa1}) - Teilmodelle werden im naechsten Lauf neu gerechnet", flush=True)
    for i, (k, z) in enumerate(zip(ks, zk)):
        gut = z.pop("_gut", {}); zw.append(z); ts = sorted(gut)
        for x in range(len(ts)):
            for y in range(x + 1, len(ts)):
                (Mi, pi), (Mj, pj) = gut[ts[x]], gut[ts[y]]
                sig = float(np.sqrt(sum(p_["rest_rel"] ** 2 + p_["massstab_haelften_rel"] ** 2 for p_ in (pi, pj))))
                kd = dict(i=ts[x], j=ts[y], M=Mi @ np.linalg.inv(Mj), zwischenmodell=i, sigma=sig, guete=float(min(pi["stimmig"] * pi.get("hebel", 1), pj["stimmig"] * pj.get("hebel", 1))))
                if LEITER and z.get("modell"):                                          # Eskalationsleiter (tools/bruecke_hebel.leiter): Ausgleich, Urteil, gefuehrtes Nachmessen
                    try: kd.update(leiter_kante(z, ts[x], ts[y], Mi, Mj, pi, pj, R, a))
                    except Exception as ex: kd["leiter"] = dict(fehler=str(ex)[:300])
                kanten.append(kd)
    lage, weg, baum = spannbaum([t for t, _ in tl], kanten, A); kr = kreise_pruefen(kanten, lage, weg, baum, ausd_teil)
    raus = set()
    for c in kr:
        if not c["ok"]: raus |= {t for t in lage if t != A and set(weg[t]) & set(c["kanten"])}
    teile = {}
    for t, _ in tl:
        if t == A: continue
        if t in lage and t not in raus:
            teile[str(t)] = dict(ok=True, M_nach_A=lage[t].tolist(), weg=[[kanten[n]["i"], kanten[n]["j"]] for n in weg[t]], massstab_unsicher=round(float(np.sqrt(sum(kanten[n]["sigma"] ** 2 for n in weg[t]))), 4))
        else: teile[str(t)] = dict(ok=False, grund="Kreisschluss-Widerspruch" if t in raus else "keine stimmige Kopplung")
    kj = [dict(i=k["i"], j=k["j"], zwischenmodell=k["zwischenmodell"], guete=round(k["guete"], 1), sigma=round(k["sigma"], 5), im_baum=n in baum, leiter=k.get("leiter")) for n, k in enumerate(kanten)]
    erreicht = {A} | {int(t) for t, v in teile.items() if v["ok"]}
    fl = luecke(erreicht, {t: f"Bruecke zu Teil(en) {[x for x in z['teile'] if x != t]} vorhanden, Kopplung nicht stimmig ({z.get('grund') or '; '.join(f'Teil {tk}: ' + str(v.get('grund')) for tk, v in (z.get('kopplungen') or {}).items() if v.get('grund') != 'stimmig')}) - mehr Fotos dieses Uebergangs"
                           for z in zw for t in z["teile"]})
    rc = 0 if len(erreicht) > 1 else (3 if kanten or any(z.get("kopplungen") for z in zw) else 2)
    txt = (f"Teile {sorted(erreicht - {A})} an Teil {A} gekoppelt ({len(kanten)} Kanten, {len(kr)} Kreise{', Widerspruch' if raus else ''})" if rc == 0 else
           "keine stimmige Kopplung" if rc == 3 else "kein Zwischenmodell aus >= 2 Teilen - die Bruecke traegt nicht")
    return ende(rc, txt, teile=teile, kanten=kj, kreise=kr, zwischenmodelle=zw, fotoluecken=fl, eingabe_db=edb)


if __name__ == "__main__": sys.exit(main())
