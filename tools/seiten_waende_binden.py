#!/usr/bin/env python3
"""seiten_waende_binden.py <dicht_a.ply> <dicht_b.ply> --gps <vereinen.json> --aus <ordner> [--modell-a <sparse> --modell-b <sparse> --bilder <fotos>]

GEGENSEITEN UEBER GEMEINSAME WAENDE BINDEN (24.11.2026, Kettenlauf schwabentor-1122w, Teil 1 = Suedseite, 63 Bilder).
BEFUND: Klappung gescheitert, Querspur abgelehnt, LoD2 je Teil "Bestwert am Kastenrand" -> Teil 1 nur ueber das Foto-GPS (+-1,4 Grad Bootstrap) und darum WEGGELASSEN.
GEMESSEN (dichte Wolken der Teile, B per GPS-Lage auf A):
  - Die Klappung ist fuer diesen Fall der falsche Ansatz: Teil 1 ist keine Gegenseiten-VERWECHSLUNG (Martinstor), sondern eine andere Seite, die Teil 0 nie im selben Bild
    hat. Die 19 Klapp-Inlier (von 105 Punktpaaren) legen B schon OHNE Klappen auf die richtige Seite (Kameras 173 Grad auseinander, Nachbarbau auf DERSELBEN Flanke wie in A
    - erst die Klappung bringt ihn auf die falsche). Die Turmhoehen-Probe scheitert, weil die dichte Wolke von A oben duenn ist (A 33 m p99,9, B 41 m).
  - Die GPS-Lage von B ist um 9,9 Grad GEKIPPT (Lot der B-Waende gegen das Lot der A-Waende; 3431 bzw. 20505 Wandnormalen): das Foto-GPS legt nur den Grundriss fest,
    das Lot von B kommt aus den Bild-x-Achsen von 63 Fotos. Dazu 5,7 Grad Wandrichtung (A 83,7 / B 78,0 Grad mod 90) - beides ist mit "+-1,4 Grad" nicht beschrieben.
  - Teil 0 sieht den Turm oberhalb der Nachbardaecher RUNDUM (Kasten aus vier Wandlinien z 14-40 m, Drohnen-/Fernbilder). Teil 1 sieht Suedwand + Ostflanke
    desselben Turms -> GEMEINSAME WAENDE (die Wand, die B frontal sieht, hat A schraeg von oben). Das ist eine Bindung ohne gemeinsame Bildmerkmale.
VERFAHREN (nur CPU, Sekunden):
  1. LOT VON B aus seinen EIGENEN Waenden (seiten_vereinen.lot_aus_waenden, dichte Wolke) gegen das Wand-Lot von A -> Kippung um die Mitte der B-Wolke. Unabhaengig vom GPS.
  2. WANDPUNKTE beider Teile: ebene, senkrechte Flaechenstuecke (Normale waagerecht) ueber Strassenhoehe (Z_MIN_M), im Grundriss um die B-Waende.
  3. GRUNDRISS-SUCHE im GPS-Korridor (seiten_querspur_binden.korridor, gleiche Grenzen wie die Querspur): Drehung um das Lot x Verschiebung, Wertung = mittlere Naehe der
     B-Wandpunkte zu den A-Waenden (Abstandsfeld, Kreuzkorrelation per FFT). Dann Feinausgleich Punkt-zu-Linie (Drehung + Verschiebung, Massstab bleibt GPS).
  4. HOEHE (24.11., 1122z: Teil 1 am GPS-Fusspunkt 6,4 m zu tief): aus der 3D-UEBERLAPPUNG - je gemeinsam belegter Grundriss-Saeule das hochpassgefilterte
     Hoehenprofil (Fenster, Gesimse, Traufe, Helm) von A und B kreuzkorreliert (z_saeulen); STRASSENBODEN von A gegen B in gemeinsamen Zellen als unabhaengige
     Gegenprobe (boden_versatz; uneinig > HOEHE_EINIG_M -> abgelehnt); Struktur nicht eindeutig -> Boden; beides fehlt -> GPS-Fusspunkt + Meldung (kein Raten).
     Danach Tor UNTER GELAENDE (unter_gelaende): > UNTER_ANTEIL der B-Punkte in Strassenzellen > UNTER_M unter dem Boden von A -> abgelehnt. Seitenbild <aus>/waende_seite.jpg.
     Das alte globale Profil der ebenen Wandpunkte (z_versatz) war hoehenblind (senkrechte Ebenen) und verwischt (alle Fassaden in einem Histogramm) -> nur Bericht.
  5. MASSSTAB (24.11., 1122y): Aehnlichkeit Punkt-zu-Linie (Fangfenster DOPPEL_MAX_M) - uebernommen nur, wenn die Treffer-Wandzuege ihn belegen (nicht durch einen
     gemeinsamen Punkt, Hebel >= HEBEL_MIN_M), er >= 3 Streuungen vom GPS abweicht, <= 25 % und mehr Treffer bringt; sonst GPS-Massstab.
TOR (jede Probe einzeln, uebernommen nur wenn ALLE bestehen; sonst bleibt die GPS-Lage):
  - eindeutig: zweitbester Gipfel >= ABSTAND_ZWEIT_M entfernt hoechstens ZWEIT_ANTEIL des besten (eine Wand allein gleitet laengs -> mehrdeutig);
  - nicht am Kastenrand der Suche; Ergebnis im GPS-Korridor (Drehung, Massstab, Lage der B-Kameras; die KIPPUNG wird hier aus den Waenden gemessen, nicht vom GPS);
  - beide Wandrichtungen tragen (je >= MIN_RICHTUNG_ANTEIL der Treffer), Trefferanteil >= MIN_TREFFER;
  - ZWEI HOEHENBAENDER (unter/ueber dem Median der B-Wandpunkte) einzeln ausgeglichen stimmen ueberein (<= BAND_LAGE_M, <= BAND_DREH_GRAD) - zwei getrennte Bauteile;
  - Wandabstand B->A danach kleiner als in der GPS-Lage;
  - DOPPELWAND: kein B-Wandblatt (>= max(40 Punkte, 3 %)) parallel 0,5-3 m neben einer A-Wand ohne selbst zu treffen (1122y starr: 200 Punkte 2,6 m neben der
    Nachbarwand, 22 m vom Anker -> 9-m-Blatt im Grundriss-Tor, Kette abgebrochen; Massstab 0,881 x GPS (Hebel 9,4 m) deckte beide, Treffer 60 -> 74 %);
  - TURMSPITZE (in der Bindung nicht benutzt): sehen beide Wolken eine schlanke Spitze in gleicher Hoehe, liegt sie waagerecht uebereinander (sonst 'nicht messbar', Bericht);
  - GEOTAGS VON B (main, --bilder): B-Kameras nach der Bindung ueber den A-Rahmen in ENU - Median hoechstens GPS_MEHR_M schlechter als die GPS-Lage, >= 70 % unter 12 m.
  - LOT-TORE (main, kamera_lot_probe; 24.11. 1122zb): (a) Fluchtpunkt-Lot der B-Fotos nach der Bindung <= LOT_VP_GRAD neben dem Lot von A; (b) Kamerahoehe gegen DGM1
    (kamerahoehe_pruefen) NUR mit der Kippung (GPS-Massstab) - treibt sie die Steigung aus dem Band, ist das Wand-Lot nicht belegt. Endlage ausserhalb, Kippung innerhalb
    = Wand-Massstab passt zum Turm, nicht zum Kameraring -> Bindung bleibt, Fernkameras mit Rest > 4 m 'Lage unbrauchbar' (pruefung.lot_tore). 1122zb gemessen: Wand-Lot
    von B = Fluchtpunkt-Lot (1,9 Grad, 12 Bilder) = Bild-x-Lot der 15 Hangkameras (3,5 Grad); FALSCH war das GPS-Lot von B (Bild-x-Achsen, 48 Strassenkameras mit engem
    Blickfaecher: Singulaerwerte 0,32/0,07 -> 10 Grad daneben). DGM-Steigung GPS-Lage 1,27 -> Kippung 0,99 -> Endlage 0,87 (Wand-Massstab 0,882; Kamera-GPS sagt ~1,0).
  Der Korridor nutzt die EHRLICHE GPS-Unsicherheit (Bootstrap + Sitzungsfehler); die Lage der B-Kameras zaehlt nur waagerecht; die Kippung um die Mitte der B-Kameras
  (dort traegt das GPS die Hoehe).
1122w (24.11., Zwischendaten nur gelesen, CPU ~2 min): Kippung 10,0 Grad (um den Fusspunkt), Drehung +4,6 Grad, Verschiebung 3,6 m; Wandabstand Median 2,40 -> 0,07 m, Treffer 60 %,
  Geotags von B 5,1 -> 7,8 m (79 % < 12 m), Turmspitze nicht messbar (A-Wolke oben duenn), Hoehe am Fusspunkt nach GPS (Profil nicht eindeutig, nur Bericht). Seitenansicht: Turm, Helm und Uhr
  von A und B decken sich (vorher Helm um Meter versetzt und geneigt).
1122z (24.11., nur gelesen): Struktur +6,55 m (392 Saeulen, zweiter Gipfel 18 %), Boden +6,40 m (35 Zellen, Streuung 0,34 m); unter Gelaende 19,3 % -> 0,1 % (A 0,06 %).
Ausgabe <aus>/waende.json (ok, urteil, B_nach_A nur bei ok, B_nach_A_gps, pruefung{..., hoehe_3d}, korridor), Kontrollbild <aus>/waende.jpg (Grundriss vorher/nachher) + waende_seite.jpg.
rc 0 = gebunden, 2 = zu wenig Eingabe/Wandpunkte (nichts getan), 3 = abgelehnt. GRENZEN: Massstab nur mit Wand-Beleg (sonst GPS; 1122y: Waende 0,881 belegt, dann
lehnt die Geotag-Probe ab: Median 5,1 -> 8,4 m bei Grenze +3 m - der Massstab verschiebt die 24 m entfernten B-Kameras ~3 m); braucht einen Teil A,
der die von B gesehenen Waende mitsieht (Drohne/Fernbild/Uebereck); bei einem Kastenturm mit vier gleichen Seiten verhindert der GPS-Korridor die 90-Grad-Verwechslung.
Test: tests/test_seiten_waende_binden.py. Python: /media/oem/scan/venv-colmap/bin/python -I (pycolmap nur fuer die B-Kameras; ohne Modell: B-Wolke als Bezug)."""
import os, sys, json, argparse
import numpy as np

T = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, T)
from seiten_querspur_binden import gps_unsicherheit, korridor, zerlege, anwenden, KIPP_MAX_GRAD   # gleicher GPS-Korridor wie die Querspur-Bindung
from seiten_vereinen import lot_aus_waenden, stange

Z_MIN_M = 3.0             # ANNAHME: Wandpunkte erst ueber Strassenhoehe (Autos, Schilder, Passanten)
ZELLE_M = 0.10            # Raster des Abstandsfelds
SIGMA_M = 0.15            # Naehe-Wertung exp(-d^2 / 2 sigma^2); Wanddicke-Rauschen der dichten Wolken ~0,05-0,1 m
DREH_SCHRITT = 0.25       # Grad, Grobsuche
TREFFER_M = 0.25          # B-Wandpunkt "auf einer A-Wand"
MIN_WANDPUNKTE = 150      # ANNAHME: je Teil im Suchgebiet
MIN_TREFFER = 0.40        # ANNAHME: Anteil der B-Wandpunkte auf A-Waenden nach der Bindung
MIN_RICHTUNG_ANTEIL = 0.10  # ANNAHME: jede der zwei Wandrichtungen traegt >= 10 % der Treffer (sonst gleitet B laengs der einen Wand)
ZWEIT_ANTEIL = 0.85       # ANNAHME: zweitbester Gipfel (>= ABSTAND_ZWEIT_M entfernt) hoechstens 85 % des besten
ABSTAND_ZWEIT_M = 1.0
BAND_LAGE_M = 0.30        # ANNAHME: zwei Hoehenbaender einig auf 0,3 m ...
BAND_DREH_GRAD = 1.0      # ... und 1 Grad
KIPP_GRENZE_GRAD = 15.0   # lot_aus_waenden sucht Normalen nur bis ~14 Grad um das Start-Lot
RAND_M = 0.2              # Gipfel naeher als 0,2 m am Suchrand = Kastenrand
Z_PROFIL_M = 0.2          # Hoehenprofil-Raster
MIN_KIPP_NORMALEN = 300
SPITZE_M = 0.6            # ANNAHME: Helmstangen beider Teile waagerecht <= 0,6 m (Martinstor: oberstes Band traf die Handmessung auf 0,1 m)
SPITZE_HOEHE_ANTEIL = 0.10  # Spitze nur vergleichbar, wenn beide Wolken sie bis auf 10 % der Hoehe erreichen
SPITZE_SCHLANK_M = 1.0    # ANNAHME: ... und das oberste Band schlank ist (Streuung <= 1 m; 1122w: B 0,3 m, A 3,9 m = Spitze in A nicht getroffen)
GPS_MEHR_M = 3.0          # ANNAHME: Geotags von B duerfen nach der Bindung im Median hoechstens 3 m weiter weg liegen (~1 Sigma Sitzungsfehler 3,4 m, gps_unsicherheit)
GPS_ANTEIL_MIN = 0.70     # ANNAHME: und >= 70 % unter seiten_gps_vereinen.GRENZE_M (12 m)
DREH_SUCHE_MAX = 20.0     # ANNAHME: Suche um das Lot hoechstens +-20 Grad (weit weg von 45/90 Grad - Kastenturm-Verwechslung)
LAGE_SUCHE_MAX_M = 8.0    # ANNAHME: Verschiebung hoechstens +-8 m (Rechenaufwand; ein Turm von 8-12 m Seite wuerde sonst auf die Nachbarwand rutschen)
# MASSSTAB AUS DEN WAENDEN + DOPPELWAND-GEGENPROBE (24.11.2026, Kettenlauf 1122y: starr gebunden sass Teil 1 auf der Turm-Ostwand, die Nachbarwand 22 m weiter lag
# 2,6 m parallel daneben = 9-m-Wandblatt im Grundriss-Tor; Massstab 0,88 deckte beide, GPS-Massstab hat ehrlich +-16 %)
PARALLEL_GRAD = 15.0      # ANNAHME: Wandstuecke gelten als parallel unter 15 Grad (Normalen der dichten Wolke streuen ~5 Grad)
MIN_ZUG_PUNKTE = 30       # ANNAHME: ein Wandzug traegt ab 30 Treffern (Grundriss-Wandpunkte, ~0,5 % der B-Wandpunkte 1122)
HEBEL_MIN_M = 5.0         # Massstab nur mitschaetzen ab 5 m Hebel: Streuung ~ SIGMA_M / Hebel <= 3 % - deutlich besser als das GPS (ehrlich 16 %, 1122)
MASS_SIGNIFIKANZ = 3.0    # Massstab nur uebernehmen, wenn er um >= 3 Streuungen (SIGMA_M / Hebel) von dem des GPS abweicht - sonst bleibt der GPS-Massstab
MASS_MAX_REL = 0.25       # ANNAHME: Massstab aus den Waenden hoechstens +-25 % gegen GPS (~1,5 x ehrliche GPS-Streuung 1122; dahinter faengt das 3-m-Fenster falsche Waende)
DOPPEL_MIN_M = 0.5        # Doppelwand: B-Blatt 0,5 ...
DOPPEL_MAX_M = 3.0        # ... bis 3 m neben einer parallelen A-Wand (unter 0,5 m = Rauschen/Wanddicke; ueber 3 m = andere Wand). Zugleich Fangfenster der Massstab-Suche.
DOPPEL_LAENGS_M = 1.0     # A-Punkt hoechstens 1 m laengs versetzt (die A-Wand laeuft am B-Blatt entlang)
DOPPEL_MIN_PUNKTE = 40    # ANNAHME: ein Blatt zaehlt ab 40 Punkten ...
DOPPEL_ANTEIL = 0.03      # ... und 3 % der B-Wandpunkte (1122y: 199 Punkte = 11 %; Einzelpunkte an Erkern/Simsen bleiben darunter)
# HOEHE AUS DER 3D-UEBERLAPPUNG + BODEN-GEGENPROBE (24.11.2026, Nutzer 12:50 "Ostteil nach unten in den Boden verrutscht", 12:55 "muss automatisch reinmatchen";
# Kette 1122z: Teil 1 nach Bindung ~6 m zu tief, Spitze 39 statt 45 m). Ersetzt "Hoehe am GPS-Fusspunkt" (s. hoehe_belegen).
Z_SAEULE_M = 0.5          # Grundriss-Saeule (gemeinsam von A und B belegt) fuer das Hoehenprofil
Z_BIN_M = 0.2             # Hoehenraster der Saeulenprofile
Z_HOCHPASS_M = 3.0        # Profil minus gleitendes Mittel ueber 3 m: Fenster/Gesimse/Traufe bleiben, durchgehende Wand (hoehenblind) faellt weg
Z_SUCHE_M = 15.0          # ANNAHME: Fusspunkt-Hoehe kann um Stockwerke falsch sein (1122z: 6 m); weiter = Rechenaufwand + Fehlgipfel
Z_MIN_SAEULEN = 40        # ANNAHME: mindestens 40 gemeinsam belegte Saeulen (1122z: 399)
Z_MIN_BELEGT = 10         # Saeule zaehlt ab 10 belegten Hoehenbins (2 m) je Teil
Z_ZWEIT_ANTEIL = 0.6      # ANNAHME: zweitbester Gipfel (>= ABSTAND_ZWEIT_M entfernt) hoechstens 60 % des besten (1122z: 13-29 %; globales Profil alt: nicht eindeutig)
BODEN_ZELLE_M = 1.0       # Bodenzelle: 3-%-Hoehe je 1-m-Zelle (>= BODEN_MIN_PUNKTE Punkte)
BODEN_MIN_PUNKTE = 10        # ANNAHME: Strassen dichter Wolken schraeg gesehen, duenn (1122z Teil 1)
BODEN_BAND_M = 1.5        # ANNAHME: Strassenzelle = Zellboden hoechstens 1,5 m ueber dem 10-%-Wert aller Zellboeden des Teils (Daecher/Mauerkronen fallen weg, Gefaelle bleibt)
BODEN_DICKE_M = 0.3       # Strassenzelle muss unten waagerecht sein: Punkte im Band +-0,3 m um den Zellboden ...
BODEN_FLACH_FAKTOR = 1.5  # ANNAHME: ... mindestens 1,5-mal so viele wie im gleich hohen Band darueber (0,3-0,9 m; senkrechte Wand: Verhaeltnis ~1; Strasse: >> 1).
                          # Test: Wolke ohne Strasse, Wandfuss 3 m hoch, gab sonst 'Boden' +2,1 m statt keinen
BODEN_MIN_ZELLEN = 15    # ANNAHME: Bodenbeleg ab 15 gemeinsamen Strassenzellen ...
BODEN_STREU_MAX_M = 1.0   # ... mit robuster Streuung (IQR / 1,35) hoechstens 1 m
HOEHE_EINIG_M = 1.0       # ANNAHME: Struktur- und Bodenhoehe einig auf 1 m (Bodenzellen: 3-%-Wert, Rauschen/Bordstein ~0,3-0,5 m)
UNTER_M = 1.0             # Punkt "unter Gelaende": mehr als 1 m unter dem Strassenboden von A in derselben Zelle (Bordstein/Rauschen darunter)
UNTER_ANTEIL = 0.05       # ANNAHME: hoechstens 5 % der B-Punkte in gemeinsamen Strassenzellen unter Gelaende (Boden = 3-%-Wert -> A selbst ~1 %; 1122z vorher 20 %+)
# LOT-TORE NACH DER KIPPUNG (24.11.2026, Kette 1122zb Teil 1 = Ost: Kippung 10 Grad aus 3431 B-Wandnormalen - richtig oder falsch? s. kamera_lot_probe):
LOT_VP_GRAD = 4.0         # ANNAHME: Lot aus den Fluchtpunkten der Senkrechten in den B-Fotos (schwerkraft_je_bild.lot_welt) nach der Bindung hoechstens 4 Grad neben dem Lot von A.
                          # Gemessen 1122zb: Teil 0 Fluchtpunkt/Wand 0,3 Grad, Teil 1 Fluchtpunkt/Wand 1,9 Grad (12 Bilder, Streuung 0,8 Grad); der abzufangende Fehler ist 10 Grad.


# ---------- Grundlagen
def drehung(achse, grad):
    a = np.asarray(achse, float); a = a / np.linalg.norm(a); K = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]]); w = np.radians(grad)
    return np.eye(3) + np.sin(w) * K + (1 - np.cos(w)) * K @ K


def basis(lot):
    e1 = np.cross(lot, [1.0, 0, 0] if abs(lot[0]) < 0.9 else [0, 1.0, 0]); e1 /= np.linalg.norm(e1); return np.array([e1, np.cross(lot, e1), lot])


def ply_lesen(p, max_n=1500000):
    """xyz einer COLMAP-fused.ply (27 Byte je Punkt), gleichmaessig ausgeduennt per memmap (die A-Wolke hat 16 Mio. Punkte / 450 MB)."""
    f = open(p, "rb"); n = 0; kopf = 0
    while True:
        l = f.readline(); kopf += len(l); s = l.decode(errors="replace").strip()
        if s.startswith("element vertex"): n = int(s.split()[-1])
        if s == "end_header" or not l: break
    m = np.memmap(p, dtype=np.dtype([("p", "<f4", 3), ("n", "<f4", 3), ("c", "u1", 3)]), mode="r", offset=kopf, shape=(n,))
    return np.asarray(m["p"][::max(1, n // max_n)], np.float64)


def wandpunkte(X, k=16, flach=0.02, senk=0.15, n_max=400000, saat=0):
    """Ebene, senkrechte Flaechenstuecke (lokales System, z = Lot) -> (Punkte, Normalen)."""
    from scipy.spatial import cKDTree
    if len(X) > n_max: X = X[np.random.default_rng(saat).choice(len(X), n_max, replace=False)]
    if len(X) < k + 1: return X[:0], X[:0]
    _, I = cKDTree(X).query(X, k); Nb = X[I] - X[I].mean(1, keepdims=True); w, U = np.linalg.eigh(np.einsum('nki,nkj->nij', Nb, Nb)); n = U[:, :, 0]
    ok = (w[:, 0] / (w[:, 1] + 1e-30) < flach) & (np.abs(n[:, 2]) < senk); return X[ok], n[ok]


def r2(g):
    c, s = np.cos(np.radians(g)), np.sin(np.radians(g)); return np.array([[c, -s], [s, c]])


# ---------- Grundriss-Suche
def feld(PA2, mitte, halb):
    """Naehe-Feld exp(-d^2/2sigma^2) der A-Wandpunkte auf einem Raster um 'mitte' (+-halb m). -> (S, ursprung)."""
    from scipy.ndimage import distance_transform_edt
    n = int(np.ceil(2 * halb / ZELLE_M)) + 1; o = np.asarray(mitte) - halb; ij = np.floor((PA2 - o) / ZELLE_M).astype(int)
    ok = (ij >= 0).all(1) & (ij < n).all(1); belegt = np.ones((n, n), bool); belegt[ij[ok, 1], ij[ok, 0]] = False
    d = distance_transform_edt(belegt) * ZELLE_M; return np.exp(-d ** 2 / (2 * SIGMA_M ** 2)), o


def suche(PA2, PB2, c, grad_max, lage_max):
    """Grobsuche Drehung (um c) x Verschiebung. -> dict(dreh, schieb, wert, zweit, zweit_abstand, rand, karte)."""
    from scipy.signal import fftconvolve
    r_b = float(np.percentile(np.linalg.norm(PB2 - c, axis=1), 99)); halb = r_b + lage_max + 2.0; S, o = feld(PA2, c, halb); n = S.shape[0]
    ks = int(np.ceil(lage_max / ZELLE_M)); best = None; karte = None; schritt = DREH_SCHRITT if grad_max <= 5 else 2 * DREH_SCHRITT   # weite Suche grober, fein() gleicht nach
    for g in np.arange(-grad_max, grad_max + 1e-9, schritt):
        Q = (PB2 - c) @ r2(g).T; ij = np.round(Q / ZELLE_M).astype(int); m = int(np.abs(ij).max()) + 1
        K = np.zeros((2 * m + 1, 2 * m + 1)); np.add.at(K, (ij[:, 1] + m, ij[:, 0] + m), 1.0)
        Kk = fftconvolve(S, K[::-1, ::-1], mode="same") / len(PB2)                  # Kk[y, x] = Summe S an (Punkte + Verschiebung, Mitte = Rasterzelle y, x)
        ci = int(round((c[0] - o[0]) / ZELLE_M)); cj = int(round((c[1] - o[1]) / ZELLE_M))
        A = Kk[cj - ks:cj + ks + 1, ci - ks:ci + ks + 1]
        if karte is None: karte = A.copy()
        else: karte = np.maximum(karte, A)
        j, i = np.unravel_index(np.argmax(A), A.shape)
        if best is None or A[j, i] > best[0]: best = (float(A[j, i]), float(g), np.array([(i - ks) * ZELLE_M, (j - ks) * ZELLE_M]))
    w, g, sv = best; jj, ii = np.mgrid[-ks:ks + 1, -ks:ks + 1] * ZELLE_M; d = np.hypot(ii - sv[0], jj - sv[1])
    innen = np.hypot(ii, jj) <= lage_max; zw = karte[(d >= ABSTAND_ZWEIT_M) & innen]; z = float(zw.max()) if len(zw) else 0.0
    zi = np.unravel_index(np.argmax(np.where((d >= ABSTAND_ZWEIT_M) & innen, karte, -1)), karte.shape)
    rand = bool(np.hypot(*sv) > lage_max - RAND_M or abs(g) > grad_max - schritt / 2)
    return dict(dreh=g, schieb=sv, wert=w, zweit=z, zweit_abstand=float(np.hypot(ii[zi] - sv[0], jj[zi] - sv[1])), rand=rand)


def fein(PA2, NA2, PB2, c, g0, s0, runden=15, grenze=0.5, m=1.0):
    """Punkt-zu-Linie-Ausgleich (Drehung um c, Verschiebung; Massstab m um c FEST): B-Wandpunkte auf die naechste A-Wand. -> (dreh, schieb, treffer-Maske)."""
    g, s, m, tr = fein_aehnlich(PA2, NA2, PB2, c, g0, s0, runden, grenze, m0=m, frei=False); return g, s, tr


def bild2(PB2, c, g, s, m=1.0): return m * (PB2 - c) @ r2(g).T + c + s


def fein_aehnlich(PA2, NA2, PB2, c, g0, s0, runden=15, grenze=0.5, m0=1.0, frei=True):
    """Wie fein(), mit frei=True zusaetzlich der MASSSTAB m um c (Aehnlichkeit im Grundriss). -> (dreh, schieb, m, treffer-Maske)."""
    from scipy.spatial import cKDTree
    baum = cKDTree(PA2); g, s, m = float(g0), np.asarray(s0, float).copy(), float(m0)
    for k in range(runden):
        Q = bild2(PB2, c, g, s, m); d, i = baum.query(Q); gr = max(TREFFER_M, grenze * (1 - k / runden))
        ok = d < gr
        if ok.sum() < 10: break
        n = NA2[i[ok]]; q = Q[ok]; p = PA2[i[ok]]; rq = q - c - s; J = np.c_[(n[:, 1] * rq[:, 0] - n[:, 0] * rq[:, 1]), n]   # d(n.(q-p))/d(dreh rad, sx, sy)
        if frei: J = np.c_[J, np.einsum('ij,ij->i', n, rq) / m]                                            # d/dm
        r = np.einsum('ij,ij->i', n, q - p); x = np.linalg.lstsq(J, -r, rcond=None)[0]; g += float(np.degrees(x[0])); s += x[1:3]
        if frei: m += float(x[3])
        if np.abs(x).max() < 1e-5: break
    Q = bild2(PB2, c, g, s, m); d, _ = baum.query(Q); return g, s, m, d < TREFFER_M


def zuege(P, N, verbind_m=0.5, min_n=None):
    """Wandzuege der Treffer: Punkte (Grundriss) mit Normalen, verbunden wenn < verbind_m entfernt UND parallel (< PARALLEL_GRAD). -> Liste dict(n, normale, d, mitte, laenge)."""
    from scipy.spatial import cKDTree
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    min_n = MIN_ZUG_PUNKTE if min_n is None else min_n
    if len(P) < min_n: return []
    pa = cKDTree(P).query_pairs(verbind_m, output_type="ndarray"); cp = np.cos(np.radians(PARALLEL_GRAD))
    pa = pa[np.abs(np.einsum('ij,ij->i', N[pa[:, 0]], N[pa[:, 1]])) > cp]
    _, lab = connected_components(coo_matrix((np.ones(len(pa)), (pa[:, 0], pa[:, 1])), shape=(len(P), len(P))), directed=False); aus = []
    for l in np.unique(lab):
        j = lab == l
        if j.sum() < min_n: continue
        nn = N[j] * np.sign(N[j] @ N[j][0])[:, None]; n = nn.mean(0); n /= np.linalg.norm(n); t = np.array([-n[1], n[0]]); u = P[j] @ t
        aus.append(dict(n=int(j.sum()), normale=n, d=float(np.median(P[j] @ n)), mitte=P[j].mean(0), laenge=float(np.percentile(u, 98) - np.percentile(u, 2))))
    return aus


def hebel(zg):
    """MASSSTAB-HEBEL der Wandzuege (m): Abstand der Wandlinien von ihrem gemeinsamen Ausgleichspunkt (Wurzel der Restquadratsumme / (Zuege - 2), die Verschiebung
    nimmt 2 Freiheitsgrade). Laufen alle Linien durch einen Punkt (eine Ecke, eine Wand, zwei Waende), legt eine Verschiebung sie alle fest und der Massstab um diesen
    Punkt ist NICHT bestimmt (Hebel 0). Erst nicht parallele Wandzuege in unterschiedlichem Abstand (oder zwei parallele Waende) belegen ihn; die Restquadratsumme ist
    die Information ueber den Massstab neben der Verschiebung -> Massstab-Streuung ~ Wandlage-Rauschen / Hebel."""
    if len(zg) < 3: return 0.0
    Nn = np.array([z["normale"] for z in zg]); d = np.array([z["d"] for z in zg]); x = np.linalg.lstsq(Nn, d, rcond=None)[0]
    return float(np.sqrt(np.sum((Nn @ x - d) ** 2) / (len(zg) - 2)))


def doppelwand(PA2, NA2, Q, NQ, tr):
    """DOPPELWAND-GEGENPROBE nach der Bindung: B-Wandpunkte, die selbst NICHT auf A treffen, aber parallel (< PARALLEL_GRAD) und DOPPEL_MIN_M..DOPPEL_MAX_M neben einer
    A-Wand liegen (laengs hoechstens DOPPEL_LAENGS_M versetzt), zu Blaettern verbunden (1 m). -> Liste dict(n, versatz_m, mitte, abstand_anker_m), groesste zuerst."""
    from scipy.spatial import cKDTree
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    baum = cKDTree(PA2); cp = np.cos(np.radians(PARALLEL_GRAD)); kand = []; off = []
    for i in np.flatnonzero(~tr):
        J = np.array(baum.query_ball_point(Q[i], DOPPEL_MAX_M), int)
        if not len(J): continue
        n = NA2[J]; dq = Q[i] - PA2[J]; quer = np.abs(np.einsum('ij,ij->i', dq, n)); laengs = np.abs(dq[:, 0] * n[:, 1] - dq[:, 1] * n[:, 0])
        ok = (np.abs(n @ NQ[i]) > cp) & (laengs < DOPPEL_LAENGS_M)
        if not ok.any(): continue
        q = float(quer[ok].min())
        if DOPPEL_MIN_M <= q <= DOPPEL_MAX_M: kand.append(i); off.append(q)
    if not kand: return []
    kand = np.array(kand); off = np.array(off); pa = cKDTree(Q[kand]).query_pairs(1.0, output_type="ndarray")
    _, lab = connected_components(coo_matrix((np.ones(len(pa)), (pa[:, 0], pa[:, 1])), shape=(len(kand), len(kand))), directed=False)
    anker = Q[tr].mean(0) if tr.any() else Q.mean(0); aus = []
    for l in np.unique(lab):
        j = lab == l; m_ = Q[kand[j]].mean(0)
        aus.append(dict(n=int(j.sum()), versatz_m=round(float(np.median(off[j])), 2), mitte=[round(float(x), 2) for x in m_], abstand_anker_m=round(float(np.linalg.norm(m_ - anker)), 1)))
    return sorted(aus, key=lambda x: -x["n"])


def doppel_grenze(n_b): return max(DOPPEL_MIN_PUNKTE, int(np.ceil(DOPPEL_ANTEIL * n_b)))


def z_versatz(ZA, ZB, grenze):
    """Hoehenprofile (Dichte der Wandpunkte je Hoehe) von A und B kreuzkorreliert. -> (dz, eindeutig, guete)."""
    if len(ZA) < 50 or len(ZB) < 50: return 0.0, False, 0.0
    z0, z1 = min(ZA.min(), ZB.min()) - grenze, max(ZA.max(), ZB.max()) + grenze; b = np.arange(z0, z1 + Z_PROFIL_M, Z_PROFIL_M)
    def prof(Z):
        h = np.log1p(np.histogram(Z, b)[0].astype(float)); h = h - np.convolve(h, np.ones(15) / 15, "same"); return h / (np.linalg.norm(h) + 1e-12)
    pa, pb = prof(ZA), prof(ZB); k = int(np.ceil(grenze / Z_PROFIL_M)); L = np.arange(-k, k + 1)
    cc = np.array([np.dot(pa, np.roll(pb, l)) for l in L]); i = int(np.argmax(cc)); weit = np.abs(L - L[i]) * Z_PROFIL_M >= ABSTAND_ZWEIT_M
    zw = float(cc[weit].max()) if weit.any() else 0.0; ok = cc[i] > 0.2 and zw <= ZWEIT_ANTEIL * cc[i] and abs(L[i]) < k
    return float(L[i] * Z_PROFIL_M), bool(ok), float(cc[i])


def _zellen(P, zelle):
    ij = np.floor(P[:, :2] / zelle).astype(np.int64); return ij[:, 0] * 2000003 + ij[:, 1]


def z_saeulen(PA, PB, suche=Z_SUCHE_M):
    """HOEHE AUS DER 3D-UEBERLAPPUNG (lokales A-System, z = Lot, Meter; B schon im Grundriss gebunden). Je gemeinsam belegter Grundriss-Saeule (Z_SAEULE_M) das
    Belegungsprofil in z (log Anzahl je Z_BIN_M), hochpassgefiltert (Z_HOCHPASS_M) und normiert; Kreuzkorrelation summiert ueber alle Saeulen -> Versatz dz fuer B.
    URSACHE des alten Fehlschlags (z_versatz, 1122z: 7,6 m, Guete 0,29, nicht eindeutig): es nahm (a) nur Punkte EBENER SENKRECHTER Wandstuecke - die sind gegen eine
    Hoehenverschiebung blind (Fensterkanten, Simse, Traufe sind gerade nicht eben-senkrecht) - und (b) EIN globales Histogramm aller Waende: Fensterreihen verschiedener
    Fassaden in verschiedener Hoehe verwischen, die Dichte spiegelt die Sichtbarkeit (A von oben, B frontal) statt der Gestalt. Je Saeule bleibt die Lage der Fenster,
    Gesimse und Traufe erhalten (1122z: 399 Saeulen, Gipfel 6,6 m, zweiter 13-29 %).
    Unterhalb Boden + Z_MIN_M + Z_HOCHPASS_M/2 (je Teil, eigener 2-%-Wert) wird das Profil ausgeblendet: der Boden selbst bleibt fuer die unabhaengige Gegenprobe.
    -> dict(dz_m, eindeutig, guete, zweit_anteil, saeulen, grund)."""
    aus = dict(dz_m=0.0, eindeutig=False, guete=0.0, zweit_anteil=None, saeulen=0, grund="")
    if len(PA) < 100 or len(PB) < 100: aus["grund"] = "zu wenig Punkte"; return aus
    ka, kb = _zellen(PA, Z_SAEULE_M), _zellen(PB, Z_SAEULE_M); gem = np.intersect1d(np.unique(ka), np.unique(kb))
    ma, mb = np.isin(ka, gem), np.isin(kb, gem); A_, B_ = PA[ma], PB[mb]; ka, kb = ka[ma], kb[mb]
    if len(gem) < Z_MIN_SAEULEN: aus.update(saeulen=int(len(gem)), grund=f"nur {len(gem)} gemeinsame Saeulen (noetig {Z_MIN_SAEULEN})"); return aus
    fa, fb = float(np.percentile(A_[:, 2], 2)), float(np.percentile(B_[:, 2], 2))
    z0 = min(np.percentile(A_[:, 2], 0.5), np.percentile(B_[:, 2], 0.5)) - suche - Z_HOCHPASS_M; z1 = max(np.percentile(A_[:, 2], 99.5), np.percentile(B_[:, 2], 99.5)) + suche + Z_HOCHPASS_M
    nz = int(np.ceil((z1 - z0) / Z_BIN_M)) + 1
    def prof(P, k, fuss):
        iz = np.clip(((P[:, 2] - z0) / Z_BIN_M).astype(int), 0, nz - 1); H = np.zeros((len(gem), nz)); np.add.at(H, (np.searchsorted(gem, k), iz), 1.0)
        belegt = (H > 0).sum(1); h = np.log1p(H); w = max(3, int(round(Z_HOCHPASS_M / Z_BIN_M)) | 1)
        from scipy.ndimage import uniform_filter1d
        h = h - uniform_filter1d(h, w, axis=1, mode="constant"); h[:, : max(0, int((fuss + Z_MIN_M + Z_HOCHPASS_M / 2 - z0) / Z_BIN_M))] = 0.0
        return h, belegt
    ha, ba = prof(A_, ka, fa); hb, bb = prof(B_, kb, fb); ok = (ba >= Z_MIN_BELEGT) & (bb >= Z_MIN_BELEGT)
    na_, nb_ = np.linalg.norm(ha, axis=1), np.linalg.norm(hb, axis=1); ok &= (na_ > 0) & (nb_ > 0); aus["saeulen"] = int(ok.sum())
    if ok.sum() < Z_MIN_SAEULEN: aus["grund"] = f"nur {int(ok.sum())} Saeulen mit Hoehenstruktur in beiden Teilen (noetig {Z_MIN_SAEULEN})"; return aus
    ha, hb = ha[ok] / na_[ok, None], hb[ok] / nb_[ok, None]
    from scipy.signal import fftconvolve
    k = int(np.ceil(suche / Z_BIN_M)); cc_voll = fftconvolve(ha, hb[:, ::-1], mode="full", axes=1).sum(0) / len(ha)   # cc_voll[nz-1+l] = sum_z ha(z) hb(z-l)
    L = np.arange(-k, k + 1); cc = cc_voll[nz - 1 + L]; i = int(np.argmax(cc)); weit = np.abs(L - L[i]) * Z_BIN_M >= ABSTAND_ZWEIT_M
    zw = float(cc[weit].max()) if weit.any() else 0.0; dz = float(L[i] * Z_BIN_M)
    if 0 < i < len(cc) - 1:                                                             # Parabel durch den Gipfel: Feinlage unter dem Raster
        a_, b_, c_ = cc[i - 1], cc[i], cc[i + 1]; den = a_ - 2 * b_ + c_
        if den < 0: dz += float(np.clip(0.5 * (a_ - c_) / den, -0.5, 0.5)) * Z_BIN_M
    za = zw / cc[i] if cc[i] > 0 else 1.0; rand = abs(L[i]) >= k - 1
    ein = bool(cc[i] > 0 and za <= Z_ZWEIT_ANTEIL and not rand)
    aus.update(dz_m=round(dz, 3), eindeutig=ein, guete=round(float(cc[i]), 4), zweit_anteil=round(float(za), 3),
               grund="" if ein else ("Gipfel am Rand der Suche" if rand else f"zweiter Gipfel {100 * za:.0f} % (Grenze {100 * Z_ZWEIT_ANTEIL:.0f} %)"))
    return aus


def strassen_boden(P):
    """Strassenzellen eines Teils: {zelle: 3-%-Hoehe} fuer Zellen (BODEN_ZELLE_M) mit >= BODEN_MIN_PUNKTE Punkten, deren Boden hoechstens BODEN_BAND_M ueber dem
    10-%-Wert aller Zellboeden liegt (Daecher, Mauerkronen, nur von oben gesehene Flaechen fallen weg)."""
    k = _zellen(P, BODEN_ZELLE_M); o = np.argsort(k, kind="stable"); k, z = k[o], P[o, 2]
    u, s, n = np.unique(k, return_index=True, return_counts=True); j = n >= BODEN_MIN_PUNKTE
    if not j.any(): return {}
    zb, fl = [], []
    for a, m in zip(s[j], n[j]):
        zz = z[a:a + m]; q = np.percentile(zz, 3); zb.append(q); unten = np.sum(np.abs(zz - q) <= BODEN_DICKE_M); drueber = np.sum((zz > q + BODEN_DICKE_M) & (zz <= q + 3 * BODEN_DICKE_M))
        fl.append(unten >= BODEN_FLACH_FAKTOR * max(drueber, 1))
    zb, fl = np.array(zb), np.array(fl); f = fl                                         # waagerechte Flaeche unten (kein Wandfuss einer Wolke, die die Strasse nicht sieht)
    if not f.any(): return {}
    grenze = np.percentile(zb[f], 10) + BODEN_BAND_M
    return {int(kk): float(v) for kk, v, ff in zip(u[j], zb, f) if ff and v <= grenze}


def boden_versatz(PA, PB):
    """UNABHAENGIGE GEGENPROBE: Strassenboden von A minus Strassenboden von B in gemeinsamen Zellen. -> dict(dz_m, streuung_m, zellen, messbar)."""
    sa, sb = strassen_boden(PA), strassen_boden(PB); g = [k for k in sb if k in sa]
    if len(g) < BODEN_MIN_ZELLEN: return dict(dz_m=None, streuung_m=None, zellen=len(g), messbar=False, grund=f"nur {len(g)} gemeinsame Strassenzellen (noetig {BODEN_MIN_ZELLEN})")
    d = np.array([sa[k] - sb[k] for k in g]); q1, q3 = np.percentile(d, [25, 75]); sd = float((q3 - q1) / 1.349)
    ok = sd <= BODEN_STREU_MAX_M
    return dict(dz_m=round(float(np.median(d)), 3), streuung_m=round(sd, 3), zellen=len(g), messbar=bool(ok), grund="" if ok else f"Streuung {sd:.2f} m > {BODEN_STREU_MAX_M} m")


def unter_gelaende(PA, PB):
    """TOR 'TEILWOLKE UNTER GELAENDE' (allgemein, je Seitenteil): Anteil der B-Punkte in gemeinsamen Strassenzellen, die mehr als UNTER_M unter dem Strassenboden von A
    liegen; zum Vergleich derselbe Anteil von A selbst (Rauschen der dichten Wolke). -> dict(anteil_b, anteil_a, zellen, ok) (ok None = nicht pruefbar)."""
    sa = strassen_boden(PA)
    if not sa: return dict(anteil_b=None, anteil_a=None, zellen=0, ok=None)
    sk = np.array(sorted(sa), np.int64); sv = np.array([sa[int(x)] for x in sk])
    def anteil(P):
        k = _zellen(P, BODEN_ZELLE_M); m = np.isin(k, sk)
        if m.sum() < 100: return None, int(len(np.unique(k[m])))
        g = sv[np.searchsorted(sk, k[m])]; return float((P[m, 2] < g - UNTER_M).mean()), int(len(np.unique(k[m])))
    ab, n = anteil(PB); aa, _ = anteil(PA)
    if ab is None: return dict(anteil_b=None, anteil_a=aa, zellen=n, ok=None)
    return dict(anteil_b=round(ab, 4), anteil_a=round(aa, 4), zellen=n, ok=bool(ab <= UNTER_ANTEIL))


def hoehe_belegen(PA, PB):
    """HOEHE VON B (lokales A-System, B im Grundriss gebunden): vorrangig aus der 3D-Ueberlappung (z_saeulen), Boden (boden_versatz) als unabhaengige Gegenprobe.
      Struktur eindeutig + Boden einig (<= HOEHE_EINIG_M) oder nicht messbar -> dz = Struktur (Boden-Fehlen gemeldet);
      Struktur eindeutig + Boden uneinig -> 'uneinig' (Bindung ablehnen);
      Struktur nicht eindeutig + Boden messbar -> dz = Boden (gemeldet); beides fehlt -> dz 0, 'nicht belegt' (kein Raten; Unter-Gelaende-Tor entscheidet).
    -> dict(dz_m, quelle, uneinig, struktur, boden, meldung)."""
    st = z_saeulen(PA, PB); bo = boden_versatz(PA, PB); aus = dict(struktur=st, boden=bo, uneinig=False)
    if st["eindeutig"]:
        if bo["messbar"] and abs(st["dz_m"] - bo["dz_m"]) > HOEHE_EINIG_M:
            aus.update(dz_m=0.0, quelle="uneinig", uneinig=True, meldung=f"Hoehe uneinig: Struktur {st['dz_m']:+.2f} m, Boden {bo['dz_m']:+.2f} m (Grenze {HOEHE_EINIG_M} m)")
        else:
            aus.update(dz_m=st["dz_m"], quelle="struktur", meldung=f"Hoehe aus der 3D-Ueberlappung {st['dz_m']:+.2f} m ({st['saeulen']} Saeulen, zweiter Gipfel {100 * st['zweit_anteil']:.0f} %); "
                       + (f"Boden einig {bo['dz_m']:+.2f} m ({bo['zellen']} Zellen)" if bo["messbar"] else f"Boden nicht pruefbar ({bo['grund']})"))
    elif bo["messbar"]:
        aus.update(dz_m=bo["dz_m"], quelle="boden", meldung=f"Hoehe aus dem Strassenboden {bo['dz_m']:+.2f} m ({bo['zellen']} Zellen, Streuung {bo['streuung_m']:.2f} m); Struktur nicht eindeutig ({st['grund']})")
    else:
        aus.update(dz_m=0.0, quelle="nicht belegt", meldung=f"Hoehe NICHT BELEGT (Struktur: {st['grund']}; Boden: {bo['grund']}) - bleibt am GPS-Fusspunkt")
    return aus


def seitenbild(pfad, PA, PB, titel):
    """Seitenansichten (zwei waagerechte Achsen) A blau, B rot, Hoehenmarken alle 10 m."""
    import cv2
    W, H = 700, 700; rng = np.random.default_rng(0); c = np.median(PB[:, :2], 0); zl = float(np.percentile(np.r_[PA[:, 2], PB[:, 2]], 0.5)) - 2
    zh = float(np.percentile(np.r_[PA[:, 2], PB[:, 2]], 99.9)) + 2; r = max(zh - zl, 20.0) / 2; sk = H / (2 * r); bilder = []
    for ax in (0, 1):
        im = np.full((H, W, 3), 255, np.uint8)
        for P, col in ((PA, (200, 120, 0)), (PB, (0, 0, 220))):
            P = P[rng.choice(len(P), min(len(P), 300000), replace=False)]; u = (W / 2 + (P[:, ax] - c[ax]) * sk).astype(int); v = (H - (P[:, 2] - zl) * sk).astype(int)
            ok = (u >= 0) & (u < W) & (v >= 0) & (v < H); im[v[ok], u[ok]] = col
        for zz in np.arange(np.ceil(zl / 10) * 10, zh, 10):
            v = int(H - (zz - zl) * sk); cv2.line(im, (0, v), (10, v), (0, 0, 0), 1); cv2.putText(im, f"{zz:.0f}", (12, v + 4), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 0), 1)
        bilder.append(im)
    im = np.hstack(bilder); cv2.putText(im, titel[:160], (8, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 1); cv2.imwrite(pfad, im)


# ---------- Kern
def binden(DA, DB, G, lot0, ref_b, bild=None):
    """DA/DB dichte Wolken (je eigenes Modellsystem), G = seiten_querspur_binden.gps_unsicherheit(...), lot0 = Start-Lot von A, ref_b = Bezugspunkte in B (Kamerazentren).
    -> Ergebnis-dict (ok, urteil, zu_wenig, B_nach_A bei ok, pruefung, korridor)."""
    mj = G["m_je_einheit"]; Mg = G["M"]; pr = {}; erg = dict(art="waende", B_nach_A_gps=Mg.tolist(), pruefung=pr)
    ua, na = lot_aus_waenden(DA, np.asarray(lot0, float)); Bg = anwenden(Mg, DB); ub, nb = lot_aus_waenden(Bg, ua)
    kipp = float(np.degrees(np.arccos(np.clip(ua @ ub, -1, 1)))); pr.update(lot_normalen_a=int(na), lot_normalen_b=int(nb), kippung_gps_grad=round(kipp, 2))
    if nb < MIN_KIPP_NORMALEN or na < MIN_KIPP_NORMALEN:
        erg.update(ok=False, zu_wenig=True, urteil=f"Lot aus den Waenden nicht messbar (Normalen A {na}, B {nb}, noetig {MIN_KIPP_NORMALEN}) - GPS-Lage bleibt"); return erg
    # KIPPUNG von B um den FUSSPUNKT seiner Wolke (waagerecht Wolkenmitte, Hoehe = Boden der B-Wolke): dort traegt die GPS-Lage die Hoehe (Boden der dichten Wolke
    # unter den nahen GPS-Kameras, seiten_gps_vereinen.rahmen). Waende legen die Hoehe nicht fest. 1122w gemessen: um die Kameramitte gekippt rutschte der Turm 8,4 m
    # waagerecht und 11,6 m nach oben (Fern-/Schlossbergkameras weit weg und hoch) - falsch; um die Wolkenmitte deckten sich Traufe, Uhr und Helm beider Teile.
    pv = np.median(Bg, 0); pv = pv - (pv @ ua - np.percentile(Bg @ ua, 2)) * ua; Rk = drehung(np.cross(ub, ua), kipp) if kipp > 1e-6 else np.eye(3)
    Mk = np.eye(4); Mk[:3, :3] = Rk; Mk[:3, 3] = pv - Rk @ pv
    erg["B_nach_A_kipp"] = (Mk @ Mg).tolist(); pr["lot_a"] = [float(x) for x in ua]             # fuer die Lot-Tore in main (kamera_lot_probe): nur Kippung, GPS-Massstab
    E = basis(ua); L = np.eye(4); L[:3, :3] = mj * E                                   # lokales metrisches System von A (z = Lot)
    la = anwenden(L, DA); lb = anwenden(L @ Mk @ Mg, DB); boden = float(np.percentile(la[:, 2], 2))
    wa, nwa = wandpunkte(la[la[:, 2] > boden + Z_MIN_M]); wb, nwb = wandpunkte(lb[lb[:, 2] > boden + Z_MIN_M])
    c = np.median(wb[:, :2], 0) if len(wb) else np.zeros(2)
    # KORRIDOR mit der EHRLICHEN GPS-Unsicherheit (Zufall + Sitzungsfehler, gps_unsicherheit.py; Lehre 22.11.: Bootstrap allein unterschaetzt - 1122 Teil 1 Bootstrap +-1,4 Grad,
    # ehrlich +-9,3 Grad; die Waende messen 4-5 Grad). Suche hoechstens +-DREH_SUCHE_MAX (90-Grad-Verwechslung eines Kastenturms bleibt ausgeschlossen).
    G = dict(G, dreh_sd=max(G["dreh_sd"], G.get("dreh_sd_ehrlich") or 0.0), mass_sd=max(G["mass_sd"], G.get("mass_sd_ehrlich") or 0.0))
    k0 = korridor(Mg, G, ua, ref_b); gd, lg = min(k0["dreh_grenze_grad"], DREH_SUCHE_MAX), min(k0["lage_grenze_m"], LAGE_SUCHE_MAX_M); pr.update(dreh_grenze_grad=gd, lage_grenze_m=lg)
    r_b = float(np.percentile(np.linalg.norm(wb[:, :2] - c, axis=1), 99)) if len(wb) else 0.0; nah = np.linalg.norm(wa[:, :2] - c, axis=1) < r_b + lg + 2.0
    wa, nwa = wa[nah], nwa[nah]; pr.update(wandpunkte_a=int(len(wa)), wandpunkte_b=int(len(wb)))
    if len(wa) < MIN_WANDPUNKTE or len(wb) < MIN_WANDPUNKTE:
        erg.update(ok=False, zu_wenig=True, urteil=f"zu wenig Wandpunkte im Suchgebiet (A {len(wa)}, B {len(wb)}, noetig {MIN_WANDPUNKTE}) - GPS-Lage bleibt"); return erg
    A2, NA2 = wa[:, :2], nwa[:, :2] / (np.linalg.norm(nwa[:, :2], axis=1, keepdims=True) + 1e-12); B2 = wb[:, :2]
    from scipy.spatial import cKDTree
    d_vor = float(np.median(cKDTree(A2).query(B2)[0]))
    s = suche(A2, B2, c, gd, lg); pr["suche"] = dict(dreh_grad=round(s["dreh"], 2), schieb_m=[round(float(x), 2) for x in s["schieb"]], wert=round(s["wert"], 3), zweit=round(s["zweit"], 3),
                                                    zweit_abstand_m=round(s["zweit_abstand"], 2), kastenrand=s["rand"])
    g, sv, tr = fein(A2, NA2, B2, c, s["dreh"], s["schieb"]); tr0 = tr
    # MASSSTAB MITSCHAETZEN (Aehnlichkeit im Grundriss um c, in der Hoehe um den Fusspunkt von B): der Massstab B->A kam bisher ungeprueft vom GPS (1122: ehrlich +-16 %).
    # Starr passt alles nahe am Anker, 20 m weiter entsteht eine Doppelwand (1122y). Uebernommen nur, wenn die Treffer ihn BELEGEN: Wandzuege, die nicht durch einen
    # gemeinsamen Punkt laufen (Hebel >= HEBEL_MIN_M), Abweichung >= MASS_SIGNIFIKANZ Streuungen, hoechstens MASS_MAX_REL, mehr Treffer als starr. Sonst GPS-Massstab.
    NB2 = nwb[:, :2] / (np.linalg.norm(nwb[:, :2], axis=1, keepdims=True) + 1e-12); nq = lambda g_: NB2 @ r2(g_).T
    dop0 = doppelwand(A2, NA2, bild2(B2, c, g, sv), nq(g), tr)
    gm, svm, mm, trm = fein_aehnlich(A2, NA2, B2, c, g, sv, runden=30, grenze=DOPPEL_MAX_M)
    zg = zuege(bild2(B2, c, gm, svm, mm)[trm], nq(gm)[trm]); hb = hebel(zg); sd_m = SIGMA_M / hb if hb > 0 else float("inf")
    mg = []
    if hb < HEBEL_MIN_M: mg.append(f"Hebel {hb:.1f} m < {HEBEL_MIN_M} m ({len(zg)} Wandzuege)")
    if not (np.isfinite(mm) and mm > 0): mg.append(f"Aehnlichkeit entartet (Massstab {mm})"); mm = 1.0
    elif abs(np.log(mm)) < MASS_SIGNIFIKANZ * sd_m: mg.append(f"Abweichung {100 * (mm - 1):+.1f} % unter {MASS_SIGNIFIKANZ:.0f} Streuungen ({100 * sd_m:.1f} %)")
    if abs(mm - 1) > MASS_MAX_REL: mg.append(f"Abweichung {100 * (mm - 1):+.1f} % ueber {100 * MASS_MAX_REL:.0f} %")
    if trm.mean() <= tr.mean(): mg.append(f"nicht mehr Treffer ({100 * tr.mean():.0f} -> {100 * trm.mean():.0f} %)")
    ms = 1.0
    if not mg: g, sv, ms, tr = gm, svm, mm, trm
    pr["massstab"] = dict(gegen_gps=round(mm, 4), uebernommen=not mg, gruende=mg, hebel_m=round(hb, 2), streuung_rel=round(min(sd_m, 9.9), 4), wandzuege=len(zg),
                          treffer_starr=round(float(tr0.mean()), 3), treffer_aehnlich=round(float(trm.mean()), 3))
    # 24.11.2026: Skalierungsmittelpunkt c in B-Koordinaten ablegen -> gps_probe misst den Hebel der GEOTAGGTEN B-Kameras dazu (Massstab-Toleranz in gps_urteil)
    _zc = float(np.median(wb[:, 2])) if len(wb) else 0.0
    pr["massstab"]["mitte_b"] = [float(x) for x in anwenden(np.linalg.inv(L @ Mk @ Mg), np.array([[c[0], c[1], _zc]]))[0]]
    Q = bild2(B2, c, g, sv, ms)
    di, ii = cKDTree(A2).query(Q); d_nach = float(np.median(di))
    ax = (np.degrees(np.arctan2(NA2[:, 1], NA2[:, 0])) % 90); az = float(np.degrees(np.angle(np.exp(4j * np.radians(ax)).mean())) / 4 % 90)
    u = np.array([np.cos(np.radians(az)), np.sin(np.radians(az))]); v = np.array([-u[1], u[0]])   # die zwei Wandrichtungen (Normalen) von A
    def richt(m):
        n_ = np.abs(nwb[m, :2] @ r2(g).T); return ((np.abs(n_ @ u) > 0.8).mean(), (np.abs(n_ @ v) > 0.8).mean()) if m.any() else (0.0, 0.0)
    ra, rb_ = richt(tr)
    # ZWEITE PROBE: zwei Hoehenbaender einzeln ausgeglichen. Verglichen wird die Lage nur laengs der Wandnormalen, die in BEIDEN Baendern tragen (eine Wand allein legt
    # die Lage laengs ihrer selbst nicht fest - 1122w: unteres Band sieht nur die Ostflanke und glitt 1,1 m laengs); traegt keine Richtung in beiden, keine Probe.
    zm = float(np.median(wb[:, 2])); baender = []
    for m in (wb[:, 2] < zm, wb[:, 2] >= zm):
        if m.sum() < MIN_WANDPUNKTE // 2: baender.append(None); continue
        gb_, sb_, tb_ = fein(A2, NA2, B2[m], c, g, sv, m=ms); mk = np.zeros(len(B2), bool); mk[np.flatnonzero(m)[tb_]] = True
        baender.append((gb_, sb_, richt(mk), float(tb_.mean())))
    # Hoehe: Profile der B-Treffer und der A-Wandpunkte in ihrer Naehe
    ZB = wb[tr, 2]
    nah_a = cKDTree(Q[tr]).query(wa[:, :2])[0] < TREFFER_M if tr.any() else np.zeros(len(wa), bool); ZA = wa[nah_a, 2]
    dz, z_ok, z_g = z_versatz(ZA, ZB, lg)
    pr.update(dreh_grad=round(g, 3), schieb_m=[round(float(x), 3) for x in sv], treffer=round(float(tr.mean()), 3), richtungen=[round(float(ra), 3), round(float(rb_), 3)],
              wandabstand_median_m=dict(gps=round(d_vor, 3), nach=round(d_nach, 3)), hoehe=dict(dz_m=round(dz, 2), eindeutig=z_ok, guete=round(z_g, 3), n_a=int(len(ZA)), n_b=int(len(ZB))),
              baender=[None if b is None else dict(dreh_grad=round(b[0], 3), schieb_m=[round(float(x), 3) for x in b[1]], richtungen=[round(float(x), 3) for x in b[2]], treffer=round(b[3], 3)) for b in baender])
    # Gesamtmatrix B -> A: L^-1 * P * L * Mk * Mg, P = Drehung um c (Lot) + Verschiebung + dz im lokalen System
    zf = float(np.percentile(lb[:, 2], 2))                                             # Fusspunkt-Hoehe von B: der Massstab aendert sie nicht (dort traegt das GPS)
    P = np.eye(4); P[:2, :2] = ms * r2(g); P[2, 2] = ms; P[:2, 3] = c + sv - ms * r2(g) @ c; P[2, 3] = zf - ms * zf
    M = np.linalg.inv(L) @ P @ L @ Mk @ Mg
    # HOEHE (24.11.2026, Kette 1122z, Nutzer "Ostteil in den Boden verrutscht"): bisher blieb sie am GPS-Fusspunkt (Boden der dichten B-Wolke unter den GPS-Kameras,
    # seiten_gps_vereinen.rahmen). 1122z gemessen: nur 12 GPS-Kameras von B mit Bodenpunkten im 5-m-Umkreis, deren "Boden" streut p10 -3,6 / p90 +10,1 m (erhoehte
    # Standorte, Waende/Daecher im Umkreis) -> Teil 1 lag 6,4 m (Strassenboden) zu tief, 19 % seiner Punkte in Strassenzellen > 1 m unter dem Boden von A, Spitze 39 statt 45 m.
    # Jetzt: Hoehe aus der 3D-Ueberlappung (Saeulenprofile, z_saeulen), Strassenboden von A als unabhaengige Gegenprobe, danach Tor "unter Gelaende".
    # Das alte globale Wandprofil (z_versatz) bleibt nur Bericht (pruefung.hoehe).
    pr["hoehe"]["nur_bericht"] = True
    lbn0 = anwenden(L @ M, DB); hb_ = hoehe_belegen(la, lbn0); dz_h = float(hb_["dz_m"])
    T_ = np.eye(4); T_[2, 3] = dz_h; M = np.linalg.inv(L) @ T_ @ L @ M
    ug = unter_gelaende(la, lbn0 + [0, 0, dz_h]); ug_vor = unter_gelaende(la, lbn0)
    pr["hoehe_3d"] = dict(hb_, unter_gelaende=ug, unter_gelaende_fusspunkt=ug_vor)
    if bild:
        try: seitenbild(os.path.splitext(bild)[0] + "_seite.jpg", la, lbn0 + [0, 0, dz_h], f"Seitenansicht nach Bindung: {hb_['meldung']}")
        except Exception as ex: pr["hoehe_3d"]["seitenbild_fehler"] = f"{type(ex).__name__}: {ex}"
    k = korridor(M, G, ua, ref_b)
    # Lage der B-Kameras nur WAAGERECHT gegen das GPS (Handy-GPS traegt keine Hoehe; die Kippung aus den Waenden hebt/senkt ferne Kameras, 1122w: 17,5 m 3D bei 10 Grad)
    dX = anwenden(M, ref_b) - anwenden(Mg, ref_b); dX = dX - np.outer(dX @ ua, ua); k["lage_3d_m"] = k["lage_m"]; k["lage_m"] = round(float(np.median(np.linalg.norm(dX, axis=1))) * mj, 3)
    k["gruende"] = [x for x in k["gruende"] if not x.startswith("Lage der B-Kameras")] + ([f"Lage der B-Kameras waagerecht {k['lage_m']:.1f} m neben GPS (Grenze {k['lage_grenze_m']:.1f} m)"] if k["lage_m"] > k["lage_grenze_m"] else [])
    erg["korridor"] = k
    gr = []
    if s["rand"]: gr.append(f"Bestwert am Kastenrand der Suche (Drehung {s['dreh']:+.2f} Grad, Verschiebung {np.hypot(*s['schieb']):.2f} m, Grenzen {gd} Grad / {lg} m)")
    if s["zweit"] > ZWEIT_ANTEIL * s["wert"]: gr.append(f"mehrdeutig: zweite Lage {s['zweit_abstand']:.1f} m daneben erreicht {100 * s['zweit'] / max(s['wert'], 1e-9):.0f} % des Bestwerts")
    if kipp > KIPP_GRENZE_GRAD: gr.append(f"Kippung der GPS-Lage {kipp:.1f} Grad (Wand-Lot misst nur bis {KIPP_GRENZE_GRAD:.0f})")
    kg = [x for x in k["gruende"] if not x.startswith("Kippung")]                      # Kippung kommt hier aus den Waenden, nicht vom GPS (dessen Lot = Bild-x-Achsen)
    if kg: gr.append("ausserhalb des GPS-Korridors: " + "; ".join(kg))
    if tr.mean() < MIN_TREFFER: gr.append(f"nur {100 * tr.mean():.0f} % der B-Wandpunkte auf A-Waenden (noetig {100 * MIN_TREFFER:.0f} %)")
    if min(ra, rb_) < MIN_RICHTUNG_ANTEIL: gr.append(f"nur eine Wandrichtung traegt ({100 * ra:.0f} % / {100 * rb_:.0f} %) - Lage laengs der Wand nicht bestimmt")
    if any(b is None for b in baender): gr.append("ein Hoehenband ohne genug Wandpunkte - keine zweite Probe")
    else:
        ds = np.asarray(baender[0][1]) - baender[1][1]; dd = abs(baender[0][0] - baender[1][0]); getragen = [i for i in (0, 1) if min(baender[0][2][i], baender[1][2][i]) >= MIN_RICHTUNG_ANTEIL]
        dl = float(max([abs(ds @ (u, v)[i]) for i in getragen], default=float("nan"))); pr["baender_uneinig"] = dict(lage_m=round(dl, 3), dreh_grad=round(dd, 3), richtungen_verglichen=len(getragen))
        if not getragen: gr.append("keine Wandrichtung traegt in beiden Hoehenbaendern - keine zweite Probe")
        elif dl > BAND_LAGE_M or dd > BAND_DREH_GRAD: gr.append(f"Hoehenbaender uneinig ({dl:.2f} m / {dd:.2f} Grad, Grenzen {BAND_LAGE_M} m / {BAND_DREH_GRAD} Grad)")
    if d_nach >= d_vor: gr.append(f"Wandabstand nicht kleiner ({d_vor:.2f} -> {d_nach:.2f} m)")
    if hb_["uneinig"]: gr.append(hb_["meldung"])
    if ug["ok"] is False: gr.append(f"Teilwolke B unter Gelaende: {100 * ug['anteil_b']:.1f} % der B-Punkte in {ug['zellen']} Strassenzellen > {UNTER_M} m unter dem Boden von A "
                                    f"(Grenze {100 * UNTER_ANTEIL:.0f} %, A selbst {100 * (ug['anteil_a'] or 0):.1f} %; Hoehe: {hb_['quelle']})")
    # DRITTE PROBE: TURMSPITZE (Helmstange, seiten_vereinen.stange) - in der Bindung NICHT benutzt (nur Waende). Beide Wolken muessen die Spitze bis nahe derselben Hoehe
    # haben (sonst 'nicht messbar', nur Bericht: 1122w endet die A-Wolke oben duenn); dann muss sie waagerecht auf SPITZE_M (bzw. 2 % der Hoehe) uebereinanderliegen.
    lbn = anwenden(L @ M, DB); wm = c + sv; zn = lbn[np.linalg.norm(lbn[:, :2] - wm, axis=1) < 15.0, 2]
    if len(zn) > 200:
        H = float(np.percentile(zn, 99.9) - boden); sa_, sb_ = stange(la, wm, H, boden), stange(lbn, wm, H, boden)
        if sa_ is not None and sb_ is not None:
            dxy = float(np.linalg.norm(sa_[0] - sb_[0])); dh = abs(sa_[1] - sb_[1]) / max(H, 1e-9)
            messbar = bool(dh <= SPITZE_HOEHE_ANTEIL and max(sa_[3], sb_[3]) <= SPITZE_SCHLANK_M)   # flaches Dach/Traufkante (einseitig gesehen) ist keine Spitze
            pr["spitze"] = dict(a_hoehe_m=round(sa_[1], 2), b_hoehe_m=round(sb_[1], 2), streuung_m=[round(sa_[3], 2), round(sb_[3], 2)], abstand_m=round(dxy, 2), messbar=messbar)
            if messbar and dxy > max(SPITZE_M, 0.02 * H): gr.append(f"Turmspitzen {dxy:.2f} m auseinander (Grenze {max(SPITZE_M, 0.02 * H):.2f} m)")
    # DOPPELWAND-GEGENPROBE (nach Bindung und Massstab): B-Wandblaetter parallel 0,5-3 m neben einer A-Wand, ohne selbst zu treffen, = dieselbe Wand doppelt
    # (1122y starr: 199 Punkte 2,6 m neben der Nachbarwand, 22 m vom Anker -> 9-m-Blatt im Grundriss-Tor). Bindung dann ABGELEHNT (GPS-Lage bleibt, Ausweichweg).
    dop = doppelwand(A2, NA2, Q, nq(g), tr); dg = doppel_grenze(len(B2)); grob = [x for x in dop if x["n"] >= dg]
    pr["doppelwand"] = dict(grenze_punkte=dg, starr=[x for x in dop0 if x["n"] >= dg][:5], nachher=grob[:5], nachher_klein=[x for x in dop if x["n"] < dg][:3])
    if grob: gr.append(f"Doppelwand: {len(grob)} B-Wandblatt/-blaetter parallel neben einer A-Wand (groesstes {grob[0]['n']} Punkte, {grob[0]['versatz_m']:.1f} m daneben, "
                       f"{grob[0]['abstand_anker_m']:.0f} m vom Anker; Grenze {dg} Punkte)")
    if bild: kontrollbild(bild, A2, B2, Q, wa, wb, tr, 0.0, pr, gr)
    if gr: erg.update(ok=False, urteil="ABGELEHNT: " + "; ".join(gr) + " - GPS-Lage bleibt"); return erg
    erg.update(ok=True, B_nach_A=M.tolist(), urteil=f"ueber gemeinsame Waende gebunden: Kippung {kipp:.1f} Grad (Wand-Lot), Drehung {g:+.2f} Grad, Verschiebung {np.hypot(*sv):.2f} m, "
               "Massstab " + (f"aus den Waenden {ms:.3f} x GPS (Hebel {hb:.1f} m)" if ms != 1.0 else "nach GPS") + f", {hb_['meldung']}; Wandabstand {d_vor:.2f} -> {d_nach:.2f} m, Treffer {100 * tr.mean():.0f} %; gegen GPS {k['dreh_lot_grad']:+.1f} Grad, "
               f"Lage der B-Kameras {k['lage_m']:.1f} m (Grenze {k['lage_grenze_m']} m)")
    return erg


def _winkel(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float); return float(np.degrees(np.arccos(np.clip(abs(a @ b) / (np.linalg.norm(a) * np.linalg.norm(b)), 0, 1))))


def kamerahoehe_pruefen(C_b, he, M_gps, M_kipp, M_ende, ua, mj):
    """TOR KAMERAHOEHE GEGEN DGM1 (tools/kamerahoehe_dgm.vergleich) fuer die Bindung, getrennt nach KIPPUNG und MASSSTAB.
    C_b: B-Kamerazentren (B-Modell) mit Geotag, he: erwartete Hoehe DGM1(GPS) + Hand (m, Versatz frei), ua: Lot von A (A-Modell), mj: Meter je A-Einheit.
    Verglichen: GPS-Lage (M_gps), NUR die Kippung aus den Waenden mit GPS-Massstab (M_kipp), Endlage (M_ende, mit Massstab aus den Waenden).
    Die Steigung Modell/DGM vermischt Kippung und Massstab, wenn die erhoehten Kameras alle auf EINER Seite stehen (1122zb: Schlossberg 60-85 m weg; freier Lot-Fit
    Bootstrap +-5,9 Grad) - darum wird die Kippung allein mit dem GPS-Massstab geprueft:
      - Kippung abgelehnt, wenn die Kamerahoehen damit ausserhalb des erlaubten Bands (STEIG_MIN..STEIG_MAX) liegen UND die GPS-Lage darin liegt oder naeher an 1 ist
        (Wand-Lot falsch; 1122zb echt: GPS-Lage 1,27 -> Kippung 0,99 bestaetigt, Kippung andersherum 1,55 -> abgelehnt);
      - Endlage ausserhalb, Kippung allein innerhalb: der Wand-Massstab passt zum Turm, nicht zum Kameraring (Teil gebogen / Kamera-Massstab anders) -> Bindung bleibt
        (sie kommt nur aus dem Turmbereich), die Kameras mit Rest > REST_MAX_M werden als 'Lage unbrauchbar' gemeldet;
      - Rest je Kamera (Endlage, Steigung 1, Versatz aus den Strassenkameras) > REST_MAX_M -> 'Lage unbrauchbar' (immer gemeldet, kein Ablehnungsgrund).
    -> dict(gps, kipp, ende (je kamerahoehe_dgm.vergleich), ok (None = nicht messbar), gruende, hinweise, lage_unbrauchbar (Indizes), rest_m)."""
    import kamerahoehe_dgm as KD
    C_b = np.asarray(C_b, float); he = np.asarray(he, float); ua = np.asarray(ua, float) / np.linalg.norm(ua)
    h = lambda M: (anwenden(np.asarray(M, float), C_b) @ ua) * mj
    e = {n: KD.vergleich(h(M), he) for n, M in (("gps", M_gps), ("kipp", M_kipp), ("ende", M_ende))}
    rein = lambda s: s is not None and KD.STEIG_MIN <= s <= KD.STEIG_MAX
    sg, sk, se = (e[n].get("steigung") for n in ("gps", "kipp", "ende")); gr, hw = [], []
    aus = dict(gps=e["gps"], kipp=e["kipp"], ende=e["ende"], gruende=gr, hinweise=hw, lage_unbrauchbar=[], rest_m=[])
    if e["kipp"]["ok"] is None: aus["ok"] = None; hw.append(e["kipp"]["urteil"]); return aus
    hm = h(M_ende); g = np.isfinite(hm) & np.isfinite(he); st = g & (he <= KD.ERHOEHT_M); ref = st if st.sum() >= 3 else g
    r = hm - he - (float(np.median((hm - he)[ref])) if ref.any() else 0.0); aus["rest_m"] = [round(float(x), 2) for x in r]
    aus["lage_unbrauchbar"] = [int(i) for i in np.flatnonzero(g & (np.abs(r) > KD.REST_MAX_M))]
    if sk is None: hw.append("Steigung nicht messbar (ebenes Umfeld) - Kippung nur ueber den Rest geprueft")
    elif not rein(sk) and (rein(sg) or sg is None or abs(np.log(sk)) > abs(np.log(sg))):        # Kippung treibt aus dem Band oder weiter hinaus als die GPS-Lage
        gr.append(f"Kippung aus den Waenden {'staucht' if sk < 1 else 'streckt'} die Kamerahoehen: Steigung Modell/DGM {sg:.2f} (GPS-Lage) -> {sk:.2f} (nur Kippung), "
                  f"erlaubt {KD.STEIG_MIN}-{KD.STEIG_MAX} - Wand-Lot nicht belegt")
    elif not rein(sk): hw.append(f"Kamerahoehen weder in GPS-Lage ({sg}) noch gekippt ({sk:.2f}) stimmig - DGM-Probe entscheidet die Kippung nicht")
    else: hw.append(f"Kippung bestaetigt: Steigung Modell/DGM {sg if sg is None else round(sg, 2)} (GPS-Lage) -> {sk:.2f} (nur Kippung)")
    if not gr and rein(sk) and se is not None and not rein(se):
        hw.append(f"Massstab aus den Waenden passt nicht zum Kameraring (Steigung Endlage {se:.2f}): Bindung gilt fuer den Turmbereich, {len(aus['lage_unbrauchbar'])} Kameras 'Lage unbrauchbar'")
    if e["kipp"]["ok"] is False and not gr and rein(sk) and e["kipp"]["rest_m"] > KD.REST_MAX_M: hw.append(e["kipp"]["urteil"])
    aus["ok"] = not gr; return aus


def lot_vp_pruefen(vp_oben_b, M_gps, M_ende, ua):
    """TOR FLUCHTPUNKT-LOT: Lot der B-Fotos aus den Fluchtpunkten senkrechter Kanten (B-Modell; unabhaengig von dichter Wolke und Waenden) nach der Bindung gegen das
    Lot von A. -> dict(gps_grad, ende_grad, ok (None ohne Fluchtpunkt-Lot), grund)."""
    if vp_oben_b is None: return dict(gps_grad=None, ende_grad=None, ok=None, grund="Fluchtpunkt-Lot von B nicht messbar (< 8 Bilder mit klarer Senkrechte)")
    v = np.asarray(vp_oben_b, float); wg = _winkel(np.asarray(M_gps, float)[:3, :3] @ v, ua); we = _winkel(np.asarray(M_ende, float)[:3, :3] @ v, ua)
    ok = we <= LOT_VP_GRAD
    return dict(gps_grad=round(wg, 2), ende_grad=round(we, 2), ok=bool(ok),
                grund="" if ok else f"Fluchtpunkt-Lot von B nach der Bindung {we:.1f} Grad neben dem Lot von A (Grenze {LOT_VP_GRAD} Grad; GPS-Lage {wg:.1f}) - Wand-Lot falsch")


def kamera_lot_probe(bilder, modell_b, ursprung, erg, mj):
    """Beide Lot-Tore am echten Teil B (pycolmap, Fotos, DGM1). Wird nach binden() gerufen (nur bei ok). -> dict(kamerahoehe, fluchtpunkt, ok, grund, lage_unbrauchbar_namen)."""
    import pycolmap
    from schwerkraft_je_bild import lot_welt
    from seiten_gps_vereinen import gps_roh
    import kamerahoehe_dgm as KD
    ua = np.asarray(erg["pruefung"]["lot_a"], float); Mg, Mk, M = (np.asarray(erg[k], float) for k in ("B_nach_A_gps", "B_nach_A_kipp", "B_nach_A"))
    r = pycolmap.Reconstruction(modell_b); ims = [im for im in r.images.values() if im.has_pose]; namen = [im.name for im in ims]
    C = np.array([im.projection_center() for im in ims]); aus = {}
    try:
        roh = gps_roh(bilder, namen); k = [i for i, n in enumerate(namen) if n in roh]
        if ursprung is None or len(k) < KD.MIN_KAMERAS: aus["kamerahoehe"] = dict(ok=None, hinweise=[f"{len(k)} B-Kameras mit Geotag / Ursprung {ursprung} - nicht messbar"])
        else:
            he, _ = KD.erwartete_hoehen([roh[namen[i]] for i in k], ursprung); kh = kamerahoehe_pruefen(C[k], he, Mg, Mk, M, ua, mj)
            kh["lage_unbrauchbar_namen"] = [namen[k[j]] for j in kh["lage_unbrauchbar"]]; aus["kamerahoehe"] = kh
    except Exception as ex: aus["kamerahoehe"] = dict(ok=None, hinweise=[f"DGM-Probe nicht moeglich ({type(ex).__name__}: {ex})"])
    try:
        ks = [dict(name=im.name, R=im.cam_from_world().rotation.matrix(), f=r.cameras[im.camera_id].mean_focal_length(), cx=r.cameras[im.camera_id].principal_point_x,
                   cy=r.cameras[im.camera_id].principal_point_y, breite=r.cameras[im.camera_id].width, hoehe=r.cameras[im.camera_id].height) for im in ims]
        vp = lot_welt(ks, bilder, n_max=200); aus["fluchtpunkt"] = dict(lot_vp_pruefen(vp["oben"] if vp else None, Mg, M, ua), bilder=(vp or {}).get("getragen"))
    except Exception as ex: aus["fluchtpunkt"] = dict(ok=None, grund=f"Fluchtpunkt-Lot nicht moeglich ({type(ex).__name__}: {ex})")
    gr = list(aus["kamerahoehe"].get("gruende") or []) + ([aus["fluchtpunkt"]["grund"]] if aus["fluchtpunkt"].get("ok") is False else [])
    aus.update(ok=not gr, grund="; ".join(gr)); return aus


def gps_probe(bilder, modell_a, modell_b, M_neu, M_gps, mitte_b=None):
    """GEOTAGS VON B als Gegenprobe: A-Rahmen Modell -> ENU (seiten_gps_vereinen.rahmen, A hat Hunderte Geotags), B-Kameras ueber M_neu bzw. M_gps in A und weiter nach
    ENU; waagerechter Abstand zu den eigenen Geotags von B (Median, und Anteil < GRENZE_M). -> dict oder None (zu wenig GPS)."""
    import seiten_gps_vereinen as SG
    A = SG.kameras(modell_a); B = SG.kameras(modell_b); roh = SG.gps_roh(bilder, A[0] + B[0])
    if len(roh) < 2 * SG.MIN_GPS: return None
    la0, lo0 = np.median([v[0] for v in roh.values()]), np.median([v[1] for v in roh.values()]); G = SG.enu(roh, la0, lo0); FA = SG.rahmen(*A, G)
    if "M" not in FA: return None
    k = [i for i, n in enumerate(B[0]) if n in G and np.linalg.norm(G[n]) < SG.RADIUS_M]
    if len(k) < SG.MIN_GPS // 2: return None
    Y = np.array([G[B[0][i]] for i in k]); C = B[1][k]; aus = dict(n_gps_b=len(k))
    for name, M in (("gps", M_gps), ("neu", M_neu)):
        d = np.linalg.norm(anwenden(FA["M"] @ M, C)[:, :2] - Y, axis=1); aus[name] = dict(median_m=round(float(np.median(d)), 2), anteil_unter_grenze=round(float((d < SG.GRENZE_M).mean()), 3))
    if mitte_b is not None:                                                             # 24.11.2026 (Nutzer "Ja, Hebel einrechnen"): Hebel der geotaggten B-Kameras um den Skalierungsmittelpunkt, ENU-Meter
        P = anwenden(FA["M"] @ M_neu, np.asarray(mitte_b, float)[None])[0]
        aus["hebel_kameras_m"] = round(float(np.median(np.linalg.norm(anwenden(FA["M"] @ M_neu, C)[:, :2] - P[:2], axis=1))), 2)
    return aus


def gps_urteil(gp, mass_sd=None):
    """Ergebnis von gps_probe -> Ablehnungsgrund (str) oder '' (bestanden). Ohne Probe (keine Geotags) = Ablehnung: dann waere die Lage nur von den Waenden getragen."""
    if not gp: return "Geotags von B nicht pruefbar (keine Gegenprobe)"
    gr = []
    # 24.11.2026 (Nutzer "Ja, Hebel einrechnen"): ist der Massstab aus den Waenden uebernommen, verschiebt er die B-Kameras um (Massstabfehler x Hebel).
    # Die Grenze darf dann die ehrliche GPS-Massstabsstreuung am Kamerahebel einrechnen: max(GPS_MEHR_M, mass_sd x Hebel). 1122y: 0,164 x ~24 m = 3,9 m statt 3,0 m.
    mehr = GPS_MEHR_M
    if mass_sd and gp.get("hebel_kameras_m"): mehr = max(GPS_MEHR_M, round(float(mass_sd) * gp["hebel_kameras_m"], 2))
    gp["grenze_mehr_m"] = mehr
    if gp["neu"]["median_m"] > gp["gps"]["median_m"] + mehr: gr.append(f"Geotags von B im Median {gp['gps']['median_m']} -> {gp['neu']['median_m']} m (hoechstens +{mehr} m)")
    if gp["neu"]["anteil_unter_grenze"] < GPS_ANTEIL_MIN: gr.append(f"nur {100 * gp['neu']['anteil_unter_grenze']:.0f} % der Geotags von B unter 12 m (noetig {100 * GPS_ANTEIL_MIN:.0f} %)")
    return "; ".join(gr)


def kontrollbild(pfad, A2, B2, Q, wa, wb, tr, dz, pr, gr):
    """Grundriss vorher (B in GPS-Lage, nur gekippt) / nachher, Ansicht der Treffer in der Hoehe. A blau, B rot."""
    import cv2
    W = 700; c = np.median(Q, 0); r = max(8.0, float(np.percentile(np.linalg.norm(Q - c, axis=1), 98)) + 3.0); sk = W / (2 * r)
    def grund(P_b, titel):
        im = np.full((W, W, 3), 255, np.uint8)
        for P, col in ((A2, (200, 120, 0)), (P_b, (0, 0, 220))):
            x = (W / 2 + (P[:, 0] - c[0]) * sk).astype(int); y = (W / 2 - (P[:, 1] - c[1]) * sk).astype(int); ok = (x >= 0) & (x < W) & (y >= 0) & (y < W)
            for dx, dy in ((0, 0), (1, 0), (0, 1)): im[np.clip(y[ok] + dy, 0, W - 1), np.clip(x[ok] + dx, 0, W - 1)] = col
        cv2.line(im, (10, W - 15), (10 + int(5 * sk), W - 15), (0, 0, 0), 2); cv2.putText(im, "5 m", (12, W - 22), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 1)
        cv2.putText(im, titel, (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 1); return im
    a = grund(B2, f"VORHER GPS-Lage (gekippt), Abstand {pr['wandabstand_median_m']['gps']:.2f} m"); b = grund(Q, f"NACHHER, Abstand {pr['wandabstand_median_m']['nach']:.2f} m, Treffer {100 * pr['treffer']:.0f} %")
    im = np.hstack([a, b]); cv2.putText(im, ("GEBUNDEN" if not gr else "ABGELEHNT: " + "; ".join(gr))[:150], (8, 45), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 160) if gr else (0, 120, 0), 1)
    ms_, dp_ = pr.get("massstab") or {}, pr.get("doppelwand") or {}
    if ms_: cv2.putText(im, f"Massstab Waende {ms_['gegen_gps']:.3f} x GPS ({'uebernommen' if ms_['uebernommen'] else 'nicht: ' + '; '.join(ms_['gruende'])}), Hebel {ms_['hebel_m']:.1f} m; "
                            f"Doppelwand starr {sum(x['n'] for x in dp_.get('starr', []))} / nachher {sum(x['n'] for x in dp_.get('nachher', []))} Pkt", (8, 65), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 0, 0), 1)
    cv2.imwrite(pfad, im)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0]); ap.add_argument("dicht_a"); ap.add_argument("dicht_b"); ap.add_argument("--gps", required=True); ap.add_argument("--aus", required=True)
    ap.add_argument("--modell-a"); ap.add_argument("--modell-b"); ap.add_argument("--bilder"); a = ap.parse_args(argv)
    os.makedirs(a.aus, exist_ok=True); wj = os.path.join(a.aus, "waende.json")
    def ende(erg, rc):
        erg.update(dicht_a=os.path.abspath(a.dicht_a), dicht_b=os.path.abspath(a.dicht_b), gps=os.path.abspath(a.gps)); json.dump(erg, open(wj, "w"), indent=1, ensure_ascii=False)
        print(json.dumps(erg.get("pruefung"), ensure_ascii=False)[:1500]); print(("WAENDE GEBUNDEN: " if erg.get("ok") else "WAENDE NICHT UEBERNOMMEN: ") + erg["urteil"]); return rc
    try:
        vj = json.load(open(a.gps)); G = gps_unsicherheit(vj); p_ = vj.get("pruefung") or {}
        if isinstance(G, dict): G.update(dreh_sd_ehrlich=p_.get("dreh_sd_ehrlich_grad"), mass_sd_ehrlich=p_.get("mass_sd_ehrlich_rel"))
    except Exception as ex: G = f"GPS-Ergebnis nicht lesbar ({type(ex).__name__})"
    if isinstance(G, str): return ende(dict(art="waende", ok=False, zu_wenig=True, urteil="keine GPS-Lage als Start/Veto: " + G), 2)
    if not (os.path.isfile(a.dicht_a) and os.path.isfile(a.dicht_b)): return ende(dict(art="waende", ok=False, zu_wenig=True, urteil="dichte Wolke eines Teils fehlt"), 2)
    DA = ply_lesen(a.dicht_a); DB = ply_lesen(a.dicht_b); lot0 = None; ref_b = None
    if a.modell_a and a.modell_b:
        try:
            import pycolmap
            from seiten_gps_vereinen import lot_aus_bild_achsen
            ra_, rb_ = pycolmap.Reconstruction(a.modell_a), pycolmap.Reconstruction(a.modell_b)
            lot0 = lot_aus_bild_achsen([im.cam_from_world().rotation.matrix() for im in ra_.images.values() if im.has_pose])
            ref_b = np.array([im.projection_center() for im in rb_.images.values() if im.has_pose])
        except Exception as ex: print(f"Modelle nicht lesbar ({type(ex).__name__}: {ex}) - Lot aus dem GPS-Rahmen, Bezug B-Wolke")
    if lot0 is None:                                                                   # Rueckfall: Lot = Hauptachse kleinster Streuung der A-Wolke waere unsicher -> Wand-Lot ab z-Achse von A
        lot0 = np.array([0, 0, 1.0])
    if ref_b is None: ref_b = DB[::max(1, len(DB) // 2000)]
    erg = binden(DA, DB, G, lot0, ref_b, bild=os.path.join(a.aus, "waende.jpg")); erg["bild"] = os.path.join(a.aus, "waende.jpg")
    def ablehnen(grund, art):
        erg.update(ok=False, urteil="ABGELEHNT: " + grund + " - GPS-Lage bleibt"); erg.pop("B_nach_A", None)
        try:                                                                           # Kontrollbild entstand vor dieser Probe ("GEBUNDEN") -> Ablehnung nachtragen
            import cv2
            im = cv2.imread(erg["bild"]); cv2.rectangle(im, (0, 30), (690, 50), (255, 255, 255), -1)
            cv2.putText(im, (f"ABGELEHNT ({art}): " + grund)[:110], (8, 45), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 160), 1); cv2.imwrite(erg["bild"], im)
        except Exception: pass
    # LOT-TORE NACH DER KIPPUNG (24.11.2026, 1122zb): Kamerahoehen gegen DGM1 (Kippung allein / Endlage) + Fluchtpunkt-Lot der B-Fotos. Schalter RCPARK_WAENDE_LOT_TOR=0 = nur Bericht.
    if erg.get("ok") and a.bilder and a.modell_b and os.path.isdir(a.bilder):
        try: kl = kamera_lot_probe(a.bilder, a.modell_b, vj.get("ursprung_wgs84"), erg, G["m_je_einheit"])
        except Exception as ex: kl = dict(ok=None, grund=f"Lot-Probe nicht moeglich ({type(ex).__name__}: {ex})")
        erg["pruefung"]["lot_tore"] = kl; kh = kl.get("kamerahoehe") or {}; fp = kl.get("fluchtpunkt") or {}
        print(f"LOT-TORE: Kamerahoehe {kh.get('ok')} ({'; '.join(kh.get('gruende') or kh.get('hinweise') or [])[:300]}), Fluchtpunkt-Lot {fp.get('ok')} "
              f"(GPS-Lage {fp.get('gps_grad')} -> {fp.get('ende_grad')} Grad, {fp.get('bilder')} Bilder){'; Lage unbrauchbar: ' + str(len(kh['lage_unbrauchbar_namen'])) + ' Kameras' if kh.get('lage_unbrauchbar_namen') else ''}")
        if kl.get("ok") is False and os.environ.get("RCPARK_WAENDE_LOT_TOR", "1") != "0": ablehnen(kl["grund"], "Lot")
    if erg.get("ok"):
        gp = None
        if a.bilder and a.modell_a and a.modell_b and os.path.isdir(a.bilder):
            try: gp = gps_probe(a.bilder, a.modell_a, a.modell_b, np.asarray(erg["B_nach_A"]), np.asarray(erg["B_nach_A_gps"]),
                                      mitte_b=(erg["pruefung"].get("massstab") or {}).get("mitte_b"))
            except Exception as ex: print(f"GPS-Probe nicht moeglich ({type(ex).__name__}: {ex})")
        _ms = erg["pruefung"].get("massstab") or {}
        erg["pruefung"]["gps_probe"] = gp; gpr = gps_urteil(gp, mass_sd=(max(G.get("mass_sd") or 0.0, G.get("mass_sd_ehrlich") or 0.0) if isinstance(G, dict) and _ms.get("uebernommen") else None))
        if gpr: ablehnen(gpr, "Geotags")
        else:
            erg["urteil"] += f"; Geotags von B Median {gp['gps']['median_m']} -> {gp['neu']['median_m']} m"
            kh = ((erg["pruefung"].get("lot_tore") or {}).get("kamerahoehe") or {}); fp = ((erg["pruefung"].get("lot_tore") or {}).get("fluchtpunkt") or {})
            if fp.get("ok"): erg["urteil"] += f"; Fluchtpunkt-Lot {fp['gps_grad']} -> {fp['ende_grad']} Grad"
            if kh.get("ok") is not None:
                erg["urteil"] += f"; Kamerahoehe/DGM Steigung {kh['gps'].get('steigung')} -> {kh['kipp'].get('steigung')} (Kippung) -> {kh['ende'].get('steigung')} (Endlage)"
                if kh.get("lage_unbrauchbar_namen"):
                    from kamerahoehe_dgm import REST_MAX_M
                    erg["urteil"] += f", {len(kh['lage_unbrauchbar_namen'])} Kameras Lage unbrauchbar (Rest > {REST_MAX_M:.0f} m)"
    return ende(erg, 0 if erg["ok"] else (2 if erg.get("zu_wenig") else 3))


if __name__ == "__main__": sys.exit(main())
