#!/bin/bash
# links_auf_platte.sh MOUNTPUNKT [SUCHWURZELN...]   (18.11.2026) - zaehlt/listet ALLE Verknuepfungen, die auf eine Platte zeigen, auch ueber Alias-Pfade.
# Anlass: umzug_auslagerung.sh bog nur Verknuepfungen mit dem Mountpfad um (/media/oem/TOSHIBA EXT/...); 424 weitere zeigten ueber den Alias /home/oem/toshiba_ext dorthin
# (und 276 in der Kopie auf der SSD noch auf den abgezogenen Stick). Vor "Platte abziehen" MUSS dieses Werkzeug 0 melden (der Alias-Link selbst zaehlt nicht).
# Aliase = Verknuepfungen in /home/oem, /media/oem und /mnt, deren aufgeloester Pfad der Mountpunkt ist.
M="${1:?Mountpunkt}"; shift; R="${*:-/home/oem /media/oem/scan /media/oem/rcdaten}"; MR=$(readlink -f "$M"); P=("$MR")
for d in /home/oem /media/oem /mnt; do for l in "$d"/*; do [ -L "$l" ] && [ "$(readlink -f "$l")" = "$MR" ] && P+=("$l"); done; done
echo "Pfadformen der Platte: ${P[*]}"; N=0
for p in "${P[@]}"; do while IFS= read -r f; do [ -L "$f" ] && [ "$f" = "$p" ] && continue; N=$((N+1)); [ $N -le 5 ] && echo "  $f -> $(readlink "$f")" | cut -c1-200; done < <(find $R -xdev -type l -lname "$p/*" 2>/dev/null); done
echo "$N Verknuepfungen zeigen auf $M"; [ $N = 0 ] || exit 3
