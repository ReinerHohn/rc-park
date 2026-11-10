# Logbuch Kreis r1: fensterreihe:og (kaufhaus_grob3, 2026-11-10)
Befund: Beleg 0,67 / Recall 0,792 / Praezision 0,491. Ergebnis: Beleg 0,979 / Recall 0,840 / Praezision 0,683.

## Formbeschreibung (Stufe 0)
Fotos (angesehen, Gitter-Crops, Overlay vorher/nachher): 6161 (27 m, nahezu frontal, Hauptmessfoto), 6120 (11,6 m, schraeg von links unten, Nahfoto), 6132 (16 m, Azimut -22), 6117 (18,5 m, Azimut +50), 6118 (Ansicht), 6161-Gruppen 2/3/4 einzeln.
- Zonen: Sohle z 10,34 -> untere Reihe 3 Lichter -> Kaempfer (Seitenlichter z 11,77, Mittellicht 12,3) -> obere Reihe 3 Lichter -> Vorhangbogen-Bekroenung (aussen senkrecht bis z 12,5, dann konkav ansteigend zu den Stegscheiteln z 13,43 bei |u| 0,48, Mittelsenke 13,34).
- Grundriss/Querschnitt: Steinrahmen (Gold gefasst) buendig mit der Wand n 12,66, Lichter tief in der Laibung (Glas hinter der Wand), Goldprofil doppelt.
- Wiederholung: 5 Gruppen (Pitch 3,96), je 3 Spalten gleicher Breite, 2 Zeilen.
- Anschluss: Sohle auf Balustrade, Figurenkonsolen bei |u| 1,98 zwischen den Gruppen.
- Am Altmodell anders: Gruppe 3,33 m breit (real 2,72), Seitenlichter 0,91 (real 0,71), Rahmenfront 0,15 vorstehend, Glas in der Wandebene, Kontur zu niedrig am Stegscheitel (13,24 statt 13,43).
Formfamilie: vorhandene `fensterreihe` (Kontur frei). Neu nur optionaler Parameter `nische_tiefe` (Lichter in der Laibung), generisch.

## Ursache
Aussenpfosten waren im Kantengitter nur 1 von 10 belegt, Breite 3 x 0,912 + 4 x 0,147 war abgeleitet. Der alte Beleg 0,67 war aufgeblaeht: die ueberbreiten Rahmen lagen auf Wandpunkten der Wolke (Abstand 0,14 < 0,15). Glas liegt in der Wolke 0,27 m hinter der Wand (n 12,38-12,41).

## Messung (Messprotokolle)
M-6161-022..044 (Breite 2,72/2,71, Lichter 0,71, Rahmen 0,105, Stege 0,19, Kontur, Hoehen), M-6120-051..054 Gegenprobe, Tiefen: M-6120-055/056/057 (30 Grad), M-6132-001/002 (63,5 Grad). Z-6161-002 (3 Lichter je Gruppe), Z-6161-003 (2 Reihen).
Widerspruch Rahmenfront: M-6120-057 12,805 gegen M-6132-002 12,646, M-6120-056 12,671, Wolke 12,64-12,65 -> buendig, Ausreisser verworfen (Paar nur 30 Grad); bestaetigt durch Gate (tiefe 0,15 -> 0,05: Beleg 0,863 -> 0,979, Praezision 0,496 -> 0,683).
Glastiefe: Foto 0,06-0,10 gegen Wolke 0,27 -> 0,2 = ANNAHME, offen.

## Aenderung
objekt.json fensterreihe:og: breite 2,72, rahmen_b 0,105, pfosten_b 0,19, scheitel_z 13,41, kontur neu, tiefe 0,05, nische_tiefe 0,2, glas_n -0,23. tools/baukasten_gen.py: nische_tiefe (Schnitt je Licht 3 mm kleiner als das Licht, Pfosten/Riegel bis auf den Nischengrund; erste Version mit deckungsgleichen Flaechen gab 154 Teilnetze/nicht wasserdicht).
Pruefungen: 7 neue (fenster_og_g3/g4_lichtweite, wand_aussen l/r, stegscheitel l/r, glas_tiefe); am Altstand alle ROT (0,92 / -0,15 / 11,79 / -0,03), jetzt gruen. Zwischenversion mit Rahmenfront-Pruefung 12,81 entfernt (Tiefe war nur ANNAHME).
Abnahme: alle Pruefungen bestanden, 1 Teilnetz, wasserdicht, Wandstaerke 0,12. regression.py identisch. teile_lage_pruefen og: Median 0,05 m, 0 % > 0,5 m (Werkzeug laeuft jetzt fuer og). foto_diff 6161: Modellkanten ohne Foto 0,0465 -> 0,0358, Fotokanten ohne Modell 0,438 -> 0,353 (Gesamtmodell).
