# Massnachweis Schwabentor (automatisch aus masstabelle.json, 2026-11-15)

Status je Mass: **OK** = Istwert im Sollbereich der Quelle; **WIDERSPRUCH** = Quellen uneins (nicht gemittelt); **FEHLER** = Modell verletzt die Quelle.
Massstab: *dokument/lod2/laser* = absolut; *foto_intern* = bekanntes Mass im selben Foto; *modell* = zirkulaer (nur Richtung belastbar).

| Merkmal | Ist | Soll | Quelltyp | Massstab | Status | Quelle |
|---|---|---|---|---|---|---|
| Wasserdicht (1=ja) | 1.00 | 1..1 | modell | - | OK | Druckfaehigkeit |
| Anzahl getrennte Koerper | 1.00 | 1..1 | modell | - | OK | Schwebende Teile |

## Belegt durch

- **modell**: 2 von 2 Pruefungen gruen (Druckbarkeit, keine Realitaetsaussage)

## Elemente des Generators: 5 belegt, 0 Annahmen

- dach: Dach Teil 0 (walm_a) - Laser DOM1 (tools/dach_vermessen.py) ueber LoD2 DEBW_001000hPLcp-Grundriss Teil 0
- dach: Spitze Teil 0 - DOM1 6 Pixel bis 49.6 m; Hoehe objekt.json hoehe_m
- wand: Grundriss Teil 0 - LoD2 DEBW_001000hPLcp GroundSurface 0
- wand: Teil 1 (ohne Dachmessung) - LoD2 DEBW_001000hPLcp Wandoberkante (31 eigene Waende)
- wand: Grundriss Teil 1 - LoD2 DEBW_001000hPLcp GroundSurface 1

## Beobachtungen ohne Pruefung

- heute Anlage: Quellen sichten: Dokumente (Hoehe), LoD2 (Grundriss/Traufe), DOM1 (Dachform), Fotos je Seite -> objekt.json/quellen fuellen, Zeilen mit Quelle anlegen

## Grenze

Offene Daten (Laser 1 m, Fotos +-5-10 %, Dokumente mit unklarer Bezugshoehe) beweisen keine Masse auf den Zentimeter.
Dieser Nachweis sagt je Mass, welche Quelle es stuetzt und wie belastbar der Massstab ist; mehr ist ehrlich nicht moeglich.
