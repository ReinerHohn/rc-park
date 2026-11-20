#!/bin/bash
# 20.11.2026: nach dem Volume-Lauf (gleiche USB-Platte, nicht parallel) den alten Martinstor-Lauf martinstor_gk3/pipe (25 GB, Stand 19.11., abgeloest durch martinstor-1120)
# von der internen scan-Partition auf die 2-TB-SSD auslagern (Verknuepfung bleibt, Pfade gelten weiter). Einmaliger Warter, kein Zeitplan.
cd /home/oem/git/rc-park
while systemctl --user is-active -q rcpark-intern_frei.service; do sleep 60; done
AUSLAGERN_MOUNT=/media/oem/rcdaten AUSLAGERN_UUID=c5601887-391a-4272-9dca-a25e4ae68be7 ionice -c3 nice bash tools/auslagern.sh /media/oem/scan/rc-park_daten/martinstor_gk3/pipe
