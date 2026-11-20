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
