# Kreis r2: fensterreihe:eg0 (kaufhaus_grob3, 2026-11-10)
Befund: Beleg 0,875 (Median 0,078), Kanten None (gitter_pkt 0) -> Guete = Beleg. Ergebnis: Beleg 0,996 (Median 0,027), Guete +0,121 (Gate +0,05). Gesamt-Recall 0,696 -> 0,696, Praezision 0,112 -> 0,112; kein Teil faellt > 0,004 (laube_rueck Recall 0,286 -> 0,282, eg1 0,945 -> 0,944).

## 1. Formbeschreibung (Stufe 0)
Fotos (angesehen): 6119 (frontal, Uebersicht/Nah), 6174 (Azimut +60, 6,9 m), 6213 (Azimut -54, 8,4 m), 6171 (Azimut +20), plus Overlay-Ansichten.
- Zonen unten->oben: Sohle z 3,20 -> untere Reihe 2 Lichter -> Kaempferriegel (Kreuzstock, Mitte z 5,33) -> obere Reihe 2 Lichter -> gerade Oberkante z 6,28 (kein First).
- Querschnitt: Rahmen/Setzholz/Kaempfer als flaches Putzrelief, Vorderflaeche etwas HINTER der Wandfront (7,25 gegen 7,28, die Wand bildet eine schmale Randleiste); Lichter tief in der Laibung (Glas in Wolke 7,02-7,06).
- Wiederholung: 2 mal 2 Lichter (Z-6119-001, in 6174/6213 gegengeprueft).
- Anschluss: sitzt in Laubenrueckwand (n 6,83-7,28), Sohle ueber Bank.
- Am Altmodell anders: Rahmenfront 7,40 (0,12 VOR der Wand, ANNAHME 'wie eg1'); Ecken 6,18 + Giebel 6,28; Quader-Nische.
Formfamilie: vorhandene fensterreihe + zwei generische Optionen (nische_front_n mit Rahmen-Ruecksprung, pfosten_oben_z).

## 2. Zaehlungen
Z-6119-001 (2+2 Lichter, uebernommen); Gegenprobe visuell in 6174/6213/6171: 2 Spalten x 2 Reihen. Keine neue Zaehlung noetig (ANNAHME: Z-Protokoll nicht neu erzeugt).

## 3. Pruefungen (Altstand -> neu)
| Pruefung | vorher | nachher | Soll | Quelle |
|---|---|---|---|---|
| fenster_eg0_rahmenfront | -0,13 ROT | +0,02 | 0..0,06 | M-6174-001 n 7,249 +-0,016 (110 Grad), M-6119-008 (3 Kameras) 7,249 +-0,039 |
| fenster_eg0_oberkante_l/r | -0,01 ROT | 0,02 | 0,02..0,06 | M-6119-001 (flach 6,28), Overlay 6119 |
Weitere Messungen: M-6119-009 Setzholz-Vorderflaeche 0,10 m = pfosten_b (keine Aenderung). bauen_abnehmen: alle Pruefungen bestanden (freiraum_audit meldet schon vorher 'fehlgeschlagen', nicht Teil dieser Arbeit), 1 Teilnetz, wasserdicht, Wandstaerke 0,13. regression.py: identisch. teile_lage_pruefen eg0: Median 0,04 m, 0 % > 0,5 m.

## 4. Overlays (Cyan Vorher, Rot Nachher, ohne Z-Puffer)
audit/gitter_generator/rundekreis2_fensterreihe_eg0_6119.jpg, _6174.jpg, _6213.jpg, _6171.jpg, _alle.jpg. Dazu audit/foto_diff_6119.jpg (Fensterumriss gelb, vor/nach identisch), audit/seiten.jpg (angesehen, unauffaellig).

## 5. Fehlerliste
- trifft: Aussenmasse/Lage in 6119, Rahmenfront (Triangulation + Wolke), flache Oberkante (6119), Setzholzbreite, 2x2 Lichter.
- trifft nicht / offen: foto_diff-Treffer 1 (FEHLT 525 m bei u 13,15 z 5,2) ungeklaert, vor/nach gleich; Laibungstiefe 0,17 und Setzholz-Tiefe (einbindung 0,2) nur aus Wolke-Glas + Sichtbild (ANNAHME); Sohle/Sohlbank-Relief, Rahmenstufung, Sprossen unmodelliert.
- ungeprueft: Rahmenbreite 0,10 seitlich/oben (nicht nachgemessen), teile_sichtpruefung nicht gelaufen, fehlteile_6119 hat keine Treffer bei eg0.
- Nebenbefund: eg1 (Beleg 0,944) und eg2 (0,983) tragen dieselbe ANNAHME tiefe 0,16/Giebel-Ecken; nicht angefasst.

## 6. Geaenderte Dateien
tools/baukasten_gen.py (nische_front_n, Ruecksprung, pfosten_oben_z); modelle/kaufhaus_grob3/objekt.json (eg0: tiefe, einbindung, nische_*, kontur, pfosten_oben_z; quader:eg0_nische aktiv false); masstabelle.json (Beobachtung, 3 Pruefungen, 3 Messungen); messprotokoll K-6171/6174/6213, M-6174-001, M-6119-008..010; NICHTS_GEBRACHT.md; REZEPT (L-KR28); Build-Artefakte (STL, seiten.jpg, pruefbericht, fehlteile_*). Nicht committet.

## 7. Generalisierte Lehre
Lehre | Anlass | Werkzeug: (a) Ausschnitt-Quader schneidet auch Teile darin -> Laibung im Fensterteil | eg0 | nische_front_n; (b) Rahmentiefe aus Kreuzung der Rahmenglieder triangulieren | eg0 Front 7,249 | foto_mass --tri; (c) Abstandskarte + Wolken-n-Histogramm vor Foto-Messung | Beleg 0,875 | agent_scratch_kreis2/diag_eg0.py; (d) Kaempfer = Oberkante - rahmen_b ist Rechenfehler bei flacher Oberkante | Giebel | kontur-Rechteck.
