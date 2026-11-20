#!/bin/bash
# vollgas_test.sh - EIN Skript fuer den CPU-Leistungstest (Nutzer 20.11.2026): neues hp-wmi-Modul signieren + laden, dann die Dauergrenze
# stufenweise anheben (Firmware-Standard -> 70 W -> 90 W) und je Stufe unter Volllast messen (Watt, Temperatur, Hitzedrosselung).
# Aufruf:  sudo bash tools/versuche/vollgas_test.sh            (alles, ca. 6 min)
#          bash tools/versuche/vollgas_test.sh --nur_messen    (ohne Root: nur eine Messung des jetzigen Zustands, 40 s)
# Sicherheiten: Modul laedt nicht / Profil fehlt -> altes Modul (hp-wmi.ko.stand_0611) wird sofort zurueckgespielt.
#               Stufe mit > 95 C oder > 5 % Drosselzeit -> zurueck auf die letzte gute Stufe. Die Firmware behaelt ihren eigenen Hitzeschutz.
# Die gesetzte Grenze gilt bis zum naechsten Neustart/Modulwechsel. Ergebnis: Tabelle am Ende + Log (fuer die Sitzung lesbar).
set -u; export LC_ALL=C
R=$(cd "$(dirname "$0")/../.." && pwd); K=$(uname -r); ARB=/media/oem/scan/rc-park_null/hpwmi_bau/build
LOG=/media/oem/scan/rc-park_daten/job_logs/vollgas_test_$(date +%m%d_%H%M).log
E=/sys/class/powercap/intel-rapl:0/energy_uj; PAR=/sys/module/hp_wmi/parameters; TH=/sys/devices/system/cpu/cpu0/thermal_throttle/package_throttle_total_time_ms
TZ_=$(for z in /sys/class/thermal/thermal_zone*; do [ "$(cat $z/type)" = x86_pkg_temp ] && echo $z/temp; done | head -1)
sag(){ echo "$@" | tee -a "$LOG"; }
temp(){ echo $(( $(cat "$TZ_") / 1000 )); }
# messen NAME LASTSEKUNDEN: Volllast auf allen 28 Faeden, gewertet werden die letzten 30 s (die Firmware faehrt die Leistung ueber ~45 s hoch)
messen(){
  local name=$1 dauer=$2 pids="" i e0 e1 t0 t1 tmax=0 t w
  for i in $(seq "$(nproc)"); do timeout "$dauer" sh -c 'while :; do :; done' & pids="$pids $!"; done
  sleep $((dauer-30)); e0=$(cat $E); t0=$(cat $TH)
  for i in $(seq 15); do sleep 2; t=$(temp); [ "$t" -gt "$tmax" ] && tmax=$t; done
  e1=$(cat $E); t1=$(cat $TH); wait $pids 2>/dev/null
  w=$(( (e1-e0)/30000000 )); DROSSEL=$(( (t1-t0)/300 )); TMAX=$tmax; WATT=$w     # Drossel in % der 30 s (ms/30000*100)
  MHZ=$(awk '/MHz/{s+=$4;n++} END{printf "%d", s/n}' /proc/cpuinfo)
  sag "$(printf '%-22s %3d W   max %3d C   Drosselzeit %2d %%' "$name" "$w" "$tmax" "$DROSSEL")"
}
setzen(){ echo "$1" > $PAR/rcpark_pl1 && echo "$2" > $PAR/rcpark_pl2 && echo 1 > $PAR/rcpark_pl_anwenden; }
zurueck_modul(){
  sag "!! Ruecksprung auf das alte Modul"
  cp $ARB/hp-wmi.ko.stand_0611 /lib/modules/$K/updates/hp-wmi.ko && depmod -a; modprobe -r hp_wmi 2>/dev/null; modprobe hp_wmi; sleep 2
  echo performance > /sys/firmware/acpi/platform_profile 2>/dev/null; sag "Profil jetzt: $(cat /sys/firmware/acpi/platform_profile 2>/dev/null)"
}

mkdir -p "$(dirname "$LOG")"; : > "$LOG"; chmod a+r "$LOG"
if [ "${1:-}" = "--nur_messen" ]; then [ -r $E ] || { echo "energy_uj nicht lesbar (sudo chmod a+r $E)"; exit 1; }; messen "jetziger Zustand" 40; exit 0; fi
[ "$(id -u)" = 0 ] || { echo "bitte mit sudo starten: sudo bash tools/versuche/vollgas_test.sh"; exit 1; }
[ -f $ARB/hp-wmi.ko ] && [ -f $ARB/hp-wmi.ko.stand_0611 ] || { echo "Modul oder Sicherung fehlt in $ARB"; exit 1; }
chmod a+r $E
sag "== Vollgas-Test $(date '+%F %T')  Kernel $K"
sag "-- 1. Ausgangslage (altes Modul, Profil $(cat /sys/firmware/acpi/platform_profile))"
messen "vorher (alt)" 75; W_ALT=$WATT

sag "-- 2. neues Modul signieren + laden"
bash "$R/tools/hp_wmi_installieren.sh" signieren 2>&1 | tail -2 | tee -a "$LOG"
bash "$R/tools/hp_wmi_installieren.sh" laden 2>&1 | tail -3 | tee -a "$LOG"
sleep 2
if [ ! -e $PAR/rcpark_pl_anwenden ] || [ ! -e /sys/firmware/acpi/platform_profile ]; then sag "FEHLER: neues Modul nicht aktiv"; zurueck_modul; exit 1; fi
echo performance > /sys/firmware/acpi/platform_profile; sag "Profil: $(cat /sys/firmware/acpi/platform_profile)"
messen "neu, Firmware-Standard" 75; W_STD=$WATT
if [ "$W_STD" -lt $((W_ALT-8)) ]; then sag "FEHLER: neues Modul bringt weniger Leistung als das alte ($W_STD < $W_ALT W)"; zurueck_modul; exit 1; fi

GUT1=0; GUT2=0
for stufe in "70 130" "90 130" "110 157"; do
  set -- $stufe; sag "-- 3. Grenze $1 W Dauer / $2 W kurz"
  if ! setzen "$1" "$2" 2>>"$LOG"; then sag "Firmware/Modul lehnt den Befehl ab (siehe: dmesg | grep rcpark)"; break; fi
  dmesg | grep rcpark | tail -1 | tee -a "$LOG"
  messen "Grenze $1 W" 90
  if [ "$TMAX" -gt 95 ] || [ "$DROSSEL" -gt 5 ]; then sag "   zu heiss -> zurueck auf die letzte gute Stufe"; setzen "$GUT1" "$GUT2"; break; fi
  if [ "$WATT" -lt $((W_STD+5)) ]; then sag "   keine Wirkung (Leistung bleibt bei $WATT W) -> Firmware nimmt die Grenze nicht an oder eine andere Bremse greift"; setzen 0 0; GUT1=0; GUT2=0; break; fi
  GUT1=$1; GUT2=$2; W_GUT=$WATT
  [ "$WATT" -lt $(( $1 - 8 )) ] && { sag "   Geraet erreicht $1 W nicht ($WATT W) -> das ist die Obergrenze"; break; }
done
sag "== ERGEBNIS: alt $W_ALT W, neu Standard $W_STD W, eingestellt bleibt: $([ "$GUT1" = 0 ] && echo 'Firmware-Standard' || echo "$GUT1 W Dauer / $GUT2 W kurz (gemessen ${W_GUT:-?} W)")"
sag "   RAPL: $(( $(cat /sys/class/powercap/intel-rapl:0/constraint_0_power_limit_uw)/1000000 )) W lang, $(( $(cat /sys/class/powercap/intel-rapl:0/constraint_1_power_limit_uw)/1000000 )) W kurz   Log: $LOG"
