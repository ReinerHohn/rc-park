# Kreis r1 213718 - balkonband:haupt (+ bruestung:balkon)

## 1. Formbeschreibung (Stufe 0)
Fotos angesehen (Formbilder): 6120 (Uebersicht Unterseite), 6132 (Schraeg West), p03 (Nah), 6145 (Schraeg von West), 6161 (frontal), 6164, 6171 (Nah Erker 2), d11 (Schraeg Ost).
- Zonen: Konsolen (11 Stueck) - duenne Plattenstirn - Platte - Balustrade (Baluster, Feldpfeiler, Handlauf).
- Ost-Ende: 6171 und d11 zeigen glatte Wand (Putz) dort, wo das Modell die Platte weiterfuehrte; die Balustrade endet an einem Pfeiler vor Erker 2. Platte endet u ~12,3 (Wolke) / Konsole 12,25.
- West-Ende: 6132/6161: Platte und Balustrade beginnen nach dem Erker-0-Wappenfeld, davor Wand; erste Konsole u -5,15 (konsolen_v11), Wolke Platte ab -5,4. 6145 allein kann West NICHT entscheiden (Erker verdeckt, ANNAHME).
- Formfamilie: vorhandene balkonband/bruestung (nur u_von/u_bis, n_baluster, u0, pfosten_erster).
- Offen: Stirn nur 0,11 m (M-6120-058..060), gestufte Oberkante, steinerne Feldpfeiler der Bruestung, Baluster-Phase (Praezision 0,53).

## 2. Zaehlungen
Keine neue; Baluster 11/Feld + Pfosten aus Z-6120-001 (alt). Neue Anzahl 57 Raster aus Platte abgeleitet, nicht neu gezaehlt (ANNAHME).

## 3. Pruefungen (alter Stand ROT -> neu OK)
| Pruefung | vorher | nachher | Soll | Quelle |
|---|---|---|---|---|
| Platte endet vor West-Erker | -1,19 | 0,01 | -0,08..0,25 | M-6145-001 + Wolke lot2 |
| Platte endet vor Ost-Erker | -1,21 | -0,01 | dito | M-6145-002 + Wolke |
| Balustrade West | -1,25 | 0,01 | dito | Wolke Handlauf-Schicht |
| Balustrade Ost | -1,27 | -0,01 | dito | dito |
bauen_abnehmen: "alle Pruefungen bestanden", 1 Widerspruch offen (alt).
Foto-F1 (halbe Aufloesung, 10 Torfotos): Teil 0,623 -> 0,600 (9 Fotos, 6171 faellt aus); auf den 9 gemeinsamen Fotos je F1-Mittel 0,605 -> 0,619 (+0,015). GATE +0,02 NICHT belegt. Bruestung 0,732 (10) -> 0,721 (9). Ehrlich: Teil wird kleiner, Recall teils trivial (d11 fk 25k->6k px).

## 4. Overlays
Formbilder Vorher: /media/oem/scan/rc-park_kreis/kaufhaus_grob3/fotoform/bilder_463a982812579942/balkonband__haupt_*.jpg; Nachher: /media/oem/scan/rc-park_daten/kaufhaus_grob3/agent_scratch_kreis1/ff_A_b/ (Bruestung ffb_A_b). rundekreis1_*-Overlays NICHT erzeugt; foto_diff/fehlteile_finden/teile_lage_pruefen NICHT gelaufen.

## 5. Fehlerliste
trifft (am Bild): Ost-Ende (6171, d11: Wand statt Platte), West-Ende (6132, 6161), seiten.jpg Nord zeigt Luecken an beiden Enden.
trifft nicht: Unterseite/Soffit rot flaechig (6120, 6132, p03), Plattenstirn zu hoch (0,37 statt 0,11), Feldpfeiler fehlen, Baluster-Phase.
ungeprueft: Konvergenz-Recall 5-10 m (Vorversuch: Rueckschritt 0,795->0,726, Fehlkanten-Cluster an Enden; hier nicht neu bewertet - Erker-Wappenband koennte sie erklaeren), 57 Raster.

## 6. Geaenderte Dateien
objekt.json (balkonband u_von/u_bis, bruestung n_baluster 57/u0/pfosten_erster 3, historie), masstabelle.json (4 Pruefungen + Messungen, Beobachtungen erledigt, neue offen: Stirn/Pfeiler), messprotokoll/M-6145-001/002.json (aus Vorzweig, markiertes Bild fehlt), NICHTS_GEBRACHT.md, REZEPT_GEBAEUDE_AUS_FOTOS.md, erzeugte STL/pruefbericht/MASSNACHWEIS.

## 7. Generalisierte Lehre
Foto-F1 belohnt Verkleinern | 4 Vorversuche Balkon | Gate nur auf gemeinsamen Fotos, Pixelzahlen mitberichten; Luecken-Pruefungen per ebene_abstand.

## NACHTRAG (nach Vortor 0,613 -> 0,608: Enden allein bringen am Foto nichts)
Ursache am Overlay (6120/6132/p03): rote Plattenunterkante bei z 8,0, im Foto liegt die Stirnunterkante bei ~8,3 (5 Messungen M-6120-058..060, M-6132-003/004, Stirn 0,11-0,14). Uebernommen: balkonband unterseite_z 8,26, `unterkante_ueberstand` 0 (neuer optionaler Parameter, Default 0,1 = Altverhalten), konsolen z_oben 8,3; 2 neue Pruefungen (Soffit frei, Stirn mittig, Kontrolle).
Foto-F1 (halb, 9 gemeinsame Fotos, Mittel je Foto): Basis 0,604 -> nur Enden 0,619 -> Enden+Stirn 0,820. Foto 6171 faellt aus (Teil dort nicht mehr sichtbar). Gewinn auch in Fotos ohne Endenbezug: p03 0,514->0,759, 6120 0,547->0,789, 6119 0,534->0,805. d11 0,798->0,711 (Recall trivial, Teil dort fast weg; Rueckschritt). Teil dazu kleiner: Fotokantenpixel halbiert -> Messartefaktanteil nicht trennbar.
Abnahme: alle Pruefungen bestanden (1 alter Widerspruch). Regression (Werkzeug baukasten_gen): identisch.
Nachher-Formbilder: /media/oem/scan/rc-park_daten/kaufhaus_grob3/agent_scratch_kreis1/ff_B_b/ (NICHT einzeln angesehen ausser Zahlen).
Offen/ungeprueft: Konvergenz-Recall 5-10 m (Vorversuch 0,795->0,726), Fehlkanten-Cluster an den Enden, Soffit-Rot zwischen Konsolen, Feldpfeiler, Baluster-Phase. Korrektur zum Hauptbericht: Dicke 1,3 mm in 1:87 ist die Platte jetzt; die Druckbarkeits-Pruefungen der Abnahme bestehen.
