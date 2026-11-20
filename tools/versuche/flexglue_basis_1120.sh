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
# Basislauf (20.11. 02:30): reiner SIFT-Lauf auf GENAU der Datenbank, aus der tuersteher.db entstand -> fairer Vergleich; danach alle Varianten zerlegt (tools/modell_zerlegen.py) bewerten
S=/media/oem/scan/rc-park_daten/martinstor_gk3/pipe/sfm/db.db
echo "== BASIS $(date +%T)"; mapper var_sift $S
for n in var_sift var_tuersteher var_flexglue var_vereint; do [ -d $Z/$n/sparse/0 ] || continue; echo "== ZERLEGT $n"
  (cd /tmp && $PY /home/oem/git/rc-park/tools/modell_zerlegen.py $Z/$n/sparse/0 --aus $Z/$n/zerlegt 2>&1 | grep ZERLEGEN; $PY $Z/bewerten.py $Z/$n/zerlegt 2>&1 | grep -E 'Nord [1-9]|Sued [1-9]' | head -4); done
