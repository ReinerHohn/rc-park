#!/bin/bash
# leistung_ab.sh - EIN Skript: A/B balanced vs performance fuer CPU, GPU und CPU+GPU zusammen (Durchsatz + Watt + Takt + Temperatur).
#   sudo bash tools/leistung_ab.sh            (dauert ca. 12 Minuten; vorher alle GPU-/CPU-Jobs beenden, sonst verfaelscht)
# Je Profil: Abkuehlen (max 90 s bis < 55 C), dann Phase CPU 90 s, GPU 60 s, CPU+GPU 90 s. Am Ende steht das urspruengliche Profil wieder.
# Ausgabe: Konsole + /media/oem/scan/rc-park_daten/leistung_ab_<zeit>.log (Rohdaten je Phase in .../leistung_ab_<zeit>/).
set -u; export LC_ALL=C
[ "$(id -u)" = 0 ] || { echo "bitte mit sudo"; exit 1; }
command -v turbostat >/dev/null || { echo "turbostat fehlt"; exit 1; }
bash "$(dirname "$0")/hpwmi_pruefen.sh" || echo "(Pruefung meldet Probleme - siehe oben)"
PP=/sys/class/platform-profile/platform-profile-0/profile
[ -w $PP ] || { echo "$PP fehlt/nicht schreibbar (hp-wmi geladen? tools/hp_wmi_installieren.sh laden)"; exit 1; }
PY=/media/oem/scan/venv-seg/bin/python
T=$(date +%Y%m%d_%H%M%S); D=/media/oem/scan/rc-park_daten/leistung_ab_$T; mkdir -p $D
exec > >(tee -a $D.log) 2>&1
if nvidia-smi --query-compute-apps=pid,name --format=csv,noheader 2>/dev/null | grep -q .; then
  echo "ACHTUNG: GPU-Prozesse laufen schon:"; nvidia-smi --query-compute-apps=pid,name --format=csv,noheader; echo "Bitte beenden und neu starten."; exit 1; fi
if [ "$(uptime | awk -F'load average: ' '{print $2}' | cut -d, -f1 | cut -d. -f1)" -ge 3 ]; then
  echo "ACHTUNG: Grundlast hoch ($(uptime | awk -F'load average: ' '{print $2}')). Bitte Jobs beenden und neu starten."; exit 1; fi
ORIG=$(cat $PP)
trap 'echo $ORIG > $PP; pkill -f _ab_cpu.py; pkill -f _ab_gpu.py; echo "Profil zurueck: $ORIG"' EXIT INT TERM

cat > $D/_ab_cpu.py <<'E'
import sys, time, hashlib, multiprocessing as mp
def arb(t):
    e = time.time() + t; n = 0; b = b"x" * 4096
    while time.time() < e: b = hashlib.sha256(b).digest() * 128; n += 1
    return n
if __name__ == "__main__":
    t = float(sys.argv[1])
    with mp.Pool(mp.cpu_count()) as p: s = sum(p.map(arb, [t] * mp.cpu_count()))
    print("CPU_DURCHSATZ_pro_s %.0f" % (s / t))
E
cat > $D/_ab_gpu.py <<'E'
import sys, time, torch
t = float(sys.argv[1]); n = 8192
a = torch.randn(n, n, device="cuda", dtype=torch.float16); b = torch.randn(n, n, device="cuda", dtype=torch.float16)
torch.cuda.synchronize(); e = time.time() + t; k = 0
while time.time() < e:
    for _ in range(10): c = a @ b
    torch.cuda.synchronize(); k += 10
print("GPU_TFLOPS %.1f" % (k * 2 * n**3 / t / 1e12))
E

phase() {  # phase PROFIL NAME DAUER CPU(0/1) GPU(0/1)
  local p=$1 name=$2 dur=$3 cpu=$4 gpu=$5 f=$D/${1}_$2.csv; local pids=""
  [ $cpu = 1 ] && { $PY -I $D/_ab_cpu.py $((dur + 2)) > $D/${p}_${name}.cpu 2>&1 & pids="$pids $!"; }
  [ $gpu = 1 ] && { PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True $PY -I $D/_ab_gpu.py $((dur + 2)) > $D/${p}_${name}.gpu 2>&1 & pids="$pids $!"; }
  sleep 2; echo "t,mhz,temp,pkgw,gpuw,gpumhz" > $f
  for i in $(seq 1 $((dur / 2))); do
    L=$(turbostat --quiet --Summary --show Bzy_MHz,PkgTmp,PkgWatt --interval 2 --num_iterations 1 2>/dev/null | tail -1 | awk '{print $1","$2","$3}')
    G=$(nvidia-smi --query-gpu=power.draw,clocks.sm --format=csv,noheader,nounits | tr -d ' ')
    echo "$((i*2)),$L,$G" >> $f
  done
  [ -n "$pids" ] && wait $pids   # NICHT bares wait: haengt ewig an dem tee der Protokollumleitung
  # Mittel ueber die zweite Haelfte (Dauerzustand, ohne Anfangsstoss) + ganze Phase
  awk -F, -v p=$p -v n=$name -v d=$dur 'NR>1{c++; m[c]=$2;t[c]=$3;w[c]=$4;g[c]=$5;gm[c]=$6} END{h=int(c/2); for(i=h+1;i<=c;i++){a+=m[i];b+=t[i];cw+=w[i];e+=g[i];f+=gm[i]} k=c-h; printf "%-12s %-8s | 2.Haelfte: CPU %5.1f W %5.0f MHz %4.0f C | GPU %5.1f W %5.0f MHz",p,n,cw/k,a/k,b/k,e/k,f/k}' $f
  printf " | %s %s\n" "$(cat $D/${p}_${name}.cpu 2>/dev/null | tr '\n' ' ')" "$(cat $D/${p}_${name}.gpu 2>/dev/null | tr '\n' ' ')"
}
abkuehlen() { for i in $(seq 1 18); do t=$(turbostat --quiet --Summary --show PkgTmp --interval 5 --num_iterations 1 2>/dev/null | tail -1 | cut -d. -f1); [ "${t:-99}" -lt 55 ] && break; done; echo "  Start bei ${t:-?} C"; }

echo "=== leistung_ab $T, Ausgangsprofil $ORIG, Kernel $(uname -r) ==="
for P in balanced performance; do
  echo "--- Profil $P ---"; echo $P > $PP; echo "  gesetzt: $(cat $PP)"; abkuehlen
  phase $P cpu 90 1 0; abkuehlen
  phase $P gpu 60 0 1; abkuehlen
  phase $P cpugpu 90 1 1
done
echo "=== fertig. Rohdaten: $D/ ; Vergleich: Zeilen balanced gegen performance (gleiche Phase). ==="
