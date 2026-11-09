# Recherche Kanten 2: Luecken zu RECHERCHE_KANTEN_MULTIVIEW_2026-11-09.md (Stand 2026-11-09)

Nicht wiederholt: Detektor-Tabelle (DeepLSD, ScaleLSD, HAWP, SOLD2, DexiNed, TEED), LIMAP/Line3D++ Grundaussagen, VP-Einrasten.
Markierung: "belegt" = diese Sitzung per Web/pip/Code geprueft; "(unverifiziert)" = aus Wissen/Suchtreffer, vor Nutzung pruefen. Lizenz von Gewichten und Trainingsdaten (ScanNet, MegaDepth, BSDS, Wireframe) vor Verkauf einzeln klaeren.

## Lokalbefund (belegt, venv-seg, Python 3.12.3)
- OpenCV dort: `opencv-python 5.0.0.93`, `cv2.ximgproc` NICHT vorhanden (kein contrib) -> EdgeDrawing/EDLines/EDCircles fehlen. `cv2.createLineSegmentDetector` (LSD) ist da.
- `opencv-contrib-python 5.0.0.93` existiert auf PyPI; es darf NICHT neben opencv-python installiert sein (gleicher Namensraum cv2). Weg: in einem eigenen Test-venv `opencv-contrib-python` (statt opencv-python) installieren; im Produktiv-venv erst nach Test tauschen.
- torch 2.15, kornia 0.9.0, lightglue vorhanden; `rcpark`-venv: numpy-Importfehler (cv2), fuer diese Arbeit unbrauchbar.
- Vorhanden auf PyPI (belegt per `pip index`): `pylimap 2.0.0`, `romatch 0.1.2`, `romav2 2.0.1`. Kein `pyelsed`.

## 1. Kantenqualitaet ohne manuelle Wahrheit

Datensaetze mit Linien-Wahrheit (alle 2D, kein Renaissance-Fassadenbezug; (unverifiziert) bei Zahlen):
- Wireframe/ShanghaiTech (Huang 2018, ca. 5000 Train/462 Test, Innen+Aussen) und York Urban (102 Bilder, Manhattan-Linien): Standard fuer Liniensegmente. Metriken: sAP5/10/15 (Endpunktabstand, L-CNN-Definition, belegt), heatmap-AP/F^H, sF (LETR). Beleg: [LETR](https://arxiv.org/pdf/2101.01909), [York-Ranking](https://hyper.ai/en/sota/tasks/line-segment-detection/benchmark/line-segment-detection-on-york-urban-dataset).
- Repeatability/Localization-Error von Linien: Metrik aus [SOLD2](https://github.com/cvg/SOLD2) auf HPatches (Homographie-Paare), plus ELSD-Paper ([arXiv 2104.14205](https://arxiv.org/pdf/2104.14205)). Prinzip uebertragbar: Detektion in Bild A, per bekannter Geometrie nach B abbilden, in B detektieren, Treffer zaehlen.
- Kanten dichte Karten: BIPED (250 Bilder, DexiNed), BSDS500 (Forschungslizenz). Fassadenparsing: CMP Facade DB (606 Bilder, Rechtecke/Fenster), ECP (104 Haussmann-Fassaden, Labels), ParisArtDeco. Alle fuer Fensterraster/Segmente, keine Bogenkanten.
- 3D-Linien: LIMAP wertet auf Hypersim (synthetisch) und Tanks&Temples gegen Mesh/Wahrheit aus (Precision/Recall bei Abstandsschwellen) (unverifiziert im Detail; [Paper](https://arxiv.org/abs/2303.17504)). Gebaeude-Wireframe: [LC2WF / BuildingWF](https://arxiv.org/pdf/2208.11948), synthetisch aus Roof-Image, Code `Luo1Cheng/LC2WF`. ETH3D/Tanks&Temples haben KEINE Kantenwahrheit, nur Scan/Mesh (unverifiziert).
- Fazit: Fuer die eigene Fassade gibt es keine fertige Wahrheit. Die Datensaetze taugen nur, um einen NEUEN Detektor/Parameter generell zu bewerten (York Urban in einer Stunde einbaubar), nicht die Pipeline-Ausgabe.

Wahrheitsfreie Metriken fuer die eigene Pipeline (vorgeschlagen, nach Staerke):
1. Synthetischer Rundlauf (stark): vorhandenes Kaufhaus-/CAD-Modell mit Texturen oder Fotos als Ebenenbild rendern, Posen mit dem gemessenen cm-Fehler stoeren, Pipeline laufen lassen, gegen die exakt bekannten Modellkanten messen (sAP/Abstand in mm). Das ist wiederholbarer Pruefstand-Sollwert. Achtung Synthetik != Echtbefund (Lehre 8.11.).
2. Held-out-Reprojektion (schwach, schon gebaut): Linien in nicht benutzte Fotos projizieren, Abstand zur dortigen Fotokante (Chamfer, Rauschboden mit Zufallsversatz). Blind fuer systematische Posenfehler.
3. Geometrie-Konsistenz: Winkelabweichung zu Manhattan-Richtungen, Abstand der 3D-Linien zu Wolken-Ebenen, Anteil Linien mit Track-Laenge >= k Fotos (LIMAP-Track-Statistik), Streuung der Einzelfoto-Positionen je Linie (Mediankonsistenz).
4. Kleine Handwahrheit (empfohlen als Anker): 6-10 Fotos/Ortho-Ausschnitte (Bogen, Fensterreihe, Statue) per Labeltool mit Polylinien beschriften (ca. 2-3 h), Nutzer macht es einmal; damit sAP/Chamfer. Danach nur noch automatisch.

## 2. Planare Feinregistrierung vor dem Stapeln

- Problem: Posenfehler cm -> in Ortho-Ebene Versatz mehrerer Pixel; Parallaxe von Teilen ausserhalb der Ebene bleibt (Homographie loest das nicht, Elemente mit Tiefenversatz maskieren/eigene Ebene).
- Dichte Korrespondenz in der Ebene: Ortho-Ansichten sind fast gleich orientiert/skaliert, daher einfache Faelle. Reihenfolge nach Aufwand:
  a) ECC (`cv2.findTransformECC`, Homographie/Affin) oder Phasenkorrelation auf Gradienten-/Kantenbild: Minuten Aufwand, subpixel, nur bei guter Startlage.
  b) [LightGlue](https://github.com/cvg/LightGlue) (SuperPoint/DISK) + RANSAC-Homographie auf den Ortho-Bildern: schon im venv. Lizenz Code Apache-2.0 (unverifiziert); SuperPoint-Gewichte Forschungslizenz (MagicLeap), DISK-Gewichte mit Pruefbedarf.
  c) Dichte Matcher [RoMa](https://github.com/Parskatt/RoMa) (belegt: Code MIT ausser DINOv2 = Apache-2.0; README sagt nichts zur Lizenz der Gewichte; `pip install romatch` 0.1.2, getestet Python 3.12) und [RoMa v2](https://pypi.org/project/romav2/) (Nov 2025, [arXiv 2511.15706](https://arxiv.org/abs/2511.15706); Code MIT ausser DINOv3 mit eigener DINOv3-Lizenz, Gewichtelizenz unbestaetigt). Liefert pro Pixel Fluss -> nicht nur Homographie, sondern Rest-Verzug (Flow) je Foto; subpixel nicht ausdruecklich dokumentiert, in Ortho-Anwendungen ca. 3 px Fehler bei Fremdmodalitaet gemessen ([Studie](https://en.papernotes.org/CVPR2026/remote_sensing/pretrained_image_matchers_for_sar_optical_satellite_registration/)), bei gleicher Modalitaet besser zu erwarten (unverifiziert, selbst messen).
  d) kornia LoFTR/EfficientLoFTR: Code Apache-2.0 ([zju3dv/LoFTR](https://github.com/zju3dv/LoFTR), belegt); Gewichte ohne Lizenzangabe, Training auf ScanNet/MegaDepth (ScanNet = nicht-kommerziell, (unverifiziert)) -> Verkaufsrisiko. RoMa/LightGlue vorziehen oder nur zum Testen.
- Wichtige Entscheidung: nicht Foto an Foto, sondern jedes Foto gegen EINE Referenz (scharfstes Foto oder vorlaeufiger Median) registrieren, 2-3 Iterationen (Median neu bilden). Pruefmass: Residuum nach Registrierung auf Kantenkarten; Vorher/Nachher Streuung der Kantenposition je Linie.
- Beantwortung: Ja, loest den Posenrest in der Ebene weitgehend (besonders Flow/Homographie je Foto), aber nicht Parallaxe. Alternative bleibt Posen per Line-/Point-BA verbessern (LIMAP).

## 3. Bogen und Kurven

- OpenCV `cv2.ximgproc.EdgeDrawing` ([Doku 5.x](https://docs.opencv.org/5.x/d1/d1c/classcv_1_1ximgproc_1_1EdgeDrawing.html), belegt): implementiert ED, EDLines, EDPF, EDCircles; Python: `detectEdges(src)`, `detectLines()`, `detectEllipses()` (Kreise/Ellipsen), `setParams`. In venv-seg FEHLT contrib (siehe oben), also erst Test-venv. Ausgabe von detectEllipses: Kreise (x,y,r) und Ellipsen; BEACHTE: EDCircles liefert nur ganze Kreise/Ellipsen, auch Bogenstuecke werden zu Vollellipse extrapoliert (unverifiziert, prueffen), und ist parameterarm aber nicht parameterfrei. Aufwand klein, Vorsicht bei Kreisen auf Statuen.
- [ELSDc](https://github.com/potato34/ELSDc) (Patraucean/Gurdjos/von Gioi, a-contrario, [TPAMI 2016](https://www.springerprofessional.de/a-parameterless-line-segment-and-elliptical-arc-detector-with-en/3986308)): parameterfrei, liefert Linien UND elliptische Boegen mit NFA-Signifikanz. Lizenz AGPL-3.0 (belegt) -> fuer Verkaufsprodukt nicht einbinden; nur als Testorakel (Kommandozeile, nur PGM, braucht CLAPACK) nutzbar. In `modelle/LIZENZ_WERKZEUGE.md` als NC/AGPL eintragen.
- Eigenbau (empfohlen, lizenzfrei): Kantenkarte DexiNed/TEED (oder Hartschwelle auf DeepLSD-Distanzfeld) -> Kantenzuege verketten -> Kreis/Ellipse per RANSAC mit Bogenwinkel-Grenze (Rundbogen: Kreis, Mittelpunkt auf Kaempferlinie, Radius R~1,9 m aus der Wolke als Prior, vgl. Stand 7.11.), Verfeinerung per `skimage.measure.EllipseModel`/`cv2.fitEllipseDirect` oder nichtlinear (Abstand zur Kante, GPU nicht noetig, aber Voting auf Torch moeglich). Mehrfoto: Bogenparameter MEHRERER Fotos im Metermass mitteln (Median je Parameter) statt Kanten stapeln -> Bogenform kommt aus wenigen Zahlen (Mittelpunkt, R, Winkelbereich), das beseitigt die Polygonstuecke direkt. Eine Parametrisierung passt auch zum Ziel CAD-Solid.
- Parametrische Splines/Bezier aus Kantenkarten mit differenzierbarem Fit: [SketchSplat](https://arxiv.org/abs/2503.14786) (3D, Lizenz/Rasterizer offen, zurueckgestellt).
- Fehllinien auf Statuen: Maske (OWLv2/SAM2 "Statue", "Figur") vor der Linienstapelung; Linien nur akzeptieren, wenn Abstand zur Ebene < Toleranz in der Wolke (Statuen stehen vor der Ebene) - billigster Filter.

## 4. Fensterraster und Fassadenregularisierung

- Klassiker: [Quasi-Regular Facade Structure Extraction (Han et al., ACCV 2012)](https://researchwith.stevens.edu/en/publications/quasi-regular-facade-structure-extraction/): unregelmaessiges Rechteckgitter aus wiederholten Fenstern, Low-Rank-Regularisierung. Gute Vorlage fuer "Gitterlinien teilen".
- Neu (belegt, nur Abstract gelesen): [Beyond Segmentation: Structurally Informed Facade Parsing (Eurographics 2026, arXiv 2604.09260)](https://arxiv.org/pdf/2604.09260): YOLOv8 + Grid-Konsistenz-Loss auf CMP, Code/Lizenz nicht geprueft. [FacAID](https://themoonlight.io/fr/review/faaid-a-transformer-model-for-neuro-symbolic-facade-reconstruction): Segmentierung -> editierbares prozedurales Programm, rauschempfindlich. [SVI2LoD3 (arXiv 2608.29992)](https://arxiv.org/pdf/2608.29992): SAM + LLM-Agent fuer LoD3-Oeffnungen aus Strassenbildern (Arxiv-Nummer ungewoehnlich, vor Verlass pruefen). Kein Fund, der direkt CAD-Solid mit Gitter-Regularisierung liefert; als Idee: Fenster-Detektion (OWLv2, vorhanden) -> Mittelpunkte/Boxen -> Gitter durch 1D-Clustering (Mean-Shift auf x-Kanten und y-Kanten, Periodizitaet per Autokorrelation) -> Fenstermasse = Median je Spalte/Zeile -> Rasterlinien ersetzen Einzelkanten. Das ist ein Eigenbau von etwa 150 Zeilen und braucht keine neue Bibliothek.
- SAM2 ([facebookresearch/sam2](https://github.com/facebookresearch/sam2), Apache-2.0 (unverifiziert)) liefert gute Fenstermasken; Masken -> minimale Rechteckanpassung (bei Rundbogenfenstern Rechteck + Halbkreis). OWLv2 liefert Box; SAM2 verfeinert. Regelwerk: Fenster einer Reihe gleiche Hoehe/Oberkante/Breite, Abstand periodisch, Toleranz aus Messrauschen (nicht lockern, um Gruen zu bekommen; Regel 1).
- Zaehlregel 9 (CLAUDE.md) bleibt: Anzahl der Fenster nur am Foto zaehlen (OWLv2 auf Foto ist erlaubt, nicht aus Wolke).

## 5. 3D-Linienrekonstruktion aus Multi-View mit bekannten Posen

- **LIMAP-Installationsweg (belegt)**: [pylimap 2.0.0 auf PyPI](https://pypi.org/project/pylimap/) (veroeffentlicht 04.09.2026, ETH CVG / Shaohui Liu, BSD-3-Clause). Wheels fuer CPython 3.10-3.13 (also 3.12 OK), Linux x86-64 glibc >= 2.28; Import weiter `import limap`. Extras `viz` (open3d) und `line2d` (einops, scikit-image, pillow). Quellverteilung nicht vorhanden. Also KEIN Quellbau noetig - die Aussage der Vorrecherche (Build COLMAP/Ceres) ist ueberholt. Einschraenkungen: Vollpipeline braucht `hloc` (nicht auf PyPI, aus requirements/Git), Detektoren HAWP/TP-LSD/LBD/RoMa/Progressive-X separat; DeepLSD/SOLD2/GlueStick laut Projekt als Zusatz. Eigene Posen: LIMAP liest COLMAP-Rekonstruktion (cameras/images/points3D) oder eigene Listen (Kamera-Modelle PINHOLE/SIMPLE_RADIAL); ihr habt `kaufhaus_alle/sfm` -> direkt. Probe in neuem venv: `python3.12 -m venv v-limap && pip install pylimap[all] torch` + Beispiel `runners/...` mit 20 Fotos.
- Aufwand: Install 0,5 Tag inkl. Adapter fuer die Posen; Lauf auf 440 Fotos zuerst als Teilmenge (50-80, nach `foto_wichtigkeit.py`). Triangulation CPU (RAM beachten), Detektion GPU (Regel: GPU von Anfang an, Detektionsteil auf CUDA).
- Line3D++: [manhofer/Line3Dpp](https://github.com/manhofer/Line3Dpp) MPL-2.0, KEIN pip-Paket (unverifiziert), CMake-Bau mit Eigen/Boost/OpenCV; als Vergleichsbasis, nicht Erstwahl. [CLMAP](https://github.com/3dv-casia/clmap) (Neuere Linien-Mapping-Methode, Lizenz nicht geprueft).
- Neural/Gaussian: EdgeGaussians (keine Lizenz), SketchSplat (Rasterizer-Lizenz offen), LineGS u.a.: Training je Szene, Lizenzluecken -> nicht erste Wahl.
- Hinweis: LIMAP ersetzt nicht die Bogenfits; 3D-Linien fuer Gesimse/Erkerkanten, Bogen weiter parametrisch.

## 6. Fertiges lizenzunkritisches Werkzeug "Kanten fuer Photogrammetrie"?

- Fertiges End-to-End-Werkzeug gibt es nicht. Naechste Bausteine: LIMAP (BSD-3, Linien aus Fotos + Posen, ca. der Kern), OpenMVG/OpenMVS/Meshroom/COLMAP rekonstruieren nur Punkte/Flaechen (Linien-Plugin nicht gefunden; COLMAP-Erweiterung = LIMAP/hloc). RealityCapture ist proprietaer (Kantenextraktion nicht offen, nicht verkaufbar integrierbar).
- Alternative OpenCV-basiert (BSD/Apache): EdgeDrawing/EDLines/EDCircles (contrib, siehe Abschnitt 3; EDLines aus dem 2011-er ED-Paper, Patent-Status (unverifiziert) vor Verkauf pruefen), LSD in OpenCV (seit 4.5.1 wieder frei, belegt im Build vorhanden), ELSED (BSD) als schneller Segmentdetektor.

## Priorisierte Handlungsliste (max. 6)

1. **Synthetischer Kantenpruefstand** (Qualitaetsmessung): Modell/CAD rendern, Posen stoeren, Pipeline laufen lassen, Chamfer/sAP gegen exakte Kanten; dazu 6-10 handbeschriftete Echt-Ausschnitte (Bogen, Fensterreihe, Statue). Aufwand 1-1,5 Tage + 2-3 h Nutzer. Ohne das ist jede weitere Verbesserung nicht messbar.
2. **Bogen parametrisch fitten** (Kreis/Ellipse per RANSAC auf Kantenkarte, Parameter ueber Fotos mitteln, Wolken-Radius als Prior; Statuenmaske + Ebenenabstand als Filter). Aufwand 1 Tag. Loest "Polygonstuecke" und "Fehllinien auf Statuen" direkt. Optional EdgeDrawing-Test in separatem contrib-venv (0,5 h).
3. **Feinregistrierung je Foto vor dem Stapeln**: erst ECC/Phasenkorrelation auf Kantenkarten (0,5 Tag), danach RoMa-Flow-Variante (1 Tag) als Vergleich; Pruefmass Streuung je Linie vorher/nachher. Gewichte-Lizenz RoMa einzeln pruefen.
4. **Fensterraster-Regularisierung**: OWLv2 (vorhanden) + SAM2-Masken -> 1D-Clustering/Autokorrelation -> Gitterlinien, Fenstermasse Median je Spalte/Zeile. Aufwand 1-2 Tage. Zaehlen am Foto (Regel 9).
5. **pylimap 2.0.0 Probe** (Wheel Py3.12, BSD-3) in eigenem venv mit 20-80 Fotos der vorhandenen SfM, Detektor DeepLSD/ScaleLSD; Ziel: 3D-Linientracks fuer Gesimse/Erkerkanten, Vergleich mit Ortho-Stapel per Punkt 1. Aufwand 1-2 Tage (hloc-Abhaengigkeit, Posen-Adapter).
6. **Lizenzliste pflegen** (`modelle/LIZENZ_WERKZEUGE.md`): ELSDc AGPL-3.0 (nicht einbinden), LoFTR-Gewichte/ScanNet, RoMa-v2-Gewichte (DINOv3-Lizenz), SuperPoint, EdgeGaussians (ohne Lizenz), EDLines-Patentfrage. Aufwand 2 h.

## Quellen
- https://pypi.org/project/pylimap/ , https://github.com/cvg/limap , https://arxiv.org/abs/2303.17504
- https://github.com/Parskatt/RoMa , https://pypi.org/project/romav2/ , https://arxiv.org/abs/2511.15706
- https://github.com/zju3dv/LoFTR
- https://docs.opencv.org/5.x/d1/d1c/classcv_1_1ximgproc_1_1EdgeDrawing.html
- https://github.com/potato34/ELSDc
- https://arxiv.org/pdf/2101.01909 , https://arxiv.org/pdf/2104.14205 , https://arxiv.org/pdf/2208.11948
- https://arxiv.org/pdf/2604.09260 , https://arxiv.org/pdf/2608.29992 , https://researchwith.stevens.edu/en/publications/quasi-regular-facade-structure-extraction/
- https://en.papernotes.org/CVPR2026/remote_sensing/pretrained_image_matchers_for_sar_optical_satellite_registration/
