# RC-Park – Kaufhaus Freiburg: Pipeline-Review und Arbeitsplan
Stand 7.11.2026. Objekt: `modelle/kaufhaus_null5`, Zielausgabe H0 (1:87).

## Kurzbewertung

**Die Mess- und Vergleichswerkzeuge sind weit entwickelt; eine belastbare End-to-End-Pipeline gibt es noch nicht.** Die größte Stärke ist die konsequente Dokumentation von Fehlversuchen und die Trennung von Wolkenmessung, LoD2-Ankern und Fotodiff. Die größten Risiken sind Datenleckage zwischen Rekonstruktion und Holdout, falsch zugeordnete `.vis`-Bild-IDs (inzwischen als Fehler gefunden und korrigiert), sowie mehrere konkurrierende „beste“ Modellstände und Kennzahlen.

| Bereich | Bewertung | Konsequenz |
|---|---|---|
| SfM/MVS und Maße | brauchbare Basis, aber Lagefehler bleiben im Reprojektionsfehler unsichtbar | Kamerazentren, Wolke und externe Anker separat prüfen |
| Netzauswahl | brauchbarer Vergleich auf 6 Holdout-Fotos; Unterschiede klein und Stichprobe klein | keine Siegerbehauptung allein aus dem Mittelwert |
| Details | Arkaden-Fits/3D-Kanten bisher nicht robust genug | Detail nur übernehmen, wenn unabhängige Messung und Bildtest bestehen |
| Validierung | teilweise vermischt: manche „Holdouts“ flossen in die Wolke ein | strikt getrennte Rekonstruktion pro Fold ist Voraussetzung für Aussagen |
| Betrieb | GPU-Semaphor und Fehlproben-Tor sinnvoll; alte OOM-Läufe dokumentiert | jeder Lauf braucht Manifest, Exitstatus, Fehlprobenzahl und Ressourcenangabe |
| Fertigung | STL und Druck sind vorhanden, aber Abnahme-/Druckkriterien nicht als abschließendes Gate gebündelt | Fertigungsfreigabe getrennt von Geometrie-Sieger erklären |

**Wichtigste Korrektur gegenüber älteren Abschnitten:** Der Kurzstand vom 6.11. hält fest, dass der `vis`-Index in vier Werkzeugen falsch über sortierte Namen statt COLMAP-Bild-IDs zugeordnet wurde. Die Korrektur (`freiraum_pruefen.vis_ids`) ist synthetisch geprüft. `carv_kh4_vis` verbessert den Holdout-Mittelwert auf −0,0095 gegenüber −0,0083 vorher, bleibt aber hinter dem Generator (−0,0111); seine Arkadenzählung ist 5 statt Soll 4. Der bisherige Druckstand bleibt deshalb `carv_kh3`. S9 verwarf alle vier automatischen Bogenfits; S10-Teil B erkannte nur 1 von 4 Bögen. Details dazu stehen in `modelle/STAND_2026-11-06.md` und den Registern CU/CW.

Die unten notierten Zahlen sind historische Befunde, keine automatisch aktuellen Statusanzeigen. Der Dokumentstand wurde am 7.11. nicht durch erneutes Ausführen aller Läufe verifiziert. Geänderte und neue Dateien im Arbeitsbaum sind nicht committet.

## 0. Leitgedanken (Nutzerregeln)
- Wolke ist die Wahrheit für Form und Detail; LoD2/DOM1 nur Anker und Endvergleich (`wolke-einzige-basis`).
- Menschenähnliche Formerkennung: Kontur zuerst MESSEN, danach benennen (Rund-/Stichbogen, Fenster), nicht Formfamilie raten.
- Alles loggen (`modelle/NICHTS_GEBRACHT.md`, `VERSUCHSREGISTER_MARTINSTOR.md`, `tools/versuch_log.py`), nichts doppelt versuchen.
- Ergebnisse nur gültig ohne Fehlproben (OOM). Widersprüche Foto/Wolke nicht mitteln.
- CPU und GPU möglichst parallel auslasten; lange Jobs nur über `tools/job_start.sh` (systemd), GPU-Jobs mit `JOB_GPU_MB`.
- Nie in Rückfragen idlen; Zeitabschätzungen ehrlich.

## 1. Eingaben [x]
- 94 registrierte Fotos (Archiv, Handy-Serien a–j, Video-Frames) in `daten/kaufhaus/fotos`. Holdout-Fotos 001 024 054 083 211 234.
- Anker: LoD2, DOM1, DGM1 (`anker3d.json`) nur für Maßstab/Lage.
- Kameras je Foto: `modelle/kaufhaus_null5/messprotokoll/K-<nr>.json` (rvec, t, f_px, cx, cy, k1, standort_xyz, rahmen_verschiebung).
- Neue Quellen geprüft: YouTube-Drohnenclips (nur private Messvorlage, Lizenz), Google Earth (Extraktion verboten), eigenes iPhone 11 (nur 1x-Kamera, JPEG) für Nahaufnahmen; Nutzer fotografiert nachmittags.

## 2. Merkmale, Matching, Bündel (SfM, COLMAP) [x]
- Merkmale (SIFT), Matching, Bündelausgleich: gemeinsam Kameras (Pose, f, k1) und dünne Wolke. Reprojektionsfehler Median 0,56 px (`tools/reproj_je_foto.py`).
- Reprojektionsfehler ist BLIND für Lagefehler (f 2 % = 0,6 m, Wolkenversatz 0,5 m bleiben unsichtbar) → kein Lagemaß (Register BS).
- Fotoauswahl `tools/foto_wichtigkeit.py`: Greedy 66 von 94 = 90 % Abdeckung; NUR für Messschleifen, nie für SfM/dichte Wolke (Register BM).

## 3. Rahmen / Maßstab [x]
- Ausrichtung an LoD2/DGM1 (`SFM-AUSRICHTUNG-*.json`). FALLE (7.11., BS10): die Datei `-alle` passte NICHT zur Wolke `dicht_alle` (Wolke 60 m daneben).
- Korrekt: Rahmen der K-Dateien per Umeyama aus den 94 Kamerazentren (`kameras_unverzerrt.json` ↔ `standort_xyz`), Rest 0,05 cm, s ≈ 1,000001. Implementiert in `tools/wolke_front.py:rahmen_umeyama` und `tools/wolke_ueber_foto.py`.

## 4. Dichte Wolke (MVS) [x]
- `sfm/dicht_alle/fused.ply`: 961 488 Punkte mit Normalen und Farbe, `.vis` (Fotos je Punkt).

## 5. Wolke → Netz (Wettbewerb) [x]
- Kandidaten (Register BR/BS): OpenMVS Delaunay+Graph-Cut `mvs_d03_pl30` (Basis), `pl30_saeule_median` (+ Säulen-Regel), `mvs_default`, `mvs_fein`, Poisson, Carving, Gaussian Splatting (schlecht, Überanpassung), PolyFit, Ebenenzellen (≈0).
- Werkzeug `tools/modell_wettbewerb.py`: Pass 1 feste Maske je Foto (`wettbewerb_kh9g/masken`, Kandidat C), Pass 2 `foto_diff` → `kosten_lr` (kleiner = besser). Raster-Modus `--raster` (GPU, FD_RASTER=1), `--batch` (Punktmodus, 2,1× schneller, `foto_diff_batch.py`).
- Raster-Mittel (23 Fotos, Glättung 0,18): default −0,1139, Säule −0,1086, d03_pl30 −0,1064, fein −0,0864. default vs Säule NICHT signifikant. Feines Netz schlechter.
- Messfallen: Punktfassung degeneriert bei Tele-Foto 073 (70 Modellkanten-px) → Raster als Messziel; vor jeder Auswertung `modellkanten_px` ansehen.

## 6. Kameras prüfen / Ausgleich [~]
- Ausgleich `tools/kamera_ausgleich.py` (Pose je Foto ±1,5°/±0,3 m, Gruppen-f/k1, Gegenhälften-Prüfung, Rauschgrenze 0,008).
- Ergebnis BS3d: 12 gültige Fotos bestehen die Gegenhälften-Prüfung NICHT (Überanpassung), nichts übernommen. Nur Foto 114 trägt (lr −0,019 → −0,134, Vorschlag; K-114 unverändert).
- Synthetisch: `kosten_lr` hat kein eindeutiges Optimum; Zentrum 3–10 cm nicht rückholbar, Rotation erst ab ~0,5° (~20 px) erkennbar.
- ZURÜCKGEZOGEN: „gemeinsamer rx ≈ 0,3° = Netzfehler" (Rastergrenze, Rauschen, nicht validiert).
- Lauf 1 und Lauf 3 (OOM, `--kerne 5/4`) ungültig; Foto 073 ungültig (5,1 % Probenverlust). Fehler war VRAM-Überbelegung durch eigene Parallelität (073 ≈ 3,6 GiB).
- Neu: VRAM-Semaphor (3e-4 MiB/Pixel, Limit 6000 MiB, `AUSGLEICH_VRAM_MB`) + `gueltig_gesamt` (nur wahr bei leerem fehler.log), belegt mit `test_kamera_ausgleich.py --semaphor-test`. Semaphor gilt nur im eigenen Prozess.
- Wolke über Foto (`tools/wolke_ueber_foto.py`, BS10): Wolkenrand ↔ Fotokante median 4,0 px (Foto 114) / 2,8 px (004) gegen Zufall 11 / 6 px → Kamera 114 passt zur Wolke, der 0,36-m-Versatz liegt wahrscheinlich im NETZ. Einschränkung: Wolke entstand aus denselben Kameras (teils zirkulär). Netzkanten-Kennzahl des Tools ist defekt (nicht nutzen). Ausreißerband im Erker ungeklärt.
- Belichtungs-/Kontrast-Sweep: ohne Gewinn (Register BS).

## 7. Detail aus der Wolke: Bögen / Fenster [~; ältere Versuche, Status durch S9/S10 ergänzt]
- Foto-Median-Ortho auf Ebene f02 (`tools/bogen_kontur.py`) VERWORFEN (BS9): zerschmiert, Parallaxe der Laibungen, Kameras nicht einzeln geprüft. `fix_mess` darf nicht ausgewertet werden.
- Neu BS11: `tools/wolke_front.py` – gefärbte Wolke frontal (Orthokamera, z-Puffer aus 3D-Lage, GPU), Abdeckung je Pixel aus `.vis`. Arkaden-Kasten 20,2 × 5,2 m, 1 cm/px (`wolke_front/arkaden/`): die vier Bogenkonturen sind scharf. Belegung/Abdeckung je Höhenband in `front.json` (Belegung nur 0–27 % bei 1 cm: Wolke dünn). Tiefenfenster ±6 m zu groß (Hintergrund/Passanten im Innenfeld).
- `tools/bogen_aus_wolke.py`: Platte um die Fassadenebene (w = 1,27 m, 42 639 Punkte). Loch-Methode scheiterte (Öffnung hängt unten mit leerem Straßenbereich zusammen, 0 Löcher).
- `tools/bogen_unterkante.py`: Laibungslinie als untere Kante des Bogenbandes. Folgt den Bögen im Bild; Zacken an Pfeilern/Zwickeln. Gemeldete Kronen/Pfeiler sind STÖRWERTE, kein Messergebnis.
- Historischer Zwischenstand: robuster Fit je Bogen war hier noch offen. Die später dokumentierten S9/S10-Ergebnisse sind maßgeblich: S9 verwarf alle vier Fits; S10-Teil B fand 1/4 Kurven und bestand den vorab gesetzten Synthese-Gate bei 0,10-m-Voxel nicht. Kein Bogenbauteil freigegeben.
- Fenster (durchhängender Oberrand vs Rechteck), Dachaufbauten: gleiche Konturmethode vorgesehen, noch nicht gebaut. Dach ist nicht planar, braucht Aufnahmen von oben.
- LLM als Plausibilitätsprüfer: geeicht, Treffer 49 % / Nullkontrolle 50 % → nicht tauglich.

## 8. Prüfung / Diff [~]
- `tools/foto_diff.py` (`kosten_lr`, a-contrario; Glättung 0,18 m; Punkt- vs GPU-Raster; Maske fest je Foto, `--maske-kandidat C`), `foto_diff_batch.py`, `fehlteile_finden.py`, Regeln aus `CLAUDE.md` (Pruefstand, Sichtblatt, Zählen am Foto).
- Offen: Regression (`tools/regression.py --pruefen`) nach den Änderungen an `modell_wettbewerb.py`/`foto_diff` noch nicht gelaufen; Leave-One-Out am Diff.
- **Holdout-Leckage beachten:** Die 6 Fotos sind nur dann echte Holdouts, wenn sie weder in SfM/MVS/Wolke noch in Kamera-/Parameteranpassung oder Modellauswahl vorkommen. „Wolke ohne Holdout“ ist für einzelne Läufe dokumentiert, aber nicht durchgehend die Basis aller hier genannten Vergleiche. Die 94-Foto-Wolke ist daher kein unabhängiger Prüfstand für diese sechs Bilder.
- `kosten_lr` ist ein relatives Auswahlmaß innerhalb gleicher Kamera-, Masken-, Raster- und Glättungseinstellungen; es ist kein metrischer Geometriefehler. Werte aus Punkt- und Rastermodus oder unterschiedlicher Glättung nicht in einer Rangliste mischen.

## 9. Ausgabe [~]
- STL 1:87 (H0), 3D-Seite als Artifact (Kaufhaus HdPoLi5E7mvN35aJxhwEHC), Druck Bambu P1S (Slicer-Lektionen in Memory). Vor jedem Druck Teil neben Referenzfoto prüfen (Regel 9b).

## 10. Ressourcen und Betrieb
- Rechner: CPU i7 (28 Threads), RAM 15 GB, GPU RTX 4060 Laptop 8 GB. OOM-Fehler im Ausgleich = VRAM, nicht RAM.
- Jobs: `tools/job_start.sh NAME LOG BEFEHL`, `JOB_GPU_MB`; Datenplatte ≥ 10 GB (Platztor). Große Daten unter `/media/oem/scan/rc-park_null/`.
- Letzter dokumentierter Laufstatus: `rcpark-kh24_raster` (Raster-Wettbewerb, Glättung 0,05, 4 Netze, 23 Fotos, `--kerne 1`, 4500 MiB) lief beim Erstellen des Ursprungstexts. Abschluss/Ergebnis hier nicht verifiziert; vor Auswertung Jobstatus und Artefakte prüfen.
- Cloud (RunPod RTX 4090: 6 vCPU/41 GB RAM; Network Volume 0,07 $/GB/Monat; `--terminate-after`) nur recherchiert, Preise für CPU-Pods nicht verifiziert; nichts gemietet.

## 11. Lizenzen (vor Verkauf prüfen; `modelle/LIZENZ_WERKZEUGE.md`)
- VGGT-1B nur NC, SegFormer teils NC, CGAL-PolyFit GPL, Line3D++/LIMAP offen; LGL-Daten Namensnennung; YouTube nur private Messvorlage; Google Earth nicht extrahieren; Intel librealsense Apache 2.0.

## 12. Fehlschläge / zurückgezogene Aussagen (kurz, Details in `NICHTS_GEBRACHT.md`)
- „073 schlechte Kamera" → Messartefakt (BS3e). „Kameras nicht Hauptfehler" (Lauf 1) → durch OOM ungültig. „Gemeinsamer rx 0,3° = Netzfehler" → zurückgezogen. Bogenkontur aus Foto-Median → BS9 verworfen. Wolkentest mit falscher Ausrichtungsdatei → BS10.
- Rückfrage-Stillstand 04:24–08:15 (≈ 4 h verloren); OOM-Fehlproben kosteten ca. 1,5–2,5 h.

## 13. Verbesserte Reihenfolge: Gates statt paralleler Baustellen

### Gate 0 – Lauf reproduzierbar machen
Vor jeder neuen Modelländerung den Eingangssatz (Fotos samt Hashes, COLMAP-ID-Zuordnung, Kameras, Wolke samt Hash, Masken), Codeversion, Parameter, GPU-Budget und Ausgaben in einem Laufmanifest sichern. Lauf gilt nur bei Exitcode 0, leerem Fehlerlog, null OOM/fehlenden Proben und vollständigen erwarteten Outputs. Keine Werte aus ungültigen Läufen weitertragen.

### Gate 1 – Daten-/Koordinatenbasis einfrieren
1. `.vis`-Mapping über COLMAP-Bild-ID verwenden und für jeden verwendenden Verbraucher einen Zuordnungstest ausführen.
2. Rahmenumeyama der Kamerazentren als Kamera-Registrierung behandeln, nicht als unabhängigen Beweis der Wolkenlage: Kameras und Wolke stammen aus derselben SfM-Kette. Lage gegen unabhängige Boden-/Gebäudeanker prüfen; LoD2 bleibt nur ein Anker je belegter Fläche.
3. Eine kanonische Liste der verwendeten Bilder erstellen. Historische Angaben „94 registriert“ nicht ungeprüft mit neu hinzugekommenen Fotos oder den 92 IDs aus dem S10-Befund gleichsetzen.

### Gate 2 – Fairen Modellvergleich herstellen
1. Holdout-Fotos vor SfM/MVS und jeder Parameterauswahl ausschließen. Für sechs Bilder mindestens sechs Leave-one-out-Rekonstruktionen durchführen oder einen räumlich/zeitlich gruppierten, vorab fixierten Holdout verwenden; nicht nur Bilder aus einer Serie zufällig verteilen.
2. Kandidaten (Generator, `carv_kh3`, `carv_kh4_vis`, ggf. Raster-Netze) mit identischen Kameras, Masken, Auflösung und Diff-Parametern vergleichen. Fehlerproben und `modellkanten_px` je Foto protokollieren.
3. Ergebnis pro Foto plus Median/Mittel und Streuung berichten. Bei n=6 und nicht signifikantem Unterschied keinen eindeutigen Sieger ausrufen. Kandidatenwahl und Schwellen nicht auf denselben Holdout-Ergebnissen abstimmen.
4. Raster-Wettbewerb `kh24` nur auswerten, wenn Jobabschluss, Exitstatus und vollständige Ausgabedateien geprüft sind. Die Angabe „läuft“ aus diesem Dokument ist inzwischen veraltet/unbestätigt.

### Gate 3 – Geometrie und Details
1. Als Ausgangsmesh für Fertigung `carv_kh3` beibehalten, bis ein Ersatz zugleich den Bildvergleich verbessert und den Pruefstand (insbesondere genau 4 Arkaden, Traufe und Wasserdichtheit) besteht. `carv_kh4_vis` ist derzeit kein Ersatz.
2. Arkaden nicht automatisch parametrisch einbauen: S9 lehnte 4/4 Fits ab; S10 3D-Kantenfeld fand 1/4. Nächster sinnvoller Detailversuch ist die korrigierte Wolke/Belegung als Messbasis und eine unabhängig sichtbare Vorderkantenmessung. Das Ergebnis zunächst als separates, reversibles Bauteil testen.
3. Für jeden Detailkandidaten: synthetischer Positiv- und Negativtest, festgehaltene Schwellen vor Echtdaten, lokale Regionsprüfung **und** globale `kosten_lr`-Prüfung. Widerspruch Foto/Wolke nicht mitteln; Messung beibehalten und Widerspruch protokollieren.
4. Fenster und Dach erst nach validierter Arkaden-Methode angehen. Neue Handyfotos getrennt kalibrieren (Zoom/Brennweite, Schärfe, Posevertrauen) und erst nach Registrierungsprüfung in eine neue Wolkenversion übernehmen.

### Gate 4 – Freigabe für Ausgabe
1. Vollständige Regression und Pruefstand auf dem eingefrorenen Modell ausführen; offene Sollfehler explizit ausweisen.
2. Für 1:87 Mindestwand, kleinste druckbare Details, Teilung/Verbinder, Bauraum und Manifoldness im Slicerbericht protokollieren. Visuelle Prüfung jedes Druckteils neben Referenzfoto bleibt Abnahmeschritt.
3. Endlauf mit dem finalen, dokumentierten Fotosatz; Modell-, Kamera-, Wolken- und STL-Dateien über Hashes miteinander verknüpfen. Commit nur auf Auftrag.

## Reviewentscheidungen
- Die Umeyama-Bindung reicht für die starre Rahmenübertragung der Kameras, aber nicht als unabhängige absolute Lagevalidierung der Wolke. Für deren Lage braucht es externe Kontrollpunkte/Anker mit Unsicherheitsbudget; nicht pauschal das gesamte Netz auf LoD2 ziehen.
- Die 4-px-Wolkenrandmessung ist ein Diagnosewert, wegen gemeinsamer Kameras zirkulär und kein unabhängiger Kamera- oder Netzbeweis.
- Arkadenbauteil bis zum Bestehen der lokalen Messprüfung und des fairen Holdout-Tests separat und reversibel halten; erst dann in die Fertigungs-STL vereinigen.


---
# NACHTRAG 7.11.2026 Mittag

## N1. Reviews (Google, Codex) – Bewertung (Details `NICHTS_GEBRACHT.md`)
Richtig und umgesetzt/vermerkt: Wolke↔Foto zirkulär; Holdout nicht unabhängig (flog in SfM/MVS ein, 6 Fotos durch Mehrfachauswahl verbraucht → neue Nutzerfotos von heute Nachmittag als unangetasteter Abschlusstest reservieren); Wettbewerb ohne Konfig-Fingerabdruck/Vollständigkeitsgate; Regression. Falsch/übertrieben: „Vorzeichen kosten_lr geändert", Poisson-Cloudlauf, GPL-PolyFit, Timeout kh24, „VRAM-Blindflug" (job_start hat JOB_GPU_MB/.gpu_lock), „Platte ±6 m". Carving-spezifisch (nicht MVS-Basis): Blockzählung, Voxel/Strahlschritt.

## N2. Bogenform gemessen (BS15) [x Messung, ~ Einbau/Diff]
- Kette: `wolke_front.py` (Frontansicht, Rahmen per Umeyama) → `bogen_aus_wolke.py` (Platte w = 1,27 m ± 0,25, 2 cm/px, Kasten z ≤ 5,2) → `bogen_kontur_robust.py` (weiße Streupunkte weg, erste Leerzeile mit ≥ 1 m Leere darunter) → Kreisfit (RANSAC + LSQ).
- Ergebnis (gemessen, dann benannt): 4 Öffnungen, Mittelpunkt u −6,41 / −2,03 / 2,32 / 6,67 (Teilung 4,38 / 4,35 / 4,35 m), Mittelpunkt z 2,88–2,99, R 1,87–1,95 m, Scheitel 4,84–4,90 m, RMS 1,6–4,4 cm → Rundbögen (Mittelpunkt ≈ Kämpferhöhe). H0: R 21,8 mm, Teilung 50 mm.
- Zählung am Foto (Regel 9): `Z-004-003` = 4 Bögen. Sichtbild bestätigt Rundbögen mit Goldlinie.
- Einbau: `fix_wolke_rund.stl` (Basis `mvs_d03_fix`, wasserdicht, 4 Öffnungen, t_front −0,5 / t_back −3,7 wie S9). Der S9-Fit (Breite 4,23 m, Kämpfer 2,28 m) weicht von der Wolkenmessung deutlich ab – Diff entscheidet.
- Diff läuft: `rcpark-bogen_diff2` (Basis B, S9 R, Wolke W; global + Region; 22 Fotos ohne 073). Behalten nur bei Gewinn in der Region UND ohne Verschlechterung eines Fotos.
- Fallen: Kasten-Oberkante 5,2 m schneidet Kronen (~5,0 m) fast ab; Histogrammgipfel der Ebene springt bei größerem Kasten (`--w` fest setzen); Loch-Methode scheitert (Öffnung hängt unten mit Straße zusammen).

## N3. Netzwettbewerb (BS11) [x]
- Raster, Glättung 0,05, 23 Fotos: d03 −0,1128, Säule −0,1127, default −0,0997, fein −0,0484. Stabilität (Bootstrap/LOO/Halbierung): d03 = Säule gleich; default je nach Glättung vorn/hinten, nicht signifikant gegen Säule; fein sicher schlechter. KEIN stabiler Einzelsieger.
- Endlauf über alle 94 Fotos (d03, Säule, default; Glättung 0,18): `rcpark-kh25_alle94` läuft.
- `modell_wettbewerb.py`: `konfig.json` (STL Größe+mtime, Fotoliste, Raster, fd-arg, Basis) → ABBRUCH bei geänderter Konfiguration im selben Ordner; `gueltigkeit.json` (vollständig nur wenn jeder Kandidat alle Fotos hat), Versuchslog-Status `unvollstaendig`, Exit 3. Regression Martinstor + Kaufhaus: identisch.

## N4. Kameraprüfung [~]
- `kamera_unabhaengig.py` (Leave-One-Out-Neuregistrierung, Sim3-Eichung): Rauschboden ~1° / 20–100 px; Foto 114 (0,09 m, 1,17°, 40 px) kein Ausreißer; kein Befund Kamera-vs-Netz (BS12). Erste Version hatte einen Eichfehler (Gesamtsystem driftet) und war ungültig.
- Ausgleich BS3d: nichts übernommen; Aussage „gemeinsamer rx 0,3°" zurückgezogen.
- Unabhängige Prüfung braucht entweder SfM ohne Holdout-/Testfotos (teuer) oder die neuen Fotos (iPhone 11, 1x, JPEG, Originale; EXIF prüfen).

## N5. Recherche 7.11. (Websuche, nur Titel/Zusammenfassungen gelesen, nichts reproduziert)
Abgleich mit Register: das meiste ist schon erledigt oder lizenzgesperrt.
| Fund | Stand bei uns | Bewertung |
|---|---|---|
| Öffnungen als Lücken in Fassadenebene/Querschnitten + RANSAC-Ebenen (Laser Journal 2025; arXiv 2303.05998 Konflikt-Klassifikation; MDPI 2025 Faster R-CNN auf Merkmalsbildern) | genau das haben wir selbst gebaut (Platte + Leerstellen) | stützt die Methode; NEU daraus: Regeln zur Wiederherstellung verdeckter Öffnungen (LKW, Passanten) und Symmetrie-/Teilungsprüfung (arXiv 2106.00912 translationssymmetrisches Fassadenparsing) → als Prüfung „gleiche Teilung" bereits genutzt (4,35 m) |
| Bogen-/Rundfenster in der Literatur | nichts Direktes gefunden | unsere freie Kontur + Kreisfit ist Eigenbau; keine Fremdreferenz |
| Pixel-Perfect SfM (pixsfm, Lindenberger ICCV 2021): featuremetrische Verfeinerung von Keypoints, Punkten und Posen, subpixelgenau, nutzt hloc/COLMAP | NICHT versucht, nicht im Register | einziger neuer Hebel für Kamerapräzision (offene Frage 114). RISIKEN: Paket pinnt COLMAP 3.8 (wir pycolmap 4.2.1) → Versionskonflikt; Lizenz nicht geprüft; 8 GB VRAM bei 94 hochaufgelösten Fotos unklar → zuerst Lizenz + Machbarkeit an 10 Fotos, Gegenprobe synthetisch |
| LIMAP / Line3D++ (3D-Linien aus Mehransichten, nutzt SfM-Punkte, Parallelität/Orthogonalität) | Eigenbau `kanten_3d.py` (930 Linien); LIMAP nicht getestet, Lizenz offen | Kandidat für gerade Kanten (Gesims, Pfeilerkanten); für Bögen ungeeignet (nur Geraden) |
| 2DGS/3DGS-Mesh, Chamfer-Fallen (SolidGS arXiv 2412.15400; Chamfer misst Vollständigkeit nicht) | Gaussian Splatting getestet: schlecht (BR), Lizenzen NC | nicht weiter; Hinweis: kosten_lr ebenfalls kein Geometriemaß → drei Gates (Codex) |
Nicht gefunden: direkter MVS-vs-2DGS-Vergleich für Gebäude/Putzfassaden; Gewinnerwartungen aus 2DGS/NeuS bleiben Hypothesen.
Quellen: https://arxiv.org/pdf/2303.05998 · https://arxiv.org/pdf/2106.00912 · https://arxiv.org/pdf/2108.08291 (pixsfm, https://github.com/cvg/pixel-perfect-sfm) · https://arxiv.org/abs/2303.17504 (LIMAP, https://github.com/cvg/limap) · https://arxiv.org/pdf/2412.15400

## N6. Verbesserungen, die sich aus dem heutigen Wissen ergeben (Reihenfolge)
1. Bogen-Diff auswerten; bei Gewinn Bauteil übernehmen, 3D-Seite aktualisieren, Bögen aus dem Netz-Stand als neue Basis. (läuft)
2. Gleiche Plattenmethode für Pfeiler (Querschnitte), Brüstung/Konsolen, Fenster (Öffnung zurückgesetzt, Wolke dünn → Verdeckungsregeln aus der Literatur); jedes Bauteil einzeln im Diff.
3. Frontansicht/Platte mit Abdeckung je Pixel aus `.vis` nutzen, um Lücken (LKW) von echter Leere zu trennen (Wolkendichte < 3 Fotos = unbekannt, nicht „leer").
4. Dreifach-Gate statt nur kosten_lr: Bildkantenvergleich, unabhängige 3D-Messung gegen Kontrollflächen/-punkte (Anker), Fertigungsprüfung.
5. Kamera: pixsfm-Machbarkeit (Lizenz, Version, VRAM) erst nach Nutzerfotos; solange gilt „Kameras nicht nach dem Netz verschieben".
6. Neue Fotos (heute Nachmittag): als Abschlusstest reservieren, EXIF prüfen, Bogenzone neu bewerten.
7. Endlauf mit allen 94 Fotos nur mit gültiger Kamera und gueltigkeit.json = vollständig.

## Nachtrag N7 (7.11. nachmittags): Fenster der ebenen Fassade (Ortho-Ablauf, noch NICHT im Diff bewiesen)
Ablauf (Werkzeuge: tools/wolke_front.py, tools/fenster_fit.py; Daten /media/oem/scan/rc-park_null/wolke_front/fenster/):
1. **Front-Ortho** der farbigen Wolke auf die Fassadenebene (Normale 0,344/0,939, 2 cm/px, nahester Punkt je Zelle + 5-cm-Farbschicht). Achtung: front_farbe.png ist per cv2.inpaint GEFUELLT; echte Messung nur front_farbe_roh.png (Fenster 66-77 % belegt, unteres Drittel 53-65 %, BS27). Fits nur auf belegten Zellen (fenster_fit.py --belegt).
2. **Fenster finden**: Dunkelsegmentierung (Glas) -> 5 Fenster ~2,3 x 2,8 m, z 6,6-9,4 m. Anzahl ist Kandidat, Sollwert nur per Fotozaehlung (Regel 9).
3. **Wiederholungen ohne Vorlage**: Autokorrelation (BS29: Perioden 2,86/5,74/8,62/11,46 m); mit Vorlage: Template Matching (BS28: genau 5 Treffer 0,89-0,95, Vorlage zirkulaer).
4. **Ausrichten + Median** (Kreuzkorrelation; Streuung 13,5 -> 9,4 Grauwerte), 5. **parametrisches Fenster** (10 Parameter, CMA-ES pycma, Mehrfachstart; BS26), 6. **3D-Koerper** (Laibungstiefe aus Wolke) + 7. **Diff-Gate** (Region, Holdout-Fotos; nur behalten wenn Region gewinnt ohne Foto zu verschlechtern) + 8. Abnahme/Vergleich Druckteil/Foto: Schritte 6-8 OFFEN.
Plan Erker: Ebenen per RANSAC, je Flaeche eigenes Ortho, Spiegelung links/rechts (siehe NICHTS_GEBRACHT PLAN 7.11.). Recherche: modelle/RECHERCHE_2026-11-07_FENSTER.md (Top 5), RECHERCHE_2026-11-07_MESH_KANTEN.md.
Weitere Ergebnisse 7.11.: Bogen-Diff-Verlust nicht durch Plattenhoehe/t_back/Kamera-Versatz (BS21-BS21d); Wasserdicht-Reparatur mvs_default gescheitert ausser Offset-Schale (BS20-BS23, Diff offen); Sieger haengt von Glaettung ab (BS22: g0,05 Saeule, g0,18 default).
