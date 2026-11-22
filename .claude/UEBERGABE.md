# Übergabe 22.11.2026 23:15
Weiter mit: „weiter“ (oder /uebergabe fortsetzen; vorher Skill `sitzungsbeginn`). Zuerst Kettenlauf `1122o` auswerten (siehe „Läuft gerade“).

## Auftrag
- „Keine Handangriffe, nur Automatik.“ → Tore nie per Eintrag in objekt.json bestehen lassen, Detektor erweitern (Memory feedback-keine-handeintraege-nur-automatik).
- „Ich will die Südseite“ (Seite Richtung Schlossbergring), „parallel“ (darf neben der Kette laufen, Jobs sollen sich drosseln statt abzustürzen).
- „Ja, bau alles ein.“ (8 Pipeline-Verbesserungen) · „Ich will es jetzt generalisiert gelöst“ (Eckmodell allgemein).
- „versuche die Brücke noch stabiler zu machen“ (ohne neue Fotos).
- Zuletzt: „Die Methode muss vollautomatisiert so robust sein, dass sie auch mit dünnen Brücken umgehen kann … vollautomatisch merkt, an Stellen, wo es schwach wird, dann mit Software nochmal mehr rausholt als Nachmatchen. Suche nach weiteren solchen geilen Methoden.“
- Ziel in einem Satz: Die Kette baut das Schwabentor von null inkl. Südseite, alle Lage-Tore (GPS, Grundriss, Wanddicke, Lot) grün, Bild + Fehlerliste + Realitäts-% an den Nutzer.

## Erledigt und geprüft (main fa33bf9ef, gepusht)
- Lage-Prüfstand d1ee43eb4 · Haufen-Automatik (Grundriss-Tor klärt Straßenhaufen selbst, Wandklinge ≥ 3 m = rot) 9b7c2cac1.
- Betrieb + Fotoauftrag 526d42e18 (verlustbilanz.py, foto_auftrag_skizze.py, pfade.temp_ordner + Temp-Wächter).
- Dach + Erker 04f32a646 (teil_fotoform findet `<nr>.jpg`, geneigte Wandebene im Ebenen-Sweep).
- Lot 02020bc75: Fluchtpunkt-Lot trägt die Ausrichtung, Kippung fest ±0,1°, Lot-Tor `tools/lot_wandneigung.py` (≤ 2 cm/m), Vorstufe `lage_frueh.py`.
- Recherche fa33bf9ef: `research_notes/duenne_bruecken_methoden_2026-11-22.md` (13 Methoden, Rangfolge, Lizenzen).
- Kette 1122o (Stand 23:10): Lage-Tore grün – Lot 1,4 cm/m, GPS +1,2° ×0,980, Grundriss 1,2 %. Modell noch nicht fertig.
- Südseite (Zweig a0747, NICHT auf main): Eck-Kopplung über gemeinsame 3D-Punkte → Südwand +1,1°, 0,38 m innerhalb LoD2; Innen-Durchgangswände 0,16/0,17 m. Selbsttest Martinstor mit Nachmatchen 0,2° / 2,4 cm. Rest ~0,4 m ungeklärt (Teil 1 evtl. in sich verformt).

## Läuft gerade
- Kette `rcpark-kette-schwabentor-null-1122o` (Start 22:39, `--ab sfm`), 23:10 in Stufe `fassaden_kette`. Log `/media/oem/scan/rc-park_daten/job_logs/kette-schwabentor-null-1122o.log`, Stufen: `grep -a "=== " /media/oem/scan/rc-park_daten/schwabentor-1122/gesamtkette.log | tail -3`. Danach: ERGEBNIS-Zeile, `modelle/schwabentor-1122/audit/seiten.jpg` + `neben_*.jpg` ANSEHEN, Fehlerliste + Realitäts-% + 3D-HTML `/media/oem/scan/rc-park_daten/schwabentor-1122/schwabentor-1122_3d.html` an Nutzer.
- Warter brcp7gqqh (Kettenende) und bptei9uy6 (Schnelltest der Merge-Probe nach Fassadenstufe → `/media/oem/rcdaten/tmp/schnelltest_merge_sued.log`): gehen bei /clear evtl. verloren, dann von Hand prüfen.
- Merge-Probe `/media/oem/scan/rc-park_tmp/merge_probe12`, Zweig `merge-probe-1122-abend` (08efe7975 = main + a0747: Südseiten-Kopplung, bruecke_nachmatchen, sim3_robust, fotos_sammeln-Herkunft, wand_dicke Normalen/Gültigkeit, Durchblick).
- Job `rcpark-bruecke2-b1` (Agent a724, Brücken-Selbsttest, Log `/media/oem/rcdaten/tmp/bruecke2/b1.log`) läuft neben der Kette.
- Agent a724bf0d78cfa2afc (Worktree): Lot-Zwang in der Kopplung, geführtes Nachmessen, gemeinsamer Ausgleich, Eskalationsleiter.
- Agent ae06ef85afac99e13 (Worktree): Selbsttest Stufe 2, Lotfeld je Kamera (Frage: ist Teil 1 in sich verformt?), Schwachstellen-Radar.
- Agenten-Stand nach /clear: `git log --oneline main..worktree-agent-<id> | head`.

## Nächste Schritte
1. Kette 1122o prüfen: `systemctl --user is-active rcpark-kette-schwabentor-null-1122o; grep -a "ERGEBNIS DES LAUFS\|ABBRUCH\|JOB_ENDE" /media/oem/scan/rc-park_daten/job_logs/kette-schwabentor-null-1122o.log | tail -3 | cut -c1-700` → auswerten (Bilder ansehen!).
2. Schnelltest Merge-Probe: `grep -a "SCHNELLTEST:" /media/oem/rcdaten/tmp/schnelltest_merge_sued.log | tail -1`; fehlt er: nach Kettenende `cd /media/oem/scan/rc-park_tmp/merge_probe12 && bash tools/schnelltest.sh`. Nur bei „0 Fehler“: in main `git fetch` und dann `git merge --ff-only merge-probe-1122-abend`, push.
3. Danach Nachtlauf von null ab Vorprüfung (wegen fotos_sammeln-Fix) per Skill `langer-job`, JOB_RAM_MB 11000, nur EIN Kettenlauf.
4. Agenten a724/ae06 auswerten → je Zweig Merge-Probe, Merge nur bei Schnelltest 0.
5. Lizenzbefunde aus der Recherche in `modelle/LIZENZ_WERKZEUGE.md` nachtragen.
6. Offen: unabhängiges Höhen-Tor aus Fotokanten (nur Vorschlag); Foto-Tor „nicht beurteilbar“ 15/15 (teils behoben); Dublettenprüfung für Videobilder zu grob; Zweig a879 (video_bruecke, Lage nicht belegt) nicht gemergt.
7. Aufräumen nur nach „Ja“: `/dev/shm/rcpark_netz_*` (1,5 GB), `/media/oem/rcdaten/tmp/nachmatch_insp2/k.db` (834 MB).

## Entscheidungen des Nutzers
- ✓ Keine Handeinträge, nur Automatik · ✓ Root aufräumen · ✓ Südseite parallel zur Kette · ✓ alle 8 Verbesserungen einbauen · ✓ Eckmodell generalisiert · ✓ Brücke ohne neue Fotos stabilisieren.
- ? Regelungs-Zweig a7cb464f361175467 (JOB_KLASSE, neben_bremse.py, gpu_grenze.py, RAM-Buchung je Stufe): Lasttests offen; Merge und Regeländerung nur mit Zustimmung.
- ? YouTube-Cookies nur nach ausdrücklichem „Cookies ja“.

## Fehler und Lehren dieser Sitzung
- Handeintrag `grundriss_haufen_geklaert` gesetzt → Nutzer verbot es, zurückgenommen, Detektor gebaut (Memory).
- Himmelsrichtungen falsch benannt (Rahmen +x Nord, +y West); −6,5° falsch der gewählten Lösung zugeordnet.
- Warter feuerte zu früh (alte Logzeilen) → Logs ab Zeilennummer lesen.
- Sim3 durch eine Kamera 2277 km entfernt verdorben (relative Schwelle) → feste 1-m-Schwelle, sim3_robust.
- Merge-Proben scheiterten am Temp-Wächter (Tests mit mkdtemp) → pfade.temp_ordner.
- Realitäts-% 1122n erst 25 % gemeldet, richtig ~15 %.
- Doppelgänger-Prüfer nutzte 5,86 GB VRAM trotz 2500-MiB-Buchung (an Regelungs-Agent gemeldet).
- Lehren stehen in `modelle/LOGBUCH_SCHWABENTOR_KETTE_2026-11-21.md` und `Doku/projekt/lage-seiten.md` (Versucht).

## Wichtige Pfade und Befehle
- Kettenordner `/media/oem/scan/rc-park_daten/schwabentor-1122/` (gesamtkette.log, pipe/), Objekt `modelle/schwabentor-1122/objekt.json` (unversioniert).
- Kopplung `tools/seiten_eck_koppeln.py`, Nachmatchen `tools/bruecke_nachmatchen.py`, Selbsttest `eck_selbsttest.py` (im Zweig a0747 / merge_probe12).
- Selbsttest-Daten `/media/oem/rcdaten/tmp/durchblick/`, `/media/oem/rcdaten/tmp/bruecke2/`.

## Vorsicht
- Root nur 8,2 GB frei (Mindest 15 GB!) → nichts Neues auf Root, Abgelöstes per `tools/auslagern.sh` nach rcdaten.
- Fremde uncommittete Dateien nicht committen (modelle/kaufhaus_grob3/*, martinstor_gk, *MASSNACHWEIS.md, schwabentor-1120/audit/*).
- Worktree `ram-je-stufe-1120` nicht anfassen; Worktrees nie mit --force entfernen.
- Kein zweiter Kettenlauf neben 1122o; Agenten rechnen nicht während der Kette (Ausnahme bruecke2-b1 läuft – beobachten).
- Nie pkill -f mit Muster aus der eigenen Befehlszeile; Toshiba-Platte nie anfassen.
