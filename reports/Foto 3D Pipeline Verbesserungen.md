# GPS-Tore sichern die Kette, PatchMatch-Tuning spart Stunden

Die groessten Gewinne liegen in Pruefungen und Schaltern, die schon auf dem Rechner sind, nicht in neuen Modellen. Fuer die Qualitaet kommt zuerst ein Pflicht-Tor nach jedem Mapperlauf: Der Anteil der Fotos, die mehr als 15 m neben ihrem Foto-GPS landen, hat in der Nacht jeden falsch angesetzten Rundgang-Abschnitt gezeigt, und genau dieses Mass nutzt auch die Fachliteratur, weil falsche Modelle in sich stimmig aussehen ([Doppelgangers++](https://arxiv.org/html/2412.05826v2)). Der globale Mapper mit `view_graph_calibrator` bleibt der Standard (eigene Messung: 8,6 statt 40 min, 3 % statt 18 % grob falsche Fotos), aber nur mit "einer Kamera je Bild" und nur hinter dem Tor: Mit gemeinsamen Kameras je Geraet fiel er auf dieselben 18 % zurueck, und am Kaufhaus mit vielen Bildern ohne EXIF war er schlechter als der schrittweise Mapper. Fuer die Laufzeit zaehlen fast nur die Tiefenkarten: Sie brauchen 123 der rund 140 Minuten, davon 75 Minuten der zweite, "geometrische" Durchgang. Ein eigener Test von heute 07:34 zeigt, dass die Wolke ohne diesen Durchgang im Median nur 1,8 cm abweicht, bei 40 % weniger Punkten. Die zweite Qualitaetsbaustelle ist die Ausrichtung an LoD2/DGM1: Der Massstabskollaps ist ein in der Literatur beschriebenes Fehlerbild, und fuer ihn wie fuer die 134-Grad-Verdrehung liegt ein konkreter Umbauplan vor. Fuer Fassadendetails lohnt zuerst LIMAP 2.0 (BSD-3) als zweite Kantenquelle neben dem eigenen Sweep. Fast alle Gewinnzahlen ausser den eigenen Messungen sind Schaetzungen. Jede Massnahme braucht deshalb die Gegenprobe am Kaufhaus.

Lesehilfe: "Belegt" heisst, eine Quelle oder eine eigene Messung stuetzt die Aussage. "Vermutung" heisst abgeleitet oder geschaetzt, also erst messen. "Lokal geprueft" heisst: am eigenen COLMAP-Build 4.3.0.dev0 mit `colmap <befehl> -h` nachgelesen.

## Zwei Stunden Tiefenkarten, aber die Fehler entstehen davor und danach

Das Zeitbudget am Schwabentor v2 (504 Bilder, eigene Messung, `modelle/STAND_2026-11-14.md`) sieht so aus:

- Merkmale 37 s, Abgleich ueber die Paarliste 319 s.
- Mapper (berechnet die Kamerastandorte): schrittweise 40 min, global 54 s Kalibrierung + 463 s = 8,6 min.
- Tiefenkarten (PatchMatch, je Foto eine Entfernungskarte): 123 min fuer 312 Bilder. Aus den Dateizeiten im Ordner `glob_kalib_v2/dicht/stereo/depth_maps` fuer diesen Bericht nachgerechnet: erster Durchgang 47,5 min (9,2 s je Bild), zweiter Durchgang 75,5 min (14,6 s je Bild). In der Nacht liefen andere GPU-Jobs mit, die Zeiten sind also eher zu hoch.
- Fusion (Karten zu einer Punktwolke verschmelzen): rund 2 min (ebenfalls aus den Dateizeiten), 4,41 Mio. Punkte.
- Platte: 16 GB Karten (4 GB Tiefe, 12 GB Normalen), bei nur 6,2 GB freiem Platz.

Rund 90 % der Rechenzeit stecken also in den Tiefenkarten. Die Fehler der Nacht entstanden aber an anderen Stellen, und fuer jeden gibt es eine Entsprechung in der Recherche:

- **Falsch angesetzter Rundgang-Abschnitt** (31 m neben dem GPS, schrittweiser Mapper). Die GLOMAP-Autoren nennen symmetrische Bauten als Hauptfehlerursache ([GLOMAP](https://arxiv.org/html/2407.20219)). Ein symmetrischer Torturm ist dafuer das Lehrbuchbeispiel.
- **Kaufhaus: global 15,6 m, schrittweise 5,9 m GPS-Rest** (nur 32 GPS-Fotos, rund 170 Chat-Kopien ohne EXIF). Die COLMAP-Doku sagt ausdruecklich, der globale Mapper "depends on reasonably good focal length priors" und sei "less robust to outliers" ([COLMAP CLI](https://colmap.github.io/cli.html)). Die Messung passt genau dazu.
- **Ausrichtung entartet** (Wolke nur 1,5-2,5 m hoch, Massstab 2,77 bzw. 7,2, spaeter Anschlag an der Grenze 0,0994, am Kaufhaus 2,48-fach). Freie Aehnlichkeitsschaetzungen auf Teildaten kippen laut Literatur haeufig in entartete Massstaebe ([arXiv 2607.00498](https://arxiv.org/pdf/2607.00498)).
- **Geisterwand**: 92 % der Beobachtungen aus einem Videoclip, dessen Kameras 70 m entfernt und unter dem Gelaende standen. Dafuer fehlt bisher ein Tor.
- **Stumm bestandenes GPS-Tor** bei 0 gefundenen Fotos (inzwischen behoben) und ein **CGI-Standbild**, das die Vorpruefung bestand.

## Rangliste: acht Massnahmen fuer Lage und Tempo, alle mit vorhandener Software

Die Reihenfolge wiegt Nutzen gegen Aufwand. Die Punkte 1 bis 3 sind heute testbar.

### 1. GPS-Tor nach jedem Mapperlauf zur Pflicht machen und erweitern

- **Was:** Nach jedem Mapperlauf (global wie schrittweise) den Anteil der GPS-Fotos pruefen, die grob daneben liegen. Dazu drei billige Zusatzpruefungen: (a) laengste Folge aufeinanderfolgender Ausreisser in Aufnahmereihenfolge, (b) Kameras unter dem DGM1-Gelaende, (c) Kameras innerhalb eines LoD2-Grundrisses.
- **Befehl:** vorhanden sind `tools/mapper_gps_vergleich.py` und `tools/lage_gps_pruefen.py`. Als unabhaengige Gegenrechnung: `colmap model_aligner --input_path sparse/0 --output_path sparse_enu --database_path db.db --alignment_type enu --alignment_max_error 10`.
- **Messen:** Anteil GPS-Fotos ueber 15 m. Testfall ist der bekannte Abschnitt 11:30 und 11:37-11:39 am Schwabentor.
- **Gewinn:** Ein falscher Mapperlauf faellt in Sekunden auf statt nach zwei Stunden dichter Wolke.
- **Risiko:** Bei wenigen GPS-Fotos (Kaufhaus: 32) ist der Anteil grob. Wer GPS spaeter auch im Mapper nutzt (Punkt 6), braucht zurueckgehaltene Kontrollfotos, sonst prueft das Tor sich selbst.
- **Lizenz:** COLMAP BSD, eigener Code.
- **Belegt:** Doppelgangers++ bewertet Rekonstruktionen genau so, ueber den Inlier-Anteil einer robusten Einpassung der Kamerastandorte auf die Geotags, und nimmt den Anteil statt des mittleren Fehlers, weil der unempfindlich gegen GPS-Rauschen ist ([Doppelgangers++](https://arxiv.org/html/2412.05826v2)). `--alignment_max_error` ist die Ausreisserschwelle und muss groesser 0 sein, sonst bricht der Befehl ab ([COLMAP model.cc](https://raw.githubusercontent.com/colmap/colmap/main/src/colmap/exe/model.cc)). Eigene Messung: 3 % gegen 18 %. Neu um 07:35: auch der globale Mapper setzte mit 84 statt 504 Kameras wieder 18 % falsch. Er ist also nicht von sich aus immun.
- **Vermutung:** Die Schwellen (10-15 m, mindestens 90 % Inlier, Folge ab 5 Fotos) sind Startwerte ohne Quelle. Der Beispielwert 3.0 aus der COLMAP-Doku ist fuer Handy-GPS zu eng. Ein Seitentest (Richtung jeder Kamera um die Turmmitte, Modell gegen GPS) waere empfindlicher als der Abstand, weil nah am Turm die falsche Seite nur wenige Meter ausmacht.
- **Zwei Hinweise aus dem Code und der Datenbank:** `lage_gps_pruefen.py` zieht im Bootstrap einzelne Fotos (Zeile 79-80). GPS-Fehler aufeinanderfolgender Fotos haengen aber zusammen, das 90-%-Band ist deshalb zu schmal. Besser nach Standort oder Zeitabschnitt gruppiert ziehen (Vermutung aus der Recherche). In der Schwabentor-Datenbank haben 4 von 201 GPS-Vorgaben ein undefiniertes Koordinatensystem (lokal geprueft). `model_aligner` verlangt WGS84-Vorgaben, diese 4 also vorher ansehen.

### 2. Globaler Mapper mit Kalibrierung als Standard, aber eine Kamera je Bild

- **Was:** `view_graph_calibrator` schaetzt die Brennweiten aus den Bildpaaren, danach rechnet `global_mapper` alle Kameras auf einmal. Die Kamerazuordnung bleibt "eine Kamera je Bild". Faellt Tor 1 durch, laeuft der schrittweise Mapper als Zweitversuch.
- **Befehl** (wie im eigenen Skript `glob_kalib.sh`):
  - `cp db.db db_global.db`
  - `colmap view_graph_calibrator --database_path db_global.db`
  - `colmap global_mapper --database_path db_global.db --image_path bilder --output_path sparse_global`
- **Messen:** Tor 1, Zahl registrierter Bilder, Laufzeit.
- **Gewinn (belegt, eigene Messung):** 8,6 statt 40 min. 494 statt 463 registrierte Bilder. Rueckprojektion 0,92 statt 1,05 px. 3 % statt 18 % grob falsche GPS-Fotos.
- **Risiko:** Der Kalibrator veraendert Brennweiten und Paar-Geometrien in der Datenbank, deshalb immer auf einer Kopie arbeiten und nie beide Mapper auf derselben veraenderten Datei mischen ([COLMAP FAQ](https://colmap.github.io/faq.html)). Der globale Mapper kann nicht sauber unterbrochen und fortgesetzt werden ([COLMAP CLI](https://colmap.github.io/cli.html)). Eine unabhaengige Arbeit sah die Kalibrierstufe auf einem Datensatz divergieren ([InstantSfM](https://arxiv.org/html/2510.13310v2)).
- **Lizenz:** BSD.
- **Abgleich mit der Recherche:** Die Notizen hatten gemeinsame Kameras je Geraet oder Clip als Hebel vorgeschlagen (weniger Unbekannte). Die Messung von 07:35 spricht dagegen. Die Literatur stuetzt den Vorschlag ohnehin nur schwach: Ein Wettbewerbsteam meldete "gelegentlich etwa 0,01" Gewinn ([IMC 2024](https://arxiv.org/html/2407.03172)). Gemeinsame Kameras sind damit kein Standard.
- **Vermutung:** Die Ursache des Rueckfalls ist offen. Kandidaten: ein Clip mit Zoom oder Bildstabilisierung verzerrt alle seine Bilder zugleich, oder Hoch- und Querformat stecken in einer Kamera. Pruefbar ueber den Rueckprojektionsfehler je Kameragruppe. Es war ein einzelner Lauf.
- **Kleine Zusatztests (lokal geprueft, Wirkung unbelegt):** `--GlobalMapper.ba_backend CASPAR` (Buendelausgleich auf der GPU; die Entwickler nennen "oft 1-2 Groessenordnungen" gegenueber Ceres-CUDA, [COLMAP Changelog](https://colmap.github.io/changelog.html); bei 8,6 min Gesamtzeit ist der absolute Gewinn klein). `--TwoViewGeometry.use_degensac 1` fuer die ebene Arkadenfront des Kaufhauses.

### 3. Tiefenkarten: den geometrischen Durchgang weglassen, dann weiter abspecken

- **Was:** PatchMatch rechnet standardmaessig zweimal. Der zweite Durchgang gleicht die Karten untereinander ab. Fuer ein Lage-Veto reicht voraussichtlich der erste Durchgang plus strengere Fusion. Danach schrittweise: grobere Abtastung, weniger Quellbilder, kleinere Bilder.
- **Befehle/Optionen** (Stelle im eigenen Code: `tools/sfm_dicht.py` Zeile 79):
  - Schritt A: `--PatchMatchStereo.geom_consistency false --PatchMatchStereo.filter true`, Fusion mit `--input_type photometric --StereoFusion.min_num_pixels 8`.
  - Schritt B: `--PatchMatchStereo.window_step 2`.
  - Schritt C: in `stereo/patch-match.cfg` die Zeile `__auto__, 20` auf `__auto__, 10`.
  - Schritt D: `--PatchMatchStereo.max_image_size 1200`.
  - Sofort und verlustfrei: nach dem geometrischen Durchgang `stereo/depth_maps/*.photometric.bin` und `stereo/normal_maps/*.photometric.bin` loeschen.
- **Messen:** Abstand Wolke zu Wolke in beide Richtungen gegen die bestehende Wolke und gegen die Kaufhaus-Referenz, Grundriss-Tor, Hoehen an Zinnen und Tuermchen, Sekunden je Bild. Erst A allein, dann B und C dazu.
- **Gewinn Schritt A (belegt, eigene Messung):** Es entfallen 75,5 von 123 min, die Tiefenkarten werden also etwa 2,6-mal schneller, und die Kette aus Kameraberechnung und dichter Wolke faellt von rund 140 auf rund 65 min. Der Test von 07:34 (`glob_kalib_v2/fusion_photo.log`): Fusion aus den vorhandenen fotometrischen Karten in 146 s, 2,63 statt 4,41 Mio. Punkte. Genauigkeit gegen die geometrische Wolke: Median 1,8 cm, 90 % unter 6,3 cm, 1,8 % ueber 30 cm. Vollstaendigkeit: Median 2,3 cm, 0,2 % ueber 30 cm. Der Plattenbedarf halbiert sich auf rund 8 GB.
- **Gewinn Schritte B bis D (Vermutung):** B bis zu 4-fach auf den Rechenkern, denn der Quelltext nennt "roughly window_step^2" und warnt erst bei Schritten ueber 2 ([patch_match_options.h](https://raw.githubusercontent.com/colmap/colmap/main/src/colmap/mvs/patch_match_options.h)). C knapp 2-fach. D etwa 1,8-fach und 44 % weniger Platte. Zusammen waeren 10-20 min denkbar. Gemessen ist davon nichts.
- **Risiko:** Der Test von 07:34 nutzte ungefilterte Karten (im Zweifachlauf schreibt der erste Durchgang ohne Filter, [patch_match.cc](https://raw.githubusercontent.com/colmap/colmap/main/src/colmap/mvs/patch_match.cc)). Ein echter Lauf mit `filter true` faellt etwas anders aus. Keine Quelle beziffert den Qualitaetsverlust dieser Schalter. Die 40 % fehlenden Punkte vor der Uebernahme an Zinnen und Tuermchen ansehen. Nicht den Bildbestand ausduennen: Das hat lokal schon Tuermchen gekostet (`modelle/NICHTS_GEBRACHT.md`).
- **Lizenz:** BSD.
- **Belegt:** Die COLMAP-FAQ empfiehlt genau diese Schalter in dieser Reihenfolge und nennt 10 Quellbilder als Zielwert ([COLMAP FAQ](https://colmap.github.io/faq.html)). Die Fusion braucht die Normalenkarten zwingend, sie lassen sich nicht einsparen ([fusion.cc](https://raw.githubusercontent.com/colmap/colmap/main/src/colmap/mvs/fusion.cc)).
- **Nicht tun:** `gpu_index "0,0"` (zwei Arbeiter auf einer GPU) brachte selbst auf einer A100 "almost no success". Der Quelltext-Eingriff `THREADS_PER_BLOCK` lieferte dort eine kaputte Wolke mit 0 Punkten ([COLMAP Issue 2536](https://github.com/colmap/colmap/issues/2536)).

### 4. Ausrichtung an LoD2/DGM1 umbauen: GPS begrenzt, Waende bestimmen, Tore beweisen

- **Was:** `sfm_lod2_ausrichten.py` so aendern, dass die beobachteten Fehler nicht mehr gewinnen koennen. In dieser Reihenfolge:
  - Loesungen mit Anschlag an der Massstabsgrenze, Guete 0 oder Wolkenhoehe weit unter der LoD2-Hoehe sind Fehlschlaege, nie Ergebnisse.
  - Die Kamerahoehen-Bedingung (1,6 m) aus dem Fit nehmen und nur noch als Tor pruefen.
  - Die Drehsuche auf "GPS-Drehung plus/minus Unsicherheit" begrenzen statt 0-360 Grad.
  - Den Massstab als Logarithmus mit GPS-Vorgabe fuehren. Die Wand-Zuordnung nach der Grobsuche einfrieren: je Fassadenebene genau eine LoD2-Wand.
  - In die Grobsuche die LoD2-Waende der Nachbarhaeuser im Umkreis von 100-150 m aufnehmen. Das bricht die Symmetrie des quadratischen Turms. Die um 90, 180 und 270 Grad gedrehten Gegenkandidaten immer mitrechnen.
  - Beidseitig bewerten: Punkte nahe einer Wand UND sichtbare Wandlaenge mit Punkten UND Strafe fuer Punkte auf der Strasse oder Sichtstrahlen durch Waende.
- **Messen:** An Schwabentor v2 und Kaufhaus. Jeweils auch absichtlich falsche Startlagen (134 Grad, 2,5-fach) einspeisen. Das Werkzeug muss sie verwerfen. Vergleichswert ist die uebertragene Ausrichtung `glob_v2t` (Rest 0,38 m, GPS-Tor 1,1 m).
- **Gewinn:** Beseitigt alle vier Ausrichtungsfehler der Nacht. Bis dahin ist `tools/ausrichtung_uebertragen.py` der belegte Notweg (eigene Messung).
- **Risiko:** Eigenbau. Ein fertiges offenes Werkzeug "SfM auf CityGML-LoD2" wurde nicht gefunden.
- **Lizenz:** eigener Code. TEASER++ und small_gicp sind MIT ([TEASER++](https://github.com/MIT-SPARK/TEASER-plusplus), [small_gicp](https://joss.theoj.org/papers/10.21105/joss.06948.pdf)). Go-ICP ist GPL v3 und scheidet aus ([Go-ICP](https://github.com/LIHU577/Go-ICP)). Die Lizenz des L2M-Reg-Codes ist ungeprueft.
- **Belegt:** Das ebenenbasierte L2M-Reg erreicht gegen LoD2 1-5 cm Lagefehler, punktweises GICP 4-18 cm. LoD2-Waende sind hochgezogene Katastergrundrisse und liegen am Sockel, nicht an der Fassade. Der Versatz betraegt Zentimeter bis Dezimeter und darf nicht als Fit-Fehler bestraft werden ([L2M-Reg](https://arxiv.org/html/2509.16832v3)). Die Massstabsschaetzung bei Punkt-zu-Ebene-Verfahren driftet ([arXiv 2301.12796](https://arxiv.org/pdf/2301.12796)). Ein aelteres Verfahren richtet SfM-Wolken ueber Grundrisslinien in unter 30 s auf CityGML aus, braucht aber eine grobe Vorlage aus GPS ([Goebbels 2018](https://www.hs-niederrhein.de/fileadmin/dateien/FB03/Personen/goebbels/line.pdf)). Das DOM1 hat 1 m Raster und plus/minus 15 cm Hoehengenauigkeit auf festen Flaechen ([LGL DOM1](https://lgl-bw.de/Ueber-Uns/Newsletter/Galerien/Dokumente/2024-04_DOM1.pdf)).
- **Vermutung:** GPS allein legt den Massstab nur auf etwa "GPS-Fehler geteilt durch (Kameraradius mal Wurzel der unabhaengigen Standorte)" fest. Mit 5 m GPS-Fehler, 10 unabhaengigen Standorten und 10 m Radius sind das rund 16 %. Das wuerde erklaeren, warum das GPS-Tor am Schwabentor 0,857 und 0,864 meldet, die Fernfotos mit langem Hebel aber 0,97. Folge: GPS liefert Lage und grobe Drehung, den Massstab liefern Wandabstaende und Gebaeudeecken, und die feste Torgrenze 0,85-1,15 gehoert durch eine aus der Unsicherheit berechnete ersetzt. Die Formeln sind eigene Herleitung der Recherche und per Zufallsversuch zu bestaetigen. Ebenfalls Vermutung: das DOM1 als zweite, vom LoD2 unabhaengige Massstabsprobe ueber die Gebaeudehoehe (aufloesbar etwa 2-3 %).
- **Lot ohne Strassenannahme:** `colmap model_orientation_aligner` schaetzt die Senkrechte aus Fluchtlinien der Bilder ([COLMAP model.cc](https://raw.githubusercontent.com/colmap/colmap/main/src/colmap/exe/model.cc)). GeoCalib liefert sie je Einzelbild (Code Apache-2.0, Gewichte CC-BY-4.0, [GeoCalib](https://github.com/cvg/GeoCalib)). Beides haengt nicht an Fernkameras oder Drohnenfotos.

### 5. Bilder ohne EXIF: Originale nehmen, Rest vorkalibrieren, schwierige Bilder nachtraeglich anhaengen

- **Was:** (a) Chat-Kopien durch die Originale mit EXIF ersetzen (der Test `rcpark-kh_exif` ist schon eingeplant). (b) Fuer Bilder ohne EXIF (YouTube, Commons) die Brennweite mit `single_view_calibrator` vorschaetzen statt mit dem Pauschalwert. (c) Mischform: erst ein Kernmodell nur aus Bildern mit guter Brennweite global rechnen, dann den Rest schrittweise anhaengen.
- **Befehl:**
  - `colmap single_view_calibrator ... --image_list_path liste_ohne_exif.txt` (nach `feature_extractor`, vor dem Abgleich; uebrige Pflichtangaben per `-h`).
  - Kern: `colmap global_mapper ... --GlobalMapper.image_list_path kern.txt`
  - Rest: `colmap mapper --input_path kern --output_path voll --database_path db.db --image_path bilder`
- **Messen:** Tor 1 am Kaufhaus (heute 15,6 m global gegen 5,9 m schrittweise). Kontrolle ohne Musterleck: den Kalibrator auf Handyfotos mit EXIF laufen lassen und gegen die EXIF-Brennweite vergleichen.
- **Gewinn:** Vermutlich wird der globale Mapper damit auch am Kaufhaus brauchbar.
- **Risiko:** Einbild-Kalibrierung ist nur ein Startwert. Das verwandte GeoCalib erreicht beim Sichtfeld auf MegaDepth nur eine Trefferkennzahl (AUC bei 5 Grad) von rund 32 % ([GeoCalib](https://github.com/cvg/GeoCalib)).
- **Lizenz:** COLMAP BSD. Die Lizenz des AnyCalib-Modells ist ungeprueft.
- **Belegt:** Ohne EXIF setzt COLMAP die Brennweite pauschal auf 1,2-mal die Bildgroesse (lokal geprueft). Die Doku empfiehlt die Kalibrierstufen vor dem globalen Mapper ([COLMAP CLI](https://colmap.github.io/cli.html)). Eigene Messung: Am Kaufhaus verwarf die Kalibrierung 20 Kameras und 1051 Paare.
- **Vermutung:** Dass AnyCalib an Fassaden besser ist als der Pauschalwert, und dass die Mischform die Seitenverwechslung seltener macht, weil alle Turmseiten schon stehen.

### 6. Filter gegen Doppelgaenger-Bildpaare, billig zuerst

Ein Doppelgaenger-Paar sind zwei Fotos, die gleich aussehende, aber verschiedene Turmseiten zeigen. Der Abgleich haelt sie fuer dieselbe Wand.

- **Stufe a, eigener GPS-Seitenfilter (Vermutung, lizenzfrei):** Paare aus der Datenbankkopie loeschen, deren GPS-Standorte um die Turmmitte mehr als etwa 120 Grad auseinander liegen. Solche Fotos koennen dieselbe Fassade nicht sehen. Wirkt nur fuer Fotos mit GPS.
- **Stufe b, GPS im schrittweisen Mapper:** `colmap pose_prior_mapper --database_path db.db --image_path bilder --output_path sparse_prior --overwrite_priors_covariance 1 --prior_position_std_x 8 --prior_position_std_y 8 --prior_position_std_z 25 --use_robust_loss_on_prior_position 1`. Die Optionen sind lokal geprueft, der Standard von 1 m ist fuer Handy-GPS zu eng ([COLMAP FAQ](https://colmap.github.io/faq.html)). Die Werte 8/8/25 sind eigene Wahl. Sie passen zum gemessenen GPS-Rest von 5,5-6,7 m im Median und zu Studien mit 5-8,5 m medianem Handy-Fehler ([PMC8577807](https://pmc.ncbi.nlm.nih.gov/articles/PMC8577807)). Der globale Mapper kennt keine GPS-Vorgaben (lokal geprueft). Ob die Vorgabe die Fehlanheftung wirklich verhindert, ist ungemessen.
- **Stufe c, FlexGlue (neuer COLMAP-Bau noetig):** Der Abgleicher verwirft Paare, die wahrscheinlich nicht denselben Ort zeigen, mit `--FlexGlueMatching.min_covisibility` 0.5 bis 0.8 ([COLMAP features](https://colmap.github.io/_sources/features.rst.txt)). Er fehlt im Build vom 30.10. Der Code ist MIT, die Gewichte enthalten aber ein DINOv3-Teil mit einschraenkender Lizenz ([FlexGlue](https://github.com/cvg/FlexGlue)).
- **Stufe d, Doppelgangers++ (nur Diagnose):** fester Schwellwert 0.8, auf einer Schlossszene 0,874 Inlier-Anteil gegen 0,451 beim Vorgaenger ([Doppelgangers++](https://arxiv.org/html/2412.05826v2)). Lizenz CC BY-NC-SA 4.0, also nicht kommerziell ([LICENSE](https://raw.githubusercontent.com/doppelgangers25/doppelgangers-plusplus/main/LICENSE)). VRAM-Bedarf unbelegt.
- **Messen:** Tor 1 am bekannten Fehlabschnitt. Haertetest ist die Variante mit 84 gemeinsamen Kameras, die 18 % falsch setzt.
- **Risiko:** Ein Wettbewerbsteam fand, dass der Vorgaenger-Filter eine Kirchenszene nicht verbesserte ([IMC 2024](https://arxiv.org/html/2407.03172)). Also am eigenen Turm pruefen, nicht blind uebernehmen.
- **Vermutung:** Hoehere Inlier-Schwellen (`--TwoViewGeometry.min_num_inliers`) entfernen schwache Zufallspaare, aber keine echten Doppelgaenger, weil die viele stimmige Treffer haben.

### 7. Abgleich fuer Fremdbilder: erst `SIFT_LIGHTGLUE`, dann LoMa

- **Was:** Der eigene Build kann gelernte Merkmale und Abgleicher schon (lokal geprueft). Erster Test ohne neue Merkmale: Datenbank kopieren, alte Paare loeschen, mit LightGlue ueber dieselbe Paarliste neu abgleichen. Zweiter Test in einer getrennten Datenbank mit LoMa.
- **Befehl:**
  - `colmap database_cleaner --type two_view_geometries --type matches` (auf der Kopie)
  - `colmap matches_importer --match_list_path paare.txt --match_type pairs --FeatureMatching.type SIFT_LIGHTGLUE`
  - Zweiter Test: `--FeatureExtraction.type LOMA_B --LomaExtraction.max_num_features 4096`, Abgleich `--FeatureMatching.type LOMA_B`.
- **Messen:** registrierte Commons- und YouTube-Bilder, Tor 1, Foto-F1. Nicht an Trefferzahlen entscheiden. Im Log nach "Falling back to CPU" suchen.
- **Gewinn:** Auf den harten Vergleichsdaten liegt LoMa-B bei 68,7 / 51,1 / 87,4 gegen 43,9 / 35,7 / 76,9 fuer ALIKED+LightGlue, bei gleicher Laufzeit. Eine der drei Datenreihen besteht aus Wikimedia-Commons-Bildern, also unserer Quellenart ([LoMa](https://arxiv.org/html/2604.04931v1)).
- **Risiko:** Die Zahlen stammen von den LoMa-Autoren, eine unabhaengige Bestaetigung fehlt. Unter 2048 Punkten faellt die Leistung deutlich. In einer Datenbank duerfen nicht zwei Merkmalsarten stehen ([COLMAP features](https://colmap.github.io/_sources/features.rst.txt)). VRAM auf 8 GB ungemessen.
- **Lizenz:** LoMa-Code MIT, fuer die Gewichte nennt das README keine Lizenz ([LoMa README](https://github.com/davnords/loma)). LightGlue Apache-2.0 ([LightGlue](https://github.com/cvg/LightGlue)). MASt3R bleibt trotz Wettbewerbssieg aussen vor (nicht kommerziell).

### 8. Bild- und Frame-Auswahl: Geisterwand, CGI und Videos

- **Geisterwand:** Die Bilder 004-009 des Clips LMS3Va6psfY aus `stereo/fusion.cfg` nehmen. Dauerhaft deckt das die Pruefung "Kameras unter Gelaende" aus Punkt 1 ab (eigene Messung plus Vermutung zur Schwelle).
- **CGI-Standbilder:** Die Vorpruefung "mindestens 60 Treffer" bestaetigt nur Aehnlichkeit. Schaerfer (Vermutung): Treffer gegen mehrere raeumlich getrennte Kernfotos verlangen und die berechnete Kameralage gegen bestehende 3D-Punkte pruefen. KI-Bild-Erkenner taugen nicht als Tor: Der beste von 16 erreicht 75 % ([arXiv 2602.07814](https://arxiv.org/abs/2602.07814)).
- **Videos:** Praxiswerte liegen bei 2-5 Bildern je Sekunde ([COLMAP-Leitfaden](https://sebo-the-tramp.github.io/p/colmap-part1)). Belegt ist nur, dass Frames ohne Standortwechsel schlecht bestimmte Geometrie liefern ([StudioSfM](https://arxiv.org/pdf/2204.02509v1.pdf)). Ein Kriterium "genug Verschiebung zum letzten Schluesselbild" ist Vermutung. Gegen Einblendungen und Logos: `--TwoViewGeometry.filter_stationary_matches 1` (lokal geprueft). Videoframes fuer die dichte Wolke nur dort zulassen, wo `tools/kamera_abdeckung.py` eine Luecke zeigt (Vermutung).
- **Masken:** `--ImageReader.mask_path` und `--StereoFusion.mask_path` sind vorhanden (lokal geprueft). Der Nutzen fuer die Kameralage ist in den gefundenen Studien uneinheitlich (dort nur ueber Suchtreffer zugeordnet, nicht im Volltext geprueft). Niedrige Prioritaet, und die Himmelsmaske darf die Dachkontur nicht anfressen.

## Fassadendetails: zweite Kantenquelle und Orthofotos vor neuen Netzen

Der eigene Kanten-Tiefen-Sweep ist im Kern ein Abtasten von Tiefen um die Modellflaeche, bei dem die Fotos ueber jede Kante abstimmen. Die eigene Messung am Schwabentor zeigt seine Grenzen: Gegen die LoD2-Kiste ergibt sich F1 0, weil die Kiste keine Fassadenkanten hat. Die gefundenen Punkte sind fehlende Bauteile, und die Holzgalerie kragt ueber den Grundriss hinaus. Vier Schritte, wieder nach Nutzen je Aufwand:

### 9. LIMAP 2.0 als zweite, bandfreie Kantenquelle (zuerst)

- **Was:** LIMAP liest das vorhandene COLMAP-Modell, findet Geradenstuecke in den Fotos, ordnet sie zwischen Fotos zu und berechnet 3D-Linien. Es ist nicht an das Tiefenband um die Flaeche gebunden und findet so Erker, Speier und Baldachine.
- **Befehl:** `python -m pip install pylimap` (nur die Kernbibliothek; die gelernten Detektoren brauchen die Installation aus dem Quelltext), Detektor DeepLSD.
- **Messen:** Foto-F1 je Bauteil vorher und nachher. Nur Linien uebernehmen, die die Precision nicht senken. Wolke bleibt Lage-Veto.
- **Gewinn (Vermutung):** lange zusammenhaengende Kanten (Gesimse, Dachkanten, Pfeiler) mit Nachweis, welche Fotos sie stuetzen. Wenig Nutzen bei Masswerk, Boegen und dichten Rippenscharen. Aufwand etwa ein halber bis ein Tag.
- **Risiko:** Alle veroeffentlichten Zahlen stammen von Innenraeumen und Kleinobjekten, keine von Sandsteinfassaden. Ob Version 2.0.0 zum eigenen COLMAP 4.3 passt, ist ungetestet (das README nennt 4.2.0).
- **Lizenz:** LIMAP BSD-3 ([LIMAP](https://github.com/cvg/limap)). DeepLSD samt Gewichten MIT ([DeepLSD](https://github.com/cvg/DeepLSD)). Achtung beim Linien-Abgleicher GlueStick: wegen SuperPoint insgesamt nicht kommerziell ([GlueStick](https://github.com/cvg/GlueStick)).
- **Belegt:** LIMAP liefert laut eigenem Paper vollstaendigere und genauere Linienkarten als die Vorgaenger und hat seit 2026 einen Ausgleich, der Parallelitaet und gemeinsame Ebenen erzwingt, bei Laufzeit wie ein normaler Punktausgleich ([arXiv 2609.04026](https://arxiv.org/abs/2609.04026)).

### 10. Orthofoto-Stapel je Wandflaeche

- **Was:** Je Generator-Wandflaeche alle sichtbaren Fotos auf die Wand entzerren, in einem einheitlichen Meter-Raster. Das ist die gemeinsame Grundlage fuer Zaehlen (Wiederholungsabstand ueber Autokorrelation der Kantenkarte), fuer Elementmasken und fuer einen flaechigen Tiefen-Sweep, der Relief und Laibungstiefe als Hoehenkarte liefert.
- **Messen:** Zaehlung gegen `tools/foto_zaehlung.py`. Stimmen zwei unabhaengige Zaehlungen nicht ueberein, wird das eine offene Beobachtung, kein Mittelwert.
- **Gewinn:** Entzerrung auf die LoD2-Wand allein verbessert die Segmentierung um rund 11 % ([Texture2LoD3](https://arxiv.org/html/2504.05249v1)). Eine Hoehenkarte ueber einer geschlossenen Grundflaeche ist von der Bauart her wasserdicht (Vermutung zur Druckeignung, plausibel). Fuer Hinterschnitte wie Speier reicht sie nicht.
- **Massstab:** 0,3-0,8 mm Mindestdetail in 1:87 entsprechen 26-70 mm am Bau. Ein Raster von 1-2 cm genuegt, feineres Relief kann der Drucker nicht zeigen (eigene Rechnung).
- **Lizenz:** Eigenbau. SAM 3 fuer die Gegenzaehlung steht unter einer eigenen Meta-Lizenz und ist pruefpflichtig ([SAM 3](https://github.com/facebookresearch/sam3)).
- **Belegt:** Fuer Laibungstiefe aus Mehrbild-Fotos wurde kein fertiges offenes Verfahren gefunden. Die fotobasierten LoD3-Arbeiten setzen Oeffnungen flach oder mit Standardtiefe.

### 11. Den Sweep staerken statt ersetzen (alles Vermutung, je 1-2 Tage)

- Treffer in Nachbarfotos nur zaehlen, wenn die Kantenrichtung passt. DeepLSD liefert dafuer ein Richtungs- und ein Abstandsfeld ([DeepLSD](https://github.com/cvg/DeepLSD)).
- Ganze Rippenscharen gemeinsam verschieben und die Reihenfolge erhalten, statt je Pixel abzustimmen. Das zielt auf die Verwechslung paralleler Rippen.
- Zweiter Durchlauf mit dem Band um die gefundenen 3D-Kanten statt um die Grobflaeche. Viele Belege am Bandrand sind ein Warnsignal.
- Eine Karte je Wand "Beleg vor, auf, hinter der Flaeche" als automatischer Fehlteile-Finder. Die Idee stammt aus den Konfliktkarten der Laser-Arbeiten ([Scan2LoD3](https://openaccess.thecvf.com/content/CVPR2023W/PCV/papers/Wysocki_Scan2LoD3_Reconstructing_Semantic_3D_Building_Models_at_LoD3_Using_Ray_CVPRW_2023_paper.pdf)).

### 12. Generator-Parameter direkt an die Fotokanten anpassen

- **Was:** Je Bauteil wenige Parameter (Lage, Breite, Tiefe, Profilmasse) so einstellen, dass die in die Fotos projizierten Modellkanten moeglichst nah an den Fotokanten liegen. Anzahlen kommen fest aus der Foto-Zaehlung. Erst grob mit CMA-ES, dann fein mit einem selbst geschriebenen Gradienten ueber die Kantenabtastung.
- **Gewinn (Vermutung):** macht aus lueckenhaften Kanten saubere Masse mit Restfehler in Zentimetern. Ein nah verwandtes Verfahren braucht 0,06-0,56 s je Schritt, bleibt aber bei weit entferntem Start haengen ([DiffCSG](https://arxiv.org/html/2409.01421v2)). Aufwand 2-4 Tage fuer ein Musterbauteil.
- **Lizenz:** Eigenbau in PyTorch. Den fertigen Rasterer nvdiffrast meiden, er ist nur nicht kommerziell nutzbar ([nvdiffrast LICENSE](https://github.com/NVlabs/nvdiffrast/blob/main/LICENSE.txt)).
- **Zum Foto-F1 als Tor (Vermutung aus der Recherche):** immer bei zwei Toleranzen melden (etwa 2 und 6 Pixel), Kanten vorher auf ein Pixel Breite ausduennen, und die Precision (Modellkante hat Fotobeleg) als hartes Tor nehmen. Fotokanten enthalten Fugen und Schatten, die das Modell nie haben soll. Eine Veroeffentlichung, die ein solches Bildmass gegen Laser-Referenz validiert, wurde nicht gefunden.

## Was auf 8 GB nicht lohnt oder warten kann

- **Kameraberechnung per Netz (VGGT und Verwandte):** Folgearbeiten berichten Speichermangel bei rund 300 Bildern selbst auf 80-GB-Karten ([arXiv 2509.02560](https://arxiv.org/pdf/2509.02560v2)), und eine sparsamere Variante bleibt in der Bildqualitaet hinter dem Start aus COLMAP ([arXiv 2509.25191](https://arxiv.org/abs/2509.25191v1)). Beides sind Angaben aus Suchtreffern, nicht aus den Originaltabellen. Hoechstens als Starthilfe fuer einzelne Bilder.
- **GLUEMAP beobachten:** Das neue Paket des COLMAP-Teams verbindet solche Netze mit dem globalen Mapper und baut einen Doppelgaenger-Filter ein. VRAM-Bedarf und Lizenzkette der Gewichte sind ungeklaert ([GLUEMAP](https://github.com/colmap/gluemap)).
- **Gaussian Splatting als Geometriequelle:** Das beste Verfahren braucht im Mittel rund 10 GB und erreicht auf einem grossen Gebaeude nur F1 0,20 ([PGSR](https://arxiv.org/html/2406.06521v2), [NerfBaselines](https://nerfbaselines.github.io/tanksandtemples)). Lokal schon als Fehlschlag verbucht. GS4Buildings mit LoD2-Vorgabe waere nur eine Gegenprobe und ist nicht kommerziell lizenziert ([GS4Buildings](https://github.com/zqlin0521/GS4Buildings)).
- **Andere Tiefenkarten-Programme:** Die ACMM-Familie fuehrt in Vergleichen (F1 81-90 gegen 73 bei COLMAP), vor allem durch aufgefuellte glatte Flaechen ([DVP-MVS](https://arxiv.org/html/2412.11578), [ACMP](https://arxiv.org/pdf/1912.11744)). Fuer ein Lage-Veto ist das kein Gewinn, und an Gesimsen kann es glaetten. OpenMVS ist gebaut, steht aber unter AGPL, und ein Laufzeitvergleich fehlt ([OpenMVS](https://github.com/cdcseacave/openMVS/blob/master/COPYRIGHT.md)). Erst Punkt 3 ausreizen.
- **Gelernte Tiefenkarten:** In einem Vergleich 4- bis 13-mal schneller als COLMAP, aber mit "large reconstruction errors" ([arXiv 2604.10246](https://arxiv.org/html/2604.10246v1)). MapAnything mit dem Apache-Gewicht und den eigenen Kameras taugt als schnelle Gegenprobe ([MapAnything](https://github.com/facebookresearch/map-anything)).
- **Neuronale Kantenverfahren:** EMAP braucht 2,5-12 Stunden je Szene und hat keinen Weg fuer eigene Daten. EdgeGaussians trainiert in 5 Minuten, hat aber keine Lizenzdatei ([EdgeGaussians](https://arxiv.org/html/2409.12886v2)). Erst nach Punkt 9 bis 12.
- **`hierarchical_mapper`:** laut Doku weniger robust und fuer sehr grosse Bildmengen gedacht ([COLMAP FAQ](https://colmap.github.io/faq.html)).
- **Vernetzung der Wolke:** entfaellt, weil die Form aus Fotokanten kommt. Poisson ist lokal schon gescheitert.

## Fazit

Die Nacht und die Recherche zeigen dasselbe Muster: Jeder teure Fehler war in sich stimmig und fiel erst an einer unabhaengigen Quelle auf, am Foto-GPS, am Gelaende oder am Foto selbst. Ein schnellerer Mapper ist deshalb kein robusterer. Die Messung von 07:35 hat das fuer den globalen Mapper gezeigt, bevor die Literatur dazu befragt war. Der eigentliche Fortschritt sind Tore, die sich nicht selbst pruefen. Sind sie Pflicht, wird jeder Tempo-Versuch gefahrlos: Er besteht oder faellt automatisch. Damit ergibt sich die Reihenfolge fuer heute: Tor 1 scharf schalten, den Tiefenkarten-Lauf ohne geometrischen Durchgang gegen die Kaufhaus-Referenz bestaetigen, dann den Ausrichtungs-Feinfit umbauen.

Drei Dinge bleiben offen und lassen sich nur am eigenen Material klaeren. Erstens, warum gemeinsame Kameras den globalen Mapper kippen liessen. Zweitens, ob die 40 % weniger Punkte der schnellen Wolke an Zinnen und Tuermchen fehlen oder nur doppelte Belege waren. Drittens, ob GPS-Vorgaben im schrittweisen Mapper die Seitenverwechslung wirklich verhindern. Fuer keine der drei Fragen wurde eine veroeffentlichte Messung an 200-500 gemischten Fotos eines Einzelgebaeudes gefunden. Die eigenen Zahlen sind hier die beste verfuegbare Evidenz.
