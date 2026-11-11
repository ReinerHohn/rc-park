# Kreisbericht quader:laube_sockel_w (r1, 2026-11-11)

## 1. Formbeschreibung (Stufe 0; Fotos 6130 Nah, 6124 schraeg, q11 Uebersicht; ausgewertet am Torfoto-Overlay)
- Zonen von unten: Sockelfuss/Boden z 1,5; Fuellungsfelder (eingetiefte Kassetten mit Rahmen, Tuerchen/Schloss in 6130) bis ca. z 2,0; darueber ueberstehendes Gesimsband (Schattenkante unter dem Band) bis Oberkante z 2,2.
- Grundriss: Rechteck-Bank vor der Laubenrueckwand, ein durchgehender Streifen u -7,2..-1,5, Front n 7,73.
- Wiederholungen: Fuellungsfelder (nur benannt, nicht gezaehlt; keine Zaehlung -> keine Anzahl-Pruefung).
- Altes Modell: glatter Vollquader -> gelb: Gesimsband-Kanten, Feldrahmen; Praezision/Recall niedrig.
- Formfamilie: vorhandene `quader` mit `profil` (Querschnitt n,z); keine neue Familie noetig.

## 2. Zaehlungen
Keine (Felder nicht modelliert, ANNAHME: Kassettenfelder zu flach fuer H0, Tiefe nicht triangulierbar).

## 3. Messung Foto-F1 (halbe Aufloesung, 10 Torfotos, teil_fotoform)
| | vorher | nachher |
|---|---|---|
| F1 gesamt | 0,616 (9 Fotos, 6127 unbeurteilt) | 0,746 (10 Fotos) |
| Praez/Recall | 0,781/0,508 | 0,828/0,679 |
Gemeinsame 9 Fotos: Gewinn vor allem 6124 (0,82/0,35 -> 0,98/0,78) und 6130 (0,78/0,51 -> 0,81/0,56); 6206/6176/6174/q11/6115/6162 nahezu unveraendert; 6145 Praezision 0,78 -> 0,70 (Rueckschritt, Ursache ungeprueft).
Hinweis: Fotosatz verschieden (6127 neu beurteilt) - Vorsicht (Schrumpf-/Satzfalle), daher auf Gemeinsamen verglichen. Voll-Aufloesung und Tor-Entscheid beim Endtor.

## 4. Aenderung
`quader:laube_sockel_w`: `profil` [[7.2,1.5],[7.73,1.5],[7.73,1.98],[7.8,2.04],[7.8,2.2],[7.2,2.2]], n1 7,8. Gesimsband z 2,04-2,2 und Ueberstand 0,07 = ANNAHME aus Bildproportion; Sockelfront 7,73 aus Wolke; Oberkante 2,2 aus M-6117-006/M-6130-006.

## 5. Fehlerliste
- Gesimsband-Form: trifft laut Foto-F1 auf 6124/6130 besser (Fotokanten jetzt belegt); Ueberstand/Hoehe nicht triangulierbar = ANNAHME.
- Fuellungsfelder/Rahmen: fehlen weiter (gelb), ungeprueft/nicht gebaut.
- Westende u -7,2: ANNAHME, ungeprueft. 6145, q11: unveraendert schlecht (q11 Praezision 0,34, Fremdverdeckung durch Person).
- Overlays: `teil_fotoform` schrieb in diesem Modus keine Bilder; Overlays nach Vorher/Nachher NICHT selbst angesehen (ungeprueft). Vorher-Bilder: /media/oem/scan/rc-park_kreis/kaufhaus_grob3/fotoform/bilder_4b968034713841e2_v2_wolkenverdeckung_festbereich/quader__laube_sockel_w_{6130,6124,q11}.jpg

## 6. Geaenderte Dateien
modelle/kaufhaus_grob3/objekt.json, audit/kreis_bericht.md

## 7. Generalisierte Lehre
Lehre: Gesimsband-/Sockelprofil mit vorhandener quader-`profil`-Option statt Vollquader, Fotokanten-Gewinn auf gemeinsamen Fotos vergleichen | Anlass: laube_sockel_w Foto-F1 | Werkzeug: teil_fotoform.py
