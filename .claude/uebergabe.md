# uebergabe - rc-park-Besonderheiten (Skill /uebergabe)
- Zusaetzlich zu `.claude/UEBERGABE.md`: im aktiven Logbuch (siehe `modelle/ZIEL_PIPELINE_H0.md`, NACHTRAG am Ende) einen Abschnitt "UEBERGABE <datum> <zeit>" mit Verweis auf `.claude/UEBERGABE.md`.
- Laufende Jobs: `systemctl --user list-units 'rcpark-*' --no-legend` (gpuwache/platz_waechter/editordraht sind Dauerdienste, nicht melden); Logs `/media/oem/scan/rc-park_daten/job_logs/<name>.log`, Ende = Zeile `JOB_ENDE rc=`.
- Lehren: Wissensbaum `Doku/projekt/<ast>.md` (Gilt/Versucht/Offen) + Sackgassen `modelle/NICHTS_GEBRACHT.md`; Memory nur fuer Nutzerregeln.
- Vor dem Push: `bash tools/schnelltest.sh` (enthaelt doku-pflege --strict); Hooks pruefen Zugangsdaten und > 1 MB.
- Anrede "mein grosser Meister", Deutsch, keine breiten Tabellen.
