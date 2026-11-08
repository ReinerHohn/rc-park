# Recherche Runde 2 (8.11.2026): Gesamtbreite/-hoehe + Parameter-Inferenz
Ehrlich vorab: Web-Suche (5 Abfragen) lieferte wenig Neues; Treffer meist 2013-2022. Mit "?" = nicht verifiziert (Fachwissen), Lizenz VOR Verkauf an LICENSE-Datei pruefen. NC = nicht kommerziell. Runde 1 (Wand-Ortho/Gitter, Bild-Chamfer, LIMAP, nvdiffrast meiden) nicht wiederholt.

## Kernbefund zum aktuellen Fehler
Der Bauteil-Sweep loest die falsche Ebene: das Gesamtmodell ist ~25 % zu schmal (20 statt ~26 m), Dach zu niedrig. Das ist ein GLOBALES Problem (Massstab/Gesamtbreite), nicht Bauteil-Lage. Erst Gesamtbreite/-hoehe/Dachlinie aus Fotos+Wolke festnageln, dann Bauteile. Wolke sieht nur Sichtbares (BS145 Schrumpf-Falle): Zielfunktion muss "Foto-Silhouette/Kante" enthalten, nicht nur Wolkenabstand.

## (1) Inverse procedural modeling
- Single-view 3D Reconstruction via Inverse Procedural Modeling (2023/24): Generatorparameter per Genetik + Gradient ueber differenzierbaren Generator + Differentiable Rendering; Fazit der Autoren: Silhouettenbild allein reicht. https://arxiv.org/abs/2310.13373 , https://www.mdpi.com/2073-8994/16/2/184 . Code/Lizenz nicht geprueft ?. Nur Gebaeude mit handgezeichneten Fenstermasken, Demo-Niveau.
- FacAID (Transformer, neuro-symbolische Fassadenrekonstruktion, 2024): https://arxiv.org/abs/2406.01829 . Gibt Fassadenprogramm aus EINEM Bild; fuer uns nur als Startwert-Idee, Gewichte/Lizenz ?, kein Meterbezug.
- ADPM (Gaillard 2022, differenzierbare prozedurale Modelle): https://www.cs.purdue.edu/homes/bbenes/papers/Gaillard22CGF.pdf . Knotenbasiert (Houdini-artig), nicht auf unseren manifold3d-Generator uebertragbar.
- Klassik Wu/Wonka 2014, Teboul, Martinovic (Bayes/MCMC ueber Grammatik): braucht Fassaden-Labelkarte; Idee uebernehmbar = Bayes/MCMC (oder Kostenvolumen) NUR ueber die ~10 Globalparameter (Breite, Traufhoehe, Firsthoehe, Anzahl/Abstand Arkade), Likelihood = Foto-Silhouette + Wolke. Keine neue Bibliothek noetig.
- Building3D (ICCV 2023, Dachdraht aus Airborne-LiDAR, Estland): https://arxiv.org/abs/2307.11914 , https://building3d.ucalgary.ca . Luftscan-Dach, nutzt uns nicht (Fotowolke, Daten Estland, Datenlizenz ?). BuildingNet: nichts verifiziert.
Bewertung: das Gesamtrezept "Parameter per Silhouette-Verlust" ist bestaetigt, ein fertiges Repo fuer unseren Fall gibt es NICHT.

## (2) Differenzierbares Rendern + Kamera-Verfeinerung
- PyTorch3D (BSD, schon kompiliert): Silhouetten-Renderer (SoftSilhouetteShader), Gradient auf Mesh-Vertices; Parameter-Gradient nur, wenn Generator differenzierbar waere (manifold3d: NEIN). Praktisch: Boxen/Prismen/Extrusionen der Globalteile in einem kleinen torch-Mini-Modell (Gesamtkoerper+Dach als parametrische Prismen) neu abbilden -> echter Gradient. Aufwand 6-10 h, GPU ja.
- Mitsuba 3 / Dr.Jit (BSD-3 laut Suche, nachpruefen; Mitsuba 2 war GPL!): zu schwer fuer reine Silhouette, kein Vorteil gegenueber PyTorch3D. https://pypi.org/project/mitsuba
- Kamera zusammen mit Parametern: Gefahr Mehrdeutigkeit (Massstab/Brennweite vs. Breite = genau unser Fehler 25 %). Kameras NUR ueber gemeinsame SfM + EXIF/Lot fest lassen; erst wenn Gesamtmodell stimmt, Kamera-Feinlage (6 DoF) mitnehmen. Memory: f-Fehler 2 % = 0,6 m.
- Alternative ohne Gradient: Silhouetten-IoU auf GPU per Kostenvolumen (Breite x Traufe x First, je 30-50 Stufen = ~100k Hypothesen x 5 Fotos). Billig, global, kein Optimierer. BEVORZUGT.

## (3) Manhattan / Fluchtpunkte / Ebenen
- Fluchtpunkte aus Linien (LSD/DeepLSD): Rotation der Fassade im Foto relativ zur Kamera; fixiert Gier/Nick/Roll der Wand ohne Wolke. Ergaenzt den RANSAC-Lot (BS146). Metrische BREITE gibt es daraus NICHT (nur Richtungen).
- Libs: Lu-Port (MIT, 3.-Partei) https://www.github.com/rayryeng/XiaohuLuVPDetection ; NeurVPS https://nips.cc/virtual/2019/poster/13316 (Lizenz ?); VPDETR AAAI 2024 (Code ?); Open3D RANSAC-Ebenen (MIT). Nutzen gering, da Lot schon gemacht.
- Wichtiger fuer Breite: Fassadenecken im Foto (Vertikalen) + Wandebene aus Wolke -> Strahl-Ebene-Schnitt gibt Eckenposition in Meter, unabhaengig von der duennen Wolke. Das ist die direkteste Messung der 26 m. Aufwand 3-4 h (kantenbasiert, Kameras bekannt).
- Verifikationsfalle: Wolke selbst evtl. verzogen (Offen: rechter Erker 1,4 m). Mit Fotos in 2+ Kameras triangulieren, nicht nur aus einem.

## (4) Dach/Hoehe aus Silhouette (Visual Hull)
- Himmelsmaske: SAM2 Apache-2.0 (Modell auf HF Apache-2.0; BSD-3 fuer cctorch-Teil) https://github.com/facebookresearch/segment-anything-2 . Fuer Himmel reicht auch Farbe+Gradient (blau/hell, Gegenlicht ok), SAM2 nur als Fallback. Lizenz unkritisch.
- Visual Hull aus Himmelsmaske mehrerer Kameras: Dachlinie (Traufe, First, Giebelstufen) als Silhouettenkante, jeder Kantenpunkt = Strahl. Mit bekannter Kamera liefern 3+ Fotos First/Traufe in Meter (Schnitt der Strahlen mit der Firstebene aus Wolke). Dach in Wolke duenn -> hier ist Foto der einzige Messer. Nachteil: Baeume/Verdeckung, Median/Trimmung. Aufwand 6-8 h. GPU: leichtes.
- Gegenprobe synthetisch: Generatormodell in die echten Kameras rendern -> Maske -> Verfahren muss Modell-Firsthoehe zurueckfinden.

## (5) Wasserdichtes Mesh / Hybrid
- Fuer Teile ohne Parametrik (Figuren, Erkerdach): Wolke -> Poisson/Delaunay (OpenMVS gewann schon, Memory Wettbewerb) -> ManifoldPlus (Triangle Soup -> wasserdicht, C++, Eigen/libIGL; Lizenz im Suchergebnis NICHT lesbar, pruefen) https://github.com/hjwdzh/ManifoldPlus , Paper https://arxiv.org/abs/2005.11621 . Eingabe ist Mesh, keine Wolke. Alternativ manifold3d (haben wir; Apache-2?) fuer Boolean/Reparatur.
- Hybrid: Parametermodell = Huelle/Gesamtkoerper (geschlossen, druckbar), Wolkenmesh nur als Einzelteil per Boolean-Union in lokaler Region (feste Region, kein Schrumpfen, BS145). Sinnvoll fuer Figuren/Helme, nicht fuer Fassade (BS138: Kaesten verlieren Details).
- Offen: Dichte der Wolke an Figuren reicht fuer Poisson? Test messen, nicht annehmen.

## (6) Facade-parsing + 3D-Lifting Repos (>= 2023)
Ehrlich: kein einsatzfaehiges, verifiziertes Repo gefunden.
- Translational Symmetry-Aware Facade Parsing (2021, Blender-Prozedur): https://arxiv.org/abs/2106.00912 (Code/Lizenz ?).
- Deep Learning Image-to-3D Facade Parser (2025, Thermal-LoD3.1, NeRF-Ortho): https://arxiv.org/abs/2508.04406 (Code ?).
- Fazit: Bausteine selbst bauen (Runde 1: Ortho+Gitter, OWLv2/SAM2).

## Rangliste TOP 3 (Test morgen)
1. **Fassadenecken + Traufe/First per Strahlen-Triangulation aus Fotos (Punkte (3)+(4))**. Aufwand 6-8 h, Erfolg hoch (direkt die gesehene Abweichung 20 vs 26 m), GPU leicht, Lizenz frei. Test: in 4+ Fotos aus verschiedenen Richtungen linke/rechte Fassadenecke und Dachkante per Kantenprofil (Vertikalen-Detektor, kein Handpick; BS148) finden; Strahlen mit Wandebene (RANSAC aus Wolke) schneiden; Breite = Eckenabstand, Streuung zwischen Fotopaaren als Fehlermass (Ziel < 0,3 m). Erst synthetisch (Modell in Kameras rendern). Danach Modell-Sx und Traufe darauf setzen.
2. **Silhouetten-Kostenvolumen fuer Globalparameter (Breite, Traufe, First, Arkadenzahl/-abstand)**, Himmelsmaske + Modell-Silhouette (PyTorch3D Rasterizer, nur Vorwaerts), 3-6 Fotos, IoU/Chamfer. Aufwand 8-10 h, Erfolg mittel-hoch, GPU ja, BSD. Test: Gesamtkoerper ohne Details, 3 Parameter x 40 Stufen ueber 5 Fotos; Posterior-Breite je Achse notieren; Ergebnis mit Test 1 abgleichen (Widerspruch NICHT mitteln, Regel 5).
3. **Bayes/MCMC (oder Kostenvolumen) ueber diskrete Strukturparameter** (Anzahl Boegen, Pfeilerabstand), Likelihood = Wolke(Hoehenband) + Fotokante, nach Fix von 1+2. Aufwand 6 h, Erfolg mittel (BS149: Wolke zeigt keine Pfeiler). Lizenz frei. Test: Hypothesen n=4..8 durchzaehlen, BIC; vorher Zaehlung am Foto (Regel 9).
Nicht empfohlen: Mitsuba (Aufwand ohne Vorteil), nvdiffrast (NVIDIA-Lizenz), NeRF/3DGS (BS), Gradient durch manifold3d (nicht moeglich).

Quellen: https://arxiv.org/abs/2310.13373 , https://www.mdpi.com/2073-8994/16/2/184 , https://arxiv.org/abs/2406.01829 , https://www.cs.purdue.edu/homes/bbenes/papers/Gaillard22CGF.pdf , https://arxiv.org/abs/2307.11914 , https://arxiv.org/abs/2106.00912 , https://arxiv.org/abs/2508.04406 , https://github.com/facebookresearch/segment-anything-2 , https://github.com/hjwdzh/ManifoldPlus , https://arxiv.org/abs/2005.11621 , https://nips.cc/virtual/2019/poster/13316
