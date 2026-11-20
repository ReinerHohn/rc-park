# Recherche 8.11.2026: Lage parametrischer Bauteile (Wolke + kalibrierte Fotos)
Hinweis: Web-Suche lieferte wenig Aktuelles; Rest aus Fachwissen (Lizenzen VOR Verkauf an den Repos nachpruefen, mit ? markiert). Gegen NICHTS_GEBRACHT.md abgeglichen: CMA-ES, Foto-Kantenterm in CMA-ES, Netze, 3DGS nicht wiederholt.

## Kernbefund
Fensterreihen in ebener Wand sind aus der WOLKE prinzipiell unbestimmt in u/z (Wand = Plateau). Die Information steckt nur in Foto-Kanten/Textur. Daher: Ebene fest -> Fotos per Homographie auf die Wand entzerren -> 2D-Problem (Gitter/Template) loesen, nicht 3D-Distanzfeld. Die Wolke liefert nur Ebene (dn) und Tiefe der Laibungen.

## 1. Fassaden-Parsing / Fenster
- Klassisch, robust, GPU-frei: Ortho-Projektion auf die Wandebene, Kantenprojektionsprofile (Spalten/Zeilen-Summen) + Periodizitaet (Autokorrelation / FFT) -> Gitter u0, du, z0, dz. Vorlaeufer: Pu & Vosselman (Fassadenrekonstruktion aus Laserdaten), Mitra et al. "Interactive Facades" (Regularitaet/Gitter, https://discovery-pp.ucl.ac.uk/id/eprint/1393828/1/Mitra_interactiveFacades_eg13_small.pdf).
- Deep Learning Fensterinstanzen: Mask R-CNN auf Fassadenbildern (https://arxiv.org/abs/2107.10006), detectron2 (Apache-2). Zero-shot: Grounding DINO / OWLv2 + SAM2 (alle Apache-2.0?) -> Fensterboxen im Foto, dann mit bekannter Kamera + Wandebene in Meter umrechnen (Strahl-Ebene-Schnitt). Passt zu eurem OWLv2-Ansatz (Memory "Erkennen + Einpassen").
- Fassadengrammatik/Regularisierung: Teboul et al. (Shape grammar parsing), Martinovic & Van Gool (Bayesian grammar learning), DeepFacade (Symmetrie-Loss, IJCAI 2017). Nutzen: Gitterzwang (gleiche Abstaende) macht Einzelfehler unschaedlich. Daten: CMP Facade DB (frei fuer Forschung, Lizenz pruefen).
- Punktwolken-Netze (AFGL-Net, https://www.mdpi.com/2072-4292/13/24/5039): fuer eure duenne SfM-Wolke ohne Fensterloecher kaum sinnvoll.

## 2. Parametrisches Fitting
- Line3D++ (Hofer, 3D-Liniensegmente aus Bildern, Lizenz ? MPL/GPL pruefen) und LIMAP (cvg/limap, https://github.com/cvg/limap, Paper https://arxiv.org/abs/2303.17504, Lizenz vermutlich BSD-3 ?). Liefern 3D-Kanten (Fenstersimse, Giebelstufen, Bogenansaetze) unabhaengig von Dichte der Punktwolke -> Fit-Ziel "Modellkanten gegen 3D-Linien" (Abstand Linie-Linie, GPU leicht). Sinnvoll fuer Giebelstufen/Kanten, wo Wolke duenn ist. Eingabe: eure Kameras (COLMAP-Format), Liniendetektor LSD/DeepLSD/SOLD2.
- Differenzierbares Rendern: PyTorch3D (BSD, schon kompiliert) -> Silhouette/Kanten-Rendering des Bauteils + Chamfer-Distance zur Foto-Kantenkarte (Distance Transform), Gradient auf (u,z,dn). nvdiffrast: NVIDIA Source Code License (Forschung gratis, kommerziell Sonderfall ?) -> meiden, PyTorch3D reicht. Wichtig: NICHT wieder CMA-ES sondern Sweep: Bauteil-Kantenbild einmal rendern und per 2D-Verschiebung im Chamfer-Feld bewerten (wie euer Sweep, aber im Bild, ueber mehrere Fotos summiert).
- Primitive: Efficient RANSAC (CGAL = GPL/kommerziell ?) vermeiden; Open3D (MIT) RANSAC/Ebenen, eigenes GPU-Hough fuer Zylinder/Ebenen. Hilft bei Ebenen, nicht bei Fenster u/z.
- FFT-Template-Matching im Voxelgitter: gut fuer Erker/Helme (3D-Volumen), nutzlos fuer ebene Fenster. torch.fft, sofort GPU.

## 3. Mehrdeutigkeit
- Achsenweise Bestimmtheit (habt ihr) weiter nutzen; nicht bestimmte Achse nicht per Wolke, sondern aus dem Bildterm festlegen (gestaffelte Schaetzung: Wolke -> dn,Ebene; Foto -> u,z).
- Zwei Terme getrennt halten, nicht addieren (Wolke- und Bild-Kosten als Kostenvolumen 3D (du,dn,dz) ueber Sweep); Posterior = exp(-E/T) normieren, Breite je Achse = Unsicherheit, bei breit -> Gitterprior/Nachbarbauteil (Fenster gleichmaessig, Oberkante = Traufe).
- Hypothesenauswahl: Gitter-Hypothesen (Anzahl n, Teilung) diskret durchzaehlen (BIC/Modellwahl), wenige Kandidaten billig, kein lokaler Optimierer. MRF (Fensterzellen ja/nein/Lage) mit Paar-Term "gleicher Abstand" per Graph-Cut/Belief Propagation (OpenGM/maxflow) - erst wenn Gitter nicht reicht.
- Mehrere Fotos aus verschiedenen Richtungen heben Plateaus nur ueber Parallaxe der Laibung (Tiefe); Schraegsichten gewichten hoeher.

## 4. Dach/Giebel, duenne Wolke
- Silhouette gegen Himmel: Himmelsmaske (SAM2 / einfache Farb+Gradient-Segmentierung), Modell-Silhouette (PyTorch3D) gegen Maske, IoU/Chamfer, mehrere Kameras -> Giebeltreppe Stufe fuer Stufe (Kantenpunkte der Silhouette = Strahlen, kein Wolkenpunkt noetig). Gegenlicht-Fotos liefern sehr scharfe Konturen. Verdeckungen (Baeume) per Median/Ausreisser-Trimmung.
- 2D-Konturfit: Polygonzug (Stufenhoehe/-breite als Parameter) gegen Konturpunkte der Maske nach Rueckprojektion auf die Giebelebene (Ebene aus Wolke), 1D-Sweep je Stufe.

## Rangliste
1. **Wand-Ortho je Foto + Kanten-/Gitterfit fuer Fensterreihen** (u,z,du,dz,n). Aufwand 8-12 h. GPU: nebenbei (cv2/torch Homographie, FFT-Autokorrelation). Lizenz: unkritisch (OpenCV Apache, torch BSD). Test morgen: eine Fensterreihe, Ebene aus Wolke (dn fest), 5-8 Fotos mit Kamera per Homographie entzerren (je Foto EINZELN, kein Median wie BS9), Sobel-Kanten, Spalten-/Zeilenprofile + Autokorrelation -> Gitter; Streuung der Gitter zwischen Fotos = Fehlermass; Gegenprobe synthetisch (Modell-Fassade rendern in echte Kameras). Erfolg: Gitter je Foto auf <5 cm gleich.
2. **Bild-Chamfer-Sweep (PyTorch3D) fuer Giebelstufen/Boegen/Erker**, Kosten = Summe ueber Fotos, Wolkenkosten getrennt als Kostenvolumen. Aufwand 10-16 h. GPU: ja (Raster + Distance Transform + Lookup). Lizenz: BSD. Test: Giebel mit Himmelsmaske, Modellsilhouette in 3 Fotos, 2D-Sweep du,dz +-2,5 m; Plateaubreite messen wie beim Wolkensweep; erst synthetisch (Modell mit bekanntem Versatz).
3. **3D-Linien (LIMAP/Line3D++) als Fit-Ziel** fuer Kanten (Simse, Stufenkanten, Dachkanten). Aufwand 6-10 h Aufbau + Rechenzeit. GPU: Liniendetektion ja (DeepLSD), Matching teils CPU. Lizenz: LIMAP wahrscheinlich BSD, Line3D++ pruefen; DeepLSD/SOLD2 teils Forschungslizenz ?. Test: LIMAP auf 10 Kaufhaus-Fotos mit vorhandenen COLMAP-Kameras, Linien in Meter ueberlagern, Abstand Modellkante-naechste 3D-Linie je Bauteil als zusaetzliche Kostenachse.

Zusatz (zero-shot): OWLv2/Grounding-DINO-Fensterboxen als Gitter-Startwert fuer Ansatz 1 (Apache-2.0 ?), nicht als Endmass.

Quellen: https://arxiv.org/abs/2107.10006 , https://discovery-pp.ucl.ac.uk/id/eprint/1393828/1/Mitra_interactiveFacades_eg13_small.pdf , https://www.mdpi.com/2072-4292/13/24/5039 , https://github.com/cvg/limap , https://arxiv.org/abs/2303.17504 , https://github.com/NVlabs/nvdiffrast
