#!/usr/bin/env bash
# build_a3_set.sh — EIN konsistenter A3-Satz (50%-Maßstab): Rippen + Haut + Trog-Platte,
# ALLE im selben Fenster + Maßstab, Egg-Crate-Fit -0.4 (kalibriert, jetzt Default).
# Reproduzierbar: dieses Script IST der Befehl. Ausgabe: modelle/hoellental_A3_set/
#
#   ./build_a3_set.sh
#   ./zusammenbau.sh modelle/hoellental_A3_set     # danach 3D ansehen
set -euo pipefail
cd "$(dirname "$0")"

OUT="modelle/hoellental_A3_set"
DEM="daten/hoellental/dgm025_full.npy"
WINRC="--r0 470 --r1 640 --c0 3310 --c1 3570"   # Fenster ohne --zoom (tunnel_floor_portal kennt kein --zoom)
WIN="$WINRC --zoom 1"
# 50%-Maßstab: horizontal 0.78125 mm/Zelle (= halbes Spur-N bei 0.25m-DGM),
#              vertikal  3.125  mm/echtem Meter (= halbes Spur-N). vscale 0.85 wie A3.
SCALE="--mm 0.78125 --nscale 3.125 --vscale 0.85"
mkdir -p "$OUT"

# 50%-Trasse aus der VOLLSKALIGEN Track-Datei ableiten (x,y,z halbieren; is_tunnel bleibt),
# damit Tunnel/Lichtraum zum 50%-Gelände passt.
python3 - "$OUT" <<'PY'
import numpy as np, sys
out = sys.argv[1]
t = np.load("daten/hoellental/hoellental_track.npy").astype(float)
t[:, 0] *= 0.5; t[:, 1] *= 0.5; t[:, 2] *= 0.5     # x,y,z auf 50%; Spalte 3 (is_tunnel) unberührt
np.save(f"{out}/track50.npy", t)
print(f"  track50.npy: {t.shape}, x {t[:,0].min():.0f}..{t[:,0].max():.0f} mm")
PY

echo "== 1/5 Rippen-Gerüst (Snap auf Bruchkanten, Tunnel, Fit -0.4) =="
python3 tools/terrain_eggcrate.py --dem "$DEM" $WIN $SCALE --base 12 \
  --thickness 3 --snap-edges --tunnel --track "$OUT/track50.npy" \
  --gcode --out "$OUT"

echo "== 2/5 Haut-Panels (deckt Lücken + Tunnel-Dach) =="
python3 tools/terrain_skin_panels.py --dem "$DEM" $WIN $SCALE \
  --skin 4 --bed-x 250 --bed-y 210 --max-z 200 --out "$OUT/haut"

echo "== 3/5 Einhäng-Platten AUTO (nur wo die groben Rippen die Kontur verfehlen) =="
python3 tools/insert_plates_auto.py --dem "$DEM" $WIN $SCALE --snap-edges \
  --slope-max 25 --steep-min 60 --rib-miss 4 --min-area 300 \
  --wall-min-area 150 --wall-max-area 2500 --gcode --out "$OUT/platten"

echo "== 4/5 Tunnel-Teile (Gleisbett + Portal-Galerie: Dach/Wände/Stirn) =="
python3 tools/tunnel_floor_portal.py --dem "$DEM" $WINRC $SCALE --base 12 \
  --track "$OUT/track50.npy" --gcode --out "$OUT/tunnel"

echo "== 5/5 Kombinierte Vorschau (Skelett vs. fertig) =="
python3 tools/combined_view.py --dem "$DEM" $WIN $SCALE \
  --x0 130 --x1 162 --y0 80 --y1 105 --snap-edges --out "$OUT/vorschau"

echo
echo "FERTIG -> $OUT"
echo "  Rippen+G-Code in $OUT/ , Haut $OUT/haut/ , Platten $OUT/platten/ , Tunnel $OUT/tunnel/"
echo "  3D-Zusammenbau:  ./zusammenbau.sh $OUT"
echo "  Vorschau:        $OUT/vorschau/_combined.png"
