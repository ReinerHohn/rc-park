#!/bin/bash
# job_wache.sh - Lagebild fuer die Nachtwache (15.11.2026, Nutzer: "fix es so, dass es geht"): neue Jobfehler seit dem letzten Aufruf (job_start.sh
# schreibt jeden Job mit rc != 0 nach rc-park_daten/job_fehler.log), laufende Jobs, GPU-/CPU-Last, Platz. Claude ruft das Skript per Zeitplan
# (CronCreate, alle ~20 min) auf, behebt Fehler und startet neu. --nur_lesen laesst die Fehler unquittiert.
D=/media/oem/scan/rc-park_daten; F=$D/job_fehler.log; M=$D/.job_fehler_gelesen; touch "$F"
alt=$(cat "$M" 2>/dev/null || echo 0); neu=$(wc -l < "$F")
echo "== $(date '+%F %T') NEUE JOBFEHLER: $((neu - alt))"; [ "$neu" -gt "$alt" ] && tail -n +"$((alt + 1))" "$F" | cut -c1-420
[ "$1" = "--nur_lesen" ] || echo "$neu" > "$M"
echo "== LAUFENDE JOBS"; systemctl --user list-units 'rcpark-*' --no-legend 2>/dev/null | awk '{print $1}' | grep -v "gpuwache\|editordraht\|platz_waechter" | tr '\n' ' '; echo
echo "== GPU $(nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader 2>/dev/null) | Last $(cut -d' ' -f1-3 /proc/loadavg) | Buchungen: $(tr '\n' ';' < $D/.gpu_buchung 2>/dev/null)"
echo "== PLATZ Daten $(df -BG --output=avail /media/oem/scan | tail -1 | tr -d ' ') frei, Root $(df -BG --output=avail / | tail -1 | tr -d ' ') frei"
tail -n 3 /media/oem/scan/rc-park_daten/gpu_warnungen.log 2>/dev/null | cut -c1-200
