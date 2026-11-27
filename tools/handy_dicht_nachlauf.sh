#!/bin/bash
# handy_dicht_nachlauf.sh - zweite Nachtstufe nach tools/handy_nachlauf.sh: dichte Wolke der registrierten Handyfotos 26.11. (Schwabentor).
# Wartet auf "FERTIG" in $Z/nachlauf.log, dann: Union-Bilderordner -> dichte_nachtrag (GPU, ueber job_start gebucht) -> kachelfusion -> wolke_vereinigen.
# Befehle wie die erste Handy-Wolke vom 26.11. (journalctl: handy-dicht-1126b / handy-fusion-1126b / handy-vereinigen-1126). Protokoll: $Z/dicht_nachlauf.log
Z=${Z:-/media/oem/rcdaten/rc-park_daten_neu/zusatz_20261126_voll}
D=${D:-/media/oem/scan/rc-park_daten/schwabentor-1122}
O=/media/oem/rcdaten/tmp/handy2   # Ergebnisordner (alles auf rcdaten)
AUS=modelle/schwabentor-1122/messprotokoll/SFM-AUSRICHTUNG-schwabentor-1122.json
PY=/media/oem/scan/venv-colmap/bin/python
cd "$(dirname "$0")/.." || exit 2
t() { echo "$(date '+%F %T') $*"; }
warte() { # warte LOG MAXSEKUNDEN: bis JOB_ENDE im Log; Rueckgabe = rc des Jobs
  local l=$1 m=$2 i=0; while [ $i -lt $m ]; do grep -q '^JOB_ENDE' "$l" 2>/dev/null && { grep '^JOB_ENDE' "$l" | tail -1 | sed 's/.*rc=//'; return 0; }; sleep 30; i=$((i+30)); done; echo 99
}
t "warte auf FERTIG in nachlauf.log (max 6 h)"
for i in $(seq 1 720); do grep -q 'FERTIG' "$Z/nachlauf.log" && break; grep -q 'ABBRUCH' "$Z/nachlauf.log" && { t "ABBRUCH: Registrierungsstufe fehlgeschlagen, keine dichte Wolke"; exit 1; }; sleep 30; done
grep -q 'FERTIG' "$Z/nachlauf.log" || { t "ABBRUCH: Registrierung nicht rechtzeitig fertig"; exit 1; }
[ -f "$Z/lg/sparse_handy/0/images.bin" ] || { t "ABBRUCH: $Z/lg/sparse_handy/0 fehlt"; exit 1; }
mkdir -p "$O"; U=$O/bilder_union
if [ ! -d "$U" ]; then mkdir -p "$U"; cp -a /media/oem/rcdaten/tmp/handy_bilder_union/. "$U"/; fi
# Namen der Registrierung IMMER auf die Bilder von $Z/bilder (Wasserzeichen-Streifen abgeschnitten, Hoehe 1425 statt 1500); sonst passt Kamera nicht zum Bild (Undistort-Abbruch 27.11.)
for f in "$Z"/bilder/*.jpg; do ln -sfn "$f" "$U/$(basename "$f")"; done
t "Union-Ordner: $(ls "$U" | wc -l) Bilder"
# 1. Tiefenkarten (GPU)
L1=$O/dicht.log; rm -f "$L1"
PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True JOB_GPU_MB=6500 JOB_RAM_MB=6000 bash tools/job_start.sh handy2-dicht "$L1" $PY -I tools/dichte_nachtrag.py "$Z/lg/sparse_handy/0" "$D/pipe/dicht" "$U" "$O/dicht" --zelle -30 30 -30 30 --ausrichtung $AUS --min_punkte 20 --max_bilder 200 --praefix IMG_20261126 --window_step 1
t "START dichte_nachtrag"; rc=$(warte "$L1" 21600); t "ENDE dichte_nachtrag rc=$rc"; [ "$rc" = 0 ] || { t "ABBRUCH dichte_nachtrag"; exit 1; }
# 2. Fusion (CPU)
L2=$O/fusion.log; rm -f "$L2"
JOB_RAM_MB=11000 bash tools/job_start.sh handy2-fusion "$L2" $PY -I tools/kachelfusion.py "$O/dicht" "$O/handy_fusion.ply" --ausrichtung $AUS --box -30 30 -30 30 --ohne_muster LMS3Va6psfY
t "START kachelfusion"; rc=$(warte "$L2" 14400); t "ENDE kachelfusion rc=$rc"; [ "$rc" = 0 ] || { t "ABBRUCH kachelfusion"; exit 1; }
# 3. Vereinigen mit der bestehenden dichten Wolke
L3=$O/vereinigen.log; rm -f "$L3"
JOB_RAM_MB=11000 bash tools/job_start.sh handy2-vereinigen "$L3" $PY -I tools/wolke_vereinigen.py "$D/pipe/dicht/fused.ply" "$O/handy_vereint.ply" --ausrichtung $AUS --quelle handy_fusion="$O/handy_fusion.ply" --npy "$O/handy_vereint"
t "START wolke_vereinigen"; rc=$(warte "$L3" 7200); t "ENDE wolke_vereinigen rc=$rc"; [ "$rc" = 0 ] || { t "ABBRUCH wolke_vereinigen"; exit 1; }
t "FERTIG: dichte Wolke $O/handy_vereint.ply (Bruecke/Treppe sichtbar? Bild rendern)"
