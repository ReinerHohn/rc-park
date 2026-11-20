---
name: tools-pruefen
description: Pflichtpruefung nach jeder Aenderung unter tools/ (RC-Park) - Schnelltest, Regression, GPU-Nutzung, Commit.
---
1. `python3 -m py_compile <geaenderte .py>`.
2. `bash tools/schnelltest.sh 2>&1 | tail -3` - muss "0 Fehler" sagen. Rot = erst klaeren; Erwartungen nur mit Begruendung aendern.
3. `timeout 400 ~/.venvs/rcpark/bin/python tools/regression.py modelle/martinstor/objekt.json --pruefen 2>&1 | tail -1` - muss "identisch" sein (`--schnappschuss` nur bei gewollter Aenderung, im Logbuch begruenden).
4. Neues Werkzeug: kurzer Test `tools/test_<name>.py` (synthetisch, < 5 s) und in `tools/schnelltest.sh` eintragen; Docstring mit Aufruf, Zweck, rc-Bedeutung.
5. Rechenwerkzeug: laeuft es auf der GPU? (nvidia-smi waehrend Lauf; neue Werkzeuge `tools/gpu_knn.py`, ALIKED+LightGlue).
6. Skill `logbuch-commit`.
