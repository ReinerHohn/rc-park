#!/bin/bash
# ketten_probelauf.sh [--plan] [--grundstand] [--rev REV] [--bis1 STUFE] [--bis2 STUFE] [--n FOTOS] [--erneuern] [--ohne-job]
#   KETTEN-PROBELAUF vor jedem Merge in main (Skill kette-schleife Schritt 5): tools/gesamtkette.py mit ALLEN Stufen ab 'vorpruefen' auf einem KLEINEN Objekt
#   (kprobe_kaufhaus: N Bilder des Historischen Kaufhauses aus dem Netz von kaufhaus_gk, Lage dort bestanden) in einer KOPIE der Zwischenstaende.
# WARUM (24.11.2026): Merge von 16 Aenderungen, Schnelltest 0 Fehler - trotzdem brach Kettenlauf 1122za nach 2 min ab (Seitenmodell-Code neu -> Netz neu ->
#   dichte Wolke "aelter als das Netz" -> Abbruch mit Handanweisung). Einzeltests pruefen Stufen einzeln, nicht Stufenfolge + vorhandene Zwischenstaende.
# Szenarien (beide muessen ohne Ablauffehler bis GESAMTKETTE_ENDE laufen):
#   1 cache: Zwischenstaende wie vom letzten Lauf (Grundstand, mit aelterem Code gerechnet) -> der neue Code muss sie weiterverwenden oder selbst neu rechnen.
#   2 marke: danach jeder Code-Stand in den Stand-Dateien verstellt + SfM-Netz "neu geschrieben" (tools/ketten_probe.py marken) -> Folgestufen muessen neu rechnen
#            (Fall 1122za), Lauf bis --bis2 (Standard 'bauen': die Stufen mit Netz-/Wolken-/Kamera-Staenden; was danach kommt, prueft Szenario 1).
# Ablauffehler = veralteter Stand, Handanweisung (--neu ...), Absturz/Traceback, Abbruch, stiller Erfolg (*_beleg), kein GESAMTKETTE_ENDE. Rote Tor-Urteile am
#   Objekt (Daten) werden gemeldet, sperren aber nicht. Exit: 0 = beide Szenarien OK, 1 = Ablauffehler, 2 = kein Urteil (Datenabbruch, z. B. Lage), 3 = Aufruf/Umgebung,
#   4 = MERGE GESPERRT (letzter Kettenlauf eines Objekts mit BESTAND RUECKSCHRITT, tools/merge_sperre.sh; 24.11.2026).
# Orte (nie Originaldaten): /media/oem/scan/rc-park_tmp/ketten_probe/{code (git archive REV), arbeit (Kopie), grundstand, ergebnis_*.json, probelauf_*.log};
#   /media/oem/scan/rc-park_daten/kprobe_kaufhaus = Verknuepfung -> arbeit (die Kette schreibt fest nach rc-park_daten/<ziel>).
#   Quelle (nur gelesen): rc-park_daten/kaufhaus_gk/pipe/kameras.json + fotos/.
# --grundstand: einmalig (und nach --erneuern) den Grundstand rechnen: Fotowahl -> anlegen -> Kette --bis vergleich -> Kopie nach grundstand/.
# --plan: Trockenlauf - nur Voraussetzungen pruefen und Befehle/Marken zeigen, nichts rechnen, nichts schreiben (RAM < 100 MB).
# --erneuern: nach erfolgreichem Szenario 1 dessen Stand als neuen Grundstand nehmen (alter -> grundstand.alt_<zeit>, Loeschen nur nach Ja des Nutzers).
# Start NUR als Job (Skill langer-job), allein (keine andere Kette):
#   JOB_RAM_MB=7000 JOB_GPU_MB=3000 bash tools/job_start.sh ketten-probe-<x> /media/oem/scan/rc-park_daten/job_logs/ketten-probe-<x>.log bash tools/ketten_probelauf.sh --rev <zweig>
set -u
HIER="$(cd "$(dirname "$0")" && pwd)"; REPO="$(git -C "$HIER" rev-parse --show-toplevel 2>/dev/null)"
PLAN=0; GRUND=0; REV=HEAD; BIS1=vergleich; BIS2=bauen; N=60; ERNEUERN=0; OHNEJOB=0
while [ $# -gt 0 ]; do case "$1" in
  --plan) PLAN=1;; --grundstand) GRUND=1;; --erneuern) ERNEUERN=1;; --ohne-job) OHNEJOB=1;;
  --rev) REV="$2"; shift;; --bis1) BIS1="$2"; shift;; --bis2) BIS2="$2"; shift;; --n) N="$2"; shift;;
  -h|--help) sed -n '2,25p' "$0"; exit 0;; *) echo "unbekannt: $1"; exit 3;; esac; shift; done
ZIEL=kprobe_kaufhaus; QUELLE=kaufhaus_gk
W=${RCPARK_PROBE_WURZEL:-/media/oem/scan/rc-park_tmp/ketten_probe}; CODE=$W/code; ARB=$W/arbeit; GS=$W/grundstand
D=/media/oem/scan/rc-park_daten/$ZIEL; QD=/media/oem/scan/rc-park_daten/$QUELLE
PY=/media/oem/scan/venv-seg/bin/python; KP="python3 -I $HIER/ketten_probe.py"
FLAGS="--ohne-video --ohne-netz --ohne-weitere-fotos --dicht-stufe grob"
ZEIT=$(date +%Y%m%d_%H%M%S); LOGP=$W/probelauf_$ZEIT.log
FEHLER=0; fehler() { echo "VORAUSSETZUNG FEHLT: $*"; FEHLER=1; }
schritt() { echo "[$(date +%H:%M:%S)] $*"; }

# ---------- Voraussetzungen (auch im Planmodus)
[ -n "$REPO" ] || fehler "kein git-Repo um $HIER"
SHA=$(git -C "$REPO" rev-parse --short "$REV" 2>/dev/null) || fehler "Stand $REV unbekannt"
mountpoint -q /media/oem/scan || fehler "/media/oem/scan nicht eingehaengt"
git -C "$REPO" cat-file -e "$REV:modelle/$QUELLE/objekt.json" 2>/dev/null || fehler "modelle/$QUELLE/objekt.json fehlt in $REV"
git -C "$REPO" cat-file -e "$REV:tools/gesamtkette.py" 2>/dev/null || fehler "tools/gesamtkette.py fehlt in $REV"
[ -x "$PY" ] || fehler "$PY fehlt"
FREI=$(df -BG --output=avail /media/oem/scan | tail -1 | tr -dc 0-9); GSG=$(du -s -BG "$GS" 2>/dev/null | cut -f1 | tr -dc 0-9); GSG=${GSG:-3}
[ "$FREI" -ge $((15 + 2 * GSG + 1)) ] || fehler "Platz /media/oem/scan ${FREI} GB < 15 GB Mindestplatz + 2x Grundstand (${GSG} GB) + Code"
if [ -e "$D" ] && [ ! -L "$D" ]; then fehler "$D ist ein echter Ordner (keine Verknuepfung des Probelaufs) - nicht anfassen"; fi
ANDERE=$(pgrep -af "[g]esamtkette\.py" | cut -c1-160)
[ -z "$ANDERE" ] || fehler "es laeuft schon eine Kette (RAM, nie zwei Ketten): $ANDERE"
if [ "$GRUND" = 1 ]; then
  [ -f "$QD/pipe/kameras.json" ] || fehler "$QD/pipe/kameras.json fehlt (Quelle der Fotowahl; Platte /media/oem/rcdaten eingehaengt?)"
  [ -d "$QD/fotos" ] || fehler "$QD/fotos fehlt"
else
  [ -f "$GS/stand.json" ] || fehler "kein Grundstand $GS/stand.json - zuerst: ketten_probelauf.sh --grundstand (als Job)"
fi
# 24.11.2026 BESTAND-SPERRE (Nutzer: "sichere das hart ab!"): hatte der letzte Kettenlauf eines Objekts einen BESTAND RUECKSCHRITT (tools/bestand_tor.py), kein Merge -> Exit 4
SPERRE=$(bash "$HIER/merge_sperre.sh" 2>&1); SPERRE_RC=$?
if [ "$SPERRE_RC" != 0 ]; then echo "$SPERRE" | grep -E "GESPERRT|=>" ; [ "${RCPARK_SPERRE_TEST:-}" = 1 ] && exit 4; [ "$PLAN" = 1 ] || exit 4; echo "PLAN: Merge waere GESPERRT (Exit 4)"; fi
[ "${RCPARK_SPERRE_TEST:-}" = 1 ] && { echo "Bestand-Sperre frei"; exit 0; }
[ "$PLAN" = 1 ] || [ "$OHNEJOB" = 1 ] || [ -n "${RCPARK_JOB:-}" ] || fehler "nicht als Job gestartet (Skill langer-job): JOB_RAM_MB=7000 JOB_GPU_MB=3000 bash tools/job_start.sh ketten-probe-$ZEIT /media/oem/scan/rc-park_daten/job_logs/ketten-probe-$ZEIT.log bash tools/ketten_probelauf.sh $*"

echo "KETTEN-PROBELAUF $( [ $PLAN = 1 ] && echo '(PLAN, nichts wird gerechnet)') Stand $REV=$SHA, Objekt $ZIEL (Quelle $QUELLE, $N Fotos), Platz ${FREI} GB, Grundstand ${GSG} GB"
KETTE() { echo "cd $CODE && RCPARK_SIFT_MAX=1600 $PY -u -I tools/gesamtkette.py $QUELLE --ziel $ZIEL $*"; }
if [ "$PLAN" = 1 ]; then
  echo "  1 Code:     git archive $SHA -> $CODE (+ Kettenausgaben des Grundstands aus $GS/root.tar)"
  echo "  2 Daten:    cp -a $GS/daten -> $ARB ; $D -> $ARB (Verknuepfung)"
  if [ "$GRUND" = 1 ]; then
    $KP fotowahl "$QD/pipe/kameras.json" "$QD/fotos" "$ARB/fotos_quelle" --n "$N" --plan || FEHLER=1
    echo "  G anlegen:  $(KETTE --ab anlegen --bis anlegen --fotos $D/fotos_quelle $FLAGS)"
    echo "  G Lauf:     $(KETTE --ab vorpruefen --bis vergleich $FLAGS)"
  else
    echo "  S1 cache:   $(KETTE --ab vorpruefen --bis $BIS1 $FLAGS)"
    echo "  S2 marke:   $KP marken $ARB $CODE/modelle/$ZIEL   (Vorschau auf dem Grundstand:)"
    $KP marken "$GS/daten" --plan | head -12
    echo "  S2 Lauf:    $(KETTE --ab vorpruefen --bis $BIS2 $FLAGS)"
    echo "  Auswertung: $KP auswerten $D/gesamtkette_bericht.json --log $D/gesamtkette.log --ab-zeile <Zeilen vor dem Lauf> --bekannt <rot im Grundstand>"
  fi
  [ "$FEHLER" = 0 ] && echo "PLAN: Voraussetzungen erfuellt" || echo "PLAN: Voraussetzungen NICHT erfuellt"
  exit $((FEHLER ? 3 : 0))
fi
[ "$FEHLER" = 0 ] || exit 3

mkdir -p "$W"; exec 9>"$W/.lock"; flock -n 9 || { echo "ein anderer Probelauf haelt $W/.lock"; exit 3; }
exec > >(tee -a "$LOGP") 2>&1

# ---------- Code (eigener Abzug, nie main/Worktree verschmutzen) + Daten (Kopie)
neu_ordner() {   # nur eigene Probe-Ordner (Marke .ketten_probe) werden ersetzt
  if [ -e "$1" ]; then [ -f "$1/.ketten_probe" ] || { echo "ABBRUCH: $1 ohne Marke .ketten_probe - nicht ersetzt"; exit 3; }; rm -rf "$1"; fi
  mkdir -p "$1" && touch "$1/.ketten_probe"; }
schritt "Code $SHA -> $CODE"; neu_ordner "$CODE"
git -C "$REPO" archive "$SHA" | tar -x -C "$CODE" || { echo "ABBRUCH: git archive"; exit 3; }
git -C "$REPO" ls-tree -r --name-only "$SHA" > "$W/getrackt.txt"
[ "$GRUND" = 1 ] || tar -x -C "$CODE" -f "$GS/root.tar" || { echo "ABBRUCH: $GS/root.tar"; exit 3; }
sleep 1; touch "$CODE/.export_marke"
neu_ordner "$ARB"
if [ "$GRUND" = 0 ]; then schritt "Daten $GS/daten -> $ARB"; cp -a "$GS/daten/." "$ARB/" || { echo "ABBRUCH: Kopie"; exit 3; }; touch "$ARB/.ketten_probe"; fi
ln -sfn "$ARB" "$D"

lauf() {   # lauf NAME ARGS... -> Kette + Auswertung, setzt RC_<NAME>
  local name=$1; shift; local lz; lz=$(cat "$D/gesamtkette.log" 2>/dev/null | wc -l); local t0=$SECONDS
  schritt "Szenario $name: gesamtkette $*"
  (cd "$CODE" && RCPARK_SIFT_MAX=1600 "$PY" -u -I tools/gesamtkette.py "$QUELLE" --ziel "$ZIEL" "$@" > "$W/kette_${name}_$ZEIT.log" 2>&1); local rck=$?
  grep -a "ERGEBNIS DES LAUFS\|^ABBRUCH" "$W/kette_${name}_$ZEIT.log" | tail -2
  $KP auswerten "$D/gesamtkette_bericht.json" --log "$D/gesamtkette.log" --ab-zeile "$lz" --szenario "$name" --bekannt "${BEKANNT:-}" --json "$W/szenario_${name}_$ZEIT.json"
  local u=$?; echo "    Kette rc $rck, $(( (SECONDS - t0) / 60 )) min Wandzeit"; eval "RC_$name=$u"; return $u; }

if [ "$GRUND" = 1 ]; then
  schritt "Fotowahl"; $KP fotowahl "$QD/pipe/kameras.json" "$QD/fotos" "$ARB/fotos_quelle" --n "$N" || exit 3
  BEKANNT=""; lauf anlegen --ab anlegen --bis anlegen --fotos "$D/fotos_quelle" $FLAGS || { echo "GRUNDSTAND: Stufe anlegen nicht in Ordnung"; exit 1; }
  lauf grundstand --ab vorpruefen --bis vergleich $FLAGS; U=$RC_grundstand
  [ "$U" = 1 ] && { echo "GRUNDSTAND: Ablauffehler - kein Grundstand"; exit 1; }
  [ "$U" = 2 ] && { echo "GRUNDSTAND: Datenabbruch (z. B. Lage) - Objekt/Fotowahl ungeeignet (mehr Fotos: --n), kein Grundstand"; exit 2; }
else
  BEKANNT=$(python3 -I -c "import json,sys; print(','.join(json.load(open(sys.argv[1])).get('rot', [])))" "$GS/stand.json")
  lauf cache --ab vorpruefen --bis "$BIS1" $FLAGS
fi
U1=${RC_grundstand:-${RC_cache:-3}}
if [ "$U1" = 0 ] && { [ "$GRUND" = 1 ] || [ "$ERNEUERN" = 1 ]; }; then
  schritt "Grundstand sichern"; [ -d "$GS" ] && mv "$GS" "$GS.alt_$ZEIT" && echo "    alter Grundstand beiseite: $GS.alt_$ZEIT (loeschen nur nach Ja des Nutzers)"
  mkdir -p "$GS" && cp -a "$ARB/." "$GS/daten/" && $KP sichern "$CODE" "$CODE/.export_marke" "$GS/root.tar" --getrackt "$W/getrackt.txt" || { echo "ABBRUCH: Grundstand sichern"; exit 3; }
  python3 -I -c "import json,sys; R=json.load(open(sys.argv[1])); json.dump(dict(rev=sys.argv[2], zeit=sys.argv[3], fotos=int(sys.argv[4]), rot=[n for n,_ in R['daten']], sekunden=R['sekunden']), open(sys.argv[5],'w'), indent=1)" \
    "$W/szenario_$( [ $GRUND = 1 ] && echo grundstand || echo cache )_$ZEIT.json" "$SHA" "$ZEIT" "$N" "$GS/stand.json"
fi
if [ "$GRUND" = 0 ] && [ "$U1" != 3 ]; then
  schritt "Szenario marke: Code-Staende verstellen, Netz neu"; $KP marken "$ARB" "$CODE/modelle/$ZIEL" | tail -8 || echo "    (nichts verstellt)"
  lauf marke --ab vorpruefen --bis "$BIS2" $FLAGS
fi
U2=${RC_marke:-0}
ERG=0; for u in $U1 $U2; do [ "$u" = 1 ] && ERG=1; done; [ $ERG = 0 ] && for u in $U1 $U2; do [ "$u" -ge 2 ] && ERG=$u; done
echo "PROBELAUF_ERGEBNIS rc=$ERG Stand $SHA (Szenario 1: $U1, Szenario 2: ${RC_marke:-nicht gelaufen}; 0 OK, 1 Ablauffehler, 2 kein Urteil) Log $LOGP"
exit $ERG
