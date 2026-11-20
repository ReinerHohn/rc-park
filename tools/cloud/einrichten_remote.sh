#!/bin/bash
# einrichten_remote.sh - laeuft AUF der vast.ai-Maschine (von tools/cloud/vast.sh einrichten aufgerufen). Baut die gleichen Umgebungen
# an den gleichen Pfaden wie auf dem Laptop: /media/oem/scan/venv-seg (torch cu132), /media/oem/scan/venv-colmap (pycolmap-cuda12 4.2.1),
# /home/oem/.venvs/rcpark (trimesh-Generator), /media/oem/scan/colmap-build/prefix/bin/colmap (Quellstand ce2b5ab, CUDA, GPU-Arch der Maschine).
# Unterschied zum Laptop (ANNAHME, bewusst): Ceres aus Ubuntu-Paket OHNE CUDA/cuDSS -> Buendelausgleich auf CPU (laut Messung 13.11.
# nur 17,1 statt 13,6 s; die Kette laeuft ohnehin mit --Mapper.ba_use_gpu 0). Wiederholbar: fertige Teile werden uebersprungen.
set -euo pipefail
REPO=/home/oem/git/rc-park; C=$REPO/tools/cloud; S=/media/oem/scan
export DEBIAN_FRONTEND=noninteractive HOME=/home/oem
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader
apt-get update -qq
apt-get install -y -qq git cmake ninja-build build-essential python3-venv python3-dev rsync \
  libboost-program-options-dev libboost-graph-dev libboost-system-dev libeigen3-dev libfreeimage-dev libmetis-dev \
  libgoogle-glog-dev libgtest-dev libgmock-dev libsqlite3-dev libglew-dev libcgal-dev libceres-dev \
  libcurl4-openssl-dev libssl-dev libgl1 libglib2.0-0 >/dev/null
mkdir -p $S /home/oem/.venvs $S/rc-park_daten/job_logs $S/rc-park_tmp $S/tmp $S/hf_cache

venv() {  # ZIEL ANFORDERUNGEN [extra-index]
  [ -x "$1/bin/python" ] && "$1/bin/python" -c "pass" && [ -f "$1/.fertig" ] && { echo "$1 schon da"; return; }
  python3 -m venv "$1"; "$1/bin/pip" -q install -U pip
  grep -v -E "^(-e |.* @ file:)" "$2" > /tmp/anf.txt
  "$1/bin/pip" -q install ${3:+--extra-index-url "$3"} -r /tmp/anf.txt && touch "$1/.fertig"
}
venv $S/venv-seg    $C/anforderungen_seg.txt    https://download.pytorch.org/whl/cu132 &
venv $S/venv-colmap $C/anforderungen_colmap.txt &
venv /home/oem/.venvs/rcpark $C/anforderungen_gen.txt &

if [ ! -x $S/colmap-build/prefix/bin/colmap ]; then
  mkdir -p $S/colmap-build && cd $S/colmap-build
  [ -d colmap ] || git clone -q https://github.com/colmap/colmap.git
  cd colmap && git checkout -q ce2b5ab9df3801c2b75edbba338c04ad3c8cc6af
  cmake -S . -B build-cuda -G Ninja -DCMAKE_BUILD_TYPE=Release -DCUDA_ENABLED=ON -DGUI_ENABLED=OFF \
    -DCMAKE_CUDA_ARCHITECTURES=native -DCMAKE_INSTALL_PREFIX=$S/colmap-build/prefix >/dev/null
  ninja -C build-cuda install > $S/rc-park_daten/job_logs/colmap_bau.log 2>&1 || { tail -20 $S/rc-park_daten/job_logs/colmap_bau.log; exit 4; }
fi
wait
$S/colmap-build/prefix/bin/colmap help 2>&1 | head -2
$S/venv-seg/bin/python -I -c "import torch;print('torch',torch.__version__,'cuda',torch.cuda.is_available())"
$S/venv-colmap/bin/python -I -c "import pycolmap;print('pycolmap',pycolmap.__version__)"
/home/oem/.venvs/rcpark/bin/python -c "import trimesh;print('trimesh',trimesh.__version__)"
cd $REPO && bash tools/schnelltest.sh 2>&1 | tail -5 || echo "Schnelltest auf der Cloud nicht bestanden - Ursache pruefen, bevor Jobs laufen"
echo EINRICHTEN_FERTIG
