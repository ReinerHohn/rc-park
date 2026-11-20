#!/bin/bash
# Dichte Wolken der FlexGlue-Seitenstuecke (Martinstor 20.11.) fuer seiten_vereinen (Achse aus Helmstange), dann vereinen + Abgleich mit vereinen3
Z=/media/oem/rcdaten/tmp/flexglue/var_flexglue/zerlegt; D=/media/oem/rcdaten/tmp/fg_dicht; PY="/media/oem/scan/venv-colmap/bin/python -I"; F=/media/oem/scan/rc-park_daten/martinstor_gk3/fotos
cd /tmp
for k in 1 0; do echo "== DICHT $k $(date +%T)"; $PY /home/oem/git/rc-park/tools/dicht_modell.py $Z/$k $F $D/s$k 2>&1 | grep -E 'FERTIG|Bildwahl|fused|Fehler|Traceback' | tail -4; done
echo "== VEREINEN $(date +%T)"; $PY /home/oem/git/rc-park/tools/seiten_vereinen.py $Z/0 $Z/1 /media/oem/scan/rc-park_daten/martinstor_gk3/pipe/sfm/db.db --aus $D/vereinen --dicht-a $D/s0/fused.ply --dicht-b $D/s1/fused.ply 2>&1 | grep -v '^I2026' | tail -6
