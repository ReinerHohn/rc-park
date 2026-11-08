#!/bin/bash
# platz_waechter.sh - Nutzerauftrag 8.11. ("wenn zu wenig Platz auf der SSD, dann auslagern und nicht deswegen stoppen").
# Prueft alle 60 s den freien Platz auf /media/oem/scan; unter WAECHTER_MIN_GB (Standard 14) wird der groesste KALTE Ordner
# unter rc-park_null (kein Symlink, nichts in den letzten 30 min geaendert, nicht geschuetzt) per tools/auslagern.sh auf den Stick
# verschoben (rsync + Pruefsumme, Original erst nach gleicher Kopie weg, Symlink zurueck). Stick voll/fehlt -> nur melden, nichts loeschen.
MIN=${WAECHTER_MIN_GB:-14}; S=/media/oem/scan; R=$S/rc-park_null; M=${AUSLAGERN_MOUNT:-/media/oem/rcstick}
GESCHUETZT="wettbewerb_kh gschleife_bog diffpar kreislauf limap"   # enthalten d03_fix/aktive Ergebnisse; Unterordner koennen von Hand ausgelagert werden
cd "$(dirname "$0")/.."
while true; do
  frei=$(df -BG --output=avail $S | tail -1 | tr -dc 0-9)
  if [ "$frei" -lt "$MIN" ]; then
    mountpoint -q "$M" || { echo "$(date +%T) Platz ${frei}G < ${MIN}G, aber $M fehlt"; sleep 300; continue; }
    best=""; bs=0
    for d in $R/*/; do d=${d%/}; n=$(basename $d); [ -L "$d" ] && continue
      case " $GESCHUETZT " in *" $n "*) continue;; esac
      [ -n "$(find $d -mmin -30 -print -quit 2>/dev/null)" ] && continue
      s=$(du -sm $d | cut -f1); [ "$s" -gt "$bs" ] && { bs=$s; best=$d; }
    done
    if [ -z "$best" ]; then echo "$(date +%T) Platz ${frei}G < ${MIN}G, kein kalter Kandidat"; sleep 300; continue; fi
    echo "$(date +%T) Platz ${frei}G < ${MIN}G -> lagere aus: $best (${bs}M)"
    AUSLAGERN_MOUNT=$M bash tools/auslagern.sh "$best" || sleep 300
  fi
  sleep 60
done
