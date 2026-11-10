#!/bin/bash
# Formliste je Teil (teil_fotoform ueber alle kalibrierten Fotos) fuer den aktuellen main-Stand, in einem eigenen Worktree (main bleibt unberuehrt).
# Vom kreis_regler gestartet, wenn die neueste Formliste nicht zum STL von main passt. Ergebnis: rc-park_kreis/<objekt>/fotoform/<stl_sha>.json + bilder/.
set -u
OBJ=${1:-kaufhaus_grob3}; cd "$(dirname "$0")/.." || exit 1
FD=/media/oem/scan/rc-park_kreis/$OBJ/fotoform; mkdir -p "$FD"
W=$FD/wt_$$; git worktree add -q --detach "$W" HEAD || exit 1
sha=$(sha256sum "$W/modelle/stl/${OBJ}_1-87.stl" | cut -c1-16)
# METRIK-VERSION im Dateinamen (Cache-Schluessel; Gegenstueck: bauteil_kreis.metrik_suffix, kreis_regler.form_auffrischen): v2 = mit Fotowolken-Verdeckung
SUF=_$(grep -m1 '^METRIK = "' "$W/tools/teil_fotoform.py" | cut -d'"' -f2)   # aus teil_fotoform.py (Quelle der Wahrheit)
shaf=$sha$SUF
# Aufloesungs-Treppe (10.11. abends): zuerst die HALBE Formliste (Vorpruefung des Kreises, ~10x schneller), dann die volle (Endtor)
FH=/media/oem/scan/rc-park_kreis/$OBJ/fotoform_halb; mkdir -p "$FH"
if [ ! -s "$FH/$shaf.json" ]; then
  (cd "$W" && RCPARK_FOTO_SKALA=0.5 /media/oem/scan/venv-seg/bin/python -W ignore -I tools/teil_fotoform.py "$OBJ" --aus "$FH/$shaf.json.tmp") && mv "$FH/$shaf.json.tmp" "$FH/$shaf.json"
  echo "Formliste halb $shaf rc=$?"
fi
if [ -n "${NUR_HALB:-}" ]; then cd /home/oem/git/rc-park && git worktree remove --force "$W"; exit 0; fi
cd "$W" && /media/oem/scan/venv-seg/bin/python -W ignore -I tools/teil_fotoform.py "$OBJ" --aus "$FD/$shaf.json.tmp" --bilder --bilder_dir "$FD/bilder_$shaf"
rc=$?; [ $rc -eq 0 ] && mv "$FD/$shaf.json.tmp" "$FD/$shaf.json"
cd /home/oem/git/rc-park && git worktree remove --force "$W"
echo "Formliste $shaf rc=$rc"
[ $rc -eq 0 ] && python3 tools/realitaet_prozent.py "$OBJ" --nur_foto   # Realitaetszahl am Foto (Hauptzahl seit 10.11. abends) zu diesem main-Stand
exit $rc
