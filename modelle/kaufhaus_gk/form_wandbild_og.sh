#!/bin/bash
# form_wandbild_og.sh [AUSDIR] [STL] [EXTRA...] - Kaufhaus Obergeschossfenster og_1..og_5 aus dem Wandbild (tools/form_aus_wandbild.py), Aufruf wie im
# Block objekt.json bauteile_foto.form_wandbild ("quelle"). Wand = Nordwest-Front (a, t, n aus relief/w04 bzw. form_og_*.npz), Zone = Fensterrechteck +-0,24 m.
# Standard: AUSDIR = modelle/kaufhaus_gk/relief, STL (Sichtbarkeit) = Katalog-STL. Lange Laeufe ueber JOB_GPU_MB=1500 tools/job_start.sh.
set -e
cd "$(dirname "$0")/../.."
AUS="${1:-modelle/kaufhaus_gk/relief}"; STL="${2:-/media/oem/scan/rc-park_stl/kaufhaus_gk_1-87.stl}"   # Standardbau (Katalog, FORM_WANDBILD aus); shift 2 2>/dev/null || shift $#
PY="/media/oem/scan/venv-seg/bin/python -W ignore -I"
WAND="-5.53 16.64 -4.59103924 16.29597575 -5.18597575 17.57896076"     # a, a+t, a+n (t = 0.93896076,-0.34402425; n = 0.34402425,0.93896076)
R=modelle/kaufhaus_gk/relief
mkdir -p "$AUS"
i=0
for Z in "2.826 5.412" "5.834 8.371" "8.84 11.428" "11.851 14.438" "14.819 17.42"; do
  i=$((i + 1)); n=$((6 - i))                                             # og_1 liegt bei u 14,8..17,4 (Nummerierung wie im Generator: von b nach a)
  $PY tools/form_aus_wandbild.py modelle/kaufhaus_gk/objekt.json --wand $WAND --zone $Z 6.88 10.1 --fotos auto --k 5 --fein 1 --stl "$STL" \
      --tiefe $R/w04.npz --flaeche $R/w04_rein.npz --aus "$AUS/form_og_$n.npz" "$@" 2>&1 | grep -v "^  Feinausrichtung Runde"
done

