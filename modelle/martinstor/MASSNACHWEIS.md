# Massnachweis Martinstor (automatisch aus masstabelle.json, 2026-11-01)

Status je Mass: **OK** = Istwert im Sollbereich der Quelle; **WIDERSPRUCH** = Quellen uneins (nicht gemittelt); **FEHLER** = Modell verletzt die Quelle.
Massstab: *dokument/lod2/laser* = absolut; *foto_intern* = bekanntes Mass im selben Foto; *modell* = zirkulaer (nur Richtung belastbar).

| Merkmal | Ist | Soll | Quelltyp | Massstab | Status | Quelle |
|---|---|---|---|---|---|---|
| Tuermchen-Spitze Hoehe (m) | 41.35 | 40.7..41.8 | laser_dom1 | laser | OK | Laser DOM1: lokale Maxima 40,9 und 41,4 m (Journal 12: 43,6 war OSM) |
| Tuermchen-Kegel Durchmesser 2 m unter Spitze (m) | 0.48 | 0.4..1.2 | foto_verhaeltnis | modell | OK | Foto 043/044 + Journal 10/6: Kegel schlank; Nutzer 'zu gedrungen' 2026-10-31 |
| Tuermchen-Kegel Durchmesser 4 m unter Spitze (m) | 1.14 | 0.8..1.7 | foto_verhaeltnis | modell | OK | Foto 043/044, Journal 6/10: Kegel ca. 3:1 |
| Tuermchen Anzahl (Querschnitte 2 m unter Spitze) | 4.00 | 4..4 | foto_verhaeltnis | - | OK | Fotos: 4 Ecktuermchen |
| Dachreiter Dicke bei 50 m (m) | 0.18 | 0.08..0.4 | foto_vollbild | modell | OK | Foto 049 Vollbild: Nadel 0,08-0,14 m, Mast 0,09-0,26 m (+Druck-Untergrenze); DOM1 verschmiert Nadel |
| Dachreiter Dicke bei 52 m (m) | 0.16 | 0.08..0.3 | foto_vollbild | modell | OK | wie oben |
| Dachreiter Knauf Durchmesser (m) | 0.66 | 0.5..0.9 | foto_vollbild | modell | OK | Foto 049: 44 px x 1,5 cm = ~0,67 m |
| Dachreiter Knauf Lage (Anteil ueber First) | 0.19 | 0.12..0.32 | foto_verhaeltnis | - | OK | Foto 049/000: Knauf bei ~20-28 % der Spitzenlaenge |
| Gesamthoehe (m) | 60.00 | 59.5..66 | dokument | dokument | OK | Bauforschung BW (Landesdenkmalamt) 60 m nach 1901 / 65 m Objektbeschreibung; en.Wikipedia 60 m; Structurae ~65 m; de.Wikipedia 66 m (Plan Schaefer) |
| Dachansatz / Glockenstock-Oberkante (m) | 35.60 | 34.5..36.5 | laser_dom1 | laser | OK | Laser-Profil (tools/hypso_profil.py, gemeinsame Lage): bei 38/40/42/44 m hat DOM1 null Streuung (62/43/28/20 m2); Traufe 38 ergibt dort +16/+17/+12/+9 m2 (bis +40 %), Traufe 35,5 nur +4/-1/0/-2. Die Foto-Kalibrierung (37,4-38,2 m) hat oben ~1-2 m systematischen Fehler. |
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
| Dachflanke: Halbbreiten-Zunahme je m (Silhouette 38-45 m, Kamera K-030) | 0.52 | 0.4..0.56 | foto_kalibriert | foto_kalibriert | OK | tools/foto_breitenprofil.py --steigung 37,46 mit drei unabhaengigen Kameras: Foto 030 0,486 / 031 0,475 / 041 0,481; Modell 0,437-0,505. Differenz Foto-Modell hoechstens 0,05. |
| Inschrifttafel NORD Breite (m, z 7,5) | 3.35 | 3..3.8 | dokument | dokument | OK | de.wikipedia: Gedenktafel 1796 auf der Stadtseite (Nord); Foto 001; Breite 3,4 m (MASSPRUEFUNG Teil 5) |
| Keine Tafel auf SUED bei z 7,5 (m) | 0.00 | 0..0.9 | foto_vollbild | - | OK | Fotos 041/030 Vollbild: Suedwand unter dem Adler glatt (Messbereich /u/ < 2,5 m, damit die gezahnten Eckquader nicht mitzaehlen) |
| Doppeladler SUED Breite (m, z 9,45) | 1.65 | 1.3..3.2 | foto_vollbild | foto_intern | OK | Fotos 041/030: Adlerrelief rechts ueber dem Bogen, Suedseite; de.wikipedia: Toraussenseite |
| Eckturm NW Durchmesser (m, y-Ausdehnung der Punkte x<-5, z 2-9) | 2.55 | 2..2.7 | foto_vollbild | foto_intern | OK | Messprotokoll M-001-001: 2,29 m +- 0,21 (Foto 001, Massstab Tafelhoehe 2,0 m); Suedseite (Foto 000) ohne Eckturm |
| Eckturm NW Kegelspitze (m) | 14.02 | 12..15.5 | foto_vollbild | foto_intern | OK | Foto 001: Tafel 2,0 m = ~195 px -> ~97 px/m; Traufe ~5,2-5,9 m ueber Bogenscheitel (5,0 m) = ~10-11 m, Kegel ~3-3,5 m -> Spitze ~13-14,5 m (+-10 %) |
| Sockel-Grundriss Rechteck (m2, z 1 m) | 148.84 | 117..150 | lod2 | lod2 | OK | LoD2 DEBW_001000hPLcn Huellrechteck 11,7 x 11,4 m = 133 m2 (Polygon 'mit Rundung' = Eckturm enthalten; MASSPRUEFUNG Teil 9); +-12 % |
| Wasserdicht (1=ja) | 1.00 | 1..1 | modell | - | OK | Druckfaehigkeit |
| Anzahl getrennte Koerper | 1.00 | 1..1 | modell | - | OK | Schwebende Teile (Journal: 14 gefunden) |
| Laserflaeche ueber 40 m (m2, gerastert) | 42.00 | 38..48 | laser_dom1 | laser | OK | DOM1-Profil: 43 m2, Streuung 43-43 (sehr sicher, grosse Dachflaeche) |
| Silhouettenbreite bei 30 m (m, 3 Kameras) | 13.26 | 12.9..14.2 | foto_kalibriert | foto_kalibriert | OK | tools/foto_breitenprofil.py mit drei unabhaengig kalibrierten Kameras: Foto 030 13,40 m (Differenz zum Modell -0,12 m Median), Foto 031 12,56 (-0,04), Foto 041 11,12 (-0,36; andere Blickrichtung, daher anderer Absolutwert). Alle drei bestaetigen das Modell auf +-0,5 m. |
| Silhouettenbreite Zone 29-33,5 m (Kamera 031) | 11.79 | 11.2..12 | foto_kalibriert | foto_kalibriert | OK | tools/foto_breitenprofil.py, Zonenmittel ueber 29,0-33,5 m in 0,5-m-Schritten: Foto 11,59 m. Toleranz +-0,4 m (Kameraguete 0,61). Gemessen wird die LINKE Halbbreite verdoppelt - rechts verdeckt ein Nachbarhaus die Kante, das Modell wird genauso behandelt. |
| Silhouettenbreite Zone 29-31,5 m (Kamera 041) | 11.57 | 10.7..11.6 | foto_kalibriert | foto_kalibriert | OK | wie oben, Foto 041 misst 11,13 m ueber 29,0-31,5 m Gemessen wird die LINKE Halbbreite verdoppelt - rechts verdeckt ein Nachbarhaus die Kante, das Modell wird genauso behandelt. |
| Silhouettenbreite Zone 23,5-28 m (Kamera 031) | 11.51 | 11.3..12.7 | foto_kalibriert | foto_kalibriert | OK | tools/foto_breitenprofil.py: Foto 031 misst 12,30 m, Foto 030 bestaetigt die Richtung (+0,27). Toleranz +-0,7 m (eine Seite verdeckt, Kameraguete 0,61). |
| Ecktuermchen: Erkerkoerper Durchmesser bei 34 m (m) | 2.14 | 2..2.9 | foto_vollbild | modell | OK | Fotos 031/041/043 Vollbild: der achteckige Erker mit Fachwerk-Bruestung ist etwa so breit wie der Sandsteinschaft darunter (2,2-2,6 m); erst darueber beginnt der schlanke Helm |
| Ecktuermchen: Helm Durchmesser bei 37 m (m) | 1.26 | 0.8..1.9 | foto_vollbild | modell | OK | Fotos 031/041: oberhalb des Erkerdachs ist der Helm deutlich schlanker als der Erker |

## Belegt durch

- **laser_dom1**: 3 von 3 Pruefungen gruen (1-m-Raster, interpoliert, nur von oben; Strukturen < ~3 m verschmiert, Nadeln unsichtbar. BLIND auch fuer Grundriss mit Vorspruengen < ~1 m (Gesims, Erker): die Flaeche ueber Hoehe faellt dann 15-20 % zu klein aus (Martinstor 2026-11-01, Register O/P))
- **foto_verhaeltnis**: 4 von 4 Pruefungen gruen (nur Verhaeltnisse (+-5-10 %), absolute Masse nur mit bekanntem Massstab)
- **foto_vollbild**: 17 von 17 Pruefungen gruen (Vollaufloesung, Massstab aus Modell oder Dokument -> Werte grob, Richtung sicher)
- **dokument**: 2 von 2 Pruefungen gruen (Bauforschung/Denkmalamt/Wikipedia; Bezugshoehe oft unklar (60 vs 65 m))
- **foto_kalibriert**: 7 von 7 Pruefungen gruen (Kamera aus amtlichen Ankern (LoD2/DOM1), Pixel->Meter auf bekannter Ebene; +-0,1-0,3 m je Mass, +-1 m systematisch in der Hoehe (Ankerhoehen))
- **lod2**: 1 von 1 Pruefungen gruen (amtlicher Grundriss + Traufe/First, keine Aufbauten/Details)
- **modell**: 2 von 2 Pruefungen gruen (Druckbarkeit, keine Realitaetsaussage)

## Elemente des Generators: 24 belegt, 6 Annahmen

- Nord: Runder Eckturm NW mit Kegeldach - Foto 001 Vollbild (Nord); Suedseite ohne (Foto 000)
- Sued: Torbogen mit Keilsteinen - Fotos 050/030 (Sued), 001 (Nord); MASSPRUEFUNG Teil 5
- Nord: Torbogen mit Keilsteinen - Fotos 050/030 (Sued), 001 (Nord); MASSPRUEFUNG Teil 5
- Nord: Inschrifttafel 1796 - de.wikipedia: Gedenktafel auf der Stadtseite; Foto 001 (Nord)
- Sued: Doppeladler-Relief - de.wikipedia: Reichsadler an der Toraussenseite; Fotos 041/030 (Sued, rechts ueber dem Bogen)
- Sued: Giebel ueber der Uhr mit zwei konkaven Schenkeln - Foto 031 Vollbild (giebel031.jpg), Messung Scheitel 28,96 / Schenkelende 27,67 m; Nutzerhinweis 2026-11-01
- Sued: Uhr mit Giebel und Stundenmarken - Fotos 041/042 (Sued), 031/001 (Nord); MASSPRUEFUNG Teil 3
- Sued: Fenster 2 oben + 1 tiefer - Fotos 041/030/042 Vollbild (Sued)
- Nord: Giebel ueber der Uhr mit zwei konkaven Schenkeln - Foto 031 Vollbild (giebel031.jpg), Messung Scheitel 28,96 / Schenkelende 27,67 m; Nutzerhinweis 2026-11-01
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

## Beobachtungen ohne Pruefung

- 2026-11-01 Claude (Fotosichtung): Waagrechter Balken/Blende auf halber Hoehe der Schaftwand (Suedseite) -> Vollbild messen
- 2026-11-01 Claude: Ost-/Westseite (+-y) kaum fotografiert; Fenster dort sind Annahme -> Fotos der Seiten beschaffen (Mapillary/eigene)
- 2026-11-01 fehlteile_finden (Foto 030, alt vs neu) + Nutzer: Finder markierte am alten Modell die Zone Uhrgiebel/Kragdach (z 29-31 m) als FEHLT; nach Einbau von Kielbogen und Kragdach bleiben Treffer nahe der Uhr-Oberkante (Kamera K-030 ~0,5-1 m versetzt) und an der SE-Kante (Eckquader-Muster: Foto hat Quader in jeder Lage, Modell gezahnt nur jede zweite). -> Kamera mit praezisen Picks neu loesen, dann Finder erneut; Eckquader-Muster am Vollbild pruefen
- auto fehlteile_finden (Foto 041, Treffer 2): Foto zeigt Struktur ohne Modellgegenstueck bei z=39.6 m, y=0.92 m (Zelle [873, 582, 97], Score +1.00) -> audit/fehlteile_041.jpg Treffer 2 ansehen, Element benennen, Zeile + beleg()
- auto fehlteile_finden (Foto 041, Treffer 1): Foto zeigt Struktur ohne Modellgegenstueck bei z=42.73 m, y=0.86 m (Zelle [873, 485, 97], Score +1.00) -> audit/fehlteile_041.jpg Treffer 1 ansehen, Element benennen, Zeile + beleg()
- auto foto_breitenprofil (Foto 030, Kamera K-030): Silhouettenbreite z 35.0-35.5 m: Foto 12.11 m, Modell 12.73 m (-0.62 m) -> tools/beobachtungen_sichten.py entscheidet, ob mehrere Fotos einig sind
- auto foto_breitenprofil (Foto 030, Kamera K-030): Silhouettenbreite z 39.5-41.0 m: Foto 9.30 m, Modell 8.17 m (+1.13 m) -> tools/beobachtungen_sichten.py entscheidet, ob mehrere Fotos einig sind
- auto foto_breitenprofil (Foto 030, Kamera K-030): Silhouettenbreite z 44.5-46.5 m: Foto 2.94 m, Modell 3.74 m (-0.80 m) -> tools/beobachtungen_sichten.py entscheidet, ob mehrere Fotos einig sind
- auto fehlteile_finden (Foto 030, Treffer 1): Foto zeigt Struktur ohne Modellgegenstueck bei z=28.2 m, y=4.68 m (Zelle [1260, 945, 63], Score +1.00) -> audit/fehlteile_030.jpg Treffer 1 ansehen, Element benennen, Zeile + beleg()
- auto fehlteile_finden (Foto 030, Treffer 2): Foto zeigt Struktur ohne Modellgegenstueck bei z=16.56 m, y=5.18 m (Zelle [1323, 1512, 63], Score +1.00) -> audit/fehlteile_030.jpg Treffer 2 ansehen, Element benennen, Zeile + beleg()
- auto fehlteile_finden (Foto 030, Treffer 3): Foto zeigt Struktur ohne Modellgegenstueck bei z=10.0 m, y=5.55 m (Zelle [1386, 1890, 63], Score +1.00) -> audit/fehlteile_030.jpg Treffer 3 ansehen, Element benennen, Zeile + beleg()
- auto fehlteile_finden (Foto 030, Treffer 6): Foto zeigt Struktur ohne Modellgegenstueck bei z=9.13 m, y=5.57 m (Zelle [1386, 1953, 63], Score +1.00) -> audit/fehlteile_030.jpg Treffer 6 ansehen, Element benennen, Zeile + beleg()
- auto foto_breitenprofil (Foto 031, Kamera K-031): Silhouettenbreite z 23.5-28.0 m: Foto 12.32 m, Modell 11.51 m (+0.81 m) -> tools/beobachtungen_sichten.py entscheidet, ob mehrere Fotos einig sind
- auto foto_breitenprofil (Foto 031, Kamera K-031): Silhouettenbreite z 31.5-33.5 m: Foto 10.98 m, Modell 11.57 m (-0.59 m) -> tools/beobachtungen_sichten.py entscheidet, ob mehrere Fotos einig sind
- auto foto_breitenprofil (Foto 031, Kamera K-031): Silhouettenbreite z 36.0-37.5 m: Foto 10.75 m, Modell 9.96 m (+0.79 m) -> tools/beobachtungen_sichten.py entscheidet, ob mehrere Fotos einig sind
- auto foto_breitenprofil (Foto 031, Kamera K-031): Silhouettenbreite z 46.5-47.0 m: Foto 0.51 m, Modell 3.11 m (-2.60 m) -> tools/beobachtungen_sichten.py entscheidet, ob mehrere Fotos einig sind
- auto foto_breitenprofil (Foto 031, Kamera K-031): Silhouettenbreite z 48.0-48.0 m: Foto 1.32 m, Modell 0.24 m (+1.08 m) -> tools/beobachtungen_sichten.py entscheidet, ob mehrere Fotos einig sind
- auto foto_breitenprofil (Foto 041, Kamera K-041): Silhouettenbreite z 35.0-35.5 m: Foto 11.78 m, Modell 11.12 m (+0.66 m) -> tools/beobachtungen_sichten.py entscheidet, ob mehrere Fotos einig sind
- auto foto_breitenprofil (Foto 041, Kamera K-041): Silhouettenbreite z 47.0-48.0 m: Foto 1.37 m, Modell 3.04 m (-1.67 m) -> tools/beobachtungen_sichten.py entscheidet, ob mehrere Fotos einig sind
- 2026-11-01 Nutzer + tools/messung_pruefen.py: Nutzer: Uhr sitzt zu weit oben, und ueber der Uhr gehoert ein Giebel mit ZWEI KONKAV eingezogenen Schenkeln (Modell hat eine S-Kurve). Messung der Uhrhoehe ist UNGUELTIG: absolut 24,77/26,79/27,81 m (Streuung 3,0 m), Kante darueber 1,22/4,54/0,04 m - die Fotos treffen nicht dasselbe Merkmal. -> Messverfahren reparieren: Zinnen-Unterkante je Foto als Anker picken (tools/foto_pick.py) statt 'staerkste Kante' zu raten, dann Abstand Zifferblatt-Zinnen in allen drei Fotos; erst bei gueltiger Messung UZ aendern. Der konkave Giebel ist davon unabhaengig und kann sofort gebaut werden.

## Grenze

Offene Daten (Laser 1 m, Fotos +-5-10 %, Dokumente mit unklarer Bezugshoehe) beweisen keine Masse auf den Zentimeter.
Dieser Nachweis sagt je Mass, welche Quelle es stuetzt und wie belastbar der Massstab ist; mehr ist ehrlich nicht moeglich.
