#!/bin/bash
# leistung_diagnose.sh - WAS bremst die CPU unter Last? (Temperatur, Strom, Firmware). Braucht Root + Pakete (siehe modelle/CPU_LEISTUNG.md):
#   sudo apt install linux-tools-$(uname -r) msr-tools      (turbostat, rdmsr; ohne sie bricht das Skript ab)
#   sudo bash tools/leistung_diagnose.sh [DAUER=40] [PL1_W=45] [TAU_S=Werk]   (TAU_S = Zeitfenster des Dauerlimits, Werk 32 s: verschiebt sich der Leistungsabfall bei ~33 s mit, ist er Tau-bedingt)
# Erzeugt Volllast (alle Threads), setzt fuer die Dauer PL1/PL2 (Ausgangswerte werden am Ende zurueckgesetzt) und protokolliert alle 2 s:
#   Paketleistung, Paket-Temperatur, Takt (Bzy_MHz) via turbostat, Limit-Gruende (MSR 0x64F CORE_PERF_LIMIT_REASONS, Rohwert + Bitnamen nach Intel-SDM, OHNE GEWAEHR).
# Ausgabe: Konsole + /media/oem/scan/rc-park_daten/leistung_diagnose_<zeit>.log
set -u; export LC_ALL=C
DAUER=${1:-40}; PL1=${2:-45}; TAUS=${3:-}
[ "$(id -u)" = 0 ] || { echo "bitte mit sudo"; exit 1; }
command -v turbostat >/dev/null || { echo "turbostat fehlt: sudo apt install linux-tools-$(uname -r)"; exit 1; }
command -v rdmsr >/dev/null || { echo "rdmsr fehlt: sudo apt install msr-tools"; exit 1; }
modprobe msr 2>/dev/null
RAPL=/sys/class/powercap/intel-rapl:0
LOG=/media/oem/scan/rc-park_daten/leistung_diagnose_$(date +%Y%m%d_%H%M%S).log; exec > >(tee -a "$LOG") 2>&1
P1=$(cat $RAPL/constraint_0_power_limit_uw); P2=$(cat $RAPL/constraint_1_power_limit_uw); P3=$(cat $RAPL/constraint_0_time_window_us)
zurueck() { echo $P1 > $RAPL/constraint_0_power_limit_uw; echo $P2 > $RAPL/constraint_1_power_limit_uw; echo $P3 > $RAPL/constraint_0_time_window_us 2>/dev/null; pkill -f "_diag_last.py" 2>/dev/null; echo "Limits zurueck ($((P1/1000000))/$((P2/1000000)) W)"; }
trap zurueck EXIT INT TERM
echo "Beginn $(date +%T), PL1 $PL1 W, Dauer $DAUER s, Ausgang $((P1/1000000))/$((P2/1000000)) W; rdmsr 0x64f vorab: $(rdmsr -p 0 0x64f 2>&1)"
[ -n "$TAUS" ] && echo $(( TAUS * 1000000 )) > $RAPL/constraint_0_time_window_us; echo "Zeitfenster Dauerlimit: $(( $(cat $RAPL/constraint_0_time_window_us)/1000000 )) s (Werk $((P3/1000000)) s)"
echo $(( PL1 * 1000000 )) > $RAPL/constraint_0_power_limit_uw; echo $(( 130 * 1000000 )) > $RAPL/constraint_1_power_limit_uw
cat > /tmp/_diag_last.py <<'E'
import sys, time, hashlib, multiprocessing as mp
def arb(t):
    e = time.time() + t; b = b"x" * 4096
    while time.time() < e: b = hashlib.sha256(b).digest() * 128
if __name__ == "__main__":
    t = float(sys.argv[1])
    with mp.Pool(mp.cpu_count()) as p: p.map(arb, [t] * mp.cpu_count())
E
python3 /tmp/_diag_last.py $((DAUER + 4)) &
LP=$!
sleep 2
decode() {  # Rohwert (hex) -> Bitnamen (nach Intel SDM Vol.4 MSR 0x64F, OHNE GEWAEHR)
  local v=$(( 16#${1#0x} )); local n=("PROCHOT" "THERMAL" "" "" "RESIDENCY" "AVG_THERMAL" "VR_THERMAL_ALERT" "VR_TDC" "OTHER" "" "EDP/ICCMAX" "MAX_TURBO" "TURBO_TRANS_ATTENUATION" "MAX_EFFICIENCY_FREQ"); local r=""
  for i in "${!n[@]}"; do [ -n "${n[$i]}" ] && [ $(( (v >> i) & 1 )) = 1 ] && r+="${n[$i]} "; done; echo "${r:-keine}"
}
echo "Zeit  Bzy_MHz PkgTmp PkgWatt | 0x64F (Rohwert; steht VOR der Last schon gleich -> nur mit Vorsicht deuten)  Bitnamen (ohne Gewaehr)"
for i in $(seq 1 $((DAUER / 2))); do
  L=$(turbostat --quiet --Summary --show PkgWatt,PkgTmp,Bzy_MHz --interval 2 --num_iterations 1 2>/dev/null | tail -1)
  M=$(rdmsr -p 0 0x64f 2>/dev/null); [ -z "$M" ] && M=0
  echo "$(date +%T)  $L | 0x$M  $(decode $M)"
done
wait $LP 2>/dev/null
echo "Ende. Auswertung: bei 'THERMAL/AVG_THERMAL/PROCHOT' bremst die Temperatur bzw. Firmware (EC), bei 'EDP/ICCMAX' der Strom, bei 'MAX_TURBO' die Turbo-Tabelle; leer = nichts meldet sich -> Bremse ausserhalb der CPU (Firmware/EC-Stromgrenze)."
