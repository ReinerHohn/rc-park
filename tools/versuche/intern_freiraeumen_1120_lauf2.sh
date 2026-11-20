#!/bin/bash
# 20.11.2026: Paar 1 nochmal - erster Lauf meldete faelschlich ABWEICHUNG (rsync-Hinweis "skipping non-regular file" fuer Verknuepfungen zaehlte als Unterschied; Filter ergaenzt).
cd /home/oem/git/rc-park
while systemctl --user is-active -q rcpark-intern_frei.service || systemctl --user is-active -q rcpark-intern_frei_scan.service; do sleep 60; done
RSYNC_EXTRA=--no-links bash tools/versuche/intern_freiraeumen_1120.sh /media/oem/Volume/rc-park_auslagern /media/oem/rcdaten/auslagern_Volume
