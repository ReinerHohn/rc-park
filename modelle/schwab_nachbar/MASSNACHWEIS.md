# Massnachweis Schwabentor Nachbarhaus (Fachwerkhaus + Haus mit Torbogen, LoD2 Tvdv) (automatisch aus masstabelle.json, 2026-11-15)

Status je Mass: **OK** = Istwert im Sollbereich der Quelle; **WIDERSPRUCH** = Quellen uneins (nicht gemittelt); **FEHLER** = Modell verletzt die Quelle.
Massstab: *dokument/lod2/laser* = absolut; *foto_intern* = bekanntes Mass im selben Foto; *modell* = zirkulaer (nur Richtung belastbar).

| Merkmal | Ist | Soll | Quelltyp | Massstab | Status | Quelle |
|---|---|---|---|---|---|---|
| Wasserdicht (1=ja) | 1.00 | 1..1 | modell | - | OK | Druckfaehigkeit |
| Anzahl getrennte Koerper | 1.00 | 1..1 | modell | - | OK | Schwebende Teile |
| Durchfahrt (tor_n_scheitel) (m) | 6.34 | 6.15..6.55 | foto_kalibriert | SfM-Neuaufbau, Rahmen = Lasermassstab 0,933 | OK | foto_mass.py --kamera/--ebene auf der Fassadenebene (Wandgerade aus der dichten Wolke), Kameras aus dem SfM-Neuaufbau; Torbogen Nord Scheitel innen 6,35 m (Foto 113310) |
| Durchfahrt (tor_s_scheitel) (m) | 6.38 | 6.2..6.6 | foto_kalibriert | SfM-Neuaufbau, Rahmen = Lasermassstab 0,933 | OK | foto_mass.py --kamera/--ebene auf der Fassadenebene (Wandgerade aus der dichten Wolke), Kameras aus dem SfM-Neuaufbau; Torbogen Sued Scheitel innen 6,39 m (Foto commons 217) |

## Belegt durch

- **modell**: 2 von 2 Pruefungen gruen (Druckbarkeit, keine Realitaetsaussage)
- **foto_kalibriert**: 2 von 2 Pruefungen gruen (Kamera aus amtlichen Ankern (LoD2/DOM1), Pixel->Meter auf bekannter Ebene; +-0,1-0,3 m je Mass, +-1 m systematisch in der Hoehe (Ankerhoehen))

## Elemente des Generators: 9 belegt, 0 Annahmen

- dach: Dach Teil 0 (sattel_a) - Laser DOM1 (tools/dach_vermessen.py) ueber LoD2 DEBW_0010007Tvdv-Grundriss Teil 0
- wand: Grundriss Teil 0 - LoD2 DEBW_0010007Tvdv GroundSurface 0
- dach: Dach Teil 1 (sattel_b) - Laser DOM1 (tools/dach_vermessen.py) ueber LoD2 DEBW_0010007Tvdv-Grundriss Teil 1
- wand: Grundriss Teil 1 - LoD2 DEBW_0010007Tvdv GroundSurface 1
- dach: Dach Teil 2 (sattel_b) - Laser DOM1 (tools/dach_vermessen.py) ueber LoD2 DEBW_0010007Tvdv-Grundriss Teil 2
- wand: Grundriss Teil 2 - LoD2 DEBW_0010007Tvdv GroundSurface 2
- wand: Relief Fassade nord (Teil 1) mit Auskragungen - OpenMVS-Netz der neuen dichten Wolke (rc-park_daten/schwab_v3/sfm_neu/openmvs), Hoehenbild 5 cm
- wand: Relief Fassade sued (Teil 1) mit Auskragungen - OpenMVS-Netz der neuen dichten Wolke (rc-park_daten/schwab_v3/sfm_neu/openmvs), Hoehenbild 5 cm
- wand: Durchfahrt (zweiter Torbogen) Nord und Sued - foto_mass.py auf den Fassadenebenen, Fotos 113310 (Nord) und commons 217 (Sued): M-113310-001..-004, M-commons217-001..-003

## Beobachtungen ohne Pruefung

- heute Anlage: Quellen sichten: Dokumente (Hoehe), LoD2 (Grundriss/Traufe), DOM1 (Dachform), Fotos je Seite -> objekt.json/quellen fuellen, Zeilen mit Quelle anlegen
- 2026-11-15 Claude: Durchfahrt: die halbe lichte Breite (Nord 3,20 m, Sued 3,15 m; M-113310-001, M-commons217-001) laesst sich an diesem Objekt nicht pruefen - der turmseitige Pfeiler liegt bei u 6,5 und damit AUSSERHALB des LoD2-Grundrisses dieses Hauses (Hausende u 6,35): der Bogen ueberspannt das ganze Erdgeschoss, die Pfeiler gehoeren zum Turm bzw. zur Nachbarwand. Zwei falsch gestellte Pruefungen wieder entfernt. -> Pfeiler der Durchfahrt als eigene Bauteile (am Turm-Eck und am Ostende) aus Fotokanten bauen, dann Breite pruefen; zweite Bogenhaelfte in einem Foto von Osten messen (Symmetrie ist ANNAHME)

## Grenze

Offene Daten (Laser 1 m, Fotos +-5-10 %, Dokumente mit unklarer Bezugshoehe) beweisen keine Masse auf den Zentimeter.
Dieser Nachweis sagt je Mass, welche Quelle es stuetzt und wie belastbar der Massstab ist; mehr ist ehrlich nicht moeglich.
