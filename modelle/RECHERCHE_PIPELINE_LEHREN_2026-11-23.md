# Recherche Pipeline-Lehren (23.11.2026)

Nur Recherche, kein Code, kein Rechenjob. Vorher gelesen: NICHTS_GEBRACHT, LIZENZ_WERKZEUGE, VERSUCHSREGISTER/Doku-projekt (grep), METHODE_SEITEN_SFM, GLOBALER_MAPPER_STABIL. Bereits Verworfenes ist markiert. pycolmap 4.2.1 lokal abgefragt (nur Attributliste).

## 1. Duenne Bruecken zwischen Seitenmodellen
- **Beste Empfehlung: `pycolmap.align_reconstructions_via_reprojections`** (BSD-3, in 4.2.1 vorhanden). Schaetzt die Aehnlichkeit aus gemeinsamen Bildern UND deren 2D-3D-Zuordnungen mit LORANSAC auf Reprojektionsfehler; braucht keine vielen gemeinsamen 3D-Punkte, wenige Eckbilder genuegen. Danach Inlier-Anteil + Blick-Tor + Massstabs-Gegenprobe (Turmbreite) als Tor. Aufwand klein (Ersatz fuer Klappung, die laut METHODE_SEITEN_SFM Unsinn lieferte). Quelle: colmap/src/colmap/estimators/alignment.cc.
- **Zweistufig: Bruecke als eigenes Kleinmodell.** Nur Eckbilder + je ~20 Nachbarn beider Seiten mappen, dann beide Seiten per `align_reconstructions_via_proj_centers` an dieses Brueckenmodell haengen (Kette A-Bruecke-B, je Glied Unsicherheit aus RANSAC-Wiederholung/Bootstrap). Aufwand mittel.
- **Pose-Graph mit Unsicherheit**: Kanten = Seiten-Aehnlichkeiten (Sim3) + GPS als schwache Kante, Loesung mit Ceres (BSD) robust (Cauchy). Lohnt erst ab >= 3 Seiten mit Ringschluss. ANNAHME: Ringschluss Nord-Ost-Sued-West am Turm vorhanden.
- GLOMAP ueber alles: am Schwabentor bereits verworfen (1120 verklebt); globaler Mapper hat keine Positionsprioren (GLOBALER_MAPPER_STABIL Befund 6). Nicht wiederholen.

## 2. Handy-GPS als schwacher Anker
- **Beste Empfehlung: Pose-Prior-BA nach dem Mapper mit robustem Verlust**, bereits vorhanden (`tools/sfm_gps_ausgleich.py`, BSD). Optionen in 4.2.1: `use_prior_position`, `use_robust_loss_on_prior_position`, `prior_position_loss_scale` (Cauchy), Kovarianz je Bild (std_x/y/z, FAQ colmap.github.io/faq.html). Empfehlung: std 15 m horizontal, 30 m vertikal, Cauchy-Skala ~ 2-3 sigma, damit 50-m-Ausreisser kaum ziehen.
- **Vorher Ausreisser per RANSAC-Sim3** (`align_reconstruction_to_locations`) und GPS nur Massstab/Drehung, nie Lage im Meterbereich: Logbuch 22.11. zeigt systematischen Nah-GPS-Fehler (+9,4 Grad, x0,87). Seitenzuordnung: Azimut Kamera->Turmmitte aus GPS nur fuer Seitenwahl, nicht fuer Lage (Teil lag 3-4 m daneben).
- `pose_prior_mapper` (schrittweise mit Prior): moeglich, aber langsam; ANNAHME: bringt gegenueber Nach-BA wenig, solange Seiten getrennt gemappt werden.

## 3. Guete eines Wandbilds als Tor
- **Beste Empfehlung: Leave-one-out-NCC je Kamera** gegen den Median der uebrigen Projektionen (Fenster 15-31 px, auf Gradientenbild, nur Zellen mit Textur). Kamera mit Median-NCC deutlich unter der Gruppe (MAD-Ausreisser) = falsch registriert. Eigener Code (OpenCV/numpy), Aufwand klein; baut auf `wand_feinausrichtung` (NCC-Feld, Phasenkorrelation) auf.
- **Pixel-Varianz/Robust-Streuung** (MAD je Pixel nach Helligkeitsangleich) als Karte -> Anteil "zerschmierter" Flaeche als Torzahl; zeigt Doppelkonturen wie BS9.
- **Restversatz per Phasenkorrelation je Kamera** (Vektorfeld): systematischer Versatz > 2 cm = Pose falsch, nicht Wand. Kanten-NCC als Tiefenscan ist verworfen (12.11.), hier nur Konsistenzmass.

## 4. Vorbauten parametrisch
- **Beste Empfehlung: Ebenen-Hypothesen aus Fotokanten + Wandbild je Ebene** (METHODE_EBENEN_BAUPLAN weiterfuehren): je Vorbau eigene Ebenen (Front + Seiten), Sweep der Tiefe je Ebene ueber Photo-Consistency (Punkt 3), Koerper = Quader/Prisma mit Massen aus Kanten. Eigener Code.
- **Layered depth / Piecewise-planar Stereo** (Sinha et al. 2009, Gallup 2010): Tiefenkarte als Ebenen-Labels per Graph-Cut; als Idee nachbauen (scipy max-flow wie BS49).
- **Fassaden-Parsing** (Teboul, Martinovic "ATLAS"): Grammatik-/Splitgitter am Wandbild; ShapeML GPL nur Werkzeug. RANSAC-Ebenen aus Wolke + Min-Cut schon gelaufen (BS48/49, ~0 Gewinn) - nur als Lage-Veto.

## 5. SIFT first_octave, Merkmale
- **Empfehlung: first_octave 0 bei max_image_size 3200-4000** statt -1: -1 verdoppelt das Bild (4x Speicher, mehr Kleinst-Merkmale aus Rauschen/Schaerfung der Handy-JPEGs). ANNAHME: bei 12 MP bringt -1 nur fuer ferne Kleinmotive etwas; vorher A/B an Inlier-Anzahl/Track-Laenge messen. GPU-SIFT-Speicher waechst etwa mit Pixelzahl je Oktave; 1600 px haben wir als VRAM-Grenze (Memory).
- **ALIKED (BSD-3) + LightGlue (Apache-2.0)**, auch DISK (Apache) - verkaufstauglich; SuperPoint NEIN. Fuer Turm-SfM verworfen (01.11. Netz verbogen, 15.11. Seiten verklebt); nur fuer Nachregistrierung behalten.

## 6. Laufzeit bei ~1100 Bildern
- **Beste Empfehlung: Retrieval-Paarauswahl** - `VocabTreePairGenerator` (in 4.2.1, BSD), top-k 30-50 + sequenziell fuer Videoclips + GPS-Naehe als Zusatz (`spatial`). Spart gegenueber exhaustive (~600k Paare) >90 %; laut Logbuch 20.11. sind 91 % der Paare ohnehin vergeblich.
- **MegaLoc** (github.com/gmberton/MegaLoc, MIT laut Quelle, LICENSE ungelesen) als Retrieval-Vorfilter. ANNAHME Lizenzfalle: Trainingsdaten u.a. Mapillary-SLS (NC), wie bei LoMa - nur Test, bis geklaert.
- Global Mapper je Seite (schon Standard, Sekunden) und Kamera je Clip (303 statt 1032 Kameras) beibehalten; COLMAP mit AVX2/FMA neu bauen (Testbau lief 20.11.).

Quellen: https://colmap.github.io/faq.html, https://github.com/colmap/colmap (alignment.cc, bundle_adjustment_ceres.cc), https://github.com/gmberton/MegaLoc, https://huggingface.co/gberton/MegaLoc, https://github.com/cvg/LightGlue, https://github.com/Shiaoming/ALIKED.
