#!/bin/bash
# colmap-bauen.sh - COLMAP + Ceres SELBST aus dem Quellcode bauen, mit CUDA aus pip-Paketen (kein apt-CUDA, kein apt-COLMAP).
# Nutzer 19.11.2026: "er muss wissen, wie er es installiert"; "selber bauen, nicht aus apt, wenn es neuere gibt, die besser taugen".
# Stand = genau der Bau vom 13.11.2026 (colmap-build/colmap/build-cuda/CMakeCache.txt): COLMAP ce2b5ab (4.3.dev) mit CUDA, CASPAR, ONNX, CGAL,
# Ceres 07a9526 mit CUDA + cuDSS (GPU-Buendelausgleich), sm_89 (RTX 4060), Ninja, Release.
#
#   bash tools/umgebung/colmap-bauen.sh --pruefen              nur zeigen, was da ist / fehlt (baut nichts)
#   bash tools/umgebung/colmap-bauen.sh                        bauen nach /media/oem/scan/colmap-build/prefix (vorhandenes colmap wird als colmap.alt_<datum> behalten)
#   bash tools/umgebung/colmap-bauen.sh --ziel /media/oem/scan/colmap-test --colmap main --ceres master
#                                                              Testbau einer NEUEREN Version in einen eigenen Ordner (alter Bau bleibt unberuehrt; erst A/B messen, dann umstellen)
# Dauer ca. 1-2 h (Ceres ~15 min, COLMAP ~60 min), Platz ca. 8 GB, RAM: ninja -j6 (CUDA-Dateien brauchen je ~1,5 GB).
#
# WICHTIG (gefunden 19.11.): der Bau vom 13.11. linkt CUDA-Bibliotheken AUS venv-seg und venv-colmap (cuda-toolkit-combo zeigt per Verknuepfung hinein).
# Ein torch-Update in venv-seg kann COLMAP still kaputt machen. Dieses Skript legt deshalb alle CUDA-Teile in einen EIGENEN Ordner ($CUDA_DIR).
set -euo pipefail
D=/media/oem/scan
ZIEL=$D/colmap-build/prefix; COLMAP_REF=ce2b5ab; CERES_REF=07a9526; PRUEFEN=0; JOBS=${JOBS:-6}
while [ $# -gt 0 ]; do case "$1" in
  --pruefen) PRUEFEN=1;; --ziel) ZIEL=$2; shift;; --colmap) COLMAP_REF=$2; shift;; --ceres) CERES_REF=$2; shift;;
  *) echo "unbekannt: $1"; exit 2;; esac; shift; done
QUELLE=$(dirname "$ZIEL")/quellen-$(basename "$ZIEL")          # Quellcode je Ziel getrennt
CUDA_DIR=$(dirname "$ZIEL")/cuda-$(basename "$ZIEL")           # pip-CUDA je Ziel getrennt (unabhaengig von den Python-Umgebungen)
KOMBI=$CUDA_DIR/kombi                                          # include/ lib64/ bin/ wie ein normales CUDA-Toolkit
[ -t 1 ] && { G=$'\e[32m'; R=$'\e[31;1m'; Y=$'\e[33m'; N=$'\e[0m'; } || { G=; R=; Y=; N=; }
ok() { echo "  ${G}✔${N} $*"; }; fehlt() { echo "  ${R}✘${N} $*"; }

# CUDA aus pip (Versionen = Bau 13.11.; nvcc 13.2, cuDSS 1.0.0.35)
CUDA_PAKETE="nvidia-cuda-nvcc==13.2.86 nvidia-cuda-runtime==13.2.86 nvidia-cuda-crt==13.2.86 nvidia-nvvm==13.2.86 nvidia-cuda-cccl nvidia-cuda-nvrtc==13.2.86
 nvidia-cublas==13.4.1.3 nvidia-cusolver==12.2.0.11 nvidia-cusparse==12.7.10.12 nvidia-cufft==12.2.0.57 nvidia-curand nvidia-nvjitlink nvidia-cudss-cu13==1.0.0.35"
# Systembibliotheken (aus apt: Grundbausteine, bei denen eine neuere Version nichts bringt; COLMAP/Ceres/CUDA selbst NICHT aus apt)
APT="build-essential cmake ninja-build git libeigen3-dev libgoogle-glog-dev libgflags-dev libsqlite3-dev libcgal-dev
 libmetis-dev libsuitesparse-dev libblas-dev liblapack-dev libcurl4-openssl-dev libssl-dev libopengl-dev
 libopenimageio-dev libgmp-dev libmpfr-dev libunwind-dev"

echo "== COLMAP-Bau: Ziel $ZIEL, COLMAP $COLMAP_REF, Ceres $CERES_REF"
fehl_apt=$(for p in $APT; do dpkg -s "$p" >/dev/null 2>&1 || echo -n "$p "; done)
[ -z "$fehl_apt" ] && ok "Systempakete vollstaendig" || fehlt "Systempakete fehlen: $fehl_apt  ->  sudo apt install $fehl_apt"
[ -x "$KOMBI/bin/nvcc" ] && ok "CUDA (pip) in $CUDA_DIR" || fehlt "CUDA (pip) fehlt in $CUDA_DIR"
[ -f "$ZIEL/lib/cmake/Ceres/CeresConfig.cmake" ] && ok "Ceres in $ZIEL" || fehlt "Ceres fehlt in $ZIEL"
if [ -x "$ZIEL/bin/colmap" ] && LD_LIBRARY_PATH="$KOMBI/lib64:${LD_LIBRARY_PATH:-}" "$ZIEL/bin/colmap" -h >/dev/null 2>&1; then ok "COLMAP laeuft: $ZIEL/bin/colmap"; else fehlt "COLMAP fehlt/startet nicht in $ZIEL (mit $KOMBI/lib64)"; fi
[ $PRUEFEN = 1 ] && exit 0
[ -n "$fehl_apt" ] && { echo "${R}Erst die Systempakete installieren (Befehl oben), dann neu starten.${N}"; exit 3; }
frei=$(df -BG --output=avail "$D" | tail -1 | tr -dc 0-9); [ "$frei" -lt 12 ] && { echo "${R}nur $frei GB frei auf $D - Bau braucht ~8 GB + Puffer${N}"; exit 3; }

# 1) CUDA aus pip in eigenen Ordner + Toolkit-Ansicht (Verknuepfungen)
mkdir -p "$CUDA_DIR"
python3 -m pip install --quiet --upgrade --target "$CUDA_DIR/pip" $CUDA_PAKETE
rm -rf "$KOMBI"; mkdir -p "$KOMBI/include" "$KOMBI/lib64"
for t in "$CUDA_DIR"/pip/nvidia/*/; do
  [ -d "$t/include" ] && find "$t/include" -mindepth 1 -maxdepth 1 -exec ln -sfn {} "$KOMBI/include/" \;
  [ -d "$t/lib" ] && find "$t/lib" -mindepth 1 -maxdepth 1 -exec ln -sfn {} "$KOMBI/lib64/" \;
  [ -d "$t/bin" ] && [ ! -e "$KOMBI/bin" ] && [ -x "$t/bin/nvcc" ] && ln -sfn "$t/bin" "$KOMBI/bin"
  [ -d "$t/nvvm" ] && ln -sfn "$t/nvvm" "$KOMBI/nvvm"
done
ln -sfn lib64 "$KOMBI/lib"   # CMake sucht neben bin/ in lib/ (19.11.: ohne -> "-lcudart_static kann nicht gefunden werden")
for so in "$KOMBI"/lib64/lib*.so.*; do b=${so%%.so.*}.so; [ -e "$b" ] || ln -s "$(basename "$so")" "$b"; done   # libcublas.so -> libcublas.so.13 (zum Linken)
"$KOMBI/bin/nvcc" --version | tail -1
CUDSS=$(dirname "$(find "$CUDA_DIR/pip" -name 'libcudss.so.*' | head -1)")
mkdir -p "$CUDA_DIR/cudss-cmake"; cat > "$CUDA_DIR/cudss-cmake/cudssConfig.cmake" <<EOF
# Minimale Konfiguration fuer das pip-Paket nvidia-cudss-cu13 (Ceres erwartet find_package(cudss NO_MODULE) und Ziel 'cudss').
set(cudss_VERSION 1.0.0)
if(NOT TARGET cudss)
  add_library(cudss SHARED IMPORTED)
  set_target_properties(cudss PROPERTIES IMPORTED_LOCATION "$(ls "$CUDSS"/libcudss.so.* | head -1)" INTERFACE_INCLUDE_DIRECTORIES "$(dirname "$CUDSS")/include")
endif()
set(cudss_FOUND TRUE)
EOF
echo "set(PACKAGE_VERSION 1.0.0)
set(PACKAGE_VERSION_COMPATIBLE TRUE)" > "$CUDA_DIR/cudss-cmake/cudssConfigVersion.cmake"
export PATH="$KOMBI/bin:$PATH" LD_LIBRARY_PATH="$KOMBI/lib64:$CUDSS:${LD_LIBRARY_PATH:-}" CUDA_HOME="$KOMBI"

# 2) Quellen holen (fester Stand = reproduzierbar; 'main'/'master' = neuester Stand fuer Testbauten)
holen() { local url=$1 dir=$2 ref=$3; [ -d "$dir/.git" ] || git clone --quiet "$url" "$dir"; git -C "$dir" fetch --quiet origin; git -C "$dir" checkout --quiet "$ref"
          [ "$ref" = main ] || [ "$ref" = master ] && git -C "$dir" pull --quiet --ff-only origin "$ref"
          git -C "$dir" submodule update --init --recursive --quiet   # Ceres bringt abseil als Untermodul mit (19.11.: ohne -> 'absl not found')
          echo "  $(basename "$dir"): $(git -C "$dir" log -1 --format='%h %cd %s' --date=short | cut -c1-90)"; }
mkdir -p "$QUELLE"
holen https://github.com/ceres-solver/ceres-solver.git "$QUELLE/ceres" "$CERES_REF"
holen https://github.com/colmap/colmap.git "$QUELLE/colmap" "$COLMAP_REF"

# 3) Ceres mit CUDA + cuDSS
cmake -S "$QUELLE/ceres" -B "$QUELLE/ceres/bau" -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX="$ZIEL" -DUSE_CUDA=ON \
  -DCMAKE_CUDA_ARCHITECTURES=89 -DCMAKE_CUDA_COMPILER="$KOMBI/bin/nvcc" -DCUDAToolkit_ROOT="$KOMBI" -Dcudss_DIR="$CUDA_DIR/cudss-cmake" \
  -DBUILD_TESTING=OFF -DBUILD_EXAMPLES=OFF -DBUILD_BENCHMARKS=OFF > "$QUELLE/ceres-cmake.log"
ninja -C "$QUELLE/ceres/bau" -j "$JOBS" install > "$QUELLE/ceres-bau.log" && ok "Ceres gebaut"

# 4) COLMAP (Schalter wie build-cuda vom 13.11.)
# ONNX-Falle (19.11.2026, COLMAP-Issue #5053): github.com/microsoft/onnxruntime/releases/... liefert 404 -> frischer Bau scheitert.
# Ausweg: entpackte Kopie aus dem Bau vom 13.11. (Vorrat auf rcdaten) per FETCHCONTENT_SOURCE_DIR_ONNXRUNTIME einspeisen.
ONNX_VERSION=$(grep -oP 'set\(ONNX_VERSION\s+"?\K[0-9.]+' "$QUELLE/colmap/cmake/FindDependencies.cmake" | head -1)
ONNX_VORRAT=${ONNX_VORRAT:-/media/oem/rcdaten/vorrat/onnxruntime-linux-x64-gpu_cuda12-$ONNX_VERSION}
ONNX_OPT=""
# Falle 2 (20.11.2026): COLMAPs FindDependencies.cmake LOESCHT lib/cmake im eingespeisten Ordner -> Vorrat nach dem ersten Bau kaputt, jeder weitere Bau scheitert
# ("file COPY cannot find .../lib/cmake/onnxruntime"). Darum je Ziel eine Kopie einspeisen, Vorrat bleibt unberuehrt.
if [ -d "$ONNX_VORRAT/lib/cmake/onnxruntime" ]; then ONNX_KOPIE=$(dirname "$ZIEL")/onnx-$(basename "$ZIEL"); rm -rf "${ONNX_KOPIE:?}"; cp -a "$ONNX_VORRAT" "$ONNX_KOPIE"
  ONNX_OPT="-DFETCHCONTENT_SOURCE_DIR_ONNXRUNTIME=$ONNX_KOPIE"; ok "ONNX $ONNX_VERSION aus Vorrat $ONNX_VORRAT (Kopie $ONNX_KOPIE)"
else echo "${Y}kein ONNX-Vorrat fuer $ONNX_VERSION ($ONNX_VORRAT) - Download kann mit 404 scheitern (Issue #5053)${N}"; fi
[ -x "$ZIEL/bin/colmap" ] && cp -p "$ZIEL/bin/colmap" "$ZIEL/bin/colmap.alt_$(date +%Y%m%d)"
cmake -S "$QUELLE/colmap" -B "$QUELLE/colmap/bau" -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX="$ZIEL" \
  -DCUDA_ENABLED=ON -DCMAKE_CUDA_ARCHITECTURES=89 -DCMAKE_CUDA_COMPILER="$KOMBI/bin/nvcc" -DCUDAToolkit_ROOT="$KOMBI" \
  -DCeres_DIR="$ZIEL/lib/cmake/Ceres" -Dcudss_DIR="$CUDA_DIR/cudss-cmake" -DCASPAR_ENABLED=ON -DONNX_ENABLED=ON -DCGAL_ENABLED=ON \
  -DOPENGL_ENABLED=ON -DGUI_ENABLED=OFF -DTESTS_ENABLED=OFF -DFETCH_BOOST=ON -DFETCH_FAISS=ON -DFETCH_ONNX=ON -DFETCH_POSELIB=ON $ONNX_OPT > "$QUELLE/colmap-cmake.log"
ninja -C "$QUELLE/colmap/bau" -j "$JOBS" install > "$QUELLE/colmap-bau.log" && ok "COLMAP gebaut"

# 5) Startumgebung + Probe
cat > "$ZIEL/colmap-umgebung.sh" <<EOF
# vor dem Aufruf von $ZIEL/bin/colmap einlesen:  source $ZIEL/colmap-umgebung.sh
export LD_LIBRARY_PATH="$KOMBI/lib64:$CUDSS:$ZIEL/lib:\${LD_LIBRARY_PATH:-}"
EOF
# shellcheck disable=SC1090
source "$ZIEL/colmap-umgebung.sh"
"$ZIEL/bin/colmap" -h 2>&1 | head -3
ldd "$ZIEL/bin/colmap" | grep -q 'not found' && { fehlt "fehlende Bibliotheken:"; ldd "$ZIEL/bin/colmap" | grep 'not found'; exit 4; }
ok "fertig: $ZIEL/bin/colmap  (Umgebung: source $ZIEL/colmap-umgebung.sh)"
echo "${Y}Vor dem Umstellen der Kette: A/B-Messung (gleiche Datenbank, Mapper + PatchMatch, Zeit und Ergebnis) - siehe modelle/LOGBUCH_*.${N}"
