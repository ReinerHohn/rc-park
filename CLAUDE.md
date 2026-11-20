# RC-Park – Arbeitsregeln (Kurzfassung)
Fotos -> SfM (COLMAP) -> 3D -> druckbares H0-Modell (1:87), wird verkauft. Deutsch, Anrede "Meister", keine breiten Tabellen.
Stand zuerst: `modelle/ZIEL_PIPELINE_H0.md` (UEBERGABE/NACHTRAG am Ende) -> dort verlinktes Logbuch (UEBERGABE am Ende). Sitzungsbeginn: Skill `sitzungsbeginn`.
WISSENSBAUM (nie ganze Ordner/grosse Dateien lesen): Dokumente `modelle/INDEX.md` -> Ast -> grosse Datei ueber `modelle/inhalt/<name>.md` (Zeilennummern, Read offset/limit); Werkzeuge `tools/INDEX.md` -> `tools/index/<thema>.md`; Archiv `modelle/archiv/INDEX.md`. Neu erzeugen: `python3 tools/baum_erzeugen.py`. Volltext Regeln: `modelle/REGELN_AUSFUEHRLICH.md`.

## KERNMETHODE (nie vergessen)
- Form = Fotokanten + Triangulation (Kanten-Tiefen-Sweep mit SfM-Kameras). SfM liefert die KAMERAS. Dichte Wolke/LoD2/DOM1 nur Lage-Veto, Hoehe, Gegenprobe.
- WANDBILD = BAUPLAN: Wand aus vielen Fotos entzerrt (`tools/fassade_fein.py`) + Tiefe je Zelle -> Gestalt nachbilden. Erkennen = nur Zone/Loch. Keine Musterteile; Katalog nur Freistehendes.
- Jede Kette: Kantenstufe + Foto-F1 (`tools/teil_fotoform.py`) + `tools/foto_diff.py` als Tor.
- Formfamilie aus >= 3 Fotos. Zaehlen nur am Foto (`tools/foto_zaehlung.py`), Masse nur `tools/foto_mass.py`.
- Quellen nicht mitteln; Lage unabhaengig belegen (GPS, DOM1-Hoehe, Massstab). Neue Objekte: Fotos -> SfM -> LoD2 nur Abgleich.
- Ungesehene Wand nie spiegeln/erfinden -> Fotos suchen. Neue Bauteile nur generisch in `tools/bauteile.py`.
- Symmetrische Tuerme: Seitenverwechslung pruefen; globale Modelle erst `tools/modell_zerlegen.py`, dann bewerten.
- Verwerfen nur mit benannter Ursache. Vor neuen Versuchen: `modelle/NICHTS_GEBRACHT.md`, `modelle/VERSUCHSREGISTER_MARTINSTOR.md`, `modelle/LIZENZ_WERKZEUGE.md` (nur verkaufstaugliche Lizenzen; NC nur Test).

## Pflicht-Pruefungen (Ablauf je Skill)
- Generatoraenderung -> Skill `abnahme` (`tools/bauen_abnehmen.sh <objekt>`; nur bei "alle Pruefungen bestanden" weiter; Sollwerte nie lockern ohne neue Quelle + `historie`).
- tools-Aenderung -> Skill `tools-pruefen` (`bash tools/schnelltest.sh`, dann `tools/regression.py ... --pruefen`).
- Nach dichter Wolke -> Skill `wolke-tore`.
- Sichtbeobachtung = Testauftrag: erst `beobachtungen_offen` in `masstabelle.json`, dann messen, dann Generator.
- Zahlen allein gelten nicht: `audit/seiten.jpg` + `audit/neben_*.jpg` ansehen. Fehlerliste vor Lob, Realitaets-% melden. Annahmen heissen `ANNAHME: ...`.

## Technik
- Grosse Daten nie auf Root: `/media/oem/scan/...` (knapp) bzw. `/media/oem/rcdaten` (gross), Symlinks. Ohne /media/oem/scan kein git. Toshiba-Platte nie anfassen.
- Python: `/media/oem/scan/venv-seg/bin/python -I` (torch/CUDA), `/media/oem/scan/venv-colmap/bin/python -I` (pycolmap), Generator `~/.venvs/rcpark` (trimesh). Einfachster Weg: `tools/py <werkzeug.py> ...` (waehlt die Umgebung nach Importen). Nackter `python3` hat weder trimesh noch pycolmap (224 Fehler bisher).
- Lange Jobs nur per Skill `langer-job` (`tools/job_start.sh` mit JOB_GPU_MB/JOB_RAM_MB); vorher Dummy-Test; GPU immer nutzen, VRAM-Summe <= 7000 MiB.
- Nie zwei Optimierer/Generatorlaeufe mit gleicher Zwischendatei parallel. Nie `pkill -f` mit Muster aus der eigenen Befehlszeile.
- Loeschen nur nach ausdruecklichem "Ja". Kein Push ohne Auftrag. Eigene Aenderungen sofort committen (Skill `logbuch-commit`), Attribution-Zeilen. Hook nur Nutzer.
- Nie idle, nachts weiterarbeiten; aber KEIN wiederkehrender Cron/Loop fuer Job-/GPU-Checks (einmalige Warter ok).
- Kontext sparen: Ausgaben kuerzen (cut/head/tail). Bilder (SendUserFile) + 3D-HTML zeigen. Kein Druck ohne Nutzerwunsch.

## Bei Aufgabe X -> Skill / Dokument
- Neues Objekt / Kette von null -> `objekt-von-null`. SfM/Mapper -> `modelle/GLOBALER_MAPPER_STABIL.md`.
- Foto vom Nutzer vor Ort -> `foto-vor-ort`.
- Bauteil neu/falsch -> `bauteil-runde` (`modelle/VORLAGE_BAUTEIL_RUNDE.md`).
- Fassaden/Fenster/Relief/leere Wand -> `fassaden` (`modelle/PIPELINE_FASSADEN.md`).
- Rippen/Baender/Leisten/Staebe -> `linien-features`.
- Drucken -> `druck`.
- Lehren: `modelle/REZEPT_GEBAEUDE_AUS_FOTOS.md` (Lehren-Register). Platten: Memory reference-laufwerke-uuid.
