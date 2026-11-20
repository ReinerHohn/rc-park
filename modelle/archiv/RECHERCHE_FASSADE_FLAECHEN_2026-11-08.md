# Recherche Fassaden-Flaechen, Wiederholung, Konturschluss (8.11.2026)

Reine Web-Recherche (Suchmaschine, Treffer teils Spiegelseiten). Lizenzangaben stammen aus Suchtreffern, NICHT aus den LICENSE-Dateien: vor Verkauf in den Originalrepos pruefen (siehe `modelle/LIZENZ_WERKZEUGE.md`). Was nicht gefunden wurde, steht als "nicht belegt".

## 1. Befunde je Themenblock

### a) Wiederholungs-/Gittererkennung in Fassaden
- Musialski et al. 2010 (TU Wien): im entzerrten Frontbild werden Horizontal- und Vertikalrichtung getrennt behandelt, Ergebnis sind achsparallele Teilungslinien, die Regionen mit starker Translationssymmetrie abgrenzen. [PDF](https://www.cg.tuwien.ac.at/research/publications/2010/musialski-2010-tof/musialski-2010-tof-draft.pdf)
- Patent US9036915 (Architectural pattern detection): Harris-Ecken als Saatpunkte, je Saat SSD-Aehnlichkeitskarte des Patches. Patentiert, Rechtslage fuer Eigenbau nicht geprueft. [Google Patents](https://patents.google.com/patent/US9036915)
- Previtali et al. 2013 (ISPRS Annals): Wiederholstrukturen in Laserscans in drei Stufen: Segmentierung, Element-Clustering, Regularitaetsschaetzung (Gitterparameter per kleinste Quadrate). [ISPRS](https://isprs-annals.copernicus.org/articles/II-5-W2/241/2013/)
- Shen et al. (Cardiff): Fassade als rechteckiges Gitter bzw. Gittermix, rekursive top-down-Teilung; gleiche Pipeline fuer 3D-Scan und Bild. [PDF](https://orca.cardiff.ac.uk/45701/1/a184-shen.pdf)
- Mitra et al. "Interactive Facades": Segmentierung, Wiederholungserkennung und Elementkonfiguration gemeinsam zu optimieren ist besser als nacheinander. [PDF](https://discovery-pp.ucl.ac.uk/id/eprint/1393828/1/Mitra_interactiveFacades_eg13_small.pdf)
- Teboul et al. CVPR 2011: Fassadenparsing als Formgrammatik (rekursive Binaersplits) mit Reinforcement Learning. [HAL](https://hal.archives-ouvertes.fr/hal-00856135); PAMI-Fassung [PDF](https://simonl02.users.greyc.fr/files/Documents/Publications/teboul_pami_2013.pdf). Code/Lizenz: nicht belegt.
- Datensaetze: CMP Facade (Tylecek), Spiegel auf Hugging Face als MIT gelistet (nicht verbindlich fuer das Original) [HF](https://huggingface.co/datasets/Xpitfire/cmp_facade/commit/48bbc4fe767dcfaffcd60f8f8b2a7fe7d21dcbc7); Original-Lizenz nicht belegt. ECP: Nutzung in [DeepFacade/IJCAI 2017](https://ijcai.org/proceedings/2017/320.md) belegt, Lizenz nicht belegt. Beide sind Fotos neuzeitlicher Fassaden, Eignung fuer unsere Fachwerk-/Historienfassade nicht belegt.
- Detektoren: OWLv2 `google/owlv2-base-patch16` laut HF-Metadaten Apache-2.0 [HF](https://huggingface.co/google/owlv2-base-patch16). Grounding DINO laut Roboflow Apache-2.0 [Roboflow](https://roboflow.com/model-licenses/grounding-dino). Ultralytics-YOLO (v5/v8/v10/11/12) laut Roboflow AGPL-3.0 [Vergleich](https://playground.roboflow.com/models/compare/grounding-dino-vs-yolov8): fuer Verkauf kritisch. Fensterspezifische Genauigkeit dieser Modelle: nicht belegt.

### b) Konturschluss und Formanpassung
- Schneider-Algorithmus (kubische Bezier an Polylinie, Graphics Gems): Python-Port `fitCurves` (volkerp) laut Treffer MIT [GitHub](https://github.com/volkerp/fitCurves); Inkscape/2geom-C++-Version dual LGPL 2.1/MPL 1.1 [bezier-utils](https://bazaar.launchpad.net/~jaspervdg/+junk/aem-diffusion-curves/view/head:/2geom/bezier-utils.cpp). Quelle der Idee: [graphicsgems.org](http://graphicsgems.org/).
- OpenCV `cv2.ximgproc.EdgeDrawing` (ED, EDLines, EDPF, EDCircles; `detectEdges` dann `detectEllipses`; opencv-contrib). [Doku](https://docs.opencv.org/4.x/javadoc/org/opencv/ximgproc/EdgeDrawing.html). OpenCV-Lizenz (Apache-2.0 ab 4.5) und EDCircles-Patentlage: nicht belegt in den Treffern.
- scikit-image Kreis-/Ellipsen-RANSAC (`CircleModel`, `EllipseModel`, `ransac`): Treffer fehlten; Lizenz BSD-3 ist nur Allgemeinwissen, nicht belegt.
- Watershed/Felzenszwalb/SLIC/MCG, Elder-Zucker, Hough-Bogen: keine Treffer, Lizenzen nicht belegt (OpenCV/scikit-image enthalten Watershed, Felzenszwalb, SLIC als Funktionen).

### c) Foundation-Modelle
- SAM und SAM 2: Modelle/Code Apache-2.0; SAM 2 mit Nebenbedingungen (Demo-Schriften SIL OFL 1.1, optionaler GPU-Connected-Component-Code aus cc_torch mit eigener Lizenz); Datensatz SA-1B nur Forschungslizenz. Automatischer Maskengenerator ist in beiden Repos. [SAM](https://github.com/facebookresearch/segment-anything), [SAM2 PyPI](https://pypi.org/project/sam2/0.4.0)
- VRAM: kein offizieller Wert gefunden. Community-Angaben: auf <8 GB die kleine Variante, lange Bildkante <= 1024 px (unsichere Quellen: [theneuralbase](https://theneuralbase.com/sam/learn/beginner/oom-for-large-images/)). SAM2.1 small laut README 46 M Parameter. Messung per `torch.cuda.max_memory_allocated()` noetig.
- Eignung von SAM auf Orthobild+Tiefenbild eines Fachwerkhauses: nicht belegt (nur Plausibilitaet: Kacheln ~1024 px, Tiefenkanal als zusaetzliche Kante/Gate).

### d) Scan-to-BIM / Flaechenabstraktion
- PolyFit (Nan/Wonka): GPL-3.0, Solver braucht Gurobi (Lizenz nur akademisch frei) in der Original-Variante; in CGAL seit Aug. 2019 (Polygonal Surface Reconstruction); Python-Bindings fuer PolyFit-Release laut Treffer vorhanden. City3D (TU Delft): GPL-3.0, CGAL + Gurobi. [PolyFit](https://github.com/LiangliangNan/PolyFit), [City3D](https://github.com/tudelft3d/City3D), [CGAL-Doku](https://doc.cgal.org/latest/Polygonal_surface_reconstruction/examples.html)
- CGAL: Duallizenz GPL3+ / kommerziell (GeometryFactory); Kernel/Support LGPL, die meisten Algorithmen GPL. [cgal.org/license](https://www.cgal.org/license.html). Kinetic Shape Reconstruction: Paketlizenz und Python-Bindings nicht belegt.
- CloudCompare Facets, Pointfuse: keine Treffer, nicht belegt.
- Bewertung: alles GPL/Gurobi/CGAL ist fuer Verkaufsplaene schwer und passt zudem eher auf Daecher/Quader als auf Fassaden-2D-Flaechen. Unser Fall ist 2D (Ortho + Tiefe), daher kein Bedarf.

### e) Mittelung ahnlicher Konturen
- Mittelform ueber normierte Fourier-Koeffizienten (Groesse, Startpunkt, Orientierung entfernt), Rueckrechnung zur Mittelkontur. [Beleg 1](https://reference-global.com/article/10.2478/bhee-2019-0009), [Beleg 2](https://core.ac.uk/download/13710923.pdf)
- Fourier-Deskriptoren per kleinste Quadrate ausrichten: [Larsen, DTU](https://www2.imm.dtu.dk/pubdb/pubs/4045-full.html).
- Robustes (L1-)Procrustes mit Resistenz gegen Objekt- und Landmarken-Ausreisser: [Larsen, DTU/PeerJ-Vorabdruck](https://eprints.whiterose.ac.uk/173432/1/PeerJCompSci_authorms.pdf) (Zuordnung der Quelle aus Suchtreffer, vor Zitat pruefen). Generalisiertes Procrustes: Mittelform zentriert und Einheitsgroesse.
- Direktes Verfahren "robuster Median ueber Fourier-Konturen": nicht belegt; Ableitung unten ist eigene Ingenieursidee, nicht Literatur.
- `scipy.spatial.procrustes` / `orthogonal_procrustes`: Existenz Allgemeinwissen, Treffer fehlten (nicht belegt).

## 2. Bewertung nach Nutzen/Aufwand (fuer Python, OpenCV, NumPy, PyTorch, scipy, trimesh)

| Rang | Verfahren | Prinzip | Paket / Lizenz | Aufwand | Risiko |
|---|---|---|---|---|---|
| 1 | Kontur-Cluster + robuste Mittelform (Resampling auf N Punkte, Ausrichtung per Procrustes mit Skala+Verschiebung, Punktweise Median/Mittel, Instanzen = Mittelform skaliert/verschoben) | Gleiche Elemente werden per Aehnlichkeit gruppiert (Maskenform, IoU oder Fourier-Abstand), auf gemeinsame Bezugsform gelegt, punktweise gemittelt; Mittelform ersetzt alle Instanzen | NumPy/scipy/OpenCV (alle permissiv; Lizenzen nicht in Treffern belegt); Methodenbeleg Abschnitt e | 1-2 Tage | niedrig; Gefahr: echte Unterschiede (Verwitterung, Schattenkanten) werden wegmittelt, deshalb Residuum je Instanz anzeigen |
| 2 | Template-Matching (cv2.matchTemplate, NCC) auf Ortho-Farbe+Tiefe, ab einem Nutzer-Beispiel | Nutzer markiert 1 Fenster, NCC findet weitere Treffer; Treffer werden Cluster fuer Rang 1. Entspricht Saatpunkt-/Aehnlichkeitskarte aus Patent/Musialski | OpenCV | 0,5-1 Tag | niedrig; Skalen/Beleuchtung fix im Ortho, daher gut passend |
| 3 | Kreisbogen-/Ellipsen-/Bezier-Fit auf Kantenzuegen (Kreis per algebraischem LSQ + RANSAC, Bogen als Sehne+Pfeilhoehe; Schneider-Fit fuer freie Kurven) | Randpunkte eines Kantenzugs werden an Kreis oder Spline angepasst, Luecken werden durch die Modellkurve geschlossen | NumPy/scipy, `fitCurves` (MIT laut Treffer) oder eigene 60 Zeilen | 1 Tag | niedrig-mittel; Bogen vs. Ellipse Modellwahl per Residuum |
| 4 | Konturschluss durch Endpunkt-Verbindung (Endpunkte mit Richtung/Abstand paaren, Kosten = Abstand + Winkel, kuerzester Pfad auf Kantenkarte) | Gestalt-Verfahren: Luecken nur schliessen, wenn Fortsetzung glatt und kurz; sonst geschlossene Zelle per Distanzkarte/Watershed | OpenCV, skimage (`route_through_array`) | 2-3 Tage | mittel (falsche Schluesse) |
| 5 | Regionen aus Kantenkarte per Watershed/Felzenszwalb/SLIC statt reine Connected Components | Keimpunkte aus Distanztransformation der Nicht-Kanten; Watershed schliesst kleine Luecken implizit | OpenCV / skimage | 0,5-1 Tag | mittel (Uebersegmentierung) |
| 6 | SAM 2.1 small als Regionsvorschlag auf Ortho-Kacheln | Foundation-Modell liefert Masken fuer Fenster, Rahmen, Putzflaechen; Tiefenbild/Kanten filtern | `sam2` (Apache-2.0, Nebenbedingungen oben) | 1-2 Tage + VRAM-Messung | mittel-hoch; Zugewinn auf unseren Fassaden nicht belegt, aber nutzerseitig als Vorschlag brauchbar |
| 7 | OWLv2 / Grounding DINO fuer "window", "arch" | Offene Vokabeln-Detektion liefert Boxen; Boxen als Saat fuer Rang 2 | transformers, Apache-2.0 (laut HF/Roboflow) | 0,5 Tag | mittel (Boxgenauigkeit grob); Regel 9: Zaehlen nur am Foto |
| 8 | Gitter-/Grammatik-Parsing (Musialski, Teboul) | Teilungslinien-Raster, Spalten/Zeilen mit gleicher Struktur | Code nicht belegt, Eigenbau | 3-5 Tage | hoch; Fassade ist kein reines Gitter (Erker, Staffelgiebel) |
| 9 | PolyFit / City3D / CGAL-KSR | 3D-Flaechenabstraktion per Optimierung | GPL-3.0, Gurobi, CGAL GPL/kommerziell | hoch | passt nicht (2D-Problem, Lizenz) |
| - | Ultralytics-YOLO eigenes Fenster-Training | Detektor | AGPL-3.0 (laut Roboflow) | mittel | Lizenz fuer Verkauf kritisch, nicht empfohlen |

## 3. Empfehlung: die 3 ersten Schritte
1. **Wiederholte Elemente mitteln (Rang 1+2):** Nutzer klickt ein Fenster oder Bogen als Beispiel, NCC-Template-Matching auf Farb+Tiefen-Ortho findet Kandidaten; Konturen auf feste Punktzahl resamplen, per Procrustes (Skala+Translation, ggf. kleine Rotation) ausrichten, punktweise Median als Mittelform; Mittelform an allen Instanzen einsetzen, Restabweichung je Instanz als Zahl/Overlay zeigen (Regeln 3, 9, 9b beachten; Zaehlung am Foto belegen).
2. **Bogen- und Kurvenfit (Rang 3):** Kantenzuege per RANSAC auf Kreis/Ellipse, sonst Schneider-Bezier; der Fit schliesst die Luecken und liefert die parametrische Form (Radius, Stichhoehe) fuer die Tabelle `masstabelle.json`.
3. **Geschlossene Zellen (Rang 4+5):** Endpunkt-Verbindung mit Winkel/Abstandskosten, danach Watershed auf der Kantenkarte; SAM 2.1 small (Rang 6) nur als optionaler Vorschlagsgenerator nach VRAM-Messung.

## 4. Nicht belegt / offen
- Lizenz und Code von Teboul, CMP-Original, ECP; Genauigkeit von OWLv2/Grounding DINO auf Fenstern; SAM-2-VRAM auf RTX 4060 (messen); Kinetic Shape Reconstruction Lizenz/Bindings; CloudCompare-Facets/Pointfuse; scikit-image/scipy/OpenCV-Lizenztexte (hier nicht per Treffer geprueft); ein fertiges "robuster Median ueber Fourier-Konturen"-Verfahren.
- Alle Lizenzangaben vor Verkauf in `modelle/LIZENZ_WERKZEUGE.md` gegen die Original-LICENSE-Dateien eintragen.
