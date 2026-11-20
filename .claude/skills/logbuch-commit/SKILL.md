---
name: logbuch-commit
description: Nach jedem Versuch oder jeder Arbeitseinheit (RC-Park) - Logbuchzeile, Sackgassen, Lehren, Uebergabe, Commit der eigenen Dateien.
---
1. Logbuch `modelle/LOGBUCH_<THEMA>_<datum>.md`: Uhrzeit, Was, Ergebnis mit Zahl, Beleg (Pfad/Bild), Folge. Fehler und Korrekturen zuerst, ehrlich.
2. Sackgasse mit benannter Ursache -> `modelle/NICHTS_GEBRACHT.md`; Lehre -> Register in `modelle/REZEPT_GEBAEUDE_AUS_FOTOS.md`; Versuch V* -> `modelle/ZIEL_PIPELINE_H0.md`.
3. Neue Dokumente/Werkzeuge: `python3 tools/baum_erzeugen.py`. Experiment-Skripte nach `tools/versuche/<name>_<MMTT>.*` kopieren (Pfade im Logbuch muessen existieren).
4. masstabelle geaendert: vorher `bash tools/bauen_abnehmen.sh <obj> --nur-pruefen`.
5. Doku-Pflege (Skill `doku-pflege`, Modus schnell; bei neuen Versuchen/Lehren Modus voll): neue Versuche als Zeile in den passenden Ast `Doku/projekt/<ast>.md` (Gilt/Versucht/Offen), dann `python3 ~/.claude/skills/doku-pflege/check.py --strict` = Exit 0.
6. Commit nur eigene Dateien (`git add <pfade>`, nie `-A`), Text endet mit den Attribution-Zeilen der Sitzung. Danach `git fetch` + zusammenfuehren + `git push` (pre-push-Hook prueft Zugangsdaten/> 1 MB).
7. Vor /clear oder Sitzungsende: Abschnitt "UEBERGABE <datum> <zeit>" ans Logbuch-Ende + Verweis in ZIEL_PIPELINE_H0.md.
