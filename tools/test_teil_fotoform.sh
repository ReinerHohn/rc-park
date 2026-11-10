#!/bin/bash
# Beweis (L-KR25): Varianten per Generator; bestanden 10.11. 11:20: OG-Fenster F1 0,891 -> 0,860 (u+0,3 m) / 0,826 (1 statt 3 Lichter), rumpf_og 0,750 -> 0,711 / 0,715.
# Gegenprobe teil_fotoform: Varianten per GENERATOR (nicht zusammengesetzt). Erwartung: V1 (u+0,3 m) und V2 (1 statt 3 Lichter) schlechter als V0.
set -u
S=${1:-/tmp/gegenprobe_form}; mkdir -p $S
cd /home/oem/git/rc-park
for v in V0 V1 V2; do
  W=/media/oem/scan/rc-park_kreis/kaufhaus_grob3/gp_$v; git worktree add -q --detach $W HEAD
  python3 - $W $v <<'PY'
import json,sys
W,v=sys.argv[1:]; p=W+'/modelle/kaufhaus_grob3/objekt.json'; o=json.load(open(p))
for b in o['bauteile']:
  if b['typ']=='fensterreihe:og':
    if v=='V1': b['u_mitte']=round(b['u_mitte']+0.3,3)
    if v=='V2': b['n_lichter']=1
json.dump(o,open(p,'w'),ensure_ascii=False,indent=1)
PY
  ( cd $W && GEN=$(python3 -c "import json;print(json.load(open('modelle/kaufhaus_grob3/objekt.json'))['generator'])") && BAUTEILE_AUS=$W/_teile bash -c "$GEN" > $S/gp_$v.gen.log 2>&1
    /media/oem/scan/venv-seg/bin/python -W ignore -I tools/teil_fotoform.py kaufhaus_grob3 --teile_dir $W/_teile --nur fensterreihe__og,quader__rumpf_og --fotos 6120,6119,6132,6161,6115,6145 --aus $S/gp_$v.json --bilder --bilder_dir $S/gp_bilder --etikett $v 2>&1 | grep -E "fensterreihe|rumpf" | sed "s/^/$v /" )
  git worktree remove --force $W
done
