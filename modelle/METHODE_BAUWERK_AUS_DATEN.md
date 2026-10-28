# Methode: echtes Bauwerk → validiertes Modell im echten Gelände (ohne Scan)

Erarbeitet am Ravennaviadukt (Höllentalbahn), 2026-10-26. Kernaussage des Projekts:
**die reproduzierbare Modell-Erzeugung aus Daten ist das Herzstück** — belegt durch
`tools/bauwerk_pipeline.py`, das aus nur den Recherche-Fakten (Name, Lage, Maße)
deterministisch das fertige, validierte, platzierte Modell erzeugt.

## Prinzip
**Kein Scan nötig.** Das Rückgrat ist immer: **Maße (Wikipedia) + OSM-Trasse + LGL-DGM1**.
Ein Scan ist bestenfalls Textur-Vorlage, nie die Geometrie-Quelle (beim Linach-Scan war er
die Falle: nur 2 Bögen, löchrig). Ravenna wurde komplett scan-frei beim ersten echten
Durchlauf als korrekt validiert.

## Die 7 Schritte (= `tools/bauwerk_pipeline.py`)
1. **Lokalisieren** — lat/lon → UTM32 → LGL-2km-Kachel (ungerade-E / gerade-N, SW-Ecke).
2. **Gelände** — DGM1 laden unter `opengeodata.lgl-bw.de/data/dgm/dgm1_32_{E}_{N}_2_bw.zip`
   (Pfad `/data/dgm/`, NICHT `/data/dgm1/`!), 4× 1 km-XYZ → `dgm_xyz_to_npy.py` → north-up npy.
3. **Trasse** — OSM-Overpass `way(around:200,lat,lon)[railway]`, die `bridge=viaduct`-Linie
   → UTM-Polyline. Mehrere Mirror + Retry (öffentliche API ist unzuverlässig).
4. **Modell** — `viadukt_gelaende.py`: folgt der Trasse (Lage/Richtung/Kurve) UND dem
   DGM1-Profil. Grundlinie = Gelände, Deck = Trassen-Gefälle zwischen den Enden, Pfeiler
   variabel hoch, Bögen als shapely-(Weg s, Höhe z)-Löcher → UTM-extrudiert.
5. **Validieren** — `validate_bauwerk.py`: Architektur am geraden Kanon-Modell
   (`ravenna_viadukt.py`) prüfen: richtige Zahl OFFENER Bögen + Durchsicht-Anteil + L:H.
6. **Platzieren** — `bauwerk_szene.py --world --textur granit`: graues Hillshade-Gelände,
   Granit-Textur, Durchsicht-Schieber, zuverlässiges Szenen-HTML.
7. **Beweis** — DOP20-Orthofoto laden, Modell-Trasse drüberlegen: unabhängige Lage-
   Verifikation über eine zweite Datenquelle (Foto statt Vektor).

## Erkenntnisse & Fallen (teuer gelernt, hier festgenagelt)
- **Koordinaten IMMER verifizieren** — erste Ravenna-Lage lag 1,5 km daneben (Wikipedia holen,
  nicht schätzen).
- **Ausrichtung linearer Infrastruktur aus OSM**, nicht aus der DEM-Topografie. Die „max-Dip"-
  Talquerung lag ~50° falsch (nahm die Hangfalllinie). Die OSM-`bridge=viaduct`-Linie gibt
  Azimut + Mittelpunkt + Krümmung + (via DGM1) Längsprofil.
- **Ein flacher, gerader Viadukt trifft zwei unterschiedlich hohe Enden NICHT.** Lösung ist
  nicht die Kurve, sondern **Deck-Gefälle + variable Pfeilerhöhe** (Ravenna: West 754 m,
  Ost 763 m, Sohle 717 m bei s=62 m, nicht mittig).
- **Kurve nur, wenn die Daten sie zeigen.** Ravenna ist laut OSM (7 Segmente alle 107,0°,
  Abweichung 0,01 m) UND laut Orthofoto schnurgerade. Bauchgefühl ≠ Daten.
- **3D-HTML:** three.js-Addons brauchen `<script type=importmap>`, sonst grauer Hintergrund
  (Modell lädt nicht); GLB via `atob` → `GLTFLoader.parse`.
- **Optik:** graues Hillshade-Relief + heller Himmel (sonst „viel schwarz"); Durchsicht-
  Schieber für Gelände + Bauwerk (wie Hirschsprung-Zusammenbau-Tool).
- **Validator-Grenzen:** prüft gerade/gleichhohe Modelle sauber; ein gelände-folgendes,
  diagonales, gegradetes Modell sprengt seine Annahmen → **Architektur am Kanon-Modell**
  validieren, **Lage am Orthofoto**.

## Form-Beweis aus Fotos (`tools/foto_bogen_abgleich.py`)
Die **Form** ist das Entscheidende — ein Modell am richtigen Ort nützt nichts, wenn die
Bogenform falsch ist. Beweis aus echten Fotos (Wikimedia Commons, CC):
- **Bogen-Leibung = Oberkante der dunklen Öffnung** (größte zusammenhängende dunkle
  Komponente). Kreis-Fit daran → Radius R + Leibungsbreite (Spannweite).
- **Stich/Spannweite ≈ 0,50 + kleiner Fit-Fehler = echter Halbkreis** — maßstabsunabhängig
  (lokales Verhältnis, perspektiv-robust). Über eine bekannte reale Spannweite zusätzlich
  Maßstab px→m, um absolute Maße zu prüfen.
- **Ravenna-Ergebnis:** über 4 Bögen Stich/Span = **0,46 ± 0,05** (Modell 0,50), Fit-Fehler
  Ø 3,5 % (bester Bogen 0,7 %); Maßstab aus 20-m-Spannweite → R = 9,3 m ≈ 10 m. Perspektive
  (Panorama von Mitte) erklärt scheinbar größere Mittelbögen bei real gleicher Spannweite.
  Fotos bestätigen außerdem: **Granit-Quadermauerwerk**, variable Pfeilerhöhe + Deck-Gefälle
  (= gelände-folgende Elevation deckt sich mit dem Foto). → **Form in 3D bestätigt.**
- Belege: `daten/ravenna/rv_bogen_abgleich.png`, `rv_arch_fit.png`.

## Generische Dach-Tiefen-Regel (Root-Cause „Dach viel zu lang")
Erlernt am Hotel Oberkirch (Münsterplatz 22, Nachbar des Kaufhauses). Die **LOD2-Bounding-Box
liefert die VOLLE Grundstückstiefe** — Altstadt-Parzellen sind schmal + tief (Oberkirch: Front
9,4 m, Tiefe **15,7 m**; das LOD2-Gebäude hatte 3 Teile, der First 21 m gilt für das tiefe
Gesamtdach). Baut man ein traufständiges Satteldach über die volle Tiefe, erreicht es zwar echt
den First, sieht aber **freistehend wie eine lange Rampe** aus — real steckt das tiefe Dach
zwischen den Nachbarn, vom Platz sieht man nur die (perspektivisch verkürzte) Vorderschräge.
**Fix (generisch in `tools/bauwerk_generator.py`):** echte Neigung aus LOD2 ableiten
`pitch = atan2(first−traufe, tiefe/2)` → modellierte Tiefe auf eine **Straßenfront-Tiefe** kappen
(Default ≈ Fassadenbreite) → First aus `(pitch, gekappte Tiefe)` NEU. Die zur Straße zeigende
Schräge behält ihren echten Winkel. Oberkirch: Tiefe 15,7→9,4 m, First 21,0→17,4 m,
Dachanteil 44→32 % (= nahe der Foto-Impression). Gegenstück zur Frontfoto-Verkürzung (die
Masse-Höhe bleibt LOD2-fest; nur die freistehende Tiefen-Darstellung wird gekappt).

## Generischer Bauwerkgenerator (`tools/bauwerk_generator.py`)
Config-getriebene Engine für Straßenfront-Altstadthäuser: das Gebäude ist eine JSON-Konfig
(`bauwerke/<name>.json`) aus Masse + Stückzahlen + Feature-Flags; die Engine baut nur aktivierte
Elemente. Generische Bausteine: Putzfassade-Raster, **reiche Fenster** (Rahmen + Sprossen
`cols×rows` + Sohlbank), Lamellenläden, Blumenkästen, EG-Modul (Tür + Bogen-Schaufenster +
Schriftband + Wappen + Laternen, Positionen per `x_frac`), Traufgesims + Sockelband,
traufständiges Satteldach mit obiger Tiefen-Regel, Gauben/Dachluken/Schornsteine, Hero-Ausleger.
Erst-Beleg: `bauwerke/hotel_oberkirch.json`. (Ornamentgebäude wie das Kaufhaus mit Arkade/Erker/
Statuen bleiben vorerst im Spezialgenerator `kaufhaus_measured.py`.)

## Beweis der Reproduzierbarkeit
`python3 tools/bauwerk_pipeline.py --config ravenna --out /tmp/ravenna_zero` läuft aus leerem
Ordner durch alle 7 Schritte → **Validierung PASS** (9 Bögen, L:H 6,0). Die live aus OSM
geholte Trasse ist **0,000 m** identisch zur zuvor manuell ermittelten; das Deliverable-Mesh
deckungsgleich. D.h. die Methodik (nicht nur das Einzelergebnis) ist deterministisch
reproduzierbar und skaliert per Config auf jedes BW-Bauwerk.
