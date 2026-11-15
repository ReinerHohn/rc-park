# Massnachweis Historisches Kaufhaus Freiburg - grober Generator aus Teilen (Foto-Diff-Fahrzeug) (automatisch aus masstabelle.json, 2026-11-15)

Status je Mass: **OK** = Istwert im Sollbereich der Quelle; **WIDERSPRUCH** = Quellen uneins (nicht gemittelt); **FEHLER** = Modell verletzt die Quelle.
Massstab: *dokument/lod2/laser* = absolut; *foto_intern* = bekanntes Mass im selben Foto; *modell* = zirkulaer (nur Richtung belastbar).

| Merkmal | Ist | Soll | Quelltyp | Massstab | Status | Quelle |
|---|---|---|---|---|---|---|
| Wasserdicht (1=ja) | 0.00 | 1..1 | modell | - | FEHLER | Druckfaehigkeit |
| Anzahl getrennte Koerper | 3.00 | 1..1 | modell | - | FEHLER | Schwebende Teile |

## Belegt durch

- **modell**: 0 von 2 Pruefungen gruen (Druckbarkeit, keine Realitaetsaussage)

## Elemente des Generators: 8 belegt, 0 Annahmen

- dach: Dach Teil 0 (sattel_a) - Laser DOM1 (tools/dach_vermessen.py) ueber LoD2 DEBW_0010007Tv9r-Grundriss Teil 0
- dach: Spitze Teil 0 - DOM1 3 Pixel bis 21.2 m; Hoehe DOM1-max
- wand: Grundriss Teil 0 - LoD2 DEBW_0010007Tv9r GroundSurface 0
- wand: Teil 1 (ohne Dachmessung) - LoD2 DEBW_0010007Tv9r Wandoberkante (5 eigene Waende)
- wand: Grundriss Teil 1 - LoD2 DEBW_0010007Tv9r GroundSurface 1
- dach: Dach Teil 2 (sattel_a) - Laser DOM1 (tools/dach_vermessen.py) ueber LoD2 DEBW_0010007Tv9r-Grundriss Teil 2
- dach: Spitze Teil 2 - DOM1 1 Pixel bis 13.1 m; Hoehe DOM1-max
- wand: Grundriss Teil 2 - LoD2 DEBW_0010007Tv9r GroundSurface 2

## Beobachtungen ohne Pruefung

- heute Anlage: Quellen sichten: Dokumente (Hoehe), LoD2 (Grundriss/Traufe), DOM1 (Dachform), Fotos je Seite -> objekt.json/quellen fuellen, Zeilen mit Quelle anlegen

## Grenze

Offene Daten (Laser 1 m, Fotos +-5-10 %, Dokumente mit unklarer Bezugshoehe) beweisen keine Masse auf den Zentimeter.
Dieser Nachweis sagt je Mass, welche Quelle es stuetzt und wie belastbar der Massstab ist; mehr ist ehrlich nicht moeglich.
