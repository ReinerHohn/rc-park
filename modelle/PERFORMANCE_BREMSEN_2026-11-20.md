# Versteckte Performance-Bremsen: Pipeline, Bibliotheken, Hardware (Untersuchung 20.11.2026, 16:30-16:45)

Auftrag Nutzer: "suche tief weiter nach versteckten Performancebremsen ... wo sind Sweetspots mit geringen Kosten/Aufwand". Alles hier ist am laufenden System
gemessen oder im Quelltext nachgelesen; was NICHT gemessen ist, steht als ANNAHME/offen. Hardware-Stand: `modelle/HARDWARE_STAND_2026-11-20.md`.

## Wo die Zeit liegt (Kettenberichte, Minuten je Stufe)
- martinstor_gk3 (362 min): sfm 180, mapper 68, vorpruefen 36, video_suchen 33, netz_fotos 11.
- kaufhaus_gk2 (445 min): sfm 180, seiten_luecken 110, vorpruefen 49, video_suchen 32.
- kaufhaus_gk (218 min): sfm 86, video_suchen 81.
-> Die SfM-Stufe (Abgleich + Mapper) ist mit Abstand der groesste Block; Bauen/Fassaden/Fenster liegen je unter 5 min.

## A. Pipeline
1. **Abgleich: 91 % der Paare sind vergeblich** (gemessen an martinstor-1120 `db.db`): 769 478 Paare abgeglichen, nur 71 488 (9,3 %) ergeben eine bestaetigte
   Zwei-Bild-Geometrie. Dauer 62 min (langsame Kerne) bzw. ~37 min (alle Kerne, hochgerechnet aus 343 Paare/s am 19.11.).
   Bildsuche als Vorfilter ist VERSUCHT und gescheitert (DINOv2: top-40 enthaelt nur 26 % der SIFT-Paare, top-150 45 %; LOGBUCH_KETTENTEST Z.378). MegaLoc ungetestet (Lizenz Trainingsdaten offen).
   Offene Idee (nicht gemessen): zweistufiger Abgleich - erst billig (wenige Merkmale/kleines Bild) alle Paare, voll nur fuer Paare mit Rohtreffern; oder Videostetigkeit nutzen
   (trifft Schluesselbild k ein Foto nicht, die Nachbarn k+-4 auch nicht pruefen). Aufwand mittel, moeglicher Gewinn ~25 min je Kette.
2. **Mapper-Kaskade bei Datenmangel** (Quelltext `tools/iphone_sfm.py` Z.124-142, Lauf 1120b): Konsens (2 x globaler Mapper + Stufe 2, ~70 min) -> traegt nicht
   (815/2107 Bilder) -> NOCHMAL ein globaler Lauf (seit 16:01, > 35 min) -> GPS-Tor -> faellt es durch (am Martinstor zu erwarten: Wikimedia-Geotags sind keine Kamerastandorte,
   lauf1: 96 % > 15 m), kommt zusaetzlich der SCHRITTWEISE Mapper mit `--Mapper.num_threads 1` ueber alle 2107 Bilder (Stunden). Also bis zu 5 Mapper-Laeufe hintereinander.
   Sweetspots: (a) lauf1 des Konsens als "globalen Lauf" wiederverwenden statt neu rechnen (~30 min; lauf1 rechnet auf der bereinigten DB - Gleichwertigkeit mit mapper_bewerten pruefen);
   (b) GPS-Tor ueberspringen, wenn das Objekt als "Geotags unbrauchbar" bekannt ist (dann entscheidet es ohnehin nichts); (c) pruefen, ob num_threads 1 noetig ist
   (der Mapper ist laut Rezept auch mit festem Seed nicht deterministisch). Alles Entscheidungen mit Qualitaetsfolgen -> erst messen.
3. Globaler Mapper innen (global.log 1120b, 1681 Bilder): Lagebestimmung 116 s, Gesamtausgleich 561 s, Nachtriangulieren > 20 min. Das Nachtriangulieren laeuft
   Bild fuer Bild in EINER Schleife (`global_mapper.cc` Z.480) und nutzt ~4 Kerne, GPU 0 %. Dazu 51 Teilmodelle. Kein billiger Hebel ausser `skip_retriangulation` (kostet Punkte).
4. Vorpruefung (Profil an 59 Bildern, 29 s): 65 % der Zeit sind 24 einzelne LightGlue-Aufrufe je Bild (jedes der 24 Referenzfotos, 13 ms), Bildlesen 6 %, ALIKED 8 %.
   Gemischte Genauigkeit ist dort schon an. Sweetspot: Referenzfoto des letzten Treffers zuerst pruefen und beim ersten Treffer >= Schwelle aufhoeren (Videobilder treffen meist
   dasselbe Foto) - ANNAHME 30-50 % von 36-49 min; aendert nur, WELCHES Foto als Beleg im JSON steht, nicht das Ja/Nein.
5. Schon behoben heute: Kette nur auf langsamen Kernen; 3-h-Limit; CPU 55 W (siehe HARDWARE_STAND).

## B. Bibliotheken
1. **COLMAP + Ceres sind ohne AVX2/FMA gebaut** (gemessen: `libcolmap_sfm.a` 0 AVX-Befehle, `libceres.a` 0 FMA; build.ninja 0 x `-march=native`, Flags nur `-O3`).
   Die CPU kann AVX2 + FMA. Betroffen: Ceres-Ableitungen, Eigen, RANSAC-Schaetzer, Triangulation - also genau die CPU-Teile des Mappers.
   Testbau LAEUFT: `rcpark-colmap_opt_bau` (BAU_FLAGS="-O3 -march=native", Ziel `/media/oem/rcdaten/colmap-opt/prefix`, Log `/media/oem/rcdaten/tmp/colmap_opt_bau_1120.log`, JOBS=2 neben der Kette, Stunden).
   Danach A/B mit `tools/versuche/blas_ab_1120.sh`-Muster (gleicher Buendelausgleich, Endkosten muessen gleich sein) + ein Mapper-Lauf. Erwartung 10-30 % auf CPU-Anteilen (ANNAHME).
2. OpenBLAS statt Referenz-BLAS: gemessen, kein Gewinn (158 -> 148 s). GPU-Loeser 33 s (4,8 x) - wird genutzt.
3. LightGlue gemischte Genauigkeit (`tools/versuche/lg_mp_ab.py`, 20 Fotos, 54 Paare): Zuordnung 14,8 -> 9,7 ms/Paar (-34 %), Treffer 296,9 -> 296,1; ALIKED unveraendert 33 ms/Bild;
   cudnn.benchmark ohne Wirkung. `lg_match.py` und `zusatzfotos_lightglue.py` laufen noch ohne (Stufe seiten_luecken 110 min): Umstellung = eine Zeile je Werkzeug, vorher Trefferzahlen am echten Lauf vergleichen.
   (Die 4,9 % "Uebereinstimmung" im Testausdruck ist ein Messfehler des Skripts: Merkmale je Lauf neu berechnet, Indizes nicht vergleichbar.)
4. torch 2.15: TF32 fuer matmul aus (`allow_tf32=False`), nicht gemessen.

## C. Hardware / Kernel
- Platten: USB-SSD liest 404 MB/s, intern 4,8 GB/s; Plattendruck < 2,5 % -> kein Engpass, anderes Dateisystem bringt nichts.
- RAM 16 GB bleibt der groesste Hebel (parallele Mapper-Laeufe, zwei Objekte gleichzeitig). zswap an: Faktor 3,6 gemessen.
- CPU: 80-90 W Dauer statt 55 W (durchgewaermt). Regler nimmt bei Wenig-Faden-Last unnoetig zurueck (offen).
- Grosse Speicherseiten (THP always): 0 kB in Nutzung, A/B offen. Kernel-Sicherheitsbremsen abschalten: 1-3 %, nicht empfohlen.

## Rangfolge nach Nutzen je Aufwand
1. AVX2-Bau von COLMAP/Ceres (laeuft; Aufwand: warten + A/B).
2. Mapper-Kaskade entschlacken (A2 a/b): bis ~30 min bzw. Stunden je Kette bei Datenmangel-Objekten.
3. LightGlue fp16 in den zwei Werkzeugen ohne (B3): ~1/3 der Zuordnungszeit.
4. Vorpruefung mit "letzter Treffer zuerst" (A4).
5. Zweistufiger Abgleich (A1): groesster Einzelblock, aber Entwicklungsarbeit.
6. RAM-Kauf.

## Umsetzung 20.11. ab 16:45 (Nutzer: "setz die Punkte 2 bis 4 auch um")
- Punkt 2a UMGESETZT (`tools/iphone_sfm.py`): der Ausweichweg uebernimmt Konsens-Lauf 1 als globalen Lauf statt neu zu rechnen (Schalter `RCPARK_GLOBAL_NEU=1` = alter Stand).
  Beleg der Gleichwertigkeit (martinstor-1120): frischer globaler Lauf 1681 Bilder / 249 Tsd. Punkte / 31 Stuecke, Hauptstueck 817; lauf1 1669 Bilder / 276 Tsd. Punkte, Hauptstueck 825.
  Gespart: 51 min in diesem Lauf (3039 s, mit Stoerlast durch Tests; ungestoert ~22-26 min). Logik in 4 Faellen getestet (frisch / alt / fehlt / Schalter), echter Kettenlauf steht aus.
- Punkt 2b NOCH NICHT umgesetzt (bewusst): GPS-Tor fiel wie erwartet durch (17 GPS-Fotos, 94 % > 15 m), seit 16:49 laeuft der schrittweise Mapper (1 Faden, 2107 Bilder).
  Sein Ergebnis liefert den fehlenden Vergleich global gegen schrittweise an einem Objekt mit unbrauchbaren Geotags -> danach Regel festlegen (nicht raten).
- Punkt 3 UMGESETZT (`lg_match.py`, `zusatzfotos_lightglue.py`, Schalter `RCPARK_LG_MP=0`): sauberer A/B auf GLEICHEN Merkmalen (`tools/versuche/lg_mp_ab2.py`, 24 Fotos, 86 Paare,
  1280 px, 4096 Punkte): 31,3 -> 24,5 ms/Paar (-22 %), 37 191 -> 37 180 Treffer, 99,2 % identische Zuordnungen, RANSAC-Inlier 23 549 -> 23 833, 1 von 86 Paaren wechselt die >=60-Entscheidung (58 -> 57).
  Nicht bitgleich. Am echten Stufenlauf (seiten_luecken) noch nicht gemessen.
- Punkt 4 UMGESETZT (`video_suchen.treffer(zuerst=...)`, `bilder_vorpruefen.py`, Schalter `RCPARK_VORPRUEFEN_ALLE=1`): A/B an 200 Bildern (ohne Zwischenspeicher, ohne Kette):
  83 -> 68 s (-18 %), Ja 44 / 44, 0 abweichende Entscheidungen. Weniger als geschaetzt (30-50 %): Nicht-Treffer muessen weiter gegen alle 24 Referenzfotos. Zwischenspeicher-Version unveraendert.

## Wo sonst noch AVX2 fehlt (Nutzerfrage 16:50, gemessen per objdump/Laufzeitabfrage)
- pycolmap-Rad 4.2.1 (Merkmale, Abgleich, PatchMatch, Fusion): HAT AVX2 + FMA (489 Tsd. ymm-, 184 Tsd. FMA-Befehle) - nur unser Eigenbau der COLMAP-Programme nicht.
- numpy 2.5.4 (beide Umgebungen), torch, OpenCV: waehlen die Befehle zur Laufzeit selbst (numpy meldet AVX2/FMA3 aktiv). Nichts zu holen.
- PyTorch3D-Eigenbau `_C.so`: 0 AVX - Rechenlast liegt dort auf der GPU, ANNAHME unwichtig.
- System-Pakete CHOLMOD/METIS/Referenz-BLAS (apt): ohne AVX; BLAS-Tausch gemessen ohne Gewinn.
- ANDERER Fund gleicher Art: trimesh rechnet Strahlen mit dem langsamen reinen numpy-Verfahren (`trimesh.ray.ray_triangle`), 58 Werkzeuge nutzen Strahlen (pruefstand 15 Stellen, wolke_solid, fehlerkarte,
  fassade_ortho ...). Mit `embreex` (Rad fuer Python 3.12 vorhanden, Intel Embree Apache-2.0 - Lizenz vor Einsatz in LIZENZ_WERKZEUGE pruefen) nimmt trimesh automatisch Embree.
  ACHTUNG: Embree rechnet einfach genau -> Ergebnisse nicht bitgleich (am 1.11. wurde float32 fuer Hoehenkarten deshalb verworfen) -> nur mit Regression/Abnahme-A/B. Nicht umgesetzt, nicht gemessen.

## KORREKTUR Embree (20.11. 17:10, gemessen `tools/versuche/embree_ab.py`)
- Der Fund "trimesh rechnet Strahlen langsam" war FALSCH eingeordnet: ich hatte in der Generator-Umgebung (`~/.venvs/rcpark`) nachgesehen. Dort fehlen `embreex` UND `rtree` -
  Strahlen laufen dort gar nicht (ModuleNotFoundError). In `venv-seg`, wo Pruefstand, Fehlerkarte, Fassadenbild laufen, ist `embreex 4.4.0` laengst installiert und aktiv (`ray_pyembree`).
- Was Embree dort bringt (Kaufhaus-STL, 543 Tsd. Dreiecke, 2025 Strahlen, alle Treffer): numpy-Verfahren 3,40 s, Embree 0,28 s = 12 x; 9268 / 9268 Treffer, Abweichung der ersten
  Trefferentfernung 0,000 mm. Also kein zusaetzlicher Gewinn zu holen - er ist schon da.
- Nebenfund (Fehler, keine Bremse): `tools/py` schickte 14 Werkzeuge mit Strahlen (druck_klips, h0_druckfertig, fertigung_split, filigran, duese_check ...) in die Generator-Umgebung,
  wo sie beim ersten Strahl abstuerzen wuerden. Behoben: Werkzeuge mit `.ray.`/`intersects_*` gehen nach venv-seg.

## Weitere Hebel (20.11. 17:20-18:00)
- UMGESETZT, gemessen: schrittweiser Mapper `--Mapper.num_threads 1 -> -1` (seit 14.11. ohne Grund 1). A/B Schwabentor 203 Bilder (`tools/versuche/mapper_faeden_ab.sh`):
  179 Bilder registriert nach 540 s gegen 217 s = 2,5 x; 181 Bilder / 65 019 Punkte / 1,239 px gegen 180 / 63 519 / 1,236 px (1-Faden-Lauf kurz vor Ende abgebrochen).
- UMGESETZT (Nutzer "Ja tu das", 17:42): zweite Kette parallel, solange die erste im Mapper nur 1 Kern / 2,5 GB braucht (RAM-Buchung von Hand 11000 -> 5500).
  Strukturelle Loesung offen: RAM-Buchung JE STUFE statt je Lauf (Logbuch Punkt 5) - dann startet die naechste Kette von selbst, wenn Netz-/GPU-Stufen frei sind.
- AVX2-Bau: Zwischenstand Buendelausgleich CPU alt 165 s / neu 158 s / alt 156 s, Endkosten identisch -> KEIN messbarer Gewinn beim Buendelausgleich (Rest des A/B laeuft:
  GPU-Loeser, Mapper-Lauf; Log `/media/oem/rcdaten/tmp/avx_ab_1120.log`). Die Erwartung 10-30 % ist damit fuer diesen Teil widerlegt.
- PAARLISTE - Befund mit Qualitaetsfolge (martinstor-1120, 769 478 Paare, 71 488 bestaetigt):
  Foto x Foto 438 516 Paare (7,2 % bestaetigt), Foto x Videobild 280 163 (9,1 %), Video gleicher Clip 10 731 (72,4 %; Abstand <= 3: 85 %, 4-10: 69 %, > 10: 55 %), Video x anderer Clip 40 068 (16,7 %).
  Ursache der vielen "Foto"-Paare: 596 Videobilder heissen `fotos__vf_000_2.jpg` (aus einem alten Sammelordner uebernommen, Clipname verloren, fotos_sammeln haengt _2/_3 an) und gelten
  in `paarliste()` als Fotos -> voll gegeneinander. Schon am 19.11. notiert (Logbuch Punkt 50), nicht behoben.
  VERSUCHT und ZURUECKGENOMMEN: Namen als Clip erkennen -> 321 342 statt 769 478 Paare (42 %), aber nur 71,5 % der heute bestaetigten Paare bleiben (20 401 verloren:
  13 461 Videobild x Videobild, 6 940 Videobild x Foto). Der "Fehler" liefert also echte Verbindungen, die das Schema (jedes 4. Bild als Schluesselbild) nicht findet.
  Zweistufig (bestaetigte Paare um +-2 / +-4 Nachbarbilder erweitern): 67 % / 78 % der Paare, findet 87,4 % / 91,5 % - auch nicht verlustfrei.
  FOLGERUNG: Das Schluesselbild-Schema verschenkt vermutlich bei ALLEN Clips rund ein Viertel der echten Paare. Fuer das Martinstor-Problem (fremde Seite nicht angebunden) ist das
  eher ein QUALITAETS-Hebel als ein Tempo-Hebel: Versuch "Schluesselbild-Abstand 4 -> 2 bzw. Erweiterung um bestaetigte Paare" gegen Zahl registrierter Bilder / Stuecke messen (offen).
- Netzstufen (netz_fotos 11-20 min, video_suchen 31-81 min): live gemessen 2 % CPU, 0 % GPU - reines Warten auf Antworten, nacheinander, mit Pflichtpausen gegen Ratenlimits (429).
  Hebel: Commons/Openverse und YouTube GLEICHZEITIG abfragen (verschiedene Dienste, Pausen je Dienst bleiben) und diese Stufen fuer das naechste Objekt vorziehen. Nicht umgesetzt.
- Kein Hebel (gemessen): Kleinschritte der Kette (141 Schritte < 30 s = zusammen 10 min), Python-Start (2,1 s mit torch), Platten (404 MB/s USB, 4,8 GB/s intern).

## Profil mit perf (20.11. 17:55, Nutzer hat `kernel.perf_event_paranoid=1`, `ptrace_scope=0` gesetzt; perf = /usr/lib/linux-tools-6.8.0-78/perf, gilt bis Neustart)
- Laufender schrittweiser Martinstor-Mapper (25 s Stichprobe, im globalen Ausgleich): **50,3 % `ceres::SchurEliminator<2,3,-1>::ChunkOuterProduct`, 30,7 %
  `BlockRandomAccessSparseMatrix::GetCell`**, 3,7 % memset, 2,7 % EBlockRowOuterProduct, 2,1 % Residuen. Also 81 % = Aufbau des Schur-Komplements auf der CPU.
  Der Teil ist in Ceres ueber `num_threads` parallel - und lief mit 1 Faden. Das erklaert die 2,5 x der Faden-Umstellung und warum AVX2 nichts bringt
  (GetCell ist Tabellensuche/Speicherzugriff, kein Rechnen).
- NEUER FUND im selben Log: **769 x "Linear solver failure. Failed to compute a step"**, davon 753 in den 46 globalen Ausgleichen (~16 je Ausgleich), 17 in lokalen.
  Jede gescheiterte Loesung wirft die gerade gerechnete Schur-Elimination weg (Ceres erhoeht die Daempfung und rechnet neu). Auch im Sued-Anhang, der am Mittag "hing": 100 x.
  Einstellung dabei: `--Mapper.ba_use_gpu 1 --Mapper.ba_max_num_images_direct_dense_gpu_solver 0` = immer duenn besetzter GPU-Loeser (cuDSS).
  A/B LAEUFT (`tools/versuche/mapper_loeser_ab.sh`, Log `/media/oem/rcdaten/tmp/loeser_ab_1120.log`): heute / dichter GPU-Loeser / CPU / COLMAP-Standard - Zeit, Loeserfehler, Ergebnis.
- AVX2-Bau, sauber eingeordnet: enthaelt die Befehle (libceres.a 120 877 AVX- / 40 974 FMA-Befehle gegen 525 / 0), bringt beim Buendelausgleich nichts (CPU 165/158/156 s, GPU 41/46/40 s).
- AVX2-A/B Abschluss (18:05): Mapper Schwabentor 203 Bilder alt 402 s / neu 480 s / alt 272 s (176 / 172 / 180 Bilder; Loeserfehler 205 / 66 / 37; globale Ausgleiche 56 / 101 / 67).
  Die Streuung zwischen zwei Laeufen DESSELBEN Baus (272 gegen 402 s) ist groesser als jeder Bau-Unterschied - der Mapper nimmt je Lauf einen anderen Weg (nicht deterministisch),
  dazu wechselnde Nebenlast. ENTSCHEIDUNG: kein Gewinn belegt -> alter Bau bleibt in Betrieb; Testbau bleibt liegen (`/media/oem/rcdaten/colmap-opt`, 8 GB) bis zu einer Wiederholung auf leerem Rechner.
  Lehre fuer alle Mapper-A/Bs: ein Lauf je Variante reicht nicht; mindestens 3 je Variante oder ein deterministischer Teilschritt (Buendelausgleich) als Messgroesse.
- Loeser-A/B Abschluss (18:33, Schwabentor 203 Bilder, alle Faeden, je 1 Lauf): heutige Einstellung (GPU duenn) 300 s / 38 Loeserfehler / 178 Bilder; GPU dicht 375 s / 221 / 181;
  nur CPU 501 s / 85 / 180; COLMAP-Standard 367 s / 91 / 173. Die "Linear solver failure"-Meldungen treten bei JEDEM Loeser auf (38-221) -> keine Eigenheit von cuDSS, sondern der
  Ausgleichsaufgabe selbst (Schritt nicht berechenbar, Ceres daempft staerker). Kein Loeser ist klar besser; heutige Einstellung war die schnellste -> KEINE Aenderung.
  Offen bleibt, WARUM die Schritte scheitern (Kandidat: schlecht bestimmte Kameras/Punkte); bei 1 Lauf je Variante und 272-402 s Streuung desselben Baus ist die Rangfolge nicht sicher.

## Agentenrunde 20.11. 18:40-19:00 (9 Auftraege, Berichte /media/oem/rcdaten/tmp/hebel_1120/NN_*.md) - Kernaussagen, [n] = von der Sitzung nachgemessen
- [n] LOESERFEHLER SIND DER HAUPTZEITFRESSER des laufenden Martinstor-Mappers (Korrektur zur Loeser-A/B-Aussage oben): aus `pipe/pipeline.log` 50 globale Ausgleiche;
  33 ohne Fehler = zusammen 253 s, 16 mit Fehlern (ab 153 Bildern, je 32-91 Fehler) = zusammen 6922 s (Einzelwerte 196 / 211 / 428 / 797 / 914 s). Meldung dort
  909 x "...step: Success." = Faktorisierung des duenn besetzten GPU-Loesers (cuDSS) scheitert; im kleinen Schwabentor-A/B waren es dagegen 38 x "Eigen failure ... dense Cholesky"
  (Kleinstprobleme, belanglos) - der A/B hat das eigentliche Problem also NICHT getroffen. Nicht reproduzierbar am fertigen Stueck (`zeigen/stuecke/0`, 817 Bilder: 85 s, 0 Fehler).
  Verdacht (Agent 05): eigene Kamera je Bild in `db.db` (2107 Kameras) macht die Aufgabe schlecht bestimmt; der Konsens-Weg rechnet mit Kamera je Clip und zeigt die Fehler nicht.
  Naechster Schritt: Zwischenstand des schrittweisen Mappers sichern (`--Mapper.snapshot_path/_frames_freq`) und daran Loeser/Kameraregel deterministisch vergleichen.
- [n] Caspar (GPU-Loeser ohne Schur-Aufbau, in unserem Bau enthalten, `--BundleAdjustment.backend CASPAR`): 817-Bilder-Stueck 4 s statt 85 s, ABER Ergebnis zerstoert
  (mittlerer Rueckprojektionsfehler 1e147 px); Konsensmodell 3,1 s, Fehler 0,770 -> 0,777 px (keine Verbesserung); Schwabentor 1,2 s, unveraendert. Urteil: sehr schnell, so nicht einsetzbar.
- Agent 05 weitere Stellschrauben (ungemessen): Stufe 2 mit `--Mapper.multiple_models 0` (34 % der Stufe-2-Zeit fuer Nebenmodelle), `ba_global_frames_ratio/points_ratio 1.2`
  (weniger globale Ausgleiche), `view_graph_calibrator` laeuft ohne `--random_seed` (Quelle der Streuung), `GlobalMapper.min_model_size`, `TwoViewGeometry.max_num_trials`.
- Agent 09: bei gleichzeitiger GPU-Last bremst die gemeinsame Waerme (Mapper-Faden 2,8-3,9 statt 5,3-5,5 GHz); THP/Allocator/SQLite/Platte bringen nichts; GPU zieht 108-114 W (kein 80-W-Deckel).
- Agent 06 (dichte Wolke): 83 % der Zeit GPU-Sweep, haengt an der Pixelzahl; Vorschlag 1200 statt 1600 px (ANNAHME x 0,55-0,6), Fusion mit bounding_box + Himmelsmaske gegen Falschpunkte.
- Agent 03 (Seiten verbinden): es fehlen echte Brueckenbilder; Rang 1 Fotogang durchs Tor (Nutzer), Rang 2 `colmap guided_geometric_verifier` nach Einzelausrichtung der Stuecke an LoD2
  (im Bau vorhanden, nie benutzt); MASt3R/DUSt3R/Doppelgangers++ nur NC.
- Agent 08 (offene Daten): Stadt Freiburg hat Schraegluftbilder 2021 im 3D-Viewer (Abruf gesperrt -> Anfrage Vermessungsamt); Panoramax 163 Bilder am Schwabentor (CC BY-SA);
  Mapillary-Sperre im Lizenzregister vermutlich zu streng (Nutzerentscheid).
- Agent 02 (Hardware, Preise 20.11.): RAM 2 x 16 GB ~563 EUR, 2 x 32 GB ~1110 EUR (Speicherkrise); zweiter M.2-Platz laut HP-Handbuch sehr wahrscheinlich; NVMe 1 TB 130-180 EUR, 2 TB ab 305 EUR.
- Agent 01 (Cloud): Trooper.ai (PayPal/SEPA) 4090 + 96 GB 0,89 EUR/h; Hetzner CCX53 (32 vCPU/128 GB) 0,73 EUR/h als Mapper-Knoten; CPU-Typ der Mietmaschinen vor Entscheidung messen.
- Agent 07 (Kette parallel): Zweig `ram-je-stufe-1120` (Commit 105727c7b, Worktree .claude/worktrees/agent-a1b159488c8983a24), RAM-Buchung je Stufe + Netzstufen parallel hinter Schaltern
  (Standard AUS), nur synthetisch getestet, NICHT zusammengefuehrt. Offen: GPU-Buchung je Stufe, Dienst-Sperre fuer zwei Ketten am selben Netzdienst.
- Agent 04 (Paarschema): laeuft noch.
- Agent 04 (Paarschema, offline an der DB gemessen; Bericht 04_paarschema.md, Skripte 04_paare/): Kern wie heute + bewertete Erweiterung in 3-4 Runden
  (ungepruefte Paare bewerten nach bestaetigten Clipnachbarn +-2 und gemeinsamen Partnern, je Runde nur die besten abgleichen, Schluss unter 10 % Trefferanteil):
  an den 937 Bildern mit vollstaendiger Wahrheit 39-40 % der Paare -> 97,7-99,5 % der bestaetigten Paare (Kern allein 55,7-58,8 %); alle 2107 Bilder 60-69 % der heutigen Paare -> 97,4-99,3 %
  (untere Schranke), dazu ANNAHME ~50 000 neue echte Paare, die heute nie geprueft werden. Tempogewinn maessig (25-40 statt 40-60 min), Nutzen eher Qualitaet. Wirkung auf den Mapper ungemessen.
  Groesster denkbarer Tempohebel (nur Naeherung): Erstabgleich mit den 2000 groessten Merkmalen, Schwelle >= 3 Treffer -> 21,8 % der Paare enthalten 94,5 % der bestaetigten.
  Roh-Treffer sagen die Bestaetigung vorher (>= 30 Roh-Treffer: 13,5 % der Paare, 91,1 % der bestaetigten).
- Bruecken (Agent 04 + Sichtpruefung): der Paar-Graph ist bei >= 15 Inliern EIN Stueck (1969 Bilder); fremde Seite x Hauptstueck 14 218 bestaetigte Paare, aber Median nur 20 Inlier
  (>= 100: 299, >= 300: 37); 499 der 793 fremden Bilder haben keine Kante ins Hauptstueck. 22 der 30 staerksten Bruecken liegen im Clip jEQJGdvZ26U (Bilder 39-43), Art "eben/Panorama".
  [n] Kontaktbogen angesehen (`zeigen/bruecke_clip_jEQJGdvZ26U.jpg`): das ist ein SCHWENK ueber Nachbarhaeuser der Kaiser-Joseph-Strasse, nicht das Tor - reine Drehung ohne Standlinie,
  daraus kann der Mapper nichts triangulieren. FOLGERUNG: ein Teil der "fremden Seite" ist Strassenkulisse, keine Torseite; Ziel sollte "Tor von allen Seiten gedeckt" sein,
  nicht "alle 2107 Bilder registriert". Pruefauftrag: die 793 Bilder danach einteilen, ob sie das Tor zeigen (Vorpruefung sagt nur "zeigt Objekt" gegen Referenzfotos EINER Seite).

## Nachtrag 20:40 - wo der schrittweise Mapper WIRKLICH die Zeit laesst (perf am laufenden Lauf)
- KORREKTUR zur Rangliste Punkt 1 ("Loeserfehler = Hauptzeitfresser"): am laufenden Martinstor-Mapper (610 Bilder, noch mit `num_threads 1` gestartet 14:50)
  dauert JEDER globale Ausgleich 37-39 min (19:10:36->19:47:49, 19:48:29->20:27:36), mit nur 0-7 Loeserfehlern darin. Die Fehler sind Nebensache.
- perf (15 s, PID des Mappers): 59,7 % `SchurEliminator<2,3,-1>::ChunkOuterProduct`, 29,4 % `BlockRandomAccessSparseMatrix::GetCell`, 2,6 % `EBlockRowOuterProduct`
  = 92 % Schur-Elimination auf EINEM Kern; GPU 0 % ausgelastet (cuDSS loest nur das kleine Kamerasystem danach). Kosten ~ Summe(Spurlaenge^2) -> lange Videospuren.
- Folgen: (a) `num_threads -1` (seit heute Standard, `RCPARK_MAPPER_FAEDEN`) wirkt genau hier - die Elimination laeuft je Punktblock parallel; der laufende Lauf hat es noch nicht.
  (b) Kandidat `--Mapper.ba_global_ignore_redundant_points3D 1` (COLMAP-Schalter, Standard 0): A/B `tools/versuche/mapper_redundant_ab.sh` am Schwabentor (798 Bilder), Ergebnis unten nachtragen.
  (c) Ceres-Quelle `cuda_sparse_cholesky.cc` Z. 248: nach einem Zerlegungsfehler wird die Analyse-Stufe wiederholt (cuDSS-0.3-Eigenheit) - Kosten je Fehler, aber klein gegen (a).
- Kettenfehler behoben: `tools/wolke_grundriss_pruefen.py` stapelte 30 Drehungen * alle Punkte auf der GPU -> bei 7,9 Mio. Punkten (Schwabentor) OOM auf 8 GB, Tor "nicht geprueft",
  Kette brach 20:22 ab (rc 4). Jetzt Stapelgroesse aus der Punktzahl (2e7 Elemente), Ergebnis unveraendert. Kette ab `tore` neu gestartet 20:38.

## Nachtrag 20:44 - die "fremde Seite" am Martinstor ist ueberwiegend STADTRUNDGANG, nicht Tor (gemessen + angesehen)
- Stichprobe 70 von 793 Bildern (`martinstor-1120/zeigen/fremde_seite_stichprobe.jpg`, selbst angesehen): Muenster, Rathaus, Historisches Kaufhaus, Bertoldsbrunnen,
  Strassenbahnen, sogar das Schwabentor. Das Martinstor ist nur auf einem kleinen Teil (v. a. Netzfotos, eigene Fotos, Clips SMpS-YJWpt8 / A_PUR2GXND0).
- Herkunft je Bild aus `vorpruefung.json` (2107 Bilder im Satz, Anteil in der fremden Seite):
  direkter Treffer (>= 60 Inlier gegen Referenz) 1041 Bilder -> 24 % fremd; Kette Schritt 1: 67 -> 43 %; Schritt 2: 48 -> 43 %; Kette Schritt >= 3: 387 -> 62 %;
  Zeitfenster (+-12 Videobilder um einen Treffer, OHNE eigenen Treffer): 495 -> 44 %; unter 60: 69 -> 43 %.
- Deutung: die Regeln "Kette" (Nachbar vom Nachbarn ...) und "Zeitfenster" in `tools/bilder_vorpruefen.py` laufen bei Stadtrundgang-Videos die Strasse entlang vom Tor weg.
  882 Bilder (42 % des Satzes) kamen ohne direkten Treffer hinein; 541 der 793 fremden stammen daher. Sie kosten Paarsuche + Mapperzeit (quadratisch) und erzeugen das zweite Teilmodell.
- OFFEN (messen, nicht blind umstellen - die Regeln sollten Gegenseite/Durchgang retten): Variante "Kette hoechstens 2 Schritte, Zeitfenster nur mit schwachem Treffer (>= 15 Inlier)"
  -> Satz ~1200 Bilder; Mapper darauf laufen lassen und Abdeckung je Torseite gegen heute vergleichen. Echte Gegenseiten-Kandidaten = die 252 fremden Bilder MIT direktem Treffer.

## Nachtrag 20:50 - Schwabentor-Kette 1120: Tore gerechnet, Lage NICHT bestanden (rc 3, Abbruch vor dem Modellieren - so gewollt)
- Lauf c (ab `tore`, nach dem OOM-Fix): beste Loesung 0: kamera 0, gps 0 (Drehung 0,0 Grad, Massstab 0,994, Rest Median 4,4 m; Fernfotos Richtungsfehler 0 Grad), zerfall 0 (1 Stueck, 613 Bilder),
  gps_seiten 0 (GPS-STIMMIG); ROT: grundriss 3 (Turm 141 m2: Wolke deckt 78 % des Randes, "um 90 Grad gedreht passt besser" F1 0,76), kamera_gelaende 3 (7 von 36 Commons-Netzfotos unter Gelaende, bis -16 m),
  insel 3 (Clip Laxl3ULfqEI 13 von 26 ohne Fremdstuetze), gruppen 3 (6,6 % Punkte > 6 m daneben, 7 Commons-Einzelfotos).
- Bild `modelle/schwabentor-1120/audit/wolke_grundriss.png` angesehen: Wandpunkte liegen auf der Ost-/Stadtseite des LoD2-Turms und an den Nachbarfluchten - Lage sieht richtig aus;
  die Westseite des Turms hat keine Punkte (Kameras fast nur Sektor 180-210 Grad: 405 von 623).
- Deutung (ANNAHME bis gemessen): kein Lagefehler, sondern (a) einseitige Abdeckung -> das Grundriss-Tor kann beim fast quadratischen Turm die 90-Grad-Drehung nicht ausschliessen,
  (b) rund 20 falsch eingebaute Bilder (7 Commons, 1 Clip). Naechster Schritt: diese Bilder aus Modell/Fusion nehmen und Tore neu; Tore NICHT lockern.

## Nachtrag 20:55 - Martinstor-Kette 1120b nach 6 h am Zeitlimit der SfM-Stufe abgebrochen (rc 124, 20:51) - EIGENER FEHLER
- Mein Limit-Fix vom Nachmittag (`max(21600, RCPARK_STUFE_MAX_S)`) liess 6 h stehen; der 14:50 noch mit 1 Faden gestartete schrittweise Mapper stand bei 610 von 2107 Bildern
  (globale Ausgleiche zuletzt 38 min je Stueck) und haette nie gereicht. 4 h Mapperarbeit verloren (COLMAP schreibt ohne Snapshot nichts). Limit jetzt 12 h Standard (`RCPARK_STUFE_MAX_S`).
  LEHRE: lange Mapperlaeufe mit `--Mapper.snapshot_path/--Mapper.snapshot_frames_freq` starten, damit ein Abbruch nicht alles kostet (offen, in iphone_sfm einbauen + messen).
- Statt die Kette blind zu wiederholen, zwei Mapperlaeufe direkt auf der vorhandenen Datenbank (alle Faeden, parallel, Zeiten daher nur grob vergleichbar), 20:52 gestartet:
  `mt_inkr_alle` = alle 2107 Bilder -> `/media/oem/rcdaten/tmp/martinstor_inkr_1120/std`;
  `mt_inkr_eng2` = 1156 Bilder (direkter Treffer oder Kette <= 2, ohne Zeitfenster; Liste `bilder_eng.txt`) -> `.../eng`. Frage: wie viele Torbilder/Seiten je Variante, wie lange.

## Nachtrag 21:12 - Schwabentor 1120: KORREKTUR der Deutung von 20:50 (Grundriss-Tor)
- FALSCH war: "90-Grad-Drehung nicht ausschliessbar". Nachgelesen in `audit/wolke_grundriss.json`: Eindeutigkeit OK (Identitaet 0,38 gegen beste Alternative 0,30, keine Warnung),
  Teile OK (keine Warnung). Rot macht NUR Test A: Haufen auf der Strasse, 44 105 Punkte, Mitte (20,7 / 9,3), 48 x 33 m, nicht am Foto geklaert.
- Angesehen (`audit/haufen_0.jpg`, `audit/haufen_0_schnitt.jpg` = Draufsicht/Seitenansicht der Punkte z 1,5-9 m oestlich des Turms): keine zweite Turmkopie. Die Ostwand steht in allen Hoehen
  bei x 3-4 m (Querschnitt y 11-18 m). Auf dem Platz liegen strahlenfoermige Streifen, teils himmelblau = Flugpunkte entlang von Sehstrahlen (Faecher), dazu echte Nachbarfassaden.
- Folge: kein Eintrag `grundriss_haufen_geklaert` (das waere "echte Umgebung" - ist es nicht). Offen: Herkunft der Faecher je Bildquelle bestimmen (Clip? Kameras unter Gelaende:
  0P_MuzeClHM bei -6,8 m, eigen__vf_018..031 bei -4 m, einzelne eigene Fotos bis -84 m) und diese Bilder aus der Fusion nehmen; danach Tore neu.
- Nebenbefund: `tools/kamera_gelaende.py` rechnet mit ebenem Gelaende (ANNAHME im Werkzeug). Nahe Kameras (0-15 m) stehen im Median bei +1,2 m, die tiefen Gruppen liegen 15-60 m entfernt
  bei -4 bis -7 m - das ist kein Hang, die Gruppen sind falsch verortet.

## Nachtrag 21:36 - Speicher voll: `fassade_ortho.py --zelle 0.01` (Schwabentor, 444 Messkameras) wuchs auf 4,4 GB RAM + 7,3 GB Auslagerung, Auslagerung 16 GB voll
- 21:33 von Hand beendet (kill, rc -15 in der Kette, Stufe `fenster_ortho_fein` fehlt damit; Kette lief weiter), um die zwei Mapperlaeufe (je 40 min Arbeit) vor dem OOM-Killer zu schuetzen.
  Claude Code hat dabei alle meine Warter-Shells beendet (Speicherdruck) - Jobs selbst unberuehrt.
- Ursache der Enge: EIGENER FEHLER - Kette mit von Hand gesenkter Buchung (5000 statt 11000 MiB) neben zwei Mappern gestartet. Die gesenkte Buchung galt nur fuer die Mapperphase;
  spaete Stufen (Feinbild 1 cm) brauchen > 10 GB. Strukturelle Loesung = Zweig `ram-je-stufe-1120` (Buchung je Stufe), noch nicht zusammengefuehrt.
- OFFEN: (a) `fenster_ortho_fein` fuer schwabentor-1120 nachholen, wenn die Mapper fertig sind (Kette `--ab fenster` allein, Buchung 11000);
  (b) Speicherbedarf von fassade_ortho bei 1 cm messen und begrenzen (Fassaden nacheinander freigeben / Kacheln) - heute > 11,7 GB bei einem 4-Seiten-Turm.
- perf am Mapper mit allen Faeden (21:25, 36 Faeden, 370 % CPU bei drei parallelen Jobs): ChunkOuterProduct 43 %, GetCell 19,5 %, pthread_mutex_lock/unlock 13,5 % -> Kandidat dichte Kameramatrix.
  Varianten-Skript `tools/versuche/mt_eng_varianten_1120.sh` (redundant, dicht, eng allein) - Einreihung ging mit den Wartern verloren, neu starten wenn die Mapper fertig sind.

## Nachtrag 22:20 - Agent Mapper-Skalierung (Bericht `/media/oem/rcdaten/tmp/hebel_1120/10_mapper_skalierung.md`, Quelltextstellen dort)
- AUSGEZAEHLT (Modell 1681 Kameras, 152 471 Punkte): Spurlaenge Median 5, p99 91, Maximum 684. 0,9 % der Punkte (L > 100) tragen 65 % von Summe(L^2), 2,2 % (L > 50) 78 %.
  Der Engpass sind wenige sehr lange Videospuren. Ein Spurlaengen-Deckel 50 im Ausgleich (Patch ~30 Zeilen, bundle_adjustment_ceres.cc:693-730) spart 67 % bei 13 % weniger Beobachtungen (ANNAHME zur Zeit).
- Hebel 1 (nur Schalter): globale Ausgleiche seltener/kuerzer - `ba_global_frames_ratio/points_ratio 1.4`, `max_refinements 2`, `max_num_iterations 25` = Video-Voreinstellung der Entwickler
  (option_manager.cc:113). Von 100 auf 600 Bilder ~5 statt ~19 Runden. Variante `selten` im A/B-Skript.
- Hebel 2: DENSE_SCHUR bis 1200 Bilder (GetCell = Feldindex). Variante `dicht`. Hebel 4: ITERATIVE_SCHUR ab 300 Bildern (implizit, ~Summe(L)), Variante `iterativ`.
- Zwischenstaende: `--Mapper.snapshot_path <Ordner> --Mapper.snapshot_frames_freq N` schreibt normale Binaermodelle; fortsetzen mit `colmap mapper --input_path <stand> --output_path <neu>`
  (Ergebnis dann OHNE /0). Im A/B-Skript jetzt immer an (alle 100 Bilder); in `iphone_sfm.py` noch NICHT (erst nach dem ersten echten Schnappschuss + Fortsetzungstest).
- `ba_global_ignore_redundant_points3D`: laut Quelltext werden lange Spuren zuerst BEHALTEN -> wenig Gewinn erwartet, aus dem Messplan genommen.
- Eingereiht 22:20 (`mt_eng_varianten`): startet erst, wenn der enge Mapper UND die Schwabentor-Kette fertig sind; rechnet `selten`, dann `dicht` allein am engen Satz.
