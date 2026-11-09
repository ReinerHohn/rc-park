# LOG Koerper v9: Fenster- und Erkerfamilie aus dem Kantengitter – 2026-11-09 (Agent, Werkzeug `tools/koerper_fenster_erker.py`)

Ziel: der Rohkoerper v7 (`gitter_koerper.py`) bekommt die Details, die das Kaufhaus ausmachen: Obergeschoss-Fenster (Vorhangbogen, Pfosten, Kaempfer) und beide Erker (Polygon, Fensterkranz, Untersicht, Schaft, Helm) als parametrische Koerper AUS dem Gitter, Anzahl/Lage nur mit Fotobeleg (Regel 9).
Eingaben: `kette_video/gitter.json` (2934 Segmente, helme LEER, 7 Saeulen), `koerper/rohkoerper_v7.json/.stl`, Helm aus `segmente_gitter_v7.json` (Wolkenfit, 1 Helm), Wolke `kanten3d_k80.npz`, Kameras `sfm/kam_lot2.json`, Stabilitaetskarten `stabil/` (882 Fotos).
Keine Objektkonstanten: Rahmen (u, n, Front 12,66), Balkonoberkante (Vorsprung z_max_voll 10,0) und Traufe (14,61) aus rohkoerper_v7.json; alle Fenster-/Erkermasse aus dem Gitter.

## Aufrufe
```
/media/oem/scan/venv-seg/bin/python -I tools/koerper_fenster_erker.py analyse kette_video/gitter.json koerper/rohkoerper_v7.json sfm/kam_lot2.json stabil koerper/fenster_erker_v9.json --helme segmente_gitter_v7.json   # ~1 min, GPU
~/.venvs/rcpark/bin/python tools/koerper_fenster_erker.py bauen koerper/fenster_erker_v9.json koerper/rohkoerper_v7.stl koerper/koerper_v9.stl      # 2 s
/media/oem/scan/venv-seg/bin/python -I tools/koerper_fenster_erker.py pruefen koerper/koerper_v9.stl koerper/fenster_erker_v9.json kanten3d_k80.npz sfm/kam_lot2.json bilder modelle/kaufhaus_grob3/audit/koerper_v9   # ~3 min
```

## 1 Fensterfamilie (Hauptfassade, Band z 10,0..14,61)
Rohbild `audit/koerper_v9/aufriss_fensterband_roh.jpg`: 5 "Haus"-Formen im Frontband, dazwischen kurze Steiger (Figurenkonsolen).
- Pfosten (vertikale Kanten |Offset-Front| < 0,5, 1D-RANSAC 6 cm): 12 Cluster, davon 5 Paare mit Abstand 0,91 m und z bis 13,4 (Mittellicht) bei along **-4,45 / -0,51 / 3,47 / 7,46 / 11,39**, Periode **3,96 m**.
- Horizontale: Kaempfer **11,72** (70 m Kantenlaenge, staerkste), Schulter **12,25** (32 m), Scheitel **13,31** (29 m), Gesims 14,34 (51 m). Sohlbank = Pfostenfuss **10,31**.
- Rahmenbreite aus Doppelkanten (Median benachbarter Horizontalcluster 6-30 cm): **0,147 m**.
- Bekroenung: Hoehenprofil der schraegen Kanten ueber |x - Gruppenmitte| (alle 5 Gruppen uebereinander, 75 %-Quantil): 13,3 bis |dx| 0,45, dann fallend bis 12,55 bei 1,35 -> Vorhangbogen ueber Mittellicht + abfallende Schultern ueber den Seitenlichtern (wie im Foto ip_IMG_6120).
- Lichter je Gruppe: Aussenpfosten (+-1,5 Lichtbreiten) nur 1 von 10 im Gitter -> **3 Lichter = ANNAHME aus dem Gitter**, aber die Rahmensegmente mit Aussenpfosten sind in >= 82 Fotos auf Kanten (Fotobeleg unten) und im Foto 6120 sind 3 Lichter je Gruppe zu sehen.
- **Fotobeleg je Gruppe** (Rahmensegmente gegen Stabilitaetskarten, 24 Punkte/Segment, >= 50 % auf Kante, Kamera < 45 m): ja-Minimum 82-106 Fotos, ja-Median 115-142, nein-Median 58-105 -> **5 von 5 Gruppen BELEGT** (Kriterium: jedes Rahmensegment >= 3 Fotos, Median ja >= Median nein).
- Gleichheitsregel (Median, Abweichung je Gruppe): Lichtbreite -0,012..+0,007 m; Scheitel -0,05..+0,12 m; Sohl -0,03..+0,17 m (Gruppe 3). Alle gebaut mit Medianmassen.
- **Zaehlung Gitter 5 Gruppen x 3 Lichter = 15 Fenster; Foto (c_12, 6120 angesehen): 5 Gruppen x 3 Lichter zwischen/neben den 4 Figuren = 15.** Stimmt.
Koerper je Licht: Oeffnung 10 cm tief (ANNAHME) mit Bekroenungsprofil als Oberkante, Mittelpfosten + Kaempfer als Stege 0,147 m breit, 2 cm hinter der Flaeche bis in die Wand. Der Rahmenring selbst liegt in der Wandflaeche (buendig, nicht sichtbar) - der Vorhangbogen traegt die Form.

## 2 Erkerfamilie
Rohbild `audit/koerper_v9/grundriss_erker_roh.jpg`; vertikale Kanten vor der Front (> 0,25 m), Fuss ueber Balkonoberkante, 2D-Cluster (along, Offset) Radius 15 cm:
- Erker links: 7 Pfosten (along -10,02..-7,03; vor Front 0,27/0,70/1,12/1,18/1,15/0,72/0,31) -> Mitte **-8,35**, Tiefe **1,18 m**, Frontflaeche +-0,81 (Pfosten -9,16/-8,52/-7,89 = 2 Lichter), Schraegflaechen 44 Grad bis Wandanschluss +-1,87, Lichtbreite in der Flaeche 0,64.
- Erker rechts: 8 Pfosten (14,10..17,11) -> Mitte **15,67**, Tiefe 1,18, Front +-0,68, Schraege 40 Grad, Wand +-1,86, Lichtbreite 0,62.
- Hoehen (horizontale Erkerkanten): unten **9,61**, Sohl 10,15-10,21, Kaempfer **11,36**, Schulter **12,33**, oben (Gesims) **13,17**.
- Spiegelregel: Abweichung beider Erker vom Median <= 6 cm (x_front +-0,06, Lichtbreite +-0,01, Hoehen <= 3 cm) -> beide mit Medianmassen gebaut (Wand +-1,87, Front +-0,74, Tiefe 1,18, z 9,62..13,18). Symmetrieachse aus den Erkern along **3,66**, Fenstergruppenmitte 3,47 (Differenz 0,19 m).
- Fotobeleg (Frontpfosten, Unter-/Oberkante): links ja-min 57 / Median 113, rechts 57 / 86 -> **beide BELEGT**.
- Fensterkranz: je Flaeche round(Laenge/Lichtbreite) Lichter -> 2 + 2 + 2 (Foto nu_9e1944: 2 + 2 + 2, stimmt), kleiner Vorhangbogen 25 cm ueber der Schulter (ANNAHME), Kaempfer 11,36.
- Untersicht: Huelle Erkerpolygon (z 9,62) -> Wandlinie +-0,4 m auf z 7,7 (Balkonunterkante 8,0 - 0,3; ANNAHME). Dachring: Polygon + 0,147 m, 0,27 m hoch an der Oberkante (ANNAHME).
- Helm: gitter.json hat KEINE Helme (Kette "Helme 0"); genommen aus segmente_gitter_v7.json (Wolkenfit): along 15,54 / Offset 12,26 / Fuss 15,27 / Spitze 22,44 / r 0,86 / 16 Sektoren - steckt schon im Rohkoerper. Schaft = Huelle Erkerpolygon (13,13) -> Helmkreis 0,97 r auf 15,37.
  **Zweiter Helm links = Spiegel an der Erkerachse 3,66 -> along -8,23 (ANNAHME)**; Gratkanten in 47-106 Fotos auf Kanten (nein 89-156) -> fotobelegt im Sinne >= 3 Fotos, aber mehr Nein als Ja (ferne/unscharfe Videoframes) - bleibt ANNAHME mit Fotostuetze.

## 3 Zusammenbau
Rohkoerper-STL -> manifold3d (Status NoError) - 15 Oeffnungen + 30 Stege + 2 Erker (je Polygonkoerper, Untersicht, Ring, Schaft[, Helm], - 6 Oeffnungen + 12 Stege).
Export `koerper/koerper_v9.stl` + `.ply` (indiziert) + `koerper_v9_h0.stl` (1:87, BBox 361,5 x 323,9 x 299,0 mm): **4180 Dreiecke, wasserdicht JA** (manifold-Netz, UND STL-Roundtrip + merge_vertices: 1 Koerper, Euler 2), Volumen 9200,5 m^3 (v7: 9168,2).
Pannen auf dem Weg (alle Boolesche Koinzidenzen, nach dem Rohkoerper-Log eigentlich bekannt):
1. Erkerpolygon-Kante genau auf der Frontflaeche + Erkerunterkante 9,62 im Balkonkasten (z 8-10) + Trichterspitze genau auf der Balkonunterkante 8,0 -> nach STL-Roundtrip 32 offene Kanten. Loesung: Wandanschluss 2 cm in der Wand, Trichterspitze 30 cm tiefer.
2. Huellen (Untersicht/Schaft) mit demselben Polygon wie der Erkerkoerper -> koplanare Seitenflaechen -> doppelte Scheitel. Loesung: Polygon 2 cm nach innen.
3. Mittelpfosten-Steg endete exakt auf dem Scheitel der Oeffnung -> doppelte Positionen (41) -> Steg 2 cm ueber den Scheitel.
4. `trimesh.nondegenerate_faces` entfernen macht ein manifold-Netz UNDICHT (Splitter-Dreiecke halten die Topologie) - nie anwenden; stattdessen indiziertes Netz direkt aus manifold exportieren (.ply) und Koinzidenzen an der Quelle vermeiden.

## 4 Pruefung (`koerper/koerper_v9_pruefung.json`, Bilder `modelle/kaufhaus_grob3/audit/koerper_v9/`)
Wolke -> Oberflaeche (3 Mio Punkte, GPU knn), Vergleich v7 -> v9: gesamt < 20 cm **49,8 % -> 55,4 %**, Median 0,20 -> 0,16 m.

| z-Band | v7 <20cm | v9 <20cm | v9 <50cm | v7 Median | v9 Median |
|---|---|---|---|---|---|
| 9-11 | 0,57 | **0,72** | 0,86 | 0,15 | 0,11 |
| 11-13 (Fenster/Erker) | 0,47 | **0,72** | 0,95 | 0,23 | **0,08** |
| 13-15 | 0,56 | **0,66** | 0,89 | 0,15 | 0,10 |
| 15-17 (Erkertuerme) | 0,57-0,68 | 0,68 | 0,77 | 0,09-0,16 | 0,09 |
| uebrige Baender | unveraendert | | | | |

Sichtbefund (Regel 9b, Teil neben Fotoausschnitt: links Foto, Mitte Modell aus der Fotokamera, rechts Netzkanten-Overlay):
- `vergleich_ip_IMG_6120.jpg` (Fenster nah): die drei sichtbaren Gruppen liegen auf den echten Fenstern (Pfosten, Kaempferlinie, Vorhangbogen ueber dem Mittellicht, abfallende Schultern), Sohlbank knapp ueber der Balustrade wie im Foto. Fehlt: Figuren+Konsolen+Baldachine zwischen den Gruppen, Balustrade (Balkon ist glatter Kasten), Fensterrahmen-Vorsprung (buendig), Masswerk in den Lichtern.
- `vergleich_an_handy_2026-11-06_c_handy_c_12.jpg` (ganzes Haus): 5 Gruppen x 3 Lichter an den richtigen Stellen zwischen den Figuren, beide Erker mit Helm an den richtigen Stellen (links jetzt vorhanden, war im Rohkoerper leer), Dach/Giebel wie v7.
- `vergleich_erker1_nu_9e1944dc-image.jpg` / `vergleich_erker0_..c_12.jpg` (Erker nah): Polygon (Front 2 Lichter, Schraegen 2 Lichter), Kaempfer-, Schulter-, Gesimshoehe decken sich mit dem Foto; Untersicht als Trichter plausibel. **Fehler**: Erker im Overlay ~0,3-0,5 m zu weit aussen (zur Gebaeudeecke) - Mitte aus laengengewichtetem Mittel der Pfosten (-8,35/15,67) statt aus dem Frontpfosten-Paar (-8,52/15,59); Helm/Schaft ueber dem Erker sitzt als breite Pyramide direkt auf dem Gesims, das echte Tuermchen hat einen hoeheren senkrechten Schaft und einen steileren, hoeheren Helm (Spitze im Fit zu tief, schon im v7-Log). Dachring ok.
- `render_vorn.jpg`, `render_schraeg.jpg`, `render_schraeg2.jpg`: 5 Gruppen, 2 Erker mit Helmen, Arkaden, Staffelgiebel. Rueckseite leer (ANNAHME v7).
- `overlay_ip_IMG_6261.jpg`, `overlay_ip_IMG_6120.jpg`: Netzkanten (Dieder > 30 Grad, 2635 Segmente, `koerper_v9_kanten.json`) auf den Fotos.
- **Widerspruch offen (nicht gemittelt, Regel 5)**: Erker-Wandanschluss links -10,22 / rechts 17,54 ragt ueber die Rohkoerper-Enden (-8,82 / 17,15) hinaus (1,4 bzw. 0,4 m). Erker und Fenstergruppen sind symmetrisch um along 3,5-3,7; die Enden um 4,16. Im Foto sitzt der Erker in der Gebaeudeecke, also sind eher die Endebenen des Rohkoerpers (links um ~1,4 m zu weit innen?) oder die Schraegen-Extrapolation (x_wand) falsch. Naechster Schritt: Endebenen am Foto pruefen (Overlay zeigt dort den Giebel), x_wand aus den aeussersten Pfosten (0,27-0,31 vor der Front) statt aus der Geradenextrapolation.

## Annahmen (in `fenster_erker_v9.json` -> `annahmen`)
Oeffnungstiefe 10 cm, Rahmentiefe 15 cm, Stege 2 cm hinter der Flaeche; 3 Lichter je Gruppe (Aussenpfosten im Gitter fehlen, Foto zeigt 3); Erker-Untersicht Trichter bis 30 cm unter die Balkonunterkante; Erkerschaft = Huelle Polygon -> Helmkreis; Dachring 0,27 m; Erkerfenster-Vorhangbogen 25 cm; zweiter Helm = Spiegel des Wolken-Helms an der Erkerachse.

## Offen / naechste Schritte
- Erkermitte aus dem Frontpfosten-Paar, Wandanschluss aus den aeussersten Pfosten; Endebenen-Konflikt klaeren (s.o.).
- Helm: Schaft als senkrechtes 16-Eck bis ueber die Traufe, Spitze neu messen (Foto-Silhouette), kein Pyramidenansatz direkt auf dem Erkergesims.
- Figuren/Konsolen/Baldachine (4 Steiger zwischen den Gruppen im Gitter sichtbar, z 11,5-12,5), Balustrade, Dachgauben (3 + 2 im Foto), Fensterrahmen mit Vorsprung fuer den Druck (buendige Rahmen sind bei 1:87 unsichtbar).
- Pruefstand-Sollwerte: Fenstergruppen 5 x 3 (Zaehlung am Foto `foto_zaehlung.py` noch nicht als Z-Protokoll), Periode 3,96, Kaempfer 11,72, Scheitel 13,31, Erker Tiefe 1,18 / Mitte -8,5 / 15,6.

---
# Abschnitt v10 (Runde 2, Agent, Werkzeug `tools/koerper_v10.py`; baut auf gitter_koerper.baue + koerper_fenster_erker auf)

Aufrufe:
```
~/.venvs/rcpark/bin/python tools/koerper_v10.py bauen kette_video/gitter.json koerper/rohkoerper_v7.json koerper/fenster_erker_v9.json formen/helme.json koerper      # 3 s
/media/oem/scan/venv-seg/bin/python -I tools/koerper_v10.py pruefen koerper kanten3d_k80.npz sfm/kam_lot2.json bilder modelle/kaufhaus_grob3/audit/koerper_v10          # 3 min
```
Ausgaben: `koerper/rohkoerper_v10.json` (Historie-Eintrag, Enden/Giebel korrigiert), `koerper/koerper_v10.json` (alle Teile + Annahmen + Log), `koerper_v10.stl/.ply/_h0.stl`, `koerper_v10_pruefung.json`, `koerper_v10_dicke.json`, Bilder `modelle/kaufhaus_grob3/audit/koerper_v10/`.

## 1 Erkerlage und Enden
- Erkermitte aus dem aeussersten Frontpfosten-Paar: links -8,35 -> **-8,52**, rechts 15,67 -> **15,59**; Erkerachse **3,53** (Fenstergruppenmitte 3,47). Die Arkadenpfeiler (saeulen, in along umgerechnet: -8,53 / -2,51 / 3,50 / 9,51 / 15,56, Abstand 6,0 m) stehen genau unter den Erkermitten und sind um 3,50 symmetrisch - drei unabhaengige Merkmale, eine Achse.
- Giebelebenen = Paar der hohen Endebenen (z_max > Traufe + 3 m), dessen Mitte der Erkerachse am naechsten liegt: **-8,82 (37 m, belegt, z bis 26,7) / 15,85 (33 m, belegt, z bis 23,5)**, Mitte 3,52 (v7: -8,82 / 17,15; die v7-Ebene 17,15 reicht nur z 7,9-15,6 = Seitenflaeche des rechten Erkers, kein Giebel).
- Widerspruch Erker-Wandanschluss (-10,39 / 17,46) vs Giebelebenen aufgeloest durch Ansehen von c_12 / 6261: die Erkertuerme stehen in der Gebaeudeecke, der Staffelgiebel sitzt dazwischen, der Turm steht halb vor der Giebelebene. Gebaut: Dach + Giebel along -8,82..15,85, **unterer Rumpf (Boden..Traufe, Front bis Laubenrueckwand) bis zu den Erker-Wandanschluessen verlaengert (ANNAHME)**; Endbogen der Laube in den Giebelwaenden nicht gebaut.

## 2 Staffelgiebel beide Enden
- ende_minus (-8,82): 10 Steiger, 7 als Treppe (Offset 12,76 -> 5,22, z 16,5 -> 27,4) -> Treppenpolygon.
- ende_plus (15,85): 10 Steiger, aber nur 2 monoton - die vertikalen Kanten dort (along 15,3-15,5, Offset 12,0-12,3, z 16-22,9) sind der Erkerturm, keine Stufen -> **Treppe = Spiegel von ende_minus (ANNAHME)**. Fotopruefung 6261: die gespiegelten Stufen liegen im Overlay auf den echten Stufen des nahen Giebels (im Bild links); c_12: beide Giebel mit Zacken an den richtigen Stellen.

## 3 Erkertuerme
- Senkrechter Schaft = Erkerpolygon von 9,62 bis zum Helmfuss (links 14,67, rechts 15,09); Helme = Pyramiden aus `formen/helme.json` (klein along -8,56 / Offset 12,22, Fuss 14,67, Spitze 22,34, r 0,84; gross 15,53 / 12,23, Fuss 15,09, Spitze 22,78, r 0,85; Fototest dort bestanden). Der gespiegelte v7-Helm ist raus.
- Helmachsen liegen 0,44 m HINTER der Front (Erkerpolygon-Schwerpunkt 0,5 m davor) -> Uebergang Schaftpolygon -> Helmquerschnitt 0,6 m ueber dem Fuss als Huelle (ANNAHME), sonst bliebe ein Absatz von 0,8 m.
- Sichtbefund `vergleich_erker1_nu_9e1944dc-image.jpg`: Erker liegt jetzt deckungsgleich auf dem Foto (Kanten links/rechts, Gesims, Lichter 2+2+2, Kaempfer). Schaft ueber dem Gesims im Modell ~1,9 m hoch, im Foto beginnt der Helm ~1 m ueber dem Gesims und ist am Fuss so breit wie der Erker (~3 m) - der Wolkenfit-Radius 0,85 (1,7 m) ist etwa halb so breit; die Huelle kaschiert das. Offen: Helmfuss-Radius und -hoehe am Foto messen (foto_mass), Fit-Grenzen pruefen (Regel 9c a).

## 4 Balkon, Konsolen, Figuren
- Balkon-Horizontale vor der Front (Band 7-10,2): Platte 8,16 / **8,29 (24 m)** / 8,37, vor 1,22-1,40; Handlauf 9,48 / **9,55 (22 m, vor 0,95-1,06)** / 9,66 (14 m, vor 1,21-1,29).
  Gebaut: Platte z 8,16-8,37, Tiefe 1,40, along zwischen den Erker-Wandanschluessen; Handlauf z 9,48-9,71, vor 0,95-1,29, bis 0,8 m an die Erkermitten (dort trifft er die Schraegflaechen, sonst schwebte er - erster Bau: 2 Koerper).
- **Baluster NICHT gebaut (offen)**: `formen/baluster.json` (quelle 13, 97 Instanzen) traegt den eigenen Hinweis "UNVERIFIZIERT ... automatischer Kantentest nicht bestanden"; `gitter_v7_formen2.json` existiert nicht. Folge: Band 7-9 verschlechtert sich (v9 Kasten 0,58 -> v10 0,46 < 20 cm, Median 0,14 -> 0,25), weil der v7-Balkonkasten (z 8-10) weg ist und die Balusterpunkte der Wolke jetzt keine Flaeche haben. Handlauf haengt nur an den Erkern (Druck: Stuetze noetig).
- Konsolen: Kantencluster unter der Platte (z 6,5-8,3, alle Quellen) -> **5 Bloecke** along -1,17 / 0,63 / 1,79 / 5,95 / 7,80 (0,45 breit, Tiefe Platte - 0,15). Foto 6120: 3 Konsolen je Joch (~15) - Gitter liefert nur 5, Rest offen (Regel 9: nicht erfinden).
- Figurenkonsolen/Baldachine: 4 Kantencluster zwischen den Fenstergruppen (along **-2,28 / 1,55 / 5,48 / 9,52**, 12-35 m Kanten, z 10,6-14,4, Tiefe 0,5-0,56, Breite 0,4-0,53) -> Quader je Position (ANNAHME Form). Foto c_12: 4 Figuren zwischen den 5 Gruppen - Anzahl stimmt; Lage im Overlay 6120 auf den Figuren.

## 5 Pruefung
- **Wasserdicht**: manifold-Netz (.ply, indiziert) JA, 1 Koerper, Genus 1 (= der Ring Handlauf-Erker-Platte-Erker, erwartet). **STL-Roundtrip mit Positions-Merge: NEIN** - 6 offene Kanten, alle an den Giebelebenen (along -8,82 / 15,85, Front, z 1,5 und 7,73): Huellen-Eckkante der Rumpf-Extrusion liegt in der koplanaren Front-/Bodenflaeche des Verlaengerungskastens bzw. wird vom Erker-Trichter geschnitten -> doppelte Positionen (4). Versuch "Kasten 2 cm hinter die Front" machte es schlechter (13 Koerper) - zurueckgenommen. Offen: Rumpf und Verlaengerung als EIN Querschnitt extrudieren (wie v7-Lehre 3). Slicer (Bambu Studio) repariert solche Doppelpunkte i.d.R.; vor dem Druck pruefen.
- Volumen 8953,7 m^3 (v9 9200,8: Balkonkasten weg, Ende plus 1,3 m kuerzer), 4418 Dreiecke, 2905 Netzkanten.
- Wolkennaehe (< 20 cm / Median) v9 -> v10: gesamt 55,4 % -> 54,6 % (0,16 m); **11-13: 0,72 -> 0,83 (0,06)**, **13-15: 0,66 -> 0,75**, 15-17: 0,68 -> 0,72, 17-19: 0,59 -> 0,70, 19-23: 0,63-0,72 -> 0,73-0,81, 23-27: 0,85 -> 0,88-0,90 (Giebel beide Enden); **7-9: 0,58 -> 0,46** (Baluster fehlen); 9-11: 0,72 -> 0,67 (Kasten weg).
- Mindestdicke H0 (`koerper_v10_dicke.json`, trimesh max_sphere an 4000 Oberflaechenpunkten): min 0,006 mm, 1 %-Quantil 0,32 mm, 5 %-Quantil 1,6 mm, 1,4 % der Punkte < 0,4 mm. Die duennen Punkte liegen an konvexen Kanten/Ecken (Erkerunterkante z 9,62, Handlauf-Vorderkante z 9,48, Bodenecken) = Artefakt der Kugelmethode an Kanten, keine duenne Wand. Entwurfsmasse: Stege/Rahmenbreite **1,69 mm**, Oeffnungstiefe 1,15 mm, Handlauf 2,7 mm hoch x 3,9 mm tief, Platte 2,5 mm, Konsolen 5,2 mm, Figurenbloecke 4,6-6 mm, Giebelwand 6,0 mm, Helmspitzen laufen spitz zu (Slicer rundet). Keine Entwurfsdicke unter 0,4 mm; schmalste Stege 1,7 mm > 0,4 mm P1S.
- Sichtbefund (`vergleich_*.jpg`, Foto | Modell aus Fotokamera | Kanten-Overlay):
  - c_12: beide Staffelgiebel, beide Tuerme, 5 x 3 Fenster, 4 Figurenbloecke, Balkonplatte/Handlauf an den richtigen Stellen; rechter Giebel jetzt am Foto-Giebel (v7/v9 1,3 m zu weit aussen).
  - 6261: naher Staffelgiebel deckt die echten Stufen (gespiegelt!), ferner Turm/Giebel passen; Verlaengerungskasten unter dem nahen Turm deckt die Eckwand im Foto.
  - 6120: Figurenbloecke auf den drei Figuren, Konsolen nur an 2 der ~6 sichtbaren Stellen, Handlauf ohne Baluster (sichtbare Luecke), Fenster wie v9.
  - Erker nah: deckungsgleich, Helm s.o.
  - Fehler/offen: Balustrade fehlt (groesster Wolkenverlust), Konsolenzahl, Helmfuss zu schmal/Schaft zu hoch, Laubenendboegen, Gauben (3 + 2 im Foto, gauben_v9.json vorhanden, nicht eingebaut), Rueckseite leer, STL-Roundtrip-Doppelpunkte an den Giebelebenen.

## Annahmen v10 (zusaetzlich zu v9, in `koerper_v10.json` -> `annahmen`)
Unterer Rumpf bis Erker-Wandanschluesse; Staffelgiebel ende_plus = Spiegel; Figur+Konsole+Baldachin = Quader; Konsolen 0,45 m / Tiefe Platte-0,15; Erkerschaft bis Helmfuss + Huelle 0,6 m; Plattendicke/Handlaufhoehe aus Kantenpaaren (hier belegt: 8,16/8,37 und 9,48/9,66).

---
# Abschnitt v11 (Runde 3, Agent; Nutzerbefund "offene Laube" hatte Vorrang) - `tools/koerper_v11.py`, `tools/flaeche_oder_oeffnung.py`, `tools/koerper_kette.sh`

## Nutzerbefund: Erdgeschoss ist eine offene Laube, nicht Tunnel in einer Wand - generisch abgeleitet (Regel "Flaeche vs. Oeffnung")
`tools/flaeche_oder_oeffnung.py WOLKE KAM ROH.json KOERPER_v10.json AUS.json` (GPU): je Flaechenhypothese Raster 0,5 m; je Zelle Wolkenpunkte AUF der Flaeche (|d| < 15 cm) gegen Punkte
HINTER der Flaeche (bis 8 m), deren Sehstrahl von einer Kamera VOR der Flaeche (< 45 m) die Zelle durchstoesst. hinter/auf > 3 (und hinter >= 3) -> Oeffnung; auf >= 3 und <= 3 -> Wand; sonst unentschieden.
**ANNAHME Sichtbarkeit**: kanten3d_k80 traegt keine Kamera je Punkt (vis/kan = Stimmzahlen), daher zaehlt jeder Punkt 1 Stimme, verteilt auf alle Kameras vor der Flaeche. Ergebnis (`koerper/flaechen_eg_v11.json`, Textbilder im Lauf-Log):
- **Front EG** (339 Kameras, 212k auf / 822k hinter): 64 % Oeffnung, 36 % Wand, 0 % unentschieden. Das Textbild zeigt 5 Pfeiler als Wandsaeulen, 4 Bogenoeffnungen mit nach oben schmaler werdendem Querschnitt, Bogenzwickel z 7-7,5 als Wand. Joche (Anteil Oeffnungszellen unter z 7): 0,84 / 0,85 / 0,77 / 0,78 -> offen; Endjoche -9,9..-9,0: 0,59, 16,0..16,9: 0,58 -> offen (knapp).
- **Rueckwand Laube** (436 Kameras, nur 3,9k auf / 24k hinter): 82 % unentschieden (Kantenwolke sieht die Wandflaeche kaum, wenige Kameras innen), 11 % Wand, 8 % Oeffnung; eine Komponente along -8,9..-3,9 z 4-8 (hinter/auf 496/0) -> als Nische 0,3 m gebaut (ANNAHME Tiefe). Tueren/Fenster der Rueckwand NICHT erkannt (Test unentschieden) - offen.
- **Stirnwaende** (60/51 Kameras, nur 207/2479 Punkte auf, 475k/550k hinter): 89 % / 76 % Oeffnung - aber unglaubwuerdig hoch: die "hinter"-Punkte sind das Laubeninnere, das durch die FRONTboegen gesehen wurde; ohne Kamera-Zuordnung je Punkt kreuzen die Strahlen der Seitenkameras die Stirnflaeche. Gebaut: Seitenbogen (Masse wie Reihenboegen, Scheitel 7,20) als **ANNAHME**, Stirnwand sonst Wand.
Lehre: der Test funktioniert dort, wo Kameras in grosser Zahl frontal stehen (Front EG); fuer Rueckwand/Stirn braucht er die Kamera-Zuordnung je Punkt (kanten_3d_vote muesste Bild-IDs mitschreiben).

## Bau v11
- Rumpf = EIN L-Querschnitt (Obergeschoss+Dach ab Laubendecke 8,13 = Plattenunterkante, Bogenbalken in Pfeilertiefe 0,88 ab Kaempfer 4,44 - 2 cm, Hinterhaus Rueckwand 6,54..Rueckseite) ueber die volle Laenge -10,39..17,46; oberhalb der Traufe hinter den Giebelebenen -8,82/15,85 abgeschnitten (Schnitt 2 cm ueber der Traufkante). Keine koplanaren Naehte mehr.
- Pfeiler: 5 Zylinder R 0,44 (saeulen Hauptlinie) Boden..Kaempfer, Kapitellblock 0,2 m (ANNAHME). Boegen: R 2,76, Mittelpunkt z 4,44 aus `kurven/arkaden.json` (rund, 4/4), Segmentbogen ueber lichte Weite 5,1 m; Endjoche Halbkreis ueber die Restweite (ANNAHME). Laubendecke flach (ANNAHME, Gewoelbe offen).
- Staffelgiebel beide Enden (ende_plus Spiegel, ANNAHME), Fenster 5x3, Figurenbloecke 4, Erker mit Schaft + Helmen (formen/helme.json) wie v10.
- **Baluster**: `formen/baluster_abgenommen.json` (Zaehlprotokoll Z-6120-001, 11 je Flaeche, Periode 0,306, Profil r 0,072): **67 Zylinder** zwischen Platte (8,35) und Handlauf (9,50), r 0,072 = 1,65 mm bei 1:87 (> 0,6 mm, keine druckbedingte Anhebung noetig).
- **Konsolen** (`koerper_v11.py analyse_konsolen` -> `konsolen_v11.json`): Periode = Pfeilerabstand/3 = **2,005 m**, Phase 1,79, 3 von 5 Gitterbloecken Inlier (Residuen -0,96/+0,85 = die beiden Bloecke -1,17/0,63 passen nicht ins Raster -> ersetzt durch Rasterpositionen; Beobachtung offen). 10 Konsolen zwischen den Erkern: 3 Gitterbloecke + **7 per Foto belegt** (10-40 Fotos ja; nein-Zahlen 118-188 = ferne Videoframes), 0 reine ANNAHME. Foto 6120 zeigt 3 je Joch - Raster stimmt.
- Helmfuss/Schaft: Sichtschaetzung am Ausschnitt `vergleich_erker1_nu_9e1944dc-image.jpg` (kein foto_mass-Protokoll, keine Kalibrierpunkte gesetzt): Helmfussbreite ~0,85-0,9 Erkerbreiten (3,74 m) = 3,2-3,4 m (r 1,6-1,7), Schafthoehe ueber Gesims ~0,25 Erkerbreiten = ~0,9 m. Wolkenfit: r 0,84/0,85, Schaft 1,5/1,9 m, k = 0,11; helm_fit-Grenze KMAX 0,25 (r <= 1,9 bei 7,7 m Hoehe) ist NICHT bindend - der Fit hat den Fuss aus den Wolkenpunkten so bestimmt (belegung_scheiben unter z 15,7 nur 0,2-0,5). **Offene Beobachtung, nicht gemittelt**: Foto sagt Helmfuss ~2x breiter als der Fit; naechster Schritt foto_mass an c_12/9e1944 mit Erkerbreite als Massstab.

## Gate und Pruefung v11 (`koerper_v11_pruefung.json`, `koerper_v11_slicer_vorcheck.json`, Bilder `audit/koerper_v11/`)
- **GATE bestanden**: manifold-Netz wasserdicht, STL-Roundtrip + merge_vertices wasserdicht, **0 offene Kanten, 0 doppelte Positionen, 1 Koerper**, Genus 68 (= 67 Balusterschleifen + Handlaufring). 9264 Dreiecke, Volumen 9122 m^3, H0 377,2 x 325,7 x 299,0 mm.
  Weg dorthin: 49 offene Kanten (Huelle/Balken/Hinterhaus koplanar) -> L-Querschnitt: 4 -> Endjoch-Bogen 2 cm von der Stirnwand-Innenseite: 0.
- Wolkennaehe < 20 cm (v10 -> v11): gesamt 54,6 -> **58,9 %**, Median 0,16 -> 0,12 m; 7-9: 0,46 -> **0,60** (Baluster), 9-11: 0,67 -> 0,78, 5-7: 0,53 -> 0,59, 11-15 wie v10 (0,82/0,75); **1-3: 0,19 -> 0,10 (Median 0,85 -> 1,50), 3-5: 0,47 -> 0,47 (<50 cm 0,68 -> 0,56)**: die Laube ist jetzt offen, die Tunnelwaende (falsch, aber nah an Innenpunkten) sind weg; Innenraum (Gewoelbe, Rueckwandtueren, Boden, Passanten) nicht modelliert.
- Slicer-Vorcheck: Ueberhaenge > 60 Grad 198 m^2 = 5,8 % der Flaeche (Laubendecke 8,13 ueber 6 m Tiefe, Balkonplatten-Unterseite, Erker-Trichter, Helm-Huellen, Kapitelle) - die Laubendecke ist beim Druck eine Bruecke ueber 6,1 m/87 = 70 mm, braucht Stuetzen; Mindeststege: Fenster-Stege 1,69 mm, Baluster 1,65 mm, Oeffnungstiefe 1,15 mm, Handlauf 2,7 mm, Platte 2,5 mm, Konsolen 5,2 mm, Giebelwand 6,0 mm -> nichts unter 0,4 mm.
- Sichtbefund: `vergleich_ip_IMG_6120.jpg` - Halle im Overlay offen, Blick durch den Bogen auf die Rueckwand, runde Pfeiler mit Kapitellblock, Bogen auf dem echten Bogen, Baluster-Reihe auf der echten Balustrade, Konsolen 3 je Joch an den Fotostellen, Figurenbloecke auf den Figuren. Fehlt: Rueckwandtuer/-fenster (im Foto Tuer + Fenster), Gewoelberippen, Fenster-Masswerk.
  `vergleich_ip_IMG_6261.jpg` - offene Laube mit freistehenden Saeulen, Seitenbogen am nahen Ende (im Foto ist der seitliche Durchgang zu sehen), Staffelgiebel/Tuerme wie v10. `vergleich_c_12`, `render_schraeg.jpg`: Gesamtsilhouette inkl. Balustrade und Konsolen.
  Fehler: Stirnbogen nur ANNAHME; Endjoche "offen" bei 0,58/0,59 knapp; Kapitelle als Wuerfel; Konsolen -1,17/0,63 aus dem Gitter passen nicht ins 2,0-Raster (offen).

## Kette
`tools/koerper_kette.sh GITTER.json AUSDIR [AUDITDIR]` = Stufe 11: gitter_koerper bauen -> koerper_fenster_erker analyse -> koerper_v10 bauen (Balkon/Bloecke als Testeingabe) -> flaeche_oder_oeffnung -> analyse_konsolen -> koerper_v11 bauen -> pruefen; Datenordner = Grossvater des Gitters oder RCPARK_DATEN, Zusatzdateien (Wolke, Kameras, stabil, formen/helme.json, formen/baluster_abgenommen.json, kurven/arkaden.json) per Umgebungsvariablen; Log AUSDIR/koerper_kette.log. Noch nicht als Ganzes durchgelaufen (Einzelstufen ja) - erster Komplettlauf steht aus.

---
# Runde 4 (Agent): Komplettlauf, Durchsicht mit Z-Puffer, Rueckwand, Gewoelbe, Konsolen-Nutzerbefund

## (1) Komplettlauf `tools/koerper_kette.sh kette_video_alle/gitter.json kette_video_alle/koerper modelle/kaufhaus_grob3/audit/kette_video_alle/koerper`
- Skript loggt jetzt die Formquellen: Gitter 4075 Segmente, Quellen [0,4,5,6,7,9]; helme 3 im Gitter, boegen 3 im Gitter, saeulen 7 im Gitter, baluster nicht im Gitter -> Standardpfad formen/baluster_abgenommen.json (Hinweis: der Auftrag nannte das Gitter ohne helme/boegen - es hat beide). Zwischenpfade alle relativ zum AUSDIR.
- Alle 7 Stufen laufen durch (3,5 min), Vergleichsbilder + Bericht-JSONs entstehen (`kette_video_alle/koerper/koerper_v11_pruefung.json`, `_slicer_vorcheck.json`, Bilder `audit/kette_video_alle/koerper/`). Wolkennaehe < 20 cm gesamt 64,1 % (kette_video-Lauf 58,9 %).
- **Gate NICHT bestanden** fuer dieses Gitter: 27 offene Kanten / 16 doppelte Positionen nach STL-Roundtrip (manifold-Netz selbst wasserdicht). Erste Ursache (Erkerkante -10,24 in der Stirnflaeche) behoben (Rumpf 2 cm ueber die Erker-Wandanschluesse hinaus), Rest noch nicht analysiert (anderes Gitter -> andere Koinzidenzen). Fuer kette_video/gitter.json besteht das Gate weiterhin (0/0, 1 Koerper).

## (2) Durchsicht-Test mit echter Kamera-Zuordnung
- `kanten_3d_vote.py` hat den Z-Puffer je Kamera (Bins 3 px, Umgebung 9, Toleranz 0,3 m) bereits intern (Zeile 29-31), schreibt aber nur Zaehler (vis/kan); Bild-IDs je Punkt waeren als gepackte Bitmatrix (1,8 Mio x 882 Bit = ~200 MB) machbar - nicht umgesetzt (Masken-Lauf noetig).
- Stattdessen `flaeche_oder_oeffnung.py --zpuffer`: derselbe Z-Puffer ueber die GANZE Wolke je Kamera; ein Punkt stimmt nur fuer Kameras, aus denen er vorderster Punkt ist. `--innen`: Rueckwand nur mit Kameras in der Laube (52).
  Ergebnis (`koerper/flaechen_eg_v11_zpuffer.json`): Front EG 57 % Oeffnung / 41 % Wand / 3 % unentschieden, 4 Boegen wie zuvor, Pfeiler schaerfer, Endjoche weiter Oeffnung (0,59/0,61); sichtbar aus >= 1 Kamera: 185k von 822k Hinterpunkten.
  **Rueckwand (Laubenkameras): 89 % unentschieden, 11 % Wand, 1 % Oeffnung - die "Nische -8,9..-3,9" aus Runde 3 war ein Artefakt der Aussenkameras und ist weg** (Bau liest jetzt die Z-Puffer-Datei, wenn vorhanden).
  **Stirnwaende: unveraendert 83 % / 76 % "Oeffnung" (nur 207 / 2479 Punkte auf der Flaeche)** - der Z-Puffer hilft nicht, weil die Kantenwolke auf glatten Waenden keine Punkte hat, die verdecken koennten; Stirn bleibt ANNAHME Seitenbogen. Lehre: Blankwaende sind mit einer Kantenwolke nicht entscheidbar; dafuer dichte Wolke (MVS) oder Fototextur.

## (3) Rueckwand-Oeffnungen aus Gitterkanten
Rueckwandebene 6,54 +-0,4 m, Band Boden..Decke: nur 17 Segmente; Pfosten-Cluster -12,2..-10,9 (ausserhalb des Gebaeudes, Hinterpfeiler) und -1,23..-0,41 z 1,5-6,1 mit Horizontaler 6,10 = der Rueckwand-Halbpfeiler (saeule along -0,8, R 0,44), keine Tuer/Fenster-Rechtecke. Tuer + Fenster der Rueckwand (Foto 6120) sind im Gitter nicht vorhanden -> nicht gebaut, offen (Gitterdichte in der Laube zu gering: wenige Innenkameras).

## (4) Gewoelbe
Weder kette_video noch kette_video_alle enthalten Kurven quelle 10/11; `kurven/` hat nur Arkaden-Kurven. -> Laubendecke bleibt flach (ANNAHME, Hinweis im Log), Kreuzgratgewoelbe-Familie nicht gebaut.

## Nutzerbefund Konsolen (Overlay 6120)
- Lagen jetzt NUR aus dem Periodenraster (Pfeilerabstand/3 = 2,005 m, Phase 1,79 aus den Inlier-Bloecken 1,79/5,95/7,80 und 7 fotobelegten Rasterlagen); die Gitterbloecke -1,17 und 0,63 (0,96 / 0,85 m neben dem Raster) sind VERWORFEN (`konsolen_v11.json` -> verworfen). Beobachtung offen: was diese zwei Kantencluster sind (Konsolenprofil-Kanten des Nachbarn? Figurenkonsolen darueber?).
- Form: nach unten schmaler werdende Stuetze als Huelle (oben 0,45 x Platte-0,15, unten 0,2 x 0,15 m; ANNAHME Trapez - das Gitter liefert im Konsolenband keine Profilkanten).
- Overlay 6120 (`audit/koerper_v11/vergleich_ip_IMG_6120.jpg`, Mitte/rechts): 5 Konsolen im Bild, Abstand stimmt mit den echten (Raster 2,0 m), aber alle ~0,2-0,3 m links der echten (Phase) - Phase aus den drei Gitterbloecken; Fotophase (Zaehlprotokoll an 6120) waere der naechste Schritt. Formen jetzt konisch statt Quader.

## Stand v11 nach Runde 4 (kette_video)
Gate bestanden (0 offene Kanten, 0 Doppelpunkte, 1 Koerper, Genus 69), 9216 Dreiecke, 9135 m^3, H0 377 x 326 x 299 mm; Wolkennaehe 58,9 % / Median 0,12; Rueckwand ohne Nische; Konsolen 10 im Raster (Trapez); Stirnbogen ANNAHME; Decke flach.
