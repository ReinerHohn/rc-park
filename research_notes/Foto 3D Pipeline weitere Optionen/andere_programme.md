# Andere Programme und Hybrid-Ablaeufe als Ersatz/Ergaenzung zur COLMAP-Kette (Stand November 2026)

Hinweise zur Lesart:
- "Suchtreffer" = Angabe stammt aus einer Suchmaschinen-Zusammenfassung der verlinkten Seite, die Seite selbst wurde nicht im Volltext gelesen. Vor Verwendung nachpruefen.
- "Volltext" = Seite wurde abgerufen und ausgewertet.
- Alles, wofuer keine Quelle gefunden wurde, steht unter "Gaps". Dort sind auch Angaben aus Vorwissen ohne aktuelle Quelle ausdruecklich als UNBELEGT markiert.
- CLI-Namen sind nur genannt, wenn sie auf einer abgerufenen Seite standen. Nichts davon wurde lokal ausgefuehrt.
- Der fruehere Bericht `reports/Foto 3D Pipeline Verbesserungen.md` deckt bereits ab: COLMAP-interne Massnahmen, GLUEMAP, VGGT-Speicherproblem, Gaussian Splatting als Geometriequelle (Fehlschlag), ACMM/OpenMVS als Tiefenkarten-Ersatz, MapAnything als Gegenprobe. Das wird hier nicht wiederholt, nur ergaenzt.

## 1. RealityScan (frueher RealityCapture, Epic Games)

### Takeaway
RealityScan ist der einzige kommerzielle Kandidat, der kostenlos (Umsatz unter 1 Mio. USD), per CLI voll skriptbar, mit eigenem Linux-Build (gebuendeltes Wine, experimentell) und mit direktem COLMAP-Export verfuegbar ist; die Mindestanforderung des Linux-Builds ist genau 8 GB VRAM. Belastbare Messungen zu Robustheit an symmetrischen Gebaeuden oder Zeiten auf 8 GB wurden nicht gefunden, das muss der Eintagesversuch selbst liefern.

### Cited Findings
Version und Plattform
- RealityScan 2.1 erschien Ende November 2025 (Volltext der Suchtreffer-Zusammenfassung; Epic-Ankuendigung) — [RealityScan 2.1 is now available](https://www.realityscan.com/en-US/news/realityscan-2-1-is-now-available), [CG Channel](https://www.cgchannel.com/2025/11/epic-games-releases-realityscan-2-1/)
- 2.1.1 folgte im Fruehjahr 2026 mit besserem COLMAP-Export (Wahl flache Ordner oder Standard-COLMAP-Verzeichnis, binaer oder ASCII), neuem Exporter "RealityScan XMPs with Image List" (XMP wahlweise fuer verzerrte Originalbilder oder entzerrte Bilder) und einem Fix fuer Qualitaetsverlust beim COLMAP-Export mit Originalbildern (Suchtreffer) — [Epic Doku 2.1.1](https://dev.epicgames.com/documentation/en-us/realityscan/realityscan-2-1-1), [Digital Production 06.04.2026](https://digitalproduction.com/2026/04/06/realityscan-2-1-1-adds-better-colmap-support-and-new-xmp-export-options/)
- Eine Puget-Seite erwaehnt "Version 2.2" (ab dann auch AMD-Grafikkarten); eine andere Puget-Seite sagt, NVIDIA/CUDA sei fuer vollen Betrieb noetig. Ob 2.2 die aktuelle Version im November 2026 ist, wurde nicht an einer Epic-Quelle bestaetigt (Suchtreffer) — [Puget Hardware-Empfehlungen RealityScan](https://www.pugetsystems.com/solutions/photogrammetry-workstations/realityscan/hardware-recommendations/)
- Umbenennung RealityCapture -> RealityScan im Juni 2025 (Suchtreffer) — [Puget](https://www.pugetsystems.com/solutions/photogrammetry-workstations/realityscan/hardware-recommendations/)
- Linux: "command-line-focused build ... designed for automated processing on Linux servers", laeuft in einem mitgelieferten Wine-Umfeld, auch im Docker-Container mit GPU-Durchreichung. Status "experimental". Anforderungen: 64-Bit-Linux mit NVIDIA-GPU, empfohlen Ubuntu 24.04 (Kernel 6.14) oder Fedora 39, mindestens 8 GB VRAM, mindestens 16 GB RAM. Die Desktop-Oberflaeche startet zwar, wird aber "not recommended" (Grafikfehler, Fokusprobleme, HTML-Dialoge fehlen). Unterstuetzte Wege: lokale CLI-Befehle, `.rscmd`-Befehlsdateien, Remote Command Plugin (gRPC/REST), passiver Benachrichtigungsmodus (Volltext) — [RealityScan for Linux](https://dev.epicgames.com/documentation/en-us/realityscan/realityscan-for-linux)
- Download- und Lizenzseite fuer Linux: realityscan.com/en-US/linux (leitet auf unrealengine.com um, Abruf scheiterte mit HTTP 403) — [RealityScan for Linux](https://dev.epicgames.com/documentation/en-us/realityscan/realityscan-for-linux)

Lizenz
- Kostenlos "For individuals and small businesses that made less than $1 million USD in revenue in the past 12 months", ausserdem Bildungseinrichtungen und Studierende; alle Funktionen enthalten. Darueber 1.250 USD je Platz und Jahr, 30-Tage-Test (Volltext) — [RealityScan Lizenzseite](https://www.realityscan.com/en-US/license)

CLI (alle Namen woertlich von der Epic-Seite "All Commands", Volltext; Befehle werden als Parameter an die Programmdatei uebergeben und der Reihe nach ausgefuehrt)
- Start/Projekt: `headless` (nur beim Start, blendet Oberflaeche aus), `newScene`, `add imageName` (auch `.imagelist`-Textdatei mit einem vollen Bildpfad je Zeile), `addFolder folderName` (Unterordner mit `-set "appIncSubdirs=true"`), `save MyProject.rsproj`, `quit`
- Ausrichtung: `align`, `mergeComponents`, `selectMaximalComponent`
- Passpunkte/Lage: `importGroundControlPoints gcpFileName params.xml`, `exportGroundControlPoints gcpFileName params.xml`, `importFlightLog flFileName params.xml`, `defineDistance PointNameA PointNameB distance constraintName`, `detectMarkers params.xml`
- Vorkalibrierung/Gruppen: `addImageWithCalibration` (Bild mit XMP-Datei), `exportXMP params.xml`, `setConstantCalibrationGroups`, `setPriorCalibrationGroup number`, `setPriorLensGroup number`, `lockPoseForContinue true|false`
- Export: `exportRegistration fileName params.xml`, `exportSparsePointCloud fileName params.xml`, `importColmap filePath params.xml`
- Dichte Stufe: `setReconstructionRegion box.rsbox`, `setReconstructionRegionAuto`, `calculatePreviewModel`, `calculateNormalModel`, `calculateHighModel`, `exportModel modelName fileName params.xml`, `exportSelectedModel fileName params.xml`
- Steuerung: `set "key=value"`, `writeProgress fileName timeout`
- Quelle fuer alle Zeilen oben — [RealityScan All Commands](https://dev.epicgames.com/documentation/realityscan/all-commands); Uebersicht mit Headless-Modus und RSCMD-Dateien — [Command-line operations](https://dev.epicgames.com/documentation/realityscan/command-line-operations)
- WIDERSPRUCH: Ein Pressebericht sagt, 2.1.1 habe `importColmap` in `loadColmap` umbenannt; die abgerufene Epic-Befehlsliste fuehrt weiter `importColmap` und weder `loadColmap` noch `exportColmap` — [Digital Production](https://digitalproduction.com/2026/04/06/realityscan-2-1-1-adds-better-colmap-support-and-new-xmp-export-options/) gegen [All Commands](https://dev.epicgames.com/documentation/realityscan/all-commands)

COLMAP-Export und Fallstricke
- Der COLMAP-Exporter schrieb urspruenglich immer entzerrte Bilder nach den Entzerrungs-Einstellungen des Exports; seit 2.1 koennen Dateien passend zu den verzerrten Originalbildern exportiert werden (Suchtreffer) — [Epic Doku 2.1](https://dev.epicgames.com/documentation/en-us/realityscan/realityscan-2-1), [Forum Undistorted Masks](https://forums.unrealengine.com/t/exporting-undistorted-masks-with-colmap-sparse-point-cloud/2656262)
- Ein Nutzer, der RealityScan-Ausrichtungen als COLMAP-Text exportierte und selbst entzerrte, berichtet: mit OpenCV oder COLMAPs `image_undistorter` sei das Sichtfeld "always slightly off" gegenueber RealityScans eigener Entzerrung; Frage im Thread offen (Suchtreffer) — [Forum Image undistortion](https://forums.unrealengine.com/t/reality-scan-image-undistortion/2574748)
- Masken wurden beim COLMAP-Export nicht mit entzerrt; 2.1.1 nennt Fixes fuer Maskenexport, auch per CLI (Suchtreffer) — [Epic Doku 2.1.1](https://dev.epicgames.com/documentation/en-us/realityscan/realityscan-2-1-1)
- Es gibt einen Forumthread zu einer "pinhole option" des COLMAP-Textexports und einen zu fehlgeschlagenem `cameras.csv`-Export per CLI (nur Titel gesehen) — [Colmap Text export - pinhole option](https://forums.unrealengine.com/t/colmap-text-export-pinhole-option/2657130), [Unable to export cameras.csv via CLI](https://forums.unrealengine.com/t/realitycapture-unable-to-export-cameras-csv-via-cli/2658013/2)
- nerfstudio liest RealityCapture-Ausrichtungen aus CSV ("Internal/External camera parameters"): `ns-process-data realitycapture --data {data directory} --csv {csv file} --output-dir {output directory}` (Volltext) — [nerfstudio custom data](https://docs.nerf.studio/quickstart/custom_dataset.html)

Leistung/Speicher
- Laut Puget haengt der Speicherbedarf der Ausrichtung von Bildanzahl und Merkmalszahl je Bild ab; alle Schritte ausser der Ausrichtung arbeiten "out of core" (Suchtreffer) — [Puget RAM-Artikel](https://www.pugetsystems.com/labs/articles/does-ram-capacity-affect-realitycapture-performance-1521/)
- Ein alter Techgage-Test sah bei einem Projekt nur 1,3 GB VRAM-Spitze (Suchtreffer, alte Version, ein Projekt) — [Techgage](https://techgage.com/print/exploring-photogrammetry-gpu-performance-with-realitycapture)
- Ein einzelner, nicht begutachteter Test mit 95 Fotos (2025): RealityScan-Netz in hoher Qualitaet dichter und detailreicher als Metashape, Texturfarben schwaecher, "more sensitive to hardware limitations" (Suchtreffer, anekdotisch) — [Coda Testnotizen](https://coda.io/@hsiao-pei-kao/3d-scanning-keynote/test-scans-3)

### Inferences
- Der Linux-Build passt formal genau auf die Maschine (8 GB VRAM = Untergrenze). Weil die Ausrichtung im RAM und die dichte Stufe out-of-core laeuft, ist die GPU wahrscheinlich nicht der Engpass fuer 500 Bilder; knapp wird eher der Plattenplatz (Projektcache). Cache-Ort vor dem Versuch auf die Datenplatte legen oder Windows-Partition nutzen.
- Fuer die Kernmethode (eigene Kanten-Triangulation) ist der sicherste Weg, die ENTZERRTEN Bilder samt Pinhole-Kameras aus RealityScan zu uebernehmen und alle Folgestufen auf diesen Bildern zu rechnen. Ein Mischen von RealityScan-Verzeichnungsparametern mit COLMAPs Entzerrer ist laut Forum fehleranfaellig.
- Die Probleme der eigenen Kette haben in RealityScan direkte Gegenstuecke: Komponenten (statt falsch eingehaengter Bildgruppen entstehen getrennte Komponenten, `mergeComponents`), Passpunkte/Distanzen (`importGroundControlPoints`, `defineDistance`) fuer LoD2-Bezug, Flugprotokoll/GPS-Vorgaben (`importFlightLog`), Kalibriergruppen fuer Bilder ohne EXIF. Ob das am symmetrischen Turm besser geht als im COLMAP-Mapper, ist NICHT belegt.
- Die Lizenz ist fuer Hobby und kleinen Verkauf gedruckter Modelle unkritisch, solange der Umsatz unter 1 Mio. USD bleibt; die Lizenzseite regelt die Schwelle ueber den Umsatz, nicht ueber die Art der Nutzung.

### Gaps
- Kein unabhaengiger Vergleich RealityScan gegen COLMAP/Metashape auf Posen-Genauigkeit oder Registrierungsrate 2024-2026 gefunden; keine Messung zu symmetrischen Gebaeuden/Tuermen; keine Zeitmessung fuer 500 Bilder auf 8 GB.
- Genauer CLI-Weg fuer den COLMAP-Export (ueber `exportRegistration` mit `params.xml` oder eigener Befehl) nicht bestaetigt. Vor dem Versuch in der aktuellen Befehlsliste nachsehen; `params.xml` laesst sich laut Doku-Konvention aus dem Exportdialog erzeugen (UNBELEGT, Vorwissen).
- Installationsformat, Anmeldung/Aktivierung (Epic-Konto, Token, Online-Zwang) und Lizenztext des Linux-Builds nicht abrufbar (HTTP 403).
- Ob die EULA den Verkauf von Ergebnissen (gedruckte Modelle) eigens regelt, steht nicht auf der Lizenzseite; die FAQ zur Berechnung der Umsatzschwelle war nicht lesbar.
- Aktuelle Versionsnummer November 2026 (2.1.1 oder 2.2) nicht an Epic-Quelle bestaetigt.
- Bundler-/NVM-Export: aus Vorwissen vorhanden gewesen (RealityCapture), fuer RealityScan 2.x nicht belegt.

## 2. Klassische Programme: Metashape, 3DF Zephyr, Pix4D, Meshroom/AliceVision, OpenDroneMap/OpenSfM, MicMac, OpenMVG+OpenMVS, Regard3D

### Takeaway
Fuer unbeaufsichtigten Linux-Betrieb kommen ernsthaft nur Metashape Professional (3.499 USD, Python nur dort), Meshroom 2025.1 (frei, CUDA 12) und OpenDroneMap (frei, AGPL, aber auf Drohnenraster ausgelegt) in Frage; Metashape Standard (179 USD) hat inzwischen COLMAP-Export, aber keine Python-Schnittstelle, und 3DF Zephyr ist reines Windows mit Kameraexport erst in der 4.200-Euro-Ausgabe.

### Cited Findings
Agisoft Metashape
- Preise im Agisoft-Laden: Professional 3.499 USD, Standard 179 USD, jeweils rechnergebunden und Einmalkauf; Floating nur ueber Haendler; Upgrade Standard -> Professional moeglich (Volltext) — [Agisoft Online Store](https://www.agisoft.com/buy/online-store/)
- Bildungspreise 549 USD (Pro) und 59 USD (Standard), Lizenz unbefristet mit 12 Monaten Support und Updates bis 2.xx (Suchtreffer, Zweitquelle) — [SkyeBrowse Vergleich 2026](https://www.skyebrowse.com/news/posts/metashape-vs-realitycapture)
- Funktionsliste nennt "Built-in Python scripting", "Headless operation support", "Network processing", "Ground control and check points support", "Markers / scale bars support", "LiDAR data support"; die Zuordnung zu den Ausgaben war im Abruf nicht lesbar (Volltext ohne Haekchen) — [Agisoft Feature-Vergleich](https://www.agisoft.com/features/compare/)
- Python-Schnittstelle nur in Professional (Suchtreffer: Agisoft-Vergleichstabelle und Community-Handbuch) — [Agisoft Features](https://www.agisoft.com/index.php?id=42), [Metashape Expert Manual Scripting](https://photogrammetrycommunity.github.io/metashape-expert-manual/workflow/scripting-automation/)
- WIDERSPRUCH Headless: ein Spiegel der Agisoft-Tabelle fuehrt Headless nur fuer Professional, ein Haendler fuer beide Ausgaben (Suchtreffer) — [linksoft](https://linksoft.com.tw/product/agisoft_photoscan) gegen [heliguy](https://www.heliguy.com/agisoft-metashape-i171)
- Aufruf laut Agisoft-Supportartikel: Windows `metashape.exe -r <script.py> [script arguments]`, Linux `./metashape.sh -r <script.py> [script arguments]`; auf Systemen ohne Oberflaeche zusaetzlich `-platform offscreen` (Suchtreffer) — [Agisoft Freshdesk](https://agisoft.freshdesk.com/support/solutions/articles/31000133141)
- COLMAP-Export: Datei > Export > Export Cameras, Format colmap; laut Community-Handbuch nativ ab 2.2, in 2.0/2.1 nicht vorhanden; das alte Skript `export_for_gaussian_splatting.py` gilt als abgeloest (Suchtreffer) — [Metashape Expert Manual COLMAP-Export](https://photogrammetrycommunity.github.io/metashape-expert-manual/workflow/export-reporting/colmap-export-for-3dgs/)
- WIDERSPRUCH Version: radiancefields.com meldet den COLMAP-Export bereits fuer die Standard-Ausgabe 2.1.3 (Vorabversion, Artikel von September 2024), exportiert werden Kameras, entzerrte Bilder und `sparse/0` als `.bin` (Volltext) — [radiancefields.com](https://radiancefields.com/agisoft-metashape-adds-colmap-export-support-to-standard-license)
- Verzeichnungsmodell (Volltext; die Seite stuft sich selbst als "unverified" ein): Metashapes `p1` entspricht OpenCVs `p2` und umgekehrt; der COLMAP-Export tauschte das erst ab 2.3.0 Build 21778 richtig. Hauptpunkt ist als Versatz von der Sensormitte gespeichert mit Pixelecken-Konvention: `cx_opencv = cx + W/2 - 0.5`, `cy_opencv = cy + H/2 - 0.5`. `b1`/`b2`: `fy = f + b1`, Scherung = `b2`. `k4` hat kein OpenCV-Gegenstueck im Standardvektor. Empfohlener Ausweg: entzerrt exportieren, `chunk.exportCameras(..., convert_to_pinhole=True)` — [Metashape Expert Manual Verzeichnung](https://photogrammetrycommunity.github.io/metashape-expert-manual/workflow/camera-calibration/distortion-model-opencv-colmap/)
- COLMAP-Export scheitert laut einem Nutzerbericht bei sphaerisch kalibrierten Kameras (Suchtreffer) — [Reddit-Spiegel](https://redlib.cypherpunktools.com/r/photogrammetry/comments/1jp60pn/is_it_possible_to_exportconvert_spherical_cameras)
- nerfstudio-Import: `ns-process-data metashape --data {data directory} --xml {xml file} --output-dir {output directory}`; alle Bilder muessen denselben Sensortyp haben (Volltext) — [nerfstudio custom data](https://docs.nerf.studio/quickstart/custom_dataset.html)
- Genauigkeit: In einer Sensors-Studie 2021 am selben Bildsatz mittlerer Abstandsfehler Metashape 0,212 mm, COLMAP mit MVS 0,441 mm, Meshroom 0,868 mm (Suchtreffer; Kleinobjekt, dichte Rekonstruktion, nicht Posen) — [Sensors 2021 Tabelle 4](https://pmc.ncbi.nlm.nih.gov/articles/PMC8659967/table/sensors-21-08026-t004)
- Vergleich von sechs Werkzeugen (u. a. COLMAP, Meshroom, Metashape) an einem Graben/Leitungs-Datensatz: Metashape am besten (Suchtreffer) — [ISPRS Archives 2022](https://isprs-archives.copernicus.org/articles/XLIII-B2-2022/141/2022/isprs-archives-XLIII-B2-2022-141-2022.pdf)

3DF Zephyr
- Free: hoechstens 50 Fotos oder Videobilder, eine GPU, Export nur texturierte Netze mit JPG, "personal use". Lite: 199 EUR + MwSt. einmalig, Fotozahl unbegrenzt, zwei GPUs, Export Netze/Videos. Vollversion: 4.200 EUR + MwSt. einmalig oder 250 EUR + MwSt. je Monat; erst hier Punktwolken, Kamerapositionen, Passpunkte. Unbefristete Lizenzen mit 12 Monaten Updates, Verlaengerung 20 % (Volltext) — [3Dflow Produktseite](https://www.3dflow.net/3df-zephyr-photogrammetry-software/)
- Nur Windows x64 (10/11); Lite ohne Passpunkte, ohne Orthofoto- und Kameraexport (Suchtreffer, Steam-FAQ) — [Steam 3DF Zephyr Lite](https://store.steampowered.com/app/438450)

Meshroom / AliceVision
- Meshroom 2025.1.0 vom 18.08.2025 fuer Linux (`.tar.gz`) und Windows (`.zip`). "The binaries are built with CUDA-12 and are compatible with compute capability >= 5.0." Neu u. a.: Knoten `SfMExpanding`, experimentelle Pipeline fuer modulares SfM, Parametrisierung des SfM-Bootstrappings, Ausrichten und Zusammenfuehren mehrerer SfM-Ergebnisse ueber Merkmalstreffer, Zusammenfuehren mehrerer sfmData-Dateien, `sfmFilter`, aequirektangulares Kameramodell, Fixes am Skript `meshroom_batch` (Volltext) — [Meshroom v2025.1.0 Release](https://github.com/alicevision/Meshroom/releases/tag/v2025.1.0)
- 24 vorgefertigte Pipeline-Vorlagen, Plugin-System (experimentell), Segmentierungsknoten, Meshroom von AliceVision entkoppelt, "Live Reconstruction" entfernt; 330 Aenderungen in Meshroom, 253 in AliceVision (Suchtreffer) — [Digital Production 20.08.2025](https://digitalproduction.com/2025/08/20/meshroom-2025-1-templates-plugins-and-photometric-stereo/), [MPC](https://www.mpcvfx.com/en/news/mpc-celebrates-the-release-of-meshroom-2025-1-0/)
- Ein Nutzer meldet: 2023.2 laeuft, 2025.1 nicht unter Ubuntu 24.04 (Suchtreffer, Ursache offen) — [AliceVision Google Group](https://groups.google.com/g/alicevision/c/7jSkC1BSsz4)
- Aeltere Vergleiche: Stathopoulou et al. 2019 verglichen COLMAP, OpenMVG+OpenMVS und AliceVision an grossen Szenen; Ergebnisse "often lack completeness and accuracy" in realen Faellen (Suchtreffer) — [ISPRS Archives 2019](https://isprs-archives.copernicus.org/articles/XLII-2-W17/331/2019/)

OpenDroneMap / OpenSfM
- Lizenz AGPLv3, stabile Version 3.5.6 (Juli 2025) (Suchtreffer, Wikipedia-Spiegel) — [Wikipedia-Spiegel ODM](https://wiki.krisyotam.com/content/wikipedia_en_all_nopic_2026-03/OpenDroneMap)
- Optionen woertlich aus der ODM-Doku (Volltext): `--sfm-algorithm` {`incremental` (Standard), `triangulation`, `planar`}; `--feature-type` {`akaze`, `dspsift` (Standard), `hahog`, `orb`, `sift`}; `--matcher-type` {`bow`, `bruteforce`, `flann` (Standard)}; `--feature-quality` und `--pc-quality` {`ultra`, `high`, `medium`, `low`, `lowest`}; `--use-fixed-camera-params`; `--cameras` (JSON oder `cameras.json`); `--gcp` (Passpunktdatei); `--no-gpu`; `--end-with` / `--rerun` / `--rerun-from` mit Stufen u. a. `opensfm`, `openmvs`, `odm_filterpoints`, `odm_meshing`, `odm_georeferencing`; `--camera-lens` {`auto`, `perspective`, `brown`, `fisheye`, `fisheye_opencv`, `spherical`, `equirectangular`, `dual`}; `--sky-removal`, `--bg-removal` (experimentell) — [ODM Arguments](https://docs.opendronemap.org/arguments/)
- ISPRS 2025 (Kostrzewa et al., TU Warschau): "ODM produces comparable results to Agisoft Metashape", Unterschiede bei Kamerakalibrierung und Orientierung; Zahlen nur im PDF (Volltext der Zusammenfassung) — [ISPRS Archives XLVIII-1/W4-2025, S. 65-72](https://isprs-archives.copernicus.org/articles/XLVIII-1-W4-2025/65/2025/)
- Community: Probleme mit OpenSfM-Rekonstruktion und Georeferenzierung bei Bodenaufnahmen mit schlechtem GNSS; gemischte Luft-/Bodenaufnahmen richten sich bei GPS-Versatz falsch aus (Suchtreffer) — [ODM Community "biggest pain"](https://community.opendronemap.org/t/what-is-your-biggest-pain-with-odm-opensfm/25791?page=2), [ODM Community Luft+Boden](https://community.opendronemap.org/t/reconstructing-models-from-multiple-levels-aerial-and-ground-initial-findings/11817?page=2)
- Ein Drittanbieter-Test nennt WebODM auf systematische Luftbildraster ausgelegt, ohne Geotags brauche man Passpunkte (Suchtreffer, Meinung eines Wettbewerbers) — [SkyeBrowse WebODM-Test](https://www.skyebrowse.com/news/posts/webodm-review.md)
- nerfstudio-Import: `ns-process-data odm --data /path/to/dataset --output-dir {output directory}`, alle Bilder von derselben Kamera (Volltext) — [nerfstudio custom data](https://docs.nerf.studio/quickstart/custom_dataset.html)

MicMac
- Drones 2022 (Bruecke Ponte della Cerra): Merkmalsextraktion von MicMac vergleichbar mit Photoscan; die Autoren betonen, dass Vergleiche wegen der Geheimhaltung kommerzieller Software schwer sind (Suchtreffer) — [Drones 6(242), 2022](https://www.iris.unina.it/retrieve/003288e9-3696-4e34-a01d-f318cdf1a9e9/drones-06-00242-v2.pdf)
- Ein Buchkapitel vergleicht Metashape, RealityCapture, MicMac und Meshroom an Drohnenbildern von Meteora (UNESCO); Zahlen nicht im Abstract (Suchtreffer) — [Springer Professional](https://www.springerprofessional.de/en/a-comparative-analysis-of-different-software-packages-for-3d-mod/19062226)

Aeltere Vergleiche freier Software am Kulturerbe
- Heritage 2019: freie Werkzeuge (u. a. COLMAP 3.1) gegen Metashape mit Bodenwahrheit; "promising results, with significant accuracy" (Suchtreffer) — [Heritage 2(3), 112](https://mdpi.com/2571-9408/2/3/112)
- SSRR 2018: die meisten Verfahren erreichen im Nahbereich Sub-Millimeter, glaetten aber feine Details weg (Suchtreffer) — [SSRR 2018](https://robotik.informatik.uni-wuerzburg.de/telematics/download/ssrr2018_sfm.pdf)

### Inferences
- Metashape waere fachlich der staerkste klassische Vergleichspartner (Passpunkte, Massstabsleisten, Kalibriergruppen, Linux), aber der unbeaufsichtigte Betrieb haengt an der Professional-Lizenz (3.499 USD). Mit Standard bliebe nur Klickbetrieb plus COLMAP-Export; das widerspricht der Vorgabe "ohne GUI-Klicks". Ein kostenloser Zeitversuch ist nur sinnvoll, wenn eine Testlizenz Python freischaltet (nicht belegt, siehe Gaps).
- Bei Metashape -> COLMAP gilt dieselbe Regel wie bei RealityScan: entzerrt exportieren oder mindestens Build >= 2.3.0/21778 verwenden und die Halbpixel-Konvention am Hauptpunkt nachrechnen. Sonst entstehen systematische Kantenversaetze von bis zu einem halben Pixel plus Tangentialfehler, genau in der Groessenordnung, auf die der eigene Kanten-Sweep empfindlich ist.
- Meshroom ist frei, laeuft unter Linux und per `meshroom_batch` ohne Oberflaeche, bringt aber fuer die genannten Probleme (Symmetrie, Bilder ohne EXIF) keine belegte Verbesserung gegenueber COLMAP; die Messungen, die es gibt, sehen es in Genauigkeit hinter COLMAP und Metashape. Als Ersatz nicht lohnend, hoechstens als unabhaengige Gegenprobe der Posen.
- ODM/OpenSfM ist fuer Bodenaufnahmen eines Einzelgebaeudes mit gemischten Kameras die schlechteste Passung (Annahmen: Raster, GPS, eine Kamera). AGPL beruehrt den Verkauf gedruckter Modelle nicht, nur die Weitergabe/Bereitstellung der Software.
- 3DF Zephyr faellt aus: Windows, Free auf 50 Bilder begrenzt, Kameraexport erst in der teuren Ausgabe.

### Gaps
- Pix4Dmapper/Pix4Dmatic: keine aktuelle Quelle zu Preis, Linux, CLI gefunden. UNBELEGT aus Vorwissen: Windows-Desktop, Abo im Bereich mehrerer hundert Euro je Monat, auf Drohnenbefliegung ausgerichtet; fuer dieses Projekt kaum sinnvoll.
- MicMac: Lizenz (UNBELEGT: CeCILL-B, frei auch kommerziell), Linux-CLI `mm3d` mit Tapioca/Tapas/Malt (UNBELEGT) nicht nachgeprueft. Keine Messung zu Robustheit an ungeordneten Bildsammlungen.
- OpenMVG+OpenMVS: keine Quelle 2022-2026 abgerufen. UNBELEGT: OpenMVG unter MPL2, Entwicklung seit Jahren ruhig; OpenMVS AGPL (im frueheren Bericht belegt).
- Regard3D: keine Quelle gefunden. UNBELEGT: GUI-Programm auf OpenMVG-Basis, seit Jahren nicht gepflegt, nicht skriptbar.
- Meshroom: genaue `meshroom_batch`-Optionen nicht belegt (Doku-Seite lieferte 404); ob ein Knoten fuer COLMAP-Export enthalten ist, nicht bestaetigt (UNBELEGT: `ExportColmap` existierte in 2023.x); VRAM-Bedarf der Tiefenkarten nicht belegt; Lizenz (UNBELEGT: MPL2) nicht nachgeprueft.
- Metashape: Linux-Unterstuetzung, Bedingungen der 30-Tage-Testlizenz und ob sie Python enthaelt, wurden nicht an Agisoft-Quellen bestaetigt. Headless in Standard ungeklaert (Widerspruch oben).
- Kein Vergleich 2022-2026 gefunden, der Registrierungsrate oder Drift fuer COLMAP, Metashape, RealityScan, Meshroom gemeinsam an einem Gebaeude oder Turm misst.

## 3. Neuronale und Feed-Forward-Werkzeuge auf 8 GB

### Takeaway
Feed-Forward-Modelle (VGGT, MapAnything, DUSt3R/MASt3R) liefern COLMAP-kompatible Ausgaben und zum Teil metrische Geometrie, aber keine Quelle belegt 200-500 Bilder auf 8 GB, und eine ISPRS-Studie 2026 bescheinigt ihnen "relatively large residuals"; sie taugen als Starthilfe oder Gegenprobe fuer Teilmengen, nicht als Posenquelle fuer die Kanten-Triangulation.

### Cited Findings
- VGGT: Seit Update vom 15.05.2026 laeuft das Modell bei gleichem GPU-Speicher mit "roughly 2-3x more input frames"; kein fester Hoechstwert und keine Speichertabelle auf der Seite. COLMAP-Export ueber `demo_colmap.py` mit `--scene_dir` (Bilder in `SCENE_DIR/images/`, Ausgabe `SCENE_DIR/sparse/`), optional `--use_ba`, `--max_query_pts` (Standard 4096, sparsam 2048), `--query_frame_num` (Standard 8, sparsam 5). Code seit 29.07.2025 kommerziell nutzbar (ausser Militaer); nur das Gewicht VGGT-1B-Commercial ist kommerziell lizenziert und nur auf Antrag erhaeltlich, VGGT-1B bleibt nicht-kommerziell (Volltext) — [VGGT GitHub](https://github.com/facebookresearch/vggt)
- VGGT-Speicher waechst laut einem Praktiker auf einer T4 "almost linearly" mit der Bildzahl; die 200-Bilder-Angabe der Autoren stammt von H100-Karten (Suchtreffer) — [tztechno Notiz](https://tztechno.github.io/note04), [VGGT Paper](https://arxiv.org/html/2503.11651v1)
- MapAnything: Code Apache 2.0; Gewichte `facebook/map-anything` CC-BY-NC 4.0, `facebook/map-anything-apache` Apache 2.0. Ausgabe metrisch ("directly regresses the factored metric 3D geometry"). Nimmt bekannte Intrinsik, Posen und Tiefen als Eingabe (`intrinsics`, `camera_poses`, `depth_z`, `is_metric_scale`). Sparmodus `memory_efficient_inference=True`: "up to 2000 views on 140 GB". Befehle: `python scripts/demo_colmap.py --images_dir=/YOUR/IMAGES_DIR/ --output_dir=/YOUR/OUTPUT_DIR/` (schreibt `images/` und `sparse/` mit `cameras.bin`, `images.bin`, `points3D.bin`, `points.ply`); `python scripts/demo_inference_on_colmap_outputs.py --colmap_path /path/to/your/colmap_output --viz` (Volltext) — [MapAnything GitHub](https://github.com/facebookresearch/map-anything)
- Feed-Forward-Modelle wie VGGT, Pi3, MapAnything muessen alle Bilder gleichzeitig kodieren; Token wachsen linear, Self-Attention quadratisch mit der Bildzahl (Suchtreffer, Arbeit von 2026) — [arXiv 2603.02351](https://arxiv.org/html/2603.02351)
- ISPRS Annals 2026 (Li, Vosselman, Nex, ITC Twente): Vergleich COLMAP gegen MVSNet, PatchmatchNet, MVSAnywhere, MVSFormer++, Stereo4D, FoundationStereo, DUSt3R, MASt3R, Fast3R, VGGT auf Luftbilddaten (MARS-LVIG mit LiDAR-Referenz, Pix4D-Szene). COLMAP "reliable and geometrically consistent", aber langsam; End-to-End-Verfahren schneller und robuster, wo klassische Registrierung scheitert, aber mit "relatively large residuals in 3D reconstruction, especially in challenging scenarios"; geometriegefuehrte Lernverfahren brauchen meist COLMAP-Posen (Volltext der Zusammenfassung, Zahlen nur im PDF) — [ISPRS Annals XI-2-2026, S. 721-728](https://isprs-annals.copernicus.org/articles/XI-2-2026/721/2026/)
- InstantSfM: Paper behauptet rund 40-fache Beschleunigung gegenueber COLMAP bei vergleichbarer oder besserer Genauigkeit auf 5.000 Bildern, eine GPU, reines PyTorch; COLMAP und GLOMAP scheitern laut Paper haeufig auf ScanNet/ScanNet++ (Suchtreffer, Autorenangaben) — [arXiv 2510.13310](https://arxiv.org/pdf/2510.13310v1); Projektseite ohne Angaben zu Lizenz, Speicher, Ein-/Ausgabeformat (Volltext) — [InstantSfM Projektseite](https://cre185.github.io/InstantSfM/)
- nerfstudio: `ns-process-data {images, video} --data {DATA_PATH} --output-dir {PROCESSED_DATA_DIR}`, braucht COLMAP und FFmpeg; die Doku warnt "COLMAP can be finicky"; Importer fuer Metashape, RealityCapture, ODM, Polycam (Volltext) — [nerfstudio custom data](https://docs.nerf.studio/quickstart/custom_dataset.html)
- Postshot (Jawset): Windows, NVIDIA noetig, kostenlose Stufe; `.ply`-Export seit Maerz 2026 nur noch bezahlt (Suchtreffer) — [radiancefields.com Postshot](https://radiancefields.com/platforms/postshot), [HKU-Anleitung](https://bookstack.hku.nl/books/3d-scan/page/gaussian-splatting-online-and-local)
- Ein Blog nennt 12 GB VRAM als Empfehlung fuer Postshot 2.0 und fuer den INRIA-Originalcode (Suchtreffer, Einzelquelle, unbestaetigt) — [youngju.dev 16.05.2026](https://www.youngju.dev/blog/culture/2026-05-16-3d-gaussian-splatting-photogrammetry-2026-nerfstudio-postshot-luma-genie-polycam-apple-object-capture-realitycapture-deep-dive.en)

### Inferences
- Alle Splatting-Werkzeuge (splatfacto, gsplat, Postshot, Brush) sind Darstellungs-, keine Posenwerkzeuge: sie setzen Kameras aus COLMAP/RealityScan/Metashape voraus und loesen keines der vier genannten Probleme. Der fruehere Bericht hat Splatting als Geometriequelle bereits als Fehlschlag verbucht; daran aendert die Verpackung nichts.
- MapAnything mit dem Apache-Gewicht ist das einzige Feed-Forward-Modell mit sauberer Lizenz fuer spaeteren Verkauf UND der Faehigkeit, eigene Kameras als Eingabe zu nehmen. Sinnvoller Einsatz: metrische Tiefe/Massstab als unabhaengige Gegenprobe (Lage-Veto, Massstabspruefung) auf einer Teilmenge, nicht als Posenquelle.
- VGGT-Posen sind fuer die Kanten-Triangulation zu ungenau, solange nicht `--use_ba` nachzieht; mit Buendelausgleich ist man wieder bei klassischer Optimierung, nur mit anderer Initialisierung. Fuer Bilder ohne EXIF oder schlecht einhaengbare Videobilder koennte genau diese Initialisierung nuetzen (Vermutung).
- Hochrechnung 8 GB: Wenn 2000 Bilder 140 GB brauchen (MapAnything-Sparmodus), entspraeche das bei linearer Skalierung grob 100 Bildern auf 8 GB. Das ist eine eigene Ueberschlagsrechnung, keine Herstellerangabe; die Aufloesung der Eingabebilder und der Grundbedarf des Modells verschieben die Zahl.

### Gaps
- Keine Quelle mit gemessener Bildzahl auf 8 GB fuer VGGT, MapAnything, MASt3R-SfM, DUSt3R oder splatfacto gefunden.
- Brush und gsplat: keine Quelle abgerufen. UNBELEGT aus Vorwissen: beide Apache 2.0; Brush laeuft ueber WebGPU auch ohne CUDA und hat eine Kommandozeile.
- nerfstudio mit hloc: Optionen (`--sfm-tool`, `--feature-type`, `--matcher-type`) stehen in der CLI-Referenz, die nicht abgerufen wurde; daher keine Werte genannt. UNBELEGT: Lizenz von SuperPoint/SuperGlue in hloc ist nicht kommerziell, ALIKED/DISK+LightGlue waeren frei.
- MASt3R/DUSt3R: Lizenz (UNBELEGT: CC BY-NC-SA, also nicht fuer spaeteren Verkauf) nicht nachgeprueft; MASt3R-SfM-Speichertabelle im Suchtreffer abgeschnitten.
- InstantSfM: Code-Repository, Lizenz und VRAM-Bedarf nicht gefunden; ob es eine COLMAP-Datenbank als Eingabe nimmt, unbelegt.
- Postshot: Preis, CLI und offizielle VRAM-Anforderung nicht an jawset.com geprueft.
- "Instant"-Apps auf DUSt3R/VGGT-Basis fuer Endnutzer: keine belastbare Quelle zu einem Produkt gefunden, das 200+ Bilder auf 8 GB verarbeitet.

## 4. Unabhaengige Vergleiche: Robustheit, Drift, symmetrische Szenen, Kulturerbe

### Takeaway
Es gibt keine unabhaengige Messung 2022-2026, die Registrierungsrate oder Seitenverwechslung an symmetrischen Gebaeuden ueber COLMAP, Metashape, RealityScan und Meshroom vergleicht; vorhandene Studien messen fast nur die Dichte-Genauigkeit an Kleinobjekten oder Drohnenbloecken und sehen Metashape meist vorn, COLMAP in der Mitte, Meshroom dahinter.

### Cited Findings
- Sensors 2021: Metashape 0,212 mm, COLMAP+MVS 0,441 mm, Meshroom 0,868 mm mittlerer Abstandsfehler am selben Bildsatz (Suchtreffer) — [PMC8659967 Tabelle 4](https://pmc.ncbi.nlm.nih.gov/articles/PMC8659967/table/sensors-21-08026-t004)
- ISPRS 2022, sechs Werkzeuge an Baustellendaten: Metashape am besten (Suchtreffer) — [ISPRS Archives XLIII-B2-2022](https://isprs-archives.copernicus.org/articles/XLIII-B2-2022/141/2022/isprs-archives-XLIII-B2-2022-141-2022.pdf)
- ISPRS 2025: ODM vergleichbar mit Metashape, Unterschiede bei Kalibrierung und Orientierung (Volltext Abstract) — [ISPRS Archives XLVIII-1/W4-2025](https://isprs-archives.copernicus.org/articles/XLVIII-1-W4-2025/65/2025/)
- ISPRS 2026: COLMAP geometrisch am verlaesslichsten gegenueber gelernten Verfahren (Volltext Abstract) — [ISPRS Annals XI-2-2026](https://isprs-annals.copernicus.org/articles/XI-2-2026/721/2026/)
- eCAADe 2021 pruefte, ob Meshroom Metashape an zwei Kulturerbe-Objekten ersetzen kann (Suchtreffer, Ergebnis nicht im Treffer) — [AMiner-Eintrag](https://www.aminer.org/pub/6347eb9e90e50fcafd36d6ae/comparative-analysis-of-open-source-and-commercial-photogrammetry-software-for-cultural-heritage)
- Kingsland 2020 verglich Metashape, ContextCapture und RealityCapture an einem Kleinartefakt (Suchtreffer) — [CORE](https://core.ac.uk/download/220107531.pdf)
- Symmetrie/Doppelgaenger ist als Fehlerursache nur in der Forschungsliteratur dokumentiert: doppelte Strukturen fuehren zu falsch platzierten Kameras und "disconnected building sides"; Heinly et al. 2014, Cohen et al. 2012, Doppelgangers (ICCV 2023) mit gelerntem Paarfilter (Suchtreffer) — [Heinly ECCV 2014](https://www.cs.unc.edu/~jheinly/publications/eccv2014-heinly.pdf), [Doppelgangers arXiv 2309.02420](https://arxiv.org/pdf/2309.02420.pdf), [Cohen CVPR 2012](https://snsinha.github.io/pdfs/CohenCVPR2012.pdf)
- Eine gezielte Suche nach Forenberichten zu Symmetriefehlern in RealityCapture, Metashape oder Meshroom lieferte keinen Treffer zu den Produkten, nur die Forschungsarbeiten (eigene Suche, 15.11.2026) — [Doppelgangers-Uebersicht](https://mlanthology.org/iccv/2023/cai2023iccv-doppelgangers)

### Inferences
- Kein Hersteller dokumentiert einen Doppelgaenger-Filter. Die kommerziellen Programme begegnen dem Problem ueber Bedienkonzepte: getrennte Komponenten statt erzwungener Gesamtloesung, Passpunkte, GPS-/Flugprotokoll-Vorgaben. Das ist dieselbe Logik wie die im frueheren Bericht empfohlenen GPS-Tore, nur eingebaut. Ein Programmwechsel beseitigt die Seitenverwechslung also nicht von selbst; er liefert aber eine zweite, unabhaengig berechnete Loesung, an der sich eine Verwechslung zeigt, wenn beide Loesungen widersprechen.
- Die besseren Dichte-Zahlen von Metashape sind fuer dieses Projekt wenig wert, weil die Wolke nur Lage-Veto ist; entscheidend waere Posen-Genauigkeit, und dafuer fehlen Vergleichszahlen.

### Gaps
- Keine Benchmarks an Tuermen/Stadttoren; keine Registrierungsraten fuer gemischte Sammlungen (Handy, Kamera, Videobilder, Fremdbilder ohne EXIF).
- Volltexte der ISPRS-Arbeiten 2025/2026 (Zahlen) und des Meteora-Kapitels wurden nicht gelesen.
- Keine Quelle zu Geistergeometrie durch schlecht verortete Videobilder in anderen Programmen.

## 5. Hybrid-Ablaeufe: Posen aus Werkzeug A, Dichte/Kanten in der eigenen Kette

### Takeaway
Der Weg "fremde Posen -> COLMAP-Format" ist 2026 bei RealityScan (ab 2.1/2.1.1), Metashape (ab 2.1.3/2.2, korrekt ab 2.3.0 Build 21778), VGGT und MapAnything direkt eingebaut; die Hauptgefahr sind abweichende Verzeichnungsmodelle und Hauptpunkt-Konventionen, weshalb der Export entzerrter Bilder mit Pinhole-Kameras der sichere Standard ist.

### Cited Findings
- COLMAP-Textformat besteht aus `cameras.txt`, `images.txt`, `points3D.txt`; die Standardausgabe der Entzerrung enthaelt einen Ordner `images` mit entzerrten Bildern (Suchtreffer) — [COLMAP Output Format](https://colmap.github.io/format.html)
- RealityScan: COLMAP-Export wahlweise entzerrt oder passend zu Originalbildern, binaer oder ASCII, Standard-Verzeichnis oder flach; eigene Entzerrung mit OpenCV/COLMAP trifft laut Nutzerbericht das Sichtfeld nicht exakt — [Epic Doku 2.1.1](https://dev.epicgames.com/documentation/en-us/realityscan/realityscan-2-1-1), [Forum Image undistortion](https://forums.unrealengine.com/t/reality-scan-image-undistortion/2574748)
- RealityScan liest auch COLMAP-Projekte ein: `importColmap filePath params.xml` — [All Commands](https://dev.epicgames.com/documentation/realityscan/all-commands)
- Metashape: p1/p2-Tausch, Halbpixel-Hauptpunkt, `b1`/`b2`, `k4`; sichere Variante `convert_to_pinhole=True` — [Metashape Expert Manual Verzeichnung](https://photogrammetrycommunity.github.io/metashape-expert-manual/workflow/camera-calibration/distortion-model-opencv-colmap/)
- Import von COLMAP-Kamerapositionen nach Metashape wird in der COLMAP-Gruppe diskutiert (nur Titel gesehen) — [COLMAP Google Group](https://groups.google.com/g/colmap/c/zyRUJ4rTQyI), [COLMAP Discussion 2409](https://www.github.com/colmap/colmap/discussions/2409)
- MapAnything rechnet auf vorhandenen COLMAP-Ausgaben: `python scripts/demo_inference_on_colmap_outputs.py --colmap_path /path/to/your/colmap_output --viz` — [MapAnything GitHub](https://github.com/facebookresearch/map-anything)
- VGGT schreibt `sparse/` im COLMAP-Format, optional mit Buendelausgleich (`--use_ba`) — [VGGT GitHub](https://github.com/facebookresearch/vggt)

### Inferences
- Empfohlene Hybrid-Kette fuer den Versuch: RealityScan (Linux-CLI oder Windows) nur bis zur Ausrichtung -> COLMAP-Export mit entzerrten Bildern -> eigene Tore (GPS-Tor, Grundriss-Tor, `kamera_abdeckung.py`) -> eigener Kanten-Sweep auf den entzerrten Bildern -> bei Bedarf COLMAP PatchMatch auf demselben Export. Damit ist nur EIN Verzeichnungsmodell im Spiel.
- Umgekehrte Richtung als zweiter Nutzen: die eigene COLMAP-Loesung per `importColmap` in RealityScan laden und nur dessen (out-of-core, schnelle) Netzberechnung nutzen. Das wuerde die 50-125 Minuten Tiefenkarten ersetzen, falls die Qualitaet fuer das Lage-Veto reicht (Vermutung, zu messen).
- Pruefung nach jedem Import: (1) Rueckprojektionsfehler der mitgelieferten 3D-Punkte in den uebernommenen Kameras nachrechnen, (2) Hauptpunkt gegen (W-1)/2 vergleichen, (3) Bildgroesse der entzerrten Bilder gegen `cameras.txt` pruefen, (4) Massstab und Achsen gegen Foto-GPS (`lage_gps_pruefen.py`), weil jedes Programm ein eigenes Weltkoordinatensystem setzt.
- Plattenplatz: Entzerrte Bildkopien von 500 Bildern plus Projektcache kosten mehrere GB je Versuch; bei fast voller 98-GB-Partition vor dem Versuch aufraeumen oder den Versuch auf der Windows-Partition fahren.

### Gaps
- COLMAPs eigene Importer (`model_converter`, Bundler-/NVM-Eingang) wurden nicht in der aktuellen 4.x-Doku nachgeschlagen. UNBELEGT aus Vorwissen: `colmap model_converter --input_path ... --output_path ... --output_type {BIN,TXT,NVM,Bundler,VRML,PLY,...}` exportiert; fuer den Import fremder Posen ist der uebliche Weg, `cameras.txt`/`images.txt` selbst zu schreiben und mit `point_triangulator` die Punkte neu zu rechnen. Vor Verwendung in der COLMAP-4.3-Hilfe pruefen.
- Ob RealityScans COLMAP-Export Kameramodelle wie `OPENCV`/`FULL_OPENCV` oder nur `PINHOLE` schreibt, wenn "Originalbilder" gewaehlt ist, wurde nicht geklaert (Forumthread "pinhole option" nicht gelesen).
- Kein belegter Konverter Meshroom-sfmData -> COLMAP fuer 2025.1.

## 6. Cloud-Dienste und Miet-GPUs

### Takeaway
Zu den Verbraucher-Clouddiensten wurden nur Preisangaben aus Sammelseiten gefunden, keine belastbaren Angaben zu Bildgrenzen, Posen-Export oder Automatisierung; fuer eine skriptgesteuerte Kette, die Kameraposen braucht, sind sie nach Quellenlage nicht geeignet, und Miet-GPUs loesen kein Robustheitsproblem.

### Cited Findings
- Polycam: 2026 laut einer Sammelseite Stufen Free, Basic (30 USD/Monat oder 150 USD/Jahr), Business (400 USD/Jahr je Nutzer), Enterprise; die fruehere Pro-Stufe sei entfallen (Suchtreffer, Zweitquelle; angeblich im Juli 2026 an poly.cam/pricing geprueft) — [SkyeBrowse App-Vergleich](https://www.skyebrowse.com/news/posts/best-photogrammetry-app)
- nerfstudio kann Polycam-Rohdaten nur von LiDAR-iPhone/iPad im Entwicklermodus lesen: `ns-process-data polycam --data {OUTPUT_FILE.zip} --output-dir {output directory}` (Volltext) — [nerfstudio custom data](https://docs.nerf.studio/quickstart/custom_dataset.html)
- KIRI Engine: iOS/Android/Web, kostenlose Stufe, bezahlte Stufe ab 79,99 USD/Jahr (Suchtreffer, Sammelseite) — [iTechGuides](https://www.itechguides.com/best/ai-3d-scanning-software/)
- Luma: Suchtreffer zeigen 2026 vor allem Videogenerierung (ab 9,99 USD/Monat); fuer die Aufnahme-/Splat-Funktion werden bereits "Alternativen" gelistet (Suchtreffer) — [radiancefields.com Luma-Alternativen](https://radiancefields.com/luma-ai-alternatives), [toolradar](https://toolradar.com/tools/luma-ai/pricing)
- RealityScan-Linux ist ausdruecklich fuer Server/Docker mit GPU-Durchreichung gedacht, also auch auf Miet-GPUs einsetzbar (Volltext) — [RealityScan for Linux](https://dev.epicgames.com/documentation/en-us/realityscan/realityscan-for-linux)

### Inferences
- Die Rechenzeiten der eigenen Kette (15 min bis Posen, 50-125 min dicht) rechtfertigen keine Cloud; der Engpass ist Robustheit und Plattenplatz, nicht Rechenleistung. Eine Miet-GPU mit 24+ GB waere nur fuer einen VGGT/MapAnything-Versuch mit allen 500 Bildern sinnvoll.
- Verbraucher-Apps geben in der Regel Netze/Splats aus, keine Kameraparameter; ohne Posen-Export sind sie fuer die Kernmethode wertlos. (Schluss aus fehlenden Belegen, nicht aus einer Quelle.)

### Gaps
- Autodesk ReCap Photo: keine Quelle zu Preis, Cloud-Credits oder Bildgrenze 2026 gefunden.
- Bildgrenzen je Auftrag, Nutzungsrechte an hochgeladenen Fotos/Ergebnissen und API-Zugang fuer Polycam, KIRI, Luma nicht an Herstellerseiten geprueft.
- Stundenpreise fuer Miet-GPUs nicht recherchiert.

## 7. Empfehlung fuer Eintagesversuche (Synthese)

### Takeaway
Einen Tag wert ist nur RealityScan (Linux-CLI, sonst Windows-Partition) als zweite, unabhaengige Posenquelle mit COLMAP-Export; ein halber Tag fuer MapAnything (Apache-Gewicht) als metrische Gegenprobe ist vertretbar; alles andere scheitert an Lizenzkosten, Betriebssystem, fehlender Automatisierung oder fehlendem Beleg fuer einen Vorteil.

### Cited Findings
- RealityScan: kostenlos unter 1 Mio. USD Umsatz, Linux-CLI ab 8 GB VRAM, Befehle `headless`, `addFolder`, `align`, `mergeComponents`, `exportRegistration`, `importColmap` — [Lizenz](https://www.realityscan.com/en-US/license), [Linux](https://dev.epicgames.com/documentation/en-us/realityscan/realityscan-for-linux), [All Commands](https://dev.epicgames.com/documentation/realityscan/all-commands)
- Metashape: Python nur Professional, 3.499 USD — [Agisoft Store](https://www.agisoft.com/buy/online-store/), [Agisoft Features](https://www.agisoft.com/index.php?id=42)
- 3DF Zephyr: Free 50 Bilder, Kameraexport erst ab 4.200 EUR — [3Dflow](https://www.3dflow.net/3df-zephyr-photogrammetry-software/)
- MapAnything: Apache-Gewicht, metrisch, nimmt COLMAP-Ausgaben — [MapAnything GitHub](https://github.com/facebookresearch/map-anything)
- Gelernte Verfahren mit groesseren Restfehlern als COLMAP — [ISPRS Annals 2026](https://isprs-annals.copernicus.org/articles/XI-2-2026/721/2026/)

### Inferences
Rangfolge (eigene Bewertung aus den Befunden oben):
1. RealityScan, ein Tag. Ablauf: Linux-Build laden (falls Wine-Build zickt: Windows-Partition) -> `.rscmd`-Datei mit `headless`, `newScene`, `addFolder`, `align`, ggf. `mergeComponents`, `selectMaximalComponent`, Export der Registrierung als COLMAP mit entzerrten Bildern, `save`, `quit` -> eigene Tore auf das Ergebnis. Messgroessen: Zeit bis Posen, Zahl der Komponenten und registrierten Bilder, Verhalten am symmetrischen Turm (Seitenverwechslung ja/nein laut GPS-Tor), Verhalten der Bilder ohne EXIF, Foto-F1 des Kanten-Sweeps mit diesen Kameras gegen die COLMAP-Kameras. Zweitmessung: `importColmap` der eigenen Loesung + `calculateNormalModel` als Ersatz fuer PatchMatch (Zeit, Plattenbedarf).
2. MapAnything (Apache), halber Tag: `scripts/demo_inference_on_colmap_outputs.py` auf 50-100 Bildern einer Fassade, nur als Massstabs-/Lage-Gegenprobe. Abbruch, wenn 8 GB nicht reichen.
3. Metashape nur, falls eine Testlizenz mit Python verfuegbar ist; dann als dritte Posenquelle mit Passpunkten aus LoD2. Kauf von Professional ist fuer ein Hobbyprojekt nicht zu rechtfertigen, Standard ist nicht skriptbar.
4. Nicht versuchen: 3DF Zephyr, Pix4D, ODM/OpenSfM, Regard3D, OpenMVG, Postshot/Brush/splatfacto als Posen- oder Geometriequelle, Verbraucher-Cloud-Apps. Meshroom und MicMac nur, wenn eine dritte freie Gegenprobe gebraucht wird.

Was ein Programmwechsel NICHT loest: Seitenverwechslung am symmetrischen Turm (kein Programm hat einen belegten Doppelgaenger-Filter), Geistergeometrie durch schlechte Videobilder (Bildauswahl), LoD2-Ausrichtung (bleibt eigenes Werkzeug; RealityScan/Metashape bieten dafuer nur Passpunkt-Import).

### Gaps
- Die Rangfolge beruht auf Lizenz, Automatisierbarkeit und Funktionsumfang, NICHT auf gemessener Ueberlegenheit; fuer keinen Kandidaten liegt eine unabhaengige Messung an 200-500 gemischten Bildern eines Einzelgebaeudes vor.
- Vor dem RealityScan-Versuch offen: Aktivierung des Linux-Builds, Cache-Groesse auf der Platte, genaue Exportparameter (`params.xml`) fuer COLMAP.
