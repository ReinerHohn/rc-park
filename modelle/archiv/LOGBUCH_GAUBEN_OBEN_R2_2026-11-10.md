# Logbuch gaubenreihe:oben (Kreis2 r2, 10.11.2026)

## Formbeschreibung (Stufe 0)
Fotos angesehen: 6259 (Nahfoto 29 m, Blick -38 Grad), c12 (Handy, 37 m, frontal), 6162 (35 m, schraeg von links, zeigt Wange), j05 (Tele 43 m), Sichtliste-Overlay j_05, Z-018-006 (Zaehlfoto 018). Modellpunkt vorher ins Foto projiziert (Overlay `rundekreis2_gaubenreihe_oben_alt*.jpg`).
- Zonen von unten: (1) Fensterbank (dunkle Platte, Unterkante z 20,40 an der Stirnebene n 8,31) - (2) Fensterkasten/Stirn 1,02 m breit, 0,83 m hoch, Holz, Rundbogenfenster mit Kreuzsprosse, seitliche Pfosten - (3) Vordach: ziegelgedecktes flaches Pultdach, 1,45 m breit (0,2 m ueber die Stirn hinaus), 0,22 m vor der Stirn, Unterkante z 21,23, mit kleinen Konsolen - (4) Wangen: rote Dreiecke seitlich, Pultdach laeuft ca. 1,5 m zurueck in den Hang.
- Grundriss: Rechteck-Stirn, Seitenflaechen dreieckig; keine Giebelflaeche, kein Satteldach (Widerspruch LOG_FORMEN 'Giebelgauben' -> Fotos 6162/6259 zeigen eindeutig Pultdach).
- Wiederholung: 2 Gauben (Z-018-006), gleiche Form, u 0,66 / 6,54, Teilung 5,88 m. Dritte Quelle fuer Gleichheit: Triangulation A und B stimmen in n (8,30/8,31), Breite (1,02/1,02), Vordach (1,48/1,43) auf 0,05 m.
- Anschluss: Stirn sitzt am Hang (Hang an Stirn z 20,49, Fensterbank 20,40-20,44 eingebunden).
- Aktuelles Modell war anders: Stirn 1,66 m hoch (statt 0,83), Pultdach bei 2,5 m, kein Vordach, Stirn zu schmal (0,96 ok), Lage u um 0,3-0,4 m daneben (Overlay alt).
Formfamilie: vorhandene `gaubenreihe` form schlepp, um generische Parameter vordach_vor/-breite/-dicke/dach_tiefe erweitert (kein Objektname im Code).
Offen/ANNAHME: Rueckseite entfaellt; Vordach-Dicke 0,14 geschaetzt; dach_tiefe nur 1 Punkt (M-6259-009, +-0,25); Rundbogenfenster nicht modelliert.

## Zaehlung (Stufe 1)
Z-018-006 (Foto 018, Protokoll in modelle/kaufhaus/messprotokoll): 2 Gauben obere Reihe, bestaetigt in c12, 6259 (je 1 voll, links/rechts) und 6162. Keine neue Zaehlung noetig; Anzahl nicht aus Wolke.

## Messung (Stufe 2)
Neue Kamera-Bruecke K-c12, K-j05, K-p03, K-6162 aus kam_lot2.json. Triangulation foto_mass --tri mit K-c12 + K-6259 + K-6162 (Schnittwinkel 9/20/22 Grad, Strahlabstand <= 0,07 m, +-0,13 m): M-6259-001..013. Erste Variante mit nur c12+6259 (Schnittwinkel 9 Grad) hatte +-0,27 m -> dritte Kamera noetig (L19). j05 (Tele f 9469, Gaube unscharf) nicht verwendet.
Ergebnisse: Fensterbank n 8,307 (A/B), z 20,44/20,33, Breite 1,02; Vordach-Unterkante n 8,49-8,55, z 21,30/21,16, Breite 1,48/1,43; hintere Vordachecke B n 6,82 z 22,75.
Hoehenunterschied A/B 0,14 m bleibt stehen (nicht gemittelt begruendet; im Modell gleiche Hoehe, innerhalb +-0,13).

## Pruefungen
Alte Stand: 8 FEHLER (vor/up/um/dach_z je Gaube), 2 Wachposten OK. Neu: alle bestanden. Siehe kreis_bericht.md.

## Wolkenbeleg
gaubenreihe__oben 0,459 -> 0,588 (Median 0,166 -> 0,124 m), unten 0,521 -> 0,52 (nicht angefasst). Restanteil: Wolke liegt am Dach nach altem Befund ~1 m tief; Wolke zaehlt nur zur Gegenprobe.
