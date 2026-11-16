# Massnachweis Oberlinden Haus Tvdr (Ketten-Haertetest) (automatisch aus masstabelle.json, 2026-11-16)

Status je Mass: **OK** = Istwert im Sollbereich der Quelle; **WIDERSPRUCH** = Quellen uneins (nicht gemittelt); **FEHLER** = Modell verletzt die Quelle.
Massstab: *dokument/lod2/laser* = absolut; *foto_intern* = bekanntes Mass im selben Foto; *modell* = zirkulaer (nur Richtung belastbar).

| Merkmal | Ist | Soll | Quelltyp | Massstab | Status | Quelle |
|---|---|---|---|---|---|---|
| Wasserdicht (1=ja) | 1.00 | 1..1 | modell | - | OK | Druckfaehigkeit |
| Anzahl getrennte Koerper | 1.00 | 1..1 | modell | - | OK | Schwebende Teile |

## Belegt durch

- **modell**: 2 von 2 Pruefungen gruen (Druckbarkeit, keine Realitaetsaussage)

## Elemente des Generators: 5 belegt, 0 Annahmen

- dach: Dach Teil 0 (walm_a) - Laser DOM1 (tools/dach_vermessen.py) ueber LoD2 DEBW_0010007Tvdr-Grundriss Teil 0
- dach: Spitze Teil 0 - DOM1 26 Pixel bis 16.9 m; Hoehe DOM1-max
- wand: Grundriss Teil 0 - LoD2 DEBW_0010007Tvdr GroundSurface 0
- wand: 6 Fenster Fassade f02 (automatisch erkannt) - OWLv2 auf dem Mehrfoto-Ortho (fassade_ortho.py -> fassade_parsing.py -> fenster_aus_parsing.py), Fotos eigen__IMG_20261106_113149, commons_orig2__051, eigen__IMG_20261106_113201
- wand: Gebaeude hohl, 6 Fenster durchgebrochen - bauteile.aushoehlen auf den automatisch erkannten Fenstern

## Beobachtungen ohne Pruefung

- heute Anlage: Quellen sichten: Dokumente (Hoehe), LoD2 (Grundriss/Traufe), DOM1 (Dachform), Fotos je Seite -> objekt.json/quellen fuellen, Zeilen mit Quelle anlegen

## Grenze

Offene Daten (Laser 1 m, Fotos +-5-10 %, Dokumente mit unklarer Bezugshoehe) beweisen keine Masse auf den Zentimeter.
Dieser Nachweis sagt je Mass, welche Quelle es stuetzt und wie belastbar der Massstab ist; mehr ist ehrlich nicht moeglich.
