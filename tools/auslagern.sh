#!/bin/bash
# auslagern.sh ORDNER... - kalte Daten von /media/oem/scan auf die Toshiba-Platte (NTFS, HDD, langsam) verschieben, Symlink zurueck.
# Nutzerfreigabe 6.11.: Toshiba "TOSHIBA EXT" darf als Auslagerung genutzt werden. NUR kalte Daten (nicht laufende Jobs, keine SQLite-DB im Betrieb).
# Ablauf: rsync -> Pruefsummenvergleich (rsync -c Trockenlauf, muss leer sein) -> erst dann Original entfernen und Symlink setzen. Bei Abweichung: Abbruch, nichts entfernt.
set -e
# Ziel: Standard Toshiba; AUSLAGERN_MOUNT=/media/oem/Volume waehlt die NTFS-Partition Volume (Nutzerfreigabe 7.11.)
M="${AUSLAGERN_MOUNT:-/media/oem/TOSHIBA EXT}"; Z="$M/${AUSLAGERN_ZIEL:-rc-park_auslagern}"
mountpoint -q "$M" || { echo "$M nicht eingehaengt"; exit 2; }
# Gleiches Label/Mountpunkt bei verschiedenen Platten (8.11.): AUSLAGERN_UUID erzwingt die richtige Platte
if [ -n "$AUSLAGERN_UUID" ]; then u=$(lsblk -no UUID "$(findmnt -no SOURCE "$M")" 2>/dev/null); [ "$u" = "$AUSLAGERN_UUID" ] || { echo "FALSCHE PLATTE: $M hat UUID $u, erwartet $AUSLAGERN_UUID"; exit 2; }; fi
for q in "$@"; do
  q=$(readlink -f "$q"); [ -d "$q" ] && [ ! -L "$q" ] || { echo "uebersprungen (kein Ordner/Symlink): $q"; continue; }
  case "$q" in /media/oem/scan/*) ;; *) echo "nur unter /media/oem/scan: $q"; continue;; esac
  rel=${q#/media/oem/scan/}; ziel="$Z/$rel"; mkdir -p "$(dirname "$ziel")"
  echo "== $q -> $ziel ($(du -sh "$q" | cut -f1))"
  if [ "$(findmnt -no FSTYPE "$M")" = "ext4" ]; then O1="-aH"; O2="-aHnc"; else O1="-rlt --no-perms --no-owner --no-group"; O2="-rlnc --no-perms --no-owner --no-group"; fi      # 18.11.2026: ext4-Ziel (2-TB-SSD rcdaten) mit Rechten/Hardlinks
  rsync $O1 "$q/" "$ziel/"
  d=$(rsync $O2 --itemize-changes "$q/" "$ziel/" | grep -v '^\.' | wc -l)
  [ "$d" = 0 ] || { echo "ABWEICHUNG ($d Dateien) - Original bleibt: $q"; continue; }
  rm -rf "$q" && ln -s "$ziel" "$q" && echo "ok: $q -> $M"
done
df -h /media/oem/scan "$M" | tail -2
