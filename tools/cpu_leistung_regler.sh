#!/bin/bash
# cpu_leistung_regler.sh - hebt das CPU-Dauerlimit (RAPL PL1) STUFENWEISE an, solange Temperatur es zulaesst und das Limit wirklich bindet;
# senkt bei Hitze wieder. Hintergrund: Werkseinstellung dieses Laptops 25 W/31 W (i7-14700HX darf 55 W), Takt unter Last ~1 GHz bei nur 65 C
# (Messung 6.11.15:02, modelle/CPU_LEISTUNG.md). Braucht Root (sysfs). Start: sudo tools/cpu_leistung_regler.sh   |   Dienst: tools/cpu_leistung_installieren.sh
#   Umgebungsvariablen (Standard): START=35 MAX=55 SCHRITT=5 TOK=80 THOCH=88 TNOT=92 GOK=83 T=10 PL2=130 TAU_US=(leer)
#   START   Limit beim Start/nach Notbremse (W)            MAX     Obergrenze Dauerlimit (W); Kernel meldet 55 W als Paket-Maximum (hoeher = ungetestet)
#   TOK     unter dieser CPU-Paket-Temperatur darf angehoben werden (C)     GOK  dasselbe fuer die GPU-Temperatur (Abwaerme im selben Gehaeuse)
#   THOCH   ab hier wird um SCHRITT gesenkt                 TNOT    ab hier sofort auf START
#   T       Takt der Regelung (s). Angehoben wird nur, wenn das Paket >= 90 % des Limits zieht (Limit bindet, also Last da).
# Das Skript schreibt das Limit auch zurueck, wenn thermald/Firmware es veraendert (Zaehler in der Logzeile). Beim Beenden: Ausgangswerte.
START=${START:-35}; MAX=${MAX:-55}; SCHRITT=${SCHRITT:-5}; TOK=${TOK:-80}; THOCH=${THOCH:-88}; TNOT=${TNOT:-92}; GOK=${GOK:-83}; T=${T:-10}
PL2=${PL2:-130}; TAU_US=${TAU_US:-}   # leer = Zeitfenster NICHT aendern (Test 6.11. 15:18: Fenster 95 s verschiebt den Abfall nicht, modelle/CPU_LEISTUNG.md 3d). PL2 = Kurzzeit-Boost (Firmware-Wert laut intel-rapl-mmio: 130 W), TAU = Zeitfenster des Dauerlimits (Werk 32 s): so lange darf der gleitende Mittelwert ueber PL1 liegen
RAPL=${RAPL:-/sys/class/powercap/intel-rapl:0}; STATE=${STATE:-/run/cpu_leistung_regler.state}

# Reine Entscheidung (testbar): pl1 temp watt gpu_temp -> neues pl1
entscheiden() {
  local pl1=$1 temp=$2 watt=$3 gpu=$4 neu=$1
  if   [ "$temp" -ge "$TNOT" ];  then neu=$START
  elif [ "$temp" -ge "$THOCH" ]; then neu=$(( pl1 - SCHRITT )); [ "$neu" -lt "$START" ] && neu=$START
  elif [ "$temp" -lt "$TOK" ] && [ "$gpu" -lt "$GOK" ] && [ $(( watt * 10 )) -ge $(( pl1 * 9 )) ] && [ "$pl1" -lt "$MAX" ]; then
    neu=$(( pl1 + SCHRITT )); [ "$neu" -gt "$MAX" ] && neu=$MAX
  fi
  echo "$neu"
}
[ "${1:-}" = "--nur-funktion" ] && return 0 2>/dev/null

[ "$(id -u)" -eq 0 ] || { echo "bitte mit sudo starten"; exit 1; }
[ -w $RAPL/constraint_0_power_limit_uw ] || { echo "$RAPL nicht beschreibbar (intel_rapl?)"; exit 1; }
MMIO=${MMIO:-/sys/class/powercap/intel-rapl-mmio:0}; WMI=${WMI:-/sys/module/hp_wmi/parameters}; M1_0=$(cat $MMIO/constraint_0_power_limit_uw 2>/dev/null); M2_0=$(cat $MMIO/constraint_1_power_limit_uw 2>/dev/null)
PL1_0=$(cat $RAPL/constraint_0_power_limit_uw); PL2_0=$(cat $RAPL/constraint_1_power_limit_uw); TAU_0=$(cat $RAPL/constraint_0_time_window_us)
setzen() {  # pl1_W
  local p1=$1 p2=$PL2; [ "$p2" -lt "$p1" ] && p2=$p1
  echo $(( p1 * 1000000 )) > $RAPL/constraint_0_power_limit_uw; echo $(( p2 * 1000000 )) > $RAPL/constraint_1_power_limit_uw; [ -n "$TAU_US" ] && echo $TAU_US > $RAPL/constraint_0_time_window_us 2>/dev/null
  # 20.11.2026 (tools/versuche/vollgas_test2.sh, gemessen 70/90/110 W ohne Drosselung): ueber 55 W kommt das Paket nur, wenn ALLE DREI Stellen angehoben sind -
  # MSR (oben), MMIO-Grenze der Firmware und der WMI-Befehl des Eigenbau-hp-wmi (rcpark_pl*). Fehlt eine Stelle (altes Modul, Sperre), bleibt es beim alten Verhalten.
  if [ -w $MMIO/constraint_0_power_limit_uw ]; then echo $(( p1 * 1000000 )) > $MMIO/constraint_0_power_limit_uw 2>/dev/null; echo $(( p2 * 1000000 )) > $MMIO/constraint_1_power_limit_uw 2>/dev/null; fi
  if [ -e $WMI/rcpark_pl_anwenden ]; then echo $p1 > $WMI/rcpark_pl1; echo $p2 > $WMI/rcpark_pl2; echo 1 > $WMI/rcpark_pl_anwenden 2>/dev/null; fi
}
beenden() { [ -n "$M1_0" ] && { echo $M1_0 > $MMIO/constraint_0_power_limit_uw; echo $M2_0 > $MMIO/constraint_1_power_limit_uw; } 2>/dev/null; [ -e $WMI/rcpark_pl_anwenden ] && { echo 0 > $WMI/rcpark_pl1; echo 0 > $WMI/rcpark_pl2; echo 1 > $WMI/rcpark_pl_anwenden; } 2>/dev/null; echo $PL1_0 > $RAPL/constraint_0_power_limit_uw; echo $PL2_0 > $RAPL/constraint_1_power_limit_uw; echo $TAU_0 > $RAPL/constraint_0_time_window_us 2>/dev/null; echo "Ausgangswerte wiederhergestellt ($((PL1_0/1000000))/$((PL2_0/1000000)) W)"; exit 0; }
trap beenden INT TERM
ptemp() { for z in /sys/class/thermal/thermal_zone*; do [ "$(cat $z/type 2>/dev/null)" = x86_pkg_temp ] && { echo $(( $(cat $z/temp)/1000 )); return; }; done; echo 0; }
gtemp() { nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader,nounits 2>/dev/null | head -1 | tr -dc 0-9; }

pl1=$START; setzen $pl1; korr=0
echo "Regler: START=$START MAX=$MAX SCHRITT=$SCHRITT TOK=$TOK THOCH=$THOCH TNOT=$TNOT GOK=$GOK T=${T}s (Ausgang $((PL1_0/1000000))/$((PL2_0/1000000)) W)"
e1=$(cat $RAPL/energy_uj); t1=$(date +%s.%N)
while true; do
  # 20.11.2026: Temperatur als MITTEL ueber das Messfenster (1 Wert je s) statt Augenblickswert - einzelne Turbo-Spitzen eines Kerns (92-96 C fuer < 1 s)
  # loesten sonst Ruecknahmen bis zum Notfallwert aus (Journal 15:57-16:01: 100 -> 55 W bei nur 30 W Paketleistung).
  tsum=0; for _ in $(seq "$T"); do sleep 1; tsum=$(( tsum + $(ptemp) )); done
  e2=$(cat $RAPL/energy_uj); t2=$(date +%s.%N)
  watt=$(awk -v a="$e1" -v b="$e2" -v x="$t1" -v y="$t2" 'BEGIN{d=b-a; if(d<0)d=0; printf "%d", d/1e6/(y-x)}'); e1=$e2; t1=$t2
  temp=$(( tsum / T )); gpu=$(gtemp); gpu=${gpu:-0}
  ist=$(( $(cat $RAPL/constraint_0_power_limit_uw) / 1000000 ))
  if [ "$ist" -ne "$pl1" ]; then korr=$((korr+1)); echo $(( pl1 * 1000000 )) > $RAPL/constraint_0_power_limit_uw; fi   # 20.11.2026: NUR den MSR-Wert zurueckschreiben - setzen() rief hier alle 10 s auch den WMI-Befehl (441 Aufrufe in 100 min), und der WMI-Befehl selbst stellt den MSR-Wert um (Schleife)            # fremde Aenderung (thermald/Firmware) zurueckschreiben
  neu=$(entscheiden $pl1 $temp $watt $gpu)
  if [ "$neu" -ne "$pl1" ]; then echo "$(date +%H:%M:%S) CPU ${temp}C GPU ${gpu}C Paket ${watt}W: PL1 $pl1 -> $neu W (Korrekturen durch Fremdaenderung: $korr)"; pl1=$neu; setzen $pl1; fi
  echo "pl1=$pl1 temp=$temp gpu=$gpu watt=$watt korrekturen=$korr" > "$STATE"
done
