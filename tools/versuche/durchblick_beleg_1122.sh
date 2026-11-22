#!/bin/bash
# durchblick_beleg_1122.sh - BELEG fuer die Stufe Durchblick/Umgebung (tools/seiten_erkennen.py --durchblick) an schwabentor-1122 (22.11.2026).
# Nur Kopien unter $A, Kettenordner werden nur gelesen. Vorhandene Zuordnungen (db.db), nichts neu gematcht. Start nur per tools/job_start.sh, wenn KEIN Kettenjob laeuft:
#   JOB_GPU_MB=6500 JOB_RAM_MB=11000 bash tools/job_start.sh durchblick-1122 /media/oem/rcdaten/tmp/durchblick/beleg.log bash tools/versuche/durchblick_beleg_1122.sh
# 1 Seitenerkennung --durchblick (Pruefer-Ergebnisse der Kette wiederverwendet, CPU) -> db_durch.db   2 DB-Bereinigung wie die Kette (sfm_db_variante)
# 3 view_graph_calibrator + global_mapper ueber alle Bilder des neuen Teils 0   4 Auswertung (EIN Modell? Sim3 gegen Kette, GPS Teil 1, Grundriss)
# 5 dichte Wolke des neuen Modells (dicht_modell.py, GPU)   6 wand_dicke_tor (Grenzen unveraendert) Kettenteil 0 gegen neues Modell
set -u
R=$(cd "$(dirname "$0")/../.." && pwd); A=/media/oem/rcdaten/tmp/durchblick; K=/media/oem/scan/rc-park_daten/schwabentor-1122; S=$K/pipe/sfm
C=/media/oem/scan/colmap-build/prefix/bin/colmap; SEG=/media/oem/scan/venv-seg/bin/python; COL=/media/oem/scan/venv-colmap/bin/python
export LD_LIBRARY_PATH=/media/oem/scan/cuda-toolkit-combo/lib64:/media/oem/scan/venv-seg/lib/python3.12/site-packages/nvidia/cu13/lib:/media/oem/scan/cudss-pkg/py/nvidia/cu13/lib:/media/oem/scan/venv-colmap/lib/python3.12/site-packages/nvidia/curand/lib
export TMPDIR=/media/oem/rcdaten/tmp; mkdir -p $A/eingang; cd "$R"
OBJ=$A/eingang/objekt.json; AU=$A/eingang/SFM-AUSRICHTUNG-schwabentor-1122.json
[ -f $OBJ ] && [ -f $AU ] || { echo "Eingang fehlt ($OBJ / $AU)"; exit 2; }
echo "$(date +%T) 1 Seitenerkennung --durchblick"
if [ ! -f $A/db_durch.db ]; then
  $SEG -I tools/seiten_erkennen.py $S/db.db $K/fotos --aus $A/seiten_durch.json --db-aus $A/db_durch.tmp.db --streng --fernsicht $OBJ --pruefer-aus $S/seiten.json --durchblick 2>&1 | grep -v "^  Gruppe"
  mv $A/db_durch.tmp.db $A/db_durch.db || exit 3
fi
$SEG -I -c "import json; s=json.load(open('$A/seiten_durch.json')); g=s['gemeinschaft']; t=set(s['seiten'][0]['gruppen']); open('$A/teil0.txt','w').write('\n'.join(sorted(n for n,k in g.items() if k in t))+'\n')"
echo "$(date +%T) Bildliste: $(wc -l < $A/teil0.txt) Bilder"
echo "$(date +%T) 2 DB-Bereinigung"
[ -f $A/db_durch_mapper.db ] || { $COL -I tools/sfm_db_variante.py $A/db_durch.db $A/db_durch_mapper.tmp.db --priors loeschen --kamera-je-clip --loeschen '_360\.' && mv $A/db_durch_mapper.tmp.db $A/db_durch_mapper.db; } || exit 4
echo "$(date +%T) 3 globaler Mapper"
if [ ! -d $A/sparse/0 ]; then
  cp $A/db_durch_mapper.db $A/db_global.db; $C view_graph_calibrator --database_path $A/db_global.db > $A/kalib.log 2>&1 || { echo "Kalibrierung rc $?"; exit 5; }
  mkdir -p $A/sparse; t0=$(date +%s)
  $C global_mapper --database_path $A/db_global.db --image_path $K/fotos --output_path $A/sparse --GlobalMapper.image_list_path $A/teil0.txt > $A/global.log 2>&1 || { echo "global_mapper rc $?"; tail -5 $A/global.log; exit 6; }
  echo "$(date +%T) global_mapper $(( $(date +%s) - t0 )) s, Modelle: $(ls -d $A/sparse/[0-9]* | wc -l)"
fi
G=$(for d in $A/sparse/[0-9]*; do echo "$($C model_analyzer --path $d 2>&1 | grep -m1 'Registered images' | grep -o '[0-9]*$') $d"; done | sort -rn | head -1 | cut -d' ' -f2)
echo "$(date +%T) 4 Auswertung (groesstes Modell $G)"
$COL -I tools/versuche/durchblick_beleg_1122.py --modell $G --seiten-alt $S/seiten.json --ausrichtung $AU --objekt $OBJ --bilder $K/fotos --aus $A/beleg --tol-m 1.0 || exit 7
echo "$(date +%T) 5 dichte Wolke"
[ -f $A/dicht/fused.ply ] || $SEG -I tools/dicht_modell.py $G $K/fotos $A/dicht --stufe schnell 2>&1 | tail -5
echo "$(date +%T) 6 Wanddicke"
$COL -I tools/versuche/durchblick_beleg_1122.py --modell $G --seiten-alt $S/seiten.json --ausrichtung $AU --objekt $OBJ --bilder $K/fotos --aus $A/beleg --tol-m 1.0 \
  --kette-modell $S/seiten_modelle/teil0_a/0 --kette-fused $S/seiten_modelle/teil0/dicht/fused.ply --durch-fused $A/dicht/fused.ply > /dev/null
$COL -I tools/wand_dicke_tor.py $OBJ --seiten $A/beleg/seiten_modelle_probe.json --ausrichtung $AU --aus $A/beleg/wand_dicke.json
echo "$(date +%T) fertig rc_wand=$?"
