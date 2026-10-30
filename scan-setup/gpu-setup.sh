#!/usr/bin/env bash
# gpu-setup.sh
# Richtet die GPU-Scan-Kette (CUDA) auf einem NVIDIA-Linux-Rechner ein - wiederholbar, jeder
# Schritt wird uebersprungen, wenn er schon erledigt ist. Doku: GPU-PIPELINE.md
#
#   1. NVIDIA-Treiber pruefen
#   2. Systempakete (sudo): Build-Bibliotheken fuer OpenMVS, nvtop
#   3. COLMAP mit CUDA (pycolmap-cuda12) in ein venv        -> colmap_gpu.py
#   4. CUDA-Compiler (nvcc) aus NVIDIA-Archiven, ohne Systeminstallation
#   5. OpenMVS mit CUDA bauen (Densify/Mesh/Refine/Texture)
#
# Alles Grosse landet auf DATA (Standard: die grosse Partition), nicht im Linux-Root.
#   bash gpu-setup.sh                         # DATA=/media/oem/Volume
#   DATA=/mnt/daten bash gpu-setup.sh         # anderer Rechner / andere Platte

set -u
DATA="${DATA:-/media/oem/Volume}"
CUDA_VER="${CUDA_VER:-12.9.1}"                 # Treiber muss >= 575 sein (nvidia-smi zeigt die Version)
VENV="$DATA/venv-colmap"; CUDA="$DATA/cuda12"; OMVS="$DATA/openmvs-build"

say(){ printf "\n\033[36m>>> %s\033[0m\n" "$1"; }
ok(){ printf "\033[32m%s\033[0m\n" "$1"; }
warn(){ printf "\033[33m%s\033[0m\n" "$1"; }

# --- 0. Datenplatte ---
if ! touch "$DATA/.schreibtest" 2>/dev/null; then
  warn "$DATA nicht beschreibbar. NTFS/Windows-Partition? -> in Windows den Schnellstart abschalten"
  warn "(Energieoptionen), oder anderen Ort waehlen: DATA=/pfad bash gpu-setup.sh"
  exit 1
fi
rm -f "$DATA/.schreibtest"; ok "Datenplatte: $DATA ($(df -h "$DATA" | awk 'NR==2{print $4}') frei)"

# --- 1. NVIDIA ---
say "1) NVIDIA-Treiber"
if nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader 2>/dev/null; then
  ok "OK"
else
  warn "nvidia-smi geht nicht. Haeufigste Ursache: Kernel ohne passendes NVIDIA-Modul."
  warn "Pruefen: uname -r  vs.  dpkg -l 'linux-modules-nvidia-*'  -> passenden Kernel in GRUB booten."
  exit 1
fi

# --- 2. Systempakete ---
say "2) Systempakete"
PKGS=(cmake g++ git curl python3-venv nvtop
      libboost-iostreams-dev libboost-program-options-dev libboost-system-dev libboost-serialization-dev libboost-graph-dev
      libcgal-dev libeigen3-dev libnanoflann-dev libopencv-dev libjpeg-dev libpng-dev libtiff-dev
      libglu1-mesa-dev libglew-dev libglfw3-dev)
FEHLT=(); for p in "${PKGS[@]}"; do dpkg -s "$p" >/dev/null 2>&1 || FEHLT+=("$p"); done
if [ ${#FEHLT[@]} -gt 0 ]; then
  echo "Fehlt: ${FEHLT[*]}"
  sudo apt install -y "${FEHLT[@]}" || { warn "apt fehlgeschlagen"; exit 1; }
fi
ok "OK"

# --- 3. COLMAP (CUDA) ---
say "3) COLMAP mit CUDA -> $VENV"
if ! "$VENV/bin/python" -c "import pycolmap,sys; sys.exit(0 if pycolmap.has_cuda else 1)" 2>/dev/null; then
  python3 -m venv --system-site-packages "$VENV"
  "$VENV/bin/pip" install --no-cache-dir pycolmap-cuda12 || exit 1
fi
"$VENV/bin/python" -c "import pycolmap; print('pycolmap', pycolmap.__version__, 'CUDA:', pycolmap.has_cuda)"

# --- 4. CUDA-Compiler ---
# Das pip-Paket nvidia-cuda-nvcc-cu12 enthaelt nur ptxas, kein nvcc -> offizielle Redist-Archive.
say "4) CUDA $CUDA_VER Compiler -> $CUDA"
if ! "$CUDA/bin/nvcc" --version >/dev/null 2>&1; then
  R=https://developer.download.nvidia.com/compute/cuda/redist
  DL="$DATA/cuda-dl"; mkdir -p "$DL" "$CUDA"
  J=$(curl -fsS "$R/redistrib_$CUDA_VER.json") || { warn "Download-Liste nicht erreichbar"; exit 1; }
  for p in cuda_nvcc cuda_cudart cuda_cccl cuda_nvrtc; do
    rel=$(python3 -c "import sys,json; print(json.load(sys.stdin)['$p']['linux-x86_64']['relative_path'])" <<<"$J")
    f="$DL/$(basename "$rel")"
    [ -f "$f" ] || curl -fsSL -o "$f" "$R/$rel" || exit 1
    tar xf "$f" -C "$DL" && cp -r "${f%.tar.xz}/." "$CUDA/"
  done
fi
"$CUDA/bin/nvcc" --version | tail -1

# --- 5. OpenMVS (CUDA) ---
# Fertige Linux-Pakete von OpenMVS haben kein CUDA (nur Windows) -> selbst bauen (~10-15 min).
say "5) OpenMVS mit CUDA -> $OMVS/bin"
if [ ! -x "$OMVS/bin/bin/DensifyPointCloud" ]; then
  mkdir -p "$OMVS"
  [ -d "$OMVS/src" ]    || git clone --depth 1 --recurse-submodules https://github.com/cdcseacave/openMVS.git "$OMVS/src"
  # Build-Ordner im Linux-Dateisystem waere schneller, aber Root ist meist voll -> auf DATA
  cmake -S "$OMVS/src" -B "$OMVS/build" -DCMAKE_BUILD_TYPE=Release \
    -DOpenMVS_USE_CUDA=ON -DCMAKE_CUDA_COMPILER="$CUDA/bin/nvcc" -DCUDAToolkit_ROOT="$CUDA" \
    -DCMAKE_CUDA_ARCHITECTURES=native \
    -DOpenMVS_USE_PYTHON=OFF -DOpenMVS_USE_BREAKPAD=OFF \
    -DCMAKE_INSTALL_PREFIX="$OMVS/bin" || exit 1
  cmake --build "$OMVS/build" -j"$(nproc)" && cmake --install "$OMVS/build" || exit 1
fi
ls "$OMVS/bin/bin" | grep -E "Densify|Reconstruct|Refine|Texture|Interface" | tr '\n' ' '; echo

say "FERTIG"
cat <<EOF
GPU-Last ansehen:   nvtop
COLMAP-Lauf:        $VENV/bin/python $(dirname "$(readlink -f "$0")")/colmap_gpu.py <bilder> <arbeitsordner>
OpenMVS:            $OMVS/bin/bin/
EOF
