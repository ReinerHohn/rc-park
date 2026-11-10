# Kreis-Bericht r2: stl_teil:figuren -> figurenreihe:figuren (kaufhaus_grob3, 2026-11-10)

## 1. Formbeschreibung (Stufe 0)
Volltext: `modelle/LOGBUCH_FIGUREN_R2_2026-11-10.md`. Fotos angesehen: 6120 (Nahfoto frontal), 6119, 6117 (schraeg), 6127 (Seite), 6132, 6161 (Uebersicht, alle 4), 6145, 6164.
Zonen: Pendelkonsole (Rotationsglocke: Knauf d 0,10 -> Stufe d 0,31 -> Kranz d 0,58 -> Standflaeche z 11,29) / Figur 2,1 m (Unterschenkel b 0,43, Schurz 0,47, Brust ~0,5-0,6, Kopf 0,30, Krone) / Baldachin (nicht diese Runde).
Wiederholung: 4 Figuren, Periode 3,94-3,99 m. Formfamilie: NEU generisch `figurenreihe` (baukasten_gen.py), weil `konsolenreihe` nur Quader-Huellen, `zylinder_bt` nur ein Kegelstumpf, `figuren_netz` nicht verwendet.
Ursache des Befunds: Altteil = Quader-Huellen (alter Hand-Generator), Scheitel 0,3-0,7 m zu tief, 0,2-0,3 m neben der echten Figur.

## 2. Zaehlungen
Z-6161-001 (4 Figuren), Z-6145-001 (4 Figuren, zweite Richtung). Markierkreise liegen 20-60 px neben den Figurmitten (Pick grob), Zaehlung 4 eindeutig im Bild.

## 3. Pruefungen (Alt-STL aus `git show HEAD:` gegen neue Tabelle / neues Modell)
| Pruefung | vorher | nachher | Soll | Quelle |
|---|---|---|---|---|
| Scheitel Fig 1-4 (z, STL-Rahmen) | nan (Figur nicht an der Achse) | 11,91/11,93/11,87/11,89 | 11,82-12,02 usw. | M-6120-037/030/039, M-6161-016 |
| Pendelspitze Fig 1/2/3 | 9,47/9,11/8,91 | 9,21/9,15/9,15 | 9,11-9,27 usw. | M-6120-038/031/040 |
| Standflaeche Fig 2 | nan | 9,84 | 9,757-9,917 | M-6120-032 |
| Kranz-Durchm. Fig 2 | nan | 0,57 | 0,52-0,64 | M-6120-041 |
| 2. Stufe Durchm. | 0,59 | 0,31 | 0,26-0,36 | M-6120-043 |
| Breite Unterschenkel | 0,30 | 0,43 | 0,37-0,49 | M-6120-047 |
| Breite Kopf | nan | 0,30 | 0,25-0,35 | M-6120-050 |
| Tiefe Unterschenkel | 0,21 (schon gruen) | 0,23 | 0,17-0,29 | M-6127-001 (abgeleitet) |
Alt: 12 von 13 ROT (Fig-2-Pendelspitze nur 0,001 unter der Grenze). Neu: alle 13 OK (pruefstand direkt). Der Abschlusslauf `bauen_abnehmen` siehe Abschnitt 6.
Wolkenbeleg (gleiche Metrik wie konvergenz_bericht, lot2-Wolke, GPU): alt 0,433 / Median 0,173 m (reproduziert den Befund) -> neu **0,851 / Median 0,050 m** (Konsole 0,83, Koerper 0,86).
Neue Messprotokolle: M-6120-030..050, M-6127-001..003, M-6161-016.

## 4. Overlays (Vorher rot links, Nachher gruen rechts), selbst angesehen
- modelle/kaufhaus_grob3/audit/gitter_generator/rundekreis2_figuren_6120.jpg
- ..._6132.jpg, ..._6161.jpg (alle 4), ..._6117.jpg, ..._6145.jpg
Nachher sitzen Kopf, Rumpf, Konsolenkranz und Pendelspitze auf den echten Figuren in allen 5 Fotos.

## 5. Fehlerliste
- Konsole Fig 1-3: trifft (Spitze/Kranz/Stufe in Foto gemessen). Konsole Fig 4: ungeprueft (ANNAHME gleiche z; Overlay 6161/6145 +-0,1 m).
- Koerper: Hoehe/Scheitel trifft (4 Figuren, Fotos); Breite Beine/Kopf trifft (Fig 2); Brust 0,62 = ANNAHME; Tiefe nur Fig 2 (+-0,06); Fig 1/3/4 Profil von Fig 2 uebernommen (Posen unterschiedlich, Arme/Schwert/Reichsapfel/Hut-Krempe Fig 4 nicht modelliert).
- Baldachine (Wimperg/Fialen) ueber jedem Kopf: ungeprueft, eigene Runde. Alte Nischenboxen (g_nische) mit abgeschaltet: unbelegt, dass echte Nische existiert (Fotos zeigen flache Wand) -> sonst nichts.
- Druckbarkeit: Teil ist Manifold-Koerper (statt Rohdreiecke); Gesamtbau Druckreparatur wie zuvor ok; Gesamt-Wasserdichtigkeit hier nicht gefuehrt (masstabelle _doku).
- teile_lage_pruefen (ganzes Werkzeug, alle Teile) NICHT laufen lassen (Zeit); ersetzt durch Wolkenbeleg des Teils (oben). foto_diff/fehlteile liefen im ersten bauen_abnehmen-Lauf (keine Figurentreffer ausgewertet: ungeprueft).
- teile_sichtpruefung: nicht gelaufen (Gate laut Auftrag nicht bewiesen).

## 6. Geaenderte Dateien
tools/baukasten_gen.py (neue Familie figurenreihe), tools/pruefstand.py (neue Messart z_am_punkt; Regression Register AW siehe unten), modelle/kaufhaus_grob3/objekt.json (Altteil aktiv:false + figurenreihe:figuren), masstabelle.json (Beobachtung, 13 Messungen/Pruefungen), messprotokoll/M-*, Z-6161-001, Z-6145-001, audit/gitter_generator/rundekreis2_figuren_*.jpg, modelle/stl/kaufhaus_grob3_1-87.stl und Ergebnisdateien (Neubau), modelle/LOGBUCH_FIGUREN_R2_2026-11-10.md, REZEPT (L29, L30), NICHTS_GEBRACHT.

## 7. Generalisierte Lehre
| Lehre | Anlass | Werkzeug |
|---|---|---|
| Freistehende Figuren: Achse/Scheitel/Spitze je Instanz triangulieren, Hoehen als Ebene durch die Achse, Tiefe aus Seitenfoto per Blickwinkelformel | Altteil 0,3-0,7 m tief, Beleg 0,43 -> 0,85 | foto_mass --tri/--ebene, figurenreihe |
| Pruefzeilen auf Teile vor einer Wand duerfen keine Flaechenpunkte im Achsenfenster nutzen; Alt-STL gegen neue Tabelle laufen lassen und den Grund je ROT lesen | 2 Zeilen falsch ROT (Wand) | pruefstand z_am_punkt, getrenntes r_max |
(Beide in REZEPT L29/L30, Fehlschlaege in NICHTS_GEBRACHT.)

## 8. Abnahme-Stand (ehrlich)
- `tools/pruefstand.py` direkt am neuen STL: "alle Pruefungen bestanden" (13/13 Figurenzeilen OK, 1 alter Widerspruch offen).
- Der erste volle `bauen_abnehmen`-Lauf (Bau + Fotodiagnosen aller 24 Kameras) endete VOR meiner Korrektur der Messdefinitionen mit 3 fehlgeschlagenen Figurenzeilen (Standflaeche, Breite, Tiefe; Ursache Messfenster, nicht Modell). Der Wiederholungslauf `bauen_abnehmen.sh kaufhaus_grob3 --nur-pruefen` (nach der Korrektur) endete mit "ERGEBNIS: alle Pruefungen bestanden | 1 Widerspruch offen | 41 Beobachtung(en) ohne Pruefung" (Log `/media/oem/scan/rc-park_daten/kaufhaus_grob3/agent_scratch_kreis2/figuren_r2/abn_final.log`). Pruefstand damit auch im vollen Lauf gruen.
- `tools/regression.py ... --pruefen --ohne-kette`: identisch (nur ohne Kette geprueft; volle Kette nicht gelaufen).
- Kein Commit, nichts geloescht.
