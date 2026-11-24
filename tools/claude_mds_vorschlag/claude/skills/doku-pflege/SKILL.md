---
name: doku-pflege
description: Räumt die Projekt-Doku eines Repos auf und hält sie KI-tauglich (für Claude Code) — Root-Markdown einsortieren, CLAUDE.md schlank halten (Details in pfadabhängige .claude/rules), Projekt-Wissensbaum (Gilt · Versucht · Offen, „was haben wir schon versucht") pflegen und aus Memory/Commits nachtragen, tote Links reparieren, fertige git-Worktrees entfernen. Richtet die Struktur in neuen Projekten auch erst ein. Verwenden bei „Doku aufräumen", „MDs aufräumen", „Projekt-Doku verbessern/KI-konform machen", „CLAUDE.md zu lang", „Versuche nachtragen", „Worktrees aufräumen". Aufruf: "/doku-pflege [schnell|voll|einrichten]".
---

# doku-pflege — Projekt-Doku kompakt und KI-tauglich (projektunabhängig)

**Ziel:** Claude und Mensch finden mit wenig Lesen das Richtige. Immer geladen wird nur `CLAUDE.md`; alles andere liegt im Baum
und wird nur bei Bedarf geöffnet. Nichts geht verloren: Altes wandert ins Archiv (`git mv`), nie löschen.

**Zwei Teile:**
- **dieser Skill** (`~/.claude/skills/doku-pflege/`) = Ablauf + Prüfskript `check.py`, für jedes Projekt gleich.
- **Projektteil im Repo** (optional): `.claude/doku-pflege.json` = Grenzen/Orte (Schlüssel: `check.py --config`) und
  `.claude/doku-pflege.md` = Besonderheiten (Code, der Doku-Pfade liest, Deploy-Ausschlüsse, Pflichtdateien, Privates …).
  **Schritt 0 immer:** beide lesen, falls vorhanden — Projektregeln gehen den Standards hier vor.

| Ort (Standard) | Inhalt | Grenze |
|---|---|---|
| `CLAUDE.md` | Regeln, die IMMER gelten + Befehle + Verweise | Konfig `budgets` (Std. 200) |
| `.claude/rules/*.md` | Detailregeln mit `paths:` — laden nur bei passenden Dateien | `rules_max_lines` |
| `PROJEKT.md` | Wurzel: Ast-Tabelle, Pflege-Regel, Grundsätze, „wartet auf Nutzer" | 60 |
| `Doku/projekt/<ast>.md` | **Gilt · Versucht · Offen**, eine Zeile je Punkt, Zeile 1 = Rücklink | `tree_max_lines` |
| `Doku/` · `Doku/archiv/` | Fach-Doku · Historie (Berichte/Audits/Status) | — |

Modi: `schnell` = 1, 2, 6, 7 · `voll` (Standard) = 1–7 · `einrichten` = E, dann voll.

## E. Einrichten (Projekt ohne `.claude/doku-pflege.json`, oder Modus `einrichten`)
- Erst ansehen: `ls *.md`, Größe von `CLAUDE.md`, gibt es `Doku/`/`docs/`, gibt es Memory (`check.py --config` → `_memory_dir`)?
- Vorschlag machen (eine kurze Liste) und bei Struktur-Entscheidungen den Nutzer fragen: Doku-Ordnername, welche Root-Dateien
  bleiben, welche Äste (aus den Code-Bereichen ableiten, 4–8 Stück). Bestehende Konventionen des Repos haben Vorrang.
- Dann anlegen: `.claude/doku-pflege.json` (nur abweichende Schlüssel), `.claude/doku-pflege.md` (Besonderheiten, die du dabei
  findest), Wurzel + Ast-Skelette mit den drei Abschnitten, in `CLAUDE.md` eine Zeile „Projekt-Wissen als Baum: … vor neuem Ansatz
  ‚Versucht' lesen, nach jedem Versuch eintragen". Steht `.claude/` pauschal in `.gitignore`, auf gezielte Ausschlüsse umstellen
  (`.claude/worktrees/`, `.claude/settings.local.json`) — vorher prüfen, dass der Deploy `.claude/` nicht ausliefert.
- **claude-mds automatisch einbinden:** `~/git/claude-mds/claude-mds-sync.sh` nach `.claude/claude-mds-sync.sh` kopieren und in
  `.claude/settings.json` einen SessionStart-Hook `bash "$CLAUDE_PROJECT_DIR/.claude/claude-mds-sync.sh"` + den PreToolUse-Hook
  `no_big_binaries` eintragen (Vorlage: README von claude-mds) — dann braucht kein Rechner eine Einrichtung.

## 1. Befund
`python3 ~/.claude/skills/doku-pflege/check.py` im Repo (nur lesend). ✗ = Auftrag; · = prüfen, oft harmlos.

## 2. Root-Markdown einsortieren
- Je gemeldeter Datei kurz ansehen → Ziel laut `sort_targets` (Konzept/Anleitung, die noch gilt ⇒ Doku; Bericht/Audit/Status ⇒
  Archiv). Immer `git mv`.
- VORHER Verweise suchen: `grep -rnF "<NAME>.md" --exclude-dir=.git --exclude-dir=.claude --exclude-dir=node_modules .` —
  Code, der den Pfad liest, und Doku-Links nachziehen; Querverweise innerhalb archivierter Berichte dürfen bleiben.
- README muss DIESES Projekt beschreiben und auf die Einstiege verweisen (veraltete README ⇒ Archiv, neue kurze schreiben).

## 3. CLAUDE.md schlank halten
- Zu lang ⇒ Abschnitte mit Anlass-Geschichten, Bauplänen, Detail-Checklisten nach `.claude/rules/<thema>.md` mit
  `paths:`-Frontmatter (Globs auf die Dateien, wo die Regel greift); in CLAUDE.md bleiben 1–3 Zeilen Kern + `→ .claude/rules/<thema>.md`.
- Regeln, die überall gelten (Datensicherheit, Test-Pflicht, Deploy-Weg, Arbeitsweise …), bleiben IMMER in CLAUDE.md.
- Beim Verschieben NIE kürzen oder umformulieren, nur umziehen. Danach Stichwort-Abgleich gegen `git show HEAD:CLAUDE.md`:
  jede harte Regel ist in CLAUDE.md oder einer Regeldatei auffindbar.
- Was ein Hook erzwingt (`.claude/settings.json` hooks), braucht nur einen Satz + Verweis.
- Veraltete Angaben (Laufzeiten, Pfade, Befehle) nachmessen und korrigieren statt übernehmen.

## 4. Wissensbaum pflegen
- **Neue Versuche nachtragen** seit `git log -1 --format=%cs -- <tree_glob-Ordner>`: neue Memory-Notizen (`_memory_dir`,
  `ls -t`) und Rückbau-Commits (`git log --since=<datum> --format='%h %cs %s' | grep -iE 'revert|zurück|rückbau|entfernt|statt|rollback'`).
  Bei vielen Treffern: je Ast-Gruppe einen **read-only Explore-Agenten** parallel, der Zeilen im Format unten zurückgibt —
  Agenten schreiben NIE selbst in die Äste; ich führe zusammen und verschmelze Doppeltes.
- Format, eine Zeile je Versuch:
  `- TT.MM. · <Ansatz> → ✗ verworfen | ↺ ersetzt durch X | ⚠ Falle | ⏸ zurückgestellt · <Lehre ≤ 15 Wörter> [commit/quelle]`
  Nur Belegtes; ohne Datum `- · …`. Erledigte Bugfixes ohne Lehre gehören nicht hinein (das ist der git log).
- **„Offen" ausmisten:** jeden Punkt gegen Code/git log/Tags prüfen. Erledigt ⇒ löschen; unklar ⇒ „(Stand TT.MM., ungeprüft)".
- Neue Nutzer-Vorgaben ⇒ „Gilt"; querschnittliche Nutzer-Entscheidungen ⇒ Liste in der Wurzel.
- Ast über Grenze ⇒ Zeilen in einen **Unterast** (`<ast>/<thema>.md`, in Zeile 2 des Asts verlinkt) verschieben — **nie kürzen oder weglassen** (Nutzer 24.11.2026: 66 von 125 Registerabschnitten gingen beim Verdichten verloren). Vollständigkeit gegen alle Quellen maschinell prüfen (z. B. `tools/wissensbaum_luecken.py`), nicht gegen eigene Auszüge.
- **Privates nie ins Repo** (Namen, E-Mail, Arbeitsverhältnis, Passwörter) — das gehört ins Memory.

## 4b. Wissen finden (vor jedem neuen Ansatz, jedem Agentenauftrag, jedem neuen Werkzeug)
Warum: Im Projekt rc-park lag das Wissen am 24.11.2026 vor, wurde aber nicht gefunden. Bildauswahl, Flächenmaß und Brennweite aus EXIF
wurden doppelt gebaut. Die Suche lief mit anderen Wörtern als die Quelle („Bildauswahl" gegen „Teilmenge"). Die Quelle lag im Archiv,
war nicht eingecheckt oder stand nur im Memory-Archiv.
- **Suchen:** im Projektordner `python3 ~/.claude/skills/doku-pflege/wissen_suchen.py <Wörter, wie man fragt>`.
  - Ein Aufruf durchsucht Baum, Register, Logbücher, Archiv, Memory (auch Archiv), Werkzeugköpfe und git log.
  - Ausgabe: zuerst die TOP 10 nach Relevanz, dann je Quelle.
  - Füllwörter fallen weg, Stamm und Teilwort treffen mit („auswählen" findet „Fotoauswahl").
  - Synonyme stehen je Projekt in `.claude/wissen_synonyme.json`, oder an dem Pfad, den die Konfig nennt.
  - Die Gruppe „Ähnliche Werkzeuge" findet Vorläufer auch ohne gleiches Wort (Wortschatz-Kosinus, `werkzeug_aehnlich.py`).
- **Ins Ergebnis:** Vorläufer und ✗-Zeilen gehören in den Agentenauftrag. Ein neues Werkzeug nennt sie im Kopf in einer Zeile
  `Verwandt/Vorlaeufer: …` („keine", wenn die Suche nichts fand).
- **Fehlsuche = Synonym lernen:** Ist das richtige Wort erst im zweiten Anlauf gefunden (die Suche gibt einen HINWEIS mit
  Wortvorschlägen), kommt es als Synonym in die Synonymdatei. Der Fall kommt außerdem in die Falldatei (unten).
- **Vollständigkeit:** `python3 ~/.claude/skills/doku-pflege/luecken.py` prüft, ob jeder Quelleintrag als Verweis im Baum steht.
  Quellen stehen in `.claude/doku-pflege.json` → `"wissen": {"luecken": [...]}`. Arten: abschnitt, zeile, datei. Memory-Archiv automatisch.
  Doppelt vergebene IDs werden gemeldet. Nicht eingecheckte Dateien zählen nicht als Quelle; sie werden als Warnung gemeldet, der Nutzer
  entscheidet. „0 fehlend" gilt nur mit diesem Werkzeug, nie nach einer Stichprobe.
- **Nachweis Recall@5:** `python3 ~/.claude/skills/doku-pflege/wiederfinden.py` liest die Falldatei (`"wissen": {"faelle": …}`,
  Standard `.claude/wissen_wiederfinden.json`).
  - Je echter Verlustfall: Suchwörter, wie ein Agent fragt (nicht die Quellwörter), und eine Regex auf die erwartete Fundstelle.
  - rc 1, wenn weniger als `mindest_recall` der Fälle in den Top 5 stehen. Gehört in den Schnelltest des Projekts.
  - Ein Kontrollsatz (`"kontrolle"`) wird nie zum Abstimmen benutzt. Er zeigt, ob eine Verbesserung verallgemeinert.
  - Neue echte Fehlsuchen kommen als Satz `"neu_<datum>"` mit `"erster_versuch": false` dazu. Gemessen werden sie zuerst ohne Abstimmung.
    Die Kennzahl ERSTVERSUCH-QUOTE ist der Anteil der echten Suchen, die beim ersten Anlauf trafen.
- **Alltagsfragen je Zeile (doc2query, gegen die Vokabellücke):** Wissenszeilen sind Fachkurzschrift, Fragen kommen in Alltagssprache.
  Je Baumzeile und je Register-/Archivkopf schreibt ein Sprachmodell 3 Fragen, die diese Zeile beantwortet.
  Sie liegen in `<fragen_ordner>/<pfad mit / → __>.jsonl` und sind per Zeilen-Hash an die Zeile gebunden. Suchen zeigt die Originalzeile.
  - Ablauf: `wissen_fragen.py --offen [--koepfe --glob …] --aus DIR` liefert Blöcke, Agenten schreiben die Antworten, `--einpflegen` übernimmt sie.
  - Eine neue Baumzeile bekommt ihre Fragen beim Eintragen. `--pruefen` zählt die Zeilen ohne Fragen (Warnung).
- **Bedeutungssuche (optional):** `wissen_bedeutung.py` bettet Zeilen und Fragen ein (Satz-Embedding, z. B. intfloat/multilingual-e5-small, MIT).
  Es läuft nur auf der CPU und legt einen Index je Datei-mtime an. `wissen_suchen.py` verbindet die Bedeutungssuche per Rangfusion (RRF) mit der Wortsuche.
  Eingeschaltet wird sie über `"wissen": {"bedeutung": {"python": <venv mit torch+transformers>, "modell": <ordner>, "index": <ordner>}}`.
  Fehlt etwas davon, bleibt es bei der Wortsuche. `--bedeutung aus` oder `WISSEN_BEDEUTUNG=aus` schaltet sie ab.
- Konfig-Schlüssel `"wissen"`: `baum`, `register`, `logbuch`, `archiv`, `werkzeuge` (Globs), `meta_werkzeuge`, `synonyme`, `faelle`,
  `luecken`, `memory`, `fragen_ordner`, `bedeutung`. Was fehlt, nimmt den Standard (PROJEKT.md + Doku/projekt, Doku/*.md, Doku/archiv, tools/ + scripts/).

## 5. Worktrees & Branches  (nur Gemergtes, nie erzwingen)
1. Worktrees mit laufenden Prozessen auslassen (`for p in /proc/[0-9]*; do readlink $p/cwd; done | grep <worktree-ordner>`).
2. Entfernbar nur, wenn sauber (`git -C <wt> status --porcelain --untracked-files=no` leer) UND Arbeit im Hauptbranch:
   `git cherry <main> <branch>` ohne `+` ODER Commit-Titel steht 1:1 in `git log <main> --format=%s`.
3. VOR dem Löschen `<branch> <sha>` an ein Lösch-Protokoll im Archiv anhängen (Wiederherstellung: `git branch <name> <sha>`).
4. `git worktree remove <pfad>` OHNE `--force` (gesperrte = laufende Sitzung, bleiben) → `git branch -D <branch>`;
   dann `git worktree prune`, gemergte Branches ohne Worktree mit `git branch -d`.
5. Nicht Gemergtes/Geändertes NICHT anfassen — im Bericht mit Commit-Titel auflisten, der Nutzer entscheidet.

## 6. Prüfen
- `check.py --strict` muss Exit 0 liefern.
- Code-Dateien angefasst (Pfad-Verweise) ⇒ Syntax-Check + passende Tests des Projekts. Verschobene Dateien, die Tests lesen könnten:
  in den Testdateien nach dem Dateinamen greppen.
- Deploy nur, wenn der Projektteil es für Doku-Änderungen verlangt (meist nicht).

## 7. Commit + Bericht
- Ein Commit je Schritt-Gruppe (`chore(doku): …` / `docs(projekt): …`), Verschiebungen im Body.
- Bericht: vorher/nachher (Root-Dateien, Zeilen CLAUDE.md/Wurzel, Anzahl Versuche, Worktrees/Größe), was absichtlich stehen
  blieb und warum, was beim Nutzer liegt. Neue Projekt-Besonderheit entdeckt ⇒ in `.claude/doku-pflege.md` nachtragen.
