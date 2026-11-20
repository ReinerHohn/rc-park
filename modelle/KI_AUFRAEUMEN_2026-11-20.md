# KI-konformes Aufraeumen (20.11.2026)
Befunde (zwei Lese-Agenten, nichts verschoben): `modelle/ki_aufraeumen/befund_regeln.md` (Regeln, Widersprueche, Archiv-Kandidaten), `modelle/ki_aufraeumen/befund_werkzeuge.md` (970 Werkzeuge, 26 571 Bash-Aufrufe aus 43 Sitzungen ausgewertet).

## Erledigt
- CLAUDE.md neu (39 Zeilen statt Regelhaufen): Kernmethode, Pflichtpruefungen, Technik, "Aufgabe X -> Skill". Veralteter Stand-Verweis (STAND_2026-11-14, AUFGABENLISTE_2026-11-16) ersetzt durch ZIEL_PIPELINE_H0; venv-colmap + rcdaten ergaenzt.
- 12 Projekt-Skills `.claude/skills/`: sitzungsbeginn, abnahme, tools-pruefen, langer-job, wolke-tore, objekt-von-null, foto-vor-ort, bauteil-runde, fassaden, linien-features, druck, logbuch-commit (alle Pfade geprueft).
- 3 Workflows `.claude/workflows/`: abnahme-objekte (parallel + Gegenprobe), bauteil-runde (Worktree + 3 Pruefer), versuch-messen (Register/Lizenz -> Messplan -> Skeptiker).
- Wissensbaum (erzeugt von `tools/baum_erzeugen.py`): modelle/INDEX.md (Aeste nach Thema) -> modelle/inhalt/<name>.md (Ueberschriften mit Zeilennummern fuer 17 grosse Dokumente); tools/INDEX.md -> tools/index/<thema>.md (16 Themen); modelle/archiv/INDEX.md.
- 109 alte Dokumente nach modelle/archiv (216 Verweise umgebogen), 53 unreferenzierte Alt-Werkzeuge nach tools/archiv, P1S-Zugang nach ~/.config/rcpark/p1s.json, AGENTS.md -> CLAUDE.md.

## Wartet auf Nutzer-Ja
1. ARCHIV modelle/: ~90 von 154 MD (alte STAND_*/UEBERGABE_*, Rundenlogbuecher 9./10.11., Recherchen 6.-9.11., Methoden/Plaene Oktober) nach `modelle/archiv/` (git mv, Verweise vorher umbiegen; Liste in befund_regeln.md Abschnitt 4).
2. ARCHIV tools/: ~164 vermutlich tote Werkzeuge (u.a. 30 Alt-Objekt-Skripte hirschsprung/linach/hofgut) nach `tools/archiv/` (Liste befund_werkzeuge.md Abschnitt 3).
3. Widersprueche klaeren: (a) Memory "keine Agenten selbst starten" vs. "Agenten integrieren selbst, Worktrees" (17.11.); (b) Realitaets-% aus Wolkenbeleg vs. Kernmethode (Vorschlag: Foto-F1 als Hauptzahl).
4. SICHERHEIT: `tools/p1s_print.py` hat Zugangscode + Seriennummer des Druckers im Klartext im Repo (GitHub-Remote). Vorschlag: nach `~/.config/rcpark/p1s.json`; steht schon in der Git-Historie -> Zugangscode am Drucker neu setzen, falls das Repo nicht privat ist.

## Weitere Verbesserungen (Nutzen je Aufwand)
1. Python-Umgebung: Starter `tools/py seg|col|gen <tool>` oder Hook, der bei `python3 tools/X.py` mit pycolmap/trimesh-Import warnt (224 ModuleNotFoundError bisher).
2. Kurze Ausgaben: `RCPARK_KURZ=1` fuer bauen_abnehmen/gesamtkette + Summenzeile `ABNAHME rc=.. bestanden=..` (947 Ausgaben > 20 000 Zeichen seit 14.11.).
3. Riesendokumente teilen: VERSUCHSREGISTER_MARTINSTOR (348 KB), NICHTS_GEBRACHT (171 KB) je mit Stichwort-Index am Anfang; Uebergaben max. 3 KB.
4. Regression ausbauen: nur 6 von 25 Objekten haben einen regression-Block (schwabentor, kaufhaus_grob3, martinstor-1120 ergaenzen).
5. Docstring + argparse fuer die 60 meistgenutzten Werkzeuge (362 ohne --help); Zeilen > 300 Zeichen umbrechen (Edit trifft sonst schlecht).
6. Riesendateien baukasten_gen.py (169 KB) und bauteil_kreis.py (161 KB) in Module teilen.
7. Gemeinsame `tools/pfade.py` (ROOT, DATEN, objekt_dir) statt 179 hart verdrahteter Objektnamen; `/fewer-permission-prompts` fuer weniger Rueckfragen.
8. job_start.sh warnt laut ohne JOB_GPU_MB (234 Killed, 103 CUDA-OOM in den Protokollen).
9. VORLAGE_BAUTEIL_RUNDE.md auf neue Regel-Verweise (REGELN_AUSFUEHRLICH) und tools/bauteile.py statt baukasten_gen umstellen.
10. Memory-Index: veraltete Eintraege (stand-2026-11-15, aufgabenliste-1611, uebersehene-punkte-1511, disk-space) entfernen, Doppel (mitloggen) zusammenlegen.
