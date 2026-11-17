# Massnachweis Historisches Kaufhaus Freiburg - grober Generator aus Teilen (Foto-Diff-Fahrzeug) (automatisch aus masstabelle.json, 2026-11-17)

Status je Mass: **OK** = Istwert im Sollbereich der Quelle; **WIDERSPRUCH** = Quellen uneins (nicht gemittelt); **FEHLER** = Modell verletzt die Quelle.
Massstab: *dokument/lod2/laser* = absolut; *foto_intern* = bekanntes Mass im selben Foto; *modell* = zirkulaer (nur Richtung belastbar).

| Merkmal | Ist | Soll | Quelltyp | Massstab | Status | Quelle |
|---|---|---|---|---|---|---|
| Wasserdicht (1=ja) | 1.00 | 1..1 | modell | - | OK | Druckfaehigkeit |
| Anzahl getrennte Koerper | 1.00 | 1..1 | modell | - | OK | Schwebende Teile |

## Belegt durch

- **modell**: 2 von 2 Pruefungen gruen (Druckbarkeit, keine Realitaetsaussage)

## Elemente des Generators: 13 belegt, 0 Annahmen

- dach: Dach Teil 0 (sattel_a) - Laser DOM1 (tools/dach_vermessen.py) ueber LoD2 DEBW_0010007Tv9r-Grundriss Teil 0
- dach: Spitze Teil 0 - DOM1 3 Pixel bis 21.2 m; Hoehe DOM1-max
- wand: Grundriss Teil 0 - LoD2 DEBW_0010007Tv9r GroundSurface 0
- wand: Teil 1 (ohne Dachmessung) - LoD2 DEBW_0010007Tv9r Wandoberkante (5 eigene Waende)
- wand: Grundriss Teil 1 - LoD2 DEBW_0010007Tv9r GroundSurface 1
- dach: Dach Teil 2 (sattel_a) - Laser DOM1 (tools/dach_vermessen.py) ueber LoD2 DEBW_0010007Tv9r-Grundriss Teil 2
- dach: Spitze Teil 2 - DOM1 1 Pixel bis 13.1 m; Hoehe DOM1-max
- wand: Grundriss Teil 2 - LoD2 DEBW_0010007Tv9r GroundSurface 2
- wand: Relief Fassade w03 (Fassaden-Kette) - Netz der dichten Wolke (Hoehenbild 5 cm), roh: das Foto zeigt kein Quaderwerk (Quader-Tor), kleine Loecher glatt gefuellt
- wand: Relief Fassade w04 (Fassaden-Kette) - Netz der dichten Wolke (Hoehenbild 5 cm), roh: das Foto zeigt kein Quaderwerk (Quader-Tor), kleine Loecher glatt gefuellt
- wand: Relief Fassade w05 (Fassaden-Kette) - Netz der dichten Wolke (Hoehenbild 5 cm), roh: das Foto zeigt kein Quaderwerk (Quader-Tor), kleine Loecher glatt gefuellt
- wand: 5 Fenster Fassade f02 (automatisch erkannt) - OWLv2 auf dem Mehrfoto-Ortho (fassade_ortho.py -> fassade_parsing.py -> fenster_aus_parsing.py), Fotos eigen__018_Freiburg-_Historisches_Kaufhaus_frontal_vom_Renaissanceporta, eigen__IMG_6161, eigen__051_Kaufhaus_-_panoramio_2_
- wand: Gebaeude hohl, 5 Fenster durchgebrochen - bauteile.aushoehlen auf den automatisch erkannten Fenstern

## Beobachtungen ohne Pruefung

- heute Anlage: Quellen sichten: Dokumente (Hoehe), LoD2 (Grundriss/Traufe), DOM1 (Dachform), Fotos je Seite -> objekt.json/quellen fuellen, Zeilen mit Quelle anlegen
- auto umriss_tor: Foto hoeher (Modell fehlt etwas / Verdecker): +1.47 m ueber 1.09 m bei [11.42, 1.29, 18.72] (Foto eigen__053_2017-06-15_Fronleichnam_auf_dem_Freiburger_M_nsterplatz_im_H) -> am Bild audit/umriss_<foto>.jpg pruefen; echt = messen und bauen, Verdecker = verwerfen
- auto umriss_tor: Foto hoeher (Modell fehlt etwas / Verdecker): +0.47 m ueber 0.73 m bei [10.39, 3.39, 20.97] (Foto eigen__053_2017-06-15_Fronleichnam_auf_dem_Freiburger_M_nsterplatz_im_H) -> am Bild audit/umriss_<foto>.jpg pruefen; echt = messen und bauen, Verdecker = verwerfen
- auto umriss_tor: Foto hoeher (Modell fehlt etwas / Verdecker): +0.79 m ueber 6.48 m bei [-5.02, 8.52, 20.96] (Foto eigen__053_2017-06-15_Fronleichnam_auf_dem_Freiburger_M_nsterplatz_im_H) -> am Bild audit/umriss_<foto>.jpg pruefen; echt = messen und bauen, Verdecker = verwerfen
- auto umriss_tor: Modell hoeher (zu hoch / erfunden): -0.97 m ueber 0.97 m bei [11.65, 3.06, 20.98] (Foto eigen__053_2017-06-15_Fronleichnam_auf_dem_Freiburger_M_nsterplatz_im_H) -> am Bild audit/umriss_<foto>.jpg pruefen; echt = messen und bauen, Verdecker = verwerfen
- auto umriss_tor: Modell hoeher (zu hoch / erfunden): -0.63 m ueber 6.64 m bei [6.31, 4.73, 20.99] (Foto eigen__053_2017-06-15_Fronleichnam_auf_dem_Freiburger_M_nsterplatz_im_H) -> am Bild audit/umriss_<foto>.jpg pruefen; echt = messen und bauen, Verdecker = verwerfen
- auto umriss_tor: Foto hoeher (Modell fehlt etwas / Verdecker): +1.46 m ueber 0.96 m bei [13.63, 9.62, 11.25] (Foto eigen__handy_06) -> am Bild audit/umriss_<foto>.jpg pruefen; echt = messen und bauen, Verdecker = verwerfen
- auto umriss_tor: Foto hoeher (Modell fehlt etwas / Verdecker): +1.37 m ueber 1.02 m bei [12.57, 9.59, 13.51] (Foto eigen__handy_06) -> am Bild audit/umriss_<foto>.jpg pruefen; echt = messen und bauen, Verdecker = verwerfen
- auto umriss_tor: Foto hoeher (Modell fehlt etwas / Verdecker): +1.02 m ueber 0.9 m bei [12.91, 6.73, 15.94] (Foto eigen__handy_06) -> am Bild audit/umriss_<foto>.jpg pruefen; echt = messen und bauen, Verdecker = verwerfen
- auto umriss_tor: Foto hoeher (Modell fehlt etwas / Verdecker): +0.68 m ueber 1.08 m bei [11.05, 3.18, 20.95] (Foto eigen__handy_06) -> am Bild audit/umriss_<foto>.jpg pruefen; echt = messen und bauen, Verdecker = verwerfen
- auto umriss_tor: Foto hoeher (Modell fehlt etwas / Verdecker): +1.29 m ueber 1.14 m bei [-6.72, 10.02, 20.91] (Foto eigen__handy_06) -> am Bild audit/umriss_<foto>.jpg pruefen; echt = messen und bauen, Verdecker = verwerfen
- auto umriss_tor: Modell hoeher (zu hoch / erfunden): -0.36 m ueber 3.17 m bei [8.27, 4.13, 20.93] (Foto eigen__handy_06) -> am Bild audit/umriss_<foto>.jpg pruefen; echt = messen und bauen, Verdecker = verwerfen
- 2026-11-17 Agent Detailrunde (Auftrag Nutzer: Steinmuster Ostseite nie am Foto geprueft): Steinmuster der Ostseite (w07) und Foto-'Quader' auf w00-w06 waren FALSCH: relief/w07_foto.jpg zeigte ein blaues Nachbarhaus mit Fensterlaeden, w04 roten Putz mit Fenstern und Dachziegeln. Kaufhaus ist verputzt. Bild: audit/detail_vorher_w07_foto.jpg -> ERLEDIGT 17.11.2026: fassaden_kette.py (Wandflaeche aus LoD2, Nachbarn als Verdecker, Quader-Tor in steine_aus_foto.py) - keine Fotosteine mehr, Netz-Relief an w03/w04/w05; Bild audit/neben_eigen__handy_06.jpg angesehen. OFFEN: Erker, Gauben, offene Arkaden, Staffelgiebel fehlen

## Grenze

Offene Daten (Laser 1 m, Fotos +-5-10 %, Dokumente mit unklarer Bezugshoehe) beweisen keine Masse auf den Zentimeter.
Dieser Nachweis sagt je Mass, welche Quelle es stuetzt und wie belastbar der Massstab ist; mehr ist ehrlich nicht moeglich.
