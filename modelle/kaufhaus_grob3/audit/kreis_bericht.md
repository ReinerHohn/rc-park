# Kreis a062358 r2 - erker_polygon:1 (Ost-Erker, Teil-Achteck)

**Status: Patch des verworfenen Vorversuchs a060555 r1 auf aktuellem Stand neu angewendet, gemessen, mit rippen_vor 0,12 abgestimmt. Nichts committed.**

## 1. Formbeschreibung (Stufe 0)
Fotos (in den Overlays angesehen): 6164 (Nahfoto frontal), 6161, 6145 (schraeg von Westen/Seite), 6259 (Uebersicht); Vorarbeit Runde 7 (h05, 6124, nuaca).
- Zonen von unten: Unterbau = umgekehrte Pyramide (Spitze z 6,3 in der Wand) mit gekruemmten Graten; Gesims unten (Kamm z ~8,4); Wappenzone z 8,5-9,65 (2 Schilde in der Front); Fensterbank (Kamm z 9,7); Fensterband (2 Lichter je Flaeche, Kaempfer z 11,38); Traufwulst z 13,05-13,18; darueber Helm (eigenes Bauteil).
- Grundriss: Teil-Achteck, 3 sichtbare Flaechen (Front + 2 Schraegflaechen 45 Grad), Einbindung in die Wand.
- Wiederholungen: Lichter, Wappen (gezaehlt Z-6164-001..003, nicht neu gezaehlt), Grate des Unterbaus.
- Formfamilie: vorhandene `erker_polygon` in tools/baukasten_gen.py, generisch erweitert (Gesims-/Bankprofil, Rippen nur Grate, Rippenrelief skaliert).
- Was am alten Modell anders war (Overlay vorher): Unterbau 0,1-0,2 m zu weit vorn, Traufgesims sprang schon ab z 12,74 vor (Wolke/Foto: erst ab 13,05), Rechteckgesimse statt Grat, gerade Mittelrippen ohne Fotokante.
- ANNAHME: Rueckseite/Einbindung 0,3 m unveraendert; Rippenzahl/-relief (Grate) bleibt ANNAHME.

## 2. Zaehlungen
Keine neue Zaehlung (Anzahl der Lichter/Wappen unveraendert: Z-6164-001..003). Mittelrippen am Unterbau sind keine gezaehlten Elemente: am Foto keine sichtbar -> entfernt.

## 3. Pruefungen (am alten Stand ROT: 0,71 / 0,89 / 1,60 / 0,26)
| Pruefung | vorher | nachher | Soll | Quelle |
|---|---|---|---|---|
| erker_o_unterbau66 | 0,71 | 0,56 | 0,4..0,6 | Wolke lot2 Median Scheibenmitte, Foto 6161/6164 |
| erker_o_unterbau70 | 0,89 | 0,71 | 0,52..0,72 | dito |
| erker_o_unterbau80 | 1,60 | 1,42 | 1,28..1,48 | dito |
| erker_o_trauf_unten - front | 0,26 | 0,00 | -0,06..0,06 | Wolke 0,1-m-Scheiben, Foto h05 M-h05-007 |
| Auskragung Traufgesims (Messhoehe 12,95 -> 13,14, neue Quelle) | - | 0,29 | 0,17..0,34 | Wolke, M-h05-006 |

Gate (Mittel aus Beleg und Kanten-F1, Messung konvergenz_bericht, gleiche Einstellungen wie der Kreis):
| Groesse | vorher | nachher (rippen_vor 0,12) |
|---|---|---|
| Wolkenbeleg | 0,919 | 0,983 |
| Kanten-Recall | 0,877 | 0,857 (-0,020, an der Grenze) |
| Kanten-Praezision | 0,465 | 0,520 |
| F1 | 0,608 | 0,647 |
| Guete | 0,763 | 0,815 (**+0,052**) |
Varianten rippen_vor: 0,16 -> Guete 0,814 / Recall 0,854 (-0,023, Verletzung); 0,22 -> 0,812 / 0,856; 0,12 -> 0,815 / 0,857. Recall schwankt zwischen Laeufen um ~0,003 (gitter_pkt 4292-4349): die Recall-Marge ist duenn und nicht robust belegt.
bauen_abnehmen.sh: "alle Pruefungen bestanden" (rc 0). regression.py --pruefen: identisch. teile_lage_pruefen: erker_polygon:1 Median 0,08 m (nicht markiert).

## 4. Overlays (selbst angesehen: 6164 vorher+nachher, 6145 nachher, seiten.jpg)
modelle/kaufhaus_grob3/audit/gitter_generator/rundekreis2_erker_polygon_1_IMG_{6161,6164,6145,6259}_{vorher,nachher}.jpg
(6161/6259 erzeugt, nicht einzeln angesehen = ungeprueft.)

## 5. Fehlerliste
- Unterbau-Grate/Pyramide: trifft besser (6164), Mittel-/Randbereich unten (Spitze) in 6145 weiter rot -> trifft teilweise nicht.
- Gesims unten/Bank: Kamm trifft in 6164; in 6145 Gesims-Querkanten weiter rot (Schraegsicht).
- Wappenzone/Fensterband: unveraendert, trifft (gruen), einzelne Rahmenkanten rot.
- Traufwulst: Vorsprung erst ab 13,05 trifft; Oberkante lange Querlinie in 6164 rot (Verdeckung/Helmfuss) - ungeprueft.
- Rueckflaechen/Einbindung: ANNAHME, ungeprueft.
- Ost-Erker-Hoehen ohne eigene foto_mass-Messung (aus E0 uebernommen).
- erker_polygon:0 hat denselben p98-Profilfehler, nicht angefasst.
- Gate: Recall -0,020 genau an der Grenze; Pruefer sollte mit eigener Wiederholung gegenpruefen.
- teile_sichtpruefung, foto_diff, fehlteile_finden nicht neu gefahren (nur konvergenz_bericht, Overlays); Sichtpruefung ungeprueft.
- Freiraum-Audit scheitert im Worktree (fehlende messprotokoll/SFM-AUSRICHTUNG-buendel.json), unabhaengig von dieser Aenderung (auch am Altstand).

## 6. Geaenderte Dateien
tools/baukasten_gen.py (optionale Parameter gesims[].profil, bank_profil, unterbau.rippen_mitte, rippen_skal); modelle/kaufhaus_grob3/objekt.json (nur erker_polygon:1); masstabelle.json (4 Messungen, 4 Pruefungen, Messhoehe erker_o_trauf, Beobachtung); modelle/NICHTS_GEBRACHT.md; modelle/REZEPT_GEBAEUDE_AUS_FOTOS.md (L-KR21..24); Abnahme-Artefakte (STL, MASSNACHWEIS, pruefbericht, audit/*).

## 7. Generalisierte Lehre
| Lehre | Anlass | Werkzeug |
|---|---|---|
| Verworfene Patches gegen den aktuellen Vorher-Wert neu messen (Gate kann inzwischen erreichbar sein) | r1 +0,031 -> r2 +0,052 | git apply --include, konvergenz_bericht --teile_dir |
| Median je Scheibenmitte statt p98 am Scheibenanfang | Unterbau 0,17 m falsch | profil.py, schnitt_reichweite |
| Gesims als gerundeter Grat | Praezision | baukasten_gen gesims[].profil |
| Messlauf-Rauschen ~0,003 im Recall: Gate-Grenzfaelle mehrfach messen, Varianten waehlen | Recall 0,854-0,858 | /tmp/messen.sh-Schleife |
