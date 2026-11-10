# Kreis r3: fensterreihe:eg1 (kaufhaus_grob3, 2026-11-10)
Befund: Beleg 0,94 (Median 0,07), Kanten None -> Guete = Beleg. Ergebnis: Beleg 0,998 (Median 0,03), Guete +0,058 (Gate +0,05). Gesamt-Recall 0,6955 -> 0,6958, Praezision 0,1121 -> 0,1124; rueckschritt leer.

## 1. Formbeschreibung (Stufe 0)
Fotos (angesehen): 6120 (frontal, Uebersicht ~15 m), 6119 (+10 Grad), 6243 (-49 Grad, 9 m, Nahfoto), 6206 (+66 Grad, 6 m, Nahfoto), d17 (verwackelt, nur Sicht). d20 vom Pfeiler verdeckt.
- Zonen unten->oben: Sohle z 3,21 (Sohlbank-Relief, nicht modelliert) -> untere Reihe 2 Lichter -> Kaempferriegel (Kreuzstock, Mitte z 5,38) -> obere Reihe 2 Lichter -> gerade Oberkante z 6,32 (kein First, kein Bogen).
- Querschnitt: flaches Putzrelief (Rahmen/Setzholz/Kaempfer) mit Vorderflaeche 0,02 HINTER der Wandfront 7,28; Lichter tief in der Laibung (Glas Wolke 7,11-7,20).
- Wiederholung: 2x2 Lichter (Z-6120-004, in 6119/6243/6206 gegengesehen; keine neue Zaehlung noetig). Anschluss: sitzt in der Laubenrueckwand Bogen 3, Tuer daneben (eg1_tuer, nicht angefasst).
- Am Altmodell anders: Front 7,40 (0,12 vor der Wand), kontur 0,14 zu hoch (Oberkante 6,46), Quader-Nische schnitt Setzholz.
Formfamilie: vorhandene fensterreihe mit nische_front_n/pfosten_oben_z (aus r2); kein Codeaenderung.

## 2. Zaehlungen
Z-6120-003/004 (bestehend, 2+2 Lichter), visuell in 6119/6243/6206 bestaetigt. Keine neue Z-Datei (ANNAHME: bestehende gilt).

## 3. Pruefungen
| Pruefung | vorher | nachher | Soll | Quelle |
|---|---|---|---|---|
| fenster_eg1_rahmenfront | -0,13 ROT | 0,02 | 0..0,06 | M-6243-004 (n 7,264 +-0,011, Paar 6206/6243 110 Grad), M-6119-011 (3 Kameras 7,259 +-0,037) |
| fenster_eg1_oberkante_l/r | 0,20 ROT | 0,02 | 0..0,06 | M-6120-025 (gerade 6,32) + Overlay |
| fenster_eg1_ueber_oberkante | -0,13 ROT | -0,01 | -0,02..0,02 | M-6120-025 |
bauen_abnehmen: alle Pruefungen bestanden (freiraum_audit schon vorher 'fehlgeschlagen', nicht Teil), 1 Teilnetz, wasserdicht, Wandstaerke 0,14. Keine Werkzeugaenderung -> regression.py nicht noetig. teile_lage_pruefen eg1: Median 0,04 m, 0 % > 0,5 m.

## 4. Overlays (cyan vorher, rot nachher, ohne Z-Puffer)
modelle/kaufhaus_grob3/audit/gitter_generator/rundekreis3_fensterreihe_eg1_6120.jpg, _6243.jpg, _6206.jpg, _6119.jpg, _alle.jpg. foto_diff 6119/6120/6161 rot 0,058/0,031/0,036 (Gate ok). audit/seiten.jpg angesehen: unauffaellig (eg1 dort nicht aufloesbar).

## 5. Fehlerliste
- trifft (am Bild gesehen): Aussenmasse/Oberkante 6,32 in 6120/6119, Rahmenfront (Triangulation + Wolke), Riegelhoehe 5,38, 2x2 Lichter, Rahmenstufung in 6243 deckt sich mit rot.
- trifft nicht / offen: Sohlbank-Relief und Fussverbreiterung des Rahmens (6120 unten), Sprossen unmodelliert; Laibungstiefe 0,17 nur aus Wolke-Glas; Rahmenbreite 0,10 seitlich nicht neu gemessen.
- ungeprueft: teile_sichtpruefung nicht gelaufen; fehlteile_finden/foto_diff-Treffer nicht einzeln betrachtet; eg2 hat dieselbe ANNAHME (tiefe 0,16, Giebelecken) -> naechster Kandidat.

## 6. Geaenderte Dateien
modelle/kaufhaus_grob3/objekt.json (eg1: tiefe, einbindung, kaempfer/scheitel, kontur, pfosten_oben_z, nische_*; quader:eg1_nische aktiv false), masstabelle.json (Beobachtung, 4 Pruefungen), messprotokoll M-6243-004, M-6119-011, elemente.json/pruefbericht/MASSNACHWEIS/STL (Build), konvergenz.jsonl, NICHTS_GEBRACHT.md, REZEPT (L-KR29), LOGBUCH_FENSTER_EG1_R3.

## 7. Generalisierte Lehre
Lehre | Anlass | Werkzeug
Geschwisterteile derselben Annahme sofort einzeln nachmessen | eg0->eg1 gleicher Tiefenfehler | foto_mass --tri
Hoehen per Wandebenen-Linien-Overlay pruefen, Gegenpruefung 'ueber Oberkante nur Wand' | kontur 0,14 zu hoch | Messung fenster_eg1_ueber_oberkante
