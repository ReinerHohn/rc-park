#!/bin/bash
# Beleg Seitenfilter (20.11.): Martinstor-Konsens Stufe 2 mit fremde_seite-Liste neu, Ergebnis zerlegen + gegen Seitenmodelle bewerten
T=/media/oem/rcdaten/tmp/fremd_test; K=/media/oem/scan/rc-park_daten/martinstor_gk3/pipe/sfm/konsens_arbeit; PY="/media/oem/scan/venv-colmap/bin/python -I"
mkdir -p $T/konsens/0; cd /tmp
$PY - <<PYEOF
import sys, subprocess; sys.path.insert(0, "/home/oem/git/rc-park/tools"); from global_mapper_lauf import COLMAP_BIN, ENV
cmd = [COLMAP_BIN, "mapper", "--database_path", "$K/lauf1/db_kalib.db", "--image_path", "/media/oem/scan/rc-park_daten/martinstor_gk3/fotos", "--input_path", "$K/rueckgrat/0", "--output_path", "$T/konsens/0",
       "--Mapper.fix_existing_frames", "1", "--Mapper.ba_use_gpu", "1", "--Mapper.ba_max_num_images_direct_dense_gpu_solver", "0", "--Mapper.structure_less_registration_fallback", "0", "--Mapper.image_list_path", "$T/stufe2_bilder.txt"]
print("rc", subprocess.run(cmd, env=ENV, stdout=open("$T/stufe2.log", "w"), stderr=subprocess.STDOUT).returncode, flush=True)
PYEOF
$PY /home/oem/git/rc-park/tools/modell_zerlegen.py $T/konsens/0 --min-bilder 10 --aus $T/zerlegt | grep ZERLEGEN
$PY /media/oem/rcdaten/tmp/flexglue/bewerten.py $T/zerlegt 2>&1 | grep -E 'Nord [1-9]|Sued [1-9]' | head -3
