# RC-Park – Arbeitsregeln (gelten für jede Sitzung, jedes Objekt)

## Modell-Abnahme (Pflicht; Rahmen: `modelle/METHODE_MASSTABELLE.md`)
Je Objekt `modelle/<objekt>/objekt.json` + `masstabelle.json` (Masse = Daten mit Quelle/Quelltyp/Merkmal, nicht Code).
1. Nach JEDER Generatoraenderung: `tools/bauen_abnehmen.sh <objekt>` (baut + `tools/pruefstand.py`). Martinstor: `tools/bauen_abnehmen.sh martinstor`.
   Nur bei "alle Pruefungen bestanden" weiter (Viewer, Commit, H0, Fertigung). Sollwerte nie lockern, um Gruen zu bekommen; nur mit neuer Quelle (+ `historie`).
2. **Sichtbeobachtung** (Nutzer oder eigene: "zu gedrungen", "stimmt nicht") = Testauftrag: SOFORT als `beobachtungen_offen` in die Masstabelle,
   DANN messen (Vollbild/Dokument/Laser passend zum Merkmal) und als Pruefung eintragen, die am aktuellen Modell FEHLSCHLAEGT, DANN Generator aendern.
3. Nach jedem Bau das Sichtblatt `modelle/<objekt>/audit/seiten.jpg` ANSEHEN (alle Seiten, nicht nur die fotografierte) und bei Bedarf
   `tools/foto_render_seite.py` / `tools/foto_profil_gpu.py`. Zahlen allein (IoU ohne Blick auf den ROI) gelten nicht.
3b. Jedes neue Generator-Element bekommt `beleg(seite, element, quelle)`; ohne Quelle faellt der Pruefstand durch. Annahmen heissen `ANNAHME: ...`.
4. Quellen-Blindheit (vom Pruefstand erzwungen, Exit 2): Laser DOM1 sieht keine Bauteile < ~3 m, keine Nadeln, keine Fassade, keine absolute Spitzenhoehe;
   LoD2 keine Aufbauten; Fotos keine absoluten Masse ohne Massstab; Dokumente keine Form.
5. Widersprueche zwischen Quellen (Foto vs Laser) NICHT mitteln - als offene Beobachtung stehen lassen, naechsten Schritt notieren.
6. Optimierer-/Mehrfachstart-Ergebnisse je Parameter bewerten; neue sichtbare Merkmale als Parameter + Tabellenzeile.
7. Symmetrische Objekte: Seiten unterscheidbar machen (Fotos nach Seite in `objekt.json`), sonst ist jede Kameraanpassung mehrdeutig.
8. Commit-Sperre: `tools/git_hooks/pre-commit` prueft ueberwachte Dateien. Aktivierung nur durch den Nutzer: `git config core.hooksPath tools/git_hooks`.

## Vor neuen Versuchen lesen
- `modelle/VERSUCHSREGISTER_MARTINSTOR.md` (was schon probiert wurde, Fehlschlaege, Ursachenanalyse I, Dach/Spitze J-J5, Seiten K)
- `modelle/LIZENZ_WERKZEUGE.md` (Verkauf geplant: NC-Werkzeuge nur zum Testen, eintragen)
- `modelle/LERNJOURNAL_MARTINSTOR.md`, `modelle/PIPELINE_H0.md`, `modelle/PROTOKOLL_VALIDATOR.md` (Fehler-Log F1-F10)

## Technik
- Python-Umgebungen: `/media/oem/scan/venv-seg/bin/python -I` (trimesh, torch, CUDA), `~/.venvs/rcpark` (manifold3d fuer den Generator).
- Nie zwei Optimierer/Generatorlaeufe parallel mit gleicher Zwischendatei; Generatordatei nicht aendern, solange Optimierer laufen.
- Kein Commit/Push ohne Auftrag; Commit-Texte enden mit den Attribution-Zeilen der Sitzung.
