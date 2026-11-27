#!/bin/bash
# handy_dicht_nachlauf.sh - zweite Nachtstufe nach tools/handy_nachlauf.sh: dichte Wolke der registrierten Handyfotos 26.11. (Schwabentor).
# Wartet auf "FERTIG" in $Z/nachlauf.log, dann: Union-Bilderordner -> dichte_nachtrag (GPU, ueber job_start gebucht) -> kachelfusion -> wolken_vereinen_stufe.sh (alle Wolken des Objekts).
# Befehle wie die erste Handy-Wolke vom 26.11. (journalctl: handy-dicht-1126b / handy-fusion-1126b / handy-vereinigen-1126). Protokoll: $Z/dicht_nachlauf.log
# Qualitaetstor (27.11.): SP = Eingangs-Rekonstruktion (Standard Registrierung $Z/lg/sparse_handy/0, KEIN Teilmodell -> Tor entfaellt, wird protokolliert).
# Ist SP ein eingepasstes Teilmodell (<teil>/<n>_ausgerichtet) oder EIN gesetzt, rechnet die Wolke nur bei status "ausgerichtet" in EIN (tools/teilmodell_ausrichten.py --tor).
Z=${Z:-/media/oem/rcdaten/rc-park_daten_neu/zusatz_20261126_voll}
D=${D:-/media/oem/scan/rc-park_daten/schwabentor-1122}
O=/media/oem/rcdaten/tmp/handy2   # Ergebnisordner (alles auf rcdaten)
AUS=modelle/schwabentor-1122/messprotokoll/SFM-AUSRICHTUNG-schwabentor-1122.json
PY=/media/oem/scan/venv-colmap/bin/python
SP=${SP:-$Z/lg/sparse_handy/0}
case "${SP%/}" in *_ausgerichtet|*_unsicher) b=$(basename "${SP%/}"); b=${b%_ausgerichtet}; EIN=${EIN:-$(dirname "${SP%/}")/ausrichtung.json}; TM=${TM:-${b%_unsicher}};; esac
cd "$(dirname "$0")/.." || exit 2
t() { echo "$(date '+%F %T') $*"; }
warte() { # warte LOG MAXSEKUNDEN: bis JOB_ENDE im Log; Rueckgabe = rc des Jobs
  local l=$1 m=$2 i=0; while [ $i -lt $m ]; do grep -q '^JOB_ENDE' "$l" 2>/dev/null && { grep '^JOB_ENDE' "$l" | tail -1 | sed 's/.*rc=//'; return 0; }; sleep 30; i=$((i+30)); done; echo 99
}
t "warte auf FERTIG in nachlauf.log (max 6 h)"
for i in $(seq 1 720); do grep -q 'FERTIG' "$Z/nachlauf.log" && break; grep -q 'ABBRUCH' "$Z/nachlauf.log" && { t "ABBRUCH: Registrierungsstufe fehlgeschlagen, keine dichte Wolke"; exit 1; }; sleep 30; done
grep -q 'FERTIG' "$Z/nachlauf.log" || { t "ABBRUCH: Registrierung nicht rechtzeitig fertig"; exit 1; }
[ -f "$SP/images.bin" ] || { t "ABBRUCH: $SP fehlt"; exit 1; }
if [ -n "$EIN" ]; then g=$($PY -I tools/teilmodell_ausrichten.py --tor "$EIN" --modell "${TM:-0}"); rc=$?; t "$g"; [ "$rc" = 0 ] || { t "ABBRUCH: Einpassung nicht belegt (Qualitaetstor), keine dichte Wolke auf $SP - erst tools/teilmodell_spuren_einpassen.py + Gegenproben"; exit 1; }
else t "Qualitaetstor entfaellt: $SP ist Registrierung, kein eingepasstes Teilmodell (EIN nicht gesetzt)"; fi
mkdir -p "$O"; U=$O/bilder_union
if [ ! -d "$U" ]; then mkdir -p "$U"; cp -a /media/oem/rcdaten/tmp/handy_bilder_union/. "$U"/; fi
# Namen der Registrierung IMMER auf die Bilder von $Z/bilder (Wasserzeichen-Streifen abgeschnitten, Hoehe 1425 statt 1500); sonst passt Kamera nicht zum Bild (Undistort-Abbruch 27.11.)
for f in "$Z"/bilder/*.jpg; do ln -sfn "$f" "$U/$(basename "$f")"; done
t "Union-Ordner: $(ls "$U" | wc -l) Bilder"
# 1. Tiefenkarten (GPU)
L1=$O/dicht.log; rm -f "$L1"
PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True JOB_GPU_MB=6500 JOB_RAM_MB=6000 bash tools/job_start.sh handy2-dicht "$L1" $PY -I tools/dichte_nachtrag.py "$SP" "$D/pipe/dicht" "$U" "$O/dicht" --zelle -30 30 -30 30 --ausrichtung $AUS --min_punkte 20 --max_bilder 200 --praefix IMG_20261126 --window_step 1
t "START dichte_nachtrag"; rc=$(warte "$L1" 21600); t "ENDE dichte_nachtrag rc=$rc"; [ "$rc" = 0 ] || { t "ABBRUCH dichte_nachtrag"; exit 1; }
# 2. Fusion (CPU)
L2=$O/fusion.log; rm -f "$L2"
JOB_RAM_MB=11000 bash tools/job_start.sh handy2-fusion "$L2" $PY -I tools/kachelfusion.py "$O/dicht" "$O/handy_fusion.ply" --ausrichtung $AUS --box -30 30 -30 30 --ohne_muster LMS3Va6psfY
t "START kachelfusion"; rc=$(warte "$L2" 14400); t "ENDE kachelfusion rc=$rc"; [ "$rc" = 0 ] || { t "ABBRUCH kachelfusion"; exit 1; }
# 3. Vereinigen mit ALLEN Wolken des Objekts (27.11.2026, Nutzer: "Immer vereinen"; vorher nur mit pipe/dicht/fused.ply): Register modelle/<obj>/wolken.json, Lagetore
OBJ=${OBJ:-modelle/schwabentor-1122/objekt.json}
bash tools/wolken_vereinen_stufe.sh "$OBJ" "${WV_NAME:-handy2_fusion}" "$O/handy_fusion.ply" "sfm:$AUS" "${EIN:+teilmodell:$EIN#${TM:-0}}"; rc=$?
t "ENDE wolken_vereinen rc=$rc (3 = nicht vereint/ROT, Grund oben)"; [ "$rc" = 0 ] || [ "$rc" = 3 ] || { t "ABBRUCH wolken_vereinen"; exit 1; }
t "FERTIG: dichte Wolke $O/handy_fusion.ply, vereint: /media/oem/rcdaten/tmp/wolken_vereint/$(basename "$(dirname "$OBJ")")/ (Bruecke/Treppe sichtbar? Bild rendern)"
