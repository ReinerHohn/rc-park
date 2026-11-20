# doku-pflege — rc-park-Besonderheiten
Ergänzt den allgemeinen Skill `~/.claude/skills/doku-pflege/` (Quelle: `~/git/claude-mds`); Grenzen/Orte in `.claude/doku-pflege.json`.

- **Arbeitsbranch = `kaufhaus-freiburg`** (weit vor `main`). Auf diesem Branch liegt oft viel UNCOMMITTETE Modell-Arbeit (STL/GLB/PNG,
  tools/, daten/) — Doku-Commits NUR mit gezielt gestagten Pfaden (`git add <pfad>`), nie `git add -A`/`-u`.
- **Root:** nur `HANDOFF.md` (Einstieg der Claude-Instanz auf dem GPU-PC — nicht verschieben), `README.md` (Index-Tabelle aller Dokumente — bei jedem Verschieben Links nachziehen), `CLAUDE.md`, `PROJEKT.md`, `KONZEPT.md` (Vision).
  Neue Konzept-Kapitel nach Thema in `Doku/<thema>/` und eine Zeile in die README-Tabelle.
- **`modelle/*.md`** (METHODE_*, PROTOKOLL_*, QUELLEN_REGISTER, STAND) gehören zu den Modellen und werden von Tools/Tests gelesen
  (`tests/test_quellen_hart.py` → `QUELLEN_REGISTER.md`, `tools/quellen_inventar.py` → `QUELLEN.md`) — NICHT verschieben.
- **Generierte Dateien:** `businessplan.html` (aus `build.py`) nie von Hand ändern.
- **Link-Fehlalarme:** `](bbox` in `modelle/METHODE_WUNSCH_ZU_MODELL.md` / `REPRODUKTION.md` ist Code-Text, kein Link.
- **„Versucht" nachtragen:** reichste Quelle ist der Memory-Index (`~/.claude/projects/-home-md-git-rc-park/memory/MEMORY.md`) — die Zeilen
  enthalten LEHRE/FALLE schon; dazu `modelle/AENDERUNGEN.md`/`PROTOKOLL_*.md`.
- **Tests:** `python3 tests/test_quellen_hart.py`, `python3 tests/test_hybrid_hart.py`. Doku-Änderungen brauchen keinen Build.
- **Privat:** Persönliches (Geräte, Konten, Kontakte aus `anschreiben.md`) nie in `Doku/projekt/` übernehmen.
