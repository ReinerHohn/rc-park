#!/bin/bash
# runpod_dicht.sh - dichte Wolke (PatchMatch + Fusion am Stueck, volle Bildgroesse) auf einem Runpod-Pod ODER lokal (--lokal) mit HARTER KOSTENBREMSE.
# Anleitung, Befehlsliste, Kosten: tools/cloud/CLOUD_RUNPOD.md. Rechenkern: tools/cloud/runpod_dicht.py. Paket: tools/cloud/runpod_paket.py.
# Verwandt: tools/cloud/vast.sh (vast.ai, gleiche Idee, ungetestet), tools/dicht_modell.py (lokale Stufe), tools/wolke_vereinigen.py (danach lokal).
# Vorlaeufer: tools/handy_dicht_nachlauf.sh / tools/handy_fusion_nachlauf.sh (lokal, Fusion in Kacheln wegen 15 GB RAM).
#
# Aufruf (Pod):   nohup bash runpod_dicht.sh --paket /workspace/handy_teil.tar.zst --stunden 3 > /workspace/lauf.out 2>&1 &
# Aufruf (lokal): bash runpod_dicht.sh --lokal --paket <ordner|tar.zst> --arbeit <dir> --ergebnis <dir> --py /media/oem/scan/venv-colmap/bin/python
# Optionen: --paket P (tar.zst oder entpackter Ordner)  --arbeit D (Std. /root/arbeit = Container-Platte, beim Stoppen weg)
#           --ergebnis D (Std. /workspace/ergebnis = Volume, bleibt beim Stoppen)  --stunden H (Zeitlimit Rechnen, Std. 3)
#           --warte_min M (nach Ende Zeit zum Herunterladen, dann Selbststopp; Std. 45; Fehler: --warte_fehler_min 20)
#           --stopp stop|delete|aus (Std. stop: Volume mit Ergebnis bleibt, kostet nur Speicher; delete = alles weg)
#           --py PY (vorhandenes Python mit pycolmap-cuda12; sonst venv + pip install pycolmap-cuda12==4.2.1)
#           --nur_pruefen (Dry-Run), alles nach -- geht an runpod_dicht.py (z. B. -- --groesse 0 --window_step 2)
# KOSTENBREMSE: (1) ohne funktionierendes runpodctl + RUNPOD_POD_ID/RUNPOD_API_KEY (automatisch im Pod gesetzt) startet auf dem Pod NICHTS;
#   (2) Waechter (setsid, eigener Prozess) beendet nach --stunden den Rechenjob, packt, stoppt den Pod (runpodctl pod stop $RUNPOD_POD_ID;
#   alte CLI: runpodctl stop pod); (3) jeder Fehler -> packen -> Selbststopp nach --warte_fehler_min; (4) Erfolg -> Selbststopp nach --warte_min.
#   Wichtig: der Hauptprozess eines Pods darf nicht einfach enden (Pod startet neu und kostet weiter) - nur der API-Stopp beendet die Abrechnung der GPU.
set -uo pipefail
HIER="$(cd "$(dirname "$0")" && pwd)"
if [ "${1:-}" = "--_nur_stopp" ]; then   # interner Einstieg des Waechters (Umgebung: STOPP ERG LOG RUNPOD_POD_ID)
  t() { echo "$(date '+%F %T') $*" >> "$LOG"; }
  if [ "$STOPP" = aus ]; then t "SELBSTSTOPP ($2): Modus aus (lokal/Test) - nichts zu stoppen"; exit 0; fi
  t "SELBSTSTOPP ($2): runpodctl pod $STOPP $RUNPOD_POD_ID"
  if [ "$STOPP" = delete ]; then runpodctl pod delete "$RUNPOD_POD_ID" >>"$LOG" 2>&1 || runpodctl remove pod "$RUNPOD_POD_ID" >>"$LOG" 2>&1
  else runpodctl pod stop "$RUNPOD_POD_ID" >>"$LOG" 2>&1 || runpodctl stop pod "$RUNPOD_POD_ID" >>"$LOG" 2>&1; fi
  t "Stopp-Befehl rc=$? (laeuft der Pod danach noch: von aussen stoppen!)"; exit 0
fi
PAKET=""; ARBEIT=/root/arbeit; ERG=/workspace/ergebnis; STD=3; WARTE=45; WARTE_F=20; STOPP=stop; LOKAL=0; PY=""; PRUEF=0; REST=()
while [ $# -gt 0 ]; do case "$1" in
  --paket) PAKET=$2; shift 2;; --arbeit) ARBEIT=$2; shift 2;; --ergebnis) ERG=$2; shift 2;; --stunden) STD=$2; shift 2;;
  --warte_min) WARTE=$2; shift 2;; --warte_fehler_min) WARTE_F=$2; shift 2;; --stopp) STOPP=$2; shift 2;; --lokal) LOKAL=1; shift;;
  --py) PY=$2; shift 2;; --nur_pruefen) PRUEF=1; shift;; --) shift; REST=("$@"); break;; *) echo "unbekannt: $1"; exit 2;; esac; done
[ -n "$PAKET" ] || { sed -n 2,20p "$0"; exit 2; }
mkdir -p "$ERG" "$ARBEIT"; LOG=$ERG/lauf.log
t() { echo "$(date '+%F %T') $*" | tee -a "$LOG"; }
[ "$LOKAL" = 1 ] && STOPP=aus
SEK=$(python3 -c "print(int(float('$STD')*3600))")

packen() {
  ( cd "$ERG" && tar -cf ergebnis.tar --exclude=ergebnis.tar fused.ply protokoll.log protokoll.json lauf.log patch-match.cfg fusion.cfg 2>/dev/null; sha256sum ergebnis.tar > ergebnis.tar.sha256 )
  t "gepackt: $ERG/ergebnis.tar $(du -h "$ERG/ergebnis.tar" 2>/dev/null | cut -f1)"
}
waechter_start() {  # $1 Sekunden, $2 Grund; ersetzt einen frueheren Waechter. Eigener Prozess (setsid), ueberlebt SSH-Abbruch und dieses Skript.
  [ -f "$ERG/waechter.pid" ] && kill -- -"$(cat "$ERG/waechter.pid")" 2>/dev/null
  setsid nohup bash -c "
    sleep $1; echo \"\$(date '+%F %T') ZEITLIMIT ($2) nach $1 s\" >> '$LOG'
    if [ -f '$ERG/kern.pid' ] && kill -0 \$(cat '$ERG/kern.pid') 2>/dev/null; then kill -TERM \$(cat '$ERG/kern.pid'); sleep 30; kill -KILL \$(cat '$ERG/kern.pid') 2>/dev/null; fi
    RUNPOD_POD_ID='${RUNPOD_POD_ID:-}' STOPP='$STOPP' ERG='$ERG' LOG='$LOG' bash '$HIER/runpod_dicht.sh' --_nur_stopp \"$2\"
  " >/dev/null 2>&1 < /dev/null &
  echo $! > "$ERG/waechter.pid"; t "Waechter: Selbststopp in $1 s ($2), PID $!"
}

t "START runpod_dicht.sh lokal=$LOKAL paket=$PAKET arbeit=$ARBEIT ergebnis=$ERG limit=${STD} h stopp=$STOPP"

# 1. Kostenbremse ZUERST pruefen (auf dem Pod)
if [ "$LOKAL" = 0 ]; then
  [ -n "${RUNPOD_POD_ID:-}" ] || { t "ABBRUCH: RUNPOD_POD_ID fehlt - kein Runpod-Pod? (lokal: --lokal)"; exit 7; }
  command -v runpodctl >/dev/null || { t "ABBRUCH: runpodctl fehlt im Pod - ohne Selbststopp rechnet hier nichts"; exit 7; }
  if ! { runpodctl pod get "$RUNPOD_POD_ID" >/dev/null 2>&1 || runpodctl get pod "$RUNPOD_POD_ID" >/dev/null 2>&1; }; then
    t "ABBRUCH: runpodctl kann diesen Pod nicht abfragen (RUNPOD_API_KEY?) - Selbststopp nicht belegt, rechne nicht"; exit 7; fi
  t "Kostenbremse: runpodctl erreicht Pod $RUNPOD_POD_ID"
fi
waechter_start "$SEK" "Rechen-Zeitlimit ${STD} h"
ende() {  # $1 rc
  packen
  if [ "$1" = 0 ]; then waechter_start $((WARTE*60)) "fertig, Download-Fenster ${WARTE} min"; t "FERTIG rc=0 - jetzt herunterladen: $ERG/ergebnis.tar"
  else waechter_start $((WARTE_F*60)) "Fehler rc=$1, Fenster ${WARTE_F} min"; t "ABBRUCH rc=$1 - Protokoll $LOG"; fi
  echo "JOB_ENDE rc=$1" >> "$LOG"; exit "$1"
}
trap 'ende 98' INT TERM

# 2. Umgebung
if [ -z "$PY" ]; then
  command -v zstd >/dev/null || { apt-get update -qq >/dev/null && apt-get install -y -qq zstd >/dev/null; }
  python3 -m venv /root/venv && /root/venv/bin/pip install -q "pycolmap-cuda12==4.2.1" pillow >>"$LOG" 2>&1 || { t "ABBRUCH: pip install pycolmap-cuda12"; ende 8; }
  PY=/root/venv/bin/python
fi
$PY -I -c "import pycolmap,sys;print('pycolmap',pycolmap.__version__,'cuda',pycolmap.has_cuda);sys.exit(0 if pycolmap.has_cuda else 1)" >>"$LOG" 2>&1 || { t "ABBRUCH: pycolmap ohne CUDA"; ende 8; }
nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader >>"$LOG" 2>&1
t "Umgebung ok: $PY ($(tail -2 "$LOG" | head -1))"

# 3. Paket
if [ -d "$PAKET" ]; then P=$PAKET
else
  [ -f "$PAKET.sha256" ] && { ( cd "$(dirname "$PAKET")" && sha256sum -c "$(basename "$PAKET").sha256" ) >>"$LOG" 2>&1 || { t "ABBRUCH: Pruefsumme Paket falsch"; ende 9; }; t "Pruefsumme ok"; }
  mkdir -p "$ARBEIT/paket"; tar -I zstd -xf "$PAKET" -C "$ARBEIT/paket" || { t "ABBRUCH: entpacken"; ende 9; }
  P=$(dirname "$(ls -d "$ARBEIT"/paket/*/paket.json | head -1)")
fi
t "Paket: $P ($(ls "$P/bilder" | wc -l) Bilder)"

# 4. Rechnen (Rueckgabewert direkt, nie durch Pipe verlieren)
A=(); [ "$PRUEF" = 1 ] && A=(--nur_pruefen)
$PY -I "$HIER/runpod_dicht.py" "$P" "$ARBEIT/rechnen" "$ERG" "${A[@]}" "${REST[@]}" >>"$ERG/kern.out" 2>&1 &
echo $! > "$ERG/kern.pid"; t "Rechenkern PID $! (Ausgabe $ERG/kern.out, Takt-Protokoll $ERG/protokoll.log)"
wait "$!"; RC=$?
t "Rechenkern rc=$RC; $(grep -E 'FERTIG|ABBRUCH|DRY-RUN|VERKLEINERT' "$ERG/protokoll.log" 2>/dev/null | tail -2 | tr '\n' ' ')"
ende "$RC"
