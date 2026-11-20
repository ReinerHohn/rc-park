# Auftrag 6.11.2026 in Teilen: welches Modell macht was

Grundlage: `modelle/PLAN_2026-11-06_H0_DETAIL.md` (Reihenfolge-Tabelle Abschnitt 4). Jedes Teil ist so geschrieben, dass ein Modell ohne Sitzungskontext starten kann.
Pflichtlektuere fuer JEDES Teil: `CLAUDE.md`, der Plan, `modelle/LOG_2026-11-05_FEHLER_UND_STAND.md` Abschnitt 2 und 8.
Gemeinsame Regeln: Uhrzeit per `date`; lange Jobs nur ueber `tools/job_start.sh NAME LOG BEFEHL...`; nur ein GPU-Job zur Zeit (`nvidia-smi` vorher);
jedes Ergebnis als Zeile in `modelle/<objekt>/versuche.jsonl` (Felder datum, objekt, id, was, ergebnis, naechster_schritt); kein Commit, kein Push;
keine Aenderung an `tools/baukasten_gen.py`, `tools/qualitaetsstufen.py`, `tools/pruefstand.py`, `tools/foto_diff.py`, solange das Teil es nicht ausdruecklich erlaubt.
Ehrlich berichten: Zahlen nur mit Bild, Fehlschlag als Fehlschlag.

Modellklassen: **G** = guenstiges Modell (Sonnet/Haiku), **S** = starkes Modell (Fable/Opus). Reihenfolge innerhalb einer Klasse von oben nach unten.
Teile G1-G4 koennen parallel zu S laufen, aber nie zwei GPU-Jobs gleichzeitig.

---

## G1 (guenstig) - Platz schaffen und Platzpruefung
Ziel: Root-Platte (`/`, 48 GB, war 100 % voll) auf > 5 GB frei, Datenplatte `/media/oem/scan` > 15 GB frei, und ein Tor, das Laeufe vorher pruefen.
1. `df -h / /media/oem/scan`, `du -xsh /home/oem/* /var/* /usr/local/* 2>/dev/null | sort -h | tail -25`.
2. NICHTS loeschen. Kandidaten mit Groesse auflisten und den Nutzer fragen (bekannt: `~/macsx-flash-860.tar.gz`, `~/.cache` 842 MB, Ollama-Modelle unter `/usr/share/ollama`, alte Claude-Versionen unter `~/.local/share/claude/versions`, `/swapfile`).
   Verschieben nur nach Freigabe, Ziel `/media/oem/Volume/rc-park_archiv_2026-11-06/` mit `LIESMICH.txt` (was, woher, Datum).
3. `tools/platz_pruefen.py` NEU: Argumente `--root-min-gb 5 --daten-min-gb 15`, Exit 3 bei Unterschreitung, Ausgabe beider Werte.
   Einbau: Aufruf am Anfang von `tools/bauen_abnehmen.sh` und als erster Schritt in `tools/job_start.sh` (nur dort, keine anderen Werkzeuge anfassen).
   Gegenprobe: mit `--root-min-gb 999` muss er Exit 3 liefern.
Fertig: beide Platten ueber Grenze, Tor eingebaut und gegengeprueft, Versuchslog-Zeile in `modelle/kaufhaus/versuche.jsonl`.

## G2 (guenstig) - Laufende Jobs auswerten, Regression, Beweise
Ziel: Werkzeugaenderungen vom 5.11. sind regressionsgeprueft (Regel 8b); der Stand von `--mehrstufig` ist belegt.
1. Warten bis `JOB_ENDE` in `/media/oem/scan/rc-park_daten/kaufhaus/kh_abnahme.log` und `.../video_suche.log` (Monitor, nicht pollen). Ergebnis je Log in einem Absatz: rc, Pruefstand-Ergebnis, Regression identisch oder geaendert (welche Dateien).
   Regression Kaufhaus "geaendert" ist ERWARTET (Eckpfeiler, Halle); Schnappschuss NICHT erneuern, nur melden.
2. Martinstor: `tools/bauen_abnehmen.sh martinstor` und
   `/media/oem/scan/venv-seg/bin/python -W ignore -I tools/regression.py modelle/martinstor/objekt.json --pruefen` (ueber job_start, Log `/media/oem/scan/rc-park_daten/martinstor_regression_2026-11-06.log`). Muss identisch sein. Wenn nicht: Diff-Dateien nennen, nichts aendern, STOPP und melden.
3. `tools/test_foto_diff.py` an beiden Objekten, je einmal ohne und einmal mit `--fd "--mehrstufig"`:
   `.../python -I tools/test_foto_diff.py modelle/kaufhaus_null5/objekt.json --foto 004` und `... modelle/martinstor/objekt.json --foto 014` (GPU; vorher `nvidia-smi` leer).
   Ergebnis als Tabelle T0-T6b je Objekt je Variante. Keine Schwelle lockern.
4. `audit/seiten.jpg` beider Objekte ANSEHEN und je 2 Saetze schreiben, was man sieht.
Fertig: vier Testlaeufe mit Tabelle, Regression Martinstor identisch, Versuchslog-Zeilen. Entscheidung "mehrstufig = Standard" trifft S2, nicht G2.

## G3 (guenstig) - Video-Stufe Kaufhaus
Ziel: Die gefundenen Clips werden zur Punktwolke und zu Kameras, mehr Blickwinkel fuer Erker, Gauben, Rueckseite.
1. `/media/oem/scan/rc-park_daten/kaufhaus/video_suche/video_kandidaten.json` lesen; Clips mit >= 8 Objektfotos in `modelle/kaufhaus_null5/objekt.json` unter `video_stufe` eintragen (Format wie beim Martinstor in `modelle/martinstor/objekt.json` nachsehen). Lizenz je Clip in `modelle/kaufhaus_null5/LIZENZ_BILDER.json` (YouTube-Standardlizenz = nur Test, Vermerk "Lichtbildschutz Dritter, Verkauf pruefen").
2. Lauf: `tools/job_start.sh kh_video /media/oem/scan/rc-park_daten/kaufhaus/video_2026-11-06.log /media/oem/scan/venv-seg/bin/python -I tools/nullstart.py modelle/kaufhaus_null5/objekt.json --ziel kaufhaus_null5 --ab video --videos --ohne-stufen`
   (vorher pruefen, ob `--ab video` beim Zielordner `kaufhaus_null5` die vorhandenen Netze wiederverwendet; wenn der Schritt neu rechnen will, STOPP und melden).
   Frames und Zwischenergebnisse NUR auf der Datenplatte. Platzpruefung vorher (G1).
3. Nach dem Lauf: Kamerazahl je Seite vorher/nachher (`tools/abdeckung_quellen.py`), `audit/beweis_anker_uebersicht.jpg` ansehen, Ausrichtungsfehler der Videofragmente aus dem Log.
Fertig: Tabelle Kameras je Seite vorher/nachher, Bilder angesehen, Versuchslog. Keine Generatoraenderung.

## G4 (guenstig) - Stadt-Freiburg-LoD2 als zweite Dachquelle, Stadtmesh-Lader als Pruefreferenz
Ziel: Quellentypen 18 und 19 aus `modelle/QUELLEN_REGISTER.md` sind geladen und im Inventar gruen; nichts davon geht in den Generator.
1. Stadt-LoD2 GML (Link im Register, DL-DE BY 2.0) nach `/media/oem/scan/rc-park_daten/freiburg_stadt_lod2/` laden, Lizenzvermerk in `modelle/LIZENZ_WERKZEUGE.md` (Code/Daten getrennt).
   `tools/stadt_lod2_schneiden.py` NEU: Gebaeude innerhalb des Objekt-Umrisses (aus `modelle/<objekt>/objekt.json` bzw. LGL-LoD2-Fussabdruck + 2 m) als eigene Datei `modelle/<objekt>/stadt_lod2.json` (Flaechen, First, Traufe, Georeferenz EPSG pruefen und dokumentieren).
   Vergleich zum LGL-LoD2: First, Traufe, Grundriss je Objekt (Kaufhaus, Martinstor) als Tabelle. Abweichungen NICHT mitteln, nur eintragen als `beobachtungen_offen` in `masstabelle.json` (Felder `wer`, `text`, Quelle "STADT_LOD2").
2. `tools/stadtmesh_laden.py` NEU: tileset.json von `https://3d.freiburg.de/datasource-data/2025_befliegung/22_Mesh3D_Cesium` lesen, nur Kacheln im Objekt-Umriss laden (Datenplatte), zu einem GLB/PLY im Objektrahmen zusammensetzen. Wenn Kacheln 401/403 liefern: dokumentieren, STOPP. Lizenzklasse "ungeklaert" in `LIZENZ_WERKZEUGE.md`; Datei nur unter `audit/referenz_stadtmesh/`.
   Nur ein Bild: Mesh gegen aktuelles Modell im Viewer-Render (`tools/foto_render_seite.py` o. ae.), ansehen, 3 Saetze.
3. `tools/quellen_inventar.py --name kaufhaus_null5` und `--name martinstor`: Typ 18 gruen, Typ 19 "Pruefreferenz".
Fertig: beide Dateien je Objekt, Vergleichstabelle, Inventar-Ausgabe, Versuchslog. Keine Sollwerte aendern.

## G5 (guenstig, nach S1) - Ressourcen-Sperre und Pre-Commit-Pruefung
1. `tools/job_start.sh`: Sperrdatei `/media/oem/scan/rc-park_daten/.gpu_lock` mit Jobname, wenn der Befehl ein GPU-Werkzeug ist (Liste in `tools/gpu_werkzeuge.txt`); zweiter GPU-Job wartet (Meldung alle 60 s) statt zu starten. Gegenprobe mit zwei Dummy-Jobs.
2. `tools/git_hooks/pre-commit`: Wenn `tools/baukasten_gen.py` im Commit ist, muss auch eine `masstabelle.json` oder `tools/test_*.py` im Commit sein, sonst Abbruch mit Hinweis auf CLAUDE.md Regel 2. Gegenprobe mit `git stash`-freiem Trockenlauf (`bash tools/git_hooks/pre-commit` auf gestagten Dateien).
Fertig: beide Gegenproben protokolliert.

---

## S1 (stark) - Uebernahmetor streng + Elementbuch
Ziel: Fehler 2 und 5 vom 5.11. sind technisch unmoeglich.
1. Zuerst Sichtfund als Pruefung: Masstabelle `kaufhaus_null5` bekommt eine Zeile, die am Freiraum-Modell mit den Eckoeffnungen (null6 V2) FEHLSCHLAEGT und am Stand mit genau 4 Boegen besteht (Anzahl Oeffnungen Front = Foto-Zaehlung Z-Protokoll, Regel 9).
2. `tools/qualitaetsstufen.py` `tor_ok` erweitern: Uebernahme nur, wenn (a) in jedem Bewertungsfoto rot UND gelb nicht schlechter als Stand + Toleranz aus Saatstreuung (`FD_SAAT`, messen), (b) Summe deutlich besser (gepaarter t >= 2), (c) Restfeld je Ebene nicht schlechter, (d) Pruefstand gruen, (e) druckbar (1 Koerper, wasserdicht, Mindestbreite). Jede Ablehnung mit dem verletzten Buchstaben im Log.
3. Elementbuch `modelle/<objekt>/elemente_best.json`: je Fassadenelement (Klasse, Fassade, u/v-Box) bester Stand mit lokaler Kennzahl (rot/gelb in der Element-ROI ueber alle Fotos, die es sehen). Ein Kandidat darf ein Element nur ersetzen, wenn es lokal besser wird; globaler Gewinn reicht nicht.
4. Beweis: synthetischer Test `tools/test_tor_elementbuch.py` (Stand mit 4 Boegen; Kandidat mit 2 Zusatzoeffnungen wird abgelehnt; Kandidat mit richtiger Halle wird angenommen), Kaufhaus auf null6 s3_v9 nachgerechnet, Martinstor-Regression identisch.
Darf aendern: `qualitaetsstufen.py`, `pruefstand.py` (nur neue Pruefung), neue Tests. Nicht: `baukasten_gen.py`.

## S2 (stark) - Entscheidung mehrstufige Kanten + foto_diff-Pflichten
Eingabe: Tabellen aus G2. Entscheiden, ob `--mehrstufig` Standard wird (alle Beweise bestanden, Bild besser). Wenn ja: Standard setzen, `test_foto_diff` in `regression.py` bzw. Schritt `beweise`, Schnappschuesse nur mit Register-Eintrag erneuern. Verdecker-Maske: Himmel bleibt, nur Inneres von Personen/Fahrzeugen/Laub (Tiefenkarte; SAM 2.1 Apache nur, wenn Tiefenkarte nicht reicht).
Darf aendern: `foto_diff.py`, `regression.py`, `test_foto_diff.py`.

## S3 (stark) - Stufe 4 Konvergenzschleife
Nach S1 und S2. Umsetzung nach Plan Abschnitt 3 Stufe 4: Fehlerkarte je Fassadenzelle (`tools/fehlerkarte.py`: rot/gelb-Dichte, Restfeld, Freiraum, Kamerazahl), Cluster -> Kandidaten aus vorhandenen Bauteilregeln mit Schwellen als Suchparametern, Tor aus S1, Abbruchkriterium, monotone lokale Kennzahl im Bericht.
Beweis: Stoertest (Bogen zumauern, Erker entfernen, Gaube versetzen -> Schleife findet zurueck), Kaufhaus gelb faellt ueber >= 3 Laeufe monoton, Martinstor nicht schlechter. Jeder Lauf mit Bild vorher/nachher je Foto.
Darf aendern: `qualitaetsstufen.py`, `nullstart.py` (Schritt `konvergenz`), `baukasten_gen.py` NUR fuer Parameter-Durchreichung, mit `bauen_abnehmen` beider Objekte danach.

## S4 (stark) - Stufe 3 Luecken (fehlende Bauteile)
Mindestflaeche in `fassade_parsing.py` aus Pixel/m statt 20 m2; OWLv2-Kacheln 960 px mit Ueberlappung und NMS; Zier-Neuvernetzung auf Druckaufloesung im Generator (`figuren_netz`), Konsole, Vereinigung; Gauben/Bruestung/Erkerfenster nur ueber die Schleife aus S3 (gelbe Cluster mit Tiefe in >= 2 Fotos), keine Sonderregeln.
Beweis: Erkerflaechen werden geparst (Zaehlung am Foto), Tor aus S1 nimmt sie an oder lehnt mit Buchstaben ab; Figuren 1 Koerper wasserdicht.

## S5 (stark) - Stufe 5 Feinlage je Foto, Mehrfoto-Befund
Lokaler Kameraversatz je Bildzone (Kreuzkorrelation der Kantenbilder je Richtung) als Pruefung, dann Feinlage der Kamera mit Tor gegen Buendel-Beobachtungen; Befund nur bei >= 2 Fotos; Schwelle "deutlich" statistisch (0,2/0,4/0,6 m). Normalenkanten (MoGe-2, MIT) als Gegenprobe, Lizenz je Gewicht in `LIZENZ_WERKZEUGE.md`.

## S6 (stark) - Stufe 6-8 Druck, Bericht, Abschlusstor, Nachtlauf ohne Eingriff
Duesenregel im Pruefstand (0,85 x Duese, tragend 2 x), Fassadenplatten je Seite in `druckteile_auto.py`, Teil-gegen-Foto automatisch, `lauf_bericht.py`, Viewer aus dem Lauf, Abschlusstor. Danach Kaufhaus-Nachtlauf von Null ohne Eingriff, dann Martinstor durch dieselbe Kette.

---

## Nutzer (Hand, unvermeidbar)
- Freigabe fuer G1 (was verschoben werden darf).
- Mails: bDOM (`modelle/LGL_BESTELLUNG_BDOM.txt`), ALS (`LGL_BESTELLUNG_ALS3.txt`, Zweck "kommerzieller Modellbau"), Stadtmesh-Lizenz (vermessung@freiburg.de).
- Handyfotos: streifende Blicke entlang der Kaufhaus-Front, Rueckseite, Martinstor Sued; in den Foto-Eingang legen.
- Testgitter 0,2-Duese drucken, fotografieren.

## Uebergabe zwischen Modellen
Jedes Teil endet mit einem Absatz in `modelle/STAND_2026-11-06.md` (Datum per `date`, Teilname, Ergebnis, offene Punkte, Dateien). Das naechste Modell liest diese Datei zuerst.
