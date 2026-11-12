# RC-Park – Arbeitsregeln (Kurzfassung)
Volltext aller Regeln (Nummern 1-9e, Technik, Lesepflichten): `modelle/REGELN_AUSFUEHRLICH.md` – bei Bedarf gezielt per grep/Read-Abschnitt lesen, nicht komplett.
Aktueller Stand: `modelle/STAND_2026-11-12_VORMITTAG.md` (neueste STAND_*-Datei).

## Abnahme (Pflicht)
- Nach JEDER Generatoraenderung: `tools/bauen_abnehmen.sh <objekt>`; nur bei "alle Pruefungen bestanden" weiter. Sollwerte nie lockern ohne neue Quelle (+ `historie`).
- Sichtbeobachtung = Testauftrag: erst `beobachtungen_offen` (datum, wer, text, naechster_schritt) in `masstabelle.json`, dann messen, dann Generator aendern.
- Nach jedem Bau `modelle/<objekt>/audit/seiten.jpg` ansehen; Zahlen allein gelten nicht. Neue Elemente: `beleg(seite, element, quelle)`; Annahmen heissen `ANNAHME: ...`.
- Fotomasse nur ueber `tools/foto_mass.py`; Zaehlungen nur am Foto (`tools/foto_zaehlung.py`); Form/Masse richten sich nach Fotokanten, Wolke nur Lage-Veto.
- Nach Bau: `tools/fehlteile_finden.py`, `tools/foto_diff.py`, `tools/teile_lage_pruefen.py`; vor Zeigen/Druck Teil neben Referenzfoto ansehen.
- Nach tools-Aenderung: `python3 tools/regression.py modelle/<objekt>/objekt.json --pruefen`.
- Linienhafte Features (Rippen, Baender, Leisten, Stäbe) NIE nach Farbschwelle/Wolke: Mehrfoto-Sweep mit Stabilitaetskarten (`tools/kanten_tiefe_sweep_flaeche.py`, Tiefenband um Flaeche) -> `tools/kanten_features.py --farbe stabil --sweep` (Luecken per Belegung/Spline, Rauschen faellt weg) -> `tools/features_in_objekt.py`; danach Abnahme + Render neben Foto. Druck-Teilnetze: erst `druck.splitter_verwerfen` pruefen (Mini-Splitter), nicht Konsolen.
- Quellen-Blindheit beachten (Laser/LoD2/Fotos/Dokumente); Quellenwidersprueche nicht mitteln.
- Neues Bauteil/falsch: Agentenauftrag aus `modelle/VORLAGE_BAUTEIL_RUNDE.md`.

## Technik
- Sitzungsbeginn: `bash tools/hpwmi_pruefen.sh` (bei ACHTUNG KERNEL-MODUL Nutzer sofort sagen).
- Grosse Daten nur unter `/media/oem/scan/...`, nie Root-Platte; Symlinks im Repo.
- Python: `/media/oem/scan/venv-seg/bin/python -I`, Generator `~/.venvs/rcpark`.
- Lange Jobs nur `JOB_GPU_MB=<MiB> tools/job_start.sh NAME LOG BEFEHL...`. Neue Rechenwerkzeuge von Anfang an auf GPU (`tools/gpu_knn.py`).
- Nie zwei Optimierer/Generatorlaeufe mit gleicher Zwischendatei parallel.
- Kein Commit/Push ohne Auftrag; Commit-Texte enden mit den Attribution-Zeilen der Sitzung. Pre-commit-Hook nur durch Nutzer aktivieren.
- Vor neuen Versuchen: `modelle/NICHTS_GEBRACHT.md`, `modelle/VERSUCHSREGISTER_MARTINSTOR.md`, `modelle/LIZENZ_WERKZEUGE.md`.
- Tool-Ausgaben kuerzen (cut/head/tail), Kontext sparen.
