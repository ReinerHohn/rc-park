#!/bin/bash
# 20.11.2026: Archivordner nochmal, die im ersten Lauf (alter Skriptstand ohne Filter) faelschlich ABWEICHUNG meldeten. Schon Entferntes wird als "FEHLT Quelle" uebersprungen.
cd /home/oem/git/rc-park
while systemctl --user is-active -q rcpark-intern_frei.service || systemctl --user is-active -q rcpark-intern_frei_scan.service || systemctl --user is-active -q rcpark-intern_frei2.service; do sleep 60; done
V=/media/oem/Volume; R=/media/oem/rcdaten/auslagern_Volume_archiv
bash tools/versuche/intern_freiraeumen_1120.sh $V/rc-park_archiv_2026-11-06 $R/rc-park_archiv_2026-11-06 $V/rc-park_archiv_2026-11-05 $R/rc-park_archiv_2026-11-05
