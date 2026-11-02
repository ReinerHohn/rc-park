# Roadmap: Pipeline fuer beliebige Bauwerke aus freien Bildern/Drohnenvideos (Stand 2026-11-02)

Ziel: Objekt benennen (Name + Koordinate) -> Daten holen -> Rekonstruktion -> druckbares H0-Modell, nur Software. Grundlage: vier Recherche-Berichte (Unterkompetenz markiert; alles "Wissen/Suche" vor Einsatz an der Primaerquelle pruefen, KEINE Rechtsberatung).

## 1. Daten (Lizenz entscheidet, ob es ein Produkt wird)
- NICHT tragfaehig fuer Verkauf: YouTube-Standardlizenz (heutiger Martinstor-Weg = private Messvorlage), Mapillary (NC), ETH3D (NC), Tanks and Temples (verbietet kommerzielle 3D-Modelle), Google Photorealistic 3D Tiles/Earth Studio (verbieten Analyse/Ableitung).
- Verwendbar: Commons (CC0/PD/CC BY; CC BY-SA nur nach Klaerung), YouTube-Filter 'Creative Commons' (CC BY; Rechtekette pruefen), Pexels/Pixabay (Marken, keine Weitergabe unveraenderter Kopien), Flickr (CC0/PD/BY), amtliche Daten (Namensnennung), Nutzer-Uploads mit Rechtezusicherung.
- Lizenz je Datei protokollieren, Filterliste (Standard-YouTube + NC gesperrt). Endprodukt ohne Bildtexturen (Messwerte sind Fakten, Mesh/Textur-Bearbeitung ungeklaert).
- Anwalt: Rekonstruktion = Bearbeitung? CC-BY/SA-Pflichten; § 44b UrhG (Opt-out, Beweislast); Panoramafreiheit (Drohne!); Denkmal-/Architekten-/Markenrechte; Plattform-AGB (yt-dlp).

## 2. Automatische Auswahl (Eigenleistung, nichts Fertiges gefunden)
Suche (Commons/Flickr/YouTube API mit Lizenzfilter) -> Relevanz (CLIP/DINOv2 + LightGlue-Inlier gegen Referenzbild; GPS-Plausibilitaet) -> Frame-Auswahl (Schaerfe, Basislinie, Azimut-Abdeckung) -> Masken (feste Overlays: erledigt in video_sfm.py; Himmel/Personen: SAM 2 Apache-2.0 + Grounding-DINO) -> Kennzahlen ohne Referenz (registrierte Bilder, Reproj., Abdeckung, Wiederholbarkeit).

## 3. Massstab/Lage weltweit (Rangfolge, mindestens zwei UNABHAENGIGE Quellen, Widerspruch nicht mitteln)
1 Video-Telemetrie (DJI-SRT/EXIF-GPS) gegen Kamerapfad (Sim3, robust); 2 Normobjekte (Kennzeichen, Spurweite - Ort-abhaengig 1000/1435 mm!, Tueren); 3 amtliche 3D-Daten (DE LoD2, NL 3DBAG, CH swissBUILDINGS3D, JP PLATEAU, FR LiDAR HD; AT/DK/UK/US nicht recherchiert); 4 Overture/OSM/Wikidata nur Plausibilitaet (ODbL; Hoehendefinition unklar); 5 Sonne/Schatten; 6 Metric-Depth nur Gegenprobe (Lizenzen ungeklaert); 7 GLO-30/SRTM nur Gelaende. LoD2 + DOM1 zaehlen oft als EINE Quelle. Bei uns schon: `tools/massstab_schwarm.py` (Rahmen + Plug-ins GPS/LoD2/Normobjekte).

## 4. Rekonstruktionsqualitaet (nur lizenzseitig tragfaehige Hebel, jeweils messen)
1 Konsens aus Mehrfachlaeufen (Seeds/Bildauswahl, Median) - trifft die Bandwahl-Streuung (BO), Lizenz frei; 2 MapAnything (Apache-Gewichte `map-anything-apache`) als unabhaengiger zweiter Weg, VRAM auf 8 GB messen; 3 Depth-Anything-3 (nur BASE/SMALL/METRIC-LARGE Apache) als Tiefenprior fuer duenne Kupferdaecher - HYPOTHESE, am Martinstor testen; 4 Matcher: ALIKED/DISK + LightGlue, RoMa; 5 VGGT-1B-Commercial erst nach vollem Lizenztext. Nur zum Testen (NC): MASt3R/DUSt3R, MVSAnywhere, Inria-3DGS + 2DGS/GOF/RaDe-GS/SuGaR, VGGT-1B Standard. Offen: Nadeln/glatte Daecher loest nachweislich keines.

## 5. Detailtreue (Hebel, 'belegt/erfunden' selbst bauen)
1 Periodizitaet/Symmetrie (Zinnen, Fenster, Quader: aus belegten Instanzen auf Luecken uebertragen, als 'abgeleitet' markieren) - groesster Hebel, keine Lizenzfrage; 2 RANSAC-Ebenen/Zylinder als Belegmass (Inlier-Anteil in den Pruefstand); 3 SAM 2-Bauteilmasken + Mehrbild-Abgleich; 4 2.5D Dual Contouring (MIT) fuer Dach/Zinnen statt PolyFit/City3D (GPL + Gurobi); 5 gelernte Normalen (Marigold; Lizenz pruefen) nur zum Stopfen, immer 'abgeleitet'. Plan: modelle/PLAN_DETAILGETREUE.md.

## 6. Druck H0 und Markt
Harz (MSLA/SLA) Mindestwand 0,6-0,8 mm (Formlabs/Qidi), 0,8 mm Detail im ueblichen Bereich, fuer H0 NICHT belegt -> Probedruck. SLS PA12: Wand 0,6/0,3 mm, Praegung >= 0,15 x 0,35 mm, Entpulverungsloecher >= 3,5 mm. 750 mm Hoehe -> Segmente (Einschaetzung), Nadel als Metallstift (Einschaetzung, ungeprueft). Markt: Faller fuehrt ein Martinstor-Bausatz (130922, ~50 EUR, eBay); Stadttore 35-50 EUR, Burgen 25-150 EUR; kein Foto/Video-zu-H0-Anbieter gefunden (Etsy nicht durchsucht, Zielgruppe angenommen).

## 7. Reihenfolge (jeder Schritt mit Messung/Register-Eintrag)
1. Videostufe am Martinstor messen (laeuft: tools/nullstart.py --videos; mit/ohne Video, gemeinsame Pruefungen).
2. Konsens-Median in `nullstart_beweis.py --auswerten` (Mass + MAD + 'streut').
3. Detailkatalog + `detailbudget.py`; Periodizitaets-/RANSAC-Beleg im Pruefstand.
4. Tiefenprior (DA3) und MapAnything als Test auf dem Martinstor.
5. Zweites Objekt (Burg, nur CC/PD-Daten) als Allgemeingueltigkeits-Test: Sweet-Spot, Massstabsquellen, Lizenzprotokoll.
6. Probedruck Tuermchen+Uhr; Fertigungsbewertung.
7. Anwalt zu den Lizenzfragen, bevor ein Produkt verkauft wird.
Luecken der Recherche: AT/DK/UK/US-Daten, CGAL-/StableNormal-/Lotus-Lizenz, alle VRAM-Zahlen, Bauraum/Teilung, FDM/Multi-Jet-Werte, Shape Grammars, Preise offizieller Hersteller.
