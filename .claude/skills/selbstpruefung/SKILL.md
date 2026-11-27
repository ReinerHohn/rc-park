---
name: selbstpruefung
description: Vor jedem Langlauf/Nachtkette, vor jedem Ergebnisbericht und bevor der Nutzer weggeschickt wird - die Fehler, die der Nutzer am 27.11.2026 immer wieder korrigieren musste (nicht nachgemessen, Befehl kopiert, Befund ohne Schwelle, Bild falsch gelesen, Nacht verloren). Kurze Pflicht-Checkliste.
---
Nutzer 27.11.: "was wir jetzt immer wieder von dir fordern". Jede Zeile hat einen belegten Vorfall. Abkuerzen = Rueckfall.

**A. Vor jedem Langlauf / jeder Kette (Skill langer-job Punkt 6 gilt zusaetzlich)**
1. Stufe mit Mini-Eingabe durchlaufen (Dummy), nicht nur `bash -n`. Vorfall: Undistort-Abbruch um 00:03, 8 h GPU leer.
2. Befehle aus frueheren Laeufen nie blind kopieren: Kernbindung, RAM-/VRAM-Buchung, Pfade, Bildgroessen neu pruefen. Vorfall: `taskset -c 16-27` = nur E-Kerne.
3. Nach dem Start messen: `taskset -acp <PID>`, `vmstat 2 3` (sy% > 30 = Speicherdruck), `nvidia-smi`, `free -g`. Alle 28 Kerne/GPU nutzen, Auslastung melden. Hardware: P-Kerne 0-15, E-Kerne 16-27, VRAM 8 GB, RAM 15 GB.
4. Einmaligen Pruef-Termin 5-15 min nach dem ersten Stufenwechsel setzen (CronCreate einmalig) + Abbruch melden. Nie "geh ins Bett", solange 1-4 fehlen.
5. Warteschleifen mit Zeitlimit, Rueckgabewerte nie durch `| tail` verlieren, laufende Skripte nie in-place ueberschreiben (neu schreiben + mv).

**B. Vor jedem Ergebnis / Bild / Zahl**
1. Selbst ansehen (Bild lesen), dann behaupten. Achsen und Rahmen pruefen: SfM-Rahmen hat "oben" = -y, Modellmeter z oben. Vorfall: "30 Grad geneigt" war Darstellungsfehler. Befund nie ohne unabhaengigen Gegenbeleg (Lot, DOM1, LoD2, GPS).
2. Ein Status ohne Schwelle ist kein Urteil: "ausgerichtet"/"belegt"/"PASST" nur mit Zahl + Grenze + roter Gegenprobe.
3. Gemessen von vermutet trennen (ANNAHME/ungeprueft); Zahlen mit Quelle; Fehlerliste vor Lob; keine Zahlen aus altem Satz auf neuen uebertragen (97/241 vs 327/677).
4. Eigene Falschaussage sofort benennen und korrigieren (auch auf Artifacts/Docs), nicht still ersetzen.
5. Ergebnis zeigen: Bild per SendUserFile, 3D-HTML als Artifact (Memory immer-3d-html-zeigen).

**C. Arbeitsweise**
1. Nie idle: wartet eine Rechnung, laeuft nuetzliche Arbeit (Agent im Worktree auf /media/oem/scan, nicht Root; Brief mit Regeln, Daten, was ausgeschlossen ist).
2. Abgebrochene Nutzernachrichten ("Und", "ist der") = Stand melden, nicht raten, einmal kurz nachfragen.
3. Teure/aussenwirksame Schritte (Cloud mieten, Drucken, Push von Agentenzweigen): Nutzer-Zustimmung + Obergrenze; Schluessel/Zahlungsdaten nie annehmen.
4. Lehre sofort festhalten: Memory (feedback-*) + Test, der den Fehler kuenftig rot meldet (Beispiel tools/test_keine_ekernbindung.py).
Memory-Verweise: feedback-nachtkette-dummy-und-pruefTermin, feedback-keine-ekern-bindung-hardware-pruefen, feedback-verbesserung-messen-nicht-doku, feedback-fehlerliste-vor-lob.
