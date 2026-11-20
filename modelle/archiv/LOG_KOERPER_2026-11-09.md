# LOG Koerper aus Kantengitter – 2026-11-09 (Agent, Werkzeug `tools/gitter_koerper.py`)

Ziel: erster geschlossener, druckbarer Rohkoerper AUS dem Kantengitter (Gitter -> Ebenen -> Grundriss -> Koerper), Beweis, dass die Kette bis zum Druck durchgeht.
Eingabe: `/media/oem/scan/rc-park_daten/kaufhaus_alle/segmente_gitter_v7.json` (3041 Segmente, 2577 m; 1 Helm, 7 Saeulen, 3 Kleinboegen R 0,26-0,43 ohne Verwendung).
Pruefwolke `kanten3d_k80.npz` (1,83 Mio Kantenpunkte), Kameras `sfm/kam_lot2.json`, Foto `ip_IMG_6261.jpg`.
Keine Objektkonstanten im Code: Fassadenrichtung, Ebenen, Traufe, First, Grundriss, Boegen kommen aus der Datei; Nicht-Belegtes steht in `koerper/annahmen.json`.

## Aufrufe
```
~/.venvs/rcpark/bin/python tools/gitter_koerper.py bauen  SEG.json  .../kaufhaus_alle/koerper                      # manifold3d, 1 s
/media/oem/scan/venv-seg/bin/python -I tools/gitter_koerper.py pruefen .../koerper kanten3d_k80.npz sfm/kam_lot2.json .../bilder modelle/kaufhaus_grob3/audit/koerper   # GPU-knn, 2,5 min
/media/oem/scan/venv-seg/bin/python -I tools/gitter_koerper.py aufriss SEG.json .../koerper modelle/kaufhaus_grob3/audit/koerper
```

## Stufe 1 – Hauptebenen aus dem Gitter (Ergebnis des letzten Laufs)
- Fassadenrichtung u = (0,9423, -0,3347) (160,4 Grad), laengengewichteter Doppelwinkel der horizontalen Segmente.
- Fassadenebenen (1D-RANSAC auf Segment-Stuetzpunkten, Normale n, Toleranz 8 cm, >= 30 m): 12 Ebenen. Staerkste 12,66 m (392 m Kantenlaenge), weitere 12,81/12,52/12,96 (Fassadenband 12,4-13,1 = eine Wand mit Gesimsen/Laibungen),
  13,86 m (119 m, z 7,9-12,7 = Balkon-/Erkerzone 1,2 m vor der Wand), 3,48 m (45 m, z 27,0-27,3 = Firstbereich).
- First: hoechste lange horizontale Kante z = 27,51 m (35 m), Offset 3,05 m.
- Dachebene: geneigte Segmente oberhalb der Fassade, Linie in (Offset, z): Neigung 53,3 Grad (61 m Stuetzlaenge). Die freie Linie liegt 2,34 m UEBER dem First ->
  die geneigten Kanten sind die Staffelgiebel-Kanten ueber der Dachflaeche, nicht die Dachflaeche. Daher: Dach = Neigung aus den Kanten, Lage durch den First.
- Traufe: First-gebunden 14,61 m; hoechste lange horizontale Fassadenkante 14,68 m (51 m) -> stimmen auf 7 cm ueberein. Dachflaeche stimmt mit der Wolke (Offsets der Dachpunkte je z-Band) ueberein.
- Endebenen (Normale u, perpendikulare + vertikale Kanten, >= 10 m): Enden along -8,82 m (37 m, belegt) und 17,15 m (43 m, belegt, aber nur z 7,9-15,6) -> Laenge 25,97 m.
  Offen: am Ende +17,15 liegen auch Ebenen 15,51/15,85 m (48/33 m, bis z 23,5 = Erkerturm); der Giebel oben koennte 1,3 m weiter innen stehen (Overlay: Firstende ~50 px zu weit aussen).
- Staffelgiebel: Ende minus 7 Steiger-Cluster (vertikale Kanten, Offset 12,7 -> 5,8, z 16,5 -> 26,6) als Treppe -> Polygon gebaut. Ende plus 11 Cluster, nur 2 monoton -> gerade Giebellinie (ANNAHME).
- Laubenrueckwand (eigene Suche, Erdgeschoss, Toleranz 16 cm, >= 10 m): Offset 6,54 m -> Laubentiefe 6,12 m (Wolke zeigt Rueckwand bei 7,0 m, Saeule (1,53/6,71) steht dort).

## Stufe 2 – Grundriss
Front 12,66 m, Enden -8,82/17,15 m, Rueckwand ANNAHME Firstspiegel -6,56 m (Tiefe 19,2 m; keine Kanten/Wolkenpunkte hinter Offset ~4). Boden 1,50 m (ANNAHME niedrigster Saeulenfuss; Wolke 1 %-Quantil 1,45 m).

## Stufe 3 – Koerper (manifold3d)
Huelle = EIN Fuenfeck-Querschnitt (Front, Traufe, First, Rueckwand) entlang der Fassade extrudiert (keine Boolesche Naht an der Traufe),
+ Staffelgiebelwand (0,5 m, Ende minus) + Balkonkasten (13,86 m, z 8,0-10,0 = dicht belegter Bereich der Ebene; darueber nur Erker-Abschnitte)
+ 6 Saeulen-Zylinder (die 7. steht bei along -11,4 ausserhalb des Grundrisses -> loses Teil, nicht gebaut) + Helm (16-eckige Pyramide, Fuss 15,27, Spitze 22,44, + Schaft bis zur Traufe)
- 4 Arkadenoeffnungen (Tunnel bis zur Laubenrueckwand, Boden offen = Druckbett): Kreisbogen-RANSAC auf den geneigten Gitterkanten zwischen den Saeulen:
  R 3,04 / 3,06 / 3,04 / 2,46 m, Mittelpunkt z 4,4 / 4,4 / 4,4 / 5,0, Scheitel 7,45 / 7,44 / 7,43 / 7,47 m, Inlier 59-66 %, rms 3-4 cm -> Segmentbogen ueber die lichte Weite 5,1 m, Kaempfer ~6,0 m.
Export: `koerper/rohkoerper_v7.stl` (784 Dreiecke, 9168 m^3), `rohkoerper_v7_h0.stl` (1:87, mm, BBox 356 x 321 x 299 mm), `rohkoerper_v7.json` (alle Parameter + Log), `annahmen.json`, `rohkoerper_v7_kanten.json` (455 Netzkanten Dieder > 30 Grad).

## Stufe 4 – Pruefung (`rohkoerper_v7_pruefung.json`)
- wasserdicht: JA (manifold NoError, trimesh is_watertight nach STL-Roundtrip + merge_vertices TRUE, 0 Kanten mit != 2 Flaechen, 0 degenerierte Dreiecke, 1 Koerper, Euler 2). Volumen 9168 m^3.
- Wolke -> Oberflaeche (3 Mio Oberflaechenpunkte, GPU knn): 49,8 % der Kantenpunkte < 20 cm, Median 0,20 m; 35 % der Modelloberflaeche haben Wolke < 0,5 m (Rueckseite/Enden ohne Daten).

| z-Band | n Wolke | < 20 cm | < 50 cm | Median |
|---|---|---|---|---|
| 1-3 | 254k | 0,19 | 0,32 | 0,86 (Boden, Passanten, Nachbarn, Laubeninneres) |
| 3-5 | 164k | 0,48 | 0,68 | 0,24 |
| 5-7 | 243k | 0,51 | 0,73 | 0,19 |
| 7-9 | 449k | 0,58 | 0,82 | 0,14 |
| 9-11 | 198k | 0,57 | 0,77 | 0,15 |
| 11-13 | 213k | 0,47 | 0,80 | 0,23 (Erker/Fenster, nicht gebaut) |
| 13-15 | 173k | 0,56 | 0,82 | 0,15 |
| 15-23 | 117k | 0,57-0,68 | 0,73-0,77 | 0,09-0,16 (Dach, Erkerturm) |
| 23-27 | 19k | 0,85-0,86 | 0,89-0,91 | 0,07-0,09 |

- Sichtbefund `audit/koerper/overlay_ip_IMG_6261.jpg` (Kanten) und `overlay_flaechen_ip_IMG_6261.jpg` (Flaechen 45 %): Dachneigung, First und Traufe decken sich mit dem Foto; Staffelgiebel am fernen Ende (im Bild rechts) deckt die echten Stufen;
  die 4 Arkadenboegen liegen auf den echten Boegen (Scheitel ~7,45 m, Kaempfer ~6 m); Balkonkasten liegt auf dem echten Balkon; Helm am fernen Turm ~0,5-1 m unter der echten Spitze.
  Fehlt/abweichend: naher Giebel (im Bild links) gerade statt gestuft; naher Erkerturm fehlt (kein Helm im Fit); Ende plus ~0,5-1 m zu lang; Fenster/Erker/Figuren nicht gebaut (nicht verlangt).
- `render_vorn/seite/schraeg/hinten_schraeg.jpg` (Painter, Wolke rot): Pfeiler, Boegen, Balkon, Staffel, Helm sichtbar; Rueckseite leerer Kasten (ANNAHME).
- `aufriss_gitter_front.jpg`: Gitter im Frontband als Aufriss – zeigt Arkadenboegen z 5,3-7,45, Saeulen-`z_kopf` = Bogenscheitel (NICHT Kapitell), Fensterboegen 1. OG z 11-13,3, Gesims 14,5, Helm.
- `foto_hoehenlinien_6261.jpg`: Hoehenlinien z 2..13 der Frontebene ins Foto projiziert (Kamera + Rahmen passen: z7 = Bogenscheitel, z8-9 Balkon, z11-13 Fenster).

## Annahmen (`koerper/annahmen.json`)
Rueckwand Firstspiegel; Boden = Saeulenfuss 1,50; Staffelgiebel-Trittflaechen horizontal, Rueckhaelfte gespiegelt, Wand 0,5 m; Ende plus gerade; Balkonkasten durchgehend z 8-10; Helmschaft Traufe-Helmfuss; Laubenboden = Druckbett.

## Lehren / Fehler auf dem Weg
1. Saeulen-`z_kopf` (7,1-7,7) aus dem Wolkenfit ist der Bogenscheitel, nicht das Kapitell: erster Bogenfit suchte erst ab z_kopf-0,5 und fand die Fensterboegen des 1. OG (R 1,95, z 8,4-9,1). Suchfenster = ganze Pfeilerhoehe, Mittelpunkt-Zwang zb+1..z_kopf -> richtige Boegen, 4/4 konsistent.
2. Geneigte Kanten am Giebel liegen 2,3 m ueber der Dachflaeche (Staffelgiebel); Dachebene nie frei aus ihnen fitten, Lage durch den First binden.
3. Boolesche Naehte: Dachprisma-Ecke exakt auf der Rumpfkante / Tunnelflaeche tangential an Saeulenzylinder -> manifold ok, aber nach STL-Roundtrip 16-17 nicht-mannigfaltige Kanten. Loesung: Rumpf+Dach als ein Querschnitt, Tunnel 2 cm von Zylindern weg, keine koinzidenten Endflaechen.
4. Vorsprungsebene 13,86 (z 7,9-12,7) ist nicht durchgehend: Balkon (z 8-10, along-Deckung 78-89 %) ja, Erker (z 10-12,7, 23 %) nein -> Kasten nur im dicht belegten Band, sonst verschlechtert sich Band 11-13 (0,23 -> 0,55 m).
5. Foto-Overlay ohne Sichtbarkeitstest zeigt auch Rueckflaechen (Tunnel-Rueckwandboegen) – Flaechen-Overlay (Painter) daneben legen.

## Offen / naechste Schritte
- Zweiter Helm/Erkerturm (nahes Ende) fehlt im `helme`-Fit; Endebene plus 17,15 vs 15,5-15,85 klaeren (Giebel oben vermutlich bei ~15,8).
- Staffelgiebel Ende plus: Steiger durch Turm ueberlagert, Spiegel-Prior (gitter_spiegel) pruefen.
- Seitliche Laubenboegen in den Giebelwaenden (im Foto links sichtbar) nicht gebaut.
- Anzahl Arkaden (4) ist aus `saeulen` (Wolke) – nach Regel 9 am Foto zaehlen (`foto_zaehlung.py`), bevor sie Sollwert wird.
- Pruefstand-Sollwerte fuer Wolkennaehe je Band und Masstabellen-Zeilen (Traufe 14,6, First 27,5, Neigung 53,3, Bogen R 3,05/Scheitel 7,45) noch nicht eingetragen.
