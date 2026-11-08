#!/bin/bash
# Vom Nutzer zu starten. Loescht nur wiederherstellbare Test-/Fehlstart-/Altvarianten-Ordner
# (kein Referenznetz kaufhaus_null4, keine Fotos, nicht carv_kh3 = bester Druckstand, nicht carv_kh4_vis).
set -e
B=/media/oem/scan/rc-park_null
L="$B/kaufhaus_handy2 $B/test_s4 $B/test_tor_elementbuch $B/wolke_solid/openmvs_kh $B/wolke_solid/carv_kh2 $B/wolke_solid/carv_t3 $B/wolke_solid/carv_ms2 $B/wolke_solid/synth_carv2"
du -sh $L 2>/dev/null
read -p "Diese Ordner loeschen? [j/N] " a; [ "$a" = j ] || exit 0
rm -rf $L
df -h /media/oem/scan | tail -1
