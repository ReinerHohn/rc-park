#!/bin/bash
# 20.11.2026 (Nutzer: "nachher den Lauf nicht stoppen, lass durchlaufen"): einmaliger Warter - sobald die Martinstor-Kette 1120b endet (gleich mit welchem rc,
# Auswertung macht die Sitzung), startet die Schwabentor-Kette von null unter neuem Zielnamen. Kein Zeitplan, laeuft genau einmal.
cd /home/oem/git/rc-park
while systemctl --user is-active -q rcpark-kette-martinstor-1120b.service; do sleep 60; done
grep JOB_ENDE /media/oem/scan/rc-park_daten/job_logs/kette-martinstor-1120b.log
JOB_RAM_MB=11000 JOB_CPU=alle bash tools/job_start.sh kette-schwabentor-1120 /media/oem/scan/rc-park_daten/job_logs/kette-schwabentor-1120.log \
  /media/oem/scan/venv-seg/bin/python -u -I tools/gesamtkette.py schwab_auto --ziel schwabentor-1120 --ab anlegen --dicht-stufe schnell
