# RC-Park / Martinstor – Arbeitsregeln (gelten für jede Sitzung)

## Modell-Abnahme (Pflicht, entstanden aus wiederholtem Fehler "Tuermchen zu gedrungen / Mittelspitze falsch")
1. Nach JEDER Aenderung an `modelle/martinstor_v4_gen.py`: `tools/martinstor_bauen.sh` (baut + `tools/modell_pruefstand.py`).
   Nur bei "alle Pruefungen bestanden" weiter (Viewer, Commit, H0, Fertigung). Pruefwerte nie lockern, um Gruen zu bekommen; nur mit neuer Quelle.
2. **Nutzer-Sichtbeobachtung** ("zu gedrungen", "stimmt nicht", "sieht falsch aus") = Testauftrag: ZUERST eine Pruefung in `modell_pruefstand.py`
   (mit Quelle: Foto-Messung am Vollbild oder Laser), die am aktuellen Modell FEHLSCHLAEGT, DANN den Generator aendern.
3. Nach Aenderung Foto-gegen-Render-Vergleich zeigen (`tools/foto_silhouette_gpu.py`, Bilder in `modelle/foto_silhouette/`), nicht nur Zahlen.
4. Laser-Hypsometrie (DOM1 1 m) ist **blind** fuer Schlankheit und Strukturen < ~3 m (Kegel, Nadel); gruene Laserwerte beweisen kein richtiges Aussehen.
5. Optimierer-/Mehrfachstart-Ergebnisse **je Parameter** bewerten, nicht nur als Ganzes; neue sichtbare Merkmale als Parameter ergaenzen.
6. Pruefwerte pflegen: jede behobene Abweichung bekommt dauerhaft eine Pruefung (Regressionsschutz).

## Vor neuen Versuchen lesen
- `modelle/VERSUCHSREGISTER_MARTINSTOR.md` (was schon probiert wurde, Fehlschlaege, Ursachenanalyse Abschnitt I)
- `modelle/LIZENZ_WERKZEUGE.md` (Verkauf geplant: NC-Werkzeuge nur zum Testen, eintragen)
- `modelle/LERNJOURNAL_MARTINSTOR.md`, `modelle/PIPELINE_H0.md`

## Technik
- Python-Umgebungen: `/media/oem/scan/venv-seg/bin/python -I` (trimesh, torch, CUDA), `~/.venvs/rcpark` (manifold3d fuer den Generator).
- Nie zwei Optimierer/Generatorlaeufe parallel mit gleicher Zwischendatei; Generatordatei nicht aendern, solange Optimierer laufen.
- Kein Commit/Push ohne Auftrag; Commit-Texte enden mit den Attribution-Zeilen der Sitzung.
