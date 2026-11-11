# Kreis 20261111_152551a152551 r2 – bogenreihe:laube Säulensockel zu niedrig

## 1. Formbeschreibung (Stufe 0)
Fotos: 6117 (Nahfoto Pfeiler 3, sauber, Boden sichtbar), 6115 (Pfeiler 3+4 von Nordost), d20 (Nahfoto Pfeiler 2, Boden abgeschnitten), 6127 (Übersicht, Fuß vom Schild verdeckt), 6176 (Schrägblick Gasse).
Zonen von unten: Achtkant-Sockel (senkrechte Wand, Flächen zur Fassade), darüber Schrägfase (Oktogon → runder Schaft), Rundschaft 0,88 m, Kämpfer.
Grundriss: Oktogon, Schaft rund. Wiederholung: 5 Säulen (Zählung unverändert Z-004-003/-001), alle gleich.
Formfamilie: vorhandene `bogenreihe` mit `sockel_weite/sockel_hoehe/fase_hoehe` (baukasten_gen.py) – nur Maße geändert.
Am Modell anders: Sockelwand-Oberkante lag bei z 2,00 statt 2,25–2,30, Fase endete 2,20 statt 2,41.

## 2. Zählungen
Keine neuen (Anzahl 5 Säulen unverändert).

## 3. Prüfungen
| Prüfung | vorher | nachher | Soll | Quelle |
|---|---|---|---|---|
| pfeiler3_sockelwand_d (z 2,24–2,32) | nan (ROT) | grün | 1,0–1,6 | M-6117-008/009, M-6115-016/017 |
| pfeiler3_d (Messring auf 2,38–2,45 verlegt, Soll gleich 0,81–0,94, Historie) | – | grün | 0,81–0,94 | kantengitter + M-6117-009 |
Messungen: Wandoberkante z 2,30 (M-6117-008) / 2,27 (M-6115-016); Fase-Oberkante 2,40 (M-6117-009) / 2,42 (M-6115-017); Pflaster 1,57 beide. Pfeiler 4 (M-6115-018): Wand 2,20/Pflaster 1,54, nicht verwendet.
Generator: sockel_hoehe 0,55→0,80, fase_hoehe 0,2→0,16 (0,83/0,13 trieb teile_ueberhang auf 0,0101 > 0,01).
Abnahme `bauen_abnehmen.sh` (mit RCPARK_OHNE_FOTODIAG=1): alle Prüfungen bestanden.
Foto-F1 (halbe Auflösung, 10 Torfotos): vorher 0,756 (Präz 0,726/Recall 0,788) → nachher 0,757 (0,721/0,796). **Gate +0,02 NICHT erreicht** (Sockel ist kleiner Kantenanteil). f1_h nicht gesondert gemessen.

## 4. Overlays (Vorher | Nachher)
modelle/kaufhaus_grob3/audit/gitter_generator/rundekreis2_laube_sockel_vorher_nachher_{d20,6127,6176}.jpg
(Selbst angesehen: d20 – Wandoberkante und Fase liegen nachher auf den Fotokanten; 6127 – Fuß verdeckt, nicht beurteilbar.)

## 5. Fehlerliste
- Sockelhöhe (Pfeiler 3, 2 Fotos): trifft.
- Sockelbreite/sockel_weite 1,5: ungeprüft/widersprüchlich (Verhältnis Sockel/Schaft 1,39 in 6117, 1,16 in 6115, 1,45 in d20) – nicht geändert, ANNAHME bleibt.
- Pflasterhöhe 1,57 vs boden_z 1,453: Sockel reicht 0,12 m unter das Pflaster (nicht sichtbar); nicht geändert.
- Andere Pfeiler (0,1,2,4): Höhe nur aus Pfeiler 3 (und Pfeiler 4 grob 2,20) übernommen – ungeprüft einzeln; Pflaster fällt ggf. ab.
- Nicht gelaufen: foto_diff, fehlteile_finden, teile_lage_pruefen, regression (kein Werkzeug geändert).
- Pruefer-Reste der Stirnbögen (r1) nicht bearbeitet.

## 6. Geänderte Dateien
objekt.json, masstabelle.json (2 Prüfungen/Messungen, Beobachtung erledigt), STLs/pruefbericht/MASSNACHWEIS (Bau), NICHTS_GEBRACHT.md, REZEPT_GEBAEUDE_AUS_FOTOS.md, Messprotokolle M-6117-008..011, M-6115-016..020, M-6176-001, M-6127-004, M-d20-001/002 (Letztere vier unbrauchbar/ungenutzt).

## 7. Generalisierte Lehre
L-KR32 | Anlass: Sockel zu niedrig | Werkzeug: foto_mass --kamera, teil_fotoform (Vorher = objekt.json zurücksetzen, nicht STL).
