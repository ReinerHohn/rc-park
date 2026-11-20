# Übergabe 20.11.2026 12:55
Weiter mit: /uebergabe fortsetzen

## Auftrag
- „Okay, arbeite wirklich komplett autonom heute Nacht … bleib nirgends mit einer Frage stehen“ (19./20.11.)
- „Kannst du mal das Projekt KI-konform aufräumen … Skills und Workflows bauen … wie können wir das Projekt weiter verbessern?“ → erledigt
- „von dieser Liste … alles abarbeiten, was du selber abarbeiten kannst … Informationen baumartig strukturieren“ → erledigt
- „musst pushen … mach die sensiblen Daten raus“ / „Hook, der in jedem Commit guckt“ → erledigt
- „nichts Gelerntes und keine neue Methode darf verloren“ → erledigt (Wissensbaum Doku/projekt/, 7 Äste)
- Widersprüche: „das, was neuer ist, ist besser“ → entschieden (CLAUDE.md, ENTSCHIEDEN 20.11.)

## Erledigt und geprüft
- CLAUDE.md zusammengeführt (GPU-PC + anderer Rechner), 12 Projekt-Skills `.claude/skills/`, 3 Workflows `.claude/workflows/`
- Wissensbaum: `modelle/INDEX.md`, `tools/INDEX.md` (erzeugt `tools/baum_erzeugen.py`), `PROJEKT.md` + neuer Ast `Doku/projekt/foto-sfm.md`
- 109 Altdokumente → `modelle/archiv/`, 53 tote Werkzeuge → `tools/archiv/` (nichts gelöscht)
- `tools/py` (Umgebung nach Importen), `tools/pfade.py`, job_start-Warnung, `RCPARK_KURZ=1` für bauen_abnehmen
- Merge mit origin/main (anderer Rechner) + Push: main == origin/main (12:30); Historie ohne Dateien > 1 MB und ohne Drucker-Zugangscode
- Git-Sperre `tools/git_hooks/` (pre-commit + pre-push, 1 MB ohne LFS, Zugangsdaten), installiert; doku-pflege im Schnelltest (grün)
- Skill `/uebergabe` neu in ~/git/claude-mds (dieser Text ist der erste Einsatz)

## Läuft gerade
- `rcpark-kette-martinstor-1120` · Log `/media/oem/scan/rc-park_daten/job_logs/kette-martinstor-1120.log` · Prüfen: `grep -E '^\[[0-9:]+\] [a-z_]+:' LOG | tail -1; grep -c Traceback LOG` · seit 10:27 Stufe sfm · danach Skill `wolke-tore`, Konsens `fremde_seite.txt`, audit/seiten.jpg ansehen
- Warter `tools/versuche/flexglue_stufe2_nach_kette_1120.sh` startet nach JOB_ENDE die FlexGlue-Stufe 2 (~20 h, Log `flexglue-stufe2c.log`)
- Regression Schwabentor `regr-schwab` wartet (12:50) weiter auf RAM-Buchung (Kette bucht 11000 MB), startet danach selbst; Ergebnis prüfen + committen
- `rcpark-mt_anh_sued3` (seit 19.11. 17:02, inkrementeller Mapper Süd-Anhang, Log `mt_anh_sued3.log`): 12:50 = 985/1990 Bilder, Gesamtausgleich seit 11:59 — weiterlaufen lassen, Ergebnis mit Skill wolke-tore prüfen
- (Lese-Agenten fertig, Ergebnisse gesichert)

## Nächste Schritte
1. (erledigt 20.11.: Lehren in 6 Äste + Druck, Verlustprüfung 0 fehlend, gepusht)
2. Kettenende Martinstor auswerten (Skill objekt-von-null Schritt 5), Realitäts-%.
3. Regression für kaufhaus_gk2 (Ordner bisher unversioniert) und martinstor-1120 anlegen.

## Entscheidungen des Nutzers
- ✓ Push nach jedem Arbeitsblock; ✓ „neuer ist besser“ bei Regelwidersprüchen; ✓ Archivieren; ✓ 1-MB-Grenze
- ? Force-Push, um 23 alte Dateien > 1 MB (160 MB) aus der GitHub-Historie zu entfernen
- ? FlexGlue als Standard (+30/+40 % Bilder Martinstor, +2,5 h)
- ? Bambu-Zugangscode am Drucker neu setzen (alter steht seit 30.10. auf GitHub) und in ~/.config/rcpark/p1s.json eintragen

## Fehler und Lehren dieser Sitzung
- 1159 Commits nie gepusht (alte Regel „kein Push ohne Auftrag“) → Memory feedback-push-je-arbeitsblock, CLAUDE.md
- Push hätte 8,2 GB Binärdateien hochgeladen → gestoppt, Historie bereinigt, Sperre 1 MB
- Bereinigung hätte 21 Dateien des anderen Rechners gelöscht → erkannt, ohne sie wiederholt (fremde Dateien nie aus der Historie nehmen)
- 2-Uhr-Meldung „Türsteher trennt Seiten“ war falsch (Logbuch Kettentest); tools/py erkannte `import a as b, c` nicht → behoben

## Wichtige Pfade und Befehle
- Logbuch der Nacht: `modelle/LOGBUCH_KETTENTEST_2026-11-19.md` (UEBERGABE 09:00 am Ende); Aufräumplan `modelle/KI_AUFRAEUMEN_2026-11-20.md`
- Sicherungszweige der Historien-Umschreibung: `sicherung-vor-umschreiben-1120`, `sicherung-vor-geheim-1120`, `sicherung-vor-1mb-1120`, `sicherung-vor-1mb-b-1120` (lokal, enthalten die Großdateien — nie pushen)

## Vorsicht
- `daten/martinstor/fotos` ist ein Symlink (Kette liest daraus) — nie ersetzen
- Toshiba-Platte nie anfassen; Löschen nur nach „Ja“; fremde uncommittete Kaufhaus-Dateien (modelle/kaufhaus_grob3/…) nicht mitcommitten
