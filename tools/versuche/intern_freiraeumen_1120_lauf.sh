#!/bin/bash
# Lauf 20.11.2026: Volume (interne NVMe, NTFS) von Altarchiven befreien. Paar 1 ist schon am 18.11. kopiert (Links im Ziel umgebogen -> --no-links).
cd /home/oem/git/rc-park
RSYNC_EXTRA=--no-links bash tools/versuche/intern_freiraeumen_1120.sh /media/oem/Volume/rc-park_auslagern /media/oem/rcdaten/auslagern_Volume; a=$?
bash tools/versuche/intern_freiraeumen_1120.sh /media/oem/Volume/scan_archiv /media/oem/rcdaten/auslagern_Volume_archiv/scan_archiv /media/oem/Volume/rc-park_archiv_2026-11-06 /media/oem/rcdaten/auslagern_Volume_archiv/rc-park_archiv_2026-11-06 /media/oem/Volume/rc-park_archiv_2026-11-05 /media/oem/rcdaten/auslagern_Volume_archiv/rc-park_archiv_2026-11-05; b=$?
exit $((a+b))
