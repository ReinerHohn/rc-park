# Recherche Drahtgitter-Verfahren (Mehrbild-Liniengruppierung, Ausreisser, Statistik) - 2026-11-09

Stand: Websuche 9.11.2026, nichts installiert, kein Code geaendert. Lizenzangaben: "belegt" = Seite gelesen, "unsicher" = nur Sekundaerquelle/Gedaechtnis, vor Verkauf an der LICENSE-Datei pruefen.
Schon verworfen (nicht wiederholen): Phasenkongruenz auf Ortho, DexiNed, Subpixel-Canny, Lab-b-Farbsweep, Linienpaar-Triangulation mit lockeren Schwellen.

Problem: Buendel langer paralleler Streuer bei Nahaufnahmen, duenne Hoehe (Tiefenunsicherheit entlang des Strahls gross), Staffelgiebel-Zacken.

## Prioritaete

### 1. Manhattan-/Fluchtpunkt-Richtungszwang auf 3D-Segmente (eigene Umsetzung)
- Kernidee: Aus den kalibrierten Fotos wenige dominante 3D-Richtungen (Dachfirst, Traufe, Lot, Giebelschraegen) per Mehrbild-Fluchtpunktschaetzung bestimmen (Hornacek/Maierhofer 2011: Linien ueber mehrere Bilder poolen). Jedes Segment wird auf die naechste Hauptrichtung gesnappt oder verworfen, wenn der Winkel > Schwelle; Streuer mit falscher Richtung fallen damit weg, und die Tiefe wird nur noch entlang einer 1-DOF-Familie gesucht.
- Nutzen: Direkt gegen "Buendel paralleler Streuer": parallele Linien haben exakt eine Richtung, nur Lage (2 DOF) ist frei; die duenne Hoehe schadet weniger, weil die Richtung nicht mehr aus schlecht bestimmter Tiefe kommt. Staffelgiebel-Zacken sind Schraegen mit wenigen diskreten Winkeln, also als zusaetzliche Richtungsklassen modellierbar.
- Lizenz: keine (eigene Umsetzung, Algorithmen aus Papieren). Aufwand: mittel (2-3 Tage, GPU-Histogramm auf der Richtungskugel einfach). Beachte Regel "nichts Objektspezifisches": Richtungen aus den Daten schaetzen, nicht festschreiben.
- Quelle: https://mlanthology.org/cvpr/2011/hornacek2011cvpr-extracting ; Ramalingam/Brand ICCV 2013 https://openaccess.thecvf.com/content_iccv_2013/html/Ramalingam_Lifting_3D_Manhattan_2013_ICCV_paper.html

### 2. LIMAP (cvg/limap) - Linienkarte mit Mehrbild-Gruppierung
- Kernidee: Pro Bild Linienhypothesen (LSD/SOLD2/DeepLSD) mit Matching (GlueStick/Linienbeschreiber), Triangulation, Bewertung durch Score + Sichtbarkeit, dann Graph-Clustering (Verbinden ueber Nachbarschaft der Segmente) und gemeinsame Verfeinerung mit Punkt-Linie-Verbindungen und Fluchtpunkt-/Parallel-/Orthogonal-Prioren.
- Nutzen: Genau unser Gruppierungsproblem (viele Fotos, bekannte Posen: LIMAP akzeptiert Posen als Eingabe, Triangulation mit Scoring statt fester Schwelle). Bringt fertige Tiefenunsicherheits-Behandlung und Score ueber Mehrbild-Konsens. Bei Staffelgiebeln muss man die Parallelitaets-Priore pruefen (Zacken sind nicht alle parallel).
- Lizenz: BSD-3-Clause (laut Sekundaerliste, unsicher); Abhaengigkeiten (COLMAP, PoseLib, ggf. SuperPoint-Gewichte in GlueStick-Pfad = NC) einzeln pruefen. Aufwand: mittel-hoch (Kompilierung C++ mit pybind, eigenes pip-Paket vorhanden aber schwer; nur im venv testen). GPU: Detektoren/Matcher ja, Kern auf CPU.
- Quelle: https://github.com/cvg/limap ; Paper https://arxiv.org/pdf/2303.17504

### 3. DeepLSD (nur als Detektor + Verfeinerung) 
- Kernidee: Netz sagt Linien-Attraktionsfeld und Gradientenrichtung voraus; klassischer Detektor auf diesem Feld liefert Segmente mit besserer Endpunktstabilitaet; Verfeinerung per Ceres moeglich.
- Nutzen: Wir haben bisher Kanten-Pixel (Stabilitaetskarte), keine echten Segmente mit Endpunkten. Bessere Segmente = weniger Streuer vor der Triangulation und Eingang fuer LIMAP/Line3D++. Gegenprobe zu bisher Verworfenem: DexiNed war Kantenkarte, DeepLSD liefert Segmente (nicht dasselbe), trotzdem Risiko auf Ortho-Domaene (trainiert auf Wireframe/MegaDepth).
- Lizenz: MIT inkl. Gewichte (belegt, github-Seite). Aufwand: niedrig-mittel (Inferenz per quickstart_install.sh, kein pip; GPU ok). 
- Quelle: https://github.com/cvg/DeepLSD

### 4. Line3D++ (Hofer et al.) - Segmentgruppierung per Sichtbarkeit + Graph
- Kernidee: Pro Segment Kandidaten-Matches ueber Epipolargeometrie in mehreren Bildern, Score mit Kovarianz-/Tiefenunsicherheit gewichtet, dann Graph-Clustering (Segmente, die auf dieselbe 3D-Linie fallen) mit Konsens und finaler 3D-Linienanpassung (Ceres optional, CUDA optional).
- Nutzen: Das ist die klassische Antwort auf "Buendel": Cluster werden zu einer Linie zusammengefasst, Einzelstreuer unter Mindestzahl unterstuetzender Bilder verworfen. Die Unsicherheitsgewichtung passt zu duenner Hoehe.
- Lizenz: Nach Repo-README MPL-2.0 (belegt, github.com/manhofer/Line3Dpp); in Forks als GPL genannt (alte Version). MPL-2.0 ist dateiweise Copyleft: als getrenntes Werkzeug/Binary ok, trotzdem vor Verkauf pruefen. Aufwand: mittel (CMake, Boost/Eigen/OpenCV, alter Code - CUDA-Version 5-6 getestet, CUDA ggf. abschalten; Eingabe: Posen im VisualSFM/COLMAP-Format, Segmente selbst liefern). 
- Quelle: https://github.com/manhofer/Line3Dpp

### 5. ELSR (CVPR 2022) - Ebenen- und Punkt-gefuehrte Linienrekonstruktion
- Kernidee: Segmente mit Ebenen aus der spaerlichen SfM-Punktwolke und mit nahen 3D-Punkten fuehren, um Mehrdeutigkeit der Zuordnung zu verringern; Linienkandidaten werden durch Ebene/Punkt-Naehe bewertet.
- Nutzen: Wir haben bereits eine (duenne) Wolke und Fassadenebenen; Linien auf Fassade/Dachflaechen werden an die Ebene gebunden, damit sinkt der Freiheitsgrad in Tiefenrichtung (genau unser schwacher Punkt). Planar-Prior gegen "Streuer abseits jeder Flaeche". Staffelgiebel liegen in der Giebelebene.
- Lizenz: unklar (nur ein Drittwrapper CC-BY-4.0 gefunden; Original-Lizenz unbekannt, Nutzung bis Klaerung nur zum Testen = NC). Aufwand: mittel (Original-Code C++, Eingabe .nvm). Das Prinzip "Segment nur an Ebene/Punkt zulassen" laesst sich ohne den Code selbst nachbauen.
- Quelle: https://openaccess.thecvf.com/content/CVPR2022/html/Wei_ELSR_Efficient_Line_Segment_Reconstruction_With_Planes_and_Points_Guidance_CVPR_2022_paper.html ; Wrapper https://zff.dev/spookie/ESLR

### 6. Robuste Richtung+Position-Akkumulation (Hough auf Pluecker/4-Parameter-Raum) mit Sichtbarkeits-Konsens
- Kernidee: Jedes triangulierte Segment stimmt in einem Raum aus Richtung (2 Winkel) und Lage (2 Parameter, Schnitt mit Ebene senkrecht zur Richtung) ab, gewichtet mit Kovarianz (Strahlenwinkel, Entfernung) und nur gezaehlt, wenn die Linie im Foto sichtbar war (Sichtbarkeit aus Wolke/Tiefe); Maxima = Linien, Zacken in der Verteilung = Streuer. Cluster-Schaetzung dann per Median/MAD statt Mittel.
- Nutzen: Ersetzt festes RANSAC durch globale Modenfindung; unterscheidet echte Parallelen (zwei eng benachbarte Maxima) von Streuer-Buendel (breite Verteilung ohne Spitze). GPU-freundlich (Histogramm/scatter_add). Zaehlen nur wo sichtbar verhindert, dass nicht-sichtbare Fotos die Linie "abwaehlen".
- Lizenz: keine (eigene Umsetzung). Aufwand: mittel (Tage). Verwandt: J-Linkage/T-Linkage/Progressive-X (Mehrmodell-Anpassung, ohne Schwellenwahl) - Kernidee gleich: Praeferenzmengen der Segmente clustern; Implementierungen teils mit NC-/Forschungslizenz (vor Nutzung pruefen, unsicher).
- Quelle: Hornacek 2011 (s.o.); T-Linkage https://www.diegm.uniud.it/fusiello/demo/tlk/ (Seite nicht geprueft)

### 7. Kovarianz-gewichteter Ausgleich mit robustem Kernel (Huber/Cauchy/MAD-Skalierung) und Re-Gewichtung
- Kernidee: Statt SVD-Ausgleich alle Beobachtungen mit Kovarianz aus Strahlengeometrie (Basislinie, Tiefenwinkel) und IRLS-Kernel, Skala per MAD pro Linie neu geschaetzt; zusaetzlich Prior-Terme (Richtung aus Punkt 1, Ebene aus Punkt 5).
- Nutzen: Bei Nahaufnahmen mit kleinem Parallaxwinkel dominiert sonst die schlechteste Tiefe; Gewichtung nach Strahlenwinkel entscheidet, welche Fotos ueberhaupt Tiefe liefern. Das ist die Pflege der vorhandenen SVD-Stufe, kein neuer Detektor.
- Lizenz: keine; Ceres Apache-2.0 / scipy BSD. Aufwand: niedrig. GPU: torch moeglich (LM mit autograd, kleine Probleme).
- Quelle: Standard (Hartley/Zisserman); Line3D++-Paper Hofer et al. CVIU 2016 (Kovarianz-Gewichtung)

### 8. RJMCMC / Markierte Punktprozesse fuer Liniensegmente (Forschungsoption, spaeter)
- Kernidee: Segmente als Punktprozess mit Prior (Parallelitaet, Anschluss, Ebene) und Datenenergie aus Foto-Kantenabstand; Reversible-Jump-MCMC fuegt Segmente hinzu/loescht/verschiebt, Simulated Annealing liefert die MAP-Konfiguration. Anzahl der Linien ist selbst Unbekannte (Dirichlet-/Poisson-Prior).
- Nutzen: Waere die theoretisch saubere Loesung fuer "wie viele Linien gibt es im Buendel" und Staffelgiebel-Zacken (Zacken = Prior auf feste Winkelmenge). Aber teuer und viele Hyperparameter - Erwartung: kein Gewinn gegenueber 1+6+7, nur wenn diese am Rauschboden stehen.
- Lizenz: keine fertige Bibliothek bekannt (Forschungscode, ueberwiegend nicht frei). Aufwand: hoch.
- Quelle: nicht gezielt gesucht, nur Stichwort Marked Point Process (Descombes/Zerubia); keine URL geprueft.

## Empfohlene Reihenfolge
1 -> 7 -> 6 (alles eigener Code, GPU, keine Lizenzfragen), parallel DeepLSD (3) als Segmentquelle testen und Line3D++ (4) oder LIMAP (2) als unabhaengigen Gegentest ("nicht mitteln", nur vergleichen). ELSR-Prinzip (5) in Punkt 1/7 als Ebenen-Prior einbauen. Beweis laut Regelwerk zuerst synthetisch (bekannte Streuer-Buendel mit duenner Hoehe), dann an zwei echten Objekten.

## Grenzen dieser Recherche
- Lizenzen von LIMAP, ELSR (Original) und SOLD2 nicht an der LICENSE-Datei gelesen.
- Keine Treffer fuer 2024/2025-Neuerungen (z.B. LineGS-artige Gaussian-Splatting-Linien); nicht weiter gesucht.
- Alle Eintraege gelten fuer Fotos mit bekannten Posen; keiner ist an unserer Nahaufnahme-Geometrie getestet.

Quellen: https://github.com/cvg/limap , https://arxiv.org/pdf/2303.17504 , https://github.com/cvg/DeepLSD , https://github.com/manhofer/Line3Dpp , https://github.com/cvg/GlueStick , https://openaccess.thecvf.com/content/CVPR2022/html/Wei_ELSR_Efficient_Line_Segment_Reconstruction_With_Planes_and_Points_Guidance_CVPR_2022_paper.html
