# Methode: Bauplan je Ebene und Abweichungsschleife (ab 21.11.2026)

Zweck: Die Kette von null soll erreichen, was früher nur mit dem Nutzer als Prüfer ging („passt noch nicht“ am Bild). Die Schleife ersetzt den Prüfer.
Entstehung, alle Läufe und Sackgassen: `modelle/LOGBUCH_SCHWABENTOR_KETTE_2026-11-21.md`. Offene Übergänge der Kette: `modelle/KETTE_LUECKEN_2026-11-20.md`.

## Gilt

### Grundsätze (Nutzer 21.11.2026)
- Ein Gebäude besteht aus mehreren EBENEN; jede Ebene bekommt ihren eigenen Bauplan. Ebenen in alle Richtungen, nicht nur parallel zur Wand.
- So wenig allgemeine Bauteile wie möglich: erst prüfen, was die triangulierten Fotokanten hergeben; nur der Rest kommt aus einem allgemeinen Bauteil und wird als ANNAHME belegt.
- Die Kette ersetzt den Nutzer als Prüfer: Abweichung Modell gegen Bauplan je Ebene, mit Ort, als Arbeitsliste; konvergierende Schleife.
- Dichte Wolke nur als grobe Gegenprobe (nicht dichter rechnen um ihrer selbst willen; Verbesserungen dort nur für Geschwindigkeit).
- Ergebnisse nur aus echten Kettenläufen zeigen; Proben von Hand als solche benennen. Zuerst Kette gegen Handstand vergleichen, dann bauen.

### Ablauf (Stufe `bauplan` in `tools/gesamtkette.py`)
1. **Ebenen finden**
   - Ebenen-Sweep je Wand: `tools/fassade_tiefe.py` -> `tools/vorbauten_bauplan.py` (Zone und Tiefe eines Vorbaus, grob).
   - Schichtstapel aus Kanten: `tools/ebenen_bauplan.py --stapel w0 w1 schritt` (dünne parallele Ebenen; Spitzen der Punktzahl = Ebenen). Noch nicht in der Kette.
   - Seitenebenen je Vorbau: `ebenen_bauplan.py --seiten 1` (Standard).
2. **Bauplan je Ebene** = dichte triangulierte Fotokanten auf dieser Ebene (`tools/ebenen_bauplan.py`, 4-6 s je Ebene auf der GPU) + feines Bild auf der Ebene (1 cm, `form_aus_wandbild.wandbild_fotos`).
3. **Maße aus Kanten** (`tools/ebenen_masse.py`): Ausladung, Kasten (Unter-/Oberkante, Breite), Konsolen (Zahl, Lage), Strebenfuß, Pfostenlage. Alle drei Koordinaten der Kantenpunkte nutzen (auch die Tiefe).
4. **Bau** (`bauteile.vorbauten_aus_json`, Zweig `kanten_mass`): einfache Körper aus den gemessenen Kanten; Katalogteile nur noch für das, was Kanten nicht hergeben.
5. **Abweichung je Ebene** (`tools/ebenen_abweichung.py`): Fotokanten an Modellfläche / an Modellkante, „Form fehlt“, „Detail fehlt“, „erfunden“, Flecken mit Ort, Bild je Ebene, Verlauf mit git-Stand; Gegenprobe dichte Wolke (`--wolke`).
6. **Schleife** (`tools/ebenen_schleife.py`, Treiber steht; noch nicht in `gesamtkette.py`): je Runde der größte Fleck; Umbau nur annehmen, wenn die Kennzahl seiner Ebene steigt und keine andere Ebene merklich fällt; ein Fleck, der zweimal nichts bringt, wird „offen“ gemeldet; Ende bei keinem großen Fleck, zwei Runden ohne Gewinn oder Rundengrenze.

### Gemessene Regeln und Schwellen (bisher nur am Schwabentor eingestellt - an einem zweiten Bauwerk prüfen)
- Schicht ist eine echte Ebene, wenn die dichte Wolke ≥ 80 % ihrer Kantenpunkte bestätigt (≤ 10 cm); ≤ 5 % = Scheintreffer (Drähte, Mehrdeutigkeit); 40-80 % einzeln prüfen.
- Sweep-Kandidat gilt nur, wenn er an das Bauteil anschließt (sonst Oberleitung als „Vordach“).
- Vorbau-Front: Streuung der Tiefe ≤ 0,8 m (Erker 0,5-0,6; Durchblick eines Torbogens 1,5).
- Durchgehende Kantenlinie = mindestens halb so lang belegt wie die längste Linie im Suchband.
- Tiefe ist die ungenaueste Koordinate eines Kantenpunkts (Front streute 1,05-1,35 m): Höhen auf wenige cm, Tiefen auf 10-15 cm.
- Der Handstand ist kein cm-Sollwert (Handpunkte hatten bis 0,38 m Unsicherheit); `tools/hand_vergleich.py` zeigt verlässlich nur FEHLT und grobe Abweichung.
- Kettenergebnis ohne Verbraucher im Generator = Fehler (Sackgassen-Tor in `gesamtkette.py`).

### Was aus Kanten geht / nicht geht (Erker Schwabentor)
- Geht: waagrechte Kanten (Brüstung unten/oben auf wenige cm am Handstand), Breite, Ausladung, Zahl und Lage der Konsolen, Schräge der Streben, Traufkante.
- Halb: Pfosten (Lage ja, Breite kaum - senkrechte Kanten sind dünn belegt).
- Nicht: Dachfläche (Ziegel geben keine stabilen Kanten), Stärke der Hölzer nach hinten, Knaggenform, Seitenflächen ohne Fotos von der Seite.

## Versucht (Ergebnis in einem Satz; Einzelheiten im Logbuch)
- Höhenfeld aus dem Sweep als Gestalt des Erkers: treppig, keine Pfosten/Streben - verworfen (Raster reicht für „wo“, nicht für Form).
- Katalog-Galerie mit automatisch gemessenen Grobmaßen: Bänder ±0,3-0,6 m daneben; vom Nutzer abgelehnt („nicht aus dem Baukasten“).
- Form aus Farbflächen des Bildes auf der Erkerebene: Pfosten fehlen, Gemäldestück fälschlich Front - verworfen (Farbe trennt Material nicht; Sweep-Tiefe löst < 0,4 m nicht auf).
- Feine Sweep-Tiefe mit 2-cm-Zellen: je Zelle zu verrauscht.
- Dichte Kanten auf der Erkerebene: 47 000-54 000 Punkte, Maße auf wenige cm - angenommen, in der Kette (Lauf 1121k: Erkerebene Kante 7 % -> 87 %, gesamt 35 % -> 56 %).
- Echte Seitenebenen am Erker: nur ~1700 Punkte (keine Fotos von der Seite) - Fotolücke.
- „Seitenriss“ der vorhandenen Kantenpunkte: keine neue Messung, nur die dritte Koordinate ausgelesen (Nutzer-Einwand 21.11. berechtigt) - keine eigene Stufe, keine Bestätigung.
- Schichtstapel 14 x 0,3 m an der Stadtseite: findet Wand, Erkerfront, Traufkante selbst; nicht mehr Punkte als zwei breite Läufe.
- Kennzahl „erfundene Modellkanten“: 75-94 %, weil das Wandrelief viele kleine Kanten erzeugt - so nicht brauchbar.
- Öffnungen aus den Kanten der Wandebene (`tools/oeffnungen_aus_kanten.py`, 21.11.): NUR aus Kanten findet es am Schwabentor weder Tor noch Rundbogenfenster (stabile Kanten belegen die Bögen nur zu 0-21 %, kein geschlossener Zug); mit der dichten Wolke als Fleckfinder (Rücksprung ≥ 3 Sigma, mindestens 7 cm) Tor (Breite 5,37, Kämpfer 3,66, Scheitel 6,34, Rundbogen aus dem Wolkenrand) und beide Fensternischen (1,73/1,64 breit, Scheitel 25,6, Form unbestimmt). Noch kein Verbraucher im Generator.
- Annahme „Lagekorrektur fehlt“: widerlegt (gleicher Rahmen, Vordach auf cm gleich).
- 24.11. Vordach flach statt geneigt/geschweift (Nutzer: Handstand schwab_v3 besser): Ursache `vordach_profil.messen` brauchte `kanten_mass.kasten` - bei dünnen Vorbau-Kanten (1122w-zc) kein Kasten → `vordach_profil.json` leer → Höhenfeld-Stufen/ebene Platte. Behoben: Grenzen ersatzweise aus dem Galerie-Band des Sweeps (`kasten_oder_ersatz`), Walm-Vordach ersetzt im Höhenfeld-Zweig die Zellen über der Traufe, Sweep-Pfosten ergänzen Kanten-Pfosten (`tools/test_vordach_ohne_kasten.py`). An Kopie: geschweift 12/14 Fotos.

## Offen
1. Schleife in die Kette einhängen; Kandidaten auf Vorbau-Ebenen und Wolkenflecken (Vordach, Durchfahrt). Lauf 2 (21.11.): 7 Runden, 7 angenommen, 0 verworfen, Ende „kein Kandidat mehr“: Stadtseite Fläche 83→97, Kante 50→74, Wolke 71→82; Süd Kante 23→54; West Kante 45→51 (Kästen, Echtheit am Bild noch ungeprüft). Lauf 1 verwarf den Wandversatz-Umbau (trug das Relief ab) → Wandversatz jetzt am Grundkörper.
2. Schichtstapel + Wolkenprüfung als Standard-Ebenenfinder in der Kette; Richtungen: Wände, schräg, waagrecht (Unterseiten).
3. Kennzahlen mit der Kantenstufe zusammenführen (eine Zahl je Sache; „erfunden“ nur für Kanten > 0,3 m).
4. Pfosten/Stäbe über den Mehrfoto-Sweep für Linien (Skill linien-features).
5. Vordach-Profil (Kanten blind; Wolke zeigt dort Form); Dachüberstand ist bisher ANNAHME 0,25 m, Schicht sagt ~0,35 m.
6. Wandebenen: Fenster, Uhr, Quader, Gesims über dieselbe Schleife statt Sonderwerkzeug je Bauteil.
7. Fotoauftrag: Seitenflächen von Vorbauten, Feldseite Schwabentor (4 Fotos).
8. Gegenprobe an einem zweiten Bauwerk (erst wenn das Schwabentor steht - Nutzer 21.11.).

## Belege
- Bilder: `modelle/schwabentor-1120/audit/abweichung_f00_vb0_vergleich.jpg`, `erker_kanten_dicht_probe.jpg`, `erker_ebenen_probe.jpg`, `erker_seitenriss_probe.jpg`, `ebenen_form.jpg` (verworfener Farbflächen-Versuch).
- Zahlen: `audit/ebenen_abweichung.json` + `_verlauf.jsonl`, `audit/ebenen_masse.json`, `audit/hand_vergleich.json` + `_verlauf.jsonl`.
- Daten: `/media/oem/scan/rc-park_daten/schwabentor-1120/ebenen/` (Kette), `ebenen_stapeltest/`, `ebenen_seitentest/`, `kanten_ebene_f00/` (Proben).
