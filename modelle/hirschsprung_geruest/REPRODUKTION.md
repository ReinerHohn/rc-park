# Höllental-Hirschsprung — Reproduktion (Daten → Laser-Cut)

Komplett nachbaubar. Dieses Kit (Spur N, 1:160) entstand in genau diesen Schritten. Die
**Laser-Cut-Daten (SVG+GRBL) und 3D-HTMLs liegen fertig im Git** — unten steht, wie man sie
aus den Rohdaten neu erzeugt. Allgemeine Methode: `../METHODE_WUNSCH_ZU_MODELL.md`.

Fenster/Maßstab durchgängig: `--r0 470 --r1 640 --c0 3310 --c1 3570 --mm 1.5625 --nscale 6.25
--zoom 1 --vscale 0.85` (= true-N, 406×266 mm Grundfläche, bis 378 mm hoch).

---

## 0. Voraussetzungen (Rohdaten — NICHT im Git, regenerierbar)
- **Gelände-DEM `daten/hoellental/dgm025_full.npy`** (4000×4000 float32, 0,25 m LiDAR, EPSG:25832).
  Quelle: LGL BW DGM025, Kachel **426/5309** (`dgm025_32_426_5309_1_bw_2017.tif`, Georef in der `.tfw`:
  Ursprung E426000.125 / N5309999.875, 0,25 m/px). Siehe Memory `lgl-bw-lidar`.
  TIF → NPY:
  ```python
  import numpy as np, rasterio
  a = rasterio.open("daten/hoellental/dgm025_32_426_5309_1_bw_2017.tif").read(1)
  np.save("daten/hoellental/dgm025_full.npy", a.astype("float32"))
  ```
- **Trasse `daten/hoellental/hoellental_track.npy`** — IST im Git (Zeilen `mx,my,mz,is_tunnel` in
  Modell-mm). Herkunft: OSM Overpass `way[railway](bbox)` + `tunnel=yes` (ways 23967775/76 = Tunnel,
  24059533 = offen), per pyproj EPSG:4326→25832 in Modellkoordinaten; Tunnelhöhen = gerade Steigung
  Portal→Portal. Neu ableiten nur nötig bei anderem Ausschnitt.

## 1. Gelände-Gerüst (adaptive Rippen + Tunnel-Löcher + Fingerzinken)
```bash
python3 tools/terrain_eggcrate.py --dem daten/hoellental/dgm025_full.npy \
  --mm 1.5625 --nscale 6.25 --zoom 1 --r0 470 --r1 640 --c0 3310 --c1 3570 \
  --vscale 0.85 --nx 22 --ny 18 --thickness 4 --base 12 --rib-depth 0 \
  --trans-frac 1.0 --smooth 0.6 --min-gap 7 \
  --tunnel --track daten/hoellental/hoellental_track.npy \
  --split-len 200 --finger 12 --gcode \
  --out modelle/hirschsprung_geruest
```
→ 85 Rippenstücke `ribX*/ribY*.svg(.gcode)` + `_assembled.html` (3D, drehbar).
Kernoptionen: **adaptive Dichte** (`--min-gap 7`, dicht an scharfen Kanten) · **voll bis Boden**
(`--rib-depth 0`, stabil) · **Fingerzinken** (`--split-len 200`, lange Rippen teilbar) · **echter
Tunnel** (`--tunnel --track …`, Lichtraum 30×36 in gekreuzte Rippen, für Schräge aufgeweitet).

## 2. Deckplatten (Gips-/Fliesenkleber-Basis auf sanften Zellen)
```bash
python3 tools/eggcrate_deck.py --dem daten/hoellental/dgm025_full.npy \
  --mm 1.5625 --nscale 6.25 --zoom 1 --r0 470 --r1 640 --c0 3310 --c1 3570 \
  --vscale 0.85 --nx 22 --ny 18 --smooth 0.6 --min-gap 7 --gcode \
  --out modelle/hirschsprung_geruest/deck
```
→ `deck/deck_cut_layout.svg(.gcode)` (115 flache Platten; steile Zellen = Gitter+Fliesenkleber).
Nutzt DIESELBE `rib_positions()` wie Schritt 1 → passt exakt zwischen die Rippen.

## 3. Tunnel-Kit (Gleisbett ganze Strecke + Tunnelboden + Portal-Galerie)
```bash
python3 tools/tunnel_floor_portal.py --track daten/hoellental/hoellental_track.npy \
  --out modelle/hirschsprung_geruest/tunnel --gcode
```
→ `tunnel/`: `gleisbett_1.svg` (22 mm, ganze Trasse) · `tunnelboden.svg` (30 mm, Tunnelabschnitt,
in die Lichtraum-Ausschnitte einlegen) · `galerie_{dach,wand_tal,wand_berg,stirn}.svg` (Steinschlag-
galerie am Ostportal) · `_plan.png`.

## 4. Schneidplan für den Laser  ⚠️ S9 = nur 410×400 mm
**Gewählter Weg (1200×600 ohne Sägen, Platte umsetzen):**
```bash
python3 tools/laser_zone_nest.py modelle/hirschsprung_geruest \
  --sheet 1200x600 --machine 410x400 --gcode --fdepth 3 --margin 2 \
  --out modelle/hirschsprung_geruest/zonen
```
→ `zonen/platte{N}_zone_r{R}c{C}.svg(.gcode)` + `platte_0N.png`. **3 Blätter, 3×2 Zonen,
18 Umsetz-Schnitte, ~48 % Verschnitt.** Teile über Zonengrenzen sind verzinkt (verleimen);
jede Zone genau 410×400 mit Cutter-Rahmen+Füßen+Registrier-Kreuzen. Liest `rib*/deck/tunnel`.
Flexibel: `--sheet 400x400` → 1 Zone/Blatt (kein Umsetzen). Alternative `tools/laser_blank_cut.py`
= bett-große Rohlinge einzeln.

## 5. 3D-Ansichten (optional, zum Prüfen)
```bash
python3 tools/tunnel_preview3d.py --out modelle/hirschsprung_geruest/tunnel/_tunnel3d.html  # Laser-Teile+Tunnel
python3 tools/tunnel_preview3d.py --surface --out modelle/hirschsprung_geruest/tunnel/_scene3d.html  # Gelände-Profil
```

---

## Ergebnis-Übersicht (alles im Git)
| Was | Wo |
|---|---|
| Rippen (Laser) | `ribX*.svg/.gcode`, `ribY*.svg/.gcode` |
| Deckplatten | `deck/deck_cut_layout.svg/.gcode` |
| Tunnel-Kit | `tunnel/gleisbett_1`, `tunnel/tunnelboden`, `tunnel/galerie_*` |
| Schneidplan (S9) | `zonen/platte*_zone_*.svg/.gcode` + `zonen/platte_*.png` |
| 3D drehbar | `_assembled.html`, `tunnel/_tunnel3d.html`, `tunnel/_scene3d.html` |

## Montage (Kurzfassung)
Rippen kreuzweise stecken (X-Schlitz oben / Y-Schlitz unten), Zinken verleimen → Deckplatten in
sanfte Zellen, steile mit Alu-Fliegengitter → **Flex-Fliesenkleber** als Haut + Felsstruktur →
Tunnelboden in die Lichtraum-Löcher, Gleisbett drauf, Kork + N-Flexgleis → Galerie ans Portal
(innen schwarz) → grundieren + bemalen (Fels: dunkel in Spalten/hell auf Kanten).

Details: `../METHODE_WUNSCH_ZU_MODELL.md`, Memory `hoellental-n-demonstrator`, `laser-sculpfun-s9`.
