#!/usr/bin/env bash
# laser_setup.sh — EIN Script für den Sculpfun S9:
#   installiert bei Bedarf alles Nötige (pyserial, wxPython via apt, MeerK40t)
#   und startet dann direkt die Laser-UI (MeerK40t).
# Aufruf:  bash tools/laser_setup.sh
set -u
export PATH="$HOME/.local/bin:$PATH"          # damit 'meerk40t' gefunden wird
have() { python3 -c "import $1" 2>/dev/null; }

echo "============================================"
echo "  Sculpfun S9 — Laser-UI (auto-setup + start)"
echo "============================================"

# --- Port-Hinweis (blockiert nicht) -------------------------------------------
PORT=$(ls /dev/ttyUSB* 2>/dev/null | head -1)
if [ -n "$PORT" ]; then echo "[OK]  Laser-Port: $PORT (115200, GRBL)"
else echo "[!!]  kein /dev/ttyUSB* — Laser AN + Datenkabel? (UI startet trotzdem)"; fi
groups | grep -q dialout || echo "[!!]  nicht in dialout: sudo usermod -aG dialout $USER (neu einloggen)"

# --- pyserial -----------------------------------------------------------------
if ! have serial; then
  echo "[..]  installiere pyserial"
  pip install --user --quiet pyserial 2>/dev/null \
    || pip install --user --quiet --break-system-packages pyserial 2>/dev/null
fi
have serial && echo "[OK]  pyserial"

# --- wxPython (GUI-Lib) via apt ----------------------------------------------
if ! have wx; then
  if command -v apt-get >/dev/null 2>&1; then
    echo "[..]  installiere GUI-Lib python3-wxgtk4.0 (sudo -> Passwort)"
    sudo apt-get update -qq && sudo apt-get install -y python3-wxgtk4.0
  else
    echo "[!!]  kein apt — wxPython bitte manuell installieren"
  fi
fi
have wx && echo "[OK]  wxPython (GUI)" || echo "[!!]  wxPython fehlt -> nur headless möglich"

# --- MeerK40t -----------------------------------------------------------------
if ! have meerk40t; then
  echo "[..]  installiere MeerK40t"
  pip install --user --quiet meerk40t 2>/dev/null \
    || pip install --user --quiet --break-system-packages meerk40t 2>/dev/null
fi
have meerk40t && echo "[OK]  MeerK40t" || { echo "[XX]  MeerK40t-Install fehlgeschlagen"; exit 1; }

# --- S9-Presets (idempotent) --------------------------------------------------
cat > tools/s9_laser.conf <<EOF
# Sculpfun S9 Presets (GRBL ~5,5 W) — Startwerte, in MeerK40t 'Material Test' verfeinern!
PORT=${PORT:-/dev/ttyUSB0}
BAUD=115200
CONTROLLER=GRBL
BED_X_MM=410
BED_Y_MM=400
ORIGIN=front-left
# Material        | Speed mm/min | Power % | Passes
graupappe_2-3mm   = 400 90 1-2
pappelsperr_2mm   = 220 100 2-3   # mit Air Assist
pappelsperr_3mm   = 150 100 3-5   # mit Air Assist
gravur_nummer     = 4000 20 1
# NUR rohes/unbeschichtetes Material — kein PVC/Vinyl/beschichtet (Chlorgas!)
EOF
echo "[OK]  Presets -> tools/s9_laser.conf"

# --- UI starten ---------------------------------------------------------------
echo "--------------------------------------------"
if have wx; then
  echo "== Starte MeerK40t-GUI =="
  echo "   Gerät: GRBL, ${PORT:-/dev/ttyUSB0}, 115200, Bett 410x400"
  echo "   SVGs: python3 tools/topo_laser_contours.py  (Ordner /tmp/laser)"
  exec meerk40t
else
  echo "== wxPython fehlt -> starte headless (keine GUI) =="
  exec meerk40t --no-gui
fi
