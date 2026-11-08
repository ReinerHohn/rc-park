# Massnachweis Historisches Kaufhaus Freiburg (automatisch aus masstabelle.json, 2026-11-05)

Status je Mass: **OK** = Istwert im Sollbereich der Quelle; **WIDERSPRUCH** = Quellen uneins (nicht gemittelt); **FEHLER** = Modell verletzt die Quelle.
Massstab: *dokument/lod2/laser* = absolut; *foto_intern* = bekanntes Mass im selben Foto; *modell* = zirkulaer (nur Richtung belastbar).

| Merkmal | Ist | Soll | Quelltyp | Massstab | Status | Quelle |
|---|---|---|---|---|---|---|
| Wasserdicht (1=ja) | 1.00 | 1..1 | modell | - | OK | Druckfaehigkeit |
| Anzahl getrennte Koerper | 1.00 | 1..1 | modell | - | OK | Schwebende Teile |
| Dachebene an der Nordwand, u = 4 m (m) | 12.17 | 11.2..12.3 | lod2 | lod2 | OK | LoD2 Dachflaeche an der Nordwand 11,65 m ueber rahmen.gelaende (+0,43 LoD2-Boden = 12,08 im Pruefstand), DOM1-Schnitt deckungsgleich; Stuetze Foto 018: Rinne 10,77 +-0,88 m ~0,6 m vor der Wand (M-018-001) |
| First, Mitte (m) | 21.43 | 21..21.8 | lod2 | lod2 | OK | LoD2 DEBW_0010007Tv9r First 20,97 m ueber rahmen.gelaende (+0,43 bis LoD2-Boden), DOM1-Schnitt First 20,8 m (gleiche Lage) |

## Belegt durch

- **modell**: 2 von 2 Pruefungen gruen (Druckbarkeit, keine Realitaetsaussage)
- **lod2**: 2 von 2 Pruefungen gruen (amtlicher Grundriss + Traufe/First, keine Aufbauten/Details)

## Elemente des Generators: 9 belegt, 0 Annahmen

- dach: Rumpf + Dach aus LoD2 (je Dachflaeche Prisma unter der Dachebene, auf Grundriss begrenzt) - LoD2 DEBW_0010007Tv9r (LGL BW), 6 Dachflaechen, 3 Grundflaechen
- dach: Treppengiebel: 2 Giebel (6 LoD2-Wandstuecke), je 7 Stufen je Flanke + Spitze, Kappe 0.35 m, Spitze 1.0 m ueber First, Scheibe 0.60 m - Stufenzahl: Z-050-001, Z-043-001 (Regel 9); Giebelwaende/First/Neigung LoD2; Kappe/Spitze/Dicke ANNAHME aus Fotos 050/043 (Stufe ueberragt die Dachflaeche um ~eine Kappe, Spitze ~1 m)
- Nord: Traufueberstand: Dachebene bis zur Rinne 10.42 m verlaengert, Ueberstand 0.84 m - Foto 018 (fassade_nord.json): Rinne (M-018-001); Dachneigung LoD2; Rinne in Fotomitte (x 1960) bei y 690 (M-018-001); DOM1-Kante 1-2 m vor der LoD2-Wand bestaetigt Ueberstand
- Nord: Arkade: 4 Segmentboegen, Kaempfer 2.64 m, Scheitel 4.00 m, Tiefe 4.4 m - Foto 018 (fassade_nord.json), Zaehlung Z-018-001; Pfeilerkanten bei y 1900, Kaempfer (Bogenansatz am Pfeiler) und Scheitel (Laibung) abgelesen; Segmentboegen; Tiefe: Dichte Wolke kaufhaus_null (Frontkoordinaten, Wandebene s0): Arkaden-Rueckwand +3,9 m, Erker -0,8..-1,1 m, Galerie -0,66 m, x 1,13 (Erkerabstand Foto 18,8 m / Wolke 16,7 m; Wolke ist zu klein, Register Kaufhaus 2026-11-04). ANNAHME +-20 %; Fensternische ANNAHME
- Nord: Fenster: 5 Stueck, je 3 Felder, Bruestung 6.33 / Sturz 8.65 m, Nische 0.25 m - Foto 018 (fassade_nord.json), Zaehlung Z-018-002; Fensterkanten, Unterkante (= Galerie-Handlauf), Sturz (Vorhangbogen-Tiefpunkt), Spitzen; 3 Felder je Fenster (2 Pfosten) am Foto; Nische ANNAHME
- Nord: Figuren: 4 auf Konsole mit Baldachin, Figur 6.87-8.71 m - Foto 018 (fassade_nord.json), Zaehlung Z-018-003; Figurenmitte, Konsole unten, Baldachin oben; Figur als Kegelstumpf (ANNAHME Detailgrad H0)
- Nord: Galerie: Platte 5.30 m, Handlauf 6.33 m, Vorsprung 0.75 m, Laenge 15.0 m - Foto 018 (fassade_nord.json); Galerie-Platte unten und Handlauf; Vorsprung: Dichte Wolke kaufhaus_null (Frontkoordinaten, Wandebene s0): Arkaden-Rueckwand +3,9 m, Erker -0,8..-1,1 m, Galerie -0,66 m, x 1,13 (Erkerabstand Foto 18,8 m / Wolke 16,7 m; Wolke ist zu klein, Register Kaufhaus 2026-11-04). ANNAHME +-20 %; Fensternische ANNAHME; Docken als volle Bruestung (ANNAHME H0)
- Nord: Eckerker: 2 polygonal (Schraege-Front-Schraege), Vorsprung 0.90 m, Koerper 5.03-8.82 m, Konsole bis 3.87 m, Helm bis 14.8 m - Foto 018 (fassade_nord.json), Zaehlung Z-018-004; Erkerkanten (3 Facetten: Schraege-Front-Schraege), Konsolenspitze, Wappenband unten, Erkergesims, Helmspitze; Fussueberstand ANNAHME; Vorsprung: Dichte Wolke kaufhaus_null (Frontkoordinaten, Wandebene s0): Arkaden-Rueckwand +3,9 m, Erker -0,8..-1,1 m, Galerie -0,66 m, x 1,13 (Erkerabstand Foto 18,8 m / Wolke 16,7 m; Wolke ist zu klein, Register Kaufhaus 2026-11-04). ANNAHME +-20 %; Fensternische ANNAHME
- dach: Gauben Nordseite: 5 in 2 Reihen (3+2), auf der LoD2-Dachflaeche - Foto 018 (fassade_nord.json), Zaehlung Z-018-005, Z-018-006; Gaubenmitten am Foto; Lage auf der Dachflaeche ueber Kamera-Abstand und LoD2-Dachneigung zurueckgerechnet (ANNAHME Augenhoehe Bildmitte); Gaubengroesse ANNAHME aus Pixel (~120 px breit)

## Seiten

- Nord: KEIN FOTO - ungeprueft

## Beobachtungen ohne Pruefung

- heute Anlage: Quellen sichten: Dokumente (Hoehe), LoD2 (Grundriss/Traufe), DOM1 (Dachform), Fotos je Seite -> teilweise erledigt 2026-11-03: LoD2/DOM1/DGM1 + Anker (objekt_daten.py), 126 Fotos (bilder_holen Kaltstart), SfM-Netz 76 Kameras + dichte Wolke 200k Punkte (nullstart, sfm_lod2_ausrichten); offen: Zeilen mit Quelle anlegen, Fotos je Seite (Rueckseite fehlt)
- 2026-11-03 Claude (eigene Sichtpruefung, audit/wolke_dicht_nord.jpg + _quer.jpg): Dichte Wolke (Nullstart kaufhaus_null, automatisch an LoD2/DGM1 ausgerichtet, ohne Picks): Fassadenbreite Nord ~18,5 m passt zur LoD2-Front (~18,3 m), aber Traufe/Dachansatz der Wolke liegt bei ~8,5-9 m, LoD2-Frontwand reicht bis ~11,7 m (LoD2 traufe_m min 9,65). Breite passt, Hoehe nicht -> Widerspruch Wolke vs LoD2 (Regel 5: nicht mitteln). -> 2026-11-04 geklaert (Sichtbeobachtung -> Messung): DOM1 mit EXAKTER Pixelmitte (tfw 414000,5/5316999,5; frueher 1,1 m versetzt gelesen) liegt deckungsgleich auf der LoD2-Dachflaeche (First 20,8 vs 20,97, Neigung ~52 Grad). Foto 018 frontal: Traufe 10,77 +-0,88 m (M-018-001). Foto + DOM1 + LoD2 einig -> Rumpf/Dach aus LoD2 bleibt. WIDERSPRUCH: Wolke-Dach liegt 3,35 m (MAD 0,27) unter DOM1; Nachbarfassaden passen bei jetziger Lage (Median 0,15 m) -> Wolke ist im Massstab/vertikal falsch (Erker-Abstand Wolke 17,3 m vs LoD2-Front 20,34 m -> ~0,85); Fassadenpunkte nur entlang einer Linie bestimmen den Massstab nicht. Naechster Schritt: sfm_lod2_ausrichten um DOM1-Dachhoehen als Ziel erweitern (Klassen gleich gewichten), dann Wolke neu transformieren; Fassadendetails bis dahin aus Foto 018 (foto_mass).
- 2026-11-04 Nutzer: 3D-Ansicht Kaufhaus (Fotofarben): 'viel zu dunkel, viel zu grob' -> messen: (a) Helligkeit Render vs. Fotopixel derselben Flaechen (Median-Luminanz-Verhaeltnis, Soll ~1), (b) Texelgroesse (Soll <= 3 cm/Texel H0-Vorschau statt 25 cm Eckenfarbe); Ursachen-Verdacht: Viewer sRGB->linear ohne Rueckwandlung + Lambert-Schattierung auf bereits belichteten Fotofarben; Eckenfarben auf 25-cm-Netz statt Texturatlas

## Grenze

Offene Daten (Laser 1 m, Fotos +-5-10 %, Dokumente mit unklarer Bezugshoehe) beweisen keine Masse auf den Zentimeter.
Dieser Nachweis sagt je Mass, welche Quelle es stuetzt und wie belastbar der Massstab ist; mehr ist ehrlich nicht moeglich.
