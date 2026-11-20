---
name: objekt-von-null
description: Neues Gebaeude oder Kettentest von null durch die Gesamtkette (Fotos/Netz/Videos -> SfM -> Wolke -> Tore -> Bau -> Druckteile). Verwenden bei "neues Modell", "von null", "Kette laufen lassen".
---
1. Lesen: `modelle/ZIEL_PIPELINE_H0.md` (Luecken L*, Versuche V*). Platz pruefen; Datenordner bei < 20 GB auf scan nach `/media/oem/rcdaten/rc-park_daten_gross/<ziel>` + Symlink `/media/oem/scan/rc-park_daten/<ziel>`.
2. Trockenlauf: `./0-3d-modell.sh --trocken <Name> <Ort>`.
3. Start per Skill `langer-job` (RAM 11000): `/media/oem/scan/venv-seg/bin/python -u -I tools/gesamtkette.py <quelle> --ziel <ziel> --ab anlegen --dicht-stufe schnell [--fotos <ordner>] [--ohne-video] [--ohne-netz]`. Einzelstufen: `--ab/--bis <stufe>`. FlexGlue zuschaltbar: `RCPARK_FLEXGLUE=1` (+30 % Bilder Martinstor, ~+2,5 h).
4. Fortschritt: `grep -E '^\[[0-9:]+\] [a-z_]+:' LOG | tail -3`; Fehler: `grep -E 'Traceback|ABBRUCH' LOG`.
5. Ende: Skill `wolke-tore`, Konsens `konsens_arbeit/fremde_seite.txt`, `audit/seiten.jpg` + `neben_*.jpg` ansehen, Realitaets-%.
6. Versuch V* in ZIEL_PIPELINE_H0.md eintragen, Skill `logbuch-commit`.
