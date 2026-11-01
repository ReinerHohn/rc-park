#!/bin/bash
# luefter_installieren.sh - Luefterregler dauerhaft (systemd) einrichten. Einmal: sudo tools/luefter_installieren.sh
set -e; [ "$(id -u)" -ne 0 ] && { echo "bitte: sudo $0"; exit 1; }
cp "$(dirname "$0")/luefter_adaptiv.service" /etc/systemd/system/luefter_adaptiv.service
systemctl daemon-reload && systemctl enable --now luefter_adaptiv && systemctl --no-pager status luefter_adaptiv | head -3
