---
name: kette-schleife
description: Die Agenten-Schleife (Durchbruch 22.11.2026) - Kettenlauf, Nebeneinander-Bild ansehen, je sichtbarem Befund ein opus-Agent im Worktree (nur Code), Merge-Probe, Merge nur bei Schnelltest 0, naechster Lauf. Verwenden bei "Kette verbessern", "Nacht durcharbeiten", "Modell soll aus der Kette besser werden", "Schleife".
---
Grundlage: `0_DURCHBRUCH_AGENTEN_SCHLEIFE.md` (lesen). Nichts am Modell von Hand messen/bauen. Bild schlaegt Zahl.

1. **Lauf** (immer nur EINER): Skill `langer-job`, `tools/job_start.sh kette-<obj>-<n> ... tools/gesamtkette.py <quelle> --ziel <ziel> [--ab fassaden --bis bauplan]`.
   Einmaligen Hintergrund-Warter auf `JOB_ENDE` setzen (kein wiederkehrender Cron). Waehrend der Kette rechnet niemand sonst.
2. ⛔ **ZUERST Bestand-Vergleich (HART, Nutzer 24.11.):** `audit/neben_*.jpg` + `seiten.jpg` neben die Bestbilder in `modelle/<obj>/bestand/`
   halten (README dort nennt Lauf/Zeit), Bestand-Tor im Log (`BESTAND`) lesen. Ein Bauteil sichtbar schlechter = RUECKSCHRITT: dem Nutzer
   beide Bilder schicken und so benennen, nichts mergen, Ursache-Agent (git bisect gegen den Bestand-Commit). Besser = neues Bestbild ablegen.
   **Auswerten:** `grep -a "ERGEBNIS DES LAUFS\|NICHT in Ordnung\|HANDSTAND\|FEHLER" <log> | tail`, Warnungen mit `FEHLER` im Log lesen
   (abgefangene Codefehler!), `journalctl -k --since <start> | grep -ci oom`. `audit/neben_*.jpg` + `seiten.jpg` ANSEHEN, dem Nutzer
   schicken (SendUserFile) mit Fehlerliste (sichtbar!) und Realitaets-% nach Aussehen. Logbuchzeile.
   Befund je Bauteil erst an der DETAILANSICHT bestaetigen: `audit/neben_details.jpg` (Raster) + `audit/neben_detail_<bauteil>.jpg`
   (Kettenstufe `neben_details`, tools/neben_details.py: beste SfM-Kamera je Bauteil, Profilteile zusaetzlich von der Seite; Wahl in
   `audit/neben_details.json`). Ein festes Nebenbild (Steilblick, Gegenlicht) taeuscht ("Vordach flach, Laterne fehlt" 22.11. war falsch).
   Fehlt die Detailansicht: `tools/py tools/neben_details.py modelle/<ziel>/objekt.json` (CPU, ~5 min, < 1 GB bei 1,4 Mio. Dreiecken). SCHWACH im Bild = verdeckt/kein Fotobeleg, nicht bewerten.
3. **Je Befund ein Agent** (hoechstens 2-3 gleichzeitig): `isolation: "worktree"`, `model: "opus"`, `run_in_background: true`.
   Auftrag: EIN Befund mit Bildpfad/Log/Zahlen; Ursache mit Belegen; generisch als Kettenstufe/Werkzeug + Test + Zeile in
   `tools/schnelltest.sh`; `test_undefinierte_namen` vor Commit; keine Handstand-Werte; Objektordner auf main nicht aendern;
   KEINE Rechenlaeufe waehrend der Kette; nur committen im eigenen Zweig, nicht mergen; Bericht Fehlerliste zuerst, Realitaets-%.
   Agenten fahren NIE den vollen Schnelltest (24.11.: vier parallele Laeufe, Last 137, alle 1 h im selben Selbsttest blockiert) - nur
   betroffene Einzeltests + `test_undefinierte_namen` + `bash -n tools/schnelltest.sh`, `OMP_NUM_THREADS=4`; voller Schnelltest EINMAL in der
   Merge-Probe. Ab 4 Agenten: Arbeitsbaum per `git worktree add` auf /media/oem/scan/rc-park_tmp (Root-Platz, je Baum 650 MB).
   Baut ein Befund auf einem ungemergten Zweig auf: "ZUERST `git merge --no-ff <zweig>`".
4. **Merge-Probe** waehrend die Kette laeuft: `git worktree add -b merge-probe-<x> /media/oem/scan/rc-park_tmp/merge_probe<n> main`,
   Agentenzweige dort mergen, Konflikte loesen (schnelltest.sh: beide Zeilen), Einzeltests der Agenten. NICHT in main mergen,
   solange die Kette laeuft (sie liest tools/ aus main).
5. **Nach Laufende:** vor dem Merge in main: `tools/ketten_probelauf.sh --rev merge-probe-<x>` = 0 (als Job: `JOB_RAM_MB=7000 JOB_GPU_MB=3000
   bash tools/job_start.sh ketten-probe-<x> <log> bash tools/ketten_probelauf.sh --rev merge-probe-<x>`; vorher `--plan`; einmalig `--grundstand`). Er laesst die
   ganze Kette auf kprobe_kaufhaus (60 Fotos) in einer Kopie laufen: Szenario Cache + Szenario verstellte Code-Staende (Fall 1122za). rc 1 = Ablauffehler
   (veralteter Stand, Handanweisung, Absturz, *_beleg) -> nicht mergen; Bestand-Tor rot im letzten Kettenlauf -> NICHT mergen (HART); rc 2 = kein Urteil (Lage o. ae.) -> melden. Dann Probe in main mergen, `bash tools/schnelltest.sh` = 0 Fehler, sonst zurueck + melden; `tools/baum_erzeugen.py`;
   `git pull --no-rebase --no-edit && git push`; gemergte saubere Worktrees entfernen (nie --force). Naechster Lauf (Schritt 1).
6. **Abbruch/melden:** zwei Laeufe hintereinander schlechter (Bild oder Zahl), Schnelltest rot, Platz < 15 GB trotz Aufraeumen,
   Loeschen noetig. Kippelt ein Mass von Lauf zu Lauf: zuerst zirkulaere Messung (misst eine Stufe ihr eigenes Vormodell?) suchen.
