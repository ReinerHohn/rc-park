#!/bin/bash
cd "$(dirname "$0")"
cd ../..
python3 tools/terrain_eggcrate.py --dem daten/hoellental/dgm025_full.npy \
  --mm 0.78125 --nscale 3.125 --zoom 1 --r0 470 --r1 640 --c0 3310 --c1 3570 \
  --vscale 0.85 --nx 12 --ny 8 --thickness 3 --base 12 --rib-depth 0 \
  --trans-frac 1.0 --smooth 0.6 --min-gap 7 \
  --tunnel --track daten/hoellental/hoellental_track_50.npy \
  --split-len 200 --finger 12 --fit -0.50 --gcode \
  --out modelle/hoellental_geruest_a3
firefox "modelle/hoellental_geruest_a3/_zusammenbau.html" &
