# Kreisbericht gaubenreihe:unten (Lauf 20261110_101552 r1)

Vorgehen: Die Fotomessung aus Runde R3 (Zweig kreis/kaufhaus_grob3/20261110_021332a021332-r3, Commit f194866a) war angenommen, aber nicht in main (baute auf verworfenem Stand auf). Ich habe nur die Teile uebernommen, die zu diesem Bauteil gehoeren (objekt.json-Eintrag, masstabelle.json, M-6259-014..026, Logbuch, Overlays). Neue Messungen gab es in dieser Runde nicht.

## 1. Formbeschreibung
Siehe `modelle/LOGBUCH_GAUBEN_UNTEN_R3_2026-11-10.md`. Fotos c12 (Uebersicht), 6259 (Nah), 6162 und 6161 (schraeg). Zonen von unten: Fensterbank-Platte, Fensterkasten ca. 1,02 x 0,76 m mit Rundbogenfenster, ziegelgedecktes Vordach ca. 1,43 m breit, dreieckige Wangen, Pultdach ca. 1,8 m in den Hang. Familie: vorhandene `gaubenreihe`, Form schlepp mit vordach_*.
Ich habe die Overlays 6259/6162/c12/6161 (Mitte-Gaube) selbst angesehen.

## 2. Zaehlungen
3 Gauben: Z-018-005 (unveraendert, in c12/6162 erneut gesehen).

## 3. Pruefungen
Ueberuebernommen: 18 Fotopruefungen (6 je Gaube) aus M-6259-014..026. Am Altstand rot, nach Uebernahme alle bestanden (`tools/bauen_abnehmen.sh kaufhaus_grob3`: "alle Pruefungen bestanden", 1 Widerspruch aus Altbestand). Das Rot am Altstand stammt aus dem R3-Protokoll, ich habe es hier nicht neu nachgestellt.

| Kennzahl | vorher (main) | nachher |
|---|---|---|
| Wolkenbeleg | 0,402 | 0,905 |
| Median-Abstand | 0,179 m | 0,075 m |
| Anteil mit Daten | 0,62 | 0,654 |
| Kanten-Recall | None | 0,0 (Gitter 72 Pkt) |
| Kanten-Praezision | 0,0 | 0,0 |

Gate: (Beleg+F1)/2 steigt von 0,402 auf ca. 0,453, also nur knapp ueber +0,05 (Grenzfall). Praezision/Recall fallen nicht.

## 4. Overlays
- modelle/kaufhaus_grob3/audit/gitter_generator/rundekreis3_gaubenreihe_unten_m_vorher_nachher.jpg (angesehen)
- ..._m_nachher.jpg, ..._a_vorher_nachher.jpg, ..._a_nachher.jpg, ..._c_vorher_nachher.jpg, ..._c_nachher.jpg (a, c nicht erneut angesehen)
Die Overlays stammen aus R3; die Geometrie des Teils ist identisch zum jetzigen objekt.json-Eintrag.

## 5. Fehlerliste
- Fensterkasten/Stirn, Vordach-Vorderkante, Wangen: trifft (Overlay Mitte-Gaube, 4 Fotos).
- Fensterbank-Platte: trifft nicht. Im Foto ist eine dunkle Platte (ca. 0,15-0,2 m) unter der Modell-Unterkante, nicht modelliert.
- Vordach-Rueckkante / dach_tiefe 1,8: ungeprueft (nur 1 Messpunkt, +-0,2 m).
- Gaube C (6145, sehr schraeg): nur grob.
- Rundbogenfenster: nicht modelliert (ANNAHME < 1 mm tief in H0).
- Gaube A und C: Overlay nicht erneut angesehen.
- Kanten-F1: 0, Gitter zu duenn, kein Beleg moeglich.
- Nicht gelaufen: foto_diff, teile_lage_pruefen (stuerzt nach R3-Befund mit KeyError 'world' ab), tools/teile_sichtpruefung.py.

## 6. Geaenderte Dateien
objekt.json, masstabelle.json, konvergenz.jsonl, MASSNACHWEIS.md und audit/ (Neubau), modelle/stl/kaufhaus_grob3_1-87.stl (Neubau), messprotokoll/M-6259-014..026, LOGBUCH_GAUBEN_UNTEN_R3_2026-11-10.md, NICHTS_GEBRACHT.md, REZEPT_GEBAEUDE_AUS_FOTOS.md (L32), Overlays. Zwischendateien: /media/oem/scan/rc-park_daten/kaufhaus_grob3/agent_scratch_kreis1/

## 7. Generalisierte Lehre
Lehre: Eine angenommene, aber nicht gemergte Runde laesst sich gezielt per `git diff <elter> <commit> -- <Dateien>` + `git apply --3way` uebernehmen (Binaerdateien per `git checkout <commit> -- <pfad>`). | Anlass: R3 baute auf verworfenem Stand auf | Werkzeug: git, kein neues.
