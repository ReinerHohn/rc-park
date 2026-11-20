#!/usr/bin/env bash
# leistung.sh
# Vollgas fuer lange Scans/Bauen - aendert nichts an der Qualitaet, nur Takt und Kuehlung.
# Doku: GPU-PIPELINE.md, Abschnitt "Tempo".
#
#   bash leistung.sh an       # Leistungsprofil, Luefter voll bei Last, GPU Dynamic Boost (sudo)
#   bash leistung.sh aus      # zurueck: ausgeglichen, Luefter automatisch, Dynamic Boost aus
#   bash leistung.sh          # nur anzeigen
#
# Alles bleibt ueber Neustart und Standby erhalten:
#   Profil       -> power-profiles-daemon merkt es sich (/var/lib/power-profiles-daemon/state.ini)
#   Dynamic Boost -> systemctl enable nvidia-powerd
#   Luefter      -> Dienst luefter-last.service: voll ab CPU 75 C oder GPU 70 C, zurueck auf
#                   automatisch unter CPU 60 C und GPU 55 C (Hysterese, kein Gedroehne im Leerlauf).
#                   Setzt den Wert alle 5 s neu - ueberlebt so auch Standby (Firmware setzt zurueck).
#
# Gemessen (OMEN 16, i7-14700HX, RTX 4060 Laptop, 30.10.2026):
#   - Profil stand auf "power-saver" trotz Netzteil -> CPU taktete herunter
#   - GPU an der 80-W-Grenze ("SW power cap"), 2370 statt bis 3105 MHz;
#     nvidia-powerd (Dynamic Boost) installiert, aber nicht eingerichtet
#   - Luefter auf Automatik, CPU-Paket 83 C unter Last
set -u
FAN=$(ls /sys/devices/platform/hp-wmi/hwmon/hwmon*/pwm1_enable 2>/dev/null | head -1)
UNIT=/etc/systemd/system/luefter-last.service; LOOP=/usr/local/bin/luefter-last
OLD_UNIT=/etc/systemd/system/luefter-voll.service; OLD_HOOK=/usr/lib/systemd/system-sleep/luefter-voll
POWERD_UNIT=$(ls /usr/share/doc/nvidia-kernel-common-*/nvidia-powerd.service 2>/dev/null | head -1)

status(){
  echo "Profil:        $(powerprofilesctl get 2>/dev/null || echo '?')"
  echo "CPU-EPP:       $(cat /sys/devices/system/cpu/cpu0/cpufreq/energy_performance_preference 2>/dev/null)"
  [ -n "$FAN" ] && echo "Luefter:       $(case $(cat "$FAN") in 0) echo voll;; 2) echo automatisch;; *) cat "$FAN";; esac)" \
    "(Regelung nach Last: $(systemctl is-active luefter-last.service 2>/dev/null))"
  echo "Dynamic Boost: $(systemctl is-active nvidia-powerd 2>/dev/null)"
  nvidia-smi --query-gpu=power.draw,power.limit,clocks.sm,clocks.max.sm,temperature.gpu \
    --format=csv,noheader 2>/dev/null | sed 's/^/GPU:           /'
  sensors 2>/dev/null | grep -m1 "Package id 0" | sed 's/^/CPU:           /'
}

case "${1:-}" in
  an)
    powerprofilesctl set performance
    # 0 = Luefter voll, 2 = automatisch (hp-wmi, OMEN)
    if [ -n "$FAN" ]; then
      sudo tee "$LOOP" >/dev/null <<'EOF'
#!/bin/sh
# luefter-last (rc-park scan-setup/leistung.sh): OMEN-Luefter voll bei Last, sonst automatisch
voll=0
while :; do
  c=0; for h in /sys/class/hwmon/hwmon*; do
    [ "$(cat $h/name 2>/dev/null)" = coretemp ] && c=$(( $(cat $h/temp1_input) / 1000 )); done
  g=$(nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader,nounits 2>/dev/null | head -1)
  g=${g:-0}
  if [ "$c" -ge 75 ] || [ "$g" -ge 70 ]; then voll=1
  elif [ "$c" -lt 60 ] && [ "$g" -lt 55 ]; then voll=0; fi
  for f in /sys/devices/platform/hp-wmi/hwmon/hwmon*/pwm1_enable; do
    [ "$voll" = 1 ] && echo 0 > "$f" || echo 2 > "$f"; done
  sleep 5
done
EOF
      sudo chmod +x "$LOOP"
      sudo tee "$UNIT" >/dev/null <<EOF
[Unit]
Description=OMEN-Luefter voll bei Last (rc-park scan-setup/leistung.sh)
After=systemd-modules-load.service
[Service]
ExecStart=$LOOP
Restart=always
[Install]
WantedBy=multi-user.target
EOF
      sudo systemctl disable -q luefter-voll.service 2>/dev/null; sudo rm -f "$OLD_UNIT" "$OLD_HOOK"
      sudo systemctl daemon-reload; sudo systemctl enable -q --now luefter-last.service
    fi
    # Dynamic Boost: schiebt Leistung von der CPU zur GPU. Einmal einrichten, bleibt dann aktiv.
    if [ -n "$POWERD_UNIT" ] && ! systemctl is-active -q nvidia-powerd; then
      sudo cp "$POWERD_UNIT" /etc/systemd/system/ && sudo systemctl enable --now nvidia-powerd
    fi ;;
  aus)
    powerprofilesctl set balanced
    [ -n "$FAN" ] && echo 2 | sudo tee "$FAN" >/dev/null
    sudo systemctl disable -q --now luefter-last.service 2>/dev/null; sudo rm -f "$UNIT" "$LOOP" "$OLD_UNIT" "$OLD_HOOK"
    [ -n "$FAN" ] && echo 2 | sudo tee "$FAN" >/dev/null
    systemctl is-enabled -q nvidia-powerd 2>/dev/null && sudo systemctl disable --now nvidia-powerd ;;
  "") ;;
  *) echo "Aufruf: bash leistung.sh [an|aus]"; exit 1 ;;
esac
status
