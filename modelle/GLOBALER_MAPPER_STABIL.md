# Globaler Mapper stabil machen - Versuchsprotokoll und Rezept (ab 19.11.2026)

Auftrag (Nutzer 19.11.): Methode entwickeln, mit der `colmap global_mapper` (GLOMAP-Kern in COLMAP 4.3.dev, eigener CUDA-Bau
`/media/oem/scan/colmap-build/prefix/bin/colmap`) ein stabiles Modell liefert; bekannte Fehler (Kameras 10 m zu hoch am Schwabentor 13.11.,
Martinstor gk3: GPS-Rest 70 m) durch Stufen mit bekannter Brennweite oder andere Methoden loesen, bis zum Boden (zwei Ideen ohne Gewinn).

Werkzeuge dieser Runde (alle generisch, Python `/media/oem/scan/venv-colmap/bin/python -I`):
- `tools/sfm_db_variante.py` - DB-Kopie vorbereiten: Prioren loeschen/aus EXIF sauber setzen, Kamera je Videoclip, Bilder loeschen (Regex), Bildliste.
- `tools/global_mapper_lauf.py` - ein Versuch: view_graph_calibrator -> global_mapper -> Bewertung, Zeiten, Protokollzeile.
- `tools/mapper_bewerten.py` - EINE Kennzahlenliste fuer alle Varianten (siehe unten), haengt JSON-Zeile an `versuche.jsonl`.
Arbeitsdaten: `/media/oem/rcdaten/tmp/globmap/` (DB-Kopien `db_*.db`, Modelle `sparse_*`, `logs/`, `versuche.jsonl`); Schwabentor-Gegenprobe in `.../globmap/schwab/`.
Quelle Martinstor: `/media/oem/scan/rc-park_daten/martinstor_gk3/pipe/sfm/db.db` (nur gelesen, Backup per sqlite-Backup-API, Lauf rcpark-mt_gk3 nicht beruehrt).

## Kennzahlen (immer gleich)
n_modelle (Teilmodelle), n_reg (Bilder im groessten), reproj_px (mittlerer Reprojektionsfehler), spur (mittlere Spurlaenge),
GPS: n_gps / gps_median_m / Anteil > 15 m (robuste 2D-Aehnlichkeit Kamerakern -> Foto-GPS wie `mapper_gps_vergleich.py --alle`; 30-40 % falsche Geotags,
nur Mehrheit zaehlt; Tor der Kette: <= 15 %), hoehe_p90_m (Kamera-Abstand von der Ebene durch den Kamerakern in m, Massstab aus dem GPS-Fit;
ANNAHME ebenes Strassenniveau), luecke_grad / sektoren_leer (kamera_abdeckung.py), f_unplausibel (f/Breite ausserhalb 0,3..12, Regel kamera_plausibel.py),
kameras_fern (> 20 x Medianabstand vom Kamerakern = 'zum Mond'), clip_f_cv_median (Brennweiten-Streuung je Videoclip), sek (Laufzeit).

## Befunde vor dem ersten Versuch (19.11. 00:10-00:25)
1. **EXIF-Prioren sind Gift:** von 1032 Kameras haben 47 einen EXIF-Prior (source=3); davon tragen 11 Canon-PowerShot-Bilder f = 0,87-8,7 Mio px
   (pycolmap 4.2.1 rechnet FocalPlaneXResolution falsch) und ~15 Pentax/Ricoh-Zuschnitte eine Brennweite aus der Zuschnitt-Diagonale (Faktor ~2 zu klein).
   Der `view_graph_calibrator` optimiert Kameras mit Prior NICHT (`SetParameterBlockConstant`, view_graph_calibration.cc:249) und das Tor
   `max_focal_length_ratio` greift nur fuer Kameras ohne Prior -> die falschen Werte gehen 1:1 in den Mapper. Im V0-Modell stehen 14 der 45 'fernen'
   Kameras genau auf diesen Bildern (f/Breite bis 2666). 38 der 47 Prior-Bilder sind registriert, d.h. sie verbiegen das Modell mit.
2. Nur 55 von 286 Fotos haben ueberhaupt eine EXIF-Brennweite, 231 keine (Wikimedia/Mapillary/Web); 32 Fotos haben GPS. 'Fotos bekannter Brennweite'
   sind also eine kleine Menge (24 sauber herleitbar, siehe `--priors exif`).
3. 12 Mapillary-Panoramen (`mapillary_neu__sv_NN_360.jpg`, equirektangular) stecken in der DB - kein Lochkameramodell, eins davon 'fern' (f/Breite 4424).
   89 Bilder sind 1024-px-Vorschauen (`fotos_eingang__vorschau__*`), drei davon fern mit f/Breite 0,01-1,5.
4. Freie Brennweite im Buendelausgleich (`ba_refine_focal_length 1`, eine Kamera je Bild) laeuft bei einseitigen Kameras weg: 32 registrierte Kameras mit
   f/Breite ausserhalb 0,3..12, auch ohne Prior (z.B. eigen__132 f/Breite 578).
5. Videobilder: 746 aus 17 Clips, je Clip gleiche Bildgroesse -> Kamera je Clip moeglich (`--kamera-je-clip`: 303 statt 1032 Kameras).
6. Globaler Mapper kennt KEINE Positions-Prioren (Quelltext: pose_priors nur im Rotationsmittel `ra_use_gravity`; global_positioning ohne Prior,
   TODO-Kommentare in global_mapper.cc:365). Keine Option, vorhandene Posen als Start zu uebernehmen (kein input_path). Einhaengen weiterer Bilder nur
   ueber `image_registrator` (+ `point_triangulator`, `bundle_adjuster`), d.h. zweistufig ist moeglich, aber nicht innerhalb des globalen Mappers.
7. Laufzeit/GPU: Kalibrator rechnet rein CPU (Ceres), Mapper nutzt GPU fuer globales Positionieren und Buendelausgleich. Schrittweiser Mapper (rcpark-mt_gk3)
   hatte MemoryPeak 9,6 GB - RAM-Buchung begrenzt parallele Versuche auf ~2 GB (Rest der 85 %).

## Versuche (Tabelle wird fortgeschrieben; Rohdaten `versuche.jsonl`)
| Nr | Variante | Bilder | n_mod | n_reg | reproj | GPS n / Median m / >15 m | fern | f_unpl | Luecke | sek |
|----|----------|--------|-------|-------|--------|---------------------------|------|--------|--------|-----|
| V0 | Standard (15.11.-Rezept): Kalibrator + Mapper, Kamera je Bild, Prioren wie von pycolmap | 1032 | 6 | 894 | 0,82 | 24 / 69,5 / 88 % (Kern 15: 41 m / 67 %) | 45 | 32 | 41 Grad | 1140 |
| F0 | wie V0, nur Fotos (image_list_path) | 286 | 2 | 231 | 0,95 | 24 / 181 / 100 % (Kern 34 m / 93 %) | 20 | 26 | 137 | 393 |
| F1 | nur Fotos, alle Prioren geloescht (GUESS) | 286 | 3 | 230 | 1,28 | 23 / 66 / 96 % (Kern 53 m / 100 %), Hoehe p90 13,7 m | 13 | 19 | 100 | 347 |
| F2 | nur Fotos, 24 saubere EXIF-Prioren, Rest GUESS | 286 | 3 | 230 | 0,93 | 23 / 64 / 83 % (Kern 54 m / 100 %) | 5 | 9 | 205 | 387 |
| V4b | alle Prioren weg, Kamera je Clip (291 Kameras), 12 Panoramen raus | 1020 | 4 | 881 | 0,89 | 23 / 68 / 100 % (Kern 49 m / 87 %), Hoehe p90 12,9 m | 17 | 17 | 37 | 2002 (ausgelagert; GP 1388 s statt 90) |
|     | V4b gegen V0: 881 gemeinsame Bilder, Kern deckungsgleich (517 Inlier), Rotation Median 0,8 Grad, aber 36 % der Kameras > 2 Grad anders | | | | | | | | | |
| V5 | wie V4b + AnyCalib-Prior je Bild (1002/1020 kalibriert, 288/291 Kameras) | 1020 | 4 | 881 | 0,88 | Kern 39 m / 87 % (Tor unbrauchbar, s.u.) | 10 | 10 | 34 | 2044 (ausgelagert) |
|    | V5 gegen V4b: Lage-Median 2 % Kernradius, 32 % der Kameras > 10 %; Rotation Median 0,35 Grad, 33 % > 2 Grad | | | | | | | | | |
| V6 | wie V5, Brennweiten im BA FEST (AnyCalib) | 1020 | 6 | 881 | 1,07 | Kern 52 m / 100 % (Tor unbrauchbar) | 1 | 0 | 70 | 723 (6 GB Buchung, keine Auslagerung) |
|    | V6 gegen V5: 50 % > 10 % Kernradius, Rotation 31 % > 2 Grad; Plausibilitaet perfekt, Geometrie anders - am Schwabentor (S4) nachweislich schlechter -> verworfen | | | | | | | | | |
| V7a | Stufe 1 zweistufig: globaler Mapper NUR Videobilder (746, AnyCalib-Prior, Kamera je Clip) | 746 | 5 | 612 | 0,87 | kein GPS (Video) | 0 | 0 | 73 | 896 |
|    | V7a gegen V5 (612 gemeinsame): Median 0,4 % Kernradius, 7 % > 10 %, Rotation 6 % > 2 Grad -> Videorueckgrat reproduziert sich; ohne Fotos aber 5 Teilmodelle (Fotos verbinden Clips) | | | | | | | | | |
| V7b | Stufe 2: Fotos per image_registrator + point_triangulator + bundle_adjuster (GPU) in V7a | 1020 | 1 | 753 | 0,81 | 14 / 41 m / 86 % (Kern 7: 11,9 m / 43 %), Hoehe p90 27,5 m | 4 | 3 | 93 | 1359 (Stufe 2: 463 s) |
|    | Rueckgrat bleibt unveraendert (gegen V7a 0,1 % / Rotation 0,02 Grad); nur 138 von 274 Fotos eingehaengt (V5: 220); gegen V5 gesamt 17 % > 10 %, Rotation 13 % > 2 Grad -> stabiler als V5/V4b/V6 untereinander (32-50 %), Preis: weniger Fotos | | | | | | | | | |
| V5s2 | wie V5, seed 2 (Reproduzierbarkeit Martinstor) | 1020 | 4 | 881 | 0,82 | Kern 47 m / 100 % (Tor unbrauchbar) | 12 | 8 | 52 | ~900 |
|    | V5s2 gegen V5: 27 % > 10 % Kernradius, Rotation 25 % > 2 Grad -> Laufrauschen wie am Schwabentor; Konsens-Schnitt: 630 stabil, 251 unstabil (28 %) -> Stufe 2 V8 | | | | | | | | | |
| S0 | Schwabentor Standard (Kalibrator + Mapper, wie 15.11.) | 504 | 1 | 493 | 1,19 | 193 / 4,9 m / 11 % (Kern 178: 3,5 m / 4 %), Hoehe p90 7,1 m | 14 | 14 | 25 | 636 (2 GB, ausgelagert) |
| S2 | Schwabentor ohne Prioren, Kamera je Clip (8 Clips) | 504 | 1 | 495 | 1,33 | 195 / 4,9 m / 12 % (Kern 180: 3,4 m / 6 %), Hoehe p90 5,0 m | 12 | 17 | 126 | 542 |
|    | S2 gegen S0: 37 % der Kameras > 10 % Kernradius, 16 % > 5 m, Rotation 21 % > 2 Grad; stabil: eigene Handyfotos (19 %), instabil: Commons-Fotos 60 % (f 30 % anders), Clip LMS3 51 %, Abstand 2-4 Kernradien 71 %, > 4 100 % | | | | | | | | | |
| S4 | Schwabentor AnyCalib-Prior (504/504) + Kamera je Clip + Brennweiten im BA FEST | 504 | 1 | 496 | 1,92 | 195 / 7,5 m / 30 % (Kern 6,8 m / 25 %) - SCHLECHTER | 4 | 0 | 39 | 498 (Kalibrator 1 s = uebersprungen, alle Kameras hatten Prior) |
|    | S4 gegen S0: 47 % > 10 % Kernradius, 43 % > 5 m, Rotation Median 2,0 Grad -> feste AnyCalib-Brennweite (ca. 6 % Fehler) verbiegt das Modell; nur als Prior brauchbar, nicht als Festwert | | | | | | | | | |
| S3 | Schwabentor AnyCalib-Prior + Kamera je Clip, Brennweite im BA frei | 504 | 1 | 496 | 1,31 | 195 / 6,9 m / 29 % (Kern 5,9 m / 25 %) - SCHLECHTER als S0 | 11 | 9 | 155 | 641 |
|    | Ursache: mit Prior an JEDER Kamera tut der view_graph_calibrator nichts mehr (1 s, 0 Paare neu geschaetzt) - die Kalibrierung aus den Paaren ist besser als AnyCalib. Folgeversuch S5: AnyCalib nur als Startwert (Quelle wieder GUESS) | | | | | | | | | |
| S6 | Schwabentor wie S2 + `ra_reweighting INLIER_MATCH_COUNT` | 504 | 1 | 494 | 1,15 | 194 / 5,0 m / 11 % (Kern 3,6 m / 5 %), Hoehe p90 5,9 m | 11 | 14 | 26 | 410 |
|    | S6 gegen S0: nur 13 % > 10 % Kernradius, 10 % > 5 m, Rotation 9 % > 2 Grad (S2 gegen S0: 37 / 16 / 21 %) -> naeher an S0; ob das Stabilitaet oder Zufall ist, klaert S2r (seed 2) | | | | | | | | | |
| S5 | Schwabentor AnyCalib nur als STARTWERT (Quelle GUESS, Kalibrator optimiert; 10 verworfen) + Kamera je Clip | 504 | 1 | 493 | 1,21 | 193 / 4,9 m / 10 % (Kern 3,4 m / 4 %) | 10 | 12 | 52 | 558 |
|    | S5 gegen S0: 14 % > 10 % Kernradius, Rotation 11 % > 2 Grad (wie S6) | | | | | | | | | |
| S2r | Schwabentor wie S2, seed 2 (REPRODUZIERBARKEIT) | 504 | 1 | 495 | 1,30 | 195 / 4,9 m / 12 % (Kern 3,6 m / 6 %) | 11 | 16 | 36 | 493 |
|    | **S2r gegen S2 (gleiche Eingabe, nur anderer Zufalls-Startwert): 38 % der Kameras > 10 % Kernradius, 27 % > 5 m, Rotation 30 % > 2 Grad.** Das ist das Rauschen des globalen Mappers selbst; alle Variantenunterschiede (13-50 %) liegen in dieser Groessenordnung. GPS-Tor dagegen stabil 10-12 % | | | | | | | | | |
| S2d | Schwabentor wie S2, seed 1 WIEDERHOLT | 504 | 1 | 493 | 1,38 | 193 / 4,9 m / 12 % (Kern 3,5 m / 6 %) | 11 | 13 | 125 | 467 |
|    | **S2d gegen S2 (gleicher Seed, gleiche Eingabe): 36 % > 10 % Kernradius, 20 % > 5 m** -> der globale Mapper ist auch mit festem Seed NICHT deterministisch (Mehrthread/GPU); Seed hilft nicht | | | | | | | | | |
| S7 | Schwabentor wie S2 + `ba_num_iterations 6` | 504 | 1 | 494 | 1,19 | 194 / 5,0 m / 12 % (Kern 3,6 m / 6 %) | 12 | 18 | 41 | 540 |
|    | S7 gegen S2: 37 % > 10 % - mehr BA-Runden aendern nichts am Rauschen; GPS-Tor unveraendert | | | | | | | | | |
|    | **Boden fuer Parameter am Schwabentor:** S0/S2/S2r/S2d/S5/S6/S7 alle 10-12 % GPS-Tor (Kern 4-6 %); S3/S4 (AnyCalib-Prior) 29-30 %. Zwei Ideen ohne Gewinn (S6 Gewichtung, S7 BA-Runden) -> Parametersuche beendet. Rest-Problem = Laufrauschen 36-39 % der Kameras (Peripherie) | | | | | | | | | |
|    | Konsens-Schnitt (`tools/sfm_stabil_schnitt.py`): S2/S2r -> 303 stabil (39 % raus); S2d/S7 -> 402 stabil (18 % raus). Stufe 2 S8/S8b: `colmap mapper --input_path stabil --Mapper.fix_existing_frames 1` haengt die unstabilen gegen das feste Rueckgrat ein | | | | | | | | | |
| S8b | **Konsens** Schwabentor: Rueckgrat S2d/S7 (402) + Stufe 2 `mapper --fix_existing_frames 1` (58 von 91 unstabilen wieder eingehaengt) | 504 | 1 | 460 | 1,06 | 181 / 4,7 m / **9 %** (Kern 167: 3,3 m / **2 %**), Hoehe p90 **0,9 m** | **0** | **0** | 64 | 467+540+~300 |
|    | S8b gegen S2d: 8 % > 10 % Kernradius, Rotation 5 % > 2 Grad. Bestes Schwabentor-Ergebnis in allen Kennzahlen; Preis: 33 Bilder (7 %) fehlen (lieber fehlen als falsch) | | | | | | | | | |
| S8 | Konsens Schwabentor: Rueckgrat S2/S2r (303) + Stufe 2 Standard (160 von 192 wieder eingehaengt) | 504 | 1 | 463 | 1,05 | 178 / 5,9 m / 24 % (Kern 5,4 m / 19 %) - schlechter als S8b | 13 | 4 | 132 | |
|    | **Die beiden Rueckgrate (303 bzw. 402 Kameras aus unabhaengigen Paaren) sind deckungsgleich: 285 gemeinsame, 0 % > 10 % Kernradius, Rotation 1 % > 2 Grad, GPS-Tor 5 % / Kern 2 %, 0 fern.** Alle 13 fernen Kameras in S8 stammen aus Stufe 2 (Standard-Schwellen 30 Inlier / 0,25, strukturloser Rueckfall) -> Stufe 2 muss streng sein: S8c (abs_pose_min_num_inliers 100, Ratio 0,5), S8d (zusaetzlich ohne structure_less_registration_fallback) | | | | | | | | | |
| S8c | wie S8, Stufe 2 streng (abs_pose_min_num_inliers 100, Ratio 0,5), Rueckfall an | 504 | 1 | 405 | 1,09 | 165 / 5,4 m / 20 % (Kern 13 %) | 11 | 1 | | |
| S8d | wie S8c + `structure_less_registration_fallback 0` | 504 | 1 | 365 | 1,06 | 148 / 5,4 m / 12 % (Kern 5,1 m / 3 %), Hoehe p90 2,5 m | **0** | **0** | | |
|    | -> Die fernen Kameras kommen aus dem strukturlosen Rueckfall der Registrierung (generalisierte Relativpose), nicht aus zu lockeren Inlier-Schwellen. S8e prueft: Rueckfall aus, Schwellen Standard | | | | | | | | | |
| V8 | **Konsens Martinstor**: Rueckgrat V5/V5s2 (630) + Stufe 2 Standard (200 von 251 eingehaengt) | 1020 | 1 | 830 | 0,80 | Kern 10: 41 m / 100 % (Tor unbrauchbar), Hoehe p90 9,7 m | 1 (aus Stufe 2) | 1 | 69 | ~1300 |
|    | V8 gegen V5: 23 % > 10 % Kernradius (= die neu eingehaengten); Rueckgrat unveraendert. V8b: Stufe 2 ohne Rueckfall | | | | | | | | | |
| S8e | wie S8, Stufe 2 Standard-Schwellen, aber `structure_less_registration_fallback 0` (159 von 192 eingehaengt) | 504 | 1 | 462 | 1,01 | 177 / **3,7 m / 10 %** (Kern 3,4 m / **2 %**), Hoehe p90 2,5 m | **0** | **0** | | ~300 |
|    | S8e gegen S8b (zwei unabhaengige Rezept-Ergebnisse): Median 0,1 m, 17 % > 5 m (Rohlaeufe S2/S2r: 27 %; mit Rueckfall S8/S8b: 31 %), Rotation 14 % > 2 Grad (30 %). Kernradius 24 m, 10 % = 2,4 m = GPS-Rauschen | | | | | | | | | |
| V8b | Martinstor Konsens, Stufe 2 ohne Rueckfall (196 von 251 eingehaengt) | 1020 | 1 | 826 | 0,81 | Tor unbrauchbar | **0** | **0** | | |
|    | V8b gegen V8: 8 % > 10 % (nur die Rueckfall-Kameras); Rueckgrat 630 unveraendert. **Stufe-2-Boden:** strenge Inlier-Schwellen (S8c) bringen nichts, Rueckfall aus (S8d/S8e) beseitigt alle fernen Kameras | | | | | | | | | |
| SK | **Rezept komplett** (`global_mapper_konsens.py`) Schwabentor ab Roh-DB: Schnitt 440/492 stabil (11 %), Stufe 2 ohne Rueckfall | 504 | 1 | 466 | 1,03 | 187 / 5,0 m / **9 %** (Kern 3,2 m / **3 %**), Hoehe p90 **1,0 m** | **0** | **0** | 73 | 1152 (2 Laeufe 416+331 s, Stufe 2 400 s) |
|    | SK gegen S8e (unabhaengiges Rezept-Ergebnis): Median 0,1 m, 25 % > 5 m, Rotation 16 % > 2 Grad. Draufsicht `draufsicht_SK_schwabentor.png`: alle Kameras in einer Ebene, eigene Fotos im Ring um den Turm, Video entlang der Strassen - keine Kamera in der Luft | | | | | | | | | |
| MK | **Rezept komplett** Martinstor ab Roh-DB: Schnitt 588/881 stabil (33 %), Stufe 2 ohne Rueckfall (224 von 293 eingehaengt) | 1032 | 1 | 812 | 0,76 | Tor unbrauchbar | 1 (eigen__137, echtes Fernfoto 370 m) | **0** | 73 | 3203 (2 Laeufe 875+739 s, Stufe 2 1580 s bei zwei parallelen Jobs) |
|    | MK gegen V8b: 17 % > 5 m, Rotation 19 % > 2 Grad (Rohlaeufe V5/V5s2: 27 % / 25 %) | | | | | | | | | |
|    | **Fazit Reproduzierbarkeit:** Das Rezept macht Plausibilitaet (0 ferne/unplausible Kameras, Kameras in einer Ebene) und den Kern (GPS 2-3 %) reproduzierbar; die Peripherie (Fern-/Webfotos, 17-25 % der Kameras > 5 m zwischen unabhaengigen Durchlaeufen) bleibt datenbedingt unsicher - `unstabil.txt` je Lauf benennt sie | | | | | | | | | |
- 02:27 **cameras-Tabelle in COLMAP 4.3 hat eine Zeile je (camera_id, source):** AnyCalib legt source=4 neben source=2; 'UPDATE source=2' verletzt den Schluessel.
  `--svc-als-start` kopiert jetzt Parameter der SINGLE_VIEW-Zeile in die GUESS-Zeile und loescht die Prior-Zeile.

## Sackgassen / Lehren (laufend)
- 00:50 **Kalibrator verbraucht die DB:** `view_graph_calibrator` schreibt Brennweiten (source VIEW_GRAPH) und neu geschaetzte Zweibild-Geometrien in die Datei.
  Zweiter Lauf auf derselben Datei kalibriert nichts mehr (Prior gilt als fest) und sieht nur noch 13134 statt 26880 Paare. Lauf gm_a_v1 deshalb abgebrochen;
  `global_mapper_lauf.py` kopiert die DB seither selbst (`<ziel>/db_kalib.db`).
- 00:35 **Kamera je Clip braucht Rig-Pflege:** COLMAP-4.x-DB haelt je Bild frame_data(sensor_id) + frames(rig_id) + rigs; nur images.camera_id umzuhaengen ergibt
  Absturz `Camera 466 from rig 466 not found`. `sfm_db_variante.py` zieht frame_data/frames mit und loescht verwaiste Rigs (geprueft: 0 Widersprueche).
- 00:40 **AnyCalib (single_view_calibrator) laeuft nur mit CUDA-12-Bibliotheken:** der ONNX-CUDA-Provider der COLMAP-Binary verlangt libcudart/libcublas.so.12
  (Toolkit hier CUDA 13); gefunden in `/usr/local/lib/ollama/cuda_v12`, cuDNN 9 aus venv-seg. Modell 1x heruntergeladen (3,5 min) nach `~/.cache/colmap/`.
  Dann 8 Bilder in 19 s (GPU). Lizenz Apache-2.0 (Code+Gewichte, Recherche 19.11.). Clip F8y3 (3840 px): f 2992-3092 px aus drei Einzelbildern (Streuung 3 %).
- 00:45 **GPS-Tor am Martinstor ist schwach:** nur 28 Fotos mit GPS, davon viele Fernfotos (Schlossberg 493 m, KaJo 300-430 m; dort Brennweite/Abstand kaum trennbar),
  11 innerhalb 50 m. Deshalb zusaetzlich Kern-GPS (<= 120 m vom GPS-Median, ANNAHME) und Modellvergleich (Lage + Rotation ueber gemeinsame Bilder) als Masse.
- 01:05 **Modellvergleich nur ueber Standorte ist bei Strassen-Kameras unbestimmt** (fast kollinear -> Drehung um die Strassenachse frei, 16 Grad Scheinfehler);
  Drehung jetzt aus den Kamerarotationen (chordaler Mittelwert), Standorte liefern Massstab/Versatz.
- 00:46 **RAM-Deckel 2 GB laesst den Vollsatz-Mapper auslagern:** neben rcpark-mt_gk3 (Buchung 11000) bleiben nur ~2000 MiB Buchung; MemoryHigh = 2 GB je Job.
  Zwei parallele Vollsatz-Laeufe (globales Positionieren, 330k Spuren) trieben die Auslagerung auf 15,2 von 16 GB (si/so 300 MB/s) -> gm_a_v1b gestoppt,
  v4b allein weiter mit Notstopp-Wache (ab 14,8 GB). Vollsatz-Laeufe brauchen > 2 GB (ANNAHME 4-6 GB); sauber erst nach Ende des schrittweisen Mappers.
- `python3 tools/regression.py` (System-Python) bricht mit `No module named 'trimesh'` ab - vor meiner Aenderung; Regression mit venv-seg-Python laufen lassen.
- 00:30 **Nur-Foto-Laeufe (286 Bilder) sind schlechter als der Vollsatz:** 231 Fotos ohne EXIF, 89 Vorschauen; Modelle mit 230 Bildern, Kern-GPS 34-54 m, zwischen
  den Varianten 18-22 % der gemeinsamen Kameras > 5 m und Rotationen 3,9 Grad auseinander. Die Videobilder sind das Rueckgrat, nicht die Last ->
  Zweistufigkeit 'Fotos bekannter Brennweite zuerst' faellt fuer dieses Objekt aus (zu wenige, 24 sauber).

## Befunde 01:50 (nach V4b, V5)
- **GPS-Tor am Martinstor ist unbrauchbar:** die GPS-Reste je Kernfoto sind in V0, V4b und V5 fast identisch (z.B. jm33958 57/57/58 m, jm12975 77/79/80 m,
  MartinsTorFr 5/5/5 m, Doppeladler 9/11/3 m). Drei verschiedene Modelle, derselbe Rest -> die Geotags sind das Problem: die Wikimedia-'jm'-Serie traegt
  offenbar den Standort des OBJEKTS (Rest = Abstand Kamera-Tor 50-80 m), nicht der Kamera. ANNAHME, aber durch die Gleichheit ueber Modelle gestuetzt.
  Folge: Tor am Martinstor durch Modellvergleich/Plausibilitaet ersetzen; echtes GPS-Tor nur am Schwabentor (188 eigene Handyfotos).
- **Wo die Instabilitaet sitzt (V5 gegen V4b, Ausrichtung ueber Kamerarotationen):** 13 von 17 Videoclips deckungsgleich (0-8 % der Kameras > 10 % Kernradius,
  Rotation < 0,3 Grad). Instabil: Fotos (eigen 75 %, fotos_eingang 93 % Lage, Brennweite je Foto > 10 % anders in 35-53 %), Clip A_PUR2GXND0 (66 %),
  Fernclip gjVSpDSd8rU (100 %, 3,9 Kernradien weit), pFa0tRoSp1U nur Rotation (2,8 Grad). Nach Abstand vom Kern: 0-1 Radien 19 % / 1-2 25 % / 2-4 63 % / > 4 94 %.
  -> Videorueckgrat ist stabil; die Einzelfotos mit freier Brennweite und die Fernkameras wandern (Brennweite/Abstand-Mehrdeutigkeit).
- 01:09 rcpark-mt_gk3 (schrittweiser Mapper) am ZEITLIMIT 10800 s der Kette abgebrochen (rc 124, bei ~600/1032 Bildern, sparse_inkr leer) ->
  kein schrittweises Vergleichsmodell. Meine zwei Vollsatz-Laeufe mit Auslagerung haben ihn zusaetzlich gebremst (ANNAHME; er lag schon vor 00:46 bei 530/1032).
- Warteschlange (rcpark-gm_kette, sequenziell): V6 = V5 + feste Brennweiten im BA (`ba_refine_focal_length 0`, `ba_refine_extra_params 0`);
  V7 = zweistufig: globaler Mapper nur Videobilder (746) -> Fotos per image_registrator/point_triangulator/bundle_adjuster (`--nachregistrieren`);
  V5 mit seed 2 (Reproduzierbarkeit). Schwabentor-Gegenprobe: S0 (Standard), S2 (ohne Prioren, Kamera je Clip).

## Rezept "globaler Mapper stabil" (Stand 19.11.2026 03:45, Werkzeug `tools/global_mapper_konsens.py`, Schalter `tools/iphone_sfm.py --mapper konsens`)
Reihenfolge und Befehle (alles in `global_mapper_konsens.py` gekapselt; Python `/media/oem/scan/venv-colmap/bin/python -I`, Binary COLMAP 4.3.dev CUDA):
1. **DB bereinigen** (`tools/sfm_db_variante.py <db> <kopie> --priors loeschen --kamera-je-clip --loeschen '_360\.'`): alle EXIF-Prioren weg (pycolmap 4.2.1 schreibt
   fuer Canon-PowerShot/Pentax-Zuschnitte Brennweiten bis 8,7 Mio px; Kameras mit Prior werden im Kalibrator NICHT optimiert), eine Kamera je Videoclip
   (746 -> 17 Kameras; je Clip gleiche Bildgroesse; Rig/Frame-Tabellen mitziehen), 360-Grad-Panoramen raus. Sauber herleitbare EXIF-Prioren (`--priors exif`)
   brachten am Schwabentor keinen messbaren Gewinn (nur 24 von 286 Martinstor-Fotos) - deshalb einheitlich loeschen.
2. **Zwei globale Laeufe** je `view_graph_calibrator` (eigene DB-Kopie!) + `global_mapper` mit Standardoptionen (`tools/global_mapper_lauf.py`, seed 1 und 2).
   Zeit je Lauf: Schwabentor ~8 min, Martinstor ~12 min (6 GB RAM, sonst Auslagerung x3).
3. **Konsens-Schnitt** (`tools/sfm_stabil_schnitt.py laufA/0 laufB/0 --ausgabe rueckgrat/0 --liste unstabil.txt --lage 0.10 --rot 2`): Ausrichtung ueber die
   Kamerarotationen (chordal) + Standorte; stabil = Lage < 10 % Kernradius UND Rotation < 2 Grad. Ergebnis: Rueckgrat mit 60-80 % der Kameras, das sich
   zwischen unabhaengigen Paaren reproduziert (Schwabentor: 0 % > 10 % Kernradius, Rotation 1 % > 2 Grad, GPS-Kern 2 %).
4. **Stufe 2** `colmap mapper --database_path laufA/db_kalib.db --input_path rueckgrat/0 --output_path konsens/0 --Mapper.fix_existing_frames 1
   --Mapper.structure_less_registration_fallback 0 --Mapper.ba_use_gpu 1 --Mapper.ba_max_num_images_direct_dense_gpu_solver 0`: unstabile Bilder per PnP gegen
   das FESTE Rueckgrat; der strukturlose Rueckfall MUSS aus (er erzeugt alle 'zum Mond'-Kameras). Standard-Inlier-Schwellen (30 / 0,25); strengere (100 / 0,5)
   haengen nur weniger ein, ohne Gewinn.
5. **Bewertung** `tools/mapper_bewerten.py konsens --fotos <ordner> --vergleich laufA` (Kennzahlen oben), Draufsicht `tools/sfm_draufsicht.py` ansehen.
Ergebnis Schwabentor (S8b/S8e): GPS-Tor 9-10 % (Kern 2 %), 0 ferne/unplausible Kameras, Hoehe p90 0,9-2,5 m; 7-8 % der Bilder fehlen (lieber fehlen als falsch).
Ergebnis Martinstor (V8b): 826 von 1020, 0 ferne/unplausible Kameras; Rueckgrat 630 Kameras reproduzierbar.

**Was NICHT hilft (Boden erreicht, je zwei Ideen ohne Gewinn):** AnyCalib-Brennweiten als Prior (S3: 29 %) oder fest (S4: 30 %, V6) - schalten die Paar-Kalibrierung ab
bzw. verbiegen (ca. 6 % Brennweitenfehler); AnyCalib nur als Startwert (S5): gleichwertig, nicht besser; `ra_reweighting INLIER_MATCH_COUNT` (S6) und
`ba_num_iterations 6` (S7): im Rauschen; fester `random_seed`: Mapper trotzdem nicht deterministisch (S2d: 36 % Abweichung); 'nur Fotos bekannter Brennweite zuerst':
zu wenige (24), Nur-Foto-Modelle schlechter (F0-F2); `image_registrator` statt `mapper` fuer Stufe 2 (V7b): haengt nur die Haelfte der Fotos ein.
**Grenzen / wann schrittweiser Mapper noetig:** (a) weniger als ~100 Bilder oder kein Videorueckgrat -> Konsens entfernt zu viel, schrittweise;
(b) Kette beurteilt Lage weiterhin per GPS-Tor - am Martinstor sind die Wikimedia-Geotags Objektstandorte (Rest = Abstand Kamera-Tor), Tor dort blind;
(c) Fernfotos (> 4 Kernradien) bleiben unsicher (Brennweite/Abstand), auch im Konsens - fuer Fassaden nur Rueckgrat-Kameras nutzen (`unstabil.txt`);
(d) Mehrere Teilmodelle im globalen Lauf (Martinstor 4-6): nur das groesste geht in den Konsens.
Kosten: 2 x globaler Lauf + Stufe 2 (~5-10 min) = ~25-35 min Martinstor statt > 3 h schrittweise (rcpark-mt_gk3 lief ins 3-h-Limit).

## Ergebnispfade
- Protokoll aller Versuche (JSON-Zeilen): `/media/oem/rcdaten/tmp/globmap/versuche.jsonl`; Logs `/media/oem/rcdaten/tmp/globmap/logs/`.
- Martinstor Rezept-Ergebnis: `/media/oem/rcdaten/tmp/globmap/konsens_komplett_martinstor/konsens/0` (+ `konsens.json`, `unstabil.txt`, `rueckgrat/0`, `lauf1/`, `lauf2/`).
- Schwabentor Rezept-Ergebnis: `/media/oem/rcdaten/tmp/globmap/schwab/konsens_komplett/konsens/0`.
- Einzelversuche: `/media/oem/rcdaten/tmp/globmap/sparse_*` (Martinstor), `/media/oem/rcdaten/tmp/globmap/schwab/sparse_s*` (Schwabentor); Draufsichten `draufsicht_*.png`.
- Geaenderte Werkzeuge (nicht committet, Auftrag Nutzer): `tools/iphone_sfm.py` (`--mapper konsens`), `tools/schnelltest.sh` (Test Konsens-Schnitt). Neue Werkzeuge committet.
- Offen: Kette (`gesamtkette.py`/`pipeline_objekt.py`) reicht `--mapper` nicht an `iphone_sfm.py` durch (Aufruf ohne Mapper-Argument, pipeline_objekt.py:142); fuer den Einsatz in der Kette einen Schalter `RCPARK_MAPPER=konsens` oder ein Kettenargument nachziehen (nicht umgesetzt, Standard unveraendert).

## Untersuchung 21.11.2026 (Nutzer: "untersuche tief, warum der globale Mapper gescheitert ist ... groesster Hebel") - laufend
Neu: gefilterte DB (Vordergrund-Masken `db_masken_filter.py` + `seiten_erkennen --masken --streng`), Messwerkzeug `tools/modell_lage_vergleich.py` (RANSAC-Ausgleich, Abweichung je Bildquelle).
- 12:23 Job `mt_global_gefiltert_1121` (tools/versuche/mt_global_gefiltert_1121.sh): globaler Mapper je Seite auf der gefilterten DB, je zwei Laeufe.
- SUED (102 Bilder, je 130 s statt 81 s schrittweise): beide globalen Laeufe 101 Bilder. Lauf a gegen b: 92 von 101 Bildern auf <= 1 % der Szene gleich, Median 0,04 %, 8 Bilder > 2 % (alle Einzelfotos).
  Global gegen schrittweise (gleiche DB): 74-77 von 99 auf <= 1 %, 20-22 Bilder > 2 % - fast nur Einzelfotos (eigen 14, fotos 3-5), Videobilder 0; Brennweite der Einzelfotos 2,4-6,4 % anders.
  Schrittweise 21.11. gegen schrittweise 19.11.: 12 von 43 > 2 % (eigen 11), Brennweite 5,5 % anders -> die Einzelfoto-Streuung ist KEINE Eigenheit des globalen Mappers.
- ALTE globale Laeufe (ungefiltert, 19./20.11.) mit dem neuen Werkzeug gegen den Nord-Bezug: var_sift 46 von 377 > 2 % (Median 0,32 %), var_sift_w 42/366 (0,24 %), var_flexglue 52/371 (0,49 %), var_flexglue_w 69/370 (0,65 %).
  Am 20.11. hiess es fuer flexglue_w "VERFORMT, Median 2,48 %, 358 Kameras > 2 %" - das war der NICHT robuste Ausgleich ueber alle Kameras (Ausreisser ziehen die Abbildung). Robust ausgeglichen ist der Lauf nicht verformt.
- MESSFEHLER des neuen Werkzeugs, 1. Fassung: Ausgleich ueber "die besten 60 %" = Videobilder auf einer Geraden -> Drehung um die Fahrtlinie unbestimmt, scheinbar 12-14 % Abweichung. Jetzt RANSAC ueber Vierergruppen.
- OFFEN: Nord (538 Bilder) global a/b gegen schrittweise; Vereinen aus den gefilterten globalen Stuecken; Ursache der Einzelfoto-Streuung (freie Brennweite je Foto, 231 von 286 Fotos ohne EXIF-Brennweite).

### 21.11. 12:45 - Methode BRENNWEITEN-SCHAERFE (`tools/brennweite_schaerfe.py`) gegen wandernde Einzelfotos
- Befund DB martinstor-1120 (Kette): 2107 Bilder = 2107 Kameras - JEDES Videobild hat eine eigene Kamera mit geratener Brennweite (1,2 x Breite); EXIF-Brennweite nur bei 49 Bildern, darunter unsinnige Werte (f/Breite bis 2185, bekannter pycolmap-4.2.1-Fehler).
  Die Bereinigung des Konsens-Rezepts (`sfm_db_variante.py --priors loeschen --kamera-je-clip`) laeuft nur im Konsens-Mapper, nicht im schrittweisen Weg und nicht in den Tests von heute.
- Verfahren (am fertigen Modell, ohne zweiten Lauf, ohne EXIF): je Kamera Brennweite in 25 Stufen 0,70-1,43 setzen, Lage je Stufe neu ausgleichen (PnP auf Punkten mit Spur >= 4), Breite des Bereichs mit Rest <= Minimum + 10 % = Schaerfe; scharf < 4 %, weich, unbestimmt >= 10 % oder offen.
- PRUEFUNG 1 (Sued schrittweise 99 Bilder, 3 s; Abweichung gegen globalen Lauf b): scharf 63 Bilder -> 2 wandern > 2 %; weich 15 -> 3; unbestimmt 21 -> 15 (Median 17,8 % der Szene, Brennweite 13,9 % anders). Von 20 wandernden Bildern 15 als unbestimmt erkannt, 18 mit weich. Schwellen NICHT nachgestellt (erste Fassung).
- PRUEFUNG 2 (alter globaler Nordlauf var_sift, 818 Bilder mit Kamera je Clip, 61 s): gegen schrittweisen Bezug: unbestimmt 5 -> 5 wandern, weich 12 -> 6, scharf 360 -> 33 (9 %). Lauf 1 gegen Lauf 2: unbestimmt 26 -> 23, zu_wenig 5 -> 5, weich 36 -> 11, scharf 709 -> 96 (14 %).
  -> 'unbestimmt' trifft zu 71-100 %; aber 9-14 % der 'scharfen' wandern trotzdem (Videobilder mit gemeinsamer Kamera): ZWEITE Ursache, nicht die Brennweite (Vermutung: ferne Bilder / schwach angebundene Abschnitte) - offen.
