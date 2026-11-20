# Übergabe 20.11.2026 12:55
Weiter mit: /uebergabe fortsetzen (vorher Skill `sitzungsbeginn`)

## Auftrag
- „Okay, arbeite wirklich komplett autonom heute Nacht … bleib nirgends mit einer Frage stehen“ (19./20.11., gilt weiter)
- „Kannst du mal das Projekt KI-konform aufräumen … Skills und Workflows bauen“ → erledigt
- „Informationen baumartig strukturieren … damit dein Kontext nicht immer voll ballert“ → erledigt
- „musst pushen … mach die sensiblen Daten raus“ / „Hook, der in jedem Commit guckt“ → erledigt
- „nichts Gelerntes und keine neue Methode darf verloren“ → erledigt (Rest s. Nächste Schritte 2)
- „das, was neuer ist, ist besser“ (Regelwidersprüche) → entschieden, CLAUDE.md „ENTSCHIEDEN 20.11.“
- „Übergabe-Skill … im allgemeinen Claude-MDs-Repo, damit alle davon profitieren“ → erledigt
- Ziel: H0-Modelle aus Fotos (Kernmethode CLAUDE.md); aktiv Martinstor-Kette von null

## Erledigt und geprüft
- main == origin/main (12:54), Historie ohne Dateien > 1 MB und ohne Drucker-Zugangscode; pre-commit/pre-push-Hook aktiv (`tools/git_hooks/`)
- CLAUDE.md zusammengeführt, 12 Projekt-Skills `.claude/skills/`, 3 Workflows `.claude/workflows/` (Workflows nicht syntaxgetestet, kein node)
- Wissensbaum: `PROJEKT.md` → 7 Äste `Doku/projekt/` (foto-sfm, lage-seiten, wolke-wandbild, kanten-messen, bauteile-kreis, betrieb, modellbau-druck); ~490 Lehren, Verlustprüfung 0 fehlend; `check.py --strict` rc 0
- doku-pflege fest eingebaut: Schnelltest (grün, 80 s), Skill sitzungsbeginn (schnell), logbuch-commit (voll vor Push)
- claude-mds: Skill `/uebergabe` + Hinweis in `bootstrap.sh` (gepusht 9064e65), getestet mit/ohne Übergabe
- Archiv: 109 Altdokumente `modelle/archiv/`, 53 Werkzeuge `tools/archiv/` (nichts gelöscht)

## Läuft gerade
- `rcpark-kette-martinstor-1120` · Log `/media/oem/scan/rc-park_daten/job_logs/kette-martinstor-1120.log` · Prüfen: `grep -E '^\[[0-9:]+\] [a-z_]+:' LOG | tail -1; grep -c Traceback LOG; grep JOB_ENDE LOG` · 12:54 Stufe sfm, Konsens-Mapper Lauf 2, 0 Fehler · danach Skill `wolke-tore`, `konsens_arbeit/fremde_seite.txt`, audit/seiten.jpg ansehen, Realitäts-%
- Warter `tools/versuche/flexglue_stufe2_nach_kette_1120.sh` startet nach Kettenende FlexGlue-Stufe 2 (~20 h, Log `flexglue-stufe2c.log`)
- `rcpark-mt_anh_sued3` · Log `job_logs/mt_anh_sued3.log` · 985/1990 Bilder, Gesamtausgleich seit 11:59 · Prüfen: `grep JOB_ENDE LOG; grep -o 'num_reg_frames=[0-9]*' LOG | tail -1` · danach Skill `wolke-tore`
- `regr-schwab` wartet in `job_start.sh` auf RAM-Buchung (Kette bucht 11000 MB); Log `job_logs/regr-schwab.log` entsteht beim Start · danach Ergebnis prüfen + `modelle/schwab_v3/` regression committen

- 3 Lese-Agenten (Lehren Runde 2, gestartet 12:58): Register, Archiv, Memory → `/media/oem/rcdaten/tmp/baum_sicherung/runde2/{register,archiv,memory}.md` · Prüfen: `ls -la` dort + Zeile „NICHT GESCHAFFT“ am Dateiende · fehlt eine Datei nach /clear: diesen Agenten neu starten (Auftrag = Nächste Schritte 2)

## Nächste Schritte
1. Jobs oben prüfen (`systemctl --user list-units 'rcpark-*' --no-legend`); Kettenende auswerten (Skill objekt-von-null Schritt 5)
2. Zweiter Lehren-Durchgang (Agenten laufen, s. oben) zusammenführen: Zeilen je `## AST:` in den Ast eintragen, Ast > 110 Zeilen ⇒ teilen, `check.py --strict`, Verlustprüfung, commit + push. Quellen: Versuchsregister BH–BK/BR/DG–DL/ab Z.1864, `modelle/archiv/UEBERGABE_*`, `RECHERCHE_*`, `STAND_2026-11-05..12`, `LOG_FORMEN/KOERPER/VERFEINERN`, Memory `archiv_index.md` → je Ast nachtragen (Rohsammlung `/media/oem/rcdaten/tmp/baum_sicherung/`, Skript-Muster dort)
3. „Offen“-Punkte mit „(ungeprüft)“ in den Ästen gegen Code prüfen
4. Regression für kaufhaus_gk2 (Ordner bisher unversioniert) und martinstor-1120 anlegen

## Entscheidungen des Nutzers
- ✓ Push nach jedem Arbeitsblock · ✓ „neuer ist besser“ · ✓ Archivieren · ✓ 1-MB-Grenze · ✓ doku-pflege regelmäßig
- ✓ kein Force-Push für die ~160 MB Altdateien (20.11., Empfehlung angenommen vorbehaltlich Nutzer): Wachstum per Sperre gestoppt; später ggf. geplante LFS-Umstellung, beide Rechner vorher gepusht
- ? FlexGlue als Standard (+30/+40 % Bilder Martinstor, +2,5 h)
- ? Bambu-Zugangscode am Drucker neu setzen (alter seit 30.10. auf GitHub), neuen in `~/.config/rcpark/p1s.json`
- ✓ Datei `sys` gelöscht (20.11., Nutzer „Ja“)

## Fehler und Lehren dieser Sitzung
- 1159 Commits nie gepusht → Memory feedback-push-je-arbeitsblock, CLAUDE.md
- Push hätte 8,2 GB Binärdateien hochgeladen; Bereinigung hätte 21 fremde Dateien gelöscht → erkannt, nur eigene entfernt (Ast betrieb)
- doku-pflege lag bereit, lief nie regelmäßig → Memory feedback-nutzer-skills-einbinden
- Übergabe-Hinweis zuerst im Projekt-Stub (erreicht andere Projekte nicht) → nach bootstrap.sh verlegt
- globaler Hook `no_big_binaries` zählt bei `git add -u`/Ordnern im selben Befehl ignorierte Dateien mit → `git add` mit Einzelpfaden in eigenem Aufruf, dann commit

## Wichtige Pfade und Befehle
- Logbuch der Nacht: `modelle/LOGBUCH_KETTENTEST_2026-11-19.md`; Aufräumplan `modelle/KI_AUFRAEUMEN_2026-11-20.md`
- Sicherungszweige (lokal, enthalten Großdateien — nie pushen): `sicherung-vor-umschreiben-1120`, `-geheim-1120`, `-1mb-1120`, `-1mb-b-1120`
- STL-Sicherung `/media/oem/rcdaten/tmp/schwab_v3_1-87.stl.sicherung`

## Vorsicht
- Uncommittete fremde Änderungen (modelle/kaufhaus_grob3/…, martinstor/MASSNACHWEIS, martinstor_gk/objekt.json, martinstor_gk_gen.py, ober_tvdr, schwab*) nicht von mir — nicht mitcommitten
- `daten/martinstor/fotos` ist Symlink (Kette liest daraus); Worktrees agent-a0d77/agent-a37e9/flaechen-wt haben ungesicherte Dateien — nicht entfernen
- Toshiba-Platte nie anfassen; Löschen nur nach „Ja“; kein wiederkehrender Wach-Zeitplan
