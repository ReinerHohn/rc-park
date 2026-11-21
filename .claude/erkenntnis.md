# erkenntnis - Projektbesonderheiten RC-Park (gehen dem allgemeinen Skill ~/.claude/skills/erkenntnis vor)
- Register: `modelle/ERKENNTNISSE.md` (nicht `.claude/ERKENNTNISSE.md`).
- Automatik = `tools/gesamtkette.py` (Stufen) und `tools/iphone_sfm.py` (SfM). "In der Automatik" heisst: dort aufgerufen UND ein Kettenlauf belegt es. Verwaiste Werkzeuge: `tools/INDEX.md` gegen `grep -l <werkzeug> tools/gesamtkette.py tools/iphone_sfm.py tools/pipeline_objekt.py`.
- Ansehen = Bild per SendUserFile (Kontaktbogen, Maskenprobe, Vergleichsbild), 3D als Artifact.
- Lehren: `modelle/REZEPT_GEBAEUDE_AUS_FOTOS.md` (Lehren-Register), Sackgassen `modelle/NICHTS_GEBRACHT.md`, Methoden `modelle/METHODE_*.md` / `modelle/GLOBALER_MAPPER_STABIL.md`; danach Skill `logbuch-commit`.
- Pruefungen als Tor mit rc (0 gut, 3 durchgefallen) + Test in `tools/schnelltest.sh`.
