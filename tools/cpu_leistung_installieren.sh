#!/bin/bash
# cpu_leistung_installieren.sh - CPU-Leistungsregler dauerhaft (systemd) einrichten. EINMAL pro Rechner: sudo tools/cpu_leistung_installieren.sh
# Entfernen: sudo systemctl disable --now cpu_leistung_regler   (beim Stoppen werden die Ausgangswerte 25/31 W wiederhergestellt)
set -e; [ "$(id -u)" -ne 0 ] && { echo "bitte: sudo $0"; exit 1; }
cd "$(dirname "$0")"
bash -n cpu_leistung_regler.sh
cp cpu_leistung_regler.service /etc/systemd/system/cpu_leistung_regler.service
systemctl daemon-reload && systemctl enable --now cpu_leistung_regler && sleep 2 && systemctl --no-pager status cpu_leistung_regler | head -5
echo; echo "Beobachten: journalctl -fu cpu_leistung_regler    Zustand: cat /run/cpu_leistung_regler.state"
