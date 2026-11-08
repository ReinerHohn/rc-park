#!/bin/bash
# leistung_testen.sh - CPU-(und optional GPU-)Leistungslimits stufenweise erhoehen und je Stufe Durchsatz/Takt/Temperatur/Leistung messen.
#   ! sudo bash tools/leistung_testen.sh            nur CPU (RAPL PL1/PL2), ca. 3 Minuten
#   ! sudo bash tools/leistung_testen.sh --beide    CPU-Stufen MIT gleichzeitiger GPU-Dauerlast (Alltagsfall: geteiltes Leistungsbudget/Kuehlung), danach GPU-Stufen
#   ! sudo bash tools/leistung_testen.sh --gpu      zusaetzlich GPU-Powerlimit (nvidia-smi -pl) mit Torch-Dauerlast, ca. 2 Minuten
# Sicherheit: Ursprungswerte werden gelesen und am Ende (auch bei Abbruch/Strg-C) zurueckgesetzt. Abbruch einer Stufe bei >= 92 Grad.
# Messung: feste Zeit (DAUER s) Volllast auf allen Threads, Durchsatz = Rechenschritte/s. Referenz-Stufe wird am Ende WIEDERHOLT (Drift durch parallele Jobs sichtbar).
# ACHTUNG: laufen gleichzeitig andere schwere Jobs, sind die Zahlen verrauscht - die Wiederholung der Referenz zeigt, wie stark.
# Nichts wird dauerhaft geaendert (gilt bis zum Neustart; hier zusaetzlich zurueckgesetzt).
set -u
export LC_ALL=C   # Dezimalpunkt (printf in deutscher Locale lehnt sonst Punktzahlen ab)
DAUER=${DAUER:-20}
RAPL=/sys/class/powercap/intel-rapl:0
LOG=/media/oem/scan/rc-park_daten/leistung_test_$(date +%Y%m%d_%H%M%S).log
GPU=0; BEIDE=0; [ "${1:-}" = "--gpu" ] && GPU=1; [ "${1:-}" = "--beide" ] && { GPU=1; BEIDE=1; }
[ "$(id -u)" = 0 ] || { echo "Bitte mit sudo starten: sudo bash $0"; exit 1; }
[ -d $RAPL ] || { echo "kein $RAPL"; exit 1; }
exec > >(tee -a "$LOG") 2>&1
PL1_0=$(cat $RAPL/constraint_0_power_limit_uw); PL2_0=$(cat $RAPL/constraint_1_power_limit_uw)
GPU_0=$(nvidia-smi --query-gpu=power.limit --format=csv,noheader,nounits 2>/dev/null | head -1 | cut -d. -f1)
zuruecksetzen() {
  echo; echo "== zuruecksetzen: PL1=$((PL1_0/1000000)) W PL2=$((PL2_0/1000000)) W${GPU_0:+, GPU-Limit ${GPU_0} W}"
  echo $PL1_0 > $RAPL/constraint_0_power_limit_uw 2>/dev/null; echo $PL2_0 > $RAPL/constraint_1_power_limit_uw 2>/dev/null
  [ "$GPU" = 1 ] && [ -n "${GPU_0:-}" ] && nvidia-smi -pl "$GPU_0" >/dev/null 2>&1
}
trap zuruecksetzen EXIT INT TERM
temp() { for z in /sys/class/thermal/thermal_zone*; do [ "$(cat $z/type)" = x86_pkg_temp ] && echo $(( $(cat $z/temp)/1000 )) && return; done; echo 0; }
mhz() { awk '/cpu MHz/{s+=$4;n++} END{printf "%d", s/n}' /proc/cpuinfo; }
echo "== Beginn $(date +%H:%M:%S)  Log: $LOG"
echo "Ausgangswerte: PL1=$((PL1_0/1000000)) W, PL2=$((PL2_0/1000000)) W, Paket-max=$(( $(cat $RAPL/constraint_0_max_power_uw)/1000000 )) W, Temp $(temp) C, Load $(cut -d' ' -f1 /proc/loadavg)"
echo "Laufende Fremdlast (CPU-%): $(ps -eo pcpu --no-headers | awk '{s+=$1} END{printf "%d", s}')  (bei > 300 sind die Zahlen verrauscht)"

# Volllast: je Thread feste Hash-Schleife, zaehlt Durchlaeufe in DAUER Sekunden
cat > /tmp/_last.py <<'E'
import sys, time, hashlib, multiprocessing as mp
def arb(t):
    n = 0; b = b"x" * 4096; e = time.time() + t
    while time.time() < e:
        for _ in range(200): b = hashlib.sha256(b).digest() * 128
        n += 200
    return n
if __name__ == "__main__":
    t = float(sys.argv[1]); k = mp.cpu_count()
    with mp.Pool(k) as p: r = p.map(arb, [t] * k)
    print(sum(r) / t)
E

cat > /tmp/_gpulast.py <<'E'
import sys, time, torch
t = float(sys.argv[1]); a = torch.randn(4096, 4096, device="cuda", dtype=torch.half); b = torch.randn(4096, 4096, device="cuda", dtype=torch.half)
torch.cuda.synchronize(); e = time.time() + t; n = 0
while time.time() < e:
    for _ in range(20): c = a @ b
    torch.cuda.synchronize(); n += 20
print(n * 2 * 4096 ** 3 / t / 1e12)
E
GPULOCK=/media/oem/scan/rc-park_daten/.gpu_lock
stufe_cpu() {  # name pl1_W pl2_W
  echo $(( $2 * 1000000 )) > $RAPL/constraint_0_power_limit_uw; echo $(( $3 * 1000000 )) > $RAPL/constraint_1_power_limit_uw; sleep 1
  gl=$(( $(cat $RAPL/constraint_0_power_limit_uw)/1000000 )); gl2=$(( $(cat $RAPL/constraint_1_power_limit_uw)/1000000 ))
  e1=$(cat $RAPL/energy_uj); t0=$(date +%s.%N)
  ( sleep $((DAUER/2)); echo "$(mhz) $(temp) $(( $(cat $RAPL/constraint_0_power_limit_uw)/1000000 ))" > /tmp/_mid ) & MP=$!; GP=""
  rm -f /tmp/_gtf; if [ "$BEIDE" = 1 ] && [ ! -s $GPULOCK ]; then /media/oem/scan/venv-seg/bin/python -I /tmp/_gpulast.py $((DAUER+2)) > /tmp/_gtf 2>&1 & GP=$!; fi
  tp=$(python3 /tmp/_last.py $DAUER); wait $MP $GP
  [ "$BEIDE" = 1 ] && [ -s /tmp/_gtf ] && gt=" | GPU gleichzeitig $(tail -1 /tmp/_gtf) TFLOPS" || gt=""
  e2=$(cat $RAPL/energy_uj); t1=$(date +%s.%N); read m tmp plmid < /tmp/_mid; thr=$(cat /sys/devices/system/cpu/cpu*/thermal_throttle/package_throttle_count 2>/dev/null | paste -sd+ | bc 2>/dev/null)
  w=$(echo "($e2-$e1)/1000000/($t1-$t0)" | bc -l)
  printf "%-10s gesetzt PL1/PL2=%s/%s W (gelesen %s/%s)  Durchsatz %9.0f /s  Takt %5s MHz  Temp %3s C  Paket %5.1f W  PL1-mitte %s W  Drossel-Zaehler %s%s\n" "$1" "$2" "$3" "$gl" "$gl2" "$tp" "$m" "$tmp" "$w" "$plmid" "${thr:-?}" "$gt"
  [ "$(temp)" -ge 92 ] && { echo "!! >= 92 C - weitere Stufen abgebrochen"; return 1; }
  sleep 8   # abkuehlen
}

echo; echo "== CPU-Stufen (je ${DAUER} s Volllast)"
R1=$((PL1_0/1000000)); R2=$((PL2_0/1000000))
for runde in 1 2; do
  stufe_cpu "ref-$runde" $R1 $R2 || break
  stufe_cpu "45/90-$runde" 45 90 || break
  stufe_cpu "55/120-$runde" 55 120 || break
done
echo "Gesetzte Limits am Ende der Stufen koennen von thermald/Firmware veraendert worden sein: siehe PL1-mitte (Wert mitten in der Messung)."

if [ "$GPU" = 1 ]; then
  echo; echo "== GPU-Stufen (Torch-Dauerlast ${DAUER} s je Stufe)"
  if [ -s /media/oem/scan/rc-park_daten/.gpu_lock ]; then echo "GPU-Lock gesetzt: $(cat /media/oem/scan/rc-park_daten/.gpu_lock) - GPU-Test uebersprungen (Messung wuerde stoeren)"; else
  for pl in $GPU_0 100 115 130; do
    if ! nvidia-smi -pl $pl >/dev/null 2>&1; then echo "GPU-Limit $pl W: von nvidia-smi abgelehnt (not supported in current scope?) - Stufe uebersprungen"; continue; fi
    ( sleep $((DAUER/2)); nvidia-smi --query-gpu=clocks.sm,temperature.gpu,power.draw --format=csv,noheader,nounits > /tmp/_gmid ) & MP=$!
    tf=$(/media/oem/scan/venv-seg/bin/python -I /tmp/_gpulast.py $DAUER 2>&1 | tail -1); wait $MP
    printf "GPU-Limit %3s W (gelesen %s W): %s TFLOPS fp16, mitte: [SM MHz, Temp C, Watt] %s\n" "$pl" "$(nvidia-smi --query-gpu=power.limit --format=csv,noheader,nounits | cut -d. -f1)" "$tf" "$(cat /tmp/_gmid)"
    sleep 8
  done; fi
fi
echo; echo "== Ende $(date +%H:%M:%S). Auswertung: Vergleiche Durchsatz je Stufe; 'referenz' vs 'referenz2' = Messrauschen."
