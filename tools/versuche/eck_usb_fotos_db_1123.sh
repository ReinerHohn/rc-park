#!/bin/bash
# Variante USB 23.11. 19 Uhr: ALLE eigenen Schwabentor-Fotos 15xx (Handy-Originale mit GPS) in DB-Kopie neu_usb, GPU.
set -e
B=/media/oem/rcdaten/tmp/bruecke_sued_agent; N=$B/neu_usb; Q=/media/oem/scan/rc-park_daten/schwab_auto/fotos; K=/media/oem/scan/rc-park_daten/schwabentor-1122/fotos
C=/media/oem/scan/colmap-build/prefix/bin/colmap
export LD_LIBRARY_PATH=/media/oem/scan/cuda-toolkit-combo/lib64:/media/oem/scan/venv-seg/lib/python3.12/site-packages/nvidia/cu13/lib:/media/oem/scan/cudss-pkg/py/nvidia/cu13/lib:/media/oem/scan/venv-colmap/lib/python3.12/site-packages/nvidia/curand/lib
rm -rf $N; mkdir -p $N/mix
/media/oem/scan/venv-colmap/bin/python -I -c "
import sqlite3;s=sqlite3.connect('file:$B/db.db?mode=ro',uri=True);d=sqlite3.connect('$N/db.db');s.backup(d);d.close()"
ls $Q | grep -E "^eigen__IMG_20261123_15" > $N/neu.txt
for f in $(cat $N/neu.txt); do ln -sf $Q/$f $N/mix/$f; done
for f in $(cat $B/eck/bilder.txt); do ln -sf $K/$f $N/mix/$f; done
$C feature_extractor --database_path $N/db.db --image_path $N/mix --image_list_path $N/neu.txt --FeatureExtraction.use_gpu 1 --FeatureExtraction.num_threads 4 --FeatureExtraction.max_image_size 2400 > $N/fe.log 2>&1
/media/oem/scan/venv-colmap/bin/python -I -c "
neu=[x.strip() for x in open('$N/neu.txt') if x.strip()]; alt=[x.strip() for x in open('$B/eck/bilder.txt') if x.strip()]
P=set()
for i,a in enumerate(neu):
    for b in alt+neu[i+1:]: P.add((a,b))
open('$N/paare.txt','w').write(''.join(f'{a} {b}\n' for a,b in sorted(P))); print(len(P),'Paare')"
$C matches_importer --database_path $N/db.db --match_list_path $N/paare.txt --match_type pairs --FeatureMatching.use_gpu 1 --FeatureMatching.num_threads 12 > $N/mi.log 2>&1
echo fertig
