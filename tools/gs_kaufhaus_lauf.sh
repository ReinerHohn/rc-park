#!/bin/bash
# gs_kaufhaus_lauf.sh - setzt die CUDA-Umgebung fuer gsplat (JIT) und startet venv-seg python -I mit den Argumenten (fuer tools/job_start.sh, dessen Dienst die Umgebung nicht erbt).
export CUDA_HOME=/media/oem/scan/cuda-nvcc/nvidia/cu13 PATH=/media/oem/scan/cuda-nvcc/nvidia/cu13/bin:$PATH TORCH_CUDA_ARCH_LIST=8.9 PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
cd /home/oem/git/rc-park && exec /media/oem/scan/venv-seg/bin/python -W ignore -I "$@"
