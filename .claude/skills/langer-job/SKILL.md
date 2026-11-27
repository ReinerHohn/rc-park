---
name: langer-job
description: Jeden Rechenjob laenger als ein paar Minuten (SfM, Kette, dichte Wolke, Fusion, Optimierer, Downloads) richtig starten und ueberwachen - systemd per tools/job_start.sh mit RAM/GPU-Buchung.
---
1. Vorher: Platz (`df -h /media/oem/scan /media/oem/rcdaten`), Ausgabe auf rcdaten wenn gross; Funktionsaufruf mit Mini-Eingabe testen (z.B. `--paare-max 20`).
2. Start: `JOB_GPU_MB=<MiB> JOB_RAM_MB=<MiB> bash tools/job_start.sh NAME /media/oem/scan/rc-park_daten/job_logs/NAME.log BEFEHL...` (grosse Jobs RAM 11000; VRAM-Summe aller Jobs <= 7000; nie `run_in_background` fuer Rechenjobs).
3. Warten: EINMALIGE Schleife `timeout 590 bash -c "until grep -q JOB_ENDE LOG; do sleep 30; done"` bzw. einmaliger Warter-Skript fuer Folgejobs. KEIN Cron/Loop/wiederkehrende Wache.
4. Ende: `grep JOB_ENDE LOG` (rc), Fehler sofort beheben und neu starten - nie liegen lassen, nachts weiterarbeiten.
5. Stoppen: `systemctl --user stop rcpark-NAME.service`; Prozesse per `ps`+PID, nie `pkill -f` mit eigenem Befehlsmuster.
6. **Nachtlauf / Kette aus mehreren Stufen (Lehre 27.11.2026: eine Stufe fiel um 00:03 aus, Fehler erst um 08:04 bemerkt, ~8 h GPU verloren):**
   a. Jede neue Stufe VOR dem Einreihen mit Mini-Eingabe durchlaufen (Dummy): Bildgroessen/Kameras, Pfade, Rueckgabewert pruefen. Nie nur Syntax (`bash -n`).
   b. Stufenskript: je Stufe Beginn/Ende/rc ins Protokoll, bei rc != 0 Abbruch mit Grund, Rueckgabewert nie durch `| tail` verlieren (Ausgabe in Datei), jede Warteschleife mit Zeitlimit.
   c. Einmaligen Pruef-Termin 5-15 min nach dem ersten Stufenwechsel setzen (einmalig, kein wiederkehrender Check) und Abbruch an den Nutzer melden (Push).
   d. Dem Nutzer nicht "geh ins Bett" sagen, solange a-c fehlen. Memory: feedback-nachtkette-dummy-und-pruefTermin.

