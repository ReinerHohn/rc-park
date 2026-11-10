#!/bin/bash
# Git-Objekte verlustfrei von der Root-Platte auf die Datenplatte (10.11.: .git wuchs nachts ~1 GB/h durch Kreis-Zweige mit STL/Audit-Bildern).
# Mechanismus: .git/objects/info/alternates zeigt auf $Z; Packs (unveraenderlich) werden kopiert, md5-geprueft, erst dann die bitgleichen
# Originale entfernt; zum Schluss Pruefung, dass jedes erreichbare Objekt lesbar ist. Haelt den Kreis-Merge-Lock.
# Aufruf: bash tools/git_packs_auslagern.sh [--packen]   (--packen: vorher lose Objekte mit 'git repack -d' packen, ohne prune)
set -u
cd "$(dirname "$0")/.." || exit 1
Z=/media/oem/scan/rc-park_daten/_git_objekte/rc-park
mkdir -p "$Z/pack"
exec 9>/media/oem/scan/rc-park_kreis/kaufhaus_grob3/merge.lock; flock 9
[ "${1:-}" = "--packen" ] && nice git repack -d -q
grep -qxF "$Z" .git/objects/info/alternates 2>/dev/null || echo "$Z" >> .git/objects/info/alternates
n=0
for f in .git/objects/pack/pack-*; do
  [ -e "$f" ] || continue
  cp -p "$f" "$Z/pack/" && [ "$(md5sum < "$f")" = "$(md5sum < "$Z/pack/$(basename "$f")")" ] && rm -f "$f" && n=$((n+1))
done
fehl=$(git rev-list --objects --all | cut -d' ' -f1 | git cat-file --batch-check | grep -c missing)
flock -u 9
echo "ausgelagert: $n Dateien, fehlende Objekte: $fehl"; df -h / | tail -1
[ "$fehl" = "0" ] || { echo "FEHLER: Objekte fehlen - Packs liegen weiter in $Z"; exit 1; }
