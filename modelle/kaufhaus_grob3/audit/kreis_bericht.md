# Kreis 153352 r1 – staffelgiebel:west, oberster Pfeiler

## 1 Formbeschreibung (Stufe 0)
Fotos (Torfotos, Overlays angesehen): 6164 (Nah, schraeg), q11 (Nutzerfoto), 6261 (Uebersicht, Ostgiebel-Blick), vgl. Kappenecken M-6261-022..026.
Zone Treppe: 10 Stufenpfeiler, Rhythmus 0,907 m x 1,21 m, jede Stufe waagerecht mit senkrechter Stirn und niedrigem Satteldaechlein. Der oberste Pfeiler am First ist im Foto eine normale Stufe mit Daechlein (kein hoeherer Block). Im Modell war er ein Block auf z_spitze, 1,41 m (urspruenglich 2,11 m) ueber Stufe 1 (rot oben links).
Familie: vorhandene `staffelgiebel` in tools/baukasten_gen.py, neue Option `spitze_als_stufe` (generisch, Parameter in objekt.json).
Unsicherheit: kappe -0,9 (Kappenecken) gegen -0,45 (Fotokanten) bleibt Widerspruch (Regel 5).

## 2 Zaehlungen
Z-6261-002 (10 Stufen) unveraendert, keine neue Zaehlung.

## 3 Pruefungen
| Pruefung | vorher | nachher | Soll | Quelle |
|---|---|---|---|---|
| Oberkante Stufe 0 - Stufe 1 | 1,41 (rot, Vorgaengerlauf 152051) | 1,21 | 1,06..1,36 (Band ANNAHME) | M-6261-022..026 |
| Foto-F1 (halbe Aufl., 10 Torfotos) | 0,540 | 0,539 | Gate +0,02 NICHT erreicht | teil_fotoform |
| f1_h | 0,474 | 0,491 | Veto -0,02 ok | |
bauen_abnehmen (RCPARK_OHNE_FOTODIAG=1): alle Pruefungen bestanden.

## 4 Overlays
/media/oem/scan/rc-park_kreis/kaufhaus_grob3/20261111_153352a153352/ff_eigen_bilder/staffelgiebel__west_{q11,6164,6261,6225,nu3b,...}.jpg (nachher); vorher /media/oem/scan/rc-park_kreis/kaufhaus_grob3/fotoform/bilder_a13c00b138556846_v2_wolkenverdeckung_festbereich/

## 5 Fehlerliste
- trifft (selbst gesehen): oberster Pfeiler in q11, 6261 (6164 Vorher-Bild gesehen, Nachher nicht einzeln beurteilt): roter Block weg.
- trifft nicht: lange gelbe Linie unter den Stufen (Dachanschluss) in 6261/q11; Fuss am Erker/Turm gelb-rot.
- ungeprueft: Kappenhoehe per foto_mass, Regression, teile_lage_pruefen, fehlteile_finden, foto_diff nicht gelaufen.

## 6 Geaenderte Dateien
tools/baukasten_gen.py, modelle/kaufhaus_grob3/objekt.json, masstabelle.json (Pruefung + Messungen + erledigt), NICHTS_GEBRACHT.md, REZEPT_GEBAEUDE_AUS_FOTOS.md (L55).

## 7 Generalisierte Lehre
L55: Formkorrektur an kleinem Anteil bewegt F1 < 0,01 – Beleg per Massprufung auf Regelsteigung + Overlay | Anlass Westgiebel oberster Pfeiler | masstabelle giebel_w_stufe0/1.
