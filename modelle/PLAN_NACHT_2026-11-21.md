# Nachtplan 21./22.11.2026 – Schwabentor fertig aus der Kette (für einfache Agenten)

Ziel (Nutzer): „Morgen früh ist es fertig“ – Schwabentor-Modell NUR aus Kettenläufen, mit Sichtblatt, Handstand-Zahl und Fehlerliste.
Grundregeln: CLAUDE.md lesen. Nichts von Hand messen/bauen – nur Kettenläufe starten, Agenten-Zweige mergen, prüfen, berichten.
Anrede „mein grosser Meister“, Deutsch, Fehlerliste vor Lob, Realitäts-% melden. Uhrzeit immer per `date`.

## Schleife (wiederholen bis 06:00 oder bis Abbruchregel)
1. **Platz prüfen:** `df -h / /media/oem/scan | tail -2`. Unter 15 GB: `bash tools/platz_waechter.sh einmal`.
   Fertige Worktrees nur entfernen, wenn `git -C <wt> status --porcelain | grep -v '^??'` leer ist UND der Zweig in main ist
   (`git merge-base --is-ancestor <zweig> main`), dann `git worktree remove <wt>` + `git branch -d <zweig>`. Nie --force bei Änderungen.
2. **Laufende Jobs:** `systemctl --user list-units 'rcpark-kette*' --no-legend`. Log: `/media/oem/scan/rc-park_daten/job_logs/<name>.log`.
   Ende erkennen: `grep -a "JOB_ENDE\|ERGEBNIS DES LAUFS\|HANDSTAND" <log> | tail -3`.
3. **Fertige Agenten-Zweige mergen** (`git branch | grep worktree-agent`, nur gemeldete fertige): `git merge --no-ff <zweig>`;
   Konflikt in tools/schnelltest.sh = beide Zeilen behalten; sonst Konflikt => NICHT raten, Zweig auslassen, im Logbuch melden.
   Danach `bash tools/schnelltest.sh` – nur bei „0 Fehler“ `git pull --no-rebase --no-edit && git push`, sonst `git merge --abort`/`git reset --hard ORIG_HEAD` (nur eigener Merge!) und melden.
4. **Kettenlauf starten**, sobald kein Schwabentor-Lauf aktiv ist (Name hochzählen: 1121q, 1121r, …):
   `JOB_GPU_MB=2500 JOB_RAM_MB=8000 bash tools/job_start.sh kette-schwabentor-<n> /media/oem/scan/rc-park_daten/job_logs/kette-schwabentor-<n>.log /media/oem/scan/venv-seg/bin/python -I tools/gesamtkette.py schwab_auto --ziel schwabentor-1120 --ab fassaden --bis bauplan --dicht-stufe schnell`
5. **Nach Laufende auswerten:**
   - `grep -a "ERGEBNIS DES LAUFS\|NICHT in Ordnung\|HANDSTAND" <log> | tail -4`
   - `tail -1 modelle/schwabentor-1120/audit/hand_vergleich_verlauf.jsonl` (Zahl X von 11, „daneben“)
   - Sichtblatt `modelle/schwabentor-1120/audit/seiten.jpg` ANSEHEN (Read) und an Nutzer schicken (SendUserFile).
   - **PFLICHT (Nutzer 21.11. 22:00 „Das ist noch nicht gut“ bei 11/11):** `audit/neben_*.jpg` (Foto | Modell) ANSEHEN und mitschicken. 11/11 prüft nur Höhen/Lagen, NICHT das Aussehen.
     Realitäts-% aus dem Nebeneinander schätzen (Fenster sichtbar? Quader lesbar? Vordach-Form? Eckquader? Dach?), nicht aus X/11.
   - Eine Zeile ins Logbuch `modelle/LOGBUCH_SCHWABENTOR_KETTE_2026-11-21.md`: Zeit, Lauf, git-Stand, X/11, Fehlerliste aus dem Bild.
6. **Neuer Fehler sichtbar** (Bauteil fehlt/falsch, Stufe „NICHT in Ordnung“): EINEN Worktree-Agenten starten mit
   Vorlage unten (ein Fehler je Agent, höchstens 2 gleichzeitig). Keine eigenen Fixes am Code ohne Test.
   **Fix-Agenten IMMER mit `model: "opus"` starten** (Nutzer 21.11. 19:05: Hauptsitzung darf Sonnet sein, Code-Fixes nicht) –
   Agent-Aufruf: `isolation: "worktree"`, `model: "opus"`, `run_in_background: true`. Baut der Fix auf einem ungemergten Zweig auf:
   im Auftrag „ZUERST `git merge --no-ff <zweig>`“ voranstellen.
7. Commit eigener Logbuch-/Plan-Dateien (gezielte Pfade, Attribution-Zeilen), `git pull --no-rebase --no-edit && git push`.

## Agenten-Vorlage (für Schritt 6)
„Repo /home/oem/git/rc-park. Lies CLAUDE.md. Objekt schwabentor-1120, Kette tools/gesamtkette.py. BEFUND: <Bauteil, Zahl, Bildpfad>.
Ursache benennen, GENERISCH als Kettenstufe + Test (tools/test_*.py, tools/schnelltest.sh) beheben, keine Werte aus dem Handstand,
Objektordner auf main nicht verändern, keine langen GPU-Jobs. Abschluss: schnelltest 0 Fehler, Commit nur eigene Dateien im
Worktree-Zweig (Attribution), nicht mergen. Bericht: Fehlerliste, Ursache, Fix, Kontrollbild (angesehen), Realitäts-%.“

## Offene Punkte (Reihenfolge nach Wirkung)
0. SICHTBAR (22:00, am neben-Bild): Rundbogenfenster nur flache Rechtecke (Agent läuft) · Quadermauerwerk klumpig + Eckquader verrauscht (Agent läuft) · Vordach flacher Kasten statt geschwungenes Ziegeldach · Wandgemälde unter Vordach als Klumpen statt flach · Dachüberstand dünn · Süd/Ost leer (Fotos).
1. Läuft: Agent „Kette beschleunigen“ (Wände parallel, Neubau nur am Ende) und Agent „zirkuläre Verdeckung/Vordach“ – nach Meldung mergen (Schritt 3).
2. Vordach-Anschluss 16,74 statt 19,39 (Ursache: Uneinigkeitskarte mit eigenem Modell als Verdecker) – Agent läuft.
3. Tor-Form schwankt zwischen Läufen (spitzbogen/sturz) – wenn im Lauf wieder falsch: Agent.
4. Westwand w00 (Putzwand, KEIN Wandgemälde - das sitzt auf f00 unter dem Vordach): Netz-Krümel aus unbelegten Netzinseln -> Fix tiefe_belegt (Agent 21.11. 21:30, Zweig worktree-agent-ad526fdb80742be1b).
5. Süd/Ost glatt = keine Fotos (Fotoauftrag `/media/oem/scan/rc-park_daten/schwabentor-1120/fotoauftrag_schwabentor-1120.json`) – NICHT erfinden.
6. Handstand-Vergleichswerte Uhr/Sohlbank/Laterne ~3,4 % zu tief (Kette nachweislich richtig) – NUR mit Nutzer-Ja ändern.

## Martinstor (nebenher, Schwabentor hat Vorrang)
Eingereiht `kette-martinstor-1121b` (startet automatisch nach Schwabentor 1121p; `--ab sfm`, rechnet Seitenwolken ohne Sperrliste neu, dann seiten_vereinen).
Prüfen: `grep -a "seiten_vereinen\|vereint\|ABGELEHNT\|JOB_ENDE" /media/oem/scan/rc-park_daten/job_logs/kette-martinstor-1121b.log | tail -5`.
Erwartet „vereint“ ~2 % Turmhöhen. Alte Seitenwolken liegen danach in `.../martinstor-1120/pipe/sfm/seiten_modelle/teil*/dicht_alt_*` (8,6 GB) → `bash tools/auslagern.sh <ordner>` auf /media/oem/rcdaten.
Läuft er, keinen weiteren Schwabentor-Lauf parallel mit RAM > 6000 starten – job_start wartet von selbst (RAM-Buchung), nicht von Hand Buchung senken.

## ARBEITSSPEICHER (Nutzer 21.11. 19:40: „lieber nur einen Job über Nacht als ständig scheitern“)
- Immer NUR EIN Kettenlauf gleichzeitig. Martinstor erst, wenn kein Schwabentor-Lauf mehr läuft (bzw. am Morgen) – nicht einreihen.
- Agenten dürfen während eines Kettenlaufs KEINE Rechenläufe starten (kein fassade_ortho/tiefe_lokal/steine/GPU-Test, kein Schnelltest mit Prüfstand) – nur Code + kleine synthetische Tests. Ursache 1121p: Agenten-Testlauf parallel -> CUDA-OOM w04 + Kernel-OOM w03 (Signal 6).
- Nach einem Lauf: `journalctl -k --since <Start> | grep -ci "out of memory\|oom-kill"` – > 0 melden.
- fassaden_kette wiederholt ein vom System beendetes Teilwerkzeug einmal (nacheinander) und plant Wände nach der Job-Buchung (RCPARK_RAM_MB).

## Abbruchregeln (dann nur melden, nichts erzwingen)
- Schnelltest > 0 Fehler nach Merge → Merge zurück, melden.
- Zwei Läufe hintereinander schlechter (X/11 sinkt) → keinen weiteren Merge, Ursache per Agent, melden.
- Platz < 5 GB trotz Aufräumen, GPU-OOM, Toshiba-Platte, Löschen nötig → stoppen und Nutzer fragen.

## Endbeweis (wenn ≥ 2 Läufe ohne neue Fehler)
Schwabentor einmal ganz von null: `... gesamtkette.py schwab_auto --ziel schwabentor-1120 --dicht-stufe schnell` (ohne --ab), JOB_RAM_MB=11000; Ergebnis wie Schritt 5.
