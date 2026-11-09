#!/usr/bin/env bash
# koerper_kette.sh GITTER.json AUSDIR [AUDITDIR] - Stufe 11 der Gitterkette: Gitter -> Rohkoerper -> Fenster/Erker-Analyse -> Flaeche-vs-Oeffnung (Laube)
# -> Konsolen-Wiederholung -> Koerper v11 (bauen) -> Pruefung (Wolkennaehe, Vergleichsbilder, Slicer-Vorcheck) -> STL (m) + H0-STL (1:87 mm).
# Parameter nur aus dem Gitter + Datenordner (Wolke, Kameras, Stabilitaetskarten, Fotos, formen/helme.json, formen/baluster_abgenommen.json, kurven/arkaden.json).
# Datenordner = Grossvater des Gitters (…/kaufhaus_alle/kette_video/gitter.json -> …/kaufhaus_alle) oder RCPARK_DATEN. Nichts Objektspezifisches.
set -euo pipefail
G=$(readlink -f "$1"); AUS="$2"; AUDIT="${3:-modelle/kaufhaus_grob3/audit/koerper_v11}"
DATEN="${RCPARK_DATEN:-$(dirname "$(dirname "$G")")}"
PY_M="${PY_MANIFOLD:-$HOME/.venvs/rcpark/bin/python}"; PY_S="${PY_SEG:-/media/oem/scan/venv-seg/bin/python}"
WOLKE="${WOLKE:-$DATEN/kanten3d_k80.npz}"; KAM="${KAM:-$DATEN/sfm/kam_lot2.json}"; STABIL="${STABIL:-$DATEN/stabil}"; BILDER="${BILDER:-$DATEN/bilder}"
HELME="${HELME:-$DATEN/formen/helme.json}"; BAL="${BAL:-$DATEN/formen/baluster_abgenommen.json}"
T="$(dirname "$(readlink -f "$0")")"; mkdir -p "$AUS" "$AUDIT"; LOG="$AUS/koerper_kette.log"; exec > >(tee -a "$LOG") 2>&1
echo "[$(date +%T)] koerper_kette: Gitter $G -> $AUS (Daten $DATEN)"
for f in "$WOLKE" "$KAM" "$HELME" "$BAL"; do [ -e "$f" ] || { echo "FEHLT: $f"; exit 2; }; done
# Quellen der Formen: Schluessel im Gitter oder Standardpfade (im Log genannt)
"$PY_S" -I - "$G" "$HELME" "$BAL" "$DATEN/kurven/arkaden.json" <<'PY'
import json, sys, os
d = json.load(open(sys.argv[1])); S = d.get("segmente", []); q = sorted(set(s[2] for s in S))
print(f"Gitter: {len(S)} Segmente, Quellen {q}, Schluessel {sorted(k for k in d if k != 'segmente')}")
for k, f in (("helme", sys.argv[2]), ("baluster", sys.argv[3]), ("arkaden/boegen", sys.argv[4])):
    im = d.get(k.split('/')[0]) or d.get(k.split('/')[-1])
    print(f"  Form {k}: " + (f"{len(im)} im Gitter" if im else f"nicht im Gitter -> Standardpfad {f} ({'vorhanden' if os.path.exists(f) else 'FEHLT'})"))
print(f"  Form saeulen: {len(d.get('saeulen', []))} im Gitter" + ("" if d.get('saeulen') else " - FEHLT (Pfeiler/Arkaden koennen nicht gebaut werden)"))
PY
echo "[$(date +%T)] 1 Rohkoerper (gitter_koerper bauen)";            "$PY_M" "$T/gitter_koerper.py" bauen "$G" "$AUS" --name rohkoerper_v7 | tail -3
echo "[$(date +%T)] 2 Fenster/Erker-Analyse (Fotobeleg)";           "$PY_S" -I "$T/koerper_fenster_erker.py" analyse "$G" "$AUS/rohkoerper_v7.json" "$KAM" "$STABIL" "$AUS/fenster_erker_v9.json" --helme "$HELME" | grep -v "^  Pfosten\|^  Horizontal" | tail -12
echo "[$(date +%T)] 3 Koerper v10 (Balkon/Konsolen-Bloecke als Eingabe fuer Test und Wiederholung)"; "$PY_M" "$T/koerper_v10.py" bauen "$G" "$AUS/rohkoerper_v7.json" "$AUS/fenster_erker_v9.json" "$HELME" "$AUS" | grep "Export\|Konsolen\|Balkon:"
echo "[$(date +%T)] 4 Flaeche vs. Oeffnung (Erdgeschoss)";          "$PY_S" -I "$T/flaeche_oder_oeffnung.py" "$WOLKE" "$KAM" "$AUS/rohkoerper_v7.json" "$AUS/koerper_v10.json" "$AUS/flaechen_eg_v11_zpuffer.json" --zpuffer --innen | grep -v "^   z"
echo "[$(date +%T)] 5 Konsolen-Wiederholung (Fotobeleg)";           "$PY_S" -I "$T/koerper_v11.py" analyse_konsolen "$G" "$AUS/koerper_v10.json" "$KAM" "$STABIL" "$AUS" | tail -3
echo "[$(date +%T)] 5b Konsolen einzeln + Musterzelle (Wolke/Fotos getrennt, Entscheidregel)"; "$PY_S" -I "$T/konsolen_zelle.py" "$AUS/koerper_v10.json" "$AUS/konsolen_v11.json" "$KAM" "$STABIL" "$WOLKE" --bilder "$BILDER" --audit "$AUDIT" | grep -v "^  Instanz" | tail -6
echo "[$(date +%T)] 6 Koerper v11 bauen";                           "$PY_M" "$T/koerper_v11.py" bauen "$G" "$AUS/rohkoerper_v7.json" "$AUS/fenster_erker_v9.json" "$HELME" "$BAL" "$AUS" | grep -v "^  Ebene\|^  Saeule" | tail -14
echo "[$(date +%T)] 7 Pruefung (Wolkennaehe, Vergleichsbilder, Slicer-Vorcheck)"; "$PY_S" -I "$T/koerper_v11.py" pruefen "$AUS" "$WOLKE" "$KAM" "$BILDER" "$AUDIT" | grep -v Warning | grep "wasserdicht\|naeher\|z  *[0-9]\|ueberhang_gt60_anteil\|unter_0"
echo "[$(date +%T)] 8 Kantenliste mit Kopplungsgruppen (fuer kanten_tor.py)"; "$PY_S" -I "$T/koerper_kantenliste.py" export "$AUS/koerper_v11.json" "$AUS/fenster_erker_v9.json" "$AUS/konsolen_v11.json" "$AUS/koerper_v11_kantenliste.json"
echo "[$(date +%T)] fertig: $AUS/koerper_v11.stl (m), $AUS/koerper_v11_h0.stl (1:87 mm), Bilder $AUDIT, Log $LOG"
