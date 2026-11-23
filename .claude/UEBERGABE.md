# Übergabe 23.11.2026 ~01:30
Weiter mit: „weiter“ (vorher Skill `sitzungsbeginn`). Zuerst Kettenlauf `1122p` auswerten.

## Auftrag (Nutzerworte, unverändert seit 22.11.)
- „Keine Handangriffe, nur Automatik.“ · „Ich will die Südseite“ (Richtung Schlossbergring = Feldseite f01, im Objekt „Sued“) · „parallel“.
- „Die Methode muss vollautomatisiert so robust sein, dass sie auch mit dünnen Brücken umgehen kann … vollautomatisch merkt, wo es schwach wird … Suche nach weiteren solchen geilen Methoden.“
- Ziel: Kette baut Schwabentor von null inkl. Südseite, alle Lage-Tore grün, Bild + Fehlerliste + Realitäts-% an Nutzer.

## Erledigt (main 8a049c988, gepusht)
- Kette 1122o ausgewertet: ~22 % (Nord ~55, West ~30, Süd/Ost < 10), Fehlerliste im Logbuch 23.11. 00:30. 3D https://claude.ai/artifact/ScV8KGvyjJrxxHCAzCM6pi (V2).
- In main gemergt (je Schnelltest 0): Südseiten-Kopplung a0747, Radar `verbund_schwachstellen.py` + Lotfeld `teil_verformung.py` (ae06), Nachhol-Fix (ac34: GPU-OOM bei SIFT abfangen, keine Sperre bei Speichermangel), Dach-Fix (a028: Sichtschatten/Gitterrand, Gegenprobe 28/101 -> 65/89), Testfixes test_kette_tempo/test_dach_sichtschatten.
- Lizenzbefunde Brücken-Recherche in LIZENZ_WERKZEUGE.md.

## Läuft gerade
- Kette `rcpark-kette-schwabentor-null-1122p` (Start 01:07, `--ab vorpruefen`, JOB_RAM_MB 11000). Log `/media/oem/scan/rc-park_daten/job_logs/kette-schwabentor-null-1122p.log`. Warter bm4swiekt (geht bei /clear verloren -> von Hand: `grep -a "ERGEBNIS DES LAUFS\|JOB_ENDE" <log> | tail -3`).
- Merge-Probe `/media/oem/scan/rc-park_tmp/merge_probe13` (Zweig merge-probe-1123-fenster = main + a243 Fenster/Tür/loch_gewaende + a724 Brücke/Leiter/ausgleich_epipolar). Schnelltest mit a243 = 0; nach a724 nur Einzeltests grün -> NACH Kettenende voller Schnelltest, bei 0 in main mergen.
- Agent a4effedf10a2c8bdc: gemeinsamer BA über beide Teile (Eigenverformung). Agent acc3e1a2c02b80d5e: Kegeldach Treppentürmchen + Laterne. Beide nur Code bis Kettenende.

## Nächste Schritte
1. 1122p auswerten (seiten.jpg, neben_*.jpg, neben_details.jpg ANSEHEN; registrierte Fotos von 766? f01 gefüllt?), Fehlerliste + % + 3D-Artifact (gleiche URL), Logbuch.
2. Probe13 voller Schnelltest -> main, push. Danach 1122-Messung von a724: `bash /media/oem/rcdaten/tmp/bruecke2/lauf_b4.sh` nur letzter Befehl (s1122), dann `tools/versuche/bruecke2_suedwand_1122.py`.
3. Nächster Kettenlauf mit Leiter (RCPARK_ECK_LEITER=1?) – vorher prüfen, ob Schalter Standard ist.
4. Offen: Massstab ~1,027 zu gross (Dach Traufe/First), Tür f04 0,3 m versetzt (Ortho auf Zylinder), lage_frueh Lageproben rc 3.

## Entscheidungen / Fragen an Nutzer
- ? Löschen/Auslagern (Root nur 9,9 GB, Ziel 15): /dev/shm/rcpark_netz_* 1,5 GB, nachmatch_insp2/k.db 834 MB, /media/oem/rcdaten/tmp/nachholen_agent 1,7 GB, bruecke2/k1122 11 GB (rcdaten), Worktree ac64 (1 unversionierte Datei). Nur nach „Ja“.
- ? Regelungs-Zweig a7cb464f361175467 nur mit Zustimmung. ? YouTube-Cookies nur nach „Cookies ja“.
- Seitennamen bleiben (Agent ac34 vermutete Fehlbenennung; „Süd“ = Feldseite passt zum Nutzer).

## Lehren dieser Sitzung
- Tests, die /proc/meminfo lesen, kippen unter Kettenlast -> vorspielen (builtins.open, nicht Modul-Attribut wegen importe_pruefen).
- Agenten-Jobs buchen RAM (b4 5 GB) und blockieren den Kettenstart -> Agenten vor Kettenstart anhalten lassen.
- Worktrees je ~620 MB auf Root -> gemergte sauber entfernen (unlock + remove, nie --force).

## Vorsicht
- Fremde uncommittete Dateien nicht committen (kaufhaus_grob3, martinstor_gk, *MASSNACHWEIS.md, schwabentor-1120/audit, ...). Worktree ram-je-stufe-1120 nicht anfassen. Kein zweiter Kettenlauf. Toshiba nie anfassen.
