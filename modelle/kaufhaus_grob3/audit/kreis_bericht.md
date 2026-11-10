# Bericht gaubenreihe:oben (Kreis 20261110_053953 r2)

## 1. Formbeschreibung (Stufe 0)
Fotos angesehen: 6259 (Nah), c12 (frontal), 6162 (schraeg), j05 (unscharf, nicht verwertbar), Overlay-Vorlauf. Schleppgaube: Fensterbank, Fensterkasten 1,02 m mit Rundbogenfenster, ziegelgedecktes Vordach 1,45 m mit roten Dreieckswangen; das Vordach laeuft als Ebene buendig in den Hang. Formfamilie: vorhandene `gaubenreihe` form schlepp. Befund: M-6259-009 = "Anschluss Hang" (z 22,75), Modell leitete die Rueckkante aus der Hangneigung ab (22,35) -> Ziegelflaeche in c12 ~0,4 m zu kurz. Vorversuch r1 setzte nur die Kante hoeher -> Absatz + Keil (verworfen).
Logbuch: modelle/LOGBUCH_GAUBEN_OBEN_R2b_2026-11-10_053953.md

## 2. Zaehlungen
Unveraendert Z-018-006 (2 Gauben). Keine neue Zaehlung.

## 3. Pruefungen
| Pruefung | vorher | nachher | Soll | Quelle |
|---|---|---|---|---|
| gaube_b_dach_z7 (Vordach-Oberflaeche n 7,0, rel. z) | 20,93 ROT | 21,17 gruen | 20,97-21,35 (+-0,2) | M-6259-009 + Vorderkante M-6259-007/008; nur Ebenen-Konsistenz, KEIN unabhaengiger Beleg |
| Wolkenbeleg gaubenreihe:oben | 0,589 | 0,653 (Median 0,124 -> 0,110 m) | Gate +0,05 | Wolke j_voll_lot2 (unabhaengig) |
| Kanten-Praezision | 0,0 | 0,0 (0/1304) | nicht fallen | Kantengitter v12; Recall None, F1 nicht bildbar |
bauen_abnehmen: alle Pruefungen bestanden; regression --pruefen: identisch.

## 4. Overlays / Plots
- modelle/kaufhaus_grob3/audit/gitter_generator/rundekreis2b_gaubenreihe_oben_vorher_nachher.jpg (cyan alt, rot neu; 6259, c12, 6162) - selbst angesehen
- modelle/kaufhaus_grob3/audit/gitter_generator/rundekreis2b_gaubenreihe_oben_schnitt_B.png (Querschnitt n,z durch Gaube B + Satteldach: Vordach endet buendig im Hang bei n~6,3, kein Absatz, kein Keil)

## 5. Fehlerliste
Trifft (am Bild geprueft): hintere Vordachkante in 6259 und c12; Wangenspitze 6162; kein Absatz/Keil im Querschnitt B.
Trifft nicht / offen: Stirn in c12 ~0,1 m zu breit; Fensterbank 0,1-0,2 m zu hoch; Rundbogenfenster, Konsolen, Fensterbankprofil nicht modelliert; Gaube A: Rueckkante ANNAHME wie B, A/B-Hoehenunterschied 0,14 m fehlt.
Ungeprueft: nur 1 Messpunkt (+-0,25 m), Satteldach am Hang evtl. lokal 0,4 m zu tief; j05 unscharf; foto_diff, fehlteile_finden einzeln, teile_sichtpruefung, teile_lage_pruefen (Gauben nur mit Satteldach baubar) nicht gelaufen; Querschnitt nur fuer B, Gaube A nicht geplottet; Seiten-/Schraegrender des Gesamtmodells nicht angesehen.

## 6. Geaenderte Dateien
tools/baukasten_gen.py (dach_hinten_z, generisch), modelle/kaufhaus_grob3/objekt.json, masstabelle.json (Pruefung + Beobachtung), Logbuch, REZEPT (L-KR17), NICHTS_GEBRACHT, generierte STL/pruefbericht/MASSNACHWEIS.

## 7. Generalisierte Lehre
Lehre | Anlass | Werkzeug
Gemessene Kante nie allein anheben: Flaeche als Ebene bis zum Nachbarteil fortsetzen und Querschnitt ansehen | r1 Sprungschanze | baukasten_gen dach_hinten_z, Schnitt-Plot
