# Höllental-Hirschsprung — 25% TESTSET (Viertel-N, 1:640)

Kleiner Testschnitt zum Validieren von Passung/Tunnel/Montage vor dem großen 50%-Set.
Modell **102×66 mm, bis 103 mm hoch**. 15 Rippen + 40 Kanten-Lineale = 55 Teile.
Tunnel-Lichtraum 6,2×7,3 mm (maßstäblich, MIT Dach). Gleisbett liegt auf der Oberfläche.
Fingerzinken AUS (Rippen passen aufs Bett). Keine Fuzzel-Lineale (edge-min-len 18).

## Erzeugen
```bash
python3 tools/terrain_eggcrate.py --dem daten/hoellental/dgm025_full.npy \
  --mm 0.390625 --nscale 1.5625 --zoom 1 --r0 470 --r1 640 --c0 3310 --c1 3570 \
  --vscale 0.85 --nx 12 --ny 8 --thickness 3 --base 12 --rib-depth 0 \
  --trans-frac 1.0 --smooth 0.6 --min-gap 7 --tunnel \
  --track daten/hoellental/hoellental_track_50.npy \
  --tunnel-w-m 4.0 --tunnel-h-m 5.5 --roof-min 2.0 \
  --split-len 0 --edge-min-len 18 --fit -0.50 --gcode --out modelle/hoellental_geruest_25
```
(25% = halbe Maßstabswerte des 50%-Sets: mm 0.390625, nscale 1.5625.)

## Schneiden
- `bretter/brett1.gcode`         — alle 15 Rippen (~56 min, 400×264 mm)
- `bretter_lineale/brett1.gcode` — alle 40 Lineale (~42 min)
Material 3 mm Pappel, 2×@100%/300, S9 USB DIREKT am Laptop.

## Montage
Rippen stecken → Kanten-Lineale OBEN aufkleben → Gips drüber.
