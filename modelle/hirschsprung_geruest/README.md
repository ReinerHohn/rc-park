# Hirschsprung / Höllental — Laser-Cut-Gerüst (Spur N)

Detailliertes Laser-Egg-Crate + Deckplatten der Höllental-Szene. Gips-Finish + Details per Hand.

## Settings (reproduzierbar)
```
python3 tools/terrain_eggcrate.py --dem daten/hoellental/dgm025_full.npy \
  --mm 1.5625 --nscale 6.25 --zoom 1 --r0 470 --r1 640 --c0 3310 --c1 3570 \
  --vscale 0.85 --nx 24 --ny 24 --min-gap 8 --thickness 4 --rib-depth 0 \
  --trans-frac 1.0 --smooth 0 --base 12 --tunnel --gcode --out <dir>
python3 tools/eggcrate_deck.py  <gleiche Szenen-Args>  --nx 24 --ny 24 --min-gap 8 --smooth 0 --gcode
```
- **adaptive Rippen** (dicht bei Detail, weit bei flach), **smooth 0 = roh/max Detail**,
  **Sockel 12 mm** (Rippen pinchen nicht am Talboden → nichts schwebt), **Tunnel-Loch** für die Höllentalbahn.
- Material **4 mm** Pappel/Sperrholz. Maße true-N (vscale 0,85).

## Inhalt
- `ribX_00..` + `ribY_00..` — 37 Rippen (SVG + GRBL-.gcode), mit Tunnel-Loch wo die Bahn durch.
- `deck/deck_cut_layout.svg` (+ .gcode) — 139 flache Deckplatten (Nummer graviert).
- `deck/deck_karte.png` — welche Platte in welche Zelle. 235 STEILE Zellen = Gipsbinde (siehe deck/MANIFEST.txt).
- `_assembled.html` — 3D drehbar. `_cut_layout.png` — Rippen-Schnittbild.

## Bau-Ablauf
1. **37 Rippen lasern** (4 mm). X-Rippen Schlitz oben, Y-Rippen Schlitz unten → **zusammenstecken** = 3D-Form.
2. **Deckplatten lasern** + nach `deck_karte.png` in ihre Zelle legen/kleben (Nummer graviert).
3. **Steile Zellen** (Felswand) mit **Gipsbinde/Karton** überbrücken.
4. **Gips über alles** + Details modellieren → **bemalen**.
5. **Tunnel**: Loch ist im Gerüst; **Steinschlag-Galerie am Portal = separates Teil** (nicht im Boden-DGM).

Szene-Doku: siehe Memory `hoellental-n-demonstrator`. Haut-Druck-Alternative: `modelle/hirschsprung_haut/`.
