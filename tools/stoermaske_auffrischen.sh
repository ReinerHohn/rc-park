#!/bin/bash
# Nebenzahl prozent_foto_maskiert zum main-STL: Stoermasken (tools/foto_stoermaske.py, Cache rc-park_tmp/stoermaske) + Formliste mit --stoermaske an,
# in eigenem Worktree wie fotoform_auffrischen.sh (main bleibt unberuehrt). Ergebnis rc-park_kreis/<objekt>/fotoform_stoermaske/<sha>_<METRIK>_stoermaske.json.
# Aufruf ueber tools/job_start.sh mit JOB_GPU_MB=4000 (gemessen siehe SPEC_STOERMASKE-Bericht). Danach: python3 tools/realitaet_prozent.py <objekt> --nur_foto
set -u
OBJ=${1:-kaufhaus_grob3}; cd "$(dirname "$0")/.." || exit 1
FD=/media/oem/scan/rc-park_kreis/$OBJ/fotoform_stoermaske; mkdir -p "$FD"
PY="/media/oem/scan/venv-seg/bin/python -W ignore -I"
$PY tools/foto_stoermaske.py "$OBJ" --alle --kein_blick || exit 1
W=$FD/wt_$$; git worktree add -q --detach "$W" HEAD || exit 1
sha=$(sha256sum "$W/modelle/stl/${OBJ}_1-87.stl" | cut -c1-16)
SUF=_$(grep -m1 '^METRIK = "' "$W/tools/teil_fotoform.py" | cut -d'"' -f2)
cd "$W" && $PY tools/teil_fotoform.py "$OBJ" --stoermaske an --aus "$FD/$sha${SUF}_stoermaske.json.tmp"
rc=$?; [ $rc -eq 0 ] && mv "$FD/$sha${SUF}_stoermaske.json.tmp" "$FD/$sha${SUF}_stoermaske.json"
cd - >/dev/null && git worktree remove --force "$W"
echo "Formliste Stoermaske $sha$SUF rc=$rc"; exit $rc
