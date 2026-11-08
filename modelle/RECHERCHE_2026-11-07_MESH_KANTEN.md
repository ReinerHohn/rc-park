# Recherche 7.11.2026: Mesh mit scharfen Kanten aus Wolke + Fotos (Kaufhaus)

Nur Websuche, nichts installiert. Lizenzangaben stammen aus Repo-Seiten/Suchtreffern; "?" = nicht verifiziert, vor Verkauf LICENSE-Datei lesen.
Aufwand 1 (Stunden) bis 5 (Wochen). GPU = RTX 4060 Laptop 8 GB.

## Vorab: Lizenzbefund fuer Verkauf (wichtig)
- **OpenMVS ist AGPL-3.0** (github.com/cdcseacave/openMVS, Resources: "AGPL-3.0"). Unser bisheriger Sieger (Delaunay+GraphCut, RefineMesh) ist damit fuer ein verkauftes Produkt/Dienst heikel. In `LIZENZ_WERKZEUGE.md` eintragen (Testwerkzeug, nicht im Produkt) oder kommerzielle Lizenz klaeren.
- CGAL: Alpha_wrap_3, KSR, PolyFit-Anteile = GPL-3.0-or-later ODER kommerziell (GeometryFactory). Nicht LGPL.
- Gaussian-Splatting-Familie (3DGS, 2DGS, MILo, GOF): Inria-"Gaussian-Splatting License" = nicht kommerziell. Nur als Testwerkzeug.
- nvdiffrast: NVIDIA Source Code License (nicht frei kommerziell; Anfrage ueber NVIDIA Research Licensing).

## (1) Mesh aus Splatting / Bildern mit scharfen Kanten
| Methode | Passt? | Lizenz | Aufwand | Nutzen Foto-Diff | Testplan |
|---|---|---|---|---|---|
| MILo (SIGGRAPH Asia 2025, github.com/Anttwo/MILo) | Mesh wird WAEHREND des Trainings differenzierbar mitoptimiert, 10x weniger Vertices, leere Innenseite; Kanten bleiben schaerfer als TSDF/Marching-Cubes. Eingabe COLMAP (haben wir). Py3.9/Torch 2.3.1/CUDA 11.8 (VRAM nicht genannt, `--data_device cpu`, lowres-Config) | Gaussian-Splatting-Lizenz (NC) | 4 | mittel-hoch, aber 3DGS war bei uns schon schlecht (Register BR) | `lowres` auf kh-COLMAP, Netz in foto_diff gegen OpenMVS |
| 2DGS (github.com/hbb1/2d-gaussian-splatting) | flache Surfels, gut fuer Ebenen; Mesh nur per TSDF (Open3D) -> Kanten verschmiert | LICENSE.md, Inria-artig (NC?) | 3 | gering-mittel | TSDF mit voxel 2-3 cm, Kantenkosten ansehen |
| PlanarSplatting (CVPR 2025, icetttb.github.io/PlanarSplatting) | Planare Primitive direkt optimiert, 3 min/Szene, aber fuer INNENRAEUME; Code "wird veroeffentlicht" (Stand unklar) | ? | 4 | hoch fuer Fassadenebenen, Bogen nicht | Nur wenn Repo vorhanden: Fassadenausschnitt |
| AdaptivePS (TU Delft 2026, github.com/MCHU-1999/AdaptivePS) | PlanarSplatting fuer GEBAEUDE aussen | ? | 4 | mittel-hoch | Repo/Lizenz lesen, 1 Fassade |
| Gaussian Opacity Fields (GOF) | Tetraeder-Isoflaeche, gut fuer unbegrenzte Szenen, 3DGS-Lizenz | NC | 4 | mittel | nach MILo (benutzt GOF-Extraktion) |

## (2) Kanten/Linien
- **LIMAP** (github.com/cvg/limap, **BSD-3**, `pip install pylimap`, Py3.10-3.13, Linux, CUDA nur fuer DL-Detektoren/Matcher; Rekonstruktion braucht hloc). Liefert 3D-Linien aus Kamerapfaden + Punkten; Eingabe = unsere 94 kalibrierten Fotos/COLMAP. Aufwand 2. Nutzen hoch als KANTENZWANG (Traufe, Fenster, Gesims) fuer Schnittebenen/Snap; direkt nutzbar fuer unseren "Kanten als Schnittebenen"-Hebel. Testplan: LIMAP auf 94 Fotos (LSD/DeepLSD), 3D-Linien in foto_diff reprojizieren, Anteil der Fotokanten mit 3D-Linie messen.
- **Line3D++** (Hofer; Lizenz ?, vermutlich freizuegig, pruefen): aelterer Vorlaeufer, CPU. Aufwand 2. Nur Gegenprobe zu LIMAP.
- Kanten als Zwangsbedingung im Mesh: kein fertiges Python-Paket gefunden; machbar selbst: Constrained Delaunay (fTetWild nimmt Eingabeflaechen, nicht Linien) oder Snap von Vertices/Ebenen an 3D-Linien (Eigenbau, Aufwand 3).

## (3) Wasserdicht / Reparatur ohne GPL
- **CGAL Alpha Wrap**: GPL/kommerziell (s.o.) -> nur Test. Gute Eigenschaft: garantiert wasserdicht, verfolgt Kanten bei kleinem alpha. Clean-room-MIT-Alternative: github.com/alecjacobson/alpha-wrap (Sekundaerquelle, Reife pruefen). Aufwand 2. Nutzen: Wasserdichtheit, Foto-Diff neutral bis leicht schlechter (Wrap rundet Kanten um ~alpha).
- **manifold3d** (Apache-2.0, bereits im Generator-venv): garantiert Mannigfaltigkeit nur fuer Booleans/Eingaben, repariert keine kaputten Netze. Gut als Verschmelzer Wand-Prismen + Bogen-Ausschnitt. Aufwand 1.
- **fTetWild** (MPL-2.0 laut Index; TetWild-Original GPL!): Wasserdicht + toleranzgesteuert, bewahrt Kanten besser als Alpha-Wrap, Aufwand 2 (CLI-Binary bauen). MPL = dateiweises Copyleft, verkaufbar. Testplan: OpenMVS-Netz -> fTetWild eps 0,3 % Diagonale -> Kantenkosten vorher/nachher.
- **Instant Meshes** (BSD-3, bekannt, nicht neu geprueft): Quad-Remeshing mit Kantenausrichtung (Feldglaettung), eher fuer glatte Flaechen; Kanten werden ausgerichtet, aber Qualitaet auf Fassaden mit Spitzen mittel. Aufwand 2.
- Open3D (MIT): Ball-Pivoting/Alpha-Shapes, Python, Aufwand 1; schwach bei Luecken.

## (4) Bildbasierte Verfeinerung gegen Fotos
- **OpenMVS RefineMesh**: photometrische Verfeinerung, bereits im Einsatz (AGPL). Referenz.
- **PyTorch3D** (BSD-3, bekannt): differenzierbarer Rasterizer, Silhouetten-/Kanten-Loss, Laplace/Edge-Regularisierung. Rasterizer-Kanten sind hart; Loss = a-contrario-Kantenabstand (Distanztransformation der Canny-Fotokanten, Chamfer). Aufwand 3-4. Nutzen hoch, weil direkt das Zielmass optimiert wird (Gefahr: ueberanpassen; Holdout-Fotos). Testplan: Vertex-Offset entlang Normale, Loss = Distanztransform-Wert an Rendern-Silhouettenkanten + Normalen-Konsistenz, 94 Fotos aufgeteilt 70/24.
- **nvdiffrast**: schneller, aber NVIDIA-Lizenz -> nur Test; PyTorch3D bevorzugen.
- Photometric Mesh Refinement allgemein (Delaunoy/Prados): Idee in RefineMesh enthalten; eigene Neuimplementierung unnoetig.

## (5) Gebaeude-spezifisch (Polygonflaechen)
- **PolyFit** (CGAL ab 2019, GPL) und **City3D** (github.com/tudelft3d/City3D, GPL-3, CGAL+OpenCV, SCIP im Repo): Kandidatenflaechen aus Ebenen, Auswahl per ILP -> wasserdichtes Polygonmodell, scharfe Kanten. Braucht Ebenen, keine Bogen. Passt gut fuer Kaufhaus-Hauptkoerper und Dach. Nur Test (GPL), Produkt via Eigenbau (RANSAC-Ebenen + ILP mit OR-Tools Apache-2.0) Aufwand 4. Aufwand Test 3.
- **CGAL Kinetic Shape Reconstruction** (KSR, GPL/kommerziell): Ebenen -> Zellkomplex -> graph-cut. Wasserdicht, Kanten exakt = Ebenenschnitte. Aufwand 3. Nutzen hoch (Fassade, Dach), Bogen ausserhalb (als Zusatz per manifold3d booleschem Schnitt, wie bisher).
- Unsere "Ebenen+Saeulen"-Variante war schlechter: Ursache vermutlich Ebenenwahl, nicht Konzept -> LIMAP-Linien als zusaetzliche Ebenen-/Kantenhinweise.

## Rangliste Top 5 "als Naechstes testen"
1. **LIMAP (BSD-3) -> 3D-Linien**, Abdeckungsmass gegen Fotokanten; speist 2, 3, 5. Nutzen/Aufwand und Lizenz am besten.
2. **PyTorch3D-Kantenverfeinerung** (BSD) des OpenMVS-Netzes mit Distanztransform-Loss und Holdout-Fotos; optimiert direkt das Foto-Diff-Mass.
3. **fTetWild (MPL)** auf OpenMVS-Netz: Wasserdichtheit mit minimalem Kantenverlust; Messung Kantenkosten vor/nach. Ergebnis ersetzt pymeshfix.
4. **CGAL KSR / PolyFit (nur Test, GPL)** mit Ebenen aus RANSAC + LIMAP-Linien: wasserdichtes Polygonmodell, Bogen separat; entscheidet, ob sich ein Eigenbau (OR-Tools) lohnt.
5. **MILo (NC)** auf kh-COLMAP, lowres; falls Gauss-Ansatz doch Kanten liefert. Niedrigste Prioritaet wegen 3DGS-Vorerfahrung und NC-Lizenz.
Parallel (Aufwand 1): OpenMVS-AGPL-Befund in LIZENZ_WERKZEUGE.md eintragen; Alpha-Wrap-MIT-Klon nur als Wasserdicht-Notnagel.

## Quellen
- MILo: https://arxiv.org/abs/2506.24096 , https://github.com/Anttwo/MILo
- PlanarSplatting: https://cvpr.thecvf.com/virtual/2025/poster/34959 ; AdaptivePS: https://github.com/MCHU-1999/AdaptivePS
- CGAL Lizenz: https://www.cgal.org/license.html ; Alpha_wrap_3: https://doc.cgal.org/6.0/Alpha_wrap_3/group__PkgAlphaWrap3Ref.html ; Clone: https://github.com/alecjacobson/alpha-wrap
- LIMAP: https://github.com/cvg/limap ; Paper https://arxiv.org/abs/2303.17504
- City3D: https://github.com/tudelft3d/City3D ; PolyFit: https://3d.bk.tudelft.nl/liangliang/publications/2017/polyfit/polyfit.html
- fTetWild: https://github.com/wildmeshing/fTetWild ; manifold: https://github.com/elalish/manifold
- nvdiffrast: https://github.com/NVlabs/nvdiffrast ; OpenMVS: https://github.com/cdcseacave/openMVS ; 2DGS: https://github.com/hbb1/2d-gaussian-splatting
- Nicht verifiziert (Kenntnisstand): Instant Meshes BSD-3, PyTorch3D BSD-3, Line3D++ Lizenz, PlanarSplatting-Codestand.
