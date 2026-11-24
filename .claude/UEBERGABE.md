# Übergabe 24.11.2026 11:00
Weiter mit: „weiter" (oder /uebergabe fortsetzen). Vorher Skill `sitzungsbeginn`.

## Auftrag
- Stehend (seit 22.11.): „Keine Handangriffe, nur Automatik." · „Ich will die Südseite" · „parallel", „Vollgas", „Verbessere die Pipeline". Arbeitsweise Skill `kette-schleife`.
- Heute: „Was können wir noch verbessern?" → „Ja, mach alles." · Bau auf mehreren Kernen: „Ja." · „Ja, du darfst verschieben." (MachineFrameWork, ~/.codex)
- Nutzerfrage: „Wann verschwindet diese letzte Fehlerwolke?" (Oberleitung in der Wolke am Nordturm) · „Die Gaube auf der Nordseite … warum nicht wiederverwenden?" (beantwortet: Katalogteil schwab_v3 abgeschaltet nach Regel 21.11.; Kette misst selbst, Pfosten fehlten wegen 100-Punkte-Schwelle).
- Projektast „Bahn & Anlage" (Doku/projekt/bahn-anlage.md): Laser-Unterbau, erst N-Probemodul, dann H0 + CO2-Laser (1 Durchgang, möglichst Open Source).

## Erledigt und geprüft
- 1122w (01:45–06:48, 5 h): Süd-Quader, Steinzone, Eckquader, Südfenster; Fehlerliste im Logbuch. 3D-Artifact V6 https://claude.ai/artifact/ScV8KGvyjJrxxHCAzCM6pi
- Merge-Probe 25 (Schnelltest 0): tiefe_lokal-Hash, Krümel-Kantenbeleg, Bogen-Gewände, Ortsteine Mehrfoto.
- 1122x (07:28–10:13, 2 h 45, kein Kamera-Nachholen nötig): Gewände sichtbar, Krümel weg; Süd-Uhr fehlte. ANNAHME Süd ~50 %, Nord ~55 %. Bilder: scratchpad q/x_eigen__IMG_20261106_113830.jpg, x_…113231.jpg
- Merge-Probe 26 → main a9b1baefe (Schnelltest 0, 568 s), 10 Zweige: Südfenster-Gewände, Nachhol-Zwischenspeicher, West-Schlitze (schlitze_wandbild.py) + grobes Wandbild für Ortsteine, Malplan (tools/malplan.py, Weißabgleich), Vorbau Nord (3 Pfosten, offene Brüstung, 6 Konsolen), Süd-Teil über Wände gebunden (tools/seiten_waende_binden.py; war 10° gekippt), wolke_draehte.py (Anzeige, ~45 %), gemessene Bogenfugen, Uhr aus Einzelfotos, Bau parallel (421→274 s, STL bitgleich).
- MachineFrameWork nach /media/oem/rcdaten/ausgelagert_root/git/MachineFrameWork (Prüfsumme gleich, Symlink). Rest mit Root-Rechten: ~/git/MachineFrameWork.rest_rootrechte (96 KB, Nutzer kann `sudo rm -rf`).

## Läuft gerade
- Kette 1122y (Start 10:47, alle 10 Zweige) · Log /media/oem/scan/rc-park_daten/job_logs/kette-schwabentor-null-1122y.log · Prüfen: `grep -a "JOB_ENDE\|ERGEBNIS DES LAUFS" <log>` · ANNAHME Ende ~13:00 (länger, falls Süd-Bindung Teile neu anstößt).
- Einmal-Warter bqbhltbl6 auf JOB_ENDE (geht bei /clear verloren → nach Fortsetzen Log selbst prüfen).
- Keine Agenten aktiv.

## Nächste Schritte
1. Nach 1122y-Ende: `audit/seiten.jpg`, neben_*.jpg, `tools/py tools/modell_neben_foto.py modelle/schwabentor-1122/objekt.json eigen__IMG_20261106_113830 <aus.jpg>` (Süd) und …113231 (Nord), malplan_*.jpg ansehen. Prüfen: Vorbau-Pfosten/Brüstung, Südfenster-Gewände, Bogenfugen, Süd-Uhr, West-Schlitz, Süd-Lage (seiten_modelle meldet waende_stufe?), Laufzeit je Stufe.
2. Fehlerliste + Realitäts-% je Seite an Nutzer, Bilder per SendUserFile, 3D-Artifact mit gleicher URL neu (HTML /media/oem/scan/rc-park_daten/schwabentor-1122/schwabentor-1122_3d.html), Logbuchzeile, push.
3. Zweig worktree-agent-a62da684d0af546e8 (Drahtmasken je Foto, 840a50f05, Schnelltest 0) in Merge-Probe 27 → erzwingt Neufusion + stabil_alle neu (ANNAHME +1 h).
4. Neue Agenten je Befund aus 1122y (kette-schleife). Kandidaten: Ost-Seite 239 m² ohne Fotos löst kein Nachholen aus (nur „ganz ungesehen" zählt); Mono-Versatz 10–13 cm (evtl. Folge der 10°-Kippung – nach 1122y neu messen); Knaggenform/Zierbretter Vorbau; Ortsteine West oben links; Schnittbaum in aushoehlen.
5. SIFT-GPU-Messung (first_octave 0, 27 MPx) wenn GPU frei.

## Entscheidungen des Nutzers
- ✓ Verschieben MachineFrameWork + ~/.codex erlaubt. ~/.codex NICHT verschoben, weil Codex lief (sqlite aktiv) – nachholen, wenn Codex beendet.
- ✓ Bogenfugen: nur gemessene (Regel 15.11. bleibt: nichts generieren) – in PIPELINE_FASSADEN.md vermerkt.
- ? Löschen /media/oem/rcdaten/tmp/bau_parallel_agent (~1,1 GB) + /media/oem/rcdaten/tmp/tools_alt – nur nach „Ja".
- ? Löschen 88-MB-Ordner /media/oem/scan/rc-park_daten/_agent_ortsteine – nur nach „Ja".
- ? Nachkauf Farben: mattes Grün (Vordach), Ocker/Orange (Malplan-Hinweis).

## Fehler und Lehren dieser Sitzung
- Agenten-Worktrees bleiben nach Hand-back gesperrt: sauber+gemergt → `git worktree unlock`, dann `remove` (ohne --force). Im Logbuch.
- Malplan-Agent benannte Seiten erst falsch (eigene Kompassrechnung) – Seitennamen immer aus objekt.json seiten_konvention.
- Süd-Uhr hing verdeckt vom Teillauf ab (Mosaik-Naht) – Urteile nie von Mosaik-Zufall abhängig machen (jetzt Einzelfoto-Beleg).
- GPS-Lage des Süd-Teils war 10° gekippt bei gemeldeten ±1,4° – GPS-Lot aus wenigen Fotos ist kein Beleg (lage-seiten.md Versucht).
- `rm -rf` beim Auslagern scheiterte an root-eigenen Dateien → vorher `find ! -user $USER` prüfen.
- Schnelltest-Doku-Budget (≤ 110 Zeilen je Ast) beim Mergen vieler Versucht-Zeilen beachten.

## Wichtige Pfade und Befehle
- Logbuch: modelle/LOGBUCH_SCHWABENTOR_KETTE_2026-11-21.md (Zeilen 24.11.).
- Merge-Probe: Zweig merge-probe-N im Haupt-Checkout, Konflikte in schnelltest.sh/Doku: beide Seiten behalten (Marker-Zeilen löschen), dann `bash tools/schnelltest.sh`, `--ff-only` nach main, `python3 tools/baum_erzeugen.py`.
- Kettenstart: `JOB_RAM_MB=11000 JOB_GPU_MB=6000 tools/job_start.sh kette-schwabentor-null-<id> <log> /usr/bin/env RCPARK_LAGE_FRUEH=hinweis /media/oem/scan/venv-seg/bin/python -I tools/gesamtkette.py schwab_auto --ziel schwabentor-1122 --ab vorpruefen --dicht-stufe schnell`
- Malplan-Bilder: /media/oem/rcdaten/tmp/malplan_agent/wb_ende/

## Vorsicht
- Nur EIN Kettenlauf; Agenten rechnen nicht schwer während der Kette. Root ≥ 15 GB Ziel (jetzt ~9,6 GB, je Agent-Worktree 620 MB, hart 5 GB).
- Worktrees agent-ae5474668c0142117 (dirty) und agent-a1b159488c8983a24 (ungemergt) nicht anfassen.
- Fremde uncommittete Dateien (kaufhaus_grob3, martinstor*, ober_tvdr, schwab_nachbar, modelle/inhalt/PIPELINE_FASSADEN.md) nie committen. Toshiba nie anfassen. Löschen nur nach „Ja".
