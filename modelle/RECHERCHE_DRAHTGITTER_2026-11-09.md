# Recherche 3D-Kanten-Drahtgitter aus Fotos + Wolke -> geschlossene Teile (9.11.2026)

Methodik: WebSearch/WebFetch am 9.11.2026; Lizenzen aus README/Seitenkopf gelesen, wo nicht gefunden steht "nicht belegt". VERMUTUNG = nicht belegt. Vorarbeiten gelesen: RECHERCHE_KANTEN_MULTIVIEW, RECHERCHE_KANTEN_2, RECHERCHE_FUSION, NICHTS_GEBRACHT. Dort schon behandelt und hier NICHT wiederholt: Detektoren (DeepLSD, ScaleLSD, HAWP, SOLD2, DexiNed, TEED), LIMAP-Installation (pylimap), ECC-Feinregistrierung, VP-Einrasten, Bogen-RANSAC, ELSDc (AGPL), EdgeGaussians (keine Lizenz), SketchSplat (zurueckgestellt).

## 0. Wichtiger Lokalbefund (aus NICHTS_GEBRACHT)
- LIMAP ist bereits gelaufen (BS61, 7.11.): 1773 3D-Linien aus 94 Fotos, 964 mit Spur >= 5, Deckung >= 70 % bei 63 % der Linien (Kontrolle 36 %) -> Linien echt, aber Kantenzwang im Modell (BS65) brachte nur Rauschboden (+0,0015 / -0,0003). Ergebnisse liegen in /media/oem/scan/rc-park_null/limap/ergebnis/. Es lief mit Tiefenkarten von COLMAP-dicht und nur LSD (kein DeepLSD/torch) und 94 statt 440 Fotos. Ein Neulauf mit besserem Detektor und allen Fotos ist daher kein neues Verfahren, sondern ein Parameter-Upgrade.
- Bogen-Kreisfit aus Wolkenbelegung scheiterte (BS13); Kantenkarte statt Belegung wurde schon als Weg notiert.
- Schlussfolgerung: Die Luecke ist nicht "noch eine Linienrekonstruktion", sondern (a) Bogen/Kurven als Parameterobjekte, (b) die Verbindung Drahtgitter -> geschlossene Flaechen/Volumen, (c) Pruefung gegen Fotos mit sinnvollem Score.

## 1. Methoden fuer 3D-Linien/Kurven aus Mehrfachfotos

| Methode | Prinzip | Eingabe | GPU 8 GB / Aufwand | Lizenz | Implementierung | pip/conda | Reife |
|---|---|---|---|---|---|---|---|
| LIMAP | Linientracks, Triangulation, Line-BA mit Punkten/VP/Ebenen | COLMAP-Modell + Bilder | Triangulation CPU; Detektor GPU klein | BSD-3-Clause (belegt) | https://github.com/cvg/limap | `pip install pylimap` (Py 3.10-3.13); fuer Bildpipeline `hloc` aus Git; bekannte Fallen: MKL-Abbruch im BA (patchelf), Detektoren separat | hoch (v2.0.0, Quelle: https://github.com/cvg/limap) |
| Line3D++ | klassische Paarkonsistenz, Gruppierung | COLMAP/Bundler/NVM/OpenMVG-Ausgabe, undistortierte Bilder | CUDA optional; CMake-Bau mit Boost/Eigen/OpenCV | MPL-2.0 (belegt) | https://github.com/manhofer/Line3Dpp | kein pip (VERMUTUNG) | Autor pflegt seit Jan 2018 nicht mehr (README); als Vergleichsbasis |
| ELSR (CVPR 2022) | Ebenen- und Punktfuehrung beschleunigt Linienrekonstruktion fuer Stadtszenen | SfM-Punkte + Bilder | CPU | Original ohne offizielles GitHub gefunden; Drittrepo mit CC-BY-4.0 nur fuer den Wrapper: https://zff.dev/spookie/ESLR ; Lizenz des Originals UNKLAR | https://openaccess.thecvf.com/content/CVPR2022/html/Wei_ELSR_Efficient_Line_Segment_Reconstruction_With_Planes_and_Points_Guidance_CVPR_2022_paper.html | nein | mittel; Lizenz offen -> nur Test |
| NEAT (ICCV 2023) | Neural Attraction Fields: 3D-Segmente + Junctions per Volume-Rendering aus Mehrfachbildern | Bilder + Posen + 2D-Wireframe | Szenentraining | Code nicht gefunden | https://arxiv.org/abs/2307.10206 | - | Forschungsstand; EMAP-Paper meldet EMAP besser |
| EMAP "3D Neural Edge Reconstruction" (CVPR 2024) | UDF aus DexiNed/PidiNet-Kantenkarten, danach Extraktion parametrischer Kanten (Linien UND Kurven) | meta_data.json (Kameras) + Bilder + Kantenkarten | PyTorch 2.1/CUDA 12.1 (conda, Py 3.8); VRAM nicht angegeben; Laufzeit 2,5 h auf ABC-NEF laut CurveGaussian-Tabelle | MIT (belegt) | https://github.com/cvg/EMAP | conda env aus README | **Eigene Daten ausdruecklich NICHT unterstuetzt** (Checkliste "Custom Dataset" offen); nur ABC-NEF/Replica/DTU. Dazu Szene klein (Objektzentriert, 50-100 Ansichten). Fassade 440 Fotos = VERMUTUNG: Adapter + Speicherproblem |
| NEF (Neural Edge Fields) | parametrische 3D-Kurven aus Kantenkarten | Bilder+Posen | 1,5 h (CurveGaussian-Tabelle) | Code-Ort nicht gefunden | https://arxiv.org/pdf/2303.07653 | - | veraltet gegen EMAP |
| CurveGaussian / Curve-Aware GS (2025) | bidirektionale Kopplung Kurve <-> Gaussians, direkt aus Kantenkarten, Bezier-artige Kurven | Kantenkarten, Posen (COLMAP bei Realdaten) | 3 min auf ABC-NEF (10k Iterationen), VRAM nicht berichtet; Realdaten nur Objekte 480x480 | Lizenz nicht belegt; Gaussian-Rasterizer (INRIA) ist nicht-kommerziell (VERMUTUNG, pruefen) | https://github.com/zhirui-gao/Curve-Gaussian ; https://arxiv.org/html/2506.21401v3 | - | jung; liefert nur 70 Kurven je Szene (kompakt, genau das, was wir fuer Bogen wollen) |
| SketchSplat (ICCV 2025) | differenzierbare Linien/Kurven (Kontrollpunkte, Opacity) direkt gegen 2D-Kantenbilder, Topologie-Operationen | kalibrierte Bilder, Kantenbilder (eigener 2DGS-SN-Detektor) | keine Angaben | Lizenz nicht belegt; Rasterizer-Frage offen | https://github.com/OceanYing/SketchSplat ; https://arxiv.org/pdf/2503.14786 | - | jung |
| 3D Curvix (BMVC 2025) | konsolidiert redundante 3D-Kantenpunkte zu Kurvensegmenten (Nachbarschaftsgraph -> 1D-Mannigfaltigkeit -> Verbindungsgraph) | 3D-Kantenpunkte aus "3D Edge Sketch" (Mehrfoto-Kanten) | C++/CMake, CPU, Eigen 3.3.2; "GPU-Version in Arbeit" | **keine Lizenz im README** | https://github.com/C-H-Chien/3D_Curvix ; https://bmvc2025.bmva.org/proceedings/656/ | nein | Forschungscode ("a bit messy", 4 Sterne) |
| Fabbri/Kimia "3D Curve Sketch", Wang/Kneip (Bezier-SfM) | klassisch: Kurvenstereo, verkettete Bezier-Kurven | Bilder+Posen | CPU | nicht belegt | https://multiview-3d-drawing.sourceforge.net/ ; https://arxiv.org/pdf/1810.12532v1.pdf | nein | akademisch, alt |

Statuen: Kein Linienverfahren behandelt freie Formen; Kanten an Statuen sind Texturkanten/Silhouetten, nicht Kreisbogen oder Gerade. Weiter wie im Vorlauf: Maske + Ebenenabstand als Filter, Statuen NICHT als Drahtgitter, sondern als Netz/Voxelblock aus Wolke (Poisson/Delaunay) abgrenzen (VERMUTUNG, keine Quelle).

## 2. Aus Punktwolken (ohne Fotos)

| Methode | Eingabe/Zweck | Lizenz | Befund |
|---|---|---|---|
| PC2WF (ICLR 2021) | Wolke -> Wireframe, trainiert auf ABC (CAD-Teile); Code https://github.com/YujiaLiu76/PC2WF | keine Lizenz im Repo gesehen | Test mit CUDA 10.0/Py 3.7/PyTorch 1.2/MinkowskiEngine 0.2.9 -> Altumgebung; Trainingsdomaene CAD-Teile, nicht Fassade; **nicht uebertragbar** (VERMUTUNG). Lohnt nicht |
| PBWR (2023) | Wireframe aus Luft-LiDAR (Gebaeudedaecher) https://arxiv.org/abs/2311.12062 | Code/Lizenz nicht gefunden | Dachmodelle, nicht Fassade. Lohnt nicht |
| ParSeNet -> Point2CAD (CVPR 2024) | ParSeNet/HPNet segmentieren Wolke in Flaechen (Ebene, Zylinder, Kegel, Kugel, B-Spline); Point2CAD schneidet Flaechen zu Kanten/Ecken (B-rep) | README: CC-BY-NC 4.0 (laut Seite, Seitenleiste nennt zugleich Apache-2.0: widerspruechlich, LICENSE-Datei pruefen) -> **NC, nur Test**: https://github.com/YujiaLiu76/point2cad | Eingabe (x,y,z,Flaechen-ID); Docker `toshas/point2cad:v1` mit `--gpus`, PyMesh; auf CAD-Teilen trainiert; Fassaden-Domaene fremd. Idee uebernehmen (Flaechen schneiden -> Kanten), Netz nicht |
| LC2WF/Line-Cloud-zu-Wireframe | https://github.com/Luo1Cheng/LC2WF (Suchtreffer, nicht geoeffnet) | unbekannt | VERMUTUNG: Dachwireframes aus Linienwolken, Domaene Gebaeudedach |

Fazit: Gelernte Wolke->Wireframe-Netze sind auf CAD-Teile/Daecher trainiert und fuer eine Renaissance-Fassade mit Bogen und Fenstergiebeln nicht belegt. Ihre klassische Idee (Ebenen RANSAC -> Schnitt -> Kanten) ist ohne Netz machbar (Open3D `segment_plane`, MIT, siehe Vorrecherche).

## 3. Drahtgitter -> geschlossenes Volumen

Befunde:
- Heritage-Praxis (HBIM, Scan-to-BIM): Punktwolke -> NURBS-Flaechen/Netze -> BIM-Objekte; Hauptengpass bleibt manuelle Arbeit; Luecke zwischen NURBS-Software und parametrischen BIM-Tools (ISPRS 2023: https://isprs-archives.copernicus.org/articles/XLVIII-M-2-2023/267/2023/isprs-archives-XLVIII-M-2-2023-267-2023.pdf ; Banfi NURBS-HBIM: https://re.public.polimi.it/handle/11311/885963 ; Buildings-Review 2024: https://mdpi.com/2075-5309/14/3/564 ; Rhino+Grasshopper-Automatik: DOI 10.3390/rs12071094, Andriasyan et al. 2020). Profis verbinden also nicht aus Kanten Volumen, sondern modellieren Profile/Sweeps/Loft von Hand an der Wolke (Schnitt-Profil -> Extrusion/Sweep; Bogen als parametrischer Bogen; Zierrat als Bibliotheksobjekt). VERMUTUNG: Das entspricht unserem parametrischen Generator.
- Algorithmisch (Drahtgitter -> Flaechen): Ebenen aus Linien (RANSAC mit Mehrfachzugehoerigkeit) und Flaechen aus Ebenenschnitten, Ziel wasserdichtes Netz: "Surface Reconstruction from 3D Line Segments" https://arxiv.org/pdf/1911.00451v1.pdf ; klassisch: Flaechen als minimale Zyklen im Kantengraph + Moebius-Regel zum Verschweissen (HAL-Paper https://api.core.ac.uk/oai/oai:HAL:inria-00202636v1 ; Varley/Company "A new algorithm for finding faces in wireframes"); Kandidaten-Flaechen + Auswahl per ILP (CGAL PolyFit, GPL -> nur Test; Kinetic Shape Reconstruction ebenso, siehe RECHERCHE_FUSION).
- Eigenbau-Weg (VERMUTUNG, zu pruefen): Drahtgitter nur als Constraint nutzen: Wolken-Netz (Delaunay/GraphCut, laut BS: OpenMVS vorne) + Kanten als Schnittebenen/Creases (Vorarbeit: "Kanten als Schnittebenen" naechster Hebel laut Stand 6.11.) + fTetWild (schon im Einsatz, MPL-2.0) fuer Wasserdichtheit.

## 4. Verfeinerung gegen Fotos (analysis-by-synthesis)
- Differenzierbar: NEAT (Volume-Rendering von Segmenten), SketchSplat (differenzierbare parametrische Skizzen), CurveGaussian, EMAP (alle oben). Alle brauchen Szenentraining, keines ist ein "nimm vorhandenes Drahtgitter und verfeinere es". Schnelle Quelle zu SketchSplat/NEAT: https://arxiv.org/pdf/2503.14786 ; https://arxiv.org/pdf/2307.10206 . DiffVG-Erweiterung auf 3D-B-Splines existiert (Wire-Art, https://arxiv.org/html/2605.11977), Domaene Kunst, nicht Rekonstruktion.
- LIMAP Line-BA verfeinert Linien und Posen gemeinsam, ist aber heuristisch gegen Detektionen, nicht gegen Kantenkarte.
- **Eigenbau ist hier die sinnvollste Antwort (VERMUTUNG, kein fertiges Werkzeug gefunden):** Projektion der Segmente/Bogen in die Fotos, Score = Abstand zur Kantenkarte (Distanztransformation, DexiNed/DeepLSD), Gradient auf die 6/7 Parameter je Segment oder Bogen (torch, wenige hundert Objekte -> trivial auf 8 GB). Entspricht Regel 9d(b) der CLAUDE.md (noch nicht gebaut). Einwaende aus NICHTS_GEBRACHT: Diff-Score am Rauschboden (BS46b, BS65) -> Score nur auf Kantenpixeln der Region und mit Holdout-Fotos bewerten, nicht mit Gesamtdiff.

## 5. Rangliste

ZUERST (Aufwand in Stunden):
1. **LIMAP-Neulauf mit allen Fotos + DeepLSD/ScaleLSD und Linienprojektion der FERTIGEN 3D-Linien in Holdout-Fotos** (4-8 h). Grund: Install steht (venv-limap), BSD-3, Reife. Nur Parameter-Upgrade der BS61. Nutzen: Spurlaenge als Konfidenz, Line-BA mit Ebenen/VP.
2. **Eigener differenzierbarer Bogen-/Segment-Fit gegen Kantenkarten** (6-10 h): Segmente von LIMAP/kanten_segmente als Start, Bogen als Kreisparameter (Mittelpunkt, R, Winkelbereich, Ebene), Loss = Distanztransformation DexiNed/DeepLSD, ueber Fotos gemittelt (Median). Loest Bogen/Kurven ohne neue Fremdsoftware, lizenzfrei, passend zu Regel 9d(b).
3. **Drahtgitter -> Flaechen per Ebenengraph** (8-16 h): Ebenen aus Wolke (RANSAC) + Linien, Kanten = Ebenenschnitte (stabiler als Bildkanten), Flaechenzyklen, dann fTetWild fuer Wasserdichtheit. Eigenbau nach arXiv 1911.00451 (Idee); PolyFit/KSR (GPL) nur als Testorakel.

ZUSATZ:
4. 3D Curvix (C++, CPU, keine Lizenz -> nur Test, ca. 4 h): als Konsolidierer von Kantenpunkten zu Kurvenzuegen, wenn Bogen-Fit nicht reicht. Vorher Lizenz beim Autor erfragen.
5. CurveGaussian / SketchSplat auf einer Teilszene (Bogenfeld, 15-30 Fotos, 8-12 h inkl. Adapter): Nur als Forschungstest, Rasterizer-Lizenz vor Verkauf pruefen. CurveGaussian liefert kompakte Kurven (70 je Szene statt 1952), attraktiv.
6. EMAP: nur wenn Custom-Dataset-Unterstuetzung erscheint; sonst Adapter-Aufwand (1-2 Tage) ohne Garantie, 440 Fotos wahrscheinlich zu gross (VERMUTUNG).
7. Line3D++ als Vergleichsbasis fuer LIMAP (4-6 h Bau, MPL-2.0).

LOHNT NICHT:
- PC2WF, PBWR, ParSeNet/Point2CAD (Domaene CAD/Dach, alte Umgebung bzw. NC, Fassade ungeeignet).
- NEAT/NEF (EMAP ersetzt sie; Code nicht gefunden).
- ELSR (Lizenz des Originals offen, Gewinn gegenueber LIMAP nicht belegt).
- Statuen als Drahtgitter (Freiform).

## 6. Lizenz-Merkliste (fuer LIZENZ_WERKZEUGE.md)
LIMAP BSD-3 ok; Line3D++ MPL-2.0 ok; EMAP MIT ok (Gewichte DexiNed/PidiNet separat pruefen); Point2CAD CC-BY-NC (laut README; widerspruechliche Seitenleiste) NC; CGAL PolyFit/KSR GPL nur Test; 3D Curvix, SketchSplat, CurveGaussian, PC2WF, NEAT: keine Lizenz gefunden -> wie "alle Rechte vorbehalten" behandeln, nur Test.

## Quellen
https://github.com/cvg/limap · https://github.com/manhofer/Line3Dpp · https://github.com/cvg/EMAP · https://neural-edge-map.github.io · https://arxiv.org/pdf/2405.19295 · https://arxiv.org/abs/2307.10206 · https://arxiv.org/pdf/2303.07653 · https://arxiv.org/html/2506.21401v3 · https://github.com/zhirui-gao/Curve-Gaussian · https://arxiv.org/pdf/2503.14786 · https://github.com/OceanYing/SketchSplat · https://github.com/C-H-Chien/3D_Curvix · https://bmvc2025.bmva.org/proceedings/656/ · https://openaccess.thecvf.com/content/CVPR2022/html/Wei_ELSR_Efficient_Line_Segment_Reconstruction_With_Planes_and_Points_Guidance_CVPR_2022_paper.html · https://github.com/YujiaLiu76/PC2WF · https://arxiv.org/abs/2311.12062 · https://github.com/YujiaLiu76/point2cad · https://arxiv.org/pdf/2003.12181 · https://arxiv.org/pdf/1911.00451v1.pdf · https://re.public.polimi.it/handle/11311/885963 · https://mdpi.com/2075-5309/14/3/564 · https://isprs-archives.copernicus.org/articles/XLVIII-M-2-2023/267/2023/isprs-archives-XLVIII-M-2-2023-267-2023.pdf
