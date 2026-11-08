#!/bin/bash
# gs_kaufhaus_variante.sh NAME - nach dem Training (gs_kh2/NAME/gs_ckpt.pt): Tiefenkarten rendern (GPU), TSDF-Netz (CPU, venv-o3d, Huelle +1,5 m, Komponenten < 1 % weg), Wettbewerb gegen C und mvs_d03_pl30 (Ergebnis wettbewerb_kh17_NAME).
# Ausgabe: gs_kh2/NAME/netz.stl, gs_kh2/NAME/netz.log, gs_kh2/NAME/wettbewerb.log. Aufruf ueber tools/job_start.sh (siehe gs_kaufhaus_lauf.sh fuer die GPU-Teile).
set -e; N="$1"; R=/media/oem/scan/rc-park_null; D=$R/gs_kh2/$N; cd /home/oem/git/rc-park
tools/gs_kaufhaus_lauf.sh tools/gs_kaufhaus_netz2.py --modus tiefe --daten $D > $D/tiefe.log 2>&1
/media/oem/scan/venv-o3d/bin/python -W ignore -I tools/gs_kaufhaus_netz2.py --modus tsdf --daten $D --huelle modelle/stl/kaufhaus_null5_1-87.stl --aus $D/netz.stl > $D/netz.log 2>&1
cat $D/netz.log | tail -4
/media/oem/scan/venv-seg/bin/python -W ignore -I tools/modell_wettbewerb.py modelle/kaufhaus_null5/objekt.json --aus $R/wettbewerb_kh17_$N --maske-von $R/wettbewerb_kh9g/masken --maske-kandidat C \
  --liste 000,004,010,016,022,026,032,043,049,054,059,065,073,082,095,114,120,209,214,218,222,227,247 --kerne 3 \
  --kandidat C:$R/qualitaetsstufen_kaufhaus_null6/modell_s3_v9.stl --kandidat mvs_d03_pl30:$R/wettbewerb_kh/netze5/mvs_d03_pl30.stl --kandidat gs$N:$D/netz.stl > $D/wettbewerb.log 2>&1
tail -6 $D/wettbewerb.log
