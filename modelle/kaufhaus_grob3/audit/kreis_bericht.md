# Kreis 20261110_062358a062358 r1 - fensterreihe:og

## 1. Formbeschreibung (Stufe 0)
Fotos: 6161 (27 m, frontal), 6120 (11,6 m Nahfoto), 6132 (16 m, Azimut -22), 6117 (18,5 m, Azimut +50), 6118. Siehe `modelle/LOGBUCH_FENSTER_OG_R1_2026-11-10.md`.
Zonen: Sohle z 10,34 -> untere Reihe (3 Lichter) -> Kaempfer (Seiten 11,77 / Mitte ~12,3) -> obere Reihe -> Vorhangbogen (aussen senkrecht bis 12,5, konkav zu Stegscheiteln 13,43, Mittelsenke 13,34). Steinrahmen buendig mit der Wand n 12,66, Lichter in der Laibung. 5 Gruppen, Pitch 3,96, je 3 Spalten x 2 Zeilen. Familie: vorhandene `fensterreihe`, neuer generischer Parameter `nische_tiefe`.
Am Altmodell anders: 3,33 statt 2,72 m breit, Seitenlichter 0,91 statt 0,71, Rahmen 0,15 vorstehend, Glas in Wandebene, Stegscheitel 13,24 statt 13,43.

## 2. Zaehlungen
Z-6161-002 (3 Lichter je Gruppe, G2-G4 voll), Z-6161-003 (2 Reihen je Seitenlicht); bestehend Z-6120-002, Z-6261-001, Z-hc12-001, Z-004-002, Z-043-001 (5 Gruppen). Zaehlung nur am Foto, Anzahlen unveraendert.

## 3. Pruefungen
| Pruefung | vorher | nachher | Soll | Quelle |
|---|---|---|---|---|
| Lichtweite untere Lichter g3 / g4 | 0,92 / 0,92 | 0,68 / 0,68 | 0,65-0,77 | M-6161-038..040 |
| Wand ausserhalb Rahmen links / rechts (u 1,45-1,62) | -0,15 / -0,15 | 0,00 / 0,00 | -0,06..0,08 | M-6161-022 (2,72 m), M-6161-036, M-6120-051/053 |
| Stegscheitel z links / rechts | 11,79 / 11,79 | 11,95 / 11,95 | 11,877-12,037 | M-6161-033/035 |
| Glasebene hinter Wand 12,66 | -0,03 | 0,20 | 0,05-0,30 | M-6132-001, M-6120-055 (Foto 0,06-0,10), Wolke 0,27 |
Alle 7 am Altstand ROT (abn_vorher_final.log), jetzt gruen; Sollwerte nicht gelockert. Gate konvergenz_bericht (Teil fensterreihe__og):
| Groesse | vorher | nachher |
|---|---|---|
| Wolkenbeleg | 0,670 | 0,979 |
| Kanten-Recall | 0,792 | 0,840 |
| Kanten-Praezision | 0,491 | 0,683 |
| Mittel Beleg/F1 | 0,638 | 0,866 (+0,23) |
Keine Groesse gefallen. bauen_abnehmen: alle Pruefungen bestanden (1 vorbestehender Widerspruch Gesamthoehe), 1 Teilnetz, wasserdicht. regression.py: identisch. teile_lage_pruefen og: Median 0,05 m, 0 % > 0,5 m. foto_diff 6161: Modellkanten ohne Foto 0,0465 -> 0,0358, Fotokanten ohne Modell 0,438 -> 0,353 (Gesamtmodell).

## 4. Overlays (links vorher, rechts nachher)
- modelle/kaufhaus_grob3/audit/gitter_generator/rundekreis1_fensterreihe_og_6120.jpg
- .../rundekreis1_fensterreihe_og_6161.jpg
- .../rundekreis1_fensterreihe_og_6132.jpg
- .../rundekreis1_fensterreihe_og_6117.jpg
Selbst angesehen: 6120, 6161, 6117 (Breite und Bogenform treffen); 6132 erzeugt, nicht einzeln begutachtet. seiten.jpg angesehen. fehlteile_finden: keine Treffer am Fensterband.

## 5. Fehlerliste
- Breite, Lichtweite, Rahmen/Stege, Kaempferhoehen, Bogenkontur: trifft (Overlay 6161/6120/6117).
- Rahmenfront buendig (tiefe 0,05 = Relief-ANNAHME): trifft laut 63-Grad-Triangulation + Wolke + Gate; M-6120-057 (12,805, 30 Grad) widerspricht, als Ausreisser verworfen.
- Glastiefe 0,2: ungeprueft im Betrag (Foto 0,06-0,10 gegen Wolke 0,27), offen in beobachtungen_offen.
- Sprossen/Bleiverglasung, Goldprofil (doppelte Linie), Sohlbank: fehlen (nicht modelliert).
- Praezision 0,68: Rest sind Dreiecks-Diagonalen/Stegkanten ohne Fotokante, ungeprueft je Kante.
- Gruppen 1, 2, 5: nur ueber Wiederholung (Pitch) uebernommen; Gruppe 2 Breite gemessen (M-6161-036), 5 ungeprueft.

## 6. Geaenderte Dateien
tools/baukasten_gen.py (nische_tiefe), modelle/kaufhaus_grob3/objekt.json, masstabelle.json, messprotokoll (M-6161-022..044, M-6120-051..057, M-6132-001/002, Z-6161-002/003), konvergenz.jsonl, automatisch regenerierte audit-/STL-Dateien, modelle/LOGBUCH_FENSTER_OG_R1_2026-11-10.md, NICHTS_GEBRACHT.md, REZEPT_GEBAEUDE_AUS_FOTOS.md.

## 7. Generalisierte Lehre
| Lehre | Anlass | Werkzeug |
|---|---|---|
| Beleg nach Flaeche/Tiefe aufschluesseln, bevor man ihn als Mass nimmt | Beleg 0,67 war durch ueberbreite Rahmen auf Wandpunkten aufgeblaeht | Stichprobe je Teil gegen Wolke (L-KR18) |
| Tiefen-Triangulation nur >= 45 Grad Schnittwinkel | 30-Grad-Paar 12,805 vs 63-Grad-Paar 12,646 | foto_mass --tri (L-KR19) |
| Schnitt im Generator 2-3 mm kleiner als das Element | 154 Splitter-Koerper | baukasten_gen nische_tiefe (L-KR20) |
