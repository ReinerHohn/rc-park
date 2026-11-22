#!/bin/bash
# durchblick_beleg_1122.sh - BELEG fuer die Stufe Durchblick/Umgebung (tools/seiten_erkennen.py --durchblick) an schwabentor-1122 (22.11.2026).
# Nur Kopien unter $A, Kettenordner werden nur gelesen. Vorhandene Zuordnungen (db.db), nichts neu gematcht. Start per tools/job_start.sh; PARALLEL zur Kette
# (Nutzerfreigabe 22.11. abends) mit hartem Deckel: der ganze Lauf steckt in einem systemd-Scope MemoryMax=$DECKEL (Auslagerung erlaubt), AllowedCPUs = halbe Kernzahl:
#   JOB_GPU_MB=2500 JOB_RAM_MB=5000 JOB_MEMORY_HIGH=5G JOB_OHNE_RAM_SPERRE=1 bash tools/job_start.sh durchblick-1122 /media/oem/rcdaten/tmp/durchblick/beleg.log bash tools/versuche/durchblick_beleg_1122.sh
# 1 Seitenerkennung --durchblick (Pruefer-Ergebnisse der Kette wiederverwendet, CPU) -> db_durch.db   2 DB-Bereinigung wie die Kette (sfm_db_variante)
# 3 view_graph_calibrator + global_mapper (halbe Kernzahl) ueber alle Bilder des neuen Teils 0   4 Auswertung (EIN Modell? Sim3 gegen Kette, GPS Teil 1, Grundriss)
# 5 dichte Wolke nur mit DURCH_DICHT=1 (GPU ~6 GB, nicht neben der Kette); sonst wand_dicke_tor auf den DUENNEN Punkten beider Modelle (schwaecherer Beleg, so benannt)
set -u
DECKEL=${DURCH_DECKEL:-5G}
if [ -z "${DURCH_IM_SCOPE:-}" ]; then
  H=$(( $(nproc) / 2 )); exec systemd-run --user --scope --quiet -p MemoryMax=$DECKEL -p AllowedCPUs=0-$(( H - 1 )) --setenv=DURCH_IM_SCOPE=1 env DURCH_IM_SCOPE=1 DURCH_FAEDEN=$H bash "$0" "$@"
fi
R=$(cd "$(dirname "$0")/../.." && pwd); A=/media/oem/rcdaten/tmp/durchblick; K=/media/oem/scan/rc-park_daten/schwabentor-1122; S=$K/pipe/sfm
C=/media/oem/scan/colmap-build/prefix/bin/colmap; SEG=/media/oem/scan/venv-seg/bin/python; COL=/media/oem/scan/venv-colmap/bin/python; N=${DURCH_FAEDEN:-4}
export LD_LIBRARY_PATH=/media/oem/scan/cuda-toolkit-combo/lib64:/media/oem/scan/venv-seg/lib/python3.12/site-packages/nvidia/cu13/lib:/media/oem/scan/cudss-pkg/py/nvidia/cu13/lib:/media/oem/scan/venv-colmap/lib/python3.12/site-packages/nvidia/curand/lib
export TMPDIR=/media/oem/rcdaten/tmp OMP_NUM_THREADS=$N; mkdir -p $A/eingang; cd "$R"
echo "$(date +%T) Scope: MemoryMax $DECKEL, $N Faeden"
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
  cp $A/db_durch_mapper.db $A/db_global.db; $C view_graph_calibrator --database_path $A/db_global.db > $A/kalib.log 2>&1 || { echo "Kalibrierung rc $?"; tail -3 $A/kalib.log; exit 5; }
  mkdir -p $A/sparse; t0=$(date +%s)
  $C global_mapper --database_path $A/db_global.db --image_path $K/fotos --output_path $A/sparse --GlobalMapper.image_list_path $A/teil0.txt --GlobalMapper.num_threads $N > $A/global.log 2>&1 || { echo "global_mapper rc $?"; tail -5 $A/global.log; exit 6; }
  echo "$(date +%T) global_mapper $(( $(date +%s) - t0 )) s, Modelle: $(ls -d $A/sparse/[0-9]* | wc -l)"
fi
G=$(for d in $A/sparse/[0-9]*; do echo "$($C model_analyzer --path $d 2>&1 | grep -m1 'Registered images' | grep -o '[0-9]*$') $d"; done | sort -rn | head -1 | cut -d' ' -f2)
echo "$(date +%T) 4 Auswertung (groesstes Modell $G)"
$COL -I tools/versuche/durchblick_beleg_1122.py --modell $G --seiten-alt $S/seiten.json --ausrichtung $AU --objekt $OBJ --bilder $K/fotos --aus $A/beleg --tol-m 1.0 || exit 7
if [ "${DURCH_DICHT:-0}" = "1" ]; then
  echo "$(date +%T) 5 dichte Wolke"
  [ -f $A/dicht/fused.ply ] || $SEG -I tools/dicht_modell.py $G $K/fotos $A/dicht --stufe schnell 2>&1 | tail -5
  KF=$S/seiten_modelle/teil0/dicht/fused.ply; DF=$A/dicht/fused.ply; ART=dicht
else
  echo "$(date +%T) 5 ohne dichte Wolke: duenne Punkte beider Modelle"
  KF=$A/kette_sparse.ply; DF=$A/durch_sparse.ply; ART=duenn
  $COL -I tools/versuche/durchblick_beleg_1122.py --modell x --seiten-alt x --ausrichtung x --objekt x --bilder x --aus $A/beleg --sparse-ply $S/seiten_modelle/teil0_a/0 $KF
  $COL -I tools/versuche/durchblick_beleg_1122.py --modell x --seiten-alt x --ausrichtung x --objekt x --bilder x --aus $A/beleg --sparse-ply $G $DF
fi
echo "$(date +%T) 6 Wanddicke ($ART)"
$COL -I tools/versuche/durchblick_beleg_1122.py --modell $G --seiten-alt $S/seiten.json --ausrichtung $AU --objekt $OBJ --bilder $K/fotos --aus $A/beleg --tol-m 1.0 \
  --kette-modell $S/seiten_modelle/teil0_a/0 --kette-fused $KF --durch-fused $DF > /dev/null
$COL -I tools/wand_dicke_tor.py $OBJ --seiten $A/beleg/seiten_modelle_probe.json --ausrichtung $A/beleg/ausrichtung_inlier.json --aus $A/beleg/wand_dicke_$ART.json; RCW=$?
echo "$(date +%T) fertig rc_wand=$RCW"
