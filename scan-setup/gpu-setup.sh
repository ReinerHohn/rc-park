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
#   6. Ceres mit CUDA + cuDSS und COLMAP/pycolmap dagegen bauen -> Bundle Adjustment
#      (Kamerapositionen) auch auf der GPU. pip-pycolmap kann das nicht.
#
# Alles Grosse landet auf DATA (Standard: die grosse Partition), nicht im Linux-Root.
#   bash gpu-setup.sh                         # DATA=/media/oem/Volume
#   DATA=/mnt/daten bash gpu-setup.sh         # anderer Rechner / andere Platte

set -u
DATA="${DATA:-/media/oem/Volume}"
CUDA_VER="${CUDA_VER:-12.9.1}"                 # Treiber muss >= 575 sein (nvidia-smi zeigt die Version)
CUDSS_VER="${CUDSS_VER:-1.0.0}"
OMVS_VER="${OMVS_VER:-v2.4.0}"; CGAL_VER="${CGAL_VER:-6.1.3}"
VENV="$DATA/venv-colmap"; CUDA="$DATA/cuda12"; OMVS="$DATA/openmvs-build"
GBA="$DATA/colmap-build"; GVENV="$DATA/venv-colmap-gpuba"

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
      libboost-exception-dev libboost-math-dev libboost-filesystem-dev libjxl-dev
      libcgal-dev libeigen3-dev libnanoflann-dev libopencv-dev libjpeg-dev libpng-dev libtiff-dev
      libglu1-mesa-dev libglew-dev libglfw3-dev
      libgoogle-glog-dev libgflags-dev libsuitesparse-dev libmetis-dev libsqlite3-dev
      libopenimageio-dev libcurl4-openssl-dev libssl-dev ninja-build)
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

# --- 4. CUDA-Compiler + Bibliotheken ---
# Das pip-Paket nvidia-cuda-nvcc-cu12 enthaelt nur ptxas, kein nvcc -> offizielle Redist-Archive,
# nur entpackt (keine Systeminstallation, nichts im Linux-Root).
redist(){  # redist <basis-url> <json-name> <variante|-> <paket...>
  local R=$1 N=$2 V=$3 J; shift 3
  J=$(curl -fsS "$R/$N") || { warn "Download-Liste $R/$N nicht erreichbar"; exit 1; }
  for p in "$@"; do
    rel=$(python3 -c "import sys,json; e=json.load(sys.stdin)['$p']['linux-x86_64']; print(e['$V']['relative_path'] if '$V'!='-' else e['relative_path'])" <<<"$J")
    f="$DL/$(basename "$rel")"
    [ -f "$f" ] || curl -fsSL -o "$f" "$R/$rel" || exit 1
    tar xf "$f" -C "$DL" && cp -r "${f%.tar.xz}/." "$CUDA/" && rm -rf "${f%.tar.xz}"
  done
}
say "4) CUDA $CUDA_VER (nvcc, cuBLAS/cuSOLVER/cuSPARSE) + cuDSS $CUDSS_VER -> $CUDA"
DL="$DATA/cuda-dl"; mkdir -p "$DL" "$CUDA"
[ -x "$CUDA/bin/nvcc" ] || redist https://developer.download.nvidia.com/compute/cuda/redist \
  "redistrib_$CUDA_VER.json" - cuda_nvcc cuda_cudart cuda_cccl cuda_nvrtc
[ -e "$CUDA/lib/libcusolver.so" ] || redist https://developer.download.nvidia.com/compute/cuda/redist \
  "redistrib_$CUDA_VER.json" - libcublas libcusolver libcusparse libnvjitlink libcurand
[ -e "$CUDA/lib/libcudss.so" ] || redist https://developer.download.nvidia.com/compute/cudss/redist \
  "redistrib_$CUDSS_VER.json" cuda12 libcudss
# nvcc sucht in lib64, die Redist-Archive packen nach lib
[ -e "$CUDA/lib64" ] || ln -s lib "$CUDA/lib64"
"$CUDA/bin/nvcc" --version | tail -1; ls "$CUDA/lib" | grep -E "^lib(cudss|cusolver)\.so$" | tr '\n' ' '; echo

# --- 5. OpenMVS (CUDA) ---
# Fertige Linux-Pakete von OpenMVS haben kein CUDA (nur Windows) -> selbst bauen (~10-15 min).
say "5) OpenMVS mit CUDA -> $OMVS/bin"
if [ ! -x "$OMVS/bin/bin/DensifyPointCloud" ]; then
  mkdir -p "$OMVS"
  # Release v2.4.0: braucht nur apt-Pakete + VCG. Der Entwicklungsstand (master) will zusaetzlich
  # TinyEXIF, TinyNPY, PoseLib, halfmesh ... (nur per vcpkg) -> bewusst die stabile Version.
  [ -d "$OMVS/src" ]    || git clone --depth 1 -b "$OMVS_VER" https://github.com/cdcseacave/openMVS.git "$OMVS/src"
  [ -d "$OMVS/vcglib" ] || git clone --depth 1 https://github.com/cdcseacave/VCG.git "$OMVS/vcglib"
  # OpenMVS 2.4 braucht CGAL 6 (Ubuntu 24.04 hat 5.6) -> CGAL ist reine Header, nur entpacken
  [ -d "$OMVS/CGAL-$CGAL_VER" ] || { curl -fsSL "https://github.com/CGAL/cgal/releases/download/v$CGAL_VER/CGAL-$CGAL_VER-library.tar.xz" \
    | tar xJ -C "$OMVS" || exit 1; }
  # OpenCV < 4.11 (Ubuntu 24.04: 4.6) kennt IMWRITE_JPEGXL_QUALITY nicht -> Weiche einbauen
  T="$OMVS/src/libs/Common/Types.inl"
  grep -q "CV_VERSION_MINOR >= 11" "$T" || python3 - "$T" <<'PY'
import sys; p = sys.argv[1]; s = open(p).read()
old = "\tif (ext == \".jxl\") {\n\t\tcompression_params.push_back(cv::IMWRITE_JPEGXL_QUALITY);\n\t\tcompression_params.push_back(95);\n\t} else\n"
assert old in s, "JXL-Stelle in Types.inl nicht gefunden"
open(p, "w").write(s.replace(old, "#if CV_VERSION_MAJOR > 4 || (CV_VERSION_MAJOR == 4 && CV_VERSION_MINOR >= 11)\n" + old + "#endif\n"))
PY
  # Build-Ordner im Linux-Dateisystem waere schneller, aber Root ist meist voll -> auf DATA
  cmake -S "$OMVS/src" -B "$OMVS/build" -DCMAKE_BUILD_TYPE=Release \
    -DVCG_ROOT="$OMVS/vcglib" -DCGAL_DIR="$OMVS/CGAL-$CGAL_VER/lib/cmake/CGAL" \
    -DOpenMVS_USE_CUDA=ON -DCMAKE_CUDA_COMPILER="$CUDA/bin/nvcc" -DCUDAToolkit_ROOT="$CUDA" \
    -DCMAKE_CUDA_ARCHITECTURES=native \
    -DOpenMVS_USE_PYTHON=OFF -DOpenMVS_USE_BREAKPAD=OFF \
    -DCMAKE_INSTALL_PREFIX="$OMVS/bin" || exit 1
  cmake --build "$OMVS/build" -j"$(nproc)" && cmake --install "$OMVS/build" || exit 1
fi
ls "$OMVS/bin/bin" | grep -E "Densify|Reconstruct|Refine|Texture|Interface" | tr '\n' ' '; echo

# --- 6. Ceres (CUDA + cuDSS) + COLMAP/pycolmap ---
# Ohne das: GLOMAP meldet "Ceres was compiled without cuDSS support. Falling back to CPU"
# und rechnet die Kamerapositionen nur auf der CPU. Bau ~30-60 min.
say "6) Ceres + COLMAP mit GPU-Bundle-Adjustment -> $GVENV"
export LD_LIBRARY_PATH="$CUDA/lib:${LD_LIBRARY_PATH:-}"
if ! "$GVENV/bin/python" -c "import pycolmap" 2>/dev/null; then
  mkdir -p "$GBA"
  # cuDSS gibt es erst im Ceres-Entwicklungsstand (2.2.0 kann es nicht); der braucht Abseil als Submodul
  [ -d "$GBA/ceres" ]  || git clone --depth 1 https://github.com/ceres-solver/ceres-solver.git "$GBA/ceres"
  git -C "$GBA/ceres" submodule update --init --depth 1 third_party/abseil-cpp || exit 1
  [ -d "$GBA/colmap" ] || git clone --depth 1 https://github.com/colmap/colmap.git "$GBA/colmap"
  CU=(-DCMAKE_CUDA_COMPILER="$CUDA/bin/nvcc" -DCUDAToolkit_ROOT="$CUDA" -DCMAKE_CUDA_ARCHITECTURES=native)
  cmake -S "$GBA/ceres" -B "$GBA/ceres-build" -G Ninja -DCMAKE_BUILD_TYPE=Release \
    -DWITH_CUDA=default "${CU[@]}" -Dcudss_DIR="$CUDA/lib/cmake/cudss" -DWITH_SUITESPARSE=ON \
    -DBUILD_TESTING=OFF -DBUILD_EXAMPLES=OFF -DBUILD_BENCHMARKS=OFF \
    -DCMAKE_INSTALL_PREFIX="$GBA/prefix" || exit 1
  grep -q "^#define CERES_NO_CUDSS" "$GBA/ceres-build/include/ceres/internal/config.h" \
    && { warn "Ceres ohne cuDSS konfiguriert - Abbruch"; exit 1; }
  cmake --build "$GBA/ceres-build" && cmake --install "$GBA/ceres-build" || exit 1
  cmake -S "$GBA/colmap" -B "$GBA/colmap-build" -G Ninja -DCMAKE_BUILD_TYPE=Release \
    -DCUDA_ENABLED=ON "${CU[@]}" -DGUI_ENABLED=OFF -DTESTS_ENABLED=OFF \
    -DCMAKE_PREFIX_PATH="$GBA/prefix" -DCMAKE_INSTALL_PREFIX="$GBA/prefix" || exit 1
  cmake --build "$GBA/colmap-build" && cmake --install "$GBA/colmap-build" || exit 1
  python3 -m venv --system-site-packages "$GVENV"
  "$GVENV/bin/pip" install --no-cache-dir scikit-build-core pybind11 numpy build || exit 1
  CMAKE_PREFIX_PATH="$GBA/prefix" CMAKE_ARGS="${CU[*]}" \
    "$GVENV/bin/pip" install --no-build-isolation --no-cache-dir "$GBA/colmap" || exit 1
fi
# Starter: setzt den Bibliothekspfad fuer cuDSS/cuBLAS, sonst findet pycolmap sie nicht
cat > "$DATA/colmap-gpu" <<EOS
#!/bin/sh
export LD_LIBRARY_PATH="$CUDA/lib:\${LD_LIBRARY_PATH:-}"
export SSL_CERT_FILE="\${SSL_CERT_FILE:-/etc/ssl/certs/ca-certificates.crt}"
exec "$GVENV/bin/python" "\$@"
EOS
chmod +x "$DATA/colmap-gpu"
"$DATA/colmap-gpu" -c "import pycolmap; print('pycolmap', pycolmap.__version__, 'CUDA:', pycolmap.has_cuda)"

say "FERTIG"
cat <<EOF
GPU-Last ansehen:   nvtop
COLMAP-Lauf:        $DATA/colmap-gpu $(dirname "$(readlink -f "$0")")/colmap_gpu.py <bilder> <arbeitsordner>
OpenMVS:            $OMVS/bin/bin/
EOF
