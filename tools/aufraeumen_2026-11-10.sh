#!/bin/bash
# Aufraeumen Root-Platte 10.11.2026 (vom Koordinator geprueft, Ausfuehren durch den Nutzer: Loeschen nur per Nutzer-Skript).
# Aufruf im eigenen Terminal:  sudo bash tools/aufraeumen_2026-11-10.sh
# Ziel ~10 GB frei auf / (Root 4,7 GB frei, Pruefstand verlangt 5 GB -> Kreis-Abnahmen brechen ab).
# Nichts Eingechecktes, keine Fotos geloescht: iPhone-Abzug und alte Uploads werden auf die Datenplatte VERSCHOBEN.
set -u
cd /home/oem/git/rc-park || exit 1
[ "$(id -u)" = 0 ] || { echo "Bitte mit sudo starten"; exit 1; }
D=/media/oem/scan/rc-park_daten
df -h / | tail -1

# 1) Temp-/Testdateien (~0,6 GB)
rm -rf /tmp/x /tmp/pf_pymeshlab /tmp/lotfix /tmp/tmp.tFdSIaZN1N /tmp/tmp.YV78WIfOLf /tmp/tmp.I7vi06LbWm   # Wheels 6./7.11., temporaere Firefox-Profile
rm -rf /tmp/claude-29999/-home-oem-git-rc-park/57ead240-2740-4358-802f-a9b7959b6d34   # Scratch alte Sitzung 8.11.
rm -f ./--help __tracked_surface.stl DensifyPointCloud-*.log InterfaceCOLMAP-*.log ReconstructMesh-*.log RefineMesh-*.log modelle/stl/_tmp_*.stl

# 2) OpenProject-Docker: Container seit 10 Monaten beendet, Image 3,0 GB (~3 GB). Home Assistant/ESPHome/Influx/Kanboard bleiben.
docker rm tender_wescoff && docker rmi openproject/openproject:16

# 3) Zweite Auslagerungsdatei auf Root (2 GB). Die 16-GB-Auslagerung auf der Datenplatte bleibt (13 GB frei).
swapoff /swapfile && rm -f /swapfile && sed -i 's|^/swapfile |#/swapfile |' /etc/fstab

# 4) Systemjournal auf 100 MB kuerzen (~0,55 GB), apt-Cache leeren (~0,2 GB)
journalctl --vacuum-size=100M
apt-get clean

# 5) Firefox-Cache (~0,6 GB, wird neu angelegt)
rm -rf /home/oem/.cache/mozilla

# 6) VERSCHIEBEN auf die Datenplatte (~2,3 GB): iPhone-Abzug und alte Claude-Uploads (Symlink bleibt)
mkdir -p $D/_von_root
[ -d /tmp/iph ] && mv /tmp/iph $D/_von_root/iph && chown -R oem:oem $D/_von_root/iph && echo "iPhone-Abzug jetzt in $D/_von_root/iph"
U=/home/oem/.claude/uploads/63397706-b9e2-4697-8769-9f75926107d2
[ -d $U ] && [ ! -L $U ] && mv $U $D/_von_root/ && ln -s $D/_von_root/$(basename $U) $U && chown -h oem:oem $U

df -h / | tail -1

# 10.11. 16:05: Reste von teil_fotoform in /tmp (76 Ordner, 4,1 GB, Root nur noch 5 GB). Nur Ordner, die seit >= 60 min unveraendert sind
# (laufende Messungen behalten ihren Ordner). Ab Commit "teil_fotoform: Temp auf Datenplatte" entstehen keine neuen mehr.
find /tmp -maxdepth 1 -type d -name 'tff_k_*' -mmin +60 -print -exec rm -rf {} +
df -h /
