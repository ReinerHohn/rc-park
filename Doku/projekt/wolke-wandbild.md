# 🧱 Dichte Wolke, Wandbild, Relief & Öffnungen  ← [PROJEKT.md](../../PROJEKT.md)
Details: `modelle/PIPELINE_FASSADEN.md` (Inhalt: `modelle/inhalt/`) · Skill `fassaden` · Ast [kanten-messen](kanten-messen.md)

## Gilt
- Dichte Wolke bleibt Standard (Nutzer 16.11.), liefert aber nur Lage-Veto, Höhe, Bruchstein-Relief [archiv/AUFGABENLISTE_2026-11-16 Z.29; PIPELINE_FASSADEN Z.5]
- Bruchstein-Kette: `relief_einsatz` → `relief_putz` (Fotofarbe) → `steine_generieren` (nie in Öffnungen, generiert = ANNAHME); Torbogensteine nie generieren (Nutzer 15.11.) [PIPELINE_FASSADEN Stufe fassaden, Z.299]
- Fenster = echte Löcher (`aushoehlen` am Generatorende, WAND_MM 1,2) + Rückwand in Leibungstiefe dahinter (Regel A, 18.11.) [PIPELINE_FASSADEN Z.104, Z.573]
- Generator-Reihenfolge: Rumpfschnitt/Laube vor `aushoehlen`, massive Anbauten danach; Relief in einer Nische erst nach dem Abzug vereinigen [PIPELINE_FASSADEN Z.485; LERNJOURNAL 9, 20]
- Einzelfoto-Bild für Maß/Quader direkt auf der Relief-Wandebene lesen (`steine_aus_foto --foto`), nie über ein LoD2-Ortho [PIPELINE_FASSADEN Z.269ff]

## Versucht
**Dichte Wolke (PatchMatch, Fusion, Tiefe)**
- 15.11. · PatchMatch `window_step` 2 (Stufe schnell) → ✓ Methode · 2,5× schneller, −11 % Punkte, Abweichung Median 1,3 cm [archiv/STAND_2026-11-14 Z.122]
- 15.11. · PatchMatch 10 statt 20 Quellbilder → ✗ verworfen · nur 19 % schneller, −23 % Punkte; schlechter als window_step 2 [NICHTS_GEBRACHT]
- 19.11. · Fusion `min_num_pixels` 8 → 3 → ✓ Standard · fünffache Punkte, Wand 56 → 76 % belegt, Fehlpunktanteil gleich [LOGBUCH_KETTENTEST_2026-11-19 17:15]
- 19.11. · PatchMatch Fenster 11 + `filter_min_ncc` 0,05 → ⏸ zurückgestellt · Putz 99 % belegt, aber 2,4-fache Zeit; Nutzerentscheid [ebd.]
- 19.11. · Wolken-Kontrollbild auf weißem Grund → ⚠ Falle · leere Putzflächen wirkten wie Wand; immer dunkler Grund [ebd.]
- 19.11. · Tiefenkarten unstabiler Kameras (Fernclip) mitfusioniert → ✗ verworfen · schiefe, zu große Häuserzeile; `dicht_bildwahl --ohne unstabil.txt` [ebd. 09:57]
- 19.11. · Feinstufe im Ordner der Stufe schnell → ⚠ Falle · `geom_consistency` nutzt still gefilterte Karten; jetzt Abbruch rc 5 [ebd.]
- 18.11. · Fortsetzung nach Platte-voll → ⚠ Falle · leer geschriebene Tiefenkarten brechen die Fusion (0 Punkte) [LOGBUCH_KETTENTEST Z.28-29]
- 7.11. · CLAHE-/Belichtungs-Sweep für die Wolke → ✗ verworfen · +31 % Punkte, gleicher Fehler, kein neuer Blickwinkel [NICHTS_GEBRACHT Tabelle]
- 7.-8.11. · Netz aus Wolke feiner/geglättet/geschärft, Poisson, pymeshfix, Winding Number → ✗ verworfen · mehr Dreiecke = mehr Rauschen; Lochschließen erfindet Flächen [NICHTS_GEBRACHT BS4, BS20, BS40, BS70, BS106]
- 9.11. · Höhenfeld/Relief-Kachel direkt aus der Wolke → ✗ verworfen · Nutzer „Schrott“: Bögen, Zwickel, Statuen als Brei [NICHTS_GEBRACHT 9.11.]
- 15.11. · `tiefe_lokal` (Teilnetz, 3200 px, Fotowahl für Stereo 4-35°) → ✓ Methode (Versuch) · 1-cm-Relief zeigt Fugen; Fotos vom selben Fleck (< 3°) = 73 % Löcher [PIPELINE_FASSADEN Z.69]
- 16.11. · `tiefe_lokal` 5-mm-Feld Figur / Südwand mit 3 scharfen Fotos → ✗ verworfen · Fusion liefert ~1 cm Punktabstand; unter ~5 guten Fotos lohnt es nicht [NICHTS_GEBRACHT 16.11.]
- 16.11. · zwei 4000-px-Läufe parallel auf 8 GB → ✗ · CUDA OOM; je Lauf 4500 MiB, nichts daneben [NICHTS_GEBRACHT 16.11.]
- 15.11. · fein + grob mischen ohne Entstören → ⚠ Falle · schwarze Sprenkel; Ausreißer > 2,5 cm raus, 3-Zellen-Übergang, Raster 2 cm [PIPELINE_FASSADEN Z.86]
- 20.11. · PatchMatch-Korrektur PR 5041 → ✗ kein messbarer Unterschied
- 20.11. · Depth Anything 3 als Fülltiefe → ✗ kein klarer Gewinn gegen Ebenenfüllung

**Wandbild / Fassadenbild**
- 15.11. · 1-cm-Ortho zellweise aus allen Fotos mischen → ↺ Bezugsfoto + SIFT-Homographie, Median ab 3 Fotos · Fotos 0,1-1 m versetzt, Geister [PIPELINE_FASSADEN Z.53]
- 15.11. · Verdecker per Laub-Farbregel → ↺ Parallaxe-Prinzip · zu speziell; was vor der Wand steht, wandert von Foto zu Foto [PIPELINE_FASSADEN Z.60]
- 16.11. · „Abdeckung in %“ als Brauchbarkeit → ⚠ Falle · Mosaik aus Baum/Nachbarn mit 94 % gab Schein-Fenster [PIPELINE_FASSADEN Nachtrag 18:30]
- 16.11. · Uneinigkeitskarte als Maß „Wand gesehen“ → ✗ verworfen · trennt nicht (Turm 30, Mischzeile 18); nur Fenster-Tor [PIPELINE_FASSADEN Nachtrag nachts]
- 16.11. · Strukturkarte `struktur_<id>` → ⏸ zurückgestellt · Hinweis auf Vorbauten/Mosaik, als Tor zu unscharf [ebd.]
- 16.11. · gebaute Fensterlöcher im Fassadenbild → ⚠ Falle · schwarz, Erkennung 6 → 0; Löcher mit Wandebenenfarbe füllen [ebd. 18:30]
- 16.11. · GPU-Sichtbarkeit `--gpu-sicht` → ✗ verworfen · langsamer (61 vs. 41 s) und weniger streng [PIPELINE_FASSADEN Tempo]
- 17.11. · Embree direkt + Zellrechnung auf GPU → ✓ Methode · 41 → 12 s, 49 Vergleichsbilder bitgleich [PIPELINE_FASSADEN Agentenrunde]
- 16.11. · Ortho „hängt auf einem Kern“ → ⚠ Falle · Kameras bis 350 000 km entfernt; Stapel per faulthandler holen, nicht raten [NICHTS_GEBRACHT 16.11.]
- 17.11. · `wand_feinausrichtung` (Bandpass, Phasenkorrelation, NCC-Feld) → ✓ Methode · Restversatz 1-2,5 → 0,2-0,5 cm, Fugen-F1 0,417 → 0,431 [PIPELINE_FASSADEN Z.528]
- 17.11. · Versatz je Foto in ganzen cm zum Scan rollen → ✗ · Fotos laufen wieder auseinander; ein gemeinsamer Versatz [NICHTS_GEBRACHT 17.11.]
- 17.11. · DIS-Fluss als Restversatz-Probe → ↺ Phasenkorrelation je Kachel · bei anderem Licht unbrauchbar [ebd.]
- 17.11. · bilineares Neuabtasten → ↺ kubisch · verwischt schon bei Feld 0 [ebd.]
- 17.11. · Feinausrichtung an glattem Putz / Fotos aus Jahrzehnten → ⚠ wirkungslos · nur 2-11 % vertraut; braucht gleiche Steinzeichnung [ebd.]
- 18.11. · wahres Ortho mit Netztiefe (`--proj_tiefe 1`) → ↺ affiner Konsens (Medoid + ECC) · 5-cm-Netztiefe verbiegt Rahmen in Schrägfotos [NICHTS_GEBRACHT 18.11.]
- 16.11. · Einzelfoto-Ortho auf LoD2-Ebene für Quader/Maße → ↺ `steine_aus_foto --foto` · Ebene bis 0,75 m daneben, Inhalt 0,2-1 m verschoben [PIPELINE_FASSADEN Z.288]
- 16.11. · `fassade_ein_foto auto` (schärfstes vertrauenswürdiges Foto, Verdecktes aus) → ✓ Methode · kennt aber keine Bäume, Ergebnis ansehen [PIPELINE_FASSADEN Lehren]
- 16.11. · `fassade_zylinder` Abwicklung Rundturm (1 cm) → ✓ Methode · 74 % gesehen, zwei Schlitze und Tür neu gefunden [PIPELINE_FASSADEN Z.276]
- 16.11. · Auflösungsgrenze für leere Wand lockern → ✗ verworfen · Mischbild fremder Dächer aus falschen Videoposen [PIPELINE_FASSADEN Stufe seiten]
- 16.11. · Bauteil aus unscharfem Schattenfoto gelesen → ✗ · „Bogenfenster Ost“ existierte nicht; zweites/scharfes Foto nötig [PIPELINE_FASSADEN Lehre 5]

**Relief, Bruchstein, Putz, Fugen**
- 15.11. · Putz eben über Fotofarbe (`relief_putz`) → ✓ Methode · Eckquader behalten Relief, Grenze gezahnt wie im Foto [PIPELINE_FASSADEN Stufe fassaden]
- 17.11. · `putz_eben` (Zellen < 5 cm am 1-m-Niveau) → ✓ Methode · Netzrauschen 6,6 cm machte Putzfassaden zu Brei [PIPELINE_FASSADEN Katalog]
- 16.11. · „Stein = nicht Putzfarbe“ an farbigen Häusern → ⚠ Falle · alles wird Stein; Tor „ist das Quaderwerk?“ fehlt [PIPELINE_FASSADEN Härtetest]
- 16.11. · Fugen per Helligkeitsschwelle / Hesse-Grat → ✗ verworfen · fand oben fast nichts bzw. Bossen überstimmen Fugen [PIPELINE_FASSADEN Z.124]
- 16.11. · Schichtmodell `--schwelle` 0,8 → ↺ 2,4 + Mindestabstand 16/20 cm · erfand Ziegelraster; Wert an einem Bau eingestellt [ebd.]
- 16.11. · Einzelfoto-Steine ohne Gegenfoto → ↺ Gegenfoto-Korrelation < 0,25 = keine Daten · Baum wurde zu Steinen [PIPELINE_FASSADEN 15:00]
- 16.11. · Steine aus 6-cm-Foto → ↺ `--streng` · Holzgerüst wurde Quader; > 2 cm/px oder ohne Gegenfoto kein Ergebnis [PIPELINE_FASSADEN Härtetest]
- 16.11. · `relief_quader_eben` → ✓ Methode · nur für glatt behauene Quader, nie Bruchstein [PIPELINE_FASSADEN Z.107]
- 11.11. · Depth Anything V2 als metrische Höhe (Einzelbild) → ✗ verworfen · Korrelation 0,16, erfindet 4 cm auf glattem Träger [NICHTS_GEBRACHT 11.11.]
- 17.11. · Mono-Relief kachelweise als Hochpass, Lage/Maßstab vom Scan → ✓ Methode · Fugen-F1 0,34 → 0,42 (Zufall 0,28); ganzes Feld: Korr. 0,04 [PIPELINE_FASSADEN Z.496]
- 17.11. · Mono auf Putz → ⚠ Falle · Tiefenmodell erfindet Relief aus Farbe; Putz immer Scan [ebd.]
- 17.11. · Mono-Entzerrung auf Ebene statt Relief → ↺ `--auf_relief 1` · Parallaxe gab Doppelstrich an vorspringender Tafel [PIPELINE_FASSADEN 17.11. abends]
- 17.11. · Drähte hart ausschneiden / Telea / `cv2.inpaint` float32 → ✗ verworfen · Doppellinien, Rinnen, Unsinn; weich ausblenden [ebd.]
- 17.11. · Feinpunkt-Anker skaliert Mono neu → ✗ nur Gegenprobe · Regressionsdämpfung, F1 sinkt [NICHTS_GEBRACHT 17.11.]
- 17.11. · Schattierungsmaß `schatten_tor` (Lambert) → ✗ verworfen · trennt Brei nicht (6/9); Albedo dominiert [ebd.]
- 17.11. · `relief_bereinigen` (Klumpen → Wandniveau, gerade Gesimse bleiben) → ✓ Methode [PIPELINE_FASSADEN Runde 3]
- 24.11. · Ortsteine/Eckverzahnung aus Wandbild-Farbe (`tools/ortsteine.py`, in `fassaden_kette.anbauen`) → ✓ Methode · Schwabentor 8 Kantenzonen (f00/f01/f03), Kanten im Modell gezahnt; Einzelbilder `ortho_*_einzeln` NICHT ausgerichtet (bis 5 m versetzt, Gegenseite) → Klassen aus dem Mosaik, Einzelbilder nur Bestätigung; LoD2-Kante 0,3–0,5 m neben Fotokante; Vorsprung meist unter Sweep-Auflösung → ANNAHME Druckmaß 3,5 cm [PIPELINE_FASSADEN Nachtrag 24.11.]

**Fenster, Öffnungen, Rückwand, Vorbauten**
- 15.11. · OWLv2-Parsing mit Abstimmung + `fenster_aus_parsing` → ✓ Methode · 6 von 6 Fenstern, 1-4 cm gegen Handmaß [PIPELINE_FASSADEN Stufe fenster]
- 16.11. · feste Schwelle 3 Stimmen → ↺ ≥ 50 % der sehenden Fotos · warf bei 3 Fotos 9 von 11 Fenstern weg [PIPELINE_FASSADEN Härtetest]
- 7.11. · Fenster aus Wolken-Ortho, CMA-ES, Nische ins Wolkennetz → ✗ neutral · Foto-Diff sieht 4-10-cm-Nischen nicht [NICHTS_GEBRACHT BS25-BS33]
- 7.11. · Wiederholungssuche Template/Autokorrelation → ✓ Methode · 5 Treffer 0,89-0,95, Periode 2,86 m [NICHTS_GEBRACHT BS28, BS29]
- 17.11. · `form_aus_wandbild` (k-means Lab + Tiefe je Klasse) → ⏸ Schalter `FORM_WANDBILD=1` · feinteil +0,01, am Foto wellige Kanten [NICHTS_GEBRACHT 17.11.]
- 17.11. · Lab-Abstand + Otsu als Lochentscheid → ↺ k-means + Tiefe · Goldrahmen verschmolz mit Glas [ebd.]
- 17.11. · Median mehrerer Fotos bei Restversatz > 1 cm → ✗ · Geisterkanten; bestes Einzelfoto als Rückfall [ebd.]
- 18.11. · `kanten_einrasten` (Gerade als Ganzes an stärkste Kante) → ✓ Methode · Topologie aller 5 Fenster richtig, robust gegen Bleiruten [PIPELINE_FASSADEN 18.11.]
- 18.11. · Rückwand in festem w-Band → ↺ Tiefenprofil je Feld (Manifold.slice) · Relief lag 0,12 m vor LoD2 [NICHTS_GEBRACHT 18.11.]
- 18.11. · Öffnung per Otsu-Lab bzw. nur Helligkeit → ↺ dunkler UND Farbabstand · Rahmen fehlten bzw. Gewölbeschatten wurde Loch [ebd.]
- 18.11. · Öffnungstiefe aus Parallaxe bei NCC < 0,2 → ✗ · Tür 0,14 statt 0,39 m; Ersatzquelle benennen [ebd.]
- 18.11. · Innenwand-Sweep über ganze Fassade → ↺ 1,26-m-Kostenfenster nur in Bogenkernen · Spitze sonst nur 1,8× Hintergrund [ebd.]
- 18.11. · Leibungstiefe aus zwei Gegenrichtungs-Fotos → ✓ Methode · 0,14 / 0,19 m nicht mitteln [PIPELINE_FASSADEN Z.580]
- 16.11. · Spitzbogen: Sturz → Vier-Zentren → zwei Kreisbögen → ✓ dritte Fassung · Bogenform immer neben Foto prüfen [PIPELINE_FASSADEN 15:00; NICHTS_GEBRACHT 11.11.]
- 17.11. · `oeffnungen_bogen` (Kasten + Durchblick + Formfit) → ✓ Methode · Tordurchfahrt Nord ±0,35 m; Arkadenreihen noch nicht [PIPELINE_FASSADEN Agentenrunde]
- 16.11. · Vorbauten per Ebenen-Sweep `fassade_tiefe` → ⏸ nur Hinweis · Nord belastbar; Baum/ein Standort/LoD2 2,5 m daneben → Tor lehnt ab [PIPELINE_FASSADEN Z.182, Z.384]
- 23.11. · Erkennerkasten = Öffnung (1122o: Gitterfenster 2,8×3,1 m, Schlitz als 1,28-m-Rundbogen, Tür nie gebaut, Treppenturm als „Bogen“) → ↺ `loch_gewaende.py` (Loch = dunkle Komponente, Gewände = Nicht-Wand-Farbe am Loch, Tiefe je Zelle gegen Wandring außerhalb) + `bauteile.loch_gewaende_spaet` (Schnitt auf der echten Oberfläche nach Turm/Vorbau) + `wand_anteil` (Zone außerhalb des Fassadenpolygons = Körper davor) · Kopie: Loch 1,05×1,83 / 0,14×0,87 / Tür 0,86×2,11 m; Tür 0,67 m vor der LoD2-Facette [Agent 23.11., test_loch_gewaende]

## Offen
- `tiefe_lokal`: Abdeckung (4000 px, Tiefenkarten statt Fusion), Figuren-Feld, Aufnahme als Kettenstufe (Stand 15.11.)
- `fassaden_kette.anbauen()` setzt `<wand>_mono.npz` noch nicht ein; Stufe `--fotosteine` nur syntaxgeprüft (Stand 16./17.11., ungeprüft)
- Tor „ist das überhaupt Quaderwerk?“ für farbige Häuser; belastbares Maß „Fotos zeigen dasselbe“ (Strukturvergleich) (16.11.)
- Gegenfoto-Verdeckertest: ob 41 % ausgeblendet an West zu streng ist, ungeprüft (16.11.)
- Fensterformen als Geometrie: Bogen, Maßwerk, Sechseck-/Butzenraster; Kielbogenköpfe noch als Schräge; Profil-Stufenhöhe ANNAHME (15.-18.11.)
- `fassade_tiefe`: Verdeckung, Fotowahl nach Standortabstand, Kandidaten automatisch vermessen (16.11.)
- `fassade_zylinder`: Parsing auf der Abwicklung, helle Schlitze werden nicht erkannt (16.11.)
- Unscharfe Fotos aus der Fotowahl der Feinausrichtung werfen (17.11.)
- `dicht_bildwahl`: Obergrenze nach Platz; PatchMatch-Zwischenweg (Fenster 9, window_step 3) und „Wand-Zellen belegt“ als Tor prüfen (18./19.11.)
- Rückwand schwab_v3: Plattenecke 8 cm verzogen, Ursache ungeklärt (18.11.)
- Wandbild auf gekrümmtem Rundbau (Turmtür f04): Ortho auf der LoD2-Facette, echte Fläche 0,67 m davor → Tür im Modell ~0,3 m seitlich versetzt; Ortho auf Zylinderfläche nötig (23.11.)
- Treppenturm-Kegeldach fehlt (1122o); Türblatt-Segmentbogen und Fenstergitter noch Rechteck/offen (23.11.)
