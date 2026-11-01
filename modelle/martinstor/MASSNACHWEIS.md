# Massnachweis Martinstor (automatisch aus masstabelle.json, 2026-11-01)

Status je Mass: **OK** = Istwert im Sollbereich der Quelle; **WIDERSPRUCH** = Quellen uneins (nicht gemittelt); **FEHLER** = Modell verletzt die Quelle.
Massstab: *dokument/lod2/laser* = absolut; *foto_intern* = bekanntes Mass im selben Foto; *modell* = zirkulaer (nur Richtung belastbar).

| Merkmal | Ist | Soll | Quelltyp | Massstab | Status | Quelle |
|---|---|---|---|---|---|---|
| Tuermchen-Spitze Hoehe (m) | 41.35 | 40.7..41.8 | laser_dom1 | laser | OK | Laser DOM1: lokale Maxima 40,9 und 41,4 m (Journal 12: 43,6 war OSM) |
| Tuermchen-Kegel Durchmesser 2 m unter Spitze (m) | 0.59 | 0.4..1.2 | foto_verhaeltnis | modell | OK | Foto 043/044 + Journal 10/6: Kegel schlank; Nutzer 'zu gedrungen' 2026-10-31 |
| Tuermchen-Kegel Durchmesser 4 m unter Spitze (m) | 1.42 | 0.8..1.7 | foto_verhaeltnis | modell | OK | Foto 043/044, Journal 6/10: Kegel ca. 3:1 |
| Tuermchen Anzahl (Querschnitte 2 m unter Spitze) | 4.00 | 4..4 | foto_verhaeltnis | - | OK | Fotos: 4 Ecktuermchen |
| Dachreiter Dicke bei 50 m (m) | 0.18 | 0.08..0.4 | foto_vollbild | modell | OK | Foto 049 Vollbild: Nadel 0,08-0,14 m, Mast 0,09-0,26 m (+Druck-Untergrenze); DOM1 verschmiert Nadel |
| Dachreiter Dicke bei 52 m (m) | 0.16 | 0.08..0.3 | foto_vollbild | modell | OK | wie oben |
| Dachreiter Knauf Durchmesser (m) | 0.66 | 0.5..0.9 | foto_vollbild | modell | OK | Foto 049: 44 px x 1,5 cm = ~0,67 m |
| Dachreiter Knauf Lage (Anteil ueber First) | 0.19 | 0.12..0.32 | foto_verhaeltnis | - | OK | Foto 049/000: Knauf bei ~20-28 % der Spitzenlaenge |
| Gesamthoehe (m) | 60.00 | 59.5..66 | dokument | dokument | OK | Bauforschung BW (Landesdenkmalamt) 60 m nach 1901 / 65 m Objektbeschreibung; en.Wikipedia 60 m; Structurae ~65 m; de.Wikipedia 66 m (Plan Schaefer) |
| Dachansatz / Glockenstock-Oberkante (m) | 35.60 | 36.9..39.2 | foto_kalibriert | foto_kalibriert | WIDERSPRUCH | Messprotokoll M-030-003 (Foto 030, Kamera K-030 aus LoD2/DOM1-Ankern): 37,9-38,2 m; LoD2-Wandoberkante 37,1-37,3 m / Messung: erste Hoehe ab 33,0 m (ueber dem Kragdach), bei der die Dachbreite im Achsstreifen 6,8 m erreicht |
| First / Dach-Oberkante (m) | 46.70 | 46.6..48.7 | foto_kalibriert | foto_kalibriert | OK | Messprotokoll M-030-002: Goldkugeln 47,4-47,9 m; Foto-IoU-Trend J2/J5 (First +1,6 besser) / Messung: hoechste Hoehe, bei der der Dachkoerper im Achsstreifen noch >= 2 m breit ist |
| Zinnenkranz Oberkante (m) | 31.85 | 29.5..32.5 | foto_kalibriert | foto_kalibriert | OK | Messprotokoll M-030-005: Kranzecken 30,2 / 31,2 m; Laser Stufe 31-32 m / Messung: hoechster Punkt der Suedwand-Mitte (/y/<3, Erker bei y=+-4,3 ausgeblendet) unter 34 m |
| Spitzenlaenge ueber First (m) | 13.30 | 12..16.5 | foto_vollbild | modell | OK | Foto 049 Vollbild 16,6 / 014: 16,0 / 000: 12,4 m (Massstab aus Modellmassen, grob); Register J3 |
| Fenster obere Reihe Suedseite (Anzahl, z 22,1 m) | 2.00 | 2..2 | foto_vollbild | - | OK | Fotos 041/030/042 Vollbild (Suedseite = Adlerseite): zwei Schlitzfenster unter der Uhr |
| Fenster untere Reihe Suedseite (Anzahl, z 18,5 m) | 1.00 | 1..1 | foto_vollbild | - | OK | Fotos 041/030 Vollbild: ein Fenster tiefer, rechts der Mitte |
| Fenster obere Reihe Nordseite (Anzahl, z 22,1 m) | 3.00 | 3..3 | foto_vollbild | - | OK | Fotos 031 + 001 Vollbild (Nordseite = Tafelseite): drei Fenster in einer Reihe |
| Fenster untere Reihe Nordseite (Anzahl, z 18,5 m) | 1.00 | 1..1 | foto_vollbild | - | OK | Fotos 031 + 001 Vollbild: ein Schlitz tiefer in der Mitte |
| Zinnen-Scharten Suedseite (Anzahl, z 31,1 m) | 4.00 | 4..4 | foto_vollbild | - | OK | Foto 031/041 Vollbild: 5 Zinnen = 4 Scharten je Seite (Zinnen selbst verschmelzen im STL mit den Erkern) |
| Zinnen-Scharten Nordseite (Anzahl, z 31,1 m) | 4.00 | 4..4 | foto_vollbild | - | OK | wie oben |
| Uhr Zifferblatt-Nische Suedseite (Breite m) | 4.45 | 3.9..5.2 | foto_vollbild | lod2 | OK | MASSPRUEFUNG Teil 3: Zifferblatt 158 px / 35,3 px/m = 4,5 m (Foto 042), +-12 % |
| Dachflanke Halbbreiten-Zunahme je m (Ansicht y, 37->45 m) | 0.21 | 0.11..0.19 | foto_vollbild | - | WIDERSPRUCH | Foto 049 Vollbild: Breite +0,305 px je px -> 0,15 je Seite; Foto 000 und 014: 0,125 (foto_spitze_vollbild, Register J3). Modell 0,21 = Dach laeuft zu schnell zu |
| Inschrifttafel NORD Breite (m, z 7,5) | 3.35 | 3..3.8 | dokument | dokument | OK | de.wikipedia: Gedenktafel 1796 auf der Stadtseite (Nord); Foto 001; Breite 3,4 m (MASSPRUEFUNG Teil 5) |
| Keine Tafel auf SUED bei z 7,5 (m) | 0.00 | 0..0.9 | foto_vollbild | - | OK | Fotos 041/030 Vollbild: Suedwand unter dem Adler glatt (Messbereich /u/ < 2,5 m, damit die gezahnten Eckquader nicht mitzaehlen) |
| Doppeladler SUED Breite (m, z 9,45) | 1.65 | 1.3..3.2 | foto_vollbild | foto_intern | OK | Fotos 041/030: Adlerrelief rechts ueber dem Bogen, Suedseite; de.wikipedia: Toraussenseite |
| Eckturm NW Durchmesser (m, y-Ausdehnung der Punkte x<-5, z 2-9) | 2.55 | 2..2.7 | foto_vollbild | foto_intern | OK | Messprotokoll M-001-001: 2,29 m +- 0,21 (Foto 001, Massstab Tafelhoehe 2,0 m); Suedseite (Foto 000) ohne Eckturm |
| Eckturm NW Kegelspitze (m) | 14.02 | 12..15.5 | foto_vollbild | foto_intern | OK | Foto 001: Tafel 2,0 m = ~195 px -> ~97 px/m; Traufe ~5,2-5,9 m ueber Bogenscheitel (5,0 m) = ~10-11 m, Kegel ~3-3,5 m -> Spitze ~13-14,5 m (+-10 %) |
| Sockel-Grundriss Rechteck (m2, z 1 m) | 148.84 | 117..150 | lod2 | lod2 | OK | LoD2 DEBW_001000hPLcn Huellrechteck 11,7 x 11,4 m = 133 m2 (Polygon 'mit Rundung' = Eckturm enthalten; MASSPRUEFUNG Teil 9); +-12 % |
| Wasserdicht (1=ja) | 1.00 | 1..1 | modell | - | OK | Druckfaehigkeit |
| Anzahl getrennte Koerper | 1.00 | 1..1 | modell | - | OK | Schwebende Teile (Journal: 14 gefunden) |

## Belegt durch

- **laser_dom1**: 1 von 1 Pruefungen gruen (1-m-Raster, nur von oben; Strukturen < ~3 m verschmiert, Nadeln unsichtbar)
- **foto_verhaeltnis**: 4 von 4 Pruefungen gruen (nur Verhaeltnisse (+-5-10 %), absolute Masse nur mit bekanntem Massstab)
- **foto_vollbild**: 15 von 16 Pruefungen gruen (Vollaufloesung, Massstab aus Modell oder Dokument -> Werte grob, Richtung sicher)
- **dokument**: 2 von 2 Pruefungen gruen (Bauforschung/Denkmalamt/Wikipedia; Bezugshoehe oft unklar (60 vs 65 m))
- **foto_kalibriert**: 2 von 3 Pruefungen gruen (Kamera aus amtlichen Ankern (LoD2/DOM1), Pixel->Meter auf bekannter Ebene; +-0,1-0,3 m je Mass, +-1 m systematisch in der Hoehe (Ankerhoehen))
- **lod2**: 1 von 1 Pruefungen gruen (amtlicher Grundriss + Traufe/First, keine Aufbauten/Details)
- **modell**: 2 von 2 Pruefungen gruen (Druckbarkeit, keine Realitaetsaussage)

## Elemente des Generators: 24 belegt, 6 Annahmen

- Nord: Runder Eckturm NW mit Kegeldach - Foto 001 Vollbild (Nord); Suedseite ohne (Foto 000)
- Sued: Torbogen mit Keilsteinen - Fotos 050/030 (Sued), 001 (Nord); MASSPRUEFUNG Teil 5
- Nord: Torbogen mit Keilsteinen - Fotos 050/030 (Sued), 001 (Nord); MASSPRUEFUNG Teil 5
- Nord: Inschrifttafel 1796 - de.wikipedia: Gedenktafel auf der Stadtseite; Foto 001 (Nord)
- Sued: Doppeladler-Relief - de.wikipedia: Reichsadler an der Toraussenseite; Fotos 041/030 (Sued, rechts ueber dem Bogen)
- Sued: Kielbogen-Daechlein ueber der Uhr - Fotos 031/041 Vollbild (uhr031.jpg); Nutzerhinweis 2026-11-01
- Sued: Uhr mit Giebel und Stundenmarken - Fotos 041/042 (Sued), 031/001 (Nord); MASSPRUEFUNG Teil 3
- Sued: Fenster 2 oben + 1 tiefer - Fotos 041/030/042 Vollbild (Sued)
- Nord: Kielbogen-Daechlein ueber der Uhr - Fotos 031/041 Vollbild (uhr031.jpg); Nutzerhinweis 2026-11-01
- Nord: Uhr mit Giebel und Stundenmarken - Fotos 041/042 (Sued), 031/001 (Nord); MASSPRUEFUNG Teil 3
- Nord: Fenster 3 in Reihe + 1 Schlitz - Fotos 031/001 Vollbild (Nord)
- Ost: Fenster 2 oben + 1 tiefer - ANNAHME: Ost/West nicht fotografiert
- West: Fenster 2 oben + 1 tiefer - ANNAHME: Ost/West nicht fotografiert
- Sued: Zinnenkranz 5 Zinnen - Fotos 041 (Sued), 031 (Nord)
- Nord: Zinnenkranz 5 Zinnen - Fotos 041 (Sued), 031 (Nord)
- Ost: Zinnenkranz 5 Zinnen - ANNAHME: Ost/West nicht fotografiert
- West: Zinnenkranz 5 Zinnen - ANNAHME: Ost/West nicht fotografiert
- dach: Kragdach (Kupferschraege) ueber dem Zinnenkranz bis zum Glockenstock - Fotos 031/041/043 Vollbild; Nutzerhinweis 2026-11-01
- Sued: Glockenstock mit 2 Schallarkaden - Fotos 041/043 (Sued), 031 (Nord)
- Nord: Glockenstock mit 2 Schallarkaden - Fotos 041/043 (Sued), 031 (Nord)
- Ost: Glockenstock mit 2 Schallarkaden - ANNAHME: Ost/West nicht fotografiert
- West: Glockenstock mit 2 Schallarkaden - ANNAHME: Ost/West nicht fotografiert
- dach: Dachreiter: Mast, Knauf, Nadel - Foto 049 Vollbild; Bauforschung BW 60 m
- dach: 4 Ecktuermchen mit Kegel - Fotos 041/043/044; Laser DOM1 Spitzen 41 m

## Seiten

- Nord: Fotos vorhanden
- Ost: KEIN FOTO - ungeprueft
- Sued: Fotos vorhanden
- West: KEIN FOTO - ungeprueft

## Offene Widersprueche

- Dachansatz / Glockenstock-Oberkante (m): Foto-Kalibrierung K-030: 37,4-38,2 m und LoD2-Wandoberkante 37,2 (generalisiert) GEGEN Laser-Hypsometrie: Traufe 38 verschlechtert Ziel 14,3->27,3 % (V1) bzw. 19,6 % (V2 mit First 47,6); Foto-IoU +0,003 (Rauschen, Nordfotos schlechter). Modell 35,5 bleibt. Register M9.
- Dachflanke Halbbreiten-Zunahme je m (Ansicht y, 37->45 m): Laser (optimierung_validieren, steilere Flanke 0,15): Ziel 14,3->13,8 und M2 13,9->13,4 besser, aber M1 16,1->18,4 und M3 16,1->18,0 schlechter; Foto-IoU +0,002 (Rauschen). Register J6. Bleibt 0,21 bis eine Quelle entscheidet.

## Beobachtungen ohne Pruefung

- 2026-11-01 Claude (Fotosichtung): Waagrechter Balken/Blende auf halber Hoehe der Schaftwand (Suedseite) -> Vollbild messen
- 2026-11-01 Claude: Ost-/Westseite (+-y) kaum fotografiert; Fenster dort sind Annahme -> Fotos der Seiten beschaffen (Mapillary/eigene)
- 2026-11-01 fehlteile_finden (Foto 030, alt vs neu) + Nutzer: Finder markierte am alten Modell die Zone Uhrgiebel/Kragdach (z 29-31 m) als FEHLT; nach Einbau von Kielbogen und Kragdach bleiben Treffer nahe der Uhr-Oberkante (Kamera K-030 ~0,5-1 m versetzt) und an der SE-Kante (Eckquader-Muster: Foto hat Quader in jeder Lage, Modell gezahnt nur jede zweite). -> Kamera mit praezisen Picks neu loesen, dann Finder erneut; Eckquader-Muster am Vollbild pruefen

## Grenze

Offene Daten (Laser 1 m, Fotos +-5-10 %, Dokumente mit unklarer Bezugshoehe) beweisen keine Masse auf den Zentimeter.
Dieser Nachweis sagt je Mass, welche Quelle es stuetzt und wie belastbar der Massstab ist; mehr ist ehrlich nicht moeglich.
