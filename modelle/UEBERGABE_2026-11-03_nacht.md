# Uebergabe 2026-11-03 (Stand ~10:55, vor Kontext-Leerung) - alle Erkenntnisse

Ergaenzt `UEBERGABE_2026-11-03.md` (morgens) und `UEBERGABE_2026-11-03_abend.md` (Fahrplan, Regeln, Werkzeugtabelle). Zuerst `CLAUDE.md` lesen.

## Nutzerprioritaet JETZT
"erstmal brauchen wir jetzt ein perfektes 3D-Modell" - Modellverbesserung vor Teilen/Druckvorbereitung (`tools/modell_teilen.py` ist ungetestet, pausiert).
Harte Regeln: alles vollautomatisch (jede Handarbeit -> `PLAN_VERBESSERUNG.md` "Manuell -> Pipeline" M1-M12); Bilder nur in Stufen holen und nur wenn sie helfen; auch nicht freie Bilder erlaubt, aber jedes mit Lizenzklasse; Flickr weglassen; Nutzernachrichten oft abgeschnitten -> nicht raten.

## Modell-Aenderung heute (UNCOMMITTET)
- Suedwand-Lueftungsfenster: gemessen 0,75 m (Foto 041, M-041-006, ein Lauf) statt 0,60 im Generator.
  Pruefung `fenster_S_links_breite` (Soll 0,68-0,88) in `masstabelle.json` eingetragen, schlug vorher mit 0,60 fehl; danach `fassade.json` (2 Zeilen, breite 0.6 -> 0.77, u=+-2,1, z=21,65 Unterkante) geaendert.
  Neu gebaut: `SCALE=87 MINMM=0.8 ~/.venvs/rcpark/bin/python modelle/martinstor_v4_gen.py`, `tools/pruefstand.py` -> alle Pruefungen bestanden.
  STL `modelle/stl/martinstor_v4_1-87.stl`: 28.628 Dreiecke, 6317,3 cm3, 137,4 x 144,1 x 750,6 mm, wasserdicht, 1 Koerper. Aenderung in H0 ca. 2 mm. Rechtes Fenster nicht gegengemessen.
  `fassade.json` NIE mit json.dump neu schreiben (formatiert alles um) - nur Textersetzung.
- NOCH OFFEN dazu: `tools/bauen_abnehmen.sh martinstor` (Sichtblatt `audit/seiten.jpg` ANSEHEN; braucht CUDA -> erst nach Ende der dichten Bodenwolke), `regression.py --pruefen` (mit `/media/oem/scan/venv-seg/bin/python`), Versuchslog-Eintrag (`tools/versuch_log.py`), Register-Eintrag, `modelle/export/martinstor_H0_1-87_ganz.stl` (+ Kopie auf Datenplatte) neu ziehen (ist VOR der Fensteraenderung entstanden).
- Zurueckgezogen: "Uhr/Zinnen/Fensterreihe fehlen" war FALSCH (existieren in `elemente.json`/`fassade.json`; Beobachtung in der Masstabelle als ZURUECKGEZOGEN).

## Ehrlicher Stand "perfekt"
Mit den vorhandenen Daten nicht erreichbar: Ost/West aus Symmetrie angenommen, Nadelspitze unsicher (60-67 m, Laser blind), Helmbreite Strasse 4,84 vs Drohne 5,93 m ungeklaert (laut Morgen-Uebergabe eher Mass-Unterschied), Fotokameras K-031/K-030/K-041 grob (RMS 5,1/2/2 %) -> absolute Hoehen aus Einzelfotos unzuverlaessig (Uhrmitte 27,45/26,6/25,69 m widerspricht sich, NICHT mitteln). Groesster Hebel: Fotos von erhoehten Standorten und von Sued/Ost/West.

## Messbefunde
- Abdeckung Fassade (0,5-m-Zellen): Strasse Nord 4-24 %, Drohne Nord 42/86/54 %, West bis 63 %, Ost ~20 %, Sued 0-4 %. Videos decken Sued nicht ab (Drohne N161/S0/O23/W36 Kameras, Boden N340/S1/O0/W1). Seitenzuordnung der Videos haengt an der Nordausrichtung (Symmetrie), nicht unabhaengig geprueft (M8, Werkzeug `video_seite_pruefen.py` von Strang F).
- Suednetz verbogen (Verzerrungstest Exit 1: Ecken 11-13 m daneben, Kamerahoehen negativ, Kameraabstand 8 m) -> Netz reparieren, nicht ausrichten.
- d1_cv2 reproduziert d1_cv (RMS 0,494 vs 0,498 m). Vorteil OPENCV (0,88 -> 0,28) mit gleichem Schaetzer NICHT bestaetigt (d1 0,37, d1_cv 0,39) - nicht als Beleg verwenden.
- Fehlteile Foto 030: Kamera-Bildversatz +-60 px erklaert Rot/Blau-Muster nicht.
- Silhouettenkamera 022/040 an Optimierergrenze sx=-120; K-040 neu (RMS 2,6 %, grob); K-022/K-043 nur mit Handpicks (leere Dateien, nicht committen).
- Textur: Foto-Farbe 30,9 % (Sued 63,7, Nord 55,0, Ost 1,1, West 10,0); `--produkt` faerbt 0 % (Fotos 030/040/041 sind CC BY-SA = 'bedingt').
- Lizenzregister: 281 Bilder: frei 28, Namensnennung 57, ShareAlike 144, nc 39, unfrei 11, unklar 2. Einordnung ist ANNAHME, keine Rechtsberatung; ShareAlike-Wirkung auf Texturen UNVERIFIZIERT.
- Fotodateien haben keine EXIF -> `sfm_netz --kamera-gruppen` findet 0 Gruppen (Fallback ueber Manifest/Dateiname von Strang F).

## Hardware / Umgebung
RTX 4060 Laptop, 28 Kerne, nur 15,7 GB RAM (limitiert), Root-Platte ~96 %, Datenplatte `/media/oem/scan` 14 GB frei (86 %). `energy-web.service` vom Nutzer deaktiviert (fraß CPU). Offen: Luefterregler-Duplikat `luefter_adaptiv.service`. Nur EIN GPU-Job; Agenten mit `RENDER_CPU=1`.

## Laufende Jobs (zuerst pruefen: `ps -eo pid,etime,cmd | awk '/video_dicht|bilder_schleife/ && !/awk/'`)
- Dichte Bodenwolke: `video_dicht.py` ueber Sandbox im alten Scratchpad (`.../scratchpad/sb_boden/`, geht mit der Sitzung verloren), gestartet 10:32; um 10:55 225 von 700 Tiefenkarten (2 Durchgaenge x 350, `find .../video_sfm/boden/dicht/stereo/depth_maps -type f | wc -l`), Ende ca. 12:00-12:30. Ergebnis `video_sfm/boden/dicht_modell.npy`; NIE in die Referenzwolke `sfm/dicht_nord_entzerrt.npy` mergen (bleibt ohne Video). Danach Sichtblatt/Diagnosen/GPU-Jobs frei.
- Strang D (Hintergrundagent a697ae3a43ad68f42): `tools/bilder_schleife.py` Testlauf (`--stufen 2 --max-neu 6 --max-kandidaten 12 --cpu`, Log `/media/oem/scan/rc-park_null/bilder_schleife_test/lauf2.log`). Bericht abwarten, Code + einen Lauf selbst pruefen. Aenderungen an `bilder_holen.py`, `bilder_einsortieren.py`.
- Strang F: `kamera_gueterating.py`, `video_seite_pruefen.py`, Aenderungen in `fehlteile_finden.py`, `seiten_audit.py`, `foto_dach_gemeinsam.py`, `sfm_netz.py` (nicht von der Regression abgedeckt).

## Git-Stand
Committet (nicht gepusht): `84db5b8`, `ee3db97`. UNCOMMITTET: alle oben genannten neuen/geaenderten Werkzeuge, `masstabelle.json`, `fassade.json`, STL, `PLAN_VERBESSERUNG.md`, `LIZENZ_BILDER.*`, audit-Dateien, Uebergabe-Dateien. Nicht einchecken: Symlinks `daten/martinstor_mly_fotos`, `modelle/martinstor_mly` (Mapillary NC), `messprotokoll/lupe_*`, K-022/K-043. Commit nur auf Nutzerauftrag; Texte enden mit den Attribution-Zeilen der Sitzung.

## Naechste Schritte (Reihenfolge)
1. Agent-Bericht Strang D abwarten und pruefen; Bodenwolke abwarten.
2. Fenster abschliessen: `tools/bauen_abnehmen.sh martinstor`, `audit/seiten.jpg` ansehen, `regression.py --pruefen`, Versuchslog + Register, Export-STL erneuern.
3. M1 (`video_dicht.py --aus`) bauen, dann M2-M12 und Strang D/E/F in `nullstart.py` + Regression-Konfiguration einbauen (nur ich), Schnappschuss nur mit Register.
4. Naechste belegte Abweichung am Modell: Pruefung zuerst fehlschlagen lassen, dann Generator (z. B. Nord-Fenster mit besserer Kamera, Helmbreite, Ost/West-Annahmen, Nadelhoehe).
5. Suednetz reparieren; Nullstart-Wiederholbarkeit (`tools/nullstart.py ... --ziel martinstor_null`), zweites Objekt als Generik-Test.
6. Danach erst Druckvorbereitung (`modell_teilen.py` testen; Drucker FDM Prusa/Bambu, 0,4 / evtl. 0,25 mm, Nadel als Metallstab).

## Offene Nutzerentscheidungen
K-040 behalten oder zurueck; ShareAlike-Folgen; Druckerdaten (Bauhoehe ~220-250 mm -> ca. 4 Segmente); Commit-Freigabe; `d1_cv2/dicht` (6 GB) loeschbar nur mit OK; Luefterdienst-Duplikat.

## Fallen
`regression.py` nur mit venv-seg-Python; `pkill -f` trifft eigene Shell; Foreground-sleep gesperrt; neue Dateien nie unter bestehendem Namen (`abdeckung.py` ist der Aufnahme-Assistent, meins heisst `abdeckung_quellen.py`); Subagenten-Berichte nachpruefen; Quellen nur mit identischem Schaetzer vergleichen; `audit/video_ausrichtung.json` gehoert zum LETZTEN ausgerichteten Video.
