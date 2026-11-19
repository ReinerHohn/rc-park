#!/bin/bash
# Recherche-Punkt 1: globaler Mapper MIT Schwerkraft je Bild (tools/schwerkraft_je_bild.py, nach view_graph_calibrator) gegen die 6 Laeufe ohne (colmap_ab), Schwabentor db_orig
V=/media/oem/rcdaten/tmp/schwerkraft; DB=/media/oem/rcdaten/tmp/globmap/schwab/db_orig.db; IMG=/media/oem/scan/rc-park_daten/schwab_v3/fotos; PY="/media/oem/scan/venv-colmap/bin/python -I"
ALT=$(grep '^ALT_ENV' /media/oem/rcdaten/tmp/colmap_ab/ab.sh | cut -d'"' -f2); C=/media/oem/scan/colmap-build/prefix/bin/colmap
for n in schwer1 schwer2; do
  rm -rf $V/$n; mkdir -p $V/$n/sparse; python3 -c "import sqlite3,sys; s=sqlite3.connect(sys.argv[1]); d=sqlite3.connect(sys.argv[2]); s.backup(d)" $DB $V/$n/db.db
  t=$(date +%s); LD_LIBRARY_PATH=$ALT $C view_graph_calibrator --database_path $V/$n/db.db > $V/$n/kalib.log 2>&1
  (cd /tmp && $PY /home/oem/git/rc-park/tools/schwerkraft_je_bild.py --db $V/$n/db.db --bilder $IMG 2>&1 | grep SCHWERKRAFT)
  LD_LIBRARY_PATH=$ALT $C global_mapper --database_path $V/$n/db.db --image_path $IMG --output_path $V/$n/sparse --GlobalMapper.ra_use_gravity 1 > $V/$n/global.log 2>&1
  echo "ERGEBNIS $n rc $? Zeit $(( $(date +%s)-t )) s"
  for m in $V/$n/sparse/*/; do LD_LIBRARY_PATH=$ALT $C model_analyzer --path $m 2>&1 | grep -E 'Registered images|Points:|Mean reprojection' | sed 's/.*\] /  /' | tr '\n' ' '; echo; done
done
