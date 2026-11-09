# Recherche Kantengitter NEU (Verfahren 2023-2026) - 2026-11-09

Stand: Websuche + Repo-Seiten 9.11.2026 abends, nichts installiert, kein Code geaendert.
Lizenz-Legende: **belegt** = LICENSE-Datei bzw. GitHub-API-Feld `license` gelesen; **unbelegt** = nur Paper/Sekundaerquelle. "license: null" in der GitHub-API = keine Lizenzdatei = alle Rechte vorbehalten = nur Test.
Nicht wiederholt (siehe RECHERCHE_DRAHTGITTER_2026-11-09.md, RECHERCHE_DRAHTGITTER_VERFAHREN_2026-11-09.md): LIMAP, Line3D++, ELSR, GlueStick, DeepLSD, Manhattan/VP-Zwang, IRLS, Hough-Mode, RJMCMC, PC2WF, PBWR, Point2CAD, HBIM-Praxis.

## 0. Einordnung unseres eigenen Standes
Unsere Kette (Stabilitaetskarte -> Tiefen-Sweep je Kantenpixel -> RANSAC-Segmente + SVD) ist genau das, was die Literatur 2023-2025 "zweistufig" nennt (NEF, EMAP, EdgeGaussians: erst 3D-Kantenpunkte, dann Primitive anpassen). Alle drei neuesten Arbeiten (SketchSplat ICCV 2025, CurveGaussian ICCV 2025, SGCR CVPR 2025) begruenden sich mit demselben Mangel, den wir sehen: **Luecken und Fragmente zwischen den angepassten Primitiven**, Buendel statt einer Linie. Ihre Antwort: Primitive (Linie, kubische Bezier) direkt gegen die 2D-Kantenkarten optimieren und dabei Topologie-Operationen (Endpunkte verschmelzen, Kollineare vereinen, Unsichtbare loeschen) ausfuehren. Das ist der eine Baustein, der uns fehlt; der zweite ist eine Kettenbildung der 3D-Kantenpunkte (3D Curvix), der dritte ein Wiederholungs-Prior fuer Fenster/Zacken (kein fertiger Code 2023+).

Eingabe passt ueberall: Alle neuronalen Verfahren nehmen **Graustufen-Kantenkarten in [0,1] + Posen** (DexiNed/PiDiNet). Unsere Stabilitaetskarte ist ein direkter Ersatz. Befund aus SketchSplat: gelernte Detektoren (PiDiNet/DexiNed) verschieben Kanten leicht von der Objektgrenze weg und sind dadurch mehrbild-inkonsistent; Kanten aus Tiefe/Normalen (2DGS-SN, DepthPro-SN) waren bei ihnen genauer (F5 91,3 vs 87,8). Unsere Stabilitaetskarte ist ein Detektor-Ensemble auf Bildgradienten, hat also dieselbe Verschiebungsgefahr; eine Verschneidung mit Tiefen-/Normalen-Spruengen aus der dichten Wolke waere ein billiger Zusatz (Risiko: Wolke im Dach duenn).

Zwei Lizenzbefunde fuer die Kantenkarten-Lieferanten: DexiNed MIT (belegt, API), PiDiNet MIT mit vorangestelltem Satz "It is just for research purpose, and commercial use should be contacted with authors first" (belegt, LICENSE) -> vor Verkauf anfragen oder nicht nutzen.

## 1. Priorisierte Liste (max. 8)

### 1. SketchSplat (ICCV 2025, Ying/Zwicker, Univ. Maryland)
- Kernidee: 3D-Skizzen (Linien + kubische Bezier mit Kontrollpunkten, Opazitaet, Breite) werden differenzierbar in alle Fotos gesplattet und gegen die 2D-Kantenbilder optimiert; waehrend der Optimierung laufen Topologie-Operationen (Endpunkte < Schwelle verschmelzen, ueberlappende Skizzen zusammenlegen, Kollineare vereinen, in den meisten Ansichten unsichtbare Skizzen loeschen).
- Eingabe: kalibrierte Fotos + Kantenkarten + **Initialisierung aus EdgeGS (= EdgeGaussians) oder EMAP**; Ausgabe `parametric_edges.json` (Bezier, optional fast gerade -> Linie).
- Lizenz: **MIT (belegt, LICENSE "Copyright (c) 2025 Ocean")**. Rasterizer-Abhaengigkeit nicht im README genannt (`install.sh`) -> VOR Nutzung pruefen, ob INRIA `diff-gaussian-rasterization` (NC) oder gsplat (Apache-2.0).
- Installation: kein pip, `install.sh` + conda; keine Anleitung fuer eigene Daten (nur ABC-NEF/Replica/DTU-Ordnerlayout).
- Laufzeit/VRAM: ~10 min je ABC-Szene (5 min EdgeGS-Init + 5 min Skizzen) auf einer RTX A5000; VRAM nicht berichtet; Szenen auf 1 m^3 normiert, 50 Ansichten. 440 Fotos/Fassade sind nicht erprobt.
- Nutzen fuer uns: genau der fehlende "Vervollstaendigungs-Schritt": unsere RANSAC-Segmente + Bogenkandidaten als Initialskizzen, Optimierung gegen Stabilitaetskarten, Topologie-Operationen schliessen Luecken (Dachfirst-Fragmente, Zacken-Kanten) und loeschen Streuer (unsichtbar in den meisten Fotos; Sichtbarkeit haben wir aus der Wolke). Boegen werden als Bezier direkt angepasst.
- Risiko: Autor warnt, dass unsichtbare Kanten positive Supervision bekommen (verdeckte Kanten wandern); duenne Strukturen unter Verschmelzungsschwelle (10 mm bei 1 m^3-Szene) verschmelzen faelschlich; Ergebnis haengt von der Initialisierung ab. Adapter fuer unser Datenformat noetig (1 Tag). Bei NC-Rasterizer: eigenen Linien-Splatter in torch schreiben (Punkte entlang Primitiv projizieren, Gauss-Splat gegen Kantenkarte/Distanztransformation) - das ist klein.
- Quellen: https://github.com/OceanYing/SketchSplat ; https://arxiv.org/html/2503.14786v2

### 2. 3D Curvix (BMVC 2025) + 3D Edge Sketch (WACV 2025), Brown/Kimia - Kettenbildung statt RANSAC
- Kernidee (Curvix): Unorganisierte 3D-Kantenpunkte mit Tangenten -> Nachbarschaftsgraph (Ort + Tangentenkonsistenz) -> 1D-Mannigfaltigkeit -> geordnete Kurvenzuege (`final_curves.txt` = Folge von 3D-Kanten). Edge Sketch liefert davor die 3D-Kantenpunkte per Hypothesen-Ansichtspaar + Bestaetigung in weiteren Ansichten (Third-Order-Edge-Detector, Subpixel).
- Eingabe: Curvix braucht nur 3D-Kantenpunkte + Tangenten (= Ausgabe unseres Tiefen-Sweeps, wenn wir je Punkt die 2D-Kantenrichtung mitfuehren). Edge Sketch braucht Posen als R/T-Textdateien + Kanten (MATLAB-Vorverarbeitung).
- Lizenz: **beide `license: null` (belegt, API)** -> nur Test; Edge Sketch zuletzt gepusht 2026-01-28 (6 Sterne), Curvix "GPU-Version in Arbeit", CPU/OpenMP, Eigen 3.3.2 (neuere inkompatibel), C++17, Evaluation Python 3.8.
- pip/conda: nein (CMake).
- Nutzen: Unser Kernproblem "Buendel paralleler Streuer / Fragmente" ist in der Kettenbildung besser aufgehoben als in RANSAC-Segmenten: die 1D-Mannigfaltigkeit verbindet Fragmente derselben Kante und verwirft Punkte ohne Tangenten-konsistente Nachbarn. Zacken (Staffelgiebel) und Helmkanten sind Polylinien - genau die Ausgabeform. Danach stueckweise Linie/Kreisbogen/Bezier mit Modellwahl (EdgeGaussians: Kurve nur, wenn Fehler <= 0,5 x Linienfehler).
- Risiko: Lizenz; Code "a bit messy" (Vorrecherche). Empfehlung: Verfahren NACHBAUEN (kNN auf GPU via `tools/gpu_knn.py`, Tangenten aus 2D-Kantenrichtung + Strahl, Graph-Traversal) - 1 Tag, lizenzfrei, GPU von Anfang an (Nutzerregel).
- Quellen: https://github.com/C-H-Chien/3D_Curvix ; https://github.com/C-H-Chien/3D_Edge_Sketch ; https://openaccess.thecvf.com/content/WACV2025/html/Zheng_3D_Edge_Sketch_from_Multiview_Images_WACV_2025_paper.html

### 3. EdgeGaussians (WACV 2025, Chelani/Benbihi/Sattler/Kahl) - als Vollstaendigkeits-Orakel und Bauanleitung
- Kernidee: Jeder 3D-Kantenpunkt ist ein 3D-Gaussian; Zentrum = Ort, Hauptachse = Kantenrichtung. Training per gsplat gegen Kantenkarten (L1 nur auf Kantenpixeln + gleich viele Zufalls-Hintergrundpixel), Orientierungs-Loss zu k=4 Nachbarn, Form-Loss (laenglich); danach Graph-Clustering (Ort + Richtung, Schwelle 0,8 Objekt / 0,6 DTU) und je Cluster Linie oder kubische Bezier.
- Eingabe: Kantenkarten (DexiNed/PiDiNet) + Posen; **COLMAP-Parser vorhanden ("not tested widely"), Kantenbildpfad + Skalierung in Config**; Ausgabe PLY (Gaussians mit Hauptrichtung) + Punkte auf angepassten Kurven (5 mm).
- Lizenz: **`license: null` (belegt, API, Stand Push 2025-03-11)** -> nur Test. Abhaengigkeiten: **gsplat 1.0.0 (Apache-2.0, belegt)**, torch 1.13.1+cu116, Python 3.9 (requirements.txt gelesen) - also kein INRIA-Rasterizer.
- Laufzeit/VRAM: **~5 min je Szene, 500 Epochen** (Paper, GPU nicht genannt); 17-30x schneller als NEF, 30-100x als EMAP. VRAM nicht berichtet; bei 440 Fotos: Bilder muessen heruntergerechnet und auf ~80-120 Fotos (foto_wichtigkeit.py) begrenzt werden, Gaussians nur auf Kantenpixeln -> 8 GB plausibel (VERMUTUNG).
- Qualitaet: DTU Recall 87,7 vs EMAP 77,5 vs LIMAP 74,9 (5 mm) - **vollstaendiger als EMAP/LIMAP**, aber weniger genau; Replica/Tanks&Temples qualitativ.
- Nutzen: (a) schnelles Orakel: "Welche Kanten findet ein neutrales Verfahren aus denselben Kantenkarten?" -> Luecken unseres Gitters sichtbar machen (nur Vergleich, kein Mitteln, Regel 5); (b) Bauanleitung fuer eine lizenzfreie Eigenversion auf gsplat (Apache) in 2-3 Tagen, falls SketchSplat scheitert.
- Risiko: Lizenz null; Autoren nennen heuristisches Clustering und Artefakte in komplexen Szenen; ADC-Parameter von 3DGS muessen getunt werden; dicke/verrauschte Kantenkarten = Bias (unsere Stabilitaetskarte ist eher duenn, gut).
- Quellen: https://github.com/kunalchelani/EdgeGaussians ; https://arxiv.org/html/2409.12886v2

### 4. Wiederholungs-/Symmetrie-Prior fuer Fenster und Zacken (Eigenbau; kein Code 2023+ gefunden)
- Stand der Technik: Ceylan et al. "Factored Facade Acquisition using Symmetric Line Arrangements" (Eurographics 2012): symmetrische Linien-Anordnungen werden gekoppelt mit der 3D-Linienrekonstruktion gesucht, Symmetrie als nicht-lokaler Prior; Xiao et al. (Fiducial-Linien im entzerrten Fassadenbild, Wiederholung horizontal/vertikal ausgerichtet); Translational-Symmetry-Aware Facade Parsing (2021, Symmetrierichtung schaetzen, Parsing verfeinern); LiDAR-Kachelabgleich (PERS 2019: Fassade in Kacheln, aehnliche Kacheln verschmelzen, fehlende Punkte ergaenzen). Code: keiner gefunden (Ceylan-PDF nicht ladbar, SSL-Fehler) -> **unbelegt**.
- Vorschlag (eigen, lizenzfrei): auf der Front-Ortho (SAM-Masken liegen schon vor, Memory 9.11.) Translationsperiode per Autokorrelation der Kantenkarte/Masken bestimmen (Fensterreihe: Periode dx; Zacken: 1D-Autokorrelation des Kantenprofils entlang der Giebelschraege). Das am besten belegte Element (hoechste Fotodeckung) wird als 3D-Drahtgitter an alle Perioden-Positionen kopiert; jede Kopie wird in den kalibrierten Fotos verifiziert (foto_diff-Logik), Anzahl NUR am Foto (Regel 9, Z-Protokoll). Nicht bestaetigte Kopien bleiben als `beobachtungen_offen`.
- Nutzen: fuellt Luecken dort, wo Fotos verdeckt/verwackelt sind, ohne Erfindung, weil jede Kopie einzeln gegen Fotos geprueft wird; passt zu Regel 9b (Anordnung pro Flaeche mit Foto vergleichen).
- Risiko: Fassaden historischer Gebaeude sind nicht streng periodisch (Achsabstaende variieren um Dezimeter) -> Kopie als Startwert, dann lokaler Fit (Sweep aus `teil_sweep_gpu.py`), nie starr. Aufwand 1 Tag.
- Quellen: http://vecg.cs.ucl.ac.uk/Projects/SmartGeometry/factored_facade/paper_docs/factored_facade_eg12_small.pdf (nicht gelesen) ; https://www.researchgate.net/publication/319381325 ; https://www.ingentaconnect.com/content/asprs/pers/2019/00000085/00000002/art00011

### 5. S23DR-Challenge (CVPR 2024/2025/2026, HoHo-Datensatz): Drahtgitter aus COLMAP-Sparse + Tiefe + Segmentierung
- Kernidee: Aufgabe = 3D-Drahtgitter (Knoten + Kanten mit Klassen First/Traufe/Grat/Kehle/Ortgang...) eines Hauses aus **COLMAP-Sparse-Wolke (~40k Punkte) + Posen + metrischen Tiefenkarten + Segmentierungen**, ohne RGB. Sieger 2025 (Skvrna/Neumann, CTU Prag): Knotenkandidaten durch Clustern Gestalt-gelabelter Wolkenpunkte, PointNet-artiger Klassifikator auf Wuerfel-Patches je Knoten, zweiter PointNet-Klassifikator auf **Zylinder-Patches zwischen Knotenpaaren = Kante ja/nein**. Sieger 2026 (gleiche Gruppe): Flow-Matching-DiT, 64 Knoten-Token als bedingte Menge, zweistufig (global, dann Huelle-Ausschnitt), Multi-Sample-Konsens; HSS 0,654 (Baseline gelernt 0,474, handgemacht 0,391), Vertex-F1 0,791.
- Lizenz: 2026-Loesung **Code Apache-2.0, Gewichte CC-BY-NC-4.0 (belegt, HF-Karte)**; 2025-Loesung HF-Repo `jskvrna/hoho` Apache-2.0 (Metadaten, belegt); Datensatz HoHo25k gated mit eigener Lizenzvereinbarung (Text nicht gelesen) -> Gewichte/Daten nicht fuer Verkauf.
- Laufzeit: 2025: Training wenige Stunden auf 1x A100, Inferenz < 10 ms je Patch auf T500 (~50 Kandidaten je Haus) -> fuer uns trivial.
- Nutzen: Nicht die Gewichte (Domaene: US-Wohnhaeuser, 6-36 Knoten, 4-22 Ansichten, roof-spezifische Gestalt-Klassen), sondern das **Rezept fuer Gitter-Vervollstaendigung**: Knotenkandidaten aus unseren Kantenpunkt-Clustern/Kettenenden, Kantenklassifikator auf Zylinder-Patch der Wolke+Kantenpunkte zwischen zwei Knoten. Trainingsdaten koennen wir **selbst aus unserem parametrischen Generator erzeugen** (Drahtgitter bekannt, Wolke per Render/Sampling + Rauschen, Kantenpunkte per synthetischem Sweep) - Beweistest synthetisch ist ohnehin Pflicht.
- Risiko: Domaenenluecke historische Fassade (Boegen, Zacken) -> nur mit eigenen Synthetikdaten; Aufwand 1-2 Wochen, daher nicht in den naechsten 3 Tagen.
- Quellen: https://arxiv.org/html/2506.16421v1 ; https://huggingface.co/jskvrna/2026_s23dr ; https://s23dr.github.io/2026/writeups/2026-1st-place.pdf ; https://huggingface.co/datasets/usm3d/hoho25k

### 6. CurveGaussian / Curve-Aware Gaussian Splatting (ICCV 2025, Gao et al., NUDT) - einstufig Bezier aus Kantenkarten
- Kernidee: Bezier-Kurven (kubisch + linear) sind die Parameter; an jede Kurve sind kantenorientierte Gaussians gekoppelt (Kurve steuert deren Lage), gerendert gegen Kantenkarten; Topologie wird waehrend des Trainings angepasst (Teilen/Verschmelzen/Loeschen). Initialisierung bei COLMAP-Daten aus den SfM-Punkten.
- Ausgabe: sehr kompakt: ~70 Kurven je Realobjekt statt 1952 bei EdgeGaussians; ABC: 6,9 Bezier + 22 Linien je Szene. Laufzeit ~3 min (10k Iterationen), GPU/VRAM nicht berichtet; Realdaten 480x480 Objekte, Kanten dort nicht aus PiDiNet/DexiNed (Lichtartefakte), sondern aus StableNormal-Hochkruemmung + SAM2-Maske.
- Lizenz/Code: Paper nennt https://github.com/zhirui-gao/Curve-Gaussian -> **404 am 9.11.2026**, GitHub-Suche 0 Treffer, Projektseite nicht ladbar -> **Code nicht verfuegbar, Lizenz unbelegt**.
- Nutzen: Konzept fuer Boegen/Helme: Bogen als Parameterobjekt mit angehaengten Gaussians statt Punktwolke->Kreisfit (BS13 scheiterte). Idee in Punkt 1 (SketchSplat) weitgehend enthalten.
- Risiko: kein Code; Nachbau nur, wenn SketchSplat-Weg scheitert.
- Quellen: https://arxiv.org/html/2506.21401v3

### 7. CGGT - Curve-Grounded Geometry Transformer (arXiv 2609.14521, Sept. 2026, Gao et al.) - Feed-forward
- Kernidee: VGGT-Rueckgrat; aus 2-12 unposierten Bildern in einem Durchlauf Posen, Tiefe und **2D-Kurven-Instanzmasken mit Querbild-Zuordnung**; Lift nach 3D, RANSAC-Init Linie/Ellipse/Bezier, 300 Adam-Iterationen; ~10 s je Objekt. Trainiert NUR synthetisch (Wireframe-100K aus ABC-CAD), 4x A100; Realtest nur Maschinenteile (MV2Cyl).
- Code: **nicht gefunden** (nur Projektseite genannt); Lizenz unbelegt.
- Nutzen: heute keiner (Domaene CAD, wenige Ansichten, > 50 Kurven degradiert, Verdeckung/Symmetrie ausdruecklich offen). Beobachten: die Kurven-Instanzsegmentierung ueber Ansichten hinweg ist die Idee, die unseren Tiefen-Sweep von "Pixel" auf "Kurveninstanz" heben wuerde.
- Risiko: 8 GB VRAM fuer VGGT-Inferenz knapp (VGGT-1B ist zudem NC, Memory LIZENZ).
- Quellen: https://arxiv.org/html/2609.14521v1

### 8. LineGS (Dez. 2024, NUS) - Segmente mit 3DGS-Dichte beschneiden/verschieben
- Kernidee: Vorhandene 3D-Segmente (Line3D++/ELSR) werden als Zylinderachse betrachtet; Gaussians eines trainierten 3DGS-Modells im Zylinder verschieben die Linie, ueberlange Segmente werden per Binaersuche gekuerzt.
- Lizenz: **"Gaussian-Splatting License" Inria/MPII, nur nicht-kommerziell (belegt, LICENSE.md)** -> nur Test. Braucht vollstaendiges 3DGS-Training (440 Fotos: VRAM/Zeit hoch).
- Nutzen: Idee uebertragbar auf unsere dichte Wolke statt 3DGS: Segment-Enden dort abschneiden, wo die Wolkendichte im Zylinder abbricht (gegen "ueberstehende" Firstlinien). Kleiner Eigenbau (0,5 Tag), GPU-kNN vorhanden.
- Quellen: https://github.com/ericshenggle/LineGS ; https://arxiv.org/html/2412.00477v3

## 2. Geprueft, aber nicht auf die Liste
- **EMAP (CVPR 2024, MIT)**: Checkliste heute gelesen: `[ ] Custom Dataset Support` weiterhin offen; Laufzeit 2,5 h (ABC) bis 12 h (DTU) je Szene; EdgeGaussians ist vollstaendiger und 30-100x schneller. Nur noch als Init-Alternative fuer SketchSplat. https://github.com/cvg/EMAP
- **NEF (CVPR 2023)**: Code existiert doch: https://github.com/yunfan1202/NEF_code (Korrektur zur Vorrecherche), **`license: null`**, 3080Ti/CUDA 11.4/PyTorch 1.12/Lightning 1.5, nur ABC-NEF-Blender-Format, 1,5 h je Szene -> veraltet gegen 1/3.
- **SGCR (CVPR 2025, Spherical Gaussians -> rationale Bezier)**: kein Code gefunden, nur qualitative Effizienzangaben -> unbelegt, abwarten.
- **BrepGaussian (arXiv 2602.21105, Feb. 2026)**: Gaussians mit Kanten-/Patch-Labels -> B-Rep aus Mehrbild; Code/Datensatz/Lizenz nicht genannt, CAD-Domaene -> beobachten (B-Rep = direkt druckbare Koerper, langfristig interessant).
- **BWFormer (CVPR 2025, `license: null`) und LoD2-Former (ISPRS 2026, DLR, LiDAR+Luftbild)**: Dach-Drahtgitter aus Luft-LiDAR-Hoehenkarten (Building3D CC-BY-NC-SA); fuer Fassade/Helm/Zacken ungeeignet, DOM1 1 m zu grob. Lohnt nicht.
- **LC2WF (BMVC 2022, `license: null`)**: Linienwolke -> Knoten+Verbindungen per Line-Patch-Transformer, torch 1.8/CUDA 10, synthetische Gebaeude. Idee = Punkt 5 (Kantenklassifikator), Code zu alt.
- **Vervollstaendigung per gelernter 3D-Kurven-Inpainting**: keine Arbeit 2024-2026 gefunden, die fehlende Kantenstuecke aus Verdeckung ergaenzt; die Feldantwort ist die direkte Primitiv-Optimierung (Punkt 1).
- **Neue Linienverfahren 2026 ("LineSplat" o.ae.)**: nicht gefunden.

## 3. Lizenz-Merkliste (fuer LIZENZ_WERKZEUGE.md)
SketchSplat MIT (Rasterizer offen); gsplat Apache-2.0; DexiNed MIT; PiDiNet MIT + "research purpose"-Vorspann (anfragen); EdgeGaussians, 3D Curvix, 3D Edge Sketch, NEF_code, BWFormer, LC2WF: keine Lizenz (nur Test); LineGS: Gaussian-Splatting-License NC; S23DR 2026 Code Apache-2.0, Gewichte CC-BY-NC-4.0, HoHo-Daten gated; CurveGaussian, SGCR, CGGT, BrepGaussian: Code nicht verfuegbar.

## 4. Empfohlene Reihenfolge fuer die naechsten 3 Tage
Alles mit synthetischem Beweistest zuerst (Regel: Gate + Synthetik + 2 echte Objekte + Overlay), GPU von Anfang an, Ergebnisse als Testbilder `audit/` und Register-Eintrag.

**Tag 1 (6-8 h): Kettenbildung statt Fragmente (Punkt 2, Eigenbau, lizenzfrei)**
- Tiefen-Sweep um 2D-Kantenrichtung je Punkt erweitern -> 3D-Tangente (Richtung in der Ebene aus Strahl + Bildkante).
- Curvix-artiger Graph: `gpu_knn` (k ~ 8-12), Kante nur bei Abstand < r UND Tangentenwinkel < 20 Grad; 1D-Mannigfaltigkeit (je Punkt max. 2 Nachbarn vorn/hinten), Traversal -> Polylinien; Stuecke < n Punkte verwerfen.
- Stueckweise Modellwahl Linie / Kreisbogen / kubische Bezier (Kurve nur, wenn Fehler <= 0,5 x Linienfehler, EdgeGaussians-Regel).
- Gate: Anzahl Fragmente je echter Kante (synthetisch bekannt) sinkt, Deckung in Holdout-Fotos steigt, keine Zacke verloren (Zaehlung am Foto).
- Nebenher (1 h): SketchSplat-Repo `install.sh`/Submodule lesen (Rasterizer-Lizenz), Datenformat notieren.

**Tag 2 (6-8 h): Differenzierbare Primitiv-Verfeinerung gegen Stabilitaetskarten (Punkt 1)**
- Start = Polylinien/Boegen aus Tag 1 (statt EdgeGS). Loss = Distanztransformation der Stabilitaetskarte an projizierten Stuetzpunkten, gewichtet mit Sichtbarkeit aus Wolke (verhindert SketchSplat-Fehler "unsichtbare Kanten bekommen Supervision"), Median ueber Fotos.
- Topologie-Operationen wie SketchSplat: Endpunkte verschmelzen, Kollineare vereinen, in < X % der sichtbaren Fotos belegte Skizzen loeschen; Segmentenden an Wolkendichte beschneiden (Punkt 8).
- Wenn SketchSplat-Rasterizer frei: Original auf Teilszene Arkaden (15-30 Fotos) als Gegenprobe laufen lassen; sonst nur Eigenbau.
- Gate: Kantenabstand in Holdout-Fotos (nur Kantenpixel der Region, nicht Gesamtdiff; Lehre BS46b/BS65), Primitivzahl sinkt, Boegen als ein Objekt je Bogen.

**Tag 3 (6-8 h): Wiederholungs-Prior + Orakel**
- Punkt 4: Periode der Fenster/Zacken per Autokorrelation (Ortho + Giebelprofil), Kopie des bestbelegten Elements, Verifikation je Kopie in >= 3 Fotos, Zaehlprotokoll Z-*.
- Parallel in GPU-Leerlauf: EdgeGaussians (Punkt 3) auf 80-120 Fotos (heruntergerechnet) als Vollstaendigkeits-Orakel; Ausgabe PLY neben unser Gitter legen (Overlay ansehen, nicht mitteln). Lizenz null -> nur Vergleich, Eintrag LIZENZ_WERKZEUGE.
- Danach entscheiden: reicht Eigenbau (Tag 1+2) oder lohnt die lizenzfreie EdgeGaussians-Eigenversion auf gsplat (2-3 Tage) bzw. der gelernte Kantenklassifikator aus Generator-Synthetik (Punkt 5, 1-2 Wochen).

## 5. Grenzen dieser Recherche
- Keine der Methoden ist an 400+ Fotos einer Fassade belegt; alle Benchmarks sind Objekte (ABC-NEF, DTU) oder Raeume (Replica) mit 50-100 Ansichten. VRAM-Zahlen fehlen in allen Papers.
- Ceylan-Paper (Symmetrie) und S23DR-2026-Writeup nur teilweise gelesen (PDF-Text extrahiert bzw. SSL-Fehler).
- SketchSplat-Rasterizer-Lizenz offen; CurveGaussian-Code nicht erreichbar.

## Quellen
https://github.com/OceanYing/SketchSplat · https://arxiv.org/html/2503.14786v2 · https://github.com/kunalchelani/EdgeGaussians · https://arxiv.org/html/2409.12886v2 · https://github.com/C-H-Chien/3D_Curvix · https://github.com/C-H-Chien/3D_Edge_Sketch · https://arxiv.org/html/2506.21401v3 · https://arxiv.org/html/2609.14521v1 · https://arxiv.org/abs/2505.04668 · https://arxiv.org/abs/2602.21105 · https://github.com/cvg/EMAP · https://github.com/yunfan1202/NEF_code · https://github.com/ericshenggle/LineGS · https://github.com/3dv-casia/BWformer · https://github.com/Luo1Cheng/LC2WF · https://arxiv.org/html/2506.16421v1 · https://huggingface.co/jskvrna/2026_s23dr · https://s23dr.github.io/2026/ · https://huggingface.co/datasets/usm3d/hoho25k · https://isprs-annals.copernicus.org/articles/XI-2-2026/187/2026/ · https://github.com/nerfstudio-project/gsplat · https://github.com/xavysp/DexiNed · https://github.com/zhuoinoulu/pidinet · http://vecg.cs.ucl.ac.uk/Projects/SmartGeometry/factored_facade/
