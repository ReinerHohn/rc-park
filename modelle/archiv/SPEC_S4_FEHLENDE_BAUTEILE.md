# Spezifikation S4: Stufe 3 Luecken - fehlende Bauteile finden (Mindestflaeche aus Aufloesung, Kacheln, Zier-Neuvernetzung)

Befund (Log 5.11., versuche.jsonl `null6-erkerfenster-ursache`, `figuren-druckbar-ursache`): Hauptproblem Kaufhaus sind FEHLENDE Teile (Fotokanten ohne Modell
35-59 %). Drei bekannte Ursachen: (1) `fassade_parsing --mind-flaeche 20` schliesst Vorbauflaechen (Erker 1-3 m2 je Achteckseite) aus - Erkerfenster wurden nie
gesucht; (2) OWLv2 sieht kleine Elemente (Figuren, Pfosten, Erkerfensterchen) auf dem 2x-hochskalierten Ortho nicht; (3) Bild-zu-3D-Netze (TripoSR) werden beim
Export zu Beruehrkanten (123-155 Koerper) - die Neuvernetzung auf Druckaufloesung ist bewiesen, aber nicht im Generator. Alles allgemein loesen, keine Erker-Sonderregel.

## 1. Mindestflaeche aus Aufloesung (`tools/fassade_parsing.py`, `tools/fassade_ortho.py`)
- Statt `--mind-flaeche 20.0` (m2): eine Flaeche wird geparst, wenn ihr Ortho mindestens `--mind-px 96` Pixel in der kleineren Ausdehnung hat UND mindestens
  `--mind-fotos 3` Fotos mit Guete > 0 liefert. Fuer kleine Flaechen (< 20 m2) werden Orthos mit hoeherer Aufloesung erzeugt (`fassade_ortho`: Pixelgroesse je
  Flaeche = min(--mpp, kleinere Ausdehnung / 256 px)), damit ein 2 m breiter Erkerstreifen 256 px breit ist. `--mind-flaeche` bleibt als Option fuer alte Plaene,
  Standard = aus (0). Begruendung im Docstring: Mindestflaeche war eine Handschwelle (Fehler 1), Aufloesung ist die physikalische Grenze.
- Vorbauflaechen (`--waende-stl`) werden im Laeufer-Versuch `vorbau_fenster` schon erzeugt; nach dieser Aenderung muss derselbe Versuch Erkerflaechen e00-e19 parsen.

## 2. OWLv2-Kacheln (`tools/fassade_parsing.py`)
- Ortho in Kacheln von 960 px mit 25 % Ueberlappung (Prozessorgrenze OWLv2), je Kachel erkennen, Boxen in Ortho-Koordinaten zurueckrechnen, NMS (IoU 0,5) ueber
  Kachelgrenzen; `--hoch` bleibt (2x) nur fuer Orthos < 960 px. Textembeddings einmal je Lauf cachen, fp16 auf GPU (`torch.autocast`), Kacheln als Batch (Groesse nach VRAM-Budget wie `qualitaetsstufen.vram_budget`).
- Gegenbegriffe (aus `zier_ausschnitt.py --pruefen`) fuer alle Klassen uebernehmen (Schild, Lampe, Markise, Wappen), damit Fehltreffer sinken.
- Zaehlung bleibt am Foto (Regel 9): die Abstimmung ueber Fotos (`--mind-stimmen`, `--anteil`) unveraendert; Z-Protokoll je Fassade und Klasse automatisch schreiben
  (`messprotokoll/Z-<foto>-<nr>.json` mit markiertem Bild, Format wie `foto_zaehlung.py`; Foto = das mit den meisten Zellen fuer diese Fassade). Damit koennen
  Pruefstand-Zeilen `anzahl` ohne Handzaehlung entstehen (Selbstbezugsregel beachten: das Protokoll ist NICHT die Datei, die der Generator liest).

## 3. Zier-Neuvernetzung im Generator (`tools/baukasten_gen.py` `figuren_netz`)
- Vor dem Einbau jedes Bild-zu-3D-Netzes: Neuvernetzung auf Druckaufloesung = Innen-Test (contains) auf einem Gitter mit Zelle `duese_mm x massstab / 1000`
  (ANNAHME Duese 0,4 mm, Objektparameter `druck.duese_mm`, 1:87 -> 3,5 cm), Marching Cubes, groesste Komponente, Volumen 90-100 % des Originals (sonst Element
  verwerfen mit Beleg "Netz unter Druckaufloesung"), dann Konsole (vorhandene Regel) und Vereinigung. `beleg(...)` mit Quelle und Zellgroesse.
- Gilt fuer ALLE Netz-Anbauteile (nicht nur Figuren): Funktion `netz_druckbar(mesh, zelle_m)` in `bauteile.py`, von `figuren_netz` und kuenftigen Klassen genutzt.

## 4. Beweise (`tools/test_s4.py`)
- T1 Erkerflaechen: `fassade_ortho --waende-stl` + `fassade_parsing` auf null6-Stand (s3_v9): Vorbauflaechen mit >= 3 Fotos werden geparst (Liste), Erkerfenster
  werden gefunden (Stimmen >= 2) - Anzahl je Erkerseite ins Z-Protokoll; Bild der Erkerseite mit Boxen ANSEHEN.
- T2 Kacheln vs. Hochskalieren auf der Hauptfassade f02: Erkennungen je Klasse vorher/nachher; Figuren: 4 (Foto 004 zeigt 4 Ritter); Fenster 1. OG: Zaehlung am Foto 004
  (manuell einmal als Z-Protokoll durch den Agenten: Fensterachsen 1. OG zaehlen, markieren) muss getroffen werden; keine Zusatztreffer auf Schildern.
- T3 Neuvernetzung: Lauf `figuren_auto` auf null6 (Trockentest wie kh_zier4): Ergebnis 1 Koerper, wasserdicht, Pruefstand gruen, Zier-Tor (IoU) mindestens wie V8 (0,557);
  Gegenprobe: ohne Neuvernetzung -> > 1 Koerper (wie V8).
- T4 Martinstor: `bauen_abnehmen.sh martinstor` gruen, Regression identisch (Werkzeug-/Generatoraenderung 8b); Kaufhaus-Regression: Abweichungen benennen.
- T5 Tor: Jeder neue Versuch (Erkerfenster, Figuren) muss das strenge Tor (S1b) bestehen; Ergebnis mit Buchstaben im Bericht. Fallen sie durch, ist das Ergebnis "Bauteil gefunden, Modell nicht besser" - so eintragen, nicht nachjustieren.
Plan-Datei `modelle/PLAN_STANDARD_qualitaetsstufen.json`: Versuch "Erkerfenster auf Vorbauflaechen" bleibt; keine objektbezogenen Werte.

## 5. Nicht aendern
`foto_diff.py`, `pruefstand.py`, `qualitaetsstufen.py` (S1b/S3 arbeiten dort); keine Sollwerte; GPU nur frei (nvidia-smi) oder ueber job_start (hat GPU-Sperre).
