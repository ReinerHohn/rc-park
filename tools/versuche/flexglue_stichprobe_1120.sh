#!/bin/bash
# Stufe-2-Stichprobe (4000 zufaellige SIFT-abgewiesene Paare): wie viele bestaetigt FlexGlue NEU, und wie viele davon liegen in der Bildsuche top-150?
Z=/media/oem/rcdaten/tmp/flexglue
python3 -c "import sqlite3,sys; s=sqlite3.connect(sys.argv[1]); d=sqlite3.connect(sys.argv[2]); s.backup(d); d.execute('delete from matches'); d.execute('delete from two_view_geometries'); d.commit()" $Z/k6000.db $Z/stich.db
t=$(date +%s); for i in 1 2 3 4 5 6; do bash $Z/lauf.sh $Z/stufe2_stichprobe.txt $Z/stich.db 0.5 > /dev/null 2>&1 && break; done; echo "STICHPROBE Zeit $(( $(date +%s)-t )) s"
/media/oem/scan/venv-seg/bin/python -I $Z/stich_auswerten.py
