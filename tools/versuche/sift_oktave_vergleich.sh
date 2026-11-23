#!/bin/bash
# SIFT volle Aufloesung: first_octave -1 (Bild verdoppelt, COLMAP-Standard) gegen 0 (nicht verdoppelt, passt auf 8-GB-GPU).
# CPU, damit die laufende Kette die GPU behaelt. Messgroesse: Merkmale je Bild, Paare mit >= 30 Inliern, Inlier-Median.
# Stichprobe: jedes 8. eigene Schwabentor-Foto vom 23.11. (Handy-Originale) + Eckliste der Suedbruecke.
# Aufruf: bash tools/versuche/sift_oktave_vergleich.sh <ausgabeordner> [threads]
set -e
A=${1:?ausgabe}; T=${2:-4}
Q=/media/oem/scan/rc-park_daten/schwab_auto/fotos; K=/media/oem/scan/rc-park_daten/schwabentor-1122/fotos
E=/media/oem/rcdaten/tmp/bruecke_sued_agent/eck/bilder.txt
C=/media/oem/scan/colmap-build/prefix/bin/colmap
export LD_LIBRARY_PATH=/media/oem/scan/cuda-toolkit-combo/lib64:/media/oem/scan/venv-seg/lib/python3.12/site-packages/nvidia/cu13/lib:/media/oem/scan/cudss-pkg/
rm -rf $A; mkdir -p $A/mix
ls $Q | grep -E "^eigen__IMG_20261123_15" | awk 'NR%8==1' > $A/neu.txt
for f in $(cat $A/neu.txt); do ln -sf $Q/$f $A/mix/$f; done
for f in $(cat $E); do ln -sf $K/$f $A/mix/$f; done
cat $A/neu.txt $E > $A/alle.txt
/media/oem/scan/venv-colmap/bin/python -I -c "
neu=[x.strip() for x in open('$A/neu.txt') if x.strip()]; alt=[x.strip() for x in open('$E') if x.strip()]
P=set()
for i,a in enumerate(neu):
    for b in alt+neu[i+1:]: P.add((a,b))
open('$A/paare.txt','w').write(''.join(f'{a} {b}\n' for a,b in sorted(P))); print(len(neu),'neu',len(alt),'eck',len(P),'Paare')"
for O in -1 0; do
  D=$A/okt$O.db; t0=$(date +%s)
  $C feature_extractor --database_path $D --image_path $A/mix --image_list_path $A/alle.txt --FeatureExtraction.use_gpu 0 \
     --FeatureExtraction.num_threads $T --FeatureExtraction.max_image_size -1 --SiftExtraction.first_octave $O > $A/fe$O.log 2>&1
  t1=$(date +%s)
  $C matches_importer --database_path $D --match_list_path $A/paare.txt --match_type pairs --FeatureMatching.use_gpu 0 \
     --FeatureMatching.num_threads $T > $A/mi$O.log 2>&1
  t2=$(date +%s)
  /media/oem/scan/venv-colmap/bin/python -I -c "
import sqlite3,statistics as S
c=sqlite3.connect('$D'); n=set(x.strip() for x in open('$A/neu.txt') if x.strip())
kp=dict(c.execute('select name,k.rows from images i join keypoints k on i.image_id=k.image_id'))
r=[x for (x,) in c.execute('select rows from two_view_geometries') if x>0]
print('first_octave $O: Bilder',len(kp),'fehlend',len(set(open('$A/alle.txt').read().split())-set(kp)),
 '| Merkmale neu Median',S.median([v for k,v in kp.items() if k in n]),'eck Median',S.median([v for k,v in kp.items() if k not in n]),
 '| Paare>=30 Inlier',sum(x>=30 for x in r),'>=100',sum(x>=100 for x in r),'Inlier-Median',S.median(r) if r else 0,
 '| SIFT $((t1-t0)) s, Matching $((t2-t1)) s')" | tee -a $A/ergebnis.txt
done
