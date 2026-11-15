# Fassadendetails aus Fotokanten: LoD2 -> LoD3 mit 3D-Linien/-Kurven (Stand Mitte November 2026)

Hinweise zur Lesart:
- "geprueft" = Repo-Seite oder Paper in dieser Recherche direkt abgerufen. "UNGEPRUEFT" = nur aus Suchtreffer-Zusammenfassung oder Vorwissen, vor Einsatz LICENSE-Datei/README selbst lesen.
- VRAM- und Laufzeitangaben fehlen in fast allen READMEs; wo keine Quelle existiert, steht das unter "Gaps". Schaetzungen stehen nur unter "Inferences".
- Keine Options- oder Skriptnamen ausser denen, die auf den abgerufenen Seiten standen.

## 1. 3D-Linien- und Kurvenrekonstruktion aus Fotos mit bekannten Kameras

### Takeaway
LIMAP (jetzt Version 2.0.0, BSD-3, liest/schreibt COLMAP-Modelle, per pip installierbar) ist der einzige ausgereifte, frei lizenzierte Baukasten und der naheliegende erste Versuch; es bringt seit 2026 auch eine Buendelausgleichung mit Parallelitaet/Koplanaritaet mit. Die neuronalen Kanten-Verfahren (EMAP, EdgeGaussians, CurveGaussian, SketchSplat, SGCR) liefern Kurven statt nur Geraden, sind aber auf kleinen Objekten (ABC, DTU) belegt, haben teils keine Lizenz und kaum Unterstuetzung fuer eigene COLMAP-Daten.

### Cited Findings

LIMAP und Abkoemmlinge (geometrisch, Geradenstuecke)
- LIMAP (Liu, Yu, Pautrat, Pollefeys, Larsson, CVPR 2023) ist ein Baukasten fuer Linien-Mapping und Lokalisierung; Lizenz BSD-3-Clause (geprueft). — [cvg/limap](https://github.com/cvg/limap)
- LIMAP 2.0.0 ist laut README "fully compatible with the COLMAP ecosystem (version 4.2.0 as of Sep 1, 2026)", nimmt eine vorhandene COLMAP-Rekonstruktion (bekannte Posen) als Eingabe und schreibt Ergebnisse als normale COLMAP-Modelle, die `pycolmap` liest; Linien-, Gruppen- und Wireframe-Strukturen liegen unter `structures/`. — [cvg/limap](https://github.com/cvg/limap)
- Installation: Python 3.10-3.13, CMake >= 3.17, CUDA fuer die gelernten Detektoren/Matcher; Kurzweg `python -m pip install pylimap` (nur Kernbibliothek), aus Quelle `python -m pip install -r requirements.txt` und `python -m pip install -Ive ".[all]"`; `hloc` kommt aus `requirements.txt`. — [cvg/limap](https://github.com/cvg/limap)
- Unterstuetzte Detektoren in LIMAP: LSD, SOLD2, HAWP, TP-LSD, DeepLSD, UPAL; Matcher: LBD, SOLD2, LineTR, L2D2, SuperPoint-Endpunkte (NN oder SuperGlue), GlueStick, ein RoMa-basierter Matcher; Fluchtpunkte ueber JLinkage oder Progressive-X. — [cvg/limap](https://github.com/cvg/limap)
- LIMAP hat einen "holistic SfM"-Modus, der laut README Punkte, Linien, Fluchtpunkte, Ebenen und das Wireframe gemeinsam optimiert. — [cvg/limap](https://github.com/cvg/limap)
- Zugehoeriges Paper "Stable and Scalable Bundle Adjustment of Holistic 3D Structures" (Liu, Pautrat, Barath, Hartley, Larsson; arXiv 2609.04026, Kommentar "To appear at ECCV 2026"): Gruppen hoeherer Ordnung (genannt: Koplanaritaet, Parallelitaet, Wireframes, Punkt-Linien-Zuordnung) werden als kameraartige Einheiten modelliert und als 2D-Reprojektionsfehler ausgedrueckt; Laufzeit laut Autoren vergleichbar mit reiner Punkt-BA; Code als Teil von LIMAP. — [arXiv 2609.04026](https://arxiv.org/abs/2609.04026)
- Das LIMAP-Paper berichtet deutlich vollstaendigere und genauere Linienkarten als Line3D++ und ELSR (Hypersim, Tanks and Temples). — [LIMAP Paper CVPR 2023](https://openaccess.thecvf.com/content/CVPR2023/papers/Liu_3D_Line_Mapping_Revisited_CVPR_2023_paper.pdf)
- IncreLM (BMVC 2024) baut auf LIMAP auf, rekonstruiert Linien inkrementell und nutzt Ausreisser-Matches frueherer Linien fuer spaetere; Autoren behaupten bessere Vollstaendigkeit/Genauigkeit und laengere Tracks. Lizenz BSD-3-Clause (geprueft), Eingabe COLMAP-Sparse-Modell + Bildordner, Detektoren LSD und DeepLSD, Matcher GlueStick (Top 10); README nennt COLMAP 3.8 und keine Zahlen/Laufzeiten. — [3dv-casia/IncreLM](https://github.com/3dv-casia/IncreLM), [BMVC-Paper](https://bmva-archive.org.uk/bmvc/2024/papers/Paper_256/paper.pdf)
- CLMAP (gleiche Gruppe, 3dv-casia) wird in spaeteren Arbeiten als Vergleichsverfahren neben LIMAP gefuehrt. — [3dv-casia/clmap](https://github.com/3dv-casia/clmap)
- LiP-Map ("Interacted Planes Reveal 3D Line Mapping", arXiv 2602.01296): Szene als lernbare 3D-Rechteck-Ebenen (auf PlanarSplatting aufbauend), Ebenenkanten sind die 3D-Linienkandidaten; 2D-Linien werden per Strahl einer Ebenenkante zugeordnet, kein 2D-Linien-Matching noetig. Eingaben: Posen, 2D-Linien (LSD, HAWPv3, DeepLSD, ScaleLSD getestet) sowie Tiefen-/Normalenkarten (GT oder aus Omnidata/Metric3Dv2). — [arXiv 2602.01296](https://arxiv.org/html/2602.01296v1)
- LiP-Map Zahlen (5 mm, ScanNetV2 mit DeepLSD): Recall 0,350 gegen 0,106 (LIMAP) und 0,161 (CLMAP); 3015 Linien gegen 397 bzw. 613; Genauigkeit aber nicht durchweg besser, und LIMAP/CLMAP bauen laengere Tracks mit mehr Stuetzbildern. Laufzeit ca. 333 s je Szene (100 Ansichten) auf einer RTX A6000 mit 48 GB; Code unter github.com/calmke/LiPMAP, Lizenz nicht genannt. Nur Innenraum-Datensaetze. — [arXiv 2602.01296](https://arxiv.org/html/2602.01296v1)
- LineGS (arXiv 2412.00477) kombiniert geometrisch rekonstruierte 3D-Linien mit einem 3D-Gaussian-Splatting-Modell zur Nachbesserung der Linien. — [arXiv 2412.00477](https://arxiv.org/pdf/2412.00477)

Neuronale Kantenfelder / Gaussian-Kanten (Kurven)
- EMAP ("3D Neural Edge Reconstruction", CVPR 2024) lernt Kantenabstand und -richtung als Unsigned Distance Function aus Mehrbild-Kantenkarten; die Autoren begruenden das mit einem systematischen Fehler des Kantendichtefelds von NEF. — [arXiv 2405.19295](https://arxiv.org/html/2405.19295v1)
- EMAP-Repo: "The majority of EMAP is licensed under a MIT License"; Kantenkarten aus vortrainiertem DexiNed und PiDiNet; "Custom Dataset Support" ist im README nicht abgehakt, Trainingsskripte nur fuer ABC-NEF, Replica, DTU; keine Angabe zu VRAM/Laufzeit im README. — [cvg/EMAP](https://github.com/cvg/EMAP)
- EdgeGaussians (arXiv 2409.12886): Kantenpunkte als 3D-Gaussians mit Hauptachse = Kantenrichtung. Trainingszeit laut Tabelle 0:05 h auf ABC-NEF und DTU gegen NEF 1:26/1:50 h und EMAP 2:30/12:00 h. — [arXiv 2409.12886](https://arxiv.org/html/2409.12886v2)
- ABC-NEF-Vergleich aus dem EdgeGaussians-Paper (Autorenangabe): F-Score bei 5/10/20 mm: LIMAP(LSD) 39,0/84,3/90,4; NEF 12,3/51,8/88,7; EMAP 59,1/88,9/94,9; EdgeGaussians 45,2/93,7/95,7. Completeness-Fehler LIMAP 18,7 gegen EMAP 8,9 und EdgeGaussians 8,4. DTU bei 5 mm: Recall LIMAP 74,9, NEAT 66,4, EMAP 77,5, EdgeGaussians 87,7. — [arXiv 2409.12886](https://arxiv.org/html/2409.12886v2)
- Eingestandene Schwaechen von EdgeGaussians: heuristisches Clustering versagt in Teilen komplexer Szenen, dicke 2D-Kantenkarten verzerren, feine Strukturen und vom 2D-Detektor verpasste Kanten fehlen; Replica und Tanks and Temples nur qualitativ. — [arXiv 2409.12886](https://arxiv.org/html/2409.12886v2)
- EdgeGaussians-Repo: keine LICENSE-Datei sichtbar (geprueft: kein Lizenz-Eintrag); Daten im EMAP-Format; ein "colmap data parser" existiert, ist laut README "not been tested widely"; Ausgabe PLY (gefilterte Gaussians mit Hauptrichtung, entlang gefitteter Kurven abgetastete Punkte). — [kunalchelani/EdgeGaussians](https://github.com/kunalchelani/EdgeGaussians)
- CurveGaussian ("Curve-Aware Gaussian Splatting for 3D Parametric Curve Reconstruction", arXiv 2506.21401): einstufig, optimiert parametrische 3D-Kurven direkt aus 2D-Kantenkarten, mit adaptiver Topologie (Linearisieren, Verschmelzen, Teilen, Ausduennen). Das Paper bemaengelt an EMAP unvollstaendige und an EdgeGaussians fragmentierte Ergebnisse (Konkurrenzaussage, nicht unabhaengig). — [arXiv 2506.21401](https://arxiv.org/abs/2506.21401)
- SketchSplat (arXiv 2503.14786) optimiert parametrische 3D-Kanten ("sketches") ueber differenzierbares Rastern in 2D-Kantenbilder; SGCR (arXiv 2505.04668) nutzt sphaerische Gaussians fuer parametrische 3D-Kurven. — [arXiv 2503.14786](https://arxiv.org/pdf/2503.14786), [arXiv 2505.04668](https://arxiv.org/pdf/2505.04668)
- NEAT (CVPR 2024) rekonstruiert 3D-Wireframes ohne explizites Linien-Matching, indem 3D-Liniensegmente aus neuronalen Feldern gerendert werden. — [NEAT CVPR 2024](https://openaccess.thecvf.com/content/CVPR2024/papers/Xue_NEAT_Distilling_3D_Wireframes_from_Neural_Attraction_Fields_CVPR_2024_paper.pdf)

### Inferences
- Das eigene Verfahren (Kanten-Tiefen-Sweep um die Modellflaeche, Zaehlen stabiler Kanten in Nachbarfotos) ist im Kern ein Plane-Sweep fuer Kanten ohne Matching. Es entspricht der Idee hinter LiP-Map/EMAP (Kante wird im 3D gesucht, Fotos stimmen ab), waehrend LIMAP umgekehrt 2D-Segmente matcht und trianguliert. Beide Wege ergaenzen sich: LIMAP liefert lange, zusammenhaengende Segmente mit Track (welche Fotos, welche 2D-Segmente) und ist nicht an das +-0,25-0,5 m Band gebunden; der Sweep liefert Kurven und Punkte dort, wo kein Geradenstueck vorliegt (Masswerk, Boegen).
- Die drei benannten Probleme lassen sich so zuordnen: (a) Fragmentierung -> LIMAP-Track-Bildung und Segment-Verschmelzung, danach die 2026er BA mit Parallelitaet/Koplanaritaet; (b) Mehrdeutigkeit paralleler Rippen -> im Sweep die Abstimmung nicht je Pixel, sondern je 2D-Segment/Segmentgruppe fuehren (ganze Rippenschar gemeinsam verschieben, Reihenfolge-Erhalt als Nebenbedingung) und Fotos mit grosser Basis quer zur Rippenrichtung bevorzugen; LIMAP hilft hier nur begrenzt, weil Linien-Matcher bei sich wiederholenden Strukturen selbst verwechseln; (c) Features ausserhalb des Bandes (Erker, Speier, Baldachine) -> LIMAP ohne Band laufen lassen und dessen 3D-Segmente als neue lokale Stuetzflaechen fuer den Sweep verwenden.
- Fuer 8 GB VRAM ist LIMAP unkritisch einzuschaetzen: GPU wird nur fuer Detektor/Matcher je Bild(paar) gebraucht, Triangulation und BA laufen auf CPU (22 Kerne nutzbar). Das ist eine Einschaetzung aus dem Aufbau, keine dokumentierte Zahl.
- EdgeGaussians ist mit 5 Minuten Training auf kleinen Szenen der billigste Test eines Kurvenverfahrens, aber wegen fehlender Lizenz und kaum getesteter COLMAP-Anbindung nur als Experiment (nicht als Pipeline-Baustein) geeignet. EMAP mit 2,5-12 h je Szene und ohne Custom-Data-Pfad lohnt als erster Versuch nicht.
- Alle neuronalen Kantenverfahren haengen an denselben 2D-Kantenkarten (DexiNed/PiDiNet). Die eigenen Stabilitaetskarten koennten diese Eingabe direkt ersetzen; das ist der wahrscheinlichste Hebel, weil die Paper selbst dicke/verrauschte Kantenkarten als Hauptfehlerquelle nennen.
- LiP-Map passt konzeptionell gut zu "LoD2 als Startflaeche" (Ebenen aus dem Blockmodell statt aus Tiefenpriors initialisieren), ist aber nur auf Innenraeumen mit einer 48-GB-Karte belegt und ohne geklaerte Lizenz.

### Gaps
- Keine Quelle mit Messungen von LIMAP, EMAP oder EdgeGaussians auf historischen Fassaden (Sandstein, Masswerk); alle Zahlen stammen von ABC-NEF, DTU, Hypersim, ScanNet, Tanks and Temples.
- VRAM-Bedarf und Laufzeit: weder LIMAP- noch EMAP-, EdgeGaussians- oder IncreLM-README nennen Werte.
- Line3D++ (manuelhofer/Line3Dpp) und ELSR: Lizenz und Pflegezustand in dieser Recherche nicht abgerufen; UNGEPRUEFT. Beide gelten laut LIMAP-Paper als ueberholt.
- NEAT-Repo: die vermutete Adresse cvg/NEAT gibt 404; richtige Adresse und Lizenz nicht geprueft. NEF-Code und -Lizenz ebenfalls nicht geprueft.
- CurveGaussian: Code-Adresse, Laufzeit und Kurventyp standen nicht auf der Abstract-Seite; SketchSplat/SGCR: Code-Verfuegbarkeit nicht geprueft.
- Welche LIMAP-Module genau die neue Gruppen-BA ausfuehren und wie man sie aufruft, steht nicht auf den abgerufenen Seiten.
- Kurvenbasiertes SfM/MVS im klassischen Sinn (z. B. Kurven-Triangulation ohne neuronales Feld): keine aktuelle, gepflegte offene Implementierung gefunden.

## 2. 2D-Linien-, Kanten- und Knotendetektoren sowie Linien-Matcher als Eingabe

### Takeaway
DeepLSD (MIT, Code und Gewichte) und ScaleLSD (MIT, CVPR 2025) sind die beiden frei nutzbaren Liniendetektoren der Wahl; TEED (MIT, 58k Parameter) ist der leichteste gelernte Kantendetektor. Beim Matching ist Vorsicht geboten: GlueStick-Code ist MIT, das Gesamtsystem wegen SuperPoint aber nicht-kommerziell.

### Cited Findings
- DeepLSD: Code MIT, vortrainierte Gewichte ebenfalls MIT ("Both models are released under an MIT license"). Das Netz liefert neben Segmenten ein Distanz- und Winkelfeld; `export_features` kann mit `--pred_vps` Fluchtpunkte mit ausgeben; ein Verfeinerungsskript verbessert Segmente beliebiger Detektoren (braucht Vollinstallation mit Ceres). Getestet mit Python 3.7/CUDA 11. — [cvg/DeepLSD](https://github.com/cvg/DeepLSD)
- ScaleLSD (Ke et al., CVPR 2025): selbstueberwacht auf ueber 10 Mio. unbeschrifteten Bildern trainiert, ViT-Base-Backbone mit DPT-Kopf, baut auf HAWPv3 auf; Autoren nennen es den ersten gelernten Detektor, der das klassische LSD in allen getesteten Aufgaben (Fluchtpunkte, Zweibild-Matching, Mehrbild-3D-Linien) uebertrifft, und attestieren DeepLSD Skalierungsprobleme. — [arXiv 2506.09369](https://arxiv.org/html/2506.09369v1), [CVPR 2025 Open Access](https://openaccess.thecvf.com/content/CVPR2025/html/Ke_ScaleLSD_Scalable_Deep_Line_Segment_Detection_Streamlined_CVPR_2025_paper.html)
- ScaleLSD-Repo: Lizenz MIT (geprueft); getestet Ubuntu 22.04, CUDA 12.1, Python 3.10, PyTorch 2.5.1; Aufruf `python -m predictor.predict --img [PATH]`, Ausgabe png/pdf/json, Schalter `--use_lsd`/`--use_nms`, Knotenoptionen; Gewichte auf Hugging Face (cherubicxn/scalelsd); Matching-Demo auf GlueStick; LIMAP nur als "Related Third-party Project", keine fertige Integration. — [ant-research/scalelsd](https://github.com/ant-research/scalelsd)
- LiP-Map testet LSD, HAWPv3, DeepLSD und ScaleLSD als austauschbare Eingaben fuer 3D-Linien; die Ergebnisse haengen merklich vom Detektor ab (eigene Tabellen je Detektor). — [arXiv 2602.01296](https://arxiv.org/html/2602.01296v1)
- GlueStick ("Joint deep matcher for points and lines"): Code MIT, aber README: SuperPoint-Backbone hat nicht-kommerzielle Lizenz, daher "the overall system is non-commercial"; eine DISK-Variante war angekuendigt. — [cvg/GlueStick](https://github.com/cvg/GlueStick)
- TEED ("Tiny and Efficient Edge Detector"): MIT laut Repo; 58k Parameter ("less than 0.2% of the state-of-the-art models"); Training auf BIPED in unter 30 Minuten. — [xavysp/TEED](https://github.com/xavysp/TEED)
- EMAP und EdgeGaussians verwenden DexiNed und PiDiNet als 2D-Kantenquelle; EdgeGaussians nennt verrauschte, dicke Kantenkarten ausdruecklich als Fehlerquelle. — [cvg/EMAP](https://github.com/cvg/EMAP), [arXiv 2409.12886](https://arxiv.org/html/2409.12886v2)
- LIMAP bindet als Matcher u. a. SOLD2, LineTR, L2D2, GlueStick und einen RoMa-basierten Matcher an. — [cvg/limap](https://github.com/cvg/limap)

### Inferences
- Fuer das Projekt sind die Detektoren mit Feld-Ausgabe (DeepLSD: Distanz-/Winkelfeld) interessanter als reine Segmentlisten: das Distanzfeld ist eine weiche, subpixelgenaue Kantenkarte und koennte im Tiefen-Sweep die harte Stabilitaetskarte ergaenzen (glatterer Peak, weniger Fragmentierung). Die Linienrichtung aus dem Winkelfeld erlaubt, im Sweep nur Nachbarfoto-Kanten gleicher projizierter Richtung zu zaehlen - das reduziert Fehltreffer zwischen Rippen und Fugen.
- Die eigene Stabilitaetskarte (Kante ueberlebt viele Vorverarbeitungen) ist methodisch dieselbe Idee wie die Homographie-Adaption, mit der DeepLSD/SOLD2/ScaleLSD ihre Pseudo-Labels erzeugen. Ein Vergleich Stabilitaetskarte gegen DeepLSD-Distanzfeld am Foto-F1 ist daher ein billiger, aussagekraeftiger Test.
- Auf verwittertem Sandstein erzeugen generische Kantendetektoren (DexiNed, PiDiNet, TEED) erfahrungsgemaess viele Textur-/Fugenkanten; Liniendetektoren mit Segment-Hypothese (DeepLSD, ScaleLSD) unterdruecken das besser, verlieren aber Boegen und Masswerk. Fuer Masswerk bleibt eine Kantenkarte plus Kurvenverfahren noetig. Das ist Einschaetzung, nicht belegt.
- Wegen der SuperPoint-Lizenz ist GlueStick fuer ein rein privates Modellbauprojekt nutzbar, fuer Verkauf von Modellen/Daten aber heikel; ALIKED+LightGlue (im Projekt schon Standard) deckt nur Punkte ab. Der RoMa-basierte Linien-Matcher in LIMAP waere die Alternative; dessen Lizenz ist zu pruefen.

### Gaps
- Kein Benchmark gefunden, der Detektoren auf verwitterten Natursteinfassaden oder gotischem Masswerk vergleicht.
- Lizenzen UNGEPRUEFT (nicht abgerufen): DexiNed, PiDiNet, HAWP/HAWPv3, SOLD2, LineTR, LETR, RoMa. Vor Nutzung jeweils LICENSE lesen; insbesondere PiDiNet und RoMa-Gewichte koennten Einschraenkungen haben.
- Ob GlueStick inzwischen eine DISK- oder ALIKED-Variante mit freier Lizenz veroeffentlicht hat, steht nicht im README.
- Modellgroesse und VRAM von ScaleLSD (ViT-Base) sind im README nicht angegeben; bei voller Fotoaufloesung ist Kacheln wahrscheinlich noetig (Annahme).
- LETR und reine Wireframe-Parser (L-CNN, HAWP v1/v2) sind auf Innenraum-Wireframes trainiert; aktuelle Aussenfassaden-Ergebnisse nicht gefunden.

## 3. Fassaden-Parsing, Elementerkennung, Wiederholung/Zaehlen, Laibungstiefe

### Takeaway
Der Stand 2025/2026 ist: Foto auf die LoD2-Wandebene entzerren, dann mit Foundation-Modellen (SAM 2/SAM 3, Zero-Shot) segmentieren; Entzerrung allein bringt laut Texture2LoD3 rund 11 % Segmentierungsgewinn. Fuer Wiederholungen/Zaehlen existieren nur klassische Gitter-/Low-Rank-Verfahren auf entzerrten Fassaden, kein fertiges gelerntes Werkzeug; fuer Laibungstiefe aus Mehrbild-Fotos wurde keine dedizierte offene Methode gefunden.

### Cited Findings
- Texture2LoD3 (Tang, Li, Liang, Wysocki, Biljecki, Holst, Jutzi; CVPR-Workshop 2025): nutzt LoD1/LoD2-Modelle als ebene Ziele, um Panorama-Strassenbilder zu orthorektifizieren, und segmentiert dann die Fassade; fuehrt den Datensatz ReLoD3 ein; Segmentierungsgenauigkeit auf entzerrten Bildern um 11 % besser als auf unentzerrten. — [arXiv 2504.05249](https://arxiv.org/html/2504.05249v1)
- Si und Yao (ISPRS Archives XLIX-B2, 2026): LoD2 -> LoD3 ueber vorhandene Texturkarten, SAM2-Segmentierung und UV-basierte Rueckprojektion (Fallstudie Hongkong). — [ISPRS Archives XLIX-B2-2026, 1267](https://isprs-archives.copernicus.org/articles/XLIX-B2-2026/1267/2026/isprs-archives-XLIX-B2-2026-1267-2026.pdf)
- Saadatseresht et al. (ISPRS Archives XLIX-B2, 2026): LoD1 -> LoD3-Fassaden aus OSM-Grundrissen, sphaerischen Strassenbildern und schwachen Punktwolken-Priors. — [ISPRS Archives XLIX-B2-2026, 539](https://isprs-archives.copernicus.org/articles/XLIX-B2-2026/539/2026/)
- SVI2LoD3 (arXiv 2608.29992): agentengesteuerte Kette aus Sprach- und Bildmodellen, Zero-Shot-Segmentierung, rekonstruiert Fassadenoeffnungen als CityGML-konformes LoD3; stark auf eTRIMS laut Autoren (Abstract ohne Zahlen); fuehrt die Metrik "Facade Feature Distance" ein; Code github.com/hcu-cml/citydb-SVI2LoD3-ai (Lizenz nicht genannt). — [arXiv 2608.29992](https://arxiv.org/abs/2608.29992)
- SAM 3 ("Segment Anything with Concepts", arXiv 2511.16719): segmentiert erschoepfend alle Instanzen eines Konzepts, das als kurze Nominalphrase oder Beispielbild vorgegeben wird; keine komplexen/verweisenden Textanfragen; 30 ms je Bild mit 100+ Objekten (Herstellerangabe, Hardware dort nachlesen). Lizenz: eigene "SAM License" von Meta, kein Standard-Open-Source-Text. — [arXiv 2511.16719](https://arxiv.org/html/2511.16719v2), [facebookresearch/sam3](https://github.com/facebookresearch/sam3), [Roboflow-Erklaerung](https://blog.roboflow.com/what-is-sam3/)
- ZAHA (Wysocki et al., WACV 2025): groesster 3D-Fassaden-Segmentierungsdatensatz, 601 Mio. annotierte Punkte, 5 Klassen (LoFG2) bzw. 15 Klassen (LoFG3, u. a. Wand, Fenster, Tuer, Balkon), aus TUM-MLS-2016 (Muenchen); Vorgaenger TUM-FACADE (nur Universitaetsgebaeude) und ArCH (Kulturerbe). Punktwolken-, kein Fotodatensatz. — [ZAHA WACV 2025](https://openaccess.thecvf.com/content/WACV2025/html/Wysocki_ZAHA_Introducing_the_Level_of_Facade_Generalization_and_the_Large-Scale_WACV_2025_paper.html), [arXiv 2411.04865](https://arxiv.org/abs/2411.04865v3)
- Wiederholungserkennung klassisch: Wenzel, Drauschke, Foerstner (Bonn 2007) finden auf entzerrten Fassaden wiederholte Strukturen ohne Fenstermodell und geben eine Hierarchie von Translationen samt Wiederholungszahlen aus. — [Wenzel et al. 2007](https://www.ipb.uni-bonn.de/pdfs/Wenzel2007Detection.pdf)
- Liu et al.: Kronecker-Produkt-Low-Rank-Modell erkennt wiederholte Muster (Fenster, Balkone) auf entzerrten Fassadenbildern. — [IEEE TPAMI/Journal 8417901](https://ieeexplore.ieee.org/document/8417901)
- Wolff et al. (CVPR 2016): Gitter + Median-Kachel als Fassadenbeschreibung; jede translatorische Verschiebung des Gitters ist eine gleich gute Partition (inhaerente Mehrdeutigkeit, relevant fuers Zaehlen an Raendern). — [Wolff 2016](https://www.cvlibs.net/projects/autonomous_vision_survey/literature/Wolff2016CVPR.pdf)
- Csurka et al. (CVPR 2020) sagen selbstueberwacht Low-Rank-Wahrscheinlichkeitskarten aus einem Bild vorher; Ma et al. (KSII 2022) nutzen Wiederholungsmuster als Vorwissen, um verdeckte Fenster zu ergaenzen. — [Csurka CVPR 2020](https://openaccess.thecvf.com/content_CVPR_2020/papers/Csurka_Estimating_Low-Rank_Region_Likelihood_Maps_CVPR_2020_paper.pdf), [Ma et al. 2022](https://koreascience.kr/article/JAKO202210261250365.page)
- Mitra et al. (Eurographics 2013 STAR) fassen strukturbewusste Fassadenbearbeitung/Symmetrie zusammen. — [UCL Discovery](https://discovery-pp.ucl.ac.uk/id/eprint/1393828/1/Mitra_interactiveFacades_eg13_small.pdf)

### Inferences
- Das Projekt hat bereits alles fuer den entscheidenden Vorverarbeitungsschritt: aus SfM-Kameras und Generator-Modell laesst sich je Wandflaeche ein Orthofoto (und ein Stapel Orthofotos aus mehreren Kameras) rechnen. Darauf werden Wiederholung, Zaehlen und Segmentieren deutlich einfacher (konstante Periode in Metern statt perspektivisch verzerrt). Das Zaehlen bleibt damit regelkonform "am Foto", nur am entzerrten.
- Praktikabler Zaehl-Baustein ohne neues Modell: Autokorrelation/FFT der Kanten-Stabilitaetskarte im Orthofoto entlang der Rippen-Normalen liefert Periode und Anzahl; ein SAM-3-Lauf mit Beispielbox ("ein Fenster"/"eine Konsole") dient als unabhaengige Gegenzaehlung. Stimmen beide nicht ueberein -> Beobachtung offen statt Mittelwert.
- Das Gruppieren von 3D-Kanten zu Elementen (Fenster, Gesimsprofil) laesst sich als Zuordnungsproblem loesen: SAM-Masken im Orthofoto liefern Elementregionen; alle 3D-Kanten, deren Projektion in/auf dem Maskenrand liegt, gehoeren zum Element. Das ersetzt die manuelle Gruppierung, ohne die Form aus der Maske zu nehmen (Form bleibt aus Kanten).
- Laibungstiefe: da kein fertiges Verfahren gefunden wurde, ist der eigene Sweep der direkte Weg - je Fenstermaske zwei Kantenringe (aeussere Laibungskante auf Wandebene, innere Kante am Rahmen/Glas) und deren Tiefendifferenz; Schraegansichten von links und rechts sind noetig, weil je Ansicht eine Laibungsseite verdeckt ist. Spiegelndes Glas liefert keine stabilen Kanten, der Rahmen schon.
- Die grossen Fassadendatensaetze (CMP, ECP, eTRIMS, ZAHA) enthalten Gruenderzeit-/Moderne-Fassaden mit Rechteckfenstern; fuer Gotik (Erker, Masswerk, Baldachine, Speier) ist kein trainiertes Fassadenmodell zu erwarten, nur Zero-Shot/Beispiel-Prompting.

### Gaps
- Keine Quelle zu SAM 3, Grounding DINO oder offenen Zaehlmodellen (z. B. CountGD) speziell auf Fassaden gefunden; Eignung fuer gotische Elemente unbelegt.
- Lizenzen UNGEPRUEFT: Grounding DINO, SAM 2 (beide nach Vorwissen Apache-2.0), CMP Facades, ECP, LabelMeFacade, eTRIMS (Datensatzlizenzen nicht abgerufen). SAM-3-Lizenztext nicht im Detail gelesen (kommerzielle Bedingungen offen).
- VRAM von SAM 3 nicht ermittelt; ob es auf 8 GB bei voller Aufloesung laeuft, ist offen.
- Keine dedizierte, offene Methode fuer Fenster-Laibungstiefe aus Mehrbild-Fotos gefunden; die LoD3-Arbeiten setzen Oeffnungen meist mit Standardtiefe oder aus Laser-Konflikten.
- Die Details von SVI2LoD3 (welche Modelle, wie 3D-Lage) konnten nicht gelesen werden (PDF zu gross fuer den Abruf).

## 4. LoD2 -> LoD3 in der Forschung (TUM u. a.), inverse prozedurale Modellierung

### Takeaway
Die TUM-Linie (Scan2LoD3, CM2LoD3, FacaDiffy) baut auf Laserstrahl-Konfliktkarten gegen das LoD2-Modell und ist nur teilweise und mit proprietaeren Bausteinen (FME) offen; die fotobasierte Linie (Texture2LoD3, SVI2LoD3, SAM2-Texturansatz) erzeugt nur Oeffnungen als flache/standardisierte Elemente. Kein Verfahren liefert gotische Detailgeometrie; als Ideenquelle taugen Konfliktkarten (Foto-statt-Laser) und neuro-symbolische Split-Grammatiken (FacAID).

### Cited Findings
- Scan2LoD3 (Wysocki et al., CVPR-Workshop 2023): fusioniert drei Wahrscheinlichkeitskarten (Strahl-Konflikte Laser gegen Modell, Punktwolken-Semantik, Bildsemantik) mit einem Bayes-Netz zu Fassadenoeffnungen fuer LoD3. — [Scan2LoD3 CVPRW 2023](https://openaccess.thecvf.com/content/CVPR2023W/PCV/papers/Wysocki_Scan2LoD3_Reconstructing_Semantic_3D_Building_Models_at_LoD3_Using_Ray_CVPRW_2023_paper.pdf)
- Scan2LoD3-Repo: sieben Stufen - Ray Casting (C++), Mask-RCNN (Python), Point Transformer (Python), Konfidenz/Projektion, Bayes-Netz (R), Formextraktion (FME), CityGML-Modellierung (FME); keine Lizenzangabe und keine Releases auf der Seite. — [OloOcki/scan2lod3](https://github.com/OloOcki/scan2lod3)
- CM2LoD3 lernt Fassadensemantik aus Konfliktkarten (Strahl gegen Modell-Prior) fuer LoD3 (nur ueber Sekundaerseite gefunden, UNGEPRUEFT am Original). — [Emergent Mind CM2LoD3](https://www.emergentmind.com/topics/cm2lod3)
- FacaDiffy ergaenzt nicht gesehene Fassadenteile, indem Konfliktkarten mit einem personalisierten Stable-Diffusion-Modell inpainted werden; Code laut Autoren unter dem GitHub-Konto ThomasFroech (Verfuegbarkeit nicht geprueft). — [MCML-Publikationsseite](https://mcml.ai/publications/tll+25/)
- MLS2LoD3 verfeinert niedrige LoDs mit mobilen Laserscans zu LoD3. — [arXiv 2402.06288](https://arxiv.deeppaper.ai/papers/2402.06288v1)
- Texture2LoD3, SVI2LoD3, Si/Yao, Saadatseresht: fotobasierte LoD3-Wege, siehe Abschnitt 3. — [arXiv 2504.05249](https://arxiv.org/html/2504.05249v1), [arXiv 2608.29992](https://arxiv.org/abs/2608.29992)
- FacAID (SIGGRAPH Asia 2024): Transformer, der segmentierte Fassadenbilder in prozedurale Definitionen einer eigens entworfenen Split-Grammatik uebersetzt. — [arXiv 2406.01829](https://arxiv.org/html/2406.01829v2)
- Pro-DG kombiniert inverse prozedurale Rekonstruktion (FacAID-Grammatik) mit Diffusions-Bildsynthese fuer Fassaden (Sekundaerquelle). — [Moonlight-Review Pro-DG](https://www.themoonlight.io/review/pro-dg-procedural-diffusion-guidance-for-architectural-facade-generation)
- Nishida, Bousseau, Aliaga (Eurographics 2018): prozedurales Gebaeudemodell aus einem Foto; Stufen aus CNN-Grammatikauswahl plus Parameteroptimierung; Kamera und Baumasse aus Silhouette. — [Nishida et al. 2018](https://www.cs.purdue.edu/cgvlab/www/resources/papers/Nishida-EUROGRAPHICS-2018-Procedured_Modeling_of_a_Building.pdf)
- Hu et al.: halbueberwachte Erkennung verfeinerter Fensterstrukturen fuer inverse prozedurale Fassadenmodellierung. — [arXiv 2201.08977](https://arxiv.org/pdf/2201.08977)
- Martinovic und Van Gool: Bayes'sches Grammatiklernen; Parsing mit gelernten Grammatiken uebertrifft Bottom-up-Klassifikatoren. — [Bayesian Grammar Learning](https://typeset.io/pdf/bayesian-grammar-learning-for-inverse-procedural-modeling-19swhybxhj.pdf)

### Inferences
- Die Konfliktkarten-Idee laesst sich ohne Laser uebertragen: der eigene Kanten-Sweep liefert je Wandpixel "Kantenbeleg vor/auf/hinter der Modellflaeche". Eine Karte "Beleg hinter der Flaeche" markiert Oeffnungen/Nischen (Arkaden, Laibungen), "Beleg vor der Flaeche" markiert Vorspruenge (Erker, Gesimse, Speier). Das ist genau die Aufteilung "confirming/conflicting" der TUM-Arbeiten und waere ein automatischer Fehlteile-Finder, der das Band-Problem sichtbar macht (viele Belege am Bandrand = Band zu eng).
- Der prozedurale Generator des Projekts (Python/manifold3d) ist faktisch schon eine handgeschriebene Formgrammatik. Der Nutzen der Literatur liegt daher nicht in CGA/CityEngine, sondern in der Parameterschaetzung (Nishida: Auswahl + Optimierung) - siehe Abschnitt 8.
- Bibliotheksansaetze (Element aus 3D-Katalog waehlen und einpassen) passen fuer Rechteckfenster, nicht fuer individuelle gotische Bauteile; fuer wiederholte Elemente (Arkadenboegen, Konsolen, Baldachine) ist dagegen "ein Exemplar sauber rekonstruieren, dann per Gitter instanziieren" der uebertragbare Kern.

### Gaps
- Keine offene, komplett lauffaehige LoD2->LoD3-Kette gefunden, die nur Fotos mit bekannten Kameras nutzt und echte Tiefe (Laibung, Vorsprung) rekonstruiert.
- "Windows in the wild"/Fassaden-Layout-Optimierung und konkrete 3D-Elementbibliotheken: in dieser Recherche keine belastbare Primaerquelle abgerufen.
- Lizenz von Scan2LoD3, Texture2LoD3, FacaDiffy, SVI2LoD3, FacAID nicht ermittelt. FME ist kommerzielle Software (Vorwissen, nicht abgerufen).
- CityEngine/CGA ist proprietaer (Vorwissen); offene CGA-artige Werkzeuge wurden nicht recherchiert.

## 5. Feines Relief/Ornament; druckbare wasserdichte Netze im Massstab 1:87

### Takeaway
Fuer Relief gibt es mit GS4Buildings (TUM, 2025) ein Verfahren, das genau die Projektlage trifft - 2D Gaussian Splatting mit LoD2-Netz als Prior und COLMAP-Posen -, aber unter nicht-kommerzieller Inria-Lizenz und als dichte Flaeche, nicht als CAD-Form. Es taugt als Gegenprobe/Reliefquelle fuer Ornament (Speier, Masswerkfuellungen), nicht als Formquelle im Sinn der Kernmethode.

### Cited Findings
- GS4Buildings (arXiv 2508.07355, ISPRS Annals 2025): LoD2-Modell als geometrischer Prior fuer 2D Gaussian Splatting; Initialisierung durch Punkte vom LoD2-Netz (kein SfM-Punktsatz noetig), Tiefen-/Normalenkarten aus dem LoD2 als Zusatzverluste; zwei Phasen (erst Prior stark, dann lokal verfeinern). — [arXiv 2508.07355](https://arxiv.org/abs/2508.07355)
- GS4Buildings-Repo: Lizenz "Gaussian-Splatting non-commercial research license" (von Inria/MPII geerbt) - NICHT-KOMMERZIELL; Eingaben: georeferenziertes LoD2-Netz als OBJ im Kamerarahmen + COLMAP-Posen (`sparse/0`, `images/`); gemeldet: Vollstaendigkeit +20,5 %, geometrische Genauigkeit +32,8 %, 71,8 % weniger Gaussians im Nur-Gebaeude-Modus; Netz ueber TSDF-Fusion + Marching Cubes (`render.py --mesh_res 1024`); 30 000 Iterationen im Beispiel; kein VRAM/keine Laufzeit genannt. — [zqlin0521/GS4Buildings](https://github.com/zqlin0521/GS4Buildings)
- SF-Recon (Wuhan, arXiv 2511.13278, ISPRS Annals 2026): leichte Gebaeude-Flaechennetze direkt aus Mehrbild-Fotos; 3DGS-Feld, normalen-gradienten-gefuehrte Optimierung und eine Mehrbild-Kantenkonsistenz-Ausduennung, die Dachlinien und Wandkanten kodiert. — [arXiv 2511.13278](https://arxiv.org/pdf/2511.13278v2), [ISPRS Annals XI-2-2026](https://isprs-annals.copernicus.org/articles/XI-2-2026/303/2026/isprs-annals-XI-2-2026-303-2026.pdf)
- LiP-Map/PlanarSplatting zeigen, dass lernbare Rechteck-Ebenen mit Tiefen-/Normalenpriors in Minuten optimierbar sind (333 s, 100 Ansichten, allerdings 48-GB-Karte). — [arXiv 2602.01296](https://arxiv.org/html/2602.01296v1)

### Inferences
- Massstabsrechnung: 0,3-0,8 mm Mindestdetail bei 1:87 entsprechen 26-70 mm am Original. Relief unter ca. 3 cm Tiefe/Breite ist im Druck ohnehin nicht darstellbar; es genuegt also eine Hoehenkarte je Wandflaeche mit etwa 1-2 cm Rasterweite. Feineres muss fuer den Druck ueberhoeht oder weggelassen werden - eine Entscheidung des Generators, nicht der Rekonstruktion.
- Der passendste Eigenbau ist ein Plane-Sweep in Fassadenkoordinaten: fuer jede Wandflaeche des Generators Orthofotos mehrerer Kameras bei Tiefen d im Band rechnen und je Rasterzelle die Tiefe mit bester Fotokonsistenz (Kanten- und Gradienten-Uebereinstimmung statt Farbe, wegen Sandstein-Textur und Beleuchtungswechsel) waehlen. Das ist die flaechige Verallgemeinerung des vorhandenen Kanten-Sweeps, laeuft kachelweise auf 8 GB und liefert direkt eine Hoehenkarte (2,5D), die sich als Displacement auf die Generatorflaeche setzen und mit manifold3d wasserdicht verschneiden laesst.
- Eine Hoehenkarte ueber einer wasserdichten Grundflaeche ist per Konstruktion wasserdicht (extrudiertes Hoehenfeld), anders als Marching-Cubes-Netze aus Splatting/SDF, die Loecher, Doppelwaende und Splitter erzeugen (vgl. vorhandene Pruefung `druck.splitter_verwerfen`). Fuer Hinterschnitte (Speier, freistehendes Masswerk) reicht 2,5D nicht; dort bleibt Kanten->Generator oder ein lokal begrenztes Flaechenverfahren.
- GS4Buildings ist als "Lage-Veto/Gegenprobe" regelkonform einsetzbar (es ersetzt die dichte Wolke, nicht die Fotokanten). Auf 8 GB sollte 2DGS im Nur-Gebaeude-Modus mit reduzierter Bildaufloesung laufen; das ist eine Annahme aus ueblichen 2DGS-Erfahrungen, keine dokumentierte Zahl.

### Gaps
- Keine Quelle zu photometrischem Stereo/Normalen-Mehrbildverfahren an Aussenfassaden bei unkontrolliertem Tageslicht gefunden; klassisches Photometric Stereo setzt kontrollierte Beleuchtung voraus (Vorwissen).
- Neuronale SDF-Verfahren mit Prior-Flaeche (NeuS-Familie, Neuralangelo) und Gaussian-Surfel-Verfahren (2DGS, PGSR, GOF): VRAM, Laufzeit und Lizenzen nicht abgerufen; UNGEPRUEFT. 2DGS/3DGS-Abkoemmlinge erben nach Vorwissen meist die nicht-kommerzielle Inria-Lizenz.
- Keine Literatur zu Mindestdetail-Regeln fuer H0-Druck im Zusammenhang mit Fassadenrekonstruktion gefunden; die 0,3-0,8 mm stammen aus der Aufgabenstellung.
- VRAM/Laufzeit von GS4Buildings und SF-Recon nicht dokumentiert.

## 6. Bewertung: Metriken fuer Linien-/Kantenrekonstruktion und LoD3-Fassaden gegen Fotos

### Takeaway
Die Literatur misst 3D-Linien fast nur gegen dichte Referenzgeometrie (Accuracy/Completeness, Precision/Recall/F bei Schwellen, Laengen-Recall, Stuetzbilder je Track); ein Mass gegen Fotos wie das projektinterne Foto-vs-Render-Kanten-F1 kommt dort nicht vor und ist fuer Fassaden ohne Ground Truth die sinnvollere Wahl - mit bekannten Fallen.

### Cited Findings
- LIMAP-artige Track-Metriken: R_tau = Laengen-Recall (Summe der Laengen der Linienanteile innerhalb tau mm der Referenz, in Metern), P_tau = Anteil der Tracks innerhalb tau, dazu mittlere Zahl stuetzender Bilder/2D-Linien je Track; Schwellen 1/5/10 mm (Hypersim) bzw. 5/10/50 mm (ScanNet). — [arXiv 2602.01296](https://arxiv.org/html/2602.01296v1), [LIMAP Paper](https://openaccess.thecvf.com/content/CVPR2023/papers/Liu_3D_Line_Mapping_Revisited_CVPR_2023_paper.pdf)
- Punktbasierte Metriken (EMAP/EdgeGaussians/CurveGaussian): Punkte entlang der Kanten abtasten; Accuracy = mittlerer Abstand Vorhersage->Referenz, Completeness = Referenz->Vorhersage; Precision/Recall/F bei 5/10/20 mm. — [arXiv 2506.21401](https://arxiv.org/pdf/2506.21401), [arXiv 2409.12886](https://arxiv.org/html/2409.12886v2)
- Es gibt keine Ground-Truth-3D-Linien in realen Datensaetzen; Referenz sind Ebenennetze, rueckprojizierte Tiefenkarten oder TSDF-Fusion; teils werden nur Tracks mit mindestens 4 Stuetzbildern gewertet. — [arXiv 2602.01296](https://arxiv.org/html/2602.01296v1), [ECCV 2024 Supplement 07710](https://ecva.net/papers/eccv_2024/papers_ECCV/papers/07710-supp.pdf)
- Die Rangfolge der Verfahren haengt an der Schwelle: LIMAP ist bei 5 mm auf ABC-NEF mit EdgeGaussians vergleichbar (F5 39,0 gegen 45,2), EMAP liegt bei 5 mm vorn (59,1), bei 10/20 mm fuehrt EdgeGaussians; die Autoren fuehren Unterschiede auf dicke 2D-Kantenkarten und einen Verfeinerungsschritt zurueck. — [arXiv 2409.12886](https://arxiv.org/html/2409.12886v2)
- LiP-Map rekonstruiert viel mehr Linien bei hoeherem Recall, aber kuerzere Tracks mit weniger Stuetzbildern als LIMAP/CLMAP - Recall und Track-Qualitaet koennen gegenlaeufig sein. — [arXiv 2602.01296](https://arxiv.org/html/2602.01296v1)
- Fassadenebene: ueblich sind mIoU und pixelbasierte Masse; SVI2LoD3 schlaegt "Facade Feature Distance" vor, einen Abstand im Merkmalsraum eines Vision Transformers, der laut Autoren semantische Richtigkeit und Layout erfasst. — [arXiv 2608.29992](https://arxiv.org/abs/2608.29992)

### Inferences
- Fallen des Foto-vs-Render-Kanten-F1, abgeleitet aus den obigen Befunden: (1) Toleranzbreite bestimmt das Ergebnis ebenso wie die mm-Schwellen oben - F1 immer bei mindestens zwei Toleranzen (z. B. 2 px und 6 px) melden; (2) dicke Fotokanten belohnen dicke/doppelte Renderkanten - beide Seiten vor dem Vergleich ausduennen (ein Pixel breit) und symmetrisch als Chamfer rechnen; (3) Fotokanten enthalten Textur, Fugen, Schatten, Verschmutzung, die das Modell nie haben soll - Precision des Renders (Modellkante hat Fotobeleg) ist das harte Tor, Recall gegen Fotokanten ist nur relativ zwischen Varianten vergleichbar; (4) Posefehler von 1-2 px wirken wie Formfehler - Bewertung ueber mehrere Fotos mitteln und das schlechteste Foto getrennt melden; (5) Verdeckung: Renderkanten nur dort werten, wo das Modell im Foto sichtbar und nicht von Fremdobjekten (Baeume, Leitungen) verdeckt ist.
- Zusaetzlich sinnvoll, analog zu "Stuetzbilder je Track": je 3D-Feature die Zahl der Fotos, in denen es eine stabile Kante trifft (Mehrbild-Beleg), als Abnahmekriterium; ein Feature mit Beleg in nur einem Foto ist nicht trianguliert.
- Ein lernbasiertes Aehnlichkeitsmass wie Facade Feature Distance ist als Abnahme-Tor ungeeignet (nicht geometrisch interpretierbar), hoechstens als grober Suchindikator "Teil fehlt ganz".

### Gaps
- Keine Veroeffentlichung gefunden, die ein Bildraum-Kanten-F1 oder Bildraum-Chamfer als Abnahmemass fuer LoD3-Fassaden validiert (z. B. Korrelation mit Laser-Ground-Truth).
- Formeln der M1-Metriken von LiP-Map (Anhang) und laengengewichtete gegen ungewichtete Wertung nicht gelesen.
- Kein oeffentlicher Benchmark mit Referenz-Linien fuer historische Fassaden gefunden.

## 7. Analyse-durch-Synthese / differenzierbares Rendern zum Anpassen prozeduraler Parameter an Fotokanten

### Takeaway
Belegt ist das Prinzip (Parameter eines prozeduralen Generators per Silhouettenverlust durch einen differenzierbaren Renderer anpassen, Mitsuba 3; mit genetischem Algorithmus als Ausweg bei nicht differenzierbaren Generatoren) - aber nur fuer Einzelobjekte und Silhouetten. Eine veroeffentlichte Kette "nvdiffrast + Kantenverlust + Fassadengenerator" wurde nicht gefunden; fuer das Projekt ist ableitungsfreie Optimierung gegen ein Kanten-Distanzfeld der realistischere Einstieg.

### Cited Findings
- "Single-view 3D reconstruction via inverse procedural modeling" (arXiv 2310.13373): schaetzt Eingaben eines prozeduralen Generators ueber einen Silhouettenverlust zwischen Referenz und Rendering; Implementierung mit Mitsuba 3; verlangt einen differenzierbaren Generator (Jacobi-Matrix Vertex-Positionen nach Parametern); fuer nicht differenzierbare Generatoren beschreiben die Autoren einen genetischen Algorithmus. — [arXiv 2310.13373](https://arxiv.org/html/2310.13373v1), [Eurographics Digital Library](https://diglib.eg.org/handle/10.2312/cgvc20231189)
- Nishida et al. 2018 kombinieren CNN-Auswahl der Grammatik mit anschliessender Parameteroptimierung - Vorlaeufer ohne Gradienten durch den Renderer. — [Nishida et al. 2018](https://www.cs.purdue.edu/cgvlab/www/resources/papers/Nishida-EUROGRAPHICS-2018-Procedured_Modeling_of_a_Building.pdf)
- SketchSplat und CurveGaussian zeigen, dass parametrische 3D-Kanten/Kurven direkt per differenzierbarem Rastern gegen 2D-Kantenkarten optimiert werden koennen, einschliesslich Topologie-Operationen (Verschmelzen, Teilen, Ausduennen). — [arXiv 2503.14786](https://arxiv.org/pdf/2503.14786), [arXiv 2506.21401](https://arxiv.org/abs/2506.21401)
- nvdiffrast wird in der Literatur als verbreiteter differenzierbarer Rasterisierer gefuehrt und fuer Gradientenabstieg auf prozeduralen (Material-)Parametern eingesetzt. — [TexPro arXiv 2410.15891](https://arxiv.org/pdf/2410.15891)
- Die LIMAP-BA drueckt Gruppenbedingungen (parallel, koplanar) als 2D-Reprojektionsfehler aus und bleibt dabei so schnell wie Punkt-BA - ein Hinweis, dass Kanten-Reprojektionsfehler mit klassischer nichtlinearer Ausgleichung (ohne Renderer) effizient loesbar sind. — [arXiv 2609.04026](https://arxiv.org/abs/2609.04026)

### Inferences
- manifold3d-Boolesche Operationen sind nicht differenzierbar und aendern die Topologie sprunghaft; ein Gradient "Pixel -> Generatorparameter" existiert daher nicht ohne Neubau des Generators. Praktikabel sind drei Stufen: (A) ableitungsfrei: je Bauteil wenige Parameter (Lage, Breite, Tiefe, Anzahl, Profilmasse) mit CMA-ES/Koordinatensuche optimieren; Kostenfunktion = Chamfer der projizierten Modellkanten gegen das Distanzfeld der Foto-Stabilitaetskanten ueber mehrere Fotos. Dafuer reicht Projektion der Generator-Kantenlinien (kein Rendern), Verdeckung per einmaligem Tiefenpuffer; Tausende Auswertungen je Minute auf der GPU sind realistisch, VRAM unkritisch. (B) halb-differenzierbar: die Feature-Kanten als 3D-Polylinien/Splines mit festen Parameter-Abhaengigkeiten (z. B. Rippenschar = Start + i*Abstand) in PyTorch formulieren und direkt per Autograd gegen die Distanzfelder optimieren - das ist die Gruppen-BA-Idee mit eigenen Nebenbedingungen. (C) volles differenzierbares Rendern nur fuer Silhouetten/Verdeckungskanten grosser Koerper (Erker, Dachkanten), wo Kanten vom Blickwinkel abhaengen.
- Stufe A/B loest gezielt zwei der Projektprobleme: Rippen-Mehrdeutigkeit (die Schar wird als Ganzes mit Zaehlung und konstantem Abstand angepasst; eine um eine Periode versetzte Loesung faellt am Scharrand auf) und Fragmentierung (Parameter werden auch von lueckenhaften Kanten bestimmt).
- Die Ganzzahl-Parameter (Anzahl) nicht optimieren, sondern aus der Foto-Zaehlung vorgeben; sonst findet der Optimierer Periodenvielfache.
- 8 GB: nvdiffrast-Rasterung eines Bauteils bei 2-4 MP ist erfahrungsgemaess im Bereich weniger hundert MB bis ca. 2 GB; Mitsuba 3 (physikalisch basiert) ist fuer reine Kanten/Silhouetten unnoetig schwer. Das sind Erfahrungswerte ohne Quelle.

### Gaps
- Keine Veroeffentlichung gefunden, die prozedurale Fassaden-/Gebaeudeparameter per differenzierbarem Rasterisierer mit Kantenverlust an Mehrbild-Fotos anpasst.
- Lizenzen UNGEPRUEFT: nvdiffrast (nach Vorwissen NVIDIA-Quellcode-Lizenz mit Nicht-Kommerz-Einschraenkung; moegliche spaetere Aenderung nicht geprueft), PyTorch3D (nach Vorwissen BSD), Mitsuba 3 (nach Vorwissen BSD-3), DiffVG (nach Vorwissen Apache-2.0).
- Keine belastbaren VRAM-/Laufzeitzahlen fuer diese Renderer bei Fassadenaufloesung gefunden.

## 8. Empfehlungen: was zuerst probieren (Nutzen, Aufwand, VRAM, Lizenz)

### Takeaway
Reihenfolge nach Nutzen je Aufwand: (1) LIMAP 2.0 auf den vorhandenen COLMAP-Modellen als zweite, bandfreie 3D-Kantenquelle; (2) Orthofoto-Stapel je Wandflaeche als gemeinsame Grundlage fuer Zaehlen, Segmentieren und Relief-Sweep; (3) DeepLSD-Distanz-/Winkelfeld im eigenen Sweep; (4) ableitungsfreie Parameteranpassung der Generator-Features gegen Kanten-Distanzfelder; erst danach neuronale Kurvenverfahren oder Splatting.

### Cited Findings
- LIMAP: BSD-3, COLMAP-kompatibel (4.2.0), pip-installierbar, Detektor-/Matcher-Auswahl, Gruppen-BA 2026. — [cvg/limap](https://github.com/cvg/limap), [arXiv 2609.04026](https://arxiv.org/abs/2609.04026)
- DeepLSD: MIT inkl. Gewichte, Distanz-/Winkelfeld, Fluchtpunkte. — [cvg/DeepLSD](https://github.com/cvg/DeepLSD)
- ScaleLSD: MIT, CLI mit JSON-Ausgabe. — [ant-research/scalelsd](https://github.com/ant-research/scalelsd)
- GlueStick: Gesamtsystem nicht-kommerziell wegen SuperPoint. — [cvg/GlueStick](https://github.com/cvg/GlueStick)
- IncreLM: BSD-3, LIMAP-basiert, COLMAP-Eingabe. — [3dv-casia/IncreLM](https://github.com/3dv-casia/IncreLM)
- Entzerrung auf LoD2-Ebenen verbessert Segmentierung um 11 %. — [arXiv 2504.05249](https://arxiv.org/html/2504.05249v1)
- EdgeGaussians: 5 min Training, aber keine Lizenz, COLMAP-Parser kaum getestet. — [kunalchelani/EdgeGaussians](https://github.com/kunalchelani/EdgeGaussians), [arXiv 2409.12886](https://arxiv.org/html/2409.12886v2)
- EMAP: ueberwiegend MIT, kein Custom-Data-Pfad, 2,5-12 h je Szene. — [cvg/EMAP](https://github.com/cvg/EMAP), [arXiv 2409.12886](https://arxiv.org/html/2409.12886v2)
- GS4Buildings: LoD2-Prior + COLMAP, nicht-kommerzielle Lizenz. — [zqlin0521/GS4Buildings](https://github.com/zqlin0521/GS4Buildings)
- SAM 3: Konzept-/Beispiel-Prompt, eigene SAM-Lizenz. — [facebookresearch/sam3](https://github.com/facebookresearch/sam3)

### Inferences
Alle Punkte dieses Abschnitts sind Empfehlungen (abgeleitet), Aufwands- und VRAM-Angaben sind Schaetzungen.

1. LIMAP 2.0 als zweite Kantenquelle (zuerst).
   - Was: vorhandenes COLMAP-Modell eines Objekts (z. B. Kaufhaus) hineingeben, Detektor DeepLSD (und zum Vergleich LSD), Linien triangulieren, Ergebnis ins Objekt-Koordinatensystem uebernehmen und gegen die Sweep-Kanten legen.
   - Erwarteter Nutzen: lange gerade Kanten (Gesimse, Dachkanten, Erkerkanten, Pfeiler) als zusammenhaengende Segmente mit Track; Features ausserhalb des Bandes werden gefunden; die Tracks liefern den Mehrbild-Beleg je Feature. Geringer Nutzen bei Masswerk/Boegen und bei dichten Rippenscharen (Matcher-Verwechslung).
   - Aufwand: 0,5-1 Tag bis zum ersten Bild. VRAM: Detektor/Matcher je Bild, voraussichtlich deutlich unter 8 GB bei verkleinerten Bildern; Triangulation/BA auf CPU. Lizenz: BSD-3 (LIMAP), MIT (DeepLSD). Matcher: GlueStick nur nicht-kommerziell; fuer freie Kette anderen Matcher waehlen und dessen Lizenz pruefen.
   - Tor: nur 3D-Segmente uebernehmen, die im Foto-F1 des Bauteils die Precision nicht senken; Wolke nur Lage-Veto.
   - Danach optional: Gruppen-BA (Parallelitaet/Koplanaritaet) und IncreLM als Variante fuer mehr Vollstaendigkeit.

2. Orthofoto-Stapel je Wandflaeche (Grundlage fuer drei Probleme).
   - Was: je Generator-Wandflaeche alle sichtbaren Fotos auf die Flaeche entzerren (einheitliches Raster in Metern).
   - Nutzen: (a) Zaehlen wiederholter Elemente per Autokorrelation der Kantenkarte plus unabhaengige Gegenzaehlung per Beispiel-Prompt (SAM 3 oder aehnlich); (b) Elementmasken zum automatischen Gruppieren der 3D-Kanten; (c) Eingabe fuer den flaechigen Plane-Sweep (Relief, Laibungstiefe).
   - Aufwand: 1-2 Tage; VRAM gering (Kacheln). Lizenz: Eigenbau; SAM 3 eigene Lizenz pruefen, SAM 2 als Ausweich.

3. Sweep staerken statt ersetzen.
   - Richtungs-Konsistenz: Treffer in Nachbarfotos nur zaehlen, wenn die Kantenrichtung zur projizierten 3D-Richtung passt (DeepLSD-Winkelfeld oder eigener Gradient).
   - Segmentweise statt pixelweise abstimmen: eine 2D-Kante (oder Rippenschar) bekommt eine gemeinsame Tiefe bzw. Tiefenebene; Reihenfolge-Nebenbedingung zwischen Nachbarrippen.
   - Band adaptiv: zweiter Durchlauf mit Band um die in Durchlauf 1 und von LIMAP gefundenen 3D-Kanten statt um die Grobflaeche; Belegdichte am Bandrand als Warnsignal.
   - Konfliktkarte je Wand (Beleg vor/auf/hinter der Flaeche) als automatischer Fehlteile-Hinweis.
   - Aufwand: je 1-2 Tage; VRAM wie bisher.

4. Parameteranpassung gegen Kanten-Distanzfelder (Analyse durch Synthese, ableitungsfrei).
   - Was: je Bauteil die Generatorparameter mit CMA-ES/Koordinatensuche so einstellen, dass projizierte Modellkanten das Mehrfoto-Kanten-Distanzfeld minimieren; Anzahlen fest aus der Foto-Zaehlung.
   - Nutzen: schliesst die Luecke "fragmentierte Kanten -> saubere parametrische Form" und liefert Masse direkt mit Restfehler in Pixeln/Zentimetern; dieselbe Kostenfunktion ist das Abnahme-F1 in weicher Form.
   - Aufwand: 2-4 Tage fuer ein Bauteil als Muster; VRAM gering. Lizenz: Eigenbau.

5. Erst danach, als Experimente.
   - EdgeGaussians mit eigenen Stabilitaetskarten fuer ein kleines Kurvenbauteil (Masswerkfenster, Arkadenbogen): 5-Minuten-Training laut Paper, aber fehlende Lizenz und ungetesteter COLMAP-Pfad; nur zur Einschaetzung, ob Gaussian-Kanten bei Boegen mehr bringen als der Sweep.
   - GS4Buildings als Relief-Gegenprobe fuer Ornament/Speier (nicht-kommerziell; Ergebnis nur Lage-/Hoehen-Veto).
   - Nicht empfohlen als erster Schritt: EMAP (Stunden je Szene, kein Custom-Data-Pfad), NEF (laut EMAP-Autoren systematisch verzerrt, im Vergleich am schwaechsten), Scan2LoD3-Kette (Laser + FME noetig), LiP-Map (48-GB-Beleg, Lizenz offen, Innenraum).

### Gaps
- Alle Aufwands-, VRAM- und Nutzenschaetzungen in diesem Abschnitt sind unbelegt und muessen am ersten Objekt gemessen werden (Foto-F1 vorher/nachher je Bauteil).
- Ob LIMAP 2.0.0 direkt mit der im Projekt installierten COLMAP-/pycolmap-Version und dem Format der vorhandenen SfM-Modelle zusammenpasst, wurde nicht getestet.
- Vor jedem neuen Versuch laut Projektregel `modelle/NICHTS_GEBRACHT.md`, `modelle/VERSUCHSREGISTER_MARTINSTOR.md` und `modelle/LIZENZ_WERKZEUGE.md` gegenpruefen; diese Dateien wurden fuer diese Recherche nicht gelesen, Ueberschneidungen mit bereits verworfenen Versuchen sind moeglich.
