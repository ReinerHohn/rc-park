# Kreis-Ost r1 staffelgiebel:ost (kaufhaus_grob3, 2026-11-10)
Nichts committet, gelöscht, geslict oder gedruckt. Logbuch: `modelle/LOGBUCH_GIEBEL_OST_R1_2026-11-10.md`.

## 1. Formbeschreibung
Fotos angesehen: 6115 (Nah), 6261 (Übersicht), 6164 (Nah); 6259 nur Overlay erzeugt, nicht einzeln beurteilt.
- Zonen: Giebelwand (roter Putz, zwei schmale Fenster in Faschen), darüber beidseitig gestufte Treppe, je Stufe Pfeilerblock mit Ziegelkäppchen.
- Querschnitt: dünne Scheibe (~0,6 m), gegen die Hauptfassadenachse gedreht (u fällt 0,06 m je m n).
- Stufen: 8 je Vorderflanke (Z-6261-002, Z-6164-004 aus Vorrunden, im Overlay 6115/6261/6164 nachgesehen). Rückflanke = Spiegel (ANNAHME).
- Am Modell anders: Scheibe parallel zur Achse und 0,2–0,4 m innen (Kontur 30–50 px daneben).
- Formfamilie: vorhandene `staffelgiebel`, neu nur optionaler generischer Parameter `u_neigung`/`n_ref` (Altverhalten bitgleich, `regression.py --pruefen`: identisch).

## 2. Zählungen
Keine neue Zählung (Stufenzahl 8 aus Z-6261-002/Z-6164-004 der Vorrunden; Z-Protokoll nicht neu erhoben).

## 3. Prüfungen
| Prüfung | vorher (Altstand) | nachher | Soll | Quelle |
|---|---|---|---|---|
| Aussenebene u bei n 3,45 | 15,851 rot | 16,312 | 16,15–16,50 | Kappenfirst-Regression M-6115-001..008 + dicke/2 (ANNAHME Kappe mittig); Gegenprobe Wolke 16,38–16,48, M-6115-009/010 16,23/16,41 (±0,23) |
| Aussenebene u bei n 10,5 | 15,85 ok | 15,888 | 15,72–16,07 | dito, Wolke 15,83–15,88 |
| Wandneigung u(3,45)−u(10,5) | 0,001 rot | 0,424 | 0,28–0,58 | Steigung −0,0609 (Streuung 0,032), Wolke −0,083 |
| Stufen 2/4/8 Oberkante, Vorderende | ok | ok (27,42/24,74/19,38/11,0) | unverändert | M-6115-002/004/008 (Messorte mit der Scheibenmitte verschoben) |
| Rückflanke/Vorderflanke Höhe | ok | 1,00 | 0,97–1,03 | Messorte verschoben |
Sollwert „Aussenebene u (n 3,45)“ von 15,55–15,95 auf 16,15–16,50 geändert, mit neuer Quelle und `historie` (alte Lesart setzte Aussenfläche = Kappenmitte).
`bauen_abnehmen.sh kaufhaus_grob3`: alle Prüfungen bestanden | 1 Widerspruch offen (Gesamthöhe, vorbestehend). `freiraum_audit` vorbestehend.
Ein Lauf von test_regeln_cb T6 fiel mit Exit 1 durch (GPU von Parallelspuren belegt), Wiederholung grün.

Kennzahlen (konvergenz_bericht, Trockenlauf, Teile neu exportiert):
| | vorher | nachher |
|---|---|---|
| Beleg | 0,224 | 0,377 |
| Median-Abstand | 0,383 m | 0,304 m |
| Kanten-Recall | 0,336 | 0,417 |
| Kanten-Präzision | 0,025 | 0,023 |
| Kanten-F1 | 0,047 | 0,044 |
| Güte (Mittel Beleg, F1) | 0,135 | 0,210 |
Gate +0,075 bei geforderten +0,05; keine Größe fällt > 0,02 (F1 −0,003). Aus den Zahlen selbst gerechnet. Die Kreis-Schleife kann anders messen (Rauschen ±0,01).
Beleg-Gewinn kommt aus Verschiebung und Neigung zusammen (u 16,05 ohne Neigung nur 0,292; Neigung allein bei 15,85 senkt auf 0,12–0,16). Gewählt wurde nicht das Beleg-Maximum, sondern der aus der Kappenfirst-Messung abgeleitete Wert (Scan 15,95–16,15 liegt im Plateau).

## 4. Overlays (rot = neu, cyan = Altstand)
- audit/gitter_generator/rundekreis_ost1_staffelgiebel_ost_6115.jpg
- audit/gitter_generator/rundekreis_ost1_staffelgiebel_ost_6261.jpg
- audit/gitter_generator/rundekreis_ost1_staffelgiebel_ost_6164.jpg
- audit/gitter_generator/rundekreis_ost1_staffelgiebel_ost_6259.jpg (erzeugt, nicht beurteilt)
- Messprotokolle M-6115-009/010 (Fensterfaschen), M-6115-011/012 (falsche Zuordnung, nicht verwenden)

## 5. Fehlerliste
- **Linke Flanke (Rückflanke) Stufenkontur 6261/6164:** trifft besser als vorher (Stufenecken ±10–20 px).
- **Rechte Flanke (Vorderflanke) 6115:** trifft teilweise; Stufenecken ±25–30 px (0,2–0,3 m) neben den Fotokäppchen, Altstand lag rechts, neu liegt links daneben.
- **Wandebene u(n):** trifft nach Wolke und Fensterfaschen; Fensterfaschen nur ±0,23 m.
- **Kappe mittig auf der Mauerkrone:** ungeprüft (ANNAHME).
- **Käppchen/Dächlein, Fenster in der Wand:** trifft nicht (fehlen).
- **Rückflanke Spiegel, Hinterseite:** ungeprüft.
- **Kanten-Präzision:** nicht gelöst (0,023), das Kantengitter hat an den Stufenecken keine Segmente.
- **`teile_lage_pruefen`:** Median 1,95 m über die ganze Scheibe inklusive verdeckter Teile, nicht aussagekräftig. Ungeprüft.
- **Nicht gelaufen:** `foto_diff`, `teile_sichtpruefung`; `fehlteile_finden` nur im Rahmen von `bauen_abnehmen`.
- **Westgiebel:** vermutlich dieselbe Neigung, nicht angefasst.

## 6. Geänderte Dateien
tools/baukasten_gen.py (`staffelgiebel`: u_neigung/n_ref), modelle/kaufhaus_grob3/objekt.json, masstabelle.json (3 Prüfungen neu/geändert, Messorte, 1 Beobachtung), messprotokoll M-6115-009..012, audit/gitter_generator/rundekreis_ost1_*, modelle/LOGBUCH_GIEBEL_OST_R1_2026-11-10.md, REZEPT_GEBAEUDE_AUS_FOTOS.md (L-KR17..19), NICHTS_GEBRACHT.md; vom Bau neu erzeugt: STL, elemente.json, MASSNACHWEIS.md, Audit-Dateien.

## 7. Generalisierte Lehre
| Lehre | Anlass | Werkzeug |
|---|---|---|
| Wandebene als Gerade u(n) regressieren und gegen Wolke je n-Streifen legen, bevor die Form angefasst wird (L-KR17) | Ostgiebel Beleg 0,22, Neigung −0,06 m/m | baukasten_gen `u_neigung`, foto_mass |
| Kappenfirst liegt mittig, Aussenfläche +dicke/2; zweite Quelle zur Gegenprobe (L-KR18) | u 15,85 → 16,05 | Regression + Wolke + Fensterfaschen |
| Strahlabstand < 0,05 m beweist die Zuordnung, ~1 m = falsches Element (L-KR19) | M-6115-011/012 | foto_mass --tri |
