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
3c. Fotomasse nur ueber `tools/foto_mass.py` (Messprotokoll M-<foto>-<nr>), Tabellenzeile mit `protokoll` und `massstab`; Massstab aus dem Modell = zirkulaer.
    `modelle/<objekt>/MASSNACHWEIS.md` ist der automatische Nachweis - nicht von Hand schreiben. Neues Objekt: `tools/objekt_anlegen.py`.
3e. Nach jedem Bau mit kalibrierter Kamera `tools/fehlteile_finden.py <objekt> <foto>` laufen lassen und die Treffer ansehen (fehlende/erfundene Teile),
    bevor der Nutzer sie findet. Nutzer-Sichtfunde zuerst als automatischen Test nachbauen, dann einbauen.
3f. **Kontur-Diff Modell gegen Foto**: `tools/foto_diff.py <objekt> <foto>` (rot = Modellkante ohne Fotokante: falsche/erfundene Form, gelb = Fotokante fehlt im Modell). Nach jedem Bau fuer die kalibrierten Fotos laufen lassen und `audit/foto_diff_<foto>.jpg` ansehen; Treffer ausserhalb der Ankerzone sind unsicher. (Register CC; Schwellen noch nicht als Pruefstand-Sollwert.)
3d. Echte Meter aus Fotos nur ueber amtliche Anker (`anker3d.json` aus LoD2/DOM1/DGM1): `foto_kalibrieren.py` -> **`foto_pick_pruefen.py` ansehen** ->
    `foto_bundle.py` -> `foto_mass.py --kamera`. Fotos ohne Bodenanker nur mit EXIF-Brennweite oder `f_gruppe`. Georeferenz jeder Nebendatei pruefen.
4. Quellen-Blindheit (vom Pruefstand erzwungen, Exit 2): Laser DOM1 sieht keine Bauteile < ~3 m, keine Nadeln, keine Fassade, keine absolute Spitzenhoehe, keinen Fussabdruck steiler Helmflaechen (> ~75 Grad: Zellzahl/Schnitt Faktor 2 zu klein, Register AR);
   LoD2 keine Aufbauten; Fotos keine absoluten Masse ohne Massstab; Dokumente keine Form.
5. Widersprueche zwischen Quellen (Foto vs Laser) NICHT mitteln - als offene Beobachtung stehen lassen, naechsten Schritt notieren.
6. Optimierer-/Mehrfachstart-Ergebnisse je Parameter bewerten; neue sichtbare Merkmale als Parameter + Tabellenzeile.
7. Symmetrische Objekte: Seiten unterscheidbar machen (Fotos nach Seite in `objekt.json`), sonst ist jede Kameraanpassung mehrdeutig.
8b. Werkzeug-/Bibliotheksaenderung (tools/*.py, bauteile.py, pruefstand.py): danach `tools/regression.py modelle/<objekt>/objekt.json --pruefen` (Kette + 10 Ergebnisdateien gegen Schnappschuss; Register AW). Schnappschuss (`--schnappschuss`) nur erneuern, wenn das Ergebnis sich AENDERN soll, mit Register-Eintrag.
9. **Zaehl-/Strukturmerkmale (Anzahl Oeffnungen/Fenster/Zinnen je Flaeche) NUR am Foto zaehlen** (`tools/foto_zaehlung.py` -> messprotokoll/Z-*.json mit markiertem Bild), nie aus Punktwolke/Laser/LoD2 und nie aus Dateien, die der Generator selbst liest (Selbstbezug).
   Merkmal-Etikett ehrlich setzen (Zaehlart -> `anzahl`/`fassade`); der Pruefstand lehnt Umgehung und Selbstbezug ab (Exit 2), `tools/test_regeln_cb.py` beweist das bei jedem Bau. Zahl aus Wolke/Median = nie Sollwert (Register CB).
9b. **Vor jedem Druck/Zeigen eines Bauteils**: Teil neben das Referenzfoto legen (Detailrender des Teils ansehen), Anzahl/Anordnung der Elemente pro Flaeche mit dem Foto vergleichen - nicht nur Slicer-Bericht und Pruefstand-Zahlen.
8. Commit-Sperre: `tools/git_hooks/pre-commit` prueft ueberwachte Dateien. Aktivierung nur durch den Nutzer: `git config core.hooksPath tools/git_hooks`.

## Vor neuen Versuchen lesen
- `modelle/VERSUCHSREGISTER_MARTINSTOR.md` (was schon probiert wurde, Fehlschlaege, Ursachenanalyse I, Dach/Spitze J-J5, Seiten K)
- `modelle/LIZENZ_WERKZEUGE.md` (Verkauf geplant: NC-Werkzeuge nur zum Testen, eintragen)
- `modelle/LERNJOURNAL_MARTINSTOR.md`, `modelle/PIPELINE_H0.md`, `modelle/PROTOKOLL_VALIDATOR.md` (Fehler-Log F1-F10)

## Technik
- Neuer/anderer Rechner: `EINRICHTUNG_RECHNER.md` abarbeiten (Luefterregler-Dienst, Datenplatte, venvs, Mapillary-Token, GPU-Regeln).
- Grosse Daten (Fotos, Foto-Eingang, SfM-Netze, Wolken, Caches, Nullstart-Objekte) NIE auf der Root-Platte: immer unter `/media/oem/scan/rc-park_daten/<objekt>/` bzw. `/media/oem/scan/rc-park_null/`, im Repo Symlinks (Nutzerregel 2026-11-01; Root war bei 99 %).
- Python-Umgebungen: `/media/oem/scan/venv-seg/bin/python -I` (trimesh, torch, CUDA), `~/.venvs/rcpark` (manifold3d fuer den Generator).
- Lange Jobs (Nullstart, SfM, Optimierer) nur ueber `tools/job_start.sh NAME LOG BEFEHL...` (systemd-Benutzerdienst): Claude-Code-Hintergrundshells werden bei Speicherknappheit beendet (2026-11-03).
- Nur ein GPU-Job zur Zeit (COLMAP SIFT-GPU stuerzt neben LightGlue/Torch ab): `tools/nullstart.py` wartet per gpu_warten, Ernte deckelt auf 45 %; Werkzeugaenderung danach `tools/nullstart.py ... --ziel martinstor_null` als Wiederholbarkeitstest (Register AY/BA).
- Nie zwei Optimierer/Generatorlaeufe parallel mit gleicher Zwischendatei; Generatordatei nicht aendern, solange Optimierer laufen.
- Kein Commit/Push ohne Auftrag; Commit-Texte enden mit den Attribution-Zeilen der Sitzung.
