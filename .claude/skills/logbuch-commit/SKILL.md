---
name: logbuch-commit
description: Nach jedem Versuch oder jeder Arbeitseinheit (RC-Park) - Logbuchzeile, Sackgassen, Lehren, Uebergabe, Commit der eigenen Dateien.
---
1. Logbuch `modelle/LOGBUCH_<THEMA>_<datum>.md`: Uhrzeit, Was, Ergebnis mit Zahl, Beleg (Pfad/Bild), Folge. Fehler und Korrekturen zuerst, ehrlich.
2. Sackgasse mit benannter Ursache -> `modelle/NICHTS_GEBRACHT.md`; Lehre -> Register in `modelle/REZEPT_GEBAEUDE_AUS_FOTOS.md`; Versuch V* -> `modelle/ZIEL_PIPELINE_H0.md`.
3. Neue Dokumente/Werkzeuge: `python3 tools/baum_erzeugen.py`. Experiment-Skripte nach `tools/versuche/<name>_<MMTT>.*` kopieren (Pfade im Logbuch muessen existieren).
4. masstabelle geaendert: vorher `bash tools/bauen_abnehmen.sh <obj> --nur-pruefen`.
5. Commit nur eigene Dateien (`git add <pfade>`, nie `-A`), Text endet mit den Attribution-Zeilen der Sitzung. Kein Push.
6. Vor /clear oder Sitzungsende: Abschnitt "UEBERGABE <datum> <zeit>" ans Logbuch-Ende + Verweis in ZIEL_PIPELINE_H0.md.
