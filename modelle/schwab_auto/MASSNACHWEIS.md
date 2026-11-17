# Massnachweis Schwabentor (automatisch aus masstabelle.json, 2026-11-17)

Status je Mass: **OK** = Istwert im Sollbereich der Quelle; **WIDERSPRUCH** = Quellen uneins (nicht gemittelt); **FEHLER** = Modell verletzt die Quelle.
Massstab: *dokument/lod2/laser* = absolut; *foto_intern* = bekanntes Mass im selben Foto; *modell* = zirkulaer (nur Richtung belastbar).

| Merkmal | Ist | Soll | Quelltyp | Massstab | Status | Quelle |
|---|---|---|---|---|---|---|
| Wasserdicht (1=ja) | 1.00 | 1..1 | modell | - | OK | Druckfaehigkeit |
| Anzahl getrennte Koerper | 1.00 | 1..1 | modell | - | OK | Schwebende Teile |

## Belegt durch

- **modell**: 2 von 2 Pruefungen gruen (Druckbarkeit, keine Realitaetsaussage)

## Elemente des Generators: 24 belegt, 0 Annahmen

- dach: Dach Teil 0 (Fotodach, mit Aufsatz) - Fotos: Sichtkegel-Schnitt der Himmelskante aus 162 Fotos (tools/dach_aus_fotos.py, 2026-11-17 11:17); Gegenprobe 63 von 112 Fotos <= 0.5 m
- wand: Grundriss Teil 0 - LoD2 DEBW_001000hPLcp GroundSurface 0
- wand: Teil 1 (ohne Dachmessung) - LoD2 DEBW_001000hPLcp Wandoberkante (31 eigene Waende)
- wand: Grundriss Teil 1 - LoD2 DEBW_001000hPLcp GroundSurface 1
- wand: Quader mit Fugen aus dem Foto, Fassade w00 ab z 10 m - tools/steine_aus_foto.py --foto auto (bestes Foto, Verdeckung, Gegenfoto)
- wand: Relief Fassade w00 (Fassaden-Kette) - Netz der dichten Wolke (Hoehenbild 5 cm); Putz ueber Fotofarbe (eigen__IMG_20261106_114133, eigen__IMG_20261106_114023, eigen__IMG_20261106_114052); Loecher generiert
- wand: Quader mit Fugen aus dem Foto, Fassade w01 ab z 10 m - tools/steine_aus_foto.py --foto auto (bestes Foto, Verdeckung, Gegenfoto)
- wand: Relief Fassade w01 (Fassaden-Kette) - Netz der dichten Wolke (Hoehenbild 5 cm); Putz ueber Fotofarbe (eigen__IMG_20261106_113429, eigen__IMG_20261106_113128, eigen__IMG_20261106_113441); Loecher generiert
- wand: Quader mit Fugen aus dem Foto, Fassade w02 ab z 10 m - tools/steine_aus_foto.py --foto auto (bestes Foto, Verdeckung, Gegenfoto)
- wand: Relief Fassade w02 (Fassaden-Kette) - Netz der dichten Wolke (Hoehenbild 5 cm); Putz ueber Fotofarbe (eigen__IMG_20261106_113128, eigen__IMG_20261106_113605, eigen__IMG_20261106_113205); Loecher generiert
- wand: Quader mit Fugen aus dem Foto, Fassade w03 ab z 10 m - tools/steine_aus_foto.py --foto auto (bestes Foto, Verdeckung, Gegenfoto)
- wand: Relief Fassade w03 (Fassaden-Kette) - Netz der dichten Wolke (Hoehenbild 5 cm); Putz ueber Fotofarbe (eigen__IMG_20261106_113416, eigen__IMG_20261106_113128, eigen__IMG_20261106_113338_1); Loecher generiert
- wand: Relief Fassade w04 (Fassaden-Kette) - Netz der dichten Wolke (Hoehenbild 5 cm); Putz ueber Fotofarbe (eigen__IMG_20261106_113743, eigen__IMG_20261106_113727_1, eigen__IMG_20261106_113744_1); Loecher generiert
- wand: Quader mit Fugen aus dem Foto, Fassade w05 ab z 0 m - tools/steine_aus_foto.py --foto auto (bestes Foto, Verdeckung, Gegenfoto)
- wand: Relief Fassade w05 (Fassaden-Kette) - Netz der dichten Wolke (Hoehenbild 5 cm); Putz ueber Fotofarbe (eigen__IMG_20261106_113854, eigen__IMG_20261106_113852, eigen__IMG_20261106_113836); Loecher generiert
- wand: Quader mit Fugen aus dem Foto, Fassade w06 ab z 0 m - tools/steine_aus_foto.py --foto auto (bestes Foto, Verdeckung, Gegenfoto)
- wand: Relief Fassade w06 (Fassaden-Kette) - Netz der dichten Wolke (Hoehenbild 5 cm); Putz ueber Fotofarbe (eigen__IMG_20261106_113852, eigen__IMG_20261106_113854, online_orig__od_02); Loecher generiert
- wand: Quader mit Fugen aus dem Foto, Fassade w07 ab z 0 m - tools/steine_aus_foto.py --foto auto (bestes Foto, Verdeckung, Gegenfoto)
- wand: Relief Fassade w07 (Fassaden-Kette) - Netz der dichten Wolke (Hoehenbild 5 cm); Putz ueber Fotofarbe (online_orig__od_02, eigen__IMG_20261106_113852, online_orig__od_08); Loecher generiert
- dach: Teil 0: ueber der Traufunterkante nur das Fotodach - tools/dach_bauen.ueber_traufe_nur_dach (Reliefreste ueber der Wand entfernt)
- wand: 2 Fenster Fassade f00 (automatisch erkannt) - OWLv2 auf dem Mehrfoto-Ortho (fassade_ortho.py -> fassade_parsing.py -> fenster_aus_parsing.py), Fotos eigen__IMG_20261106_113130, eigen__IMG_20261106_113142, eigen__IMG_20261106_113141
- wand: 2 Fenster Fassade f03 (automatisch erkannt) - OWLv2 auf dem Mehrfoto-Ortho (fassade_ortho.py -> fassade_parsing.py -> fenster_aus_parsing.py), Fotos eigen__IMG_20261106_114049, eigen__IMG_20261106_114046, eigen__IMG_20261106_114034
- wand: Tordurchfahrt Fassade f00 (spitz, automatisch erkannt) - OWLv2-Bogenkasten als Suchfenster (fassade_parsing.py) -> Ebenen-Sweep ueber die Fotos (fassade_tiefe.py: Durchblick = Fotos in der Wandtiefe nicht deckungsgleich) -> Formfamilie eingepasst (tools/oeffnungen_bogen.py), Fotos eigen__IMG_20261106_113130, eigen__IMG_20261106_113142, eigen__IMG_20261106_113141
- wand: Gebaeude hohl, 4 Fenster durchgebrochen - bauteile.aushoehlen auf den automatisch erkannten Fenstern

## Beobachtungen ohne Pruefung

- heute Anlage: Quellen sichten: Dokumente (Hoehe), LoD2 (Grundriss/Traufe), DOM1 (Dachform), Fotos je Seite -> objekt.json/quellen fuellen, Zeilen mit Quelle anlegen
- auto umriss_tor: GANZE DACHLINIE versetzt (Foto hoeher: Dach/Aufbau fehlt oder zu niedrig), 3 Fotos einig: +4.95 m ueber 0.0 m bei [0.0, 0.0, 0.0] (Foto eigen__IMG_20261106_113201) -> am Bild audit/umriss_<foto>.jpg pruefen; echt = messen und bauen, Verdecker = verwerfen

## Grenze

Offene Daten (Laser 1 m, Fotos +-5-10 %, Dokumente mit unklarer Bezugshoehe) beweisen keine Masse auf den Zentimeter.
Dieser Nachweis sagt je Mass, welche Quelle es stuetzt und wie belastbar der Massstab ist; mehr ist ehrlich nicht moeglich.
