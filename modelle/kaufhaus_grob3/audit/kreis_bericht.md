# Kreis r1 20261110_173101 - fensterreihe:eg1_tuer (Portal Tuerblatt/Gold)

## 1. Formbeschreibung (Stufe 0)
Fotos angesehen: 6207 (Nahfoto frontal), 6243 (Schraegfoto links, Uebersicht Laube), 6120 (Uebersicht, nur im Overlay, nicht neu beschrieben), dazu Formbilder 6206/6174 aus dem Torsatz (nicht einzeln beschrieben).
- Zonen unten->oben: Schwelle/Sockel; Tuerblatt (gruen, Segmentbogen oben, 2 Beschlaege, Klopfer, Briefschlitz) tief in der Nische; Laibung mit je 3 Goldschaft-Pendants (Schaft + Kapitell) auf einer Schulter z ~2,8; innerer Steinbogen (ca. 0,13 m roter Ring um den Tuerbogen); Goldbogen/Wimperg mit Goldschraegen oben.
- Querschnitt: Tuernische (Lichte 1,39) bis Tuerblatt n 6,77; ab Schulter z 2,77 Laibungsfluegel breiter (2,05 m) bis n ~7,17; Rahmenring aussen.
- Wiederholungen: 3 Goldschaefte je Seite (nur benannt; gezaehlt in Stufe 1).
- Anschluss: Rumpf quader:rumpf_eg ist massiv bis n 7,28 -> tiefer Schnitt bis 6,77 ohne Wandstaerkenproblem (Vorversuche hatten das als Hindernis notiert).
- Formfamilie: vorhandene (quader ausschnitt, freiform ausschnitt, fensterreihe kontur); NEU generisch nur `stehen_u` in quader (stehende Streifen im Ausschnitt).
- Offene Frage: Schaftbreite/-lage aus Foto 6207 ohne Parallaxekorrektur (ANNAHME); Schaftfront n 7,24 ANNAHME.

## 2. Zaehlungen
- Z-6207-002: 3 Goldschaefte links, 3 rechts (voll).
- Z-6243-002: links 3 (voll), rechts 2 von 3 (angeschnitten = teil). Gegenprobe zu Z-6207-002.

## 3. Pruefungen (Pruefstand, alter Stand ROT erwartet -> neu)
| Pruefung | vorher | nachher | Soll | Quelle |
|---|---|---|---|---|
| tuer_b3_blatt (Blatt hinter Wandfront) | 0,30 | 0,51 | 0,46..0,56 | M-6207-001 (n 6,772 +-0,026) |
| tuer_b3_breite_median | 1,48 | 1,41 | 1,36..1,43 | M-6120-028 (Lichte 1,39) |
| tuer_b3_schaft_l_anzahl | 0 | 3 | 3 | Z-6207-002 / Z-6243-002 |
| tuer_b3_schaft_r_anzahl | 0 | 3 | 3 | Z-6207-002 / Z-6243-002 |
| tuer_b3_rahmenfront (bestehend) | -0,04 | -0,04 | -0,096..0 | M-6243-002 |
Sollwerte nicht gelockert. `tools/bauen_abnehmen.sh kaufhaus_grob3`: "alle Pruefungen bestanden" (1 Widerspruch offen, vorher schon). Regression `tools/regression.py ... --pruefen`: identisch.

Foto-F1 (teil_fotoform, 10 Torfotos): **0,452 -> 0,742** (Praezision 0,753 -> 0,839, Recall 0,323 -> 0,665). Gate (+0,02) erfuellt. Einzelfotos: 6207 Recall 0,19->0,84; 6243 Praez 0,164->0,338, Recall 0,0->0,124; **6117 Praezision 0,72 -> 0,54 (Rueckschritt, nicht untersucht)**.
Wolkenbeleg/Gitter-F1 nicht separat neu gemessen (teile_lage_pruefen: Median 0,04 m, 0 % > 0,5 m; Bauteil nach Aenderung unveraendert in Lage).

## 4. Overlays
- modelle/kaufhaus_grob3/audit/gitter_generator/rundekreis1_fensterreihe_eg1_tuer_{6207,6243,6120}_nachher.jpg
- Vorher: /media/oem/scan/rc-park_kreis/kaufhaus_grob3/20261110_173101a173101/fotoform_bilder/fensterreihe__eg1_tuer_{6207,6243,6120}_r1_vorher.jpg
- Selbst angesehen: 6207 (Tuerbogen, Pfosten rechts, Schwelle gruen; Rest gelb: aeusserer Goldbogen links oben), 6243 (siehe Fehlerliste). 6120: Bild erzeugt, NICHT angesehen.

## 5. Fehlerliste
trifft (am Bild geprueft): Tuerbogen + rechte Laibungskante + Schwelle in 6207; Tuerblatt-Tiefe/Breite per Pruefstand.
trifft nicht: 6243 (schraeg): linke Kante rot (Modellkante ohne Foto, x 110-165) und rechte Kante gelb (Fotokante ohne Modell) = seitlicher Versatz der Nische in tiefer Ebene bzw. Tiefe der Laibung falsch; 6117 Praezision gesunken; aeusserer Goldbogen/Wimperg oben links in 6207 gelb (nicht modelliert).
ungeprueft: Schaftbreite/-lage/-front (ANNAHME), Kreisbogen vs. Sinusast (nur 6207 sichtbar gruen), 6120-Overlay, Wimperg/Goldschraegen/Schwelle als Formen (Relief < H0-Druckgrenze 2,6 cm echt bzw. nicht gemessen), Fehlteile_finden/foto_diff nicht neu gelaufen, Freiraum-Audit schlaegt in dieser Umgebung fehl (SFM-AUSRICHTUNG-buendel.json fehlt, auch vor meiner Aenderung).

## 6. Geaenderte Dateien
tools/baukasten_gen.py (quader `stehen_u`), modelle/kaufhaus_grob3/objekt.json (kontur -1,00/+0,98 aus Vorgaenger-Zweig 084248-r1; nische n0 6,77, u 3,625..5,035; neu freiform:eg1_tuer_bogenfeld, quader:eg1_tuer_nische_fluegel stehen_u 3+3, quader:eg1_tuer_schaefte_kopf), masstabelle.json (4 Pruefungen + 3 Messungen, `erledigt` an der Beobachtung), messprotokoll/Z-6207-002, Z-6243-002, REZEPT_GEBAEUDE_AUS_FOTOS.md (L-KR29..32), NICHTS_GEBRACHT.md, erzeugte STL/Audit-Dateien. Nichts committet.

## 7. Generalisierte Lehre
| Lehre | Anlass | Werkzeug |
|---|---|---|
| Ausschnitte werden nach der Vereinigung aller Anbauten abgezogen: Elemente in einer Laibung als stehende Streifen modellieren | Schaefte zaehlten 0 | quader `stehen_u`, ebene_vorspruenge |
| Schnittkanten nie deckungsgleich mit Nachbarflaechen (5 mm Versatz) | STL nicht wasserdicht nach 1. Bau | Druckreparatur-Meldung im Bau |
| Hindernis "Wandstaerke" erst am Volumen pruefen (Rumpf massiv) | Vorversuche liessen Tuerblatt offen | Schnittprobe / Pruefstand |
| Fotoform-Bilder nur mit --bilder | ff_eigen_bilder leer | teil_fotoform |
