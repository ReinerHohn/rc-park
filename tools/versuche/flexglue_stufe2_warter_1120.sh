#!/bin/bash
# einmaliger Warter: Martinstor-Stufe 2 (~20 h) erst nach PatchMatch-A/B und dichten Wolken (fg-dicht) fortsetzen
L=/media/oem/scan/rc-park_daten/job_logs
until grep -q JOB_ENDE $L/fg-dicht.log 2>/dev/null; do sleep 60; done
cd /home/oem/git/rc-park && JOB_GPU_MB=4000 JOB_RAM_MB=3000 bash tools/job_start.sh flexglue-stufe2 $L/flexglue-stufe2b.log bash /media/oem/rcdaten/tmp/flexglue/stufe2.sh
