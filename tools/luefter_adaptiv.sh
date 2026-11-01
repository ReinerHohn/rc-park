#!/bin/bash
# luefter_adaptiv.sh - zweistufige, temperaturgefuehrte Luefterregelung fuer Laptops mit hp-wmi (OMEN): der Treiber kennt nur
# pwm1_enable 2 (BIOS-Automatik, zurueckhaltend) und 0 (volle Drehzahl). Dieser Regler schaltet nach GPU-Temperatur mit Hysterese:
#   >= HOCH  -> voll (0)        < TIEF -> Automatik (2)
# Braucht Root (sysfs). Start:  sudo tools/luefter_adaptiv.sh [HOCH=75] [TIEF=62] [INTERVALL_S=5]
# Beenden mit Ctrl-C -> stellt Automatik wieder her. Optional dazu: sudo nvidia-smi -pl 140 (GPU-Limit, zurueck mit -pl 80).
HOCH=${1:-75}; TIEF=${2:-62}; T=${3:-5}
PWM=$(ls /sys/class/hwmon/hwmon*/pwm1_enable 2>/dev/null | head -1)
[ -z "$PWM" ] && { echo "kein pwm1_enable gefunden (hp-wmi?)"; exit 1; }
[ "$(id -u)" -ne 0 ] && { echo "bitte mit sudo starten"; exit 1; }
zustand=2; trap 'echo 2 > "$PWM"; echo; echo "Automatik wiederhergestellt"; exit 0' INT TERM
echo "Regler laeuft: voll ab ${HOCH} C, Automatik unter ${TIEF} C ($PWM)"
while true; do
  temp=$(nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader,nounits 2>/dev/null | head -1)
  cpu=$(awk '{printf "%d", $1/1000}' /sys/class/thermal/thermal_zone*/temp 2>/dev/null | sort -n | tail -1)
  [ -z "$temp" ] && temp=0; [ -z "$cpu" ] && cpu=0; max=$(( temp > cpu ? temp : cpu ))
  if [ "$zustand" -eq 2 ] && [ "$max" -ge "$HOCH" ]; then echo 0 > "$PWM"; zustand=0; echo "$(date +%H:%M:%S) ${max} C -> Luefter VOLL"; fi
  if [ "$zustand" -eq 0 ] && [ "$max" -lt "$TIEF" ]; then echo 2 > "$PWM"; zustand=2; echo "$(date +%H:%M:%S) ${max} C -> Automatik"; fi
  sleep "$T"
done
