#!/bin/bash
# zswap_an.sh [an|aus|stand] - komprimierte Auslagerung im Arbeitsspeicher (zswap) vor der Auslagerungsdatei auf der SSD.
# Grund (Nutzer 20.11.2026, modelle/HARDWARE_STAND_2026-11-20.md): 16 GB RAM, 6-8 GB staendig ausgelagert. zswap haelt ausgelagerte Seiten erst
# komprimiert im RAM (zstd, typ. 3:1) und schreibt nur den Ueberlauf auf die SSD -> Zurueckholen ohne Plattenzugriff. Wirkt sofort, ohne Neustart;
# laufende Jobs bleiben unberuehrt (schon Ausgelagertes wandert erst beim naechsten Zugriff). Dauerhaft ueber /etc/tmpfiles.d + modules-load.d.
#   sudo bash tools/zswap_an.sh an      einschalten + dauerhaft
#   sudo bash tools/zswap_an.sh aus     ausschalten + Dauer-Eintraege entfernen
#   bash tools/zswap_an.sh stand        Zustand und Kompressionsgrad (ohne Root, Statistik nur mit Root)
set -u; P=/sys/module/zswap/parameters; T=/etc/tmpfiles.d/rcpark-zswap.conf; M=/etc/modules-load.d/rcpark-zswap.conf
stand(){
  echo "zswap: enabled=$(cat $P/enabled) compressor=$(cat $P/compressor) zpool=$(cat $P/zpool) max_pool_percent=$(cat $P/max_pool_percent)"
  free -m | sed -n 2,3p
  if [ -r /sys/kernel/debug/zswap/stored_pages ]; then
    s=$(cat /sys/kernel/debug/zswap/stored_pages); b=$(cat /sys/kernel/debug/zswap/pool_total_size)
    echo "im Speicher komprimiert: $((s*4/1024)) MB Seiten in $((b/1048576)) MB Pool$([ "$b" -gt 0 ] && echo " (Faktor $(awk -v s=$s -v b=$b 'BEGIN{printf "%.1f", s*4096/b}'))")"
  fi
}
case "${1:-stand}" in
an)
  [ "$(id -u)" = 0 ] || { echo "bitte mit sudo"; exit 1; }
  [ -d $P ] || { echo "Kernel ohne zswap"; exit 1; }
  K=lzo; for k in zstd lz4; do modprobe $k 2>/dev/null; if echo $k > $P/compressor 2>/dev/null; then K=$k; break; fi; done
  echo 25 > $P/max_pool_percent; echo 1 > $P/enabled
  [ "$K" != lzo ] && echo "$K" > $M
  printf 'w %s/compressor - - - - %s\nw %s/max_pool_percent - - - - 25\nw %s/enabled - - - - 1\n' $P $K $P $P > $T
  echo "eingeschaltet (Kompressor $K, Pool bis 25 % des RAM), dauerhaft: $T"; stand;;
aus)
  [ "$(id -u)" = 0 ] || { echo "bitte mit sudo"; exit 1; }
  echo 0 > $P/enabled; rm -f $T $M; echo "ausgeschaltet, Dauer-Eintraege entfernt"; stand;;
stand) stand;;
*) echo "Aufruf: $0 an|aus|stand"; exit 2;;
esac
