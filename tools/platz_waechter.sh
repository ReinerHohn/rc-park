#!/bin/bash
# platz_waechter.sh - Nutzerauftrag 8.11. ("wenn zu wenig Platz auf der SSD, dann auslagern und nicht deswegen stoppen")
# und 11.11. 21:0x ("Abbruch ist Kacke. Du musst dafuer sorgen, dass genug Platz ist. Immer, immer, immer."):
# Kreis-Runde erker4 (+0,025 am Foto) wurde verworfen, weil die ROOT-Platte unter 5 GB fiel - der alte Waechter sah nur die Datenplatte
# und fand dort nur unter rc-park_null Kandidaten ("kein kalter Kandidat" bei 6 GB).
#
# Alle 60 s:
#  ROOT  (/): unter WAECHTER_ROOT_MIN_GB (Standard 10) kalte Agenten-Sitzungsprotokolle (~/.claude/projects/-media-oem-scan-*, 120 min unveraendert)
#        und alte /tmp/tmp*-Ordner (eigene, 6 h unveraendert) auf die Datenplatte verschieben (mv, nichts loeschen).
#  DATEN (/media/oem/scan): unter WAECHTER_MIN_GB (Standard 14) den groessten KALTEN Ordner (kein Symlink, 60 min nichts geaendert,
#        kein Git-Worktree darin, nicht geschuetzt) aus rc-park_null/*, rc-park_tmp/*, rc-park_daten/*/*, rc-park_kreis/*/2026*
#        per tools/auslagern.sh (rsync + Pruefsumme, Symlink zurueck) auf das Auslagerungsziel mit dem meisten freien Platz verschieben
#        (WAECHTER_ZIELE, Standard "/media/oem/rcdaten /media/oem/Volume" (18.11.: 2-TB-SSD statt Stick/Toshiba); AUSLAGERN_MOUNT setzt nur noch das bevorzugte Ziel).
#        Wiederholen bis MIN + 2 GB erreicht oder kein Kandidat mehr.
# Kein Ziel/kein Kandidat -> laut melden (Log), nichts loeschen.
MIN=${WAECHTER_MIN_GB:-14}; RMIN=${WAECHTER_ROOT_MIN_GB:-10}; S=/media/oem/scan
ZIELE=${WAECHTER_ZIELE:-"${AUSLAGERN_MOUNT:-} /media/oem/rcdaten /media/oem/Volume"}
GESCHUETZT="wettbewerb_kh gschleife_bog diffpar kreislauf limap _git_objekte belegt patches viewer abend"
cd "$(dirname "$0")/.."
frei_gb() { df -BG --output=avail "$1" 2>/dev/null | tail -1 | tr -dc 0-9; }
kalt() { [ -z "$(find "$1" -mmin -"$2" -print -quit 2>/dev/null)" ]; }
bestes_ziel() { local b="" bf=0 m f; for m in $ZIELE; do mountpoint -q "$m" || continue; f=$(frei_gb "$m"); [ "${f:-0}" -gt 20 ] && [ "$f" -gt "$bf" ] && { bf=$f; b=$m; }; done; echo "$b"; }

root_schritt() {
  local fr=$(frei_gb /); [ "$fr" -ge "$RMIN" ] && return
  local Z=$S/rc-park_tmp/root_auslagerung/$(date +%Y%m%d); mkdir -p "$Z"; local n=0 d
  for d in "$HOME"/.claude/projects/-media-oem-scan-*; do [ -d "$d" ] && [ ! -L "$d" ] || continue; kalt "$d" 120 || continue; mv -- "$d" "$Z/" && n=$((n+1)); done
  while IFS= read -r -d '' d; do mv -- "$d" "$Z/" && n=$((n+1)); done < <(find /tmp -maxdepth 1 -user "$(id -u)" -name 'tmp*' -mmin +360 -print0 2>/dev/null)
  # Sitzungsprotokolle der Hauptprojekte (> 1 Tag unveraendert): verschieben + Symlink zurueck (Sitzung bleibt fortsetzbar)
  local P; for P in "$HOME"/.claude/projects/-home-*; do [ -d "$P" ] || continue
    while IFS= read -r -d '' d; do local ziel="$Z/sitzungen/$(basename "$P")"; mkdir -p "$ziel"; mv -- "$d" "$ziel/" && ln -s "$ziel/$(basename "$d")" "$d" && n=$((n+1)); done \
      < <(find "$P" -mindepth 1 -maxdepth 1 ! -type l -mtime +1 -print0 2>/dev/null)
  done
  echo "$(date +%T) ROOT ${fr}G < ${RMIN}G -> $n kalte Ordner nach $Z verschoben, jetzt $(frei_gb /)G"
}

daten_schritt() {
  local fr=$(frei_gb $S); [ "$fr" -ge "$MIN" ] && return
  local M=$(bestes_ziel); [ -z "$M" ] && { echo "$(date +%T) DATEN ${fr}G < ${MIN}G, aber kein Auslagerungsziel mit > 20 GB eingehaengt ($ZIELE)"; return; }
  local best="" bs=0 d n s
  for d in $S/rc-park_null/*/ $S/rc-park_tmp/*/ $S/rc-park_daten/*/*/ $S/rc-park_kreis/*/2026*/; do
    d=${d%/}; [ -d "$d" ] && [ ! -L "$d" ] || continue; n=$(basename "$d")
    case " $GESCHUETZT " in *" $n "*) continue;; esac
    [ -L "$(dirname "$d")" ] && continue
    [ -n "$(find "$d" -maxdepth 3 -name .git -print -quit 2>/dev/null)" ] && continue   # Git-Worktree/Repo nie verschieben
    kalt "$d" 60 || continue
    s=$(du -sm "$d" 2>/dev/null | cut -f1); [ "${s:-0}" -gt "$bs" ] && { bs=$s; best=$d; }
  done
  [ -z "$best" ] || [ "$bs" -lt 100 ] && { echo "$(date +%T) DATEN ${fr}G < ${MIN}G, kein kalter Kandidat > 100 MB"; return 1; }
  echo "$(date +%T) DATEN ${fr}G < ${MIN}G -> lagere aus: $best (${bs}M) nach $M"
  AUSLAGERN_MOUNT=$M bash tools/auslagern.sh "$best" || return 1
}

while true; do
  root_schritt
  for i in 1 2 3 4 5 6 7 8 9 10; do f=$(frei_gb $S); [ "$f" -ge $((MIN + 2)) ] && break; [ "$f" -ge "$MIN" ] && [ "$i" -gt 1 ] && break; daten_schritt || break; done
  sleep 60
done
