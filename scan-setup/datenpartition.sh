#!/usr/bin/env bash
# datenpartition.sh
# Eigene ext4-Partition fuer gpu-setup.sh (DATA). Verkleinert "Volume" (NTFS) am Ende um GB GiB
# und legt dort "scan" an, eingebunden unter /media/oem/scan (fstab).   Doku: GPU-PIPELINE.md
#
#   sudo bash datenpartition.sh [GB]          # Standard 100
#
# Warum: Auf NTFS (ntfs-3g/FUSE) hingen Bau und Scans am Dateisystem - mount.ntfs-3g bei 100 % CPU,
# Compiler nur 40-50 % ausgelastet, 131 MB/s statt 1,6 GB/s auf derselben SSD. Der schnellere
# Kernel-Treiber ntfs3 ist in Linux Mint absichtlich gesperrt (/lib/modprobe.d/mint-blacklist-ntfs3.conf).
#
# NUR FUER DEN HP-LAPTOP: Die erwarteten Sektoren unten sind fest eingetragen (Stand 30.10.2026,
# dort einmal gelaufen). Auf einem anderen Rechner bricht das Skript ohne Aenderung ab ->
# dort lieber GParted nehmen. Vorher: Netzteil dran, unersetzliche Daten sichern,
# in Windows den Schnellstart aus (sonst verweigert ntfsresize die Partition).
set -euo pipefail
GB="${1:-100}"
DISK=/dev/nvme0n1; P4=/dev/nvme0n1p4; MNT=/media/oem/scan; OWNER=29999:29999
die(){ echo "ABBRUCH: $*" >&2; exit 1; }
[ "$(id -u)" = 0 ] || die "bitte mit sudo starten"

# Erwartete Lage pruefen (Stand 30.10.2026): p4 endet direkt vor p6 (Linux-Root)
START=$(cat /sys/block/nvme0n1/nvme0n1p4/start); SIZE=$(cat /sys/block/nvme0n1/nvme0n1p4/size)
P6=$(cat /sys/block/nvme0n1/nvme0n1p6/start)
[ "$START" = 281958400 ] && [ "$SIZE" = 614400000 ] && [ "$P6" = 896358400 ] \
  || die "Partitionen sehen anders aus als erwartet - nichts geaendert"
findmnt "$P4" >/dev/null && die "$P4 ist eingebunden - erst: sudo umount /media/oem/Volume"

CUT=$(( GB * 1024 * 1024 * 2 ))          # GiB -> 512-Byte-Sektoren (immer 1-MiB-ausgerichtet)
NEWSIZE=$(( SIZE - CUT )); NEWEND=$(( START + NEWSIZE - 1 ))
FSBYTES=$(( (NEWSIZE - 2048) * 512 ))     # NTFS 1 MiB kleiner als die Partition, als Puffer

echo ">>> 0) Sicherung der Partitionstabelle -> /home/oem/partitionstabelle-vorher.sfdisk"
sfdisk -d "$DISK" > /home/oem/partitionstabelle-vorher.sfdisk

echo ">>> 1) NTFS pruefen"
INFO=$(ntfsresize --info --no-progress-bar "$P4") || { echo "$INFO"; die "ntfsresize --info fehlgeschlagen (Windows-Schnellstart? -> in Windows abschalten, richtig herunterfahren)"; }
MIN=$(echo "$INFO" | sed -n 's/.*resize at \([0-9]*\) bytes.*/\1/p')
[ -n "$MIN" ] || { echo "$INFO"; die "Mindestgroesse nicht gefunden"; }
echo "    belegt mind. $((MIN/1024/1024/1024)) GiB, neue Groesse $((FSBYTES/1024/1024/1024)) GiB"
[ $(( FSBYTES - MIN )) -gt $(( 10 * 1024*1024*1024 )) ] || die "zu wenig Platz - kleinere Zahl als $GB waehlen"

echo ">>> 2) Probelauf"
ntfsresize --no-action --no-progress-bar -s "$FSBYTES" "$P4"
echo ">>> 3) NTFS verkleinern (Rueckfrage mit y bestaetigen)"
ntfsresize --no-progress-bar -s "$FSBYTES" "$P4"

echo ">>> 4) Partition 4 verkleinern, neue Partition dahinter"
# Rueckfrage von parted ("Shrinking ... Are you sure?") mit Yes bestaetigen
parted "$DISK" unit s resizepart 4 "${NEWEND}s"
parted -s "$DISK" unit s mkpart scan ext4 "$(( NEWEND + 1 ))s" "$(( P6 - 1 ))s"
partprobe "$DISK" || true; udevadm settle
NEW=$(lsblk -lnpo NAME,PARTLABEL "$DISK" | awk '$2=="scan"{print $1}')
[ -b "$NEW" ] || die "neue Partition nicht gefunden"

echo ">>> 5) ext4 auf $NEW"
mkfs.ext4 -L scan "$NEW"
UUID=$(blkid -s UUID -o value "$NEW")
mkdir -p "$MNT"
grep -q "$UUID" /etc/fstab || echo "UUID=$UUID  $MNT  ext4  defaults,noatime,nofail  0  2" >> /etc/fstab
systemctl daemon-reload; mount "$MNT"; chown "$OWNER" "$MNT"

echo ">>> 6) Volume wieder einbinden"
mount /media/oem/Volume
df -h /media/oem/Volume "$MNT"
echo "FERTIG"
