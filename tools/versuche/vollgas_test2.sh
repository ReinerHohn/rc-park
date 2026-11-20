#!/bin/bash
# vollgas_test2.sh - zweiter Durchgang (20.11.2026 15:50). Befund aus vollgas_test.sh: die Firmware nahm PL1=70 W an (rc 0), das Paket blieb bei 55 W,
# weil ZWEI weitere Grenzen auf 55 W stehen: (a) unser eigener Dienst cpu_leistung_regler (MAX=55, schreibt intel-rapl:0, senkt ab 88 C) und
# (b) intel-rapl-mmio:0 long_term 55 W. Dieser Test haelt den Regler an und setzt je Stufe ALLE DREI Stellen (WMI, MSR, MMIO), dann Volllast-Messung.
# Aufruf: sudo bash tools/versuche/vollgas_test2.sh      (ca. 5 min; neues hp-wmi-Modul muss geladen sein)
# Am Ende: Regler laeuft wieder (er zieht die MSR-Grenze auf sein MAX zurueck) - das Dauer-Einstellen macht die Sitzung nach Auswertung des Logs.
set -u; export LC_ALL=C
LOG=/media/oem/scan/rc-park_daten/job_logs/vollgas_test2_$(date +%m%d_%H%M).log
MSR=/sys/class/powercap/intel-rapl:0; MMIO=/sys/class/powercap/intel-rapl-mmio:0; E=$MSR/energy_uj; PAR=/sys/module/hp_wmi/parameters
TH=/sys/devices/system/cpu/cpu0/thermal_throttle/package_throttle_total_time_ms
TZ_=$(for z in /sys/class/thermal/thermal_zone*; do [ "$(cat $z/type)" = x86_pkg_temp ] && echo $z/temp; done | head -1)
[ "$(id -u)" = 0 ] || { echo "bitte mit sudo starten"; exit 1; }
[ -e $PAR/rcpark_pl_anwenden ] || { echo "neues hp-wmi-Modul nicht geladen (erst vollgas_test.sh)"; exit 1; }
mkdir -p "$(dirname "$LOG")"; : > "$LOG"; chmod a+r "$LOG"; chmod a+r $E
sag(){ echo "$@" | tee -a "$LOG"; }
stand(){ sag "   Grenzen jetzt: MSR $(( $(cat $MSR/constraint_0_power_limit_uw)/1000000 )) W lang / $(( $(cat $MSR/constraint_1_power_limit_uw)/1000000 )) W kurz | MMIO $(( $(cat $MMIO/constraint_0_power_limit_uw)/1000000 )) W lang / $(( $(cat $MMIO/constraint_1_power_limit_uw)/1000000 )) W kurz | Profil $(cat /sys/firmware/acpi/platform_profile)"; }
messen(){   # Volllast alle Faeden; Watt je 15-s-Abschnitt + letzte 30 s, Hoechsttemperatur, Drosselzeit
  local name=$1 dauer=$2 pids="" i e0 e1 ea eb t0 t1 tmax=0 t reihe=""
  for i in $(seq "$(nproc)"); do timeout "$dauer" sh -c 'while :; do :; done' & pids="$pids $!"; done
  t0=$(cat $TH); ea=$(cat $E)
  for i in $(seq $((dauer/15))); do
    for t in 1 2 3 4 5; do sleep 3; t=$(( $(cat "$TZ_")/1000 )); [ "$t" -gt "$tmax" ] && tmax=$t; done
    eb=$(cat $E); reihe="$reihe $(( (eb-ea)/15000000 ))"; [ "$i" = $((dauer/15-2)) ] && e0=$eb; ea=$eb
  done
  e1=$eb; t1=$(cat $TH); wait $pids 2>/dev/null
  WATT=$(( (e1-e0)/30000000 )); TMAX=$tmax; DROSSEL=$(( (t1-t0)*100/(dauer*1000) ))
  sag "$(printf '%-16s %3d W (letzte 30 s)   max %3d C   Drosselzeit %2d %%   Verlauf W je 15 s:%s' "$name" "$WATT" "$TMAX" "$DROSSEL" "$reihe")"
}
alle_setzen(){   # $1 = Watt Dauer, $2 = Watt kurz
  echo "$1" > $PAR/rcpark_pl1; echo "$2" > $PAR/rcpark_pl2; echo 1 > $PAR/rcpark_pl_anwenden 2>>"$LOG" || sag "   WMI abgelehnt"
  echo $(( $1*1000000 )) > $MSR/constraint_0_power_limit_uw 2>>"$LOG" || sag "   MSR lang nicht schreibbar"
  echo $(( $2*1000000 )) > $MSR/constraint_1_power_limit_uw 2>>"$LOG" || sag "   MSR kurz nicht schreibbar"
  echo $(( $1*1000000 )) > $MMIO/constraint_0_power_limit_uw 2>>"$LOG" || sag "   MMIO lang nicht schreibbar (Firmware-Sperre)"
  echo $(( $2*1000000 )) > $MMIO/constraint_1_power_limit_uw 2>>"$LOG" || sag "   MMIO kurz nicht schreibbar"
  sleep 1; stand
}
REGLER=$(systemctl is-active cpu_leistung_regler 2>/dev/null)
sag "== Vollgas-Test 2  $(date '+%F %T')  Regler vorher: $REGLER"; stand
[ "$REGLER" = active ] && systemctl stop cpu_leistung_regler && sag "   Regler angehalten"
echo performance > /sys/firmware/acpi/platform_profile
sag "-- 0. Bezug: 55 W an allen Stellen"; alle_setzen 55 130; messen "55 W" 60; W0=$WATT; GUT=55
for s in 70 90 110; do
  sag "-- Stufe $s W"; alle_setzen $s 157; messen "$s W" 90
  if [ "$TMAX" -gt 96 ] || [ "$DROSSEL" -gt 5 ]; then sag "   zu heiss bei $s W -> letzte gute Stufe $GUT W"; break; fi
  if [ "$WATT" -lt $((W0+5)) ]; then sag "   keine Wirkung ($WATT W) -> eine weitere, von hier nicht stellbare Bremse (Firmware/EC)"; break; fi
  GUT=$s; WGUT=$WATT
  [ "$WATT" -lt $((s-8)) ] && { sag "   Geraet erreicht $s W nicht (bleibt bei $WATT W) -> Obergrenze gefunden"; break; }
done
sag "== ERGEBNIS: Bezug $W0 W; hoechste gute Stufe $GUT W (gemessen ${WGUT:-$W0} W)"
alle_setzen 0 0 >/dev/null 2>&1; echo 55000000 > $MSR/constraint_0_power_limit_uw; echo 130000000 > $MSR/constraint_1_power_limit_uw
echo 55000000 > $MMIO/constraint_0_power_limit_uw 2>/dev/null; echo 130000000 > $MMIO/constraint_1_power_limit_uw 2>/dev/null
[ "$REGLER" = active ] && systemctl start cpu_leistung_regler && sag "   Regler laeuft wieder (Grenze vorerst wie vorher, max 55 W)"
stand; sag "   Log: $LOG"
