---
name: abnahme
description: Pflicht-Abnahme nach JEDER Generatoraenderung, objekt.json- oder masstabelle-Aenderung eines RC-Park-Objekts. Bauen, pruefen, Bilder ansehen, Realitaets-% melden.
---
1. `bash tools/bauen_abnehmen.sh <objekt>` (nur masstabelle geaendert: `--nur-pruefen`). Nur bei "alle Pruefungen bestanden" weiter; rot = Ursache klaeren, Sollwerte NIE lockern (nur mit neuer Quelle + `historie`).
2. Danach je Seite: `tools/fehlteile_finden.py`, `tools/foto_diff.py`, `tools/teile_lage_pruefen.py` (Argumente per `--help`).
3. ANSEHEN (Read-Tool): `modelle/<objekt>/audit/seiten.jpg`, `audit/neben_*.jpg` (mind. ein Foto je Seite), `audit/foto_diff_*.jpg`. Ohne diese Bilder nichts als passend melden.
4. Bericht: Fehlerliste je Teil zuerst, dann Realitaets-% (`tools/realitaet_prozent.py <objekt>`, Foto-F1 mitnennen), Bild per SendUserFile, 3D-HTML aktualisieren.
5. Skill `logbuch-commit`.
Neue Elemente im Generator: `beleg(seite, element, quelle)`; Annahmen `ANNAHME: ...`; nie ein Bauteil ersatzlos abschalten.
