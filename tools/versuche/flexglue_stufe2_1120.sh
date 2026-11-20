#!/bin/bash
# Nachtkette FlexGlue-Vergleich Martinstor (Nutzer 19.11.2026 23:20): Stufe 1 (SIFT-bestaetigte Paare) -> Tuersteher + FlexGlue -> je globaler Mapper -> Bewertung;
# danach Stufe 2 (von SIFT abgewiesene Paare, nur dort kann FlexGlue NEUE Paare finden) -> FlexGlue voll -> Mapper -> Bewertung
Z=/media/oem/rcdaten/tmp/flexglue; PY="/media/oem/scan/venv-colmap/bin/python -I"
ALT=$(grep '^ALT_ENV' /media/oem/rcdaten/tmp/colmap_ab/ab.sh | cut -d'"' -f2); C=/media/oem/scan/colmap-build/prefix/bin/colmap
mapper() { n=$1 db=$2; rm -rf "${Z:?}/${n:?}"; mkdir -p $Z/$n/sparse; cp $db $Z/$n/db.db; t=$(date +%s)
  LD_LIBRARY_PATH=$ALT $C view_graph_calibrator --database_path $Z/$n/db.db > $Z/$n/kalib.log 2>&1
  LD_LIBRARY_PATH=$ALT $C global_mapper --database_path $Z/$n/db.db --image_path /media/oem/scan/rc-park_daten/martinstor_gk3/fotos --output_path $Z/$n/sparse > $Z/$n/global.log 2>&1
  echo "ERGEBNIS $n rc $? Zeit $(( $(date +%s)-t )) s"
  for m in $Z/$n/sparse/*/; do LD_LIBRARY_PATH=$ALT $C model_analyzer --path $m 2>&1 | grep -E 'Registered images|Points:|Mean reprojection' | sed 's/.*\] /  /' | tr '\n' ' '; echo " <- $m"; done
  (cd /tmp && $PY $Z/bewerten.py $Z/$n/sparse 2>&1 | grep -v '^I2026' | head -6); }
# Stufe 2 voll (20.11. 03:30, nach Stichprobe 24 % neue Paare): setzt fort (importer ueberspringt Erledigtes), dann Mapper + Zerlegen + Bewerten
echo "== STUFE 2 $(date +%T)"; bash $Z/nochmal.sh $Z/stufe2.txt $Z/k6000.db 0.5 2>&1 | grep -E 'ERGEBNIS|ANLAUF'
cp $Z/k6000.db $Z/flexglue_voll.db; mapper var_flexglue_voll $Z/flexglue_voll.db
(cd /tmp && $PY /home/oem/git/rc-park/tools/modell_zerlegen.py $Z/var_flexglue_voll/sparse/0 --aus $Z/var_flexglue_voll/zerlegt 2>&1 | grep ZERLEGEN; $PY $Z/bewerten.py $Z/var_flexglue_voll/zerlegt 2>&1 | grep -E 'Nord [1-9]|Sued [1-9]' | head -4)
echo "== FERTIG $(date +%T)"
