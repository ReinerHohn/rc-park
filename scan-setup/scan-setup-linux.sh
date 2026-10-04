#!/usr/bin/env bash
# scan-setup-linux.sh
# Interaktives Setup fuer 3D-Scan (Photogrammetrie) auf dem RTX-Rechner (Linux).
# Installiert: Meshroom (Open Source), Blender (aufbereiten), COLMAP (optional),
# PrusaSlicer (drucken, falls per apt verfuegbar). Legt Ordner an + Anleitung.
#
# Start:   bash scan-setup-linux.sh

set -u
say(){ printf "\n\033[36m>>> %s\033[0m\n" "$1"; }
ask(){ read -r -p "$1 [J/n] " a; [[ ! "$a" =~ ^[nN] ]]; }

echo -e "\033[32m=== 3D-Scan Setup (Linux) ===\033[0m"

# --- 1. NVIDIA pruefen ---
say "Pruefe NVIDIA-Grafikkarte (noetig fuer Meshroom)..."
if command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null; then
  echo "OK (NVIDIA erkannt)"
else
  echo -e "\033[33mWARNUNG: keine NVIDIA erkannt. Meshroom braucht NVIDIA/CUDA.\033[0m"
  echo -e "\033[33mOhne NVIDIA lieber Handy-Cloud-Apps (KIRI Engine/Polycam).\033[0m"
  ask "Trotzdem weitermachen?" || exit 0
fi

# --- 2. Ordnerstruktur ---
BASE="$HOME/3DScan"
mkdir -p "$BASE"/{Fotos,Projekte,Export,Tools}
say "Arbeitsordner angelegt: $BASE  (Fotos / Projekte / Export / Tools)"

# --- 3. Pakete (Blender / COLMAP / PrusaSlicer) ---
if command -v apt >/dev/null 2>&1; then
  if ask "Blender + COLMAP per apt installieren (sudo noetig)?"; then
    say "Installiere..."; sudo apt update && sudo apt install -y blender colmap || echo "apt-Teilfehler - ggf. manuell nachinstallieren"
  fi
  if ask "PrusaSlicer per apt versuchen?"; then
    sudo apt install -y prusa-slicer 2>/dev/null || echo "PrusaSlicer nicht in apt - von prusa3d.com (AppImage) holen"
  fi
else
  echo "kein apt - Blender/COLMAP/PrusaSlicer bitte ueber deinen Paketmanager/Flatpak holen"
fi

# --- 4. Meshroom (neueste Version von GitHub) ---
if ask "Meshroom herunterladen & entpacken (~1.5 GB)?"; then
  say "Suche neueste Meshroom-Version..."
  URL=$(curl -s https://api.github.com/repos/alicevision/Meshroom/releases/latest \
        | grep browser_download_url | grep -iE 'linux.*\.tar\.gz"' | head -1 | cut -d'"' -f4)
  [ -z "$URL" ] && URL="https://github.com/alicevision/Meshroom/releases/download/v2023.3.0/Meshroom-2023.3.0-linux.tar.gz"
  say "Lade: $URL"
  curl -L "$URL" -o "$BASE/Tools/Meshroom.tar.gz"
  say "Entpacke..."
  tar xzf "$BASE/Tools/Meshroom.tar.gz" -C "$BASE/Tools" && rm "$BASE/Tools/Meshroom.tar.gz"
  MR=$(find "$BASE/Tools" -maxdepth 2 -name Meshroom -type f | head -1)
  [ -n "$MR" ] && echo -e "\033[32mMeshroom bereit: $MR\033[0m"
fi

# --- 5. Anleitung ---
say "FERTIG. So machst du deinen ersten Scan:"
cat <<EOF
1) FOTOS MACHEN (Handy reicht):
   - kleines Objekt: 40-80 Fotos rundherum, 2-3 Hoehen-Ringe
   - gleichmaessiges Licht, 70-80% Ueberlappung, scharf
   - Fotos nach:  $BASE/Fotos/<meinobjekt>/

2) MESHROOM:
   - Meshroom starten (in $BASE/Tools/...)
   - alle Fotos ins linke Fenster ziehen  ->  oben auf "Start"
   - Ergebnis: MeshroomCache/Texturing/.../texturedMesh.obj -> nach $BASE/Export

3) AUFBEREITEN (Blender):
   - OBJ importieren -> Boden/Muell weg -> aushoehlen/vereinfachen -> skalieren -> STL export

4) DRUCKEN:
   - STL in PrusaSlicer -> Supports an -> Slice -> drucken

TIPP: erst kleines Testobjekt. Gebaeude: 200-500 Fotos, 80% Ueberlappung.
Kastelburg: Mini-Drohne <250g + vorher dipul.de pruefen.
EOF
