# Übergabe 28.11.2026 15:50 (löst die von 13:55 ab)
Weiter mit: „weiter" (oder /uebergabe fortsetzen). Vorher Skill `sitzungsbeginn`. Anrede „mein grosser Meister", Deutsch, keine breiten Tabellen. Nutzer schläft ab ~15:45 und will beim Aufwachen Ergebnisse + Bilder sehen („ich will einfach Ergebnisse sehen, wo wir gerade sind"). Autonom weiterarbeiten (Nutzer 28.11.: „Arbeite ab jetzt autonom weiter").

## Auftrag
- Ziel: Schwabentor-TURM (Brücke später) aus Fotos in der KOMPLETTEN Kette zu einem sehr guten Modell (druckbar 1:87). Nutzer 28.11.: „uns erstmal auf den Turm konzentrieren". „geh alles an, geh Adaptionen an … Du darfst alles überlegen, entscheiden." Lizenz beim Testen egal. Pods erlaubt (Kostenrahmen Pod-Agent bis ca. 10 $ zusätzlich, Reserve 5 $).
- Nie Zeiten ohne Messung versprechen (ANNAHME kennzeichnen). Bei jeder Meldung Zahlen + wenn vorhanden Bild.

## Erledigt (28.11. Nachmittag)
- Befund: registrierte Handyfotos (327 vom 26.11. + 72 vom 28.11.) gingen NUR in die dichte Wolke, nie in Kantenstufe/Foto-Tor/Wandbild/F1. Fix gemergt + gepusht (main 0ba2ae47e): `tools/ausrichtung_zusatz.py` (903 → 1302 Kameras, Rahmen-Tor), `tools/kameras_zusatz.py` (Kettenschritt `k_zusatz`, 393 K-Dateien geschrieben, 6 verworfen: 11–19 m unter Gelände, alle 26.11.), `gesamtkette.kanten_mit_zusatz`. Schnelltest 0 Fehler (332 s). `modelle/schwabentor-1122/objekt.json` (UNVERSIONIERT, nur im Hauptordner) hat jetzt `zusatzfotos` = beide `lg`-Ordner (Sicherung: Scratchpad `objekt_schwabentor_vor_zusatz.json`).
- Messung Kameraauswahl der Kantenstufe (max 80, Rang Sichtanteil/√Abstand, je 30°-Sektor): gewählt 23 vom 26.11., 0 vom 28.11. (57 von 72 zugelassen, Median-Abstand 44,7 m gegen 28,7 m der gewählten, bestes Foto Platz 9 bei 6–7 Plätzen je Sektor). OFFEN: Variante mit Kontingent für Zusatzfotos messen.
- Erkenntnis „Nutzungsbilanz": Branch `erkenntnis-nutzung` (Worktree `.claude/worktrees/erkenntnis-nutzung`, 3 Commits bis d7b1aa626, NICHT in main): `tools/foto_nutzung_bilanz.py` + Kettenschritt `foto_nutzung` (nach Kantenstufe, rc 3 wenn registrierte Zusatzfotos die Kantenstufe nicht erreichen) + `tools/test_foto_nutzung_bilanz.py` (Gegenprobe rot ohne Kettenschritt) + Register-Eintrag `modelle/ERKENNTNISSE.md` + Baumzeile + Memory `feedback-erfolgsmass-nutzung-statt-einordnung`. Volle Schnelltest-Prüfung dieses Zweigs steht AUS (RAM wegen laufender Kette), danach Merge nach main (git -C /home/oem/git/rc-park merge erkenntnis-nutzung; bei Überschneidung mit erzeugten Dateien modelle/INDEX.md, modelle/inhalt/*.md: Kopie sichern, `git checkout --` der 3 Dateien, Merge, `python3 tools/baum_erzeugen.py`, vergleichen — so beim letzten Merge gemacht).
- Laufzeitmessung 1128a–d (164 min): nur ~2 % GPU, Rest CPU einfädig; Top: bauen_abnehmen.sh 28,9 min in 12 Bauten, bestand_tor 14,6, fassaden_kette 11,7, konvergenz 11,5, wolke_vereinigen 9,7, ebenen_bauplan 8,5, oeffnungen_wandbild 7,6. Einfaden-Test (20 Mio Schleifen): lokal P-Kern 0,67–0,85 s, 5090-Pod (Ryzen 9 9950X) 1,00 s, 4090-Pod (EPYC 7352) 3,11 s ⇒ GPU-Pods bringen für die Kette fast nichts; „5090 2× schneller" (frühere Meldung) beruhte auf UNVOLLSTÄNDIGEN Pod-Läufen (~36 von 96 Stufen; OpenMVS + HF-Modelle fehlten) und ist vorläufig/nicht belegt.
- LIMAP-Test (Agent a0d533bbe3d553620, beendet, Zweig `worktree-agent-a0d533bbe3d553620`, nichts in main): Gesims f01 mit GlueStick K_L 7,0 m gegen Sweep 7,5 m (eine lange Linie, Wiederholbarkeit NICHT geprüft); senkrechte Eckquader: Sweep klar besser. Empfehlung: nicht einbauen, nach Turmlauf weitermessen. Der Agent startet nichts neu, bis ich das Ende des Turmlaufs melde (SendMessage an a0d533bbe3d553620).
- Kühlung/CPU: E-Kern-Bindung (taskset 16–27) der LIMAP-Tests aufgehoben (Regel 27.11. keine dauerhafte E-Kern-Bindung); Platzwächter ist noch auf 16–27 gebunden (leicht).

## Läuft gerade
- TURM-KETTENLAUF `rcpark-kette-schwabentor-main-1128e` (Start 15:11, `gesamtkette.py schwab_auto --ziel schwabentor-1122 --ab kanten --dicht-stufe schnell`, aus main-Checkout /home/oem/git/rc-park, Buchung 7 GB RAM/6 GB GPU), Log `/media/oem/scan/rc-park_daten/job_logs/kette-schwabentor-main-1128e.log`. Stand 15:38: Stufe fassaden_kette (seit 15:20), 0 Tracebacks. Warter (Hintergrund, endet bei JOB_ENDE/Traceback/45 min Stillstand). Kantenstufe hatte 1302 Kameras, F1 0,239 (Präzision 0,151, Recall 0,567) – kanten_fertig des früheren Laufs: F1 0,243; erst `kanten_bericht_fertig.json` NACH diesem Lauf ist vergleichbar. In main wird während der Kette NICHTS an tools/ geändert (nur Worktrees).
- Agent a04009bb382a4adf2 (Worktree, Phase 1 nur Code): Abhängigkeitsgraph der Kettenstufen, Doppelbauten (12 Bauten), `stufen_parallel.py` erweitern, Tests; Phase 2 (Messlauf per `tools/ketten_probelauf.sh`, Bitgleichheit) erst auf meine Meldung, wenn Maschine frei.
- Pod-Agent aeb8e9aa07b304032: 5090-Pod `8ow3sznnllhmwa` (1,39 $/h, EU-RO-1, Volume ghhv7k1089); 4090-Pods gelöscht; Paket extra3.tar (OpenMVS, HF-Modelle) hochgeladen → vollständiger 5090-Lauf ab tore mit Stufenzahl-Prüfung (Vollständigkeit gegen 96 lokale Stufen); CPU-Pod-Probe cpu5c (~1,1 $/h, 3 min) autorisiert; Handoff-Konzept CPU-Pod → Volume → GPU-Pod nur Konzept+Messung. Bitgleichheit grund gegen par auf Pod nacheinander. Guthaben zuletzt 40,36 $, ≥ 5 $ Reserve.
- Dauerdienste (nicht melden): editordraht, platz_waechter, *-gpuwache.

## Nächste Schritte (Nacht, in dieser Reihenfolge)
1. Nach Ende von 1128e (Warter meldet): Bestand-Vergleich ZUERST: `modelle/schwabentor-1122/audit/neben_*.jpg` + `seiten.jpg` neben `modelle/schwabentor-1122/bestand/` (Bestbild `seiten__2026-11-24_0750.jpg`, `neben_details__…`), BEIDE per SendUserFile, dann Zahlen (kanten_bericht_fertig F1, Foto-Tor, bestand_tor, `audit/foto_nutzung.json` falls Schritt schon in main; Tracebacks, OOM `journalctl -k | grep -ci oom`). Rückschritt ⇒ NICHT mergen, Ursache-Agent.
2. Danach `bash tools/schnelltest.sh` im Worktree `erkenntnis-nutzung` (6 min, Maschine frei), bei 0 Fehlern mergen + pushen (siehe oben).
3. LIMAP-Agent und Parallelisierungs-Agent: Phase 2 freigeben, wenn kein Kettenlauf läuft.
4. Kameraauswahl-Variante messen (Kontingent für Zusatzfotos/Nahaufnahmen, `kantenstufe.waehlen`), Ergebnis am Bild vergleichen; STL: lose Teile (14 + 12 Dreiecke) im Bauschritt entfernen, Höhe 53,2 m vs DOM1-Max 49,6 m aus Fotokanten gegenprüfen.
5. Fotos fehlen: Nordwand frontal + Durchfahrt innen (Nutzer evtl. vor Ort); Treppe 0/21 und Stegdach 5/14 nicht eingeordnet (Teilmodell `tools/handy_teilmodell.py`), Brücke erst nach Turm (Stufe-B-Job `rcpark-hybrid1128` auf Nutzerwunsch beendet; Ergebnis A in `/media/oem/rcdaten/rc-park_daten_neu/zusatz_20261128_hybrid/`).

## Entscheidungen des Nutzers
- ✓ Turm zuerst. ✓ Pods erlaubt, CPU-/GPU-Aufteilung prüfen, ich darf entscheiden. ✓ Lizenz egal beim Testen. ✓ LIMAP-Tests beenden für den Turm-Kettenlauf. ✓ 5090-Probe/Upload ok.
- ? Löschen der Kopien `/media/oem/rcdaten/tmp/handy_alle_original/`, `handy_schwabentor_original/` nur nach „Ja".

## Fehler und Lehren dieser Sitzung
- Ich habe „5090 ~2× schneller" und „Pod-Lauf läuft" gemeldet, bevor die Stufenzahl geprüft war (Pod-Läufe waren unvollständig). Immer Stufenzahl/Vollständigkeit melden.
- `kette_integ` (/media/oem/scan/rc-park_tmp/kette_integ) hat ~1048 uncommittete Dateien (u. a. 22 tools-Dateien, +1334 Zeilen gegen seinen HEAD) und ist auf 26352da88 detached; NICHT angefasst; Turm-Kette läuft stattdessen aus dem main-Checkout (modelle/schwabentor-1122 dort ist ein Symlink auf main).
- Unversionierte Dateien (objekt.json, schwabentor-1122_gen.py) fehlen in Worktrees/Pods – hat Pod-Agent 2× aufgehalten.
- Schnelltest-Fehler „Werkzeugkopf ohne Verwandt/Vorlaeufer" bei JEDEM neuen Werkzeug: Kopfzeile `Verwandt:`/`Vorlaeufer:` von Anfang an setzen (`python3 -I tools/werkzeug_aehnlich.py --wie tools/<x>.py`, `--kopf-pruefen`).

## Wichtige Pfade und Befehle
- Kette starten (Beispiel, gebucht): `JOB_RAM_MB=7000 JOB_GPU_MB=6000 bash tools/job_start.sh kette-schwabentor-main-1128f <log> env PYTHONUNBUFFERED=1 RCPARK_BESTAND_EINZELN=1 /media/oem/scan/venv-seg/bin/python -I tools/gesamtkette.py schwab_auto --ziel schwabentor-1122 --ab kanten --dicht-stufe schnell` (aus /home/oem/git/rc-park). Laufzeitbericht: `python3 -I tools/laufzeit_bericht.py <log>`.
- Pod-Daten: `/media/oem/rcdaten/tmp/runpod_test/kette_pod/`. rclone: `. ~/.runpod/rclone_env.sh; ~/.local/bin/rclone size rp:ghhv7k1089/rc_kette`.
- Messskripte (Scratchpad): `sicht_zusatz.py` (Kamera-Rang), `lz_*.json` (Laufzeiten).

## Vorsicht
- Nur EIN lokaler Kettenlauf; keine Rechenjobs der Agenten während der Kette. Kein wiederkehrender Cron/Loop für Job-Checks (nur Warter mit Ende+Timeout).
- Nichts löschen ohne „Ja"; Worktrees nie `--force`; Root-Platte ~8 GB frei, Daten-Platte /media/oem/scan ~20 GB frei (Grenze 15 GB, Notgrenze 2 GB).
- Pods: Preis vor Anlegen nennen, nach Lauf löschen und per `list-pods` prüfen; Zugangsdaten nur in `~/.runpod/`.
