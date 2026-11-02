# Massnachweis Martinstor Torbau 1901 (McDonald's) (automatisch aus masstabelle.json, 2026-11-03)

Status je Mass: **OK** = Istwert im Sollbereich der Quelle; **WIDERSPRUCH** = Quellen uneins (nicht gemittelt); **FEHLER** = Modell verletzt die Quelle.
Massstab: *dokument/lod2/laser* = absolut; *foto_intern* = bekanntes Mass im selben Foto; *modell* = zirkulaer (nur Richtung belastbar).

| Merkmal | Ist | Soll | Quelltyp | Massstab | Status | Quelle |
|---|---|---|---|---|---|---|
| Torbau-Bogen: Oeffnungsbreite / Turmbreite | 0.65 | 0.55..0.74 | foto_vollbild | foto_intern | OK | Foto 089 (Commons CC BY-SA 4.0, nur Messvorlage), Messprotokoll M-089-002 (7,25 m +-0,6 innen), M-089-001 (8,0 m aussen); Horizontalmassstab Turm-Nordwand 11,2 m (LoD2) in gleicher Ebene |
| Torbau-Bogen: Scheitelhoehe / Oeffnungsbreite (Form: breit, nicht Schlitz) | 0.85 | 0.7..1.02 | foto_vollbild | foto_intern | OK | Foto 089 (Commons CC BY-SA 4.0, nur Messvorlage), Messprotokoll M-089-004 (6,2 m) / M-089-002 (7,25 m); senkrecht aus Giebelspitze 20,7 m verankert |
| Torbau-Front (Obergeschoss) Breite / Turmbreite | 0.63 | 0.54..0.72 | foto_vollbild | foto_intern | OK | Foto 089 (Commons CC BY-SA 4.0, nur Messvorlage), Messprotokoll M-089-007 (7,06 m +-0,6; M-089-003 reichte bis in den Nachbarn); Horizontalmassstab Turm-Nordwand 11,2 m (LoD2) in gleicher Ebene |
| Torbau 1. OG: Fensterzahl | 4.00 | 4..4 | foto_vollbild | foto_intern | OK | Foto 089 Zoom Bogenzone/Front: 4 Fenster (2+2), Foto 006 gleiche Anordnung |
| Torbau 2. OG: Fensterzahl (2 im Erker + 1 in der Wand) | 3.00 | 3..3 | foto_vollbild | foto_intern | OK | Foto 089 Zoom neben Modell-Render: Reihe ueber der Kragplatte: 2 Erkerfenster + 1 Wandfenster; die 4 war eine Fehllesung (Beobachtung torbau-erker-wand-1) |
| Torbau Giebelgeschoss: Fensterzahl | 2.00 | 2..2 | foto_vollbild | foto_intern | OK | Foto 089: 2 Fenster unter dem Schweifgiebel |
| Torbau-Giebel: Breite am Fuss / Turmbreite | 0.52 | 0.42..0.58 | foto_vollbild | foto_intern | OK | Foto 089 (Commons CC BY-SA 4.0, nur Messvorlage), Messprotokoll 089 Zoom: Giebelfuss orig. x 2010..2440 = 430 px = 5,6 m; Horizontalmassstab Turm-Nordwand 11,2 m (LoD2) in gleicher Ebene |
| Torbau-Giebel: Breite im Hals (z 19,2) / Breite am Fuss | 0.45 | 0.4..0.6 | foto_vollbild | foto_intern | OK | Foto 089 Zoom: Volutengiebel verjuengt sich von 5,6 m (z 17) auf ~3 m (z 19,2), Kappe ~1,9 m |
| Torbau Gesamthoehe (m) | 20.70 | 20..21.5 | sfm_bodenanker | foto_kalibriert | OK | Giebelspitze: Nord-Wolke 20,6-20,7 m, Drohnenwolke Kappe 21,5 m (Streuung der Quellen, NICHT gemittelt: Sollbereich deckt beide) |
| Wasserdicht (1=ja) | 1.00 | 1..1 | modell | modell | OK | Druckfaehigkeit |
| Anzahl getrennte Koerper | 1.00 | 1..1 | modell | modell | OK | Schwebende Teile |
| Torbau-Erker: Vorsprung vor der Obergeschosswand (m) | 0.50 | 0.3..0.8 | sfm_bodenanker | foto_intern | OK | Wolke Nord: Erkerfront -6,2..-6,4, Wandfront -5,8 (Differenz 0,4-0,6 m); Foto 089: Erker springt sichtbar vor |

## Belegt durch

- **foto_vollbild**: 8 von 8 Pruefungen gruen (Vollaufloesung, Massstab aus Modell oder Dokument -> Werte grob, Richtung sicher)
- **sfm_bodenanker**: 2 von 2 Pruefungen gruen (COLMAP-Netz je Fassadenseite (tools/sfm_ausrichten.py), 7 Parameter aus LoD2-Eckkanten in >= 4 Fotos, Hoehenlage aus ANNAHME Strassenkamera 1,7 +- 0,6 m; Massstab +-2-3 %, Hoehe +-0,7 m systematisch; sieht keine Fassadenzaehlung (Punkte, keine Semantik). Register AH)
- **modell**: 2 von 2 Pruefungen gruen (Druckbarkeit, keine Realitaetsaussage)

## Elemente des Generators: 9 belegt, 0 Annahmen

- Nord: Arkadengeschoss (Pfeilerfront zurueckgesetzt) - Wolke z 5-9,5: Front bei x -5,2..-5,6; Breite y -5,6..-14,7 aus Foto 089 (Bogen 8,0 m aussen, M-089-001)
- Nord: Obergeschosse (glatte Wand, auf Kragplatte) - Wolke: Front bei x -5,8 neben dem Erker; Breite 7,06 m aus Foto 089 (M-089-007)
- Nord: Erker (2 Geschosse, vorkragend) - Wolke z 10-19: vorderste Front -6,2..-6,4 bei y -10..-7,5; Foto 089 Zoom: Erker 3,2 m breit, z 10,2..17,8
- Nord: Durchgangsbogen (McDonald's-Bogen, elliptisch) - Foto 089 Zoom: Spannweite 7,25 m (M-089-002), Scheitel 6,2 m (M-089-004), Kaempfer 3,0 m (M-089-005); rechtes Bogenende verdeckt: ANNAHME symmetrisch
- Nord: Fenster 1. Obergeschoss (4) - Foto 089 Zoom: 2+2 Fenster beidseits des Erkers; Hoehe M-089-006 (1,87 m); Breite 0,9 m aus 70 px
- Nord: Fenster 2. Obergeschoss (3: 2 im Erker, 1 in der Wand) - Foto 089 Zoom; Hoehe ANNAHME wie 1. OG
- Nord: Fenster Giebelgeschoss (2) - Foto 089: zwei Fenster unter dem Schweifgiebel, symmetrisch zur Giebelachse (Abstand 1,1 m aus 85 px)
- Nord: Schweifgiebel (Voluten) - Foto 089/006: Renaissance-Schweifgiebel, Fuss 5,6 m, Hals ~3,3 m, Kappe ~1,9 m; Firsthoehe Wolke 20,7 / Drohne 21,5; Achse y -8,3 aus Wolke (Foto 089 ergaebe -9,2: offener Widerspruch, nicht gemittelt)
- Nord: Satteldach giebelstaendig - LoD2 Vorderteil 19,6 m; Firstlinie ANNAHME senkrecht zur Front; Grundbreite = Giebelfuss

## Seiten

- Nord: KEIN FOTO - ungeprueft

## Beobachtungen ohne Pruefung

- 2026-11-03 Claude (Foto 089 vs Wolke): Giebelachse: Foto 089 (Turmkante als Ursprung) y -9,2, Nord-Wolke y -8,3, Drohnenwolke ~-7,5..-8. Widerspruch ~1 m, NICHT gemittelt; Modell bleibt bei -8,3 (zwei Quellen). -> zweites frontales Foto mit freier Giebelspitze messen
- 2026-11-03 Claude (Foto 089): Bogen rechtes Ende (y ~ -14,3) liegt hinter Schild/Laterne; Spannweite aus Symmetrie zur Scheitelmitte (x 2350) geschlossen: ANNAHME. -> Foto 006/014 gegenmessen oder Drohne West/Nord Draufsicht

## Grenze

Offene Daten (Laser 1 m, Fotos +-5-10 %, Dokumente mit unklarer Bezugshoehe) beweisen keine Masse auf den Zentimeter.
Dieser Nachweis sagt je Mass, welche Quelle es stuetzt und wie belastbar der Massstab ist; mehr ist ehrlich nicht moeglich.
