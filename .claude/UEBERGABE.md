# Übergabe 20.11.2026 13:07
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
- NACHTRAG 14:55: Erste Kette `kette-martinstor-1120` brach 13:27 ab (SfM-Zeitlimit 3 h im globalen Mapper, rc 124; Konsens 843/2107 Bilder, 774 fremde Seite). Neu: `rcpark-kette-martinstor-1120b` (ab sfm, RCPARK_STUFE_MAX_S=21600, Merkmale/Paare aus Cache) · Log `job_logs/kette-martinstor-1120b.log` · danach Skill `wolke-tore`, `konsens_arbeit/fremde_seite.txt`, audit/seiten.jpg, Realitäts-%
- FlexGlue-Stufe 2 und `mt_anh_sued3` (seit 11:59 im Gesamtausgleich hängend, 1 Kern) auf Nutzerwunsch GESTOPPT 14:48 (RAM für Kette). Nach Kettenende neu starten; Süd-Anhang mit mehr Kernen. Warter-Lehre: startete FlexGlue auch nach GESCHEITERTER Kette (rc prüfen!)
- yt-dlp 2026.08.19 veraltet (2 Videos fehlen); Update braucht root: `sudo yt-dlp -U`
- `regr-schwab` FERTIG: „identisch - nichts verloren“

- Lehren Runde 2: alle 3 Agenten FERTIG (13:07), nichts läuft mehr · Ergebnis `/media/oem/rcdaten/tmp/baum_sicherung/runde2/` register.md (244 Z.), memory.md (276), archiv.md (439, inkl. neuer Ast lizenzen-werkzeuge) = 1161 Zeilen, gruppiert `## AST: <ast>[ / GILT| / OFFEN]` · Lücken je Datei am Ende (NICHT GESCHAFFT); Abgleich gegen Baum nur per Stichwort ⇒ beim Zusammenführen Doppeltes verschmelzen

## Nächste Schritte
1. Jobs oben prüfen (`systemctl --user list-units 'rcpark-*' --no-legend`); Kettenende auswerten (Skill objekt-von-null Schritt 5)
2. SOFORT: Runde 2 zusammenführen — Skript nach Muster `/tmp/.../scratchpad/baum_bauen.py` (geht bei /clear verloren; neu schreiben): Zeilen je `## AST:` in den Ast, Teilthemen übernehmen, Doppeltes (gleicher Ansatz+Datum) verschmelzen; Äste > 110 Zeilen teilen (sicher: bauteile-kreis → bauteile-generator + kreis-abnahme; kanten-messen → kanten-linien + foto-tore-messen; lage-seiten, wolke-wandbild prüfen), neuer Ast lizenzen-werkzeuge; Zeilen in PROJEKT.md; Verlustprüfung (jede Quellzeile in genau einem Ast), `check.py --strict`, commit + push. Danach REZEPT: doppelte L-Nummern (L11–L13, L-KR17–29) auflösen
3. „Offen“-Punkte mit „(ungeprüft)“ in den Ästen gegen Code prüfen
4. Regression für kaufhaus_gk2 (Ordner bisher unversioniert) und martinstor-1120 anlegen

## Entscheidungen des Nutzers
- ✓ Push nach jedem Arbeitsblock · ✓ „neuer ist besser“ · ✓ Archivieren · ✓ 1-MB-Grenze · ✓ doku-pflege regelmäßig
- ✓ (vorläufig) kein Force-Push für die ~160 MB Altdateien (20.11., meine Empfehlung, Nutzer „können wir überlegen“): Wachstum per Sperre gestoppt; später ggf. geplante LFS-Umstellung, beide Rechner vorher gepusht
- ? FlexGlue als Standard (+30/+40 % Bilder Martinstor, +2,5 h)
- ? Bambu-Zugangscode am Drucker neu setzen (alter seit 30.10. auf GitHub), neuen in `~/.config/rcpark/p1s.json`
- ✓ Datei `sys` gelöscht (20.11., Nutzer „Ja“)

## Fehler und Lehren dieser Sitzung
- Nutzerfrage 20.11.: „ist das [20 h Rechnen] einmalig?“ → ja: FlexGlue-Stufe 2 und Süd-Anhang sind einmalige Messläufe; pro Modell nur die Kette (Dauer für Martinstor noch messen und melden)
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
