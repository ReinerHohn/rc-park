#!/bin/bash
# einmaliger Warter: Martinstor-FlexGlue-Stufe 2 nach dem Kettenlauf von null fortsetzen (setzt dort fort, wo sie war)
L=/media/oem/scan/rc-park_daten/job_logs
until grep -q JOB_ENDE $L/kette-martinstor-1120.log 2>/dev/null; do sleep 120; done
cd /home/oem/git/rc-park && JOB_GPU_MB=4000 JOB_RAM_MB=3000 bash tools/job_start.sh flexglue-stufe2 $L/flexglue-stufe2c.log bash /media/oem/rcdaten/tmp/flexglue/stufe2.sh
