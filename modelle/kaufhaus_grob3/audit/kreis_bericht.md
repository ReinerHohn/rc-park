# Kreis2 baldachinreihe:baldachine – Krone nicht mittig (Nutzer 11.11. 16:17)

## 1. Formbeschreibung (Stufe 0)
Fotos: 6161 (Uebersicht frontal, alle 4), 6145 (Schraeg, Nah), 6132, 6117, 6120, 6127 angesehen (audit/rundekreis2_baldachine/p_6161, r_6161_3, h_6161_3, h_6145_3).
Zonen: Haube mit Masswerkband (rot/gold), Kranzgesims, Fialenkrone: Mittelfiale + 2 Seitenfialen mit Blattwerk, symmetrisch um die Mittelfiale (6161 Fig 3: Seitenspitzen 2142/2203, Mitte 2172 px -> Krone symmetrisch). Formfamilie unveraendert: baldachinreihe (vorhanden). Nur die Lage ist falsch, nicht die Form.
Befund: Fig 3 im Foto sichtbar ~0,1 m neben der Kronenachse (6161 und 6120).

## 2. Zaehlungen
Keine neue Zaehlung noetig (4 Baldachine, Z-6161-002 bestehend).

## 3. Pruefungen (vorher -> nachher, Soll -0,1..0,1)
| Pruefung | vorher | nachher | Quelle |
|---|---|---|---|
| Figur 2 + Baldachin 2 Versatz Krone gegen Figurenachse | -0,10 ROT | 0,00 | M-6161-049/050 (4 Kameras) |
| Figur 3 + Baldachin 3 | 0,12 ROT | 0,00 | M-6161-047/048 (3 Kameras) |
| Figur 4 + Baldachin 4 | -0,12 ROT | 0,00 | M-6161-051/052 (2 Kameras) |
Messung im selben Kamerasatz: Fotoversatz Krone-Figur Fig2 0,00 / Fig3 +0,076 / Fig4 +0,077 m (Unsicherheit je Peilung 0,03-0,06 m).
Ursache: Altwerte der Figuren (Kamerasatz 6120) und Baldachine (6161+6145) aus verschiedenen Kamerasaetzen; Figur 2 war 0,09 m falsch, Krone selbst nur <= 0,04 m.
Aenderung: Baldachin-u 5,42/1,614/-2,447 -> 5,385/1,583/-2,410; Figuren-u 5,468/1,476/-2,463 -> 5,382/1,507/-2,487. Figur 1 / Baldachin 1 nicht gemessen, unveraendert.
bauen_abnehmen: alle Pruefungen bestanden (rc=0). Foto-F1 (halbe Aufl., 10 Torfotos): baldachine 0,815 (unveraendert, Prec 0,764/Recall 0,873), figuren 0,897 (Vorher nicht gemessen = ungeprueft).

## 4. Overlays
audit/rundekreis2_baldachine/p_6161.jpg (vorher), pn_6161.jpg (nachher), r_6161_3.jpg, h_6161_3.jpg, h_6145_3.jpg (Lineale/Messausschnitte).

## 5. Fehlerliste
- trifft: Fig 2 Krone und Figur koaxial (pn_6161 angesehen); Fig 3/4 zeigen den realen Restversatz ~0,08 m.
- ungeprueft: Figur 1/Baldachin 1 (nicht gemessen, Versatz im alten Modell +0,04); Foto-F1 der Figuren vorher; Fialen/Masswerk-Formfehler aus Vorrunde (nicht Ziel).
- Restunsicherheit: Peilung +-0,03..0,06 m; 2 Kameras bei Fig 4.

## 6. Geaenderte Dateien
modelle/kaufhaus_grob3/objekt.json, masstabelle.json (Messungen, 3 Pruefungen, erledigt-Feld), messprotokoll/M-6161-047..052, NICHTS_GEBRACHT.md, REZEPT (L55), audit/*.

## 7. Generalisierte Lehre
Lehre | Anlass | Werkzeug
Relative Lage zweier Teile nur im gleichen Kamerasatz messen, Pruefung als Differenz | Scheinversatz 0,09 m durch gemischte Kamerasaetze | foto_mass --tri2d + schnitt_reichweite up-um
