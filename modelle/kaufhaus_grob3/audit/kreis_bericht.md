# Kreis eckfig r1 – erker_polygon:0 Eckfiguren (Zipfel/Drachen-Speier an den Traufecken)

## 1. Formbeschreibung (Stufe 0)
Fotos: 6145 (Nahfoto, links-frontal), h13 (frontal schräg), i08 (Nahfoto), 6225 (von unten, Nahfoto), 6164/6162 (Erker 2 bzw. Übersicht). Modell-Eckpunkte des Traufgesimses (z 12,74) in die kalibrierten Fotos projiziert.
- Zone Traufe: unter dem Helm läuft das Traufgesims (Kehle, aus 0,26) um das Teil-Achteck. An den Außenecken sitzen geschnitzte, rotbraune Konsolfiguren (Drachen/Wasserspeier): Rumpf hängt an der Gesimsecke, Kopf/Arm kragt nach außen. Größe ~0,3 m breit, ~0,45 m hoch.
- Erker 1 (u -8,47): Figuren an den Achteck-Ecken 2, 3, 4 (zwei Front-Ecken + Ecke zur Außenseite); Ecke 1 (Hausmitte-Seite) in 6145/h13/i08 ohne Figur. Erker 2 gespiegelt (Ecken 1,2,3) – an 6164 gesehen (ANNAHME Spiegel, nicht gezählt).
- Mittelfigur der Frontfläche (Nutzerhinweis 6164): an Erker 1 in keinem Foto gefunden – nicht gebaut.
- Formfamilie: neue generische Option `eckfiguren` in `erker_polygon` (tools/baukasten_gen.py): Rumpfblock bis z_ende + auskragender Kopfblock (vereinfachte Keilform, keine Schnitzdetails).
- Offen: Rückseite/Detailform (Drachenkopf) = ANNAHME.

## 2. Zählungen
Z-h13-001 (3 Figuren), Z-6145-002 (3 Figuren), beide Erker 1.  Triangulation M-6145-003 (6145+h13): Unterspitze Figur Ecke 3 (-3,94 / 16,35 / z 12,67 ±0,06).

## 3. Prüfungen (masstabelle.json, messungen eckfigur_zmin_*)
| Prüfung | vorher | nachher | Soll | Quelle |
|---|---|---|---|---|
| Ecke 2 tiefster Punkt (z−z0) | 11,29 ROT | 11,22 OK | 11,117–11,267 | Z-h13-001 |
| Ecke 3 | 11,29 ROT | 11,22 OK | 11,117–11,267 | M-6145-003 |
| Ecke 4 | 11,29 ROT | 11,22 OK | 11,117–11,267 | Z-6145-002 |
| Ecke 1 (keine Figur) | 11,29 OK | 11,29 OK | 11,267–11,307 | Z-h13-001/6145 |
bauen_abnehmen.sh kaufhaus_grob3: „alle Pruefungen bestanden“ (nach Änderung zweimal gebaut, einmal Werte nachjustiert); regression.py --pruefen: identisch.
Foto-F1 (10 Torfotos, RCPARK_FOTO_SKALA=0.5): 0,614 → 0,619 (Praez 0,769→0,762, Recall 0,511→0,522); f1_fein 0,574→0,573; f1_h 0,569→0,579. Gewinn klein (<0,03 = nicht unterscheidbar, L46) – Gate-Bedingung (≥ −0,005) erfüllt, Form aus Foto, nicht aus Sweep.

## 4. Overlays
- modelle/kaufhaus_grob3/audit/gitter_generator/rundekreis1_erker_polygon0_h13.jpg, …_6145.jpg, …_i08.jpg (Foto | nachher | vorher, mit Fotokanten); auch erker_polygon__0_6225.jpg (Erstvariante, größer).
- Fotoform-Overlays: …/20261111_185943eckfig/ff_nachher_bilder/

## 5. Fehlerliste
- Trifft: Ort der Figuren an Ecke 2/3/4 in 6145, h13, 6225 (Overlay angesehen); tiefster Punkt (M-6145-003).
- Trifft nicht / vereinfacht: Figuren sind Blöcke, keine Drachen; Größe Sichtschätzung (ANNAHME); Auskragung in Fotos nicht trianguliert.
- Ungeprüft: Erker 2 (nur Projektion an 6164, Maße übernommen); i08 nur grob; foto_diff/fehlteile_finden nicht separat ausgewertet (lief im Bau-Skript, keine Treffer an den Ecken geprüft); teile_lage_pruefen erker_polygon:0 Median 0,11 m, 24 % > 0,5 m (Vorbestand).
- Mittelfigur Frontfläche: nicht gefunden → nicht gebaut.

## 6. Geänderte Dateien
tools/baukasten_gen.py (eckfiguren), modelle/kaufhaus_grob3/objekt.json (eckfiguren Erker 0/1), masstabelle.json (4 Prüfungen, Beobachtung erledigt), messprotokoll Z-h13-001, Z-6145-002, M-6145-003, NICHTS_GEBRACHT.md, REZEPT (L58), audit/*, MASSNACHWEIS.md u. a. automatisch.

## 7. Generalisierte Lehre
Eckpunkt-Projektion in kalibrierte Fotos entscheidet, welche Ecken ein Detail tragen | Anlass: 'Zipfel an jeder Ecke' | Werkzeug: Projektionsskript + pruefstand min_im_bereich (Anzahl über Lagepruefungen mit Negativprobe). Erste Formannahme (Spitze außen) widersprach der Triangulation – tiefsten Punkt immer messen, bevor die Form gesetzt wird.
