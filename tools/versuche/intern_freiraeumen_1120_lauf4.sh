#!/bin/bash
# 20.11.2026: Volume/rc-park_auslagern (73 GB) blieb stehen, weil Verknuepfungen aus anderen Auslagerungsordnern der 2-TB-Platte noch hineinzeigen
# (Schlussdurchgang vom 18.11. fehlte). Erst umbiegen (nichts kopieren), dann geprueft entfernen.
cd /home/oem/git/rc-park
bash tools/umzug_auslagerung.sh /media/oem/Volume/rc-park_auslagern /media/oem/rcdaten/auslagern_Volume --nur_umbiegen 2>&1 | tail -5
RSYNC_EXTRA=--no-links bash tools/versuche/intern_freiraeumen_1120.sh /media/oem/Volume/rc-park_auslagern /media/oem/rcdaten/auslagern_Volume
