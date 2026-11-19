#!/bin/bash
# 0-3d-modell.sh - EIN Startbefehl fuer ein 3D-Modell (Nutzer 19.11.2026: "ein Bash-Skript, das alles startet und die Python-Umgebung einrichtet";
# Nummer 0 im Namen, damit es im Ordner immer oben steht).
#
#   ./0-3d-modell.sh Martinstor Freiburg      neues Modell oder laufendes/fertiges wieder aufnehmen (fragt nach)
#   ./0-3d-modell.sh Martinstor Freiburg --ja alle Fragen mit dem Vorschlag beantworten
#   ./0-3d-modell.sh --status                 alle Laeufe, die ueber dieses Skript gestartet wurden
#   ./0-3d-modell.sh --trocken Martinstor Freiburg   nur zeigen, was gestartet wuerde
#   ./0-3d-modell.sh --umgebung-sichern       Paketlisten der Python-Umgebungen neu nach tools/umgebung/ schreiben
#
# Ablauf: Datenplatte da? -> hp-wmi-Pruefung -> Python-Umgebungen pruefen (fehlt eine: aus tools/umgebung/<name>.txt einrichten)
#         -> tools/start3d.py (Fragen, Start der Gesamtkette als Hintergrund-Job, Fortschritt, Feinstufe nachts planen).
# Der Rechenjob laeuft als systemd-Dienst weiter, auch wenn dieses Fenster geschlossen wird (Strg-C trennt nur die Anzeige).
set -u
ROOT="$(dirname "$(readlink -f "$0")")"; cd "$ROOT" || exit 2
DATEN=/media/oem/scan
SEG=$DATEN/venv-seg; COL=$DATEN/venv-colmap; GEN=$HOME/.venvs/rcpark
COLMAP_BIN=$DATEN/colmap-build/prefix/bin/colmap
if [ -t 1 ]; then G=$'\e[32m'; R=$'\e[31;1m'; Y=$'\e[33m'; C=$'\e[36;1m'; N=$'\e[0m'; else G=; R=; Y=; C=; N=; fi

if [ "${1:-}" = "--umgebung-sichern" ]; then
  mkdir -p tools/umgebung
  for v in "$SEG" "$COL" "$GEN"; do
    "$v/bin/python" -m pip freeze 2>/dev/null | grep -v ' @ file://\|^-e ' > "tools/umgebung/$(basename "$v").txt" && echo "gesichert: tools/umgebung/$(basename "$v").txt"
  done; exit 0
fi

echo "${C}╔══ 3D-Modell erstellen ═══════════════════════════════════════════${N}"
if ! mountpoint -q "$DATEN"; then echo "ABBRUCH: Datenplatte $DATEN ist nicht eingehaengt (alle grossen Daten liegen dort)."; exit 2; fi
frei=$(df -BG --output=avail "$DATEN" | tail -1 | tr -dc 0-9); echo "Datenplatte: ${frei} GB frei"
[ "${frei:-0}" -lt 20 ] && echo "${R}ACHTUNG: weniger als 20 GB frei - eine dichte Wolke braucht 10-40 GB.${N}"

if [ -x tools/hpwmi_pruefen.sh ] || [ -f tools/hpwmi_pruefen.sh ]; then
  bash tools/hpwmi_pruefen.sh 2>&1 | grep -i 'ACHTUNG' && echo "(siehe ACHTUNG oben: Kernel-Modul hp-wmi)"
fi

# Umgebung pruefen/einrichten: name pfad prueftext
umgebung() {
  local name=$1 pfad=$2 test=$3 liste="tools/umgebung/$(basename "$2").txt" a
  if [ -x "$pfad/bin/python" ] && "$pfad/bin/python" -I -c "$test" >/dev/null 2>&1; then echo "  ${G}✔ ok${N}    $name"; return 0; fi
  echo "  ${R}✘ FEHLT${N} $name ($pfad) oder Pruefung '$test' scheitert"
  [ -f "$liste" ] || { echo "          keine Paketliste $liste - von Hand einrichten"; return 1; }
  read -r -p "          jetzt einrichten (python3 -m venv + pip install, dauert lange)? [j/N] " a
  [ "$a" = "j" ] || [ "$a" = "J" ] || return 1
  python3 -m venv "$pfad" && "$pfad/bin/pip" install -r "$liste" || { echo "          Einrichten fehlgeschlagen"; return 1; }
  "$pfad/bin/python" -I -c "$test" >/dev/null 2>&1 && echo "  ok      $name (neu eingerichtet)"
}
echo "${C}Python-Umgebungen:${N}"
fehler=0
umgebung "Bildverarbeitung + GPU (venv-seg)" "$SEG" "import torch, cv2, numpy, kornia; assert torch.cuda.is_available()" || fehler=1
umgebung "COLMAP-Python (venv-colmap)" "$COL" "import pycolmap, numpy" || { fehler=1; echo "          pycolmap ist ein eigener CUDA-Bau und steht NICHT in der Paketliste (siehe modelle/LIZENZ_WERKZEUGE.md / colmap-build)"; }
umgebung "Generator (~/.venvs/rcpark)" "$GEN" "import numpy, trimesh, manifold3d" || fehler=1
if [ -x "$COLMAP_BIN" ]; then echo "  ${G}✔ ok${N}    COLMAP-Programm ($COLMAP_BIN)"; else echo "  ${R}✘ FEHLT${N} COLMAP-Programm $COLMAP_BIN (eigener Bau)"; fehler=1; fi
if command -v nvidia-smi >/dev/null; then echo "  GPU:    $(nvidia-smi --query-gpu=name,memory.used,memory.total --format=csv,noheader 2>/dev/null | head -1)"; else echo "  ACHTUNG keine GPU (nvidia-smi fehlt)"; fi
if [ $fehler = 1 ]; then
  read -r -p "Es fehlt etwas (siehe oben). Trotzdem weiter? [j/N] " a; [ "$a" = "j" ] || [ "$a" = "J" ] || exit 2
fi
echo
exec "$SEG/bin/python" -I tools/start3d.py "$@"
