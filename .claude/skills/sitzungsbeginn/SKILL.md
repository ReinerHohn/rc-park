---
name: sitzungsbeginn
description: Start jeder RC-Park-Sitzung oder nach /clear - Kernel-Modul, laufende Jobs, Plattenplatz, Uebergabe lesen. Verwenden bei Sitzungsbeginn, "wo stehen wir", nach Kontextzusammenfassung.
---
1. `bash tools/hpwmi_pruefen.sh` - bei "ACHTUNG KERNEL-MODUL" dem Nutzer sofort sagen.
2. Laufende Jobs: `systemctl --user list-units 'rcpark-*' --no-legend | cut -c1-80`; je Job `tail -3 /media/oem/scan/rc-park_daten/job_logs/<name>.log | cut -c1-160`.
3. Platz: `df -h /media/oem/scan /media/oem/rcdaten / | cut -c1-80` (scan unter 20 GB = neue Grossdaten nach /media/oem/rcdaten + Symlink).
4. Doku: `python3 ~/.claude/skills/doku-pflege/check.py` (fehlt claude-mds: `bash ~/git/claude-mds/bootstrap.sh`); ✗ = vor der Arbeit Skill `doku-pflege` schnell. Wissensablage: `python3 -I tools/wissen_ablage_pruefen.py --still` - "nicht eingecheckt" (z. B. modelle/archiv/*.md) dem Nutzer melden (einchecken oder verwerfen? Nutzer entscheidet). Git: `git fetch` + `git status -sb` (hinterher = erst zusammenfuehren).
5. Lesen: `modelle/ZIEL_PIPELINE_H0.md` nur UEBERGABE/NACHTRAG am Ende, dann das dort genannte Logbuch nur ab "UEBERGABE".
6. Dem Nutzer in 5-8 Zeilen: was laeuft, was offen ist, was ich als Naechstes tue. Dann autonom weiter.
