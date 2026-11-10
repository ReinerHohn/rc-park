#!/bin/bash
# Formliste je Teil (teil_fotoform ueber alle kalibrierten Fotos) fuer den aktuellen main-Stand, in einem eigenen Worktree (main bleibt unberuehrt).
# Vom kreis_regler gestartet, wenn die neueste Formliste nicht zum STL von main passt. Ergebnis: rc-park_kreis/<objekt>/fotoform/<stl_sha>.json + bilder/.
set -u
OBJ=${1:-kaufhaus_grob3}; cd "$(dirname "$0")/.." || exit 1
FD=/media/oem/scan/rc-park_kreis/$OBJ/fotoform; mkdir -p "$FD"
W=$FD/wt_$$; git worktree add -q --detach "$W" HEAD || exit 1
sha=$(sha256sum "$W/modelle/stl/${OBJ}_1-87.stl" | cut -c1-16)
cd "$W" && /media/oem/scan/venv-seg/bin/python -W ignore -I tools/teil_fotoform.py "$OBJ" --aus "$FD/$sha.json.tmp" --bilder --bilder_dir "$FD/bilder_$sha"
rc=$?; [ $rc -eq 0 ] && mv "$FD/$sha.json.tmp" "$FD/$sha.json"
cd /home/oem/git/rc-park && git worktree remove --force "$W"
echo "Formliste $sha rc=$rc"
[ $rc -eq 0 ] && python3 tools/realitaet_prozent.py "$OBJ" --nur_foto   # Realitaetszahl am Foto (Hauptzahl seit 10.11. abends) zu diesem main-Stand
exit $rc
