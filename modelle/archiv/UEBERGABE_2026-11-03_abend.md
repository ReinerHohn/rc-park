# Uebergabe 2026-11-03 (Abend) - Fahrplan zum vollautomatischen Nullstart

Ergaenzt `UEBERGABE_2026-11-03.md` (Stand morgens). Zuerst lesen: `CLAUDE.md`, `modelle/PLAN_VERBESSERUNG.md` (Abschnitt "Manuell -> Pipeline", M1-M11),
`modelle/martinstor/versuche.jsonl` (`python3 -I tools/versuch_log.py modelle/martinstor/objekt.json --zeige`), Memory `alles-vollautomatisch-pipeline`.

## HARTE REGELN (Nutzer, 3.11.)
1. **Alles vollautomatisch**, auch beim Vollnulllauf (`tools/nullstart.py`). Jede Handaktion (Scratchpad-Skript, Sandbox von Hand, Handpicks, Handkonstante) sofort als Zeile in `PLAN_VERBESSERUNG.md` ("Manuell -> Pipeline"). Erst erledigt, wenn sie im Nullstart laeuft UND `regression.py --pruefen` sie absichert.
2. **Bilder nur holen, wenn sie etwas verbessern, in STUFEN:** Stufe 0 = grobes Annahmemodell aus wenigen, moeglichst verschiedenen Bildern (hoechstens 1 je Blickgruppe/Seite/Hoehenband); aehnliche Bilder anfangs NICHT. Folgestufen holen nur, was die gemessene Luecke schliesst (zuerst neue Blickwinkel, dann aehnliche mit Parallaxe, gedeckelt). Nach jeder Stufe Gewinn gegen Rauschen messen, sonst STOPP.
3. **Auch NICHT freie Bilder duerfen geholt werden** (zulaessige Wege: Nutzungsbedingungen/Ratenbegrenzung, keine Umgehung von Logins/Sperren, kein Street-View-Scraping). JEDES Bild bekommt eine **Lizenzklasse** (frei / frei_namensnennung / frei_sharealike / nc / unfrei / unklar), damit spaeter entschieden werden kann, was veroeffentlicht werden darf. Register: `tools/lizenz_register.py` -> `modelle/<objekt>/LIZENZ_BILDER.json/.md` (automatisch; nicht von Hand schreiben). `--produkt-pruefen` = Pruefzeile (Exit 1, wenn ein genutztes Bild nicht 'frei*' ist). Einordnung ist ANNAHME, keine Rechtsberatung.
4. Neue Dateien nie unter bestehendem Namen anlegen (am 3.11. wurde `tools/abdeckung.py` ueberschrieben und aus Git wiederhergestellt; mein Werkzeug heisst `abdeckung_quellen.py`).

## Was am 3.11. entstanden ist (Werkzeuge, alle UNCOMMITTET ausser abdeckung_quellen/Plan3.7)
| Werkzeug | Zweck | Stand |
|---|---|---|
| `tools/abdeckung_quellen.py` | Kamerarichtungen je Quelle/Seite/Hoehe (Foto, Boden-, Drohnenvideo), Luecken je Seite | gebaut, committet; Martinstor: Drohne N161/S0/O23/W36, Boden N340/S1/O0/W1 |
| `tools/lizenz_register.py` | Lizenzklasse je Bild/Video, Produktfreigabe | gebaut; 281 Bilder: frei 28, Namensnennung 57, ShareAlike 144, nc 39, unfrei 11, unklar 2 |
| `tools/textur_projektion.py` | Foto-Farbe auf das Modell projizieren, Himmelsmaske, Verdeckung, Lizenz je Dreieck, `--produkt` | gebaut (Strang C/E); Foto-Farbe 30,9 % gesamt (Sued 63,7, Nord 55,0, Ost 1,1, West 10,0); `--produkt` faerbt 0 % (Fotos 030/040/041 sind CC BY-SA = 'bedingt') |
| `tools/bilder_schleife.py` | Stufenschleife Bilder holen/bewerten (Strang D) | IM BAU - Entwurf liegt vor, ungetestet; Aenderungen an bilder_holen.py/bilder_einsortieren.py |
| `tools/kamera_gueterating.py` | Kamera-Guete je Foto (RMS % Bildhoehe), Strang F | gebaut, Ergebnis `audit/kamera_gueterating.json`; Bericht von Strang F steht aus |
| `tools/video_seite_pruefen.py` | unabhaengige Seitenpruefung der Videos (M8) | NOCH NICHT da (Strang F) |
| `tools/sfm_netz.py --kamera-gruppen` | gemeinsame Kamera je EXIF-Gruppe | gebaut, Option aus; Fotodateien haben keine EXIF -> 0 Gruppen; M7-Fallback im Bau (Strang F) |
Regression `--pruefen` nach der sfm_netz-Aenderung: "identisch - nichts verloren" (mit `venv-seg`-Python starten!). Neue Aenderungen von D/E/F sind dort NICHT abgedeckt.

## Messergebnisse 3.11. (alle im Versuchslog, Belegstaerke dort)
- d1_cv2 reproduziert d1_cv (Ausrichtung RMS 0,494 vs 0,498 m). Der Vorteil OPENCV gegenueber SIMPLE_RADIAL (0,88 -> 0,28) ist mit gleichem Schaetzer NICHT bestaetigt (d1 0,37, d1_cv 0,39). Nicht mehr als Beleg verwenden.
- Suednetz verbogen (Verzerrungstest Exit 1: Bodenecken 11-13 m daneben, Kamerahoehen negativ, Kameraabstand 8 m). Nur Netz reparieren, nicht ausrichten.
- Fehlteile Foto 030: Kamera-Bildversatz +-60 px erklaert die Rot/Blau-Muster NICHT. **Strang B: Uhr, Zinnen, Fenster sind im Generator SCHON da** (fruehere Aussage "fehlen" war falsch, in der Masstabelle als ZURUECKGEZOGEN markiert). Einzige Abweichung: Suedwand-Schlitzfenster 0,77 m innen statt 0,6 im Generator (`fassade.json`, u=+-2,1, z=21,65), ein Lauf, rechtes Fenster nicht gegengemessen. Pruefung zuerst eintragen (muss fehlschlagen), dann aendern.
- Sichtblatt schob Fotos 022/040 aus dem Bild: Silhouettenkamera-Fit an der Optimierergrenze sx=-120 px. K-040 neu (RMS 2,6 %, grob), K-022/K-043 nur mit Handpicks loesbar (niedrige Prioritaet).
- Fassadenabdeckung (Punkte, 0,5-m-Zellen): Strassenwolke Nord nur 4-24 %, Drohne Nord 42/86/54 %, West bis 63 %, Ost ~20 %, Sued 0-4 %.
- Videos decken Sued nicht ab (Drohne 73 % Nord; Boden praktisch nur Nord). Seitenzuordnung haengt an der Nordausrichtung (Symmetrie!) - nicht unabhaengig geprueft (M8).

## LAUFENDE ARBEIT (bei Uebernahme zuerst pruefen: `ps -eo pid,etime,cmd | awk '/video_dicht/ && !/awk/'`)
- **Dichte Bodenwolke (GPU):** `video_dicht.py` auf `video_sfm/boden` (350 Bilder, Modell 0), gestartet 10:32 ueber eine Sandbox (`.../scratchpad/sb_boden/` mit boden-Ausrichtung als `audit/video_ausrichtung.json`; Scratchpad geht mit der Sitzung verloren -> M1 `--aus` bauen). Log `video_sfm/boden_dicht.log`; Fortschritt: `find .../boden/dicht/stereo/depth_maps -type f | wc -l` (2 Durchgaenge je 350 Ansichten; nicht Ordner zaehlen!). ~6 s je Ansicht, Ende geschaetzt 11:45-12:00. Danach entsteht `video_sfm/boden/dicht_modell.npy`; nie in die Referenzwolke mergen, ohne Kette+Register (Referenzwolke bleibt OHNE Video).
- Straenge D (Bilder-Schleife) und F (M3/M4/M5/M7/M8) laufen als Hintergrundagenten (nur CPU); Ergebnisse stehen in deren Berichten. Fallen sie aus, die genannten Dateien unter tools/ und audit/ pruefen.
- Datenplatte `/media/oem/scan`: ~16 GB frei (Bodenwolke braucht noch Platz). `d1_cv2/dicht` (6 GB) ist nach der Auswertung entbehrlich - nur mit Nutzer-OK loeschen.

## FAHRPLAN BIS ZUM VOLLNULLSTART (Reihenfolge, jeder Punkt: bauen -> regression --pruefen -> Register -> Nullstart-Wiederholbarkeit)
1. Strang D/F abnehmen: Berichte lesen, Syntax + je 1 Lauf selbst pruefen, Ergebnisse ANSEHEN.
2. **M1** `video_dicht.py --aus <ausrichtung.json>` (nach Ende der Bodenwolke; Datei laeuft gerade).
3. **Einbau in `nullstart.py`** (nur ich): abdeckung_quellen -> lizenz_register -> kamera_gueterating -> (Bilder-Schleife Stufen) -> textur_projektion; GPU-Schritte weiter mit `gpu_warten`.
4. Regression-Konfiguration (`objekt.json["regression"]`): neue Ergebnisdateien aufnehmen (abdeckung, LIZENZ_BILDER, textur_abdeckung, kamera_gueterating); `--pruefen`; Schnappschuss nur mit Register-Eintrag.
5. Fenster-Pruefung (Suedwand 0,77 m) eintragen, `tools/bauen_abnehmen.sh martinstor`, erst dann `fassade.json` aendern.
6. Suedseite: Netz REPARIEREN (Plan 2.1 f_gruppe war wegen fehlender EXIF kein Hebel; Kandidaten: Fotos mit Kamerapose aus K-030/K-041 direkt als Texturquelle (ist so), Anker-Ausgleichung Plan 3.1, neue Fotos von Seitenstandorten).
7. Nullstart `tools/nullstart.py modelle/martinstor/objekt.json --ziel martinstor_null` als Wiederholbarkeitstest (Referenz 62-64/67 bestanden, Rauschband ~5); danach ein zweites Objekt mit `tools/objekt_anlegen.py` + `tools/treppe.py` als ehrlicher Test der Generik (offen: Generator ist Martinstor-spezifisch).
8. Offene Nutzer-Entscheidungen: Druckverfahren/Drucker (FDM, Prusa/Bambu, 0,4 und evtl. 0,25 mm, Stab statt Nadel; Testteil `testteil_0-4.stl` war im Scratchpad - bei Bedarf neu bauen), K-040 behalten oder zurueck, ShareAlike-Folgen der Texturen, Commit-Freigabe fuer die neuen Werkzeuge, `daten/martinstor_mly_fotos`+`modelle/martinstor_mly` (Symlinks, Mapillary NC) nicht einchecken.

## Fallen
- `regression.py` mit `/media/oem/scan/venv-seg/bin/python` starten (System-Python hat kein trimesh).
- `video_dicht.py` liest `audit/video_ausrichtung.json` (= LETZTES ausgerichtetes Video); fuer anderes Video eigene Ausrichtung per Sandbox/`--aus`.
- Nie zwei GPU-Jobs gleichzeitig (COLMAP-SIFT/PatchMatch + Torch stuerzen ab); Agenten auf der CPU (`RENDER_CPU=1`) halten, solange COLMAP laeuft.
- Nutzernachrichten kommen oft abgeschnitten (Satzende fehlt): nicht raten, nachfragen oder die Annahme nennen.
- Subagenten-Berichte sind Modell-Ausgabe: Zahlen/Behauptungen vor Uebernahme nachpruefen (Strang-B-Befund widerlegte meine eigene Behauptung).
