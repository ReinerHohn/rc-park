# Kreis-Bericht helm_geschweift:w (kaufhaus_grob3, 2026-11-10, Lauf 035748a035747 r1)

## 1. Formbeschreibung
Siehe `modelle/LOGBUCH_HELM_W_2026-11-10.md`. Fotos 6162, 6257, g03 (angesehen), i04 (nur erzeugt). Zonen: Fuss z 13,3-15,4 stetig konkav bis aufs Gesims (Altmodell: senkrechter Kranz r 1,45 + Ring 1,54 falsch), Schaft Achteck, Nadel/Kugel z 21,35. Formfamilie: bestehende `helm_geschweift` (nur Profil/Knauf geaendert).

## 2. Zaehlungen
Keine neue Zaehlung am Westhelm (Achteck, 8 Seiten: ANNAHME aus Z-nu3b-001 am Osthelm). Ungeprueft am Westhelm.

## 3. Pruefungen (alle Quelle Wolke lot2 / `W-helm_w-profil.json`; Knauf Vorversuch-Triangulation, ANNAHME uebernommen)
| Pruefung | vorher (Altstand) | nachher | Soll |
|---|---|---|---|
| helm_w_r_13_45 | 1,45 ROT | 1,68 | 1,55-1,85 |
| helm_w_r_14_12 | 1,45 ROT | 1,30 | 1,2-1,4 |
| helm_w_r_14_38 | 1,38 ROT | 1,19 | 1,09-1,29 |
| helm_w_r_14_88 | 1,08 ok | 1,01 | 0,91-1,11 |
| helm_w_knauf_r_21_35 | 0,09 ROT | 0,19 | 0,15-0,25 |
Abnahme: alle Pruefungen bestanden. Kennzahlen: Beleg 0,45 -> 0,557, Median 0,18 -> 0,111 m, Kanten R 0,426 -> 0,417, P 0,275 -> 0,312; Mittel(Beleg,F1) +0,065 (Gate +0,05, R-Abfall 0,009 < 0,02).

## 4. Overlays (rot neu, cyan alt)
- modelle/kaufhaus_grob3/audit/gitter_generator/rundekreis1_helm_geschweift_w_6162_vorher_nachher.jpg
- .../rundekreis1_helm_geschweift_w_6257_vorher_nachher.jpg
- .../rundekreis1_helm_geschweift_w_g_g_03_vorher_nachher.jpg
- .../rundekreis1_helm_geschweift_w_i_i_04_vorher_nachher.jpg (nicht einzeln angesehen)

## 5. Fehlerliste
- Fuss/Schweifung z 13,3-15,4: trifft (6162, 6257: Neu liegt auf Silhouette, Alt ragt ueber); Traufspitzen einzeln ungeprueft.
- Schaft z 15,4-21: trifft in 6162/6257/g03 grob; Wolke sagt 0,05-0,07 m breiter (Osthelm-Profil ANNAHME) - ungeprueft fein.
- Knauf z 21,35: Zahl aus Vorversuch uebernommen, im Overlay nicht gesondert geprueft (Bildausschnitt reicht nicht bis oben) - ungeprueft.
- Rueckseite: ANNAHME Spiegelung. foto_diff, fehlteile_finden, teile_lage_pruefen (Absturz vorbestehend), teile_sichtpruefung: NICHT gelaufen.

## 6. Geaenderte Dateien
modelle/kaufhaus_grob3/objekt.json, masstabelle.json, messprotokoll/W-helm_w-profil.json, STL/Teile (Neubau), audit/*, LOGBUCH_HELM_W_2026-11-10.md, NICHTS_GEBRACHT.md, REZEPT_GEBAEUDE_AUS_FOTOS.md.

## 7. Generalisierte Lehre
Lehre | Anlass | Werkzeug: L-H7 Gegenstueck-Fehler per Wolken-Mitten-Profil uebertragen statt Silhouettenspitzen triangulieren | Helm W | tools/helm_profil_wolke.py (im Rezept eingetragen; Fehlschlaege in NICHTS_GEBRACHT.md).
