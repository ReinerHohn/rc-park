# Kreis3 Fehlteil ff_+9_+5_+3 (Laubenrueckwand, Dienste) - 11.11.2026

## 1. Formbeschreibung (Stufe 0)
Fotos: 6120 (Nahe+Uebersicht der Joche), 6117 (Schraeg von Osten, Dienst frei), 6130 (von Westen, Dienst u -2,3), 6119 (Dienst hinter Pfeiler, nur Rippenansatz).
- Vorbefund: das Kreuzgewoelbe (Vorversuch/laube_rueck) ist inzwischen in main; die Gelbflecken im Kasten kommen jetzt u. a. von den **Diensten**.
- Zone Sockelband z 2,21: gedrehter/geriefter Sockel (Trommel) z 2,21-2,97, r ca. 0,215.
- Zone Schaft z 2,97-5,5: runder Schaft r ca. 0,185, halb vor der Wand (Achse n 7,34, Wandfront 7,28).
- Zone oben z ~5,5: Schaft laeuft in die Gewoelberippen aus (Rippen nicht modelliert).
- Grundriss: Kreis, Achse je Pfeilerachse (Pitch 6,02). Familie: vorhandene `zylinder` (baukasten_gen), je Dienst Sockel + Schaft.
- Modell vorher: nur glatte Wand (Front n 7,28).
Unsicher: Dienst u 3,5-3,7 (neben Tuernische/Portal), u -8,3 und 15,8 nicht gesehen.

## 2. Zaehlungen
Kein Z-Protokoll; Anzahl der gebauten Dienste (2) = gemessen 1 (u 9,745) + 1 per Pitch (ANNAHME, in 6130 nur visuell bestaetigt). Keine Zaehlart "Anzahl je Flaeche" als Sollwert gesetzt.

## 3. Pruefungen (masstabelle.json)
| Pruefung | vorher | nachher | Soll | Quelle |
|---|---|---|---|---|
| Dienst u 9,75 z 4,4 Vorsprung ab n 6,9 | 0,380 ROT | 0,62 OK | 0,565-0,685 | M-6120-064/-068 |
| Dienst u 9,75 z 2,6 Vorsprung | 0,380 ROT | 0,65 OK | 0,60-0,72 | M-6120-065/-068 |
Gesamt: "alle Pruefungen bestanden". Messprotokolle M-6120-064..068.

## 4. Overlays
- modelle/kaufhaus_grob3/audit/gitter_generator/rundekreis3_dienst_6120_vorher.jpg / _nachher.jpg / _vs.jpg / _nachher_voll.jpg
- audit/foto_diff_6120.jpg, audit/seiten.jpg (angesehen: Gesamtmodell unauffaellig)
- Nur 6120 als Vorher/Nachher; 6117/6130 nur als Messgrundlage gesehen, Overlay nachher fuer 6117/6130 NICHT erzeugt.

## 5. Fehlerliste
- trifft: Dienst u 9,745 (Reichweite/Breite gegen Foto 6120-Messung); Sichtblatt ok.
- Foto-Diff 6120: gelb 0,1475 -> 0,1115, rot 0,031 -> 0,040 (Foto-Kantenzahl nicht identisch -> nur Indiz).
- trifft nicht / fehlt: Rippenvorsprung, Kreuzstock-Fenster der Rueckwand (flach), Portalrahmen Tuer, Dienst u 3,5.
- ungeprueft: Dienst u -2,30 (nur Annahme), u -8,3/15,8, Foto-F1-Gate (teil_fotoform nicht gelaufen), teile_lage_pruefen, fehlteile_finden, Regression (keine Werkzeugaenderung).

## 6. Geaenderte Dateien
modelle/kaufhaus_grob3/objekt.json (4 zylinder-Bauteile), masstabelle.json (2 Messungen, 2 Pruefungen, 1 Beobachtung), messprotokoll/M-6120-064..068, NICHTS_GEBRACHT.md, REZEPT_GEBAEUDE_AUS_FOTOS.md, audit-Dateien, STL.

## 7. Generalisierte Lehre
Lehre: Senkrechte Rundteile per Achspeilung (--tri2d) + Vorsprungs-Schnittpruefung belegen | Anlass: Dienste fehlten | Werkzeug: foto_mass --tri2d, schnitt_reichweite (L-KR40 eingetragen).

FEHLTEIL-BEFUND: gebaut
