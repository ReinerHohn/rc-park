# Recherche: neue Verbesserungen fuer Qualitaet und Tempo (Stand 19./20.11.2026)

Nur gelesen. Nichts installiert, nichts gestartet, nichts committet.
Vorher abgeglichen mit: `reports/*.md` (6 Berichte), `modelle/LIB_UPDATES_2026-11-19.md`, `modelle/NICHTS_GEBRACHT.md`, `modelle/LIZENZ_WERKZEUGE.md`, `modelle/GLOBALER_MAPPER_STABIL.md`, `modelle/LOGBUCH_KETTENTEST_2026-11-19.md`, `modelle/RECHERCHE_VERBESSERUNG_2026-11-17.md`.
Nicht wiederholt (schon vorgeschlagen oder gemessen): AnyCalib als Prior (S3/S4 schlechter, nur Startwert S5 gleichauf), MegaLoc als Idee, LoMa-Leistungszahlen, Caspar, keep_max_num_tracks, APD-MVS, MoGe-2, Depth Pro, Prior Depth Anything, MapAnything-apache, VGGT-Commercial, VidMap-Prinzip, Cusift (#4971) als Beobachtungspunkt, Kovarianz-Drehungsmittelung, FlexGlue-Grundtest.

Kennzeichnung: **[belegt]** = steht so in Quelle/Benchmark; **[plausibel]** = eigene Einschaetzung, nicht gemessen. **Lizenz geprueft** = heute an LICENSE-Datei, README-Lizenzabschnitt oder GitHub-Lizenz-API gelesen; **ungeprueft** = nur Sekundaerquelle oder gar nicht.

Wichtigster Lizenzbefund vorab (neu): **Die LoMa-Gewichte, die COLMAP automatisch laedt, sind NICHT die "kommerziellen".** Siehe Massnahme 3.

---

## Rangliste nach Nutzen je Aufwand

### 1. Lot je Bild als Schwerkraft-Vorgabe in den globalen Mapper (`GlobalMapper.ra_use_gravity`)

- **Was es tut:** Der globale Mapper kann je Bild eine bekannte Schwerkraftrichtung (im Kamerasystem) verwenden. Dann muss die Drehungsmittelung fuer diese Bilder nur noch den Kurswinkel (1 Freiheitsgrad) bestimmen statt drei Winkel. Mit `ra_use_stratified` loest er erst das 1-Grad-System fuer Paare mit Schwerkraft, dann das volle System fuer den Rest. Kippen und Rollen koennen dann nicht mehr "wegdriften"; genau das ist unser Fehlerbild ("Kameras zu hoch", gekippter Rahmen BS150, Laufrauschen an der Peripherie).
- **Woher die Schwerkraft kommt (zwei Wege):** (a) eigenes `tools/lot_aus_fotos.py` macht schon den Fluchtpunkt der Senkrechten je Foto (LSD + RANSAC). Daraus wird mit K die Richtung im Kamerasystem, gut fuer Tuerme mit vielen senkrechten Kanten, lizenzfrei. K stammt aus EXIF bzw. AnyCalib-Startwert oder aus einem ersten Mapperlauf. (b) GeoCalib schaetzt Schwerkraft und Brennweite aus einem Einzelbild. Es gibt eine offene COLMAP-PR, die das als ONNX einbaut und `PosePrior::gravity` je Bild fuellt.
- **Quellen:** Eigener Bau hat die Schalter schon. Im Quelltext von ce2b5ab stehen `GlobalMapper.ra_use_gravity`, `GlobalMapper.ra_use_stratified`, `GravityRefiner.*`, das Feld `gravity` in der Tabelle `pose_priors` (`scene/database_sqlite.cc`) und `refine_gravity` in `exe/sfm.cc`; pycolmap 4.2.1 hat `run_gravity_refinement`. PR GeoCalib: https://github.com/colmap/colmap/pull/4797 (offen seit 01.10.2026). Bugfix Schwerkraft-Verfeinerung (schon gemergt 30.09.): https://github.com/colmap/colmap/pull/4788. GeoCalib: https://github.com/cvg/GeoCalib
- **Lizenz:** COLMAP BSD (geprueft frueher). Eigener Weg (a): eigener Code, frei. GeoCalib: Code Apache-2.0, Gewichte `geocalib-pinhole`/`geocalib-distorted` **CC BY 4.0** (geprueft heute, README-Abschnitt License + GitHub-API). Kommerziell erlaubt, Namensnennung noetig.
- **8 GB:** ja. Der Fluchtpunktweg ist reine CPU. GeoCalib ist ein kleines Netz (ungemessen, plausibel deutlich unter 2 GB).
- **Belegt / plausibel:** Gravity-gestuetzte Drehungsmittelung stammt aus GLOMAP/Theia [belegt als Verfahren]. GeoCalib-README, MegaDepth (Internetfotos): Roll-AUC 82,6/90,6/94,0 und Pitch-AUC 32,4/53,3/67,5 bei 1/5/10 Grad [belegt]. Pitch aus einem Einzelbild ist also nur auf einige Grad genau. Bei Turmfotos mit vielen langen Senkrechten ist der Fluchtpunkt vermutlich genauer [plausibel]. Ein Brennweitenfehler von 6 % ergibt bei 20 Grad Aufblick rund 1 Grad Schwerkraftfehler [eigene Rechnung]. Ob das den GPS-Rest senkt, ist ungemessen.
- **Erster Versuch:** Martinstor V0-Datenbank kopieren. Stufe 1 ist der normale Lauf. Danach fuer alle registrierten Kameras mit mindestens 15 langen Senkrechten die Lotrichtung im Kamerasystem in `pose_priors.gravity` schreiben (nur Richtung, Position leer). Dann den globalen Mapper mit `--GlobalMapper.ra_use_gravity 1 --GlobalMapper.ra_use_stratified 1` zweimal laufen lassen. Messgroessen: GPS-Tor (Median, Anteil >15 m), Lotabweichung des Rahmens (`lot_aus_fotos.py` gegen den Rahmen), Zahl der springenden Kameras im Konsens-Schnitt und Laufstreuung (zwei Laeufe). Gegenprobe Schwabentor S0.
- **Vorsicht:** Die Schwerkraft muss im COLMAP-Kamerasystem stehen (x rechts, y unten). `gravity_dir` ist voreingestellt (0,1,0). Erst an 5 Bildern pruefen, ob das Vorzeichen stimmt (Mapper-Ergebnis gegen Lot).

### 2. FlexGlue schneller: frueher abbrechen und Paare vorher eindampfen

- **Was es tut:** FlexGlue bricht nicht-kovisible Paare nach den Schichten 2, 4, 6 oder 8 (von 9) ab, wenn die Kovisibilitaet unter `min_covisibility * (1 - early_stop_decay)^(9 - Schicht)` liegt. Mit kleinerem `--FlexGlueMatching.early_stop_decay` (Voreinstellung 0,5) bricht es frueher ab, ein Doppelgaenger-Paar kostet dann nur noch etwa 2/9 der Transformerzeit. Ausserdem kostet jedes Bild nur einmal den DINOv3-Deskriptor (512x512), wenn er im Cache liegt (`--FlexGlueMatching.feature_cache_size`, ca. 4 MB je Bild auf der GPU). Die Paarliste sollte deshalb nach Bild sortiert laufen, damit der Cache trifft.
- **Quellen:** COLMAP `doc/features.rst` (main, heute gelesen): https://github.com/colmap/colmap/blob/main/doc/features.rst ; FlexGlue README (Abschnitt "Look-alike pairs and early stopping"): https://github.com/cvg/FlexGlue
- **Lizenz:** wie schon geprueft (MIT, DINOv3-Lizenz fuer das Grundnetz, laut LIZENZ_WERKZEUGE.md verkaufstauglich).
- **8 GB:** ja; `--FlexGlueMatching.num_inferences_per_gpu 1` senkt den Speicher weiter [belegt, Doku].
- **Belegt / plausibel:** Doku, ETH3D DSLR, 22 569 Paare: Bei Voreinstellung brechen 35 % der Paare frueh ab, nur 6 von 10 288 echten Paaren gehen dadurch verloren [belegt]. Wie viel ein Wert von 0,2 bis 0,3 bei unseren Videobildern spart und was er an echten Paaren kostet, ist nicht gemessen [plausibel: deutlich schneller bei vielen Fremdpaaren].
- **Erster Versuch:** Den gleichen Nord/Sued-Testsatz wie am 19.11. nehmen (3289 Querpaare, 3000 Kontrollpaare, k6000.db). Laufen lassen mit `early_stop_decay` 0,5 (Referenz), 0,3 und 0,2, dazu eine Paarliste nach Bild-ID sortiert. Messgroessen: Sekunden je abgewiesenem Paar, Sekunden je echtem Paar, Rueckhalt echter Paare (Ziel mindestens 99 %), Rate durchgelassener Querpaare.

### 3. Lizenz-Weiche LoMa: COLMAP laedt die Gewichte mit nicht-kommerziellen Trainingsdaten

- **Was es tut:** Das ist eine Schutzmassnahme vor jedem LoMa-Versuch (der Bericht vom 18.11. empfiehlt LoMa unter Punkt 7). Laut LoMa-README ist das volle Modell auch auf ScanNet++, Map-free und Mapillary Planet-scale Depth trainiert. Seit 26.09.2026 gibt es zusaetzlich **"Weights trained on only commercially licensed datasets"**: `commercial_loma_B.pt`, `commercial_loma_L.pt`, `commercial_loma_G.pt`, `commercial_loma_descriptor_G.pt`. Der COLMAP-Quelltext (`src/colmap/feature/resources.h`, `retrieval/resources.h`, eigener Bau) laedt aber `loma_detector.onnx`, `loma_descriptor_dedode_b/g.onnx`, `loma_matcher_B.onnx` usw. Das sind die normalen Gewichte, nicht die kommerziellen, und auch der LoMa-Vokabelbaum stammt von ihnen. Die kommerziellen Gewichte gibt es nur als .pt. Fuer COLMAP muesste man sie selbst nach ONNX exportieren; einen Exportweg nennt das README nicht.
- **Quellen:** https://github.com/davnords/loma (README: Updates 26.09., Training/Data, License) ; Release-Liste https://github.com/davnords/storage/releases/tag/loma (Assets heute per API gelistet) ; COLMAP `src/colmap/feature/resources.h`.
- **Lizenz:** LoMa-Code MIT (geprueft, GitHub-API), der Matcher erbt Apache-2.0 von LightGlue (geprueft, README). Fuer die Gewichte nennt das README keine eigene Lizenz. Dass die Autoren eine kommerzielle Fassung getrennt anbieten, ist ein deutliches Warnsignal fuer die Standardgewichte [geprueft: Aussage; rechtliche Folge offen]. DINOv2 (Rueckgrat des LoMa-Deskriptors) ist Apache-2.0 (geprueft, GitHub-API). Die Frage "DINOv2 = Apache?" ist damit beantwortet, das Problem sind die Trainingsdaten der LoMa-Koepfe. Fuer DaD (`loma_detector.onnx`) wurde die Lizenz nicht geprueft.
- **8 GB:** nicht gemessen.
- **Erster Versuch:** Ein Eintrag in `LIZENZ_WERKZEUGE.md` als "⚠ COLMAP-LoMa-Standardgewichte nur Test". Testen erst mit `commercial_loma_B.pt` im Python-Pfad (LoMa-Repo bzw. hloc-Integration) an 50 schwierigen Fremdfotos gegen ALIKED+LightGlue. Messgroesse: Inlier je Paar und registrierte Fremdfotos. Erst bei Gewinn einen eigenen ONNX-Export bauen.

### 4. FlexGlue-Treffer auf denselben SIFT-Punkten mit den SIFT-Treffern vereinigen; grosse Bilder im Python-Pfad mit Abschnittsrechnung

- **Was es tut:** FlexGlue verwendet die Merkmalspunkte aus der Datenbank und ignoriert die Deskriptoren [belegt, Doku]. Die k6000.db vom 19.11. enthaelt die ersten 6000 SIFT-Punkte jedes Bildes, also dieselben Indizes wie die volle DB. Deshalb lassen sich FlexGlue-Zuordnungen und SIFT-Zuordnungen je Paar vereinigen, bevor die Zweibildgeometrie geprueft wird. Das ergibt eine einzige Punktart in einer DB und laengere Spuren, ohne neue Merkmale. Die Nachtkette prueft heute nur "entweder Tuersteher oder FlexGlue", die Vereinigung ist eine dritte Variante. Zum Speicherproblem: Der Python-FlexGlue hat `query_chunk_size` (voreingestellt 4096 Punkte je Aufruf), das "bounds memory without changing results" [belegt, README]. Dazu kommen `n_layers` (z. B. 6, Laufzeit sinkt linear) und `torch.compile`. Die ONNX-Fassung in COLMAP hat diese Schalter nicht, deshalb brachen dort Bilder mit 12 000 Punkten ab.
- **Quellen:** https://github.com/cvg/FlexGlue (README: Advanced configuration, Batch inference, torch.compile) ; COLMAP `doc/features.rst` (FLEXGLUE ignoriert Deskriptoren).
- **Lizenz:** wie Massnahme 2.
- **8 GB:** ja, gerade dafuer ist `query_chunk_size` gedacht.
- **Belegt / plausibel:** Die Schalter sind belegt. Dass die Vereinigung die Kameras genauer macht als FlexGlue allein, ist [plausibel]: SIFT liefert die feinen, FlexGlue die vielen Treffer. Die Kosten je Paar haengen vor allem am Transformer ueber 2 x 64 x 64 Merkmalszellen, kaum an der Punktzahl. Weniger Punkte machen FlexGlue daher kaum schneller, sie sparen vor allem Speicher [plausibel aus der Architektur].
- **Erster Versuch:** Nach der laufenden Nachtkette eine Variante VEREINIGT bauen. Dafuer je Paar SIFT- und FlexGlue-Zuordnungen vereinigen, Duplikate entfernen, `two_view_geometries` neu schaetzen (gleiche RANSAC-Einstellungen), dann den globalen Mapper zweimal laufen lassen. Messgroessen: mittlere Spurlaenge, Reprojektionsfehler, GPS-Tor, Laufstreuung zwischen zwei Laeufen, Seitenverklebung Nord/Sued (muss 0 bleiben).

### 5. BA-Kovarianz je Kamera als Tor fuer die Wandbild-Kameras

- **Was es tut:** pycolmap kann nach dem Buendelausgleich fuer jede Kamera die Unsicherheit von Lage und Drehung schaetzen. Fuer die Kernmethode zaehlt jede Kamera, die ins Wandbild (`fassade_fein.py`) oder in den Kanten-Sweep eingeht. Heute gehen dort alle registrierten Kameras ein, auch die schwach verbundenen am Rand, die beim Konsens-Schnitt springen. Mit der Kovarianz werden sie messbar ausgesondert oder heruntergewichtet, statt nur ueber zwei Mapperlaeufe.
- **Quelle:** im installierten pycolmap 4.2.1 vorhanden: `estimate_ba_covariance`, `BACovarianceOptions`, `get_covariance_for_relative_rigid3d` (heute per `dir(pycolmap)` geprueft, venv-colmap). Doku: https://colmap.github.io/pycolmap/
- **Lizenz:** BSD (COLMAP), geprueft frueher.
- **8 GB:** CPU-Rechnung, RAM haengt an der Modellgroesse. Fuer 900 Kameras plausibel unproblematisch, sonst nur Posen schaetzen und Punkte herausrechnen lassen (Schur).
- **Belegt / plausibel:** Das Verfahren ist Standard [belegt]. Den Gewinn fuer Wandbild und Foto-F1 haben wir nicht gemessen [plausibel]. Es ergaenzt den Konsens-Schnitt und kostet nur einen Lauf.
- **Erster Versuch:** Am Schwabentor-S0-Modell die Lageunsicherheit (Spur der 3x3-Kovarianz, in Metern nach Ausrichtung) je Kamera rechnen und mit den Kameras vergleichen, die im Konsens-Schnitt springen. Messgroesse: Trefferquote "springend" gegen "obere 10 % Unsicherheit". Danach ein Wandbild mit und ohne diese Kameras rechnen; Messgroesse: Kantenschaerfe im Wandbild und Foto-F1 (`teil_fotoform.py`) der betroffenen Seite.

### 6. Bildsuche nativ in COLMAP (PR #4544: MegaLoc/MixVPR + FAISS) oder eigener Vorlauf; lizenzsaubere Rueckfalloption

- **Was es tut:** Die PR baut globale Bildbeschreiber (MixVPR 4096-dim, MegaLoc 8448-dim, ONNX, automatischer Download mit SHA256) als Ersatz bzw. Ergaenzung zum Vokabelbaum ein. Die Suche laeuft ueber FAISS, die Beschreiber werden neben der DB zwischengespeichert. Dieselbe Technik erkennt auch Schleifen im Sequenzabgleich, also Videobilder gegen spaetere Clipstellen. Das ist der fehlende Baustein, um FlexGlue nur auf wenige Paare je Bild loszulassen, statt alles gegen alles.
- **Quelle:** https://github.com/colmap/colmap/pull/4544 (offen seit 15.07.2026, zuletzt aktualisiert 17.11.2026). MegaLoc: https://github.com/gmberton/MegaLoc
- **Lizenz:** COLMAP BSD. MegaLoc-Code MIT (geprueft, GitHub-API). Die Trainingsdaten von MegaLoc duerfen laut README nicht weitergegeben werden ("datasets come from sources that we are not allowed to redistribute", geprueft). Welche Datensaetze das sind, wurde nicht geprueft; laut Sekundaerwissen gehoert Mapillary SLS (CC BY-NC-SA) dazu, ungeprueft. Das ist dieselbe Grauzone wie bei LoMa. **Rueckfalloption mit sauberer Lizenz:** DINOv2 (Apache-2.0, geprueft) mit GeM-Pooling als eigener Beschreiber. Die Trefferquote ist dann vermutlich schlechter [plausibel]. Weil die Bildsuche nur Paare vorschlaegt und nicht ins Modell eingeht, ist das Risiko kleiner als bei Gewichten, die Geometrie erzeugen [plausibel, keine Rechtsauskunft].
- **8 GB:** ja (MegaLoc 518 px, ein Bild nach dem anderen).
- **Belegt / plausibel:** Die PR-Funktion ist belegt (PR-Text). Die Trefferquote an unseren Fassaden ist ungemessen.
- **Erster Versuch:** Ohne neuen Bau, als eigenes Python-Skript: Fuer Martinstor top-k (k = 20, 30, 50) aus MegaLoc und aus DINOv2-GeM bilden. Messgroesse: Anteil der 50 715 SIFT-bestaetigten Paare (Stufe 1 der Nachtkette), die in der top-k-Liste liegen (Recall), und Paarzahl. Ziel: mindestens 95 % Recall bei hoechstens 1/5 der Paare. Dann FlexGlue nur auf top-k ∪ Clip-Nachbarn ∪ GPS-Nahe (`paarvorwahl.py`).

### 7. PatchMatch-Fehler bei schraeg gesehenen Ebenen beheben (PR #5041)

- **Was es tut:** Beim Weiterreichen einer Tiefenhypothese an das Nachbarpixel (Propagation) liess COLMAP-PatchMatch laut PR den Anteil `n_x * u` weg. Die Hypothese rutschte dadurch von ihrer 3D-Ebene, vor allem bei Pixeln abseits der Bildmitte und schraegen Normalen. Das ist genau der Fall "glatte Putzwand schraeg im Bild", wo PatchMatch heute Loecher laesst. Die PR rechnet die Tiefe direkt auf der Ebene und behaelt bei fast parallelen Strahlen die alte Tiefe.
- **Quelle:** https://github.com/colmap/colmap/pull/5041 (offen seit 14.11.2026, nicht gemergt, nicht begutachtet; 4 GPU-Regressionstests laut PR auf RTX 3060 bestanden). Verwandt: #5051 (Fusion: RGB-Abtastung bei verkleinerten Tiefenkarten um 1,5 px versetzt, laut PR-Text "vibe coded"), #5039 (PatchMatch spart RAM).
- **Lizenz:** BSD (COLMAP).
- **8 GB:** ja, gleicher Speicher wie heute.
- **Belegt / plausibel:** Der Fehler ist mathematisch begruendet und durch Tests belegt [belegt im PR]. Eine Wirkung auf echte Szenen (Vollstaendigkeit, Genauigkeit) nennt die PR nicht [plausibel: mehr Belegung auf Putz, weniger Fehlpunkte an Schraegflaechen]. Den Fehler in `NICHTS_GEBRACHT.md` und `LIB_UPDATES` nicht vermerkt.
- **Erster Versuch:** Die PR in den vorhandenen Testbau `/media/oem/rcdaten/colmap-test/` einspielen (cherry-pick, nur die MVS-Datei). Einen Putz-Ausschnitt (eine Schwabentor-Wand, 30 Bilder, 1600 px, fotometrisch) mit altem und neuem Bau rechnen. Messgroessen: Putzbelegung (Anteil Wandzellen mit Punkten), Fehlpunkte vor/hinter der LoD2-Wandebene, Laufzeit.

### 8. Videobilder mit starker Drehung erkennen (Rolling-Shutter-Mass aus den eigenen Posen)

- **Was es tut:** Bei Rolling Shutter wird jede Bildzeile zu einem anderen Zeitpunkt belichtet. Dreht die Kamera waehrenddessen, ist das Bild geschert, und das Lochkameramodell stimmt nicht. Die Groesse laesst sich aus dem eigenen Modell schaetzen: Winkelgeschwindigkeit aus den Posen der Nachbarbilder im Clip, mal Auslesezeit (Handy/Drohne typisch 15-30 ms), mal Brennweite in Pixeln, ergibt die Scherung in Pixeln. Bilder mit mehr als etwa 1-2 px duerfen dann zwar verbinden, gehen aber nicht ins Wandbild und nicht in den Kanten-Sweep.
- **Quelle:** Ein fertiges offenes RS-Werkzeug fuer COLMAP gibt es nicht. 2025/2026 gibt es nur Forschung zu Minimalloesern ohne Integration: https://arxiv.org/abs/2603.11888 (KTH, Maerz 2026, Machbarkeitscode), https://arxiv.org/abs/2506.22069 (Hruby/Pollefeys 2025, Code angekuendigt). COLMAP hat weder Optionen noch PRs zu Rolling Shutter (Quelltext ce2b5ab per grep geprueft: kein Treffer).
- **Lizenz:** eigener Code.
- **8 GB:** CPU, trivial.
- **Belegt / plausibel:** Die Physik ist belegt. Ob RS bei uns messbar ist, ist offen [plausibel bei Drohnenschwenks und Handvideos].
- **Erster Versuch:** Zuerst pruefen, ob es das Problem ueberhaupt gibt. Am Martinstor-Modell fuer alle 746 Videobilder die Winkelgeschwindigkeit aus den Nachbarposen rechnen und gegen den mittleren Reprojektionsfehler je Bild auftragen; dazu den Zeilenanteil des Fehlers (Fehler waechst mit der Bildzeile). Nur wenn ein Zusammenhang da ist (Rangkorrelation > 0,3), das Tor in die Kette nehmen. Messgroesse danach: Kantenschaerfe im Wandbild mit/ohne gescherte Bilder.

### 9. Depth Anything 3 Base mit UNSEREN Kameras als Fuelltiefe fuer Putzloecher

- **Was es tut:** DA3-Base und DA3-Small nehmen bekannte Kameras als Eingabe (`inference(images, extrinsics=..., intrinsics=..., align_to_input_ext_scale=True)`). Daraus wird eine ueber mehrere Bilder stimmige Tiefe ("Pose-Conditioned Depth Estimation: superior depth consistency when camera poses are provided"). Damit klaert sich die offene Frage aus `RECHERCHE_VERBESSERUNG_2026-11-17.md` ("ob er bekannte Posen als Eingabe nimmt, ist UNSICHER"): Er nimmt sie. Fuer weissen Putz ist das eine gelernte Mehrbildtiefe im Massstab unserer SfM, nur als Fuellwolke in Loechern (wie Punkt 11 im Bericht vom 18.11.) und nie als Form.
- **Quelle:** https://github.com/ByteDance-Seed/Depth-Anything-3 (README Modelltabelle, Spalte "Pose Cond."; `src/depth_anything_3/api.py`, heute gelesen).
- **Lizenz:** DA3-BASE und DA3-SMALL Apache-2.0, DA3METRIC-LARGE und DA3MONO-LARGE Apache-2.0; DA3-LARGE, GIANT und NESTED **CC BY-NC 4.0 = ausgeschlossen** (geprueft, README-Tabelle; Repo Apache-2.0 per API).
- **8 GB:** Base hat 0,12 Mrd. Parameter, Standardaufloesung 504 px; mit 10-20 Bildern je Aufruf plausibel unter 8 GB, ungemessen.
- **Belegt / plausibel:** Die Funktion ist belegt. Die Genauigkeit auf Putz ist ungemessen. 504 px sind grob, fuer Lageveto und Lueckenfuellung reicht das [plausibel].
- **Erster Versuch:** Eine Schwabentor-Putzwand mit 12 Fotos nehmen, Kameras aus dem Modell, DA3-Base posenbedingt laufen lassen. Messgroessen: Abstand der DA3-Punkte zur LoD2-Wandebene und zu PatchMatch-Punkten auf texturierten Nachbarflaechen (Median, p90), Anteil gefuellter Putzzellen. Fuellwolke getrennt fuehren, nicht mitteln.

---

## Bewusst nicht in der Liste

- **AnyCalib:** schon gemessen. Als Prior schlechter (S3/S4), als Startwert gleichauf (S5). Nichts Neues in COLMAP seit dem Einbau (#4778, 26.09.).
- **GeoCalib nur fuer die Brennweite:** Der FoV-Wert auf MegaDepth liegt bei AUC@10 Grad = 48,2. Das waere kaum besser als AnyCalib. Nutzen hat GeoCalib nur ueber die Schwerkraft (Massnahme 1).
- **AffineLoMa / LoMa-B64 (17.11.2026):** neu, aber mit derselben Gewichte-Frage wie Massnahme 3 und ohne erkennbaren Bezug zu unseren Engstellen.
- **RaCo (cvg, Apache-2.0, Punkte mit 2x2-Kovarianz):** COLMAP verwendet Punktkovarianzen im BA nicht. Erst interessant, wenn es so eine Gewichtung gibt.
- **Neue texturarme MVS-Arbeiten 2025/2026 (DVP-MVS++, DFM-MVS, Mono3R, MonoMVSNet):** Lizenzen nicht belegt, meist auf Depth-Anything-V2-Large (NC) aufgebaut. Gegenueber APD-MVS (Bericht 18.11.) gibt es nichts belegt Besseres mit freier Lizenz. MVSAnywhere ist NC (geprueft am 17.11.).
- **Offene COLMAP-PRs zu Pose-Prior-BA (#4939, #4940, #4947):** Der globale Mapper bekommt dadurch weiterhin keine Positionsvorgaben. Beobachten, nicht bauen.

## Zusammenfassung

Der staerkste neue Hebel fuer genaue Kameras liegt schon im eigenen Bau: Der globale Mapper nimmt je Bild eine Schwerkraftrichtung (`ra_use_gravity`, `ra_use_stratified`, Tabelle `pose_priors.gravity`). Wir koennen sie lizenzfrei aus dem vorhandenen Fluchtpunkt-Lot (`lot_aus_fotos.py`) liefern, wahlweise aus GeoCalib (Gewichte CC BY 4.0). Bei FlexGlue lassen sich Tempo und Speicher ohne neuen Code verbessern: frueher abbrechen (`early_stop_decay`), Paarliste fuer den Cache sortieren, Paare per Bildsuche vorwaehlen (COLMAP-PR #4544 oder eigenes MegaLoc/DINOv2-Skript). Grosse Bilder laufen im Python-Pfad mit `query_chunk_size`. Weil FlexGlue die DB-Punkte nutzt, kann man seine Treffer mit den SIFT-Treffern auf denselben Punkten vereinigen; das ist eine dritte Variante neben Tuersteher und reinem FlexGlue. Wichtiger Lizenzbefund: COLMAP laedt fuer LoMa die normalen Gewichte, die auch auf nicht-kommerziellen Daten trainiert sind. Die Autoren bieten getrennte "commercial_*"-Gewichte an, aber nur als .pt; vor jedem LoMa-Versuch also die Weiche stellen. Fuer weissen Putz gibt es kaum Neues mit freier Lizenz. Lohnend sind die offene PatchMatch-Korrektur fuer schraege Ebenen (#5041, billig im Testbau) und DA3-Base/Small (Apache), das nachweislich bekannte Kameras als Eingabe nimmt. Fuer Rolling Shutter gibt es 2026 kein einsatzfaehiges Werkzeug. Pruefbar ist zuerst, ob schnelle Drehung in Videobildern mit dem Reprojektionsfehler zusammenhaengt; dazu kommt die BA-Kovarianz je Kamera (in pycolmap 4.2.1 vorhanden), um unsichere Kameras aus dem Wandbild fernzuhalten.

## Ergebnis der Abarbeitung (Nacht 19./20.11.2026, Details LOGBUCH_KETTENTEST_2026-11-19.md)
1. Schwerkraft je Bild: Werkzeug gebaut (tools/schwerkraft_je_bild.py, Median 0,7 Grad), aber im Mapper SCHAEDLICH: 12-14 Bilder weniger, fast alle mit (falscher) Vorgabe; kein Genauigkeitsgewinn. NICHT in der Kette.
2. FlexGlue frueher abbrechen (0,3 / 0,2): nicht schneller, Qualitaet gleich. Standard bleibt.
3. LoMa: an der Quelle bestaetigt nicht kommerziell nutzbar (Gewichte). Gesperrt.
4. SIFT ∪ FlexGlue: trennt Seiten, 949/154 Bilder (zwischen SIFT 818/111 und FlexGlue 1065/161), 1,39 px. Kein Vorteil gegen FlexGlue allein.
5. Kamera-Unsicherheit lokal: alle Springer unter den 10 % unsichersten (Schwabentor). Werkzeug in tools/versuche.
6. Bildsuche (DINOv2): fuer neue FlexGlue-Paare wertlos (nur 9 % in top-150). Verworfen als Vorfilter.
7. PatchMatch-PR 5041: kein messbarer Unterschied. Nicht uebernehmen.
8. Rollverschluss: keine Massnahme.
9. DA3-BASE als Fuelltiefe: kein klarer Gewinn gegen Ebenenfuellung.
NEBENFUNDE mit groesstem Nutzen: (a) globaler Mapper legt punktlos getrennte Stuecke in EIN Modell -> tools/modell_zerlegen.py; (b) echtes Verkleben kam aus der Konsens-Stufe 2 -> Seitenfilter in global_mapper_konsens.py (belegt: 0 verklebte Bilder, Lage gleich); (c) FlexGlue = stabil +30/+40 % Bilder am Martinstor (zuschaltbar); (d) tools/gps_seiten_pruefen.py.
