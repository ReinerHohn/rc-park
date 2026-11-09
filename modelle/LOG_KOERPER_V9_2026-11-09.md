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
