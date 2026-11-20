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
