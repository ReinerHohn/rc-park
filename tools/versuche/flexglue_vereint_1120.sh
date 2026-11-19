#!/bin/bash
# Variante VEREINT (SIFT ∪ FlexGlue je Paar, von FlexGlue abgewiesene Paare raus), nach der Nachtkette (alle FlexGlue-Paare Stufe 1+2)
Z=/media/oem/rcdaten/tmp/flexglue; PY="/media/oem/scan/venv-colmap/bin/python -I"
ALT=$(grep '^ALT_ENV' /media/oem/rcdaten/tmp/colmap_ab/ab.sh | cut -d'"' -f2); C=/media/oem/scan/colmap-build/prefix/bin/colmap
mapper() { n=$1 db=$2; rm -rf $Z/$n; mkdir -p $Z/$n/sparse; cp $db $Z/$n/db.db; t=$(date +%s)
  LD_LIBRARY_PATH=$ALT $C view_graph_calibrator --database_path $Z/$n/db.db > $Z/$n/kalib.log 2>&1
  LD_LIBRARY_PATH=$ALT $C global_mapper --database_path $Z/$n/db.db --image_path /media/oem/scan/rc-park_daten/martinstor_gk3/fotos --output_path $Z/$n/sparse > $Z/$n/global.log 2>&1
  echo "ERGEBNIS $n rc $? Zeit $(( $(date +%s)-t )) s"
  for m in $Z/$n/sparse/*/; do LD_LIBRARY_PATH=$ALT $C model_analyzer --path $m 2>&1 | grep -E 'Registered images|Points:|Mean reprojection' | sed 's/.*\] /  /' | tr '\n' ' '; echo " <- $m"; done
  (cd /tmp && $PY $Z/bewerten.py $Z/$n/sparse 2>&1 | grep -v '^I2026' | head -6); }
echo "== VEREINIGEN $(date +%T)"; (cd /tmp && $PY $Z/vereinigen.py $Z/k6000.db /media/oem/scan/rc-park_daten/martinstor_gk3/pipe/sfm/db.db $Z/vereint.db)
LD_LIBRARY_PATH=$ALT $C geometric_verifier --database_path $Z/vereint.db > $Z/vereint_verif.log 2>&1; echo "Pruefung rc $?"
mapper var_vereint $Z/vereint.db; echo "== FERTIG $(date +%T)"
