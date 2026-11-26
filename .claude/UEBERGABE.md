# Übergabe 26.11.2026 10:30 (löst die von 26.11. 05:30 ab)
Weiter mit: „weiter“ (oder /uebergabe fortsetzen). Vorher Skill `sitzungsbeginn`.

## Auftrag
- Hauptziel (Nutzer 24.11.): Kette baut das Schwabentor automatisch mindestens so gut wie Handmodell `schwab_v3` (`modelle/PLAN_HANDMODELL_IN_KETTE.md`), danach ein zweites Objekt. „Keine Handangriffe, nur Automatik.“
- Nie schlechter als Bestand: nach jedem Lauf zuerst `audit/neben_*.jpg` neben `modelle/schwabentor-1122/bestand/` ansehen und dem Nutzer schicken, dann Zahlen. Merge nach main nur bei grünem Bestand-Tor und Schnelltest 0.
- Nutzer 26.11.: „Wann gibt es endlich mal ein 3D-HTML?“ (jetzt da) · „Wo bleibt die Dichtewolke?“ (nachgereicht) · „konvergieren heißt stetige Verbesserungen. Reicht unser Tooling?“ (Antwort: nein, siehe Nächste Schritte) · „Können wir den Probelauf nicht beenden, machen einen Direktcode-Stand?“ (Probelauf beendet, code_stand-Agent läuft).

## Erledigt und geprüft
- Lauf 1122zj (Probe 34 ea13117b8, 06:17–07:41, rc 6 durch Bestand-Tor f04): Bilder gesehen und dem Nutzer geschickt. Dach = Pyramide mit Kragen wie Handstand, Stufigkeit 0 % in allen beurteilten Zonen, Fensterform 0 FALSCH (17 geprüft), Konvergenz 1 besser / 11 gleich / 0 schlechter von 12. 7/11 PASST.
- Relief-„Verlust“ war nur das Sichtblatt (frontale Ortho zeigt Vektorschichten nicht). Fix `tools/seiten_audit.py` Streiflicht (f1757afdd), Relief im STL gleichauf mit Bestand (Hochpass-Anteil Nord/Süd/West 10/10/7 % gegen 10/9/8 %). Ost (-y) ist oben flach, im Bestand 25.11. war ein Quaderfeld (eigener Befund, offen).
- Bestandskasten f04 neu eingefroren (Freigabe Nutzer 26.11. „Ja, du kannst einfrieren“): Werkzeug `tools/bestand_zone_neu.py` + Test, Sicherung `bestand.vor_zone_neu_2026-11-26_081043.json`, andere 13 Zonen bytegleich. Bestand-F1 f04 jetzt 0,727 (Kasten u −0,26..1,20 z 0,29..2,88).
- Tür f04 (Agent a5ef, Branch `tuer-laibung-f04` 10a95321e): offline F1 0,499 → 0,677 (Bestand 0,727, Schwelle 0,073). Foto 114112 aber 0,87 → 0,66 (Laibungsband links noch rot), Sturz/Inschrift 1517 und Schulterbogen fehlen. NUR offline gemessen, Kettenlauf steht aus.
- Probe 34 = merge-probe-34 = 20da68993 (ea13117b8 + Relief-Streiflicht + bestand_zone_neu + Tür-Fix). Schnelltest 0 (zweiter Lauf; im ersten zufälliger Fehler `ebene_sicht` unter Last, einzeln 2x grün).
- 3D-HTML: https://claude.ai/artifact/HpHTFG3gnrQu74zFwuWjYx (Version 2, Lauf 1122zj, 2-cm-Raster, 250 000 Wolkenpunkte). Nicht im Browser angesehen.
- Nutzer-Freigaben umgesetzt: 4 Höhenwerte referenz_hand (11bf900e0, früher). Höhen-Tor Dach nach Foto/Wolke bewerten, Laser nur Veto: Nutzer „Beides ja“ (noch nicht umgesetzt).

## Läuft gerade
- Agent a040d9af32c60bd4b (Worktree `.claude/worktrees/agent-a040d9af32c60bd4b`): repariert `tools/code_stand.py` + Teilbau (kein VERALTET durch `__main__`/CLI/Hilfsmodule, aber echter Erzeugercode muss VERALTET geben). Bericht kommt per Handback; keine Kette, kein Merge.
- Kein Kettenlauf und kein Job aktiv (nur Dauerdienste). Probelauf `ketten-probe-p34e` per `systemctl --user stop` beendet.

## Nächste Schritte
1. Agent a040 abwarten, Bericht prüfen, Zweig in Probe 34 mergen (temporärer Worktree, dann `git update-ref refs/heads/merge-probe-34 NEU` + `git checkout NEU -- <Dateien>` im Probe-Worktree `/media/oem/scan/rc-park_tmp/merge_probe34`), Schnelltest 0.
2. Voller Lauf 1122zk aus Probe 34: `cd /media/oem/scan/rc-park_tmp/merge_probe34 && JOB_RAM_MB=9000 JOB_GPU_MB=6000 bash tools/job_start.sh kette-schwabentor-null-1122zk /media/oem/scan/rc-park_daten/job_logs/kette-schwabentor-null-1122zk.log env RCPARK_BESTAND_EINZELN=1 PYTHONUNBUFFERED=1 /media/oem/scan/venv-seg/bin/python -I tools/gesamtkette.py schwab_auto --ziel schwabentor-1122 --ab bauen --dicht-stufe schnell` (Preflight: `daten/schwabentor-1122` als Symlink im Arbeitsbaum). Nach 5 min rc bauen und STL-Zeitstempel prüfen. Warter mit JOB_ENDE/Traceback + Timeout. Dauer ca. 2,5–3 h.
3. Nach dem Lauf: Bilder (`audit/seiten.jpg` mit Streiflicht, `neben_detail_fenster_tuer_f04.jpg`, `neben_*` gegen `bestand/`) an den Nutzer, dann Zahlen: Bestand-Tor f04 (Soll ≥ 0,654), Höhen-Tor Dach, Stufigkeit, Fensterform, Foto-F1. 3D-HTML mit Wolke neu bauen: `tools/modell_3d_html.py modelle/schwabentor-1122/objekt.json <aus.html> --wolke …/wolke_anzeige/punkte_modell_schwabentor-1122.npy --farben …/punkte_farben_schwabentor-1122.npy --max_mb 15`, per Artifact unter obiger URL republizieren.
4. Grün ⇒ nach main mergen (Schnelltest 0, `merge_sperre.sh` 0), Push. Rot ⇒ nicht mergen, Ursache-Agent.
5. Stand neu einfrieren (`tools/bauteil_schleife.py einfrieren`) und ab dann Teilbau je Befund statt voller Läufe.
6. Weitere Agenten: Höhen-Tor Dach (Foto/Wolke bewerten, Laser Veto, nur mit Beleg); Ost-Seite oben flach (erst klären, welche Fotos es gibt); Tür-Laibungsband/Sturz/Schulterbogen; Fallback `w01_foto_vorbau_q_kg` („Teil verschluckt“).
7. Tooling für stetige Verbesserung (Nutzerfrage): Verlaufstabelle je Bauteil über Läufe mit Rauschschwelle als feste Kettenausgabe; Referenz-/Kastenbeleg vor dem Bestand-Tor; Massstab-Tor auch bei `--ab bauen`; Schnelltest-Flakes unter Last.

## Entscheidungen des Nutzers
- ✓ Bestandskasten f04 neu einfrieren (umgesetzt). ✓ Höhen-Tor Dach nach Foto/Wolke, Laser nur Veto (zugesagt, noch nicht umgesetzt). ✓ 4 Höhenwerte (11bf900e0). ✓ code_stand-Reparatur: Nutzer fragte „Probelauf beenden, Direktcode-Stand?“, so umgesetzt.
- ? Offen: Zweig `worktree-agent-a48b14a86946e8fd2` (a04d28bbf, Kasten-Werkzeug, enthält Generator-Indexseiten + Doku/Logbuch-Zeilen) nur teilweise in Probe 34 (nur Werkzeug + Test + Schnelltest-Zeile). Doku-Zeilen/Logbuch des Zweigs fehlen in Probe 34, später nachziehen.

## Fehler und Lehren dieser Sitzung
- 3D-HTML nachts nicht gezeigt, danach erst mit falschem (altem) STL und ohne Wolke gebaut; Regel „immer 3D-HTML zeigen“ jetzt an jeden Kettenlauf hängen (Memory vorhanden).
- „Tür sieht im Bild richtig aus“ war zu optimistisch (Detailbild statt Messung); Bild und Zahl über alle Fotos zusammen ansehen.
- Zeitangabe „2–3 h“ war für diese Art Änderung falsch gemeint: Sichtblatt/Bestand-Werkzeuge brauchen keinen Lauf. Teilbau war aber wegen `code_stand` VERALTET (Ursache des Tooling-Mangels).
- Probelauf muss als Job (`job_start.sh`) laufen; sonst rc 3 „nicht als Job gestartet“.
- `modell_3d_html.py` braucht `--wolke/--farben`, sonst Wolke 0.
- Aus früherer Sitzung: Befund nie aus Detektorlog, immer am Foto prüfen; Probelauf aus dem Probe-Worktree starten.

## Wichtige Pfade und Befehle
- Probe-Worktree `/media/oem/scan/rc-park_tmp/merge_probe34` (Symlinks, `git merge` scheitert dort). Bestand `/media/oem/rcdaten/rc-park_bestand/schwabentor-1122/` (Prüfbilder f04 `pruefung_2026-11-26_tuer_f04/bilder/`). Tür-Agent-Bilder `/media/oem/rcdaten/tmp/f04_lauf_a5ef/bilder_bericht/`, Relief-Render `/media/oem/rcdaten/tmp/relief_render/`. Bau-Kopien `/media/oem/rcdaten/tmp/f04_lauf_*` (je ~140 MB) können nach Nutzer-„Ja“ weg.
- Branches: `agent-relief-kontur` f1757afdd, `tuer-laibung-f04` 10a95321e, `worktree-agent-a48b14a86946e8fd2` a04d28bbf, `mp34-form`, `mp34-stuf` (Hilfsbranches, aufräumen). Worktrees nie mit `--force` entfernen, löschen nur nach Nutzer-„Ja“.
- Root-Platz 7,7 GB frei (Ziel > 15 GB): gemergte Worktrees entfernen, Handprobe-Ordner `/media/oem/rcdaten/rc-park_teilbau/handprobe_reliefkontur_20261126/` aufräumen (nach Ja).

## Vorsicht
- Nur EIN Teilbau oder eine Kette gleichzeitig (Bau-Sperre `/tmp/rcpark_bau_schwabentor-1122.lock`); Agenten rechnen nicht während der Kette.
- Alte eingefrorene Teilbau-Stände (`stand_20261126_013724`) werden nach der code_stand-Änderung ungültig, neu einfrieren.
- `main` hat uncommittete fremde Änderungen (modelle/kaufhaus_grob3, inhalt/…): nicht anfassen, nur eigene Pfade committen. Nach main nichts gemergt seit 29eba0e97.
