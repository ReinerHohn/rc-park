# Höllental-Hirschsprung Gerüst — A3 / lockere Passung (Stand 2026-10-22)

50%-Egg-Crate (half-N, 1:320), Schlitz-Fit **lockerer** als der alte Satz (am Gerät ermittelt:
Steck-Test 2,5 mm perfekt → `--fit -0.50`). Material **3 mm Pappelsperr**, Schnitt **2×@100%/300**,
gelasert am Sculpfun S9 (`grbl_send.py --yes`). Nest auf **A3 (410×297 nutzbar, S9-Fenster 410×400)**.

## Komplett neu erzeugen (alle 25+ Rippen + ALLE Kanten erfasst)
```bash
python3 tools/terrain_eggcrate.py --dem daten/hoellental/dgm025_full.npy \
  --mm 0.78125 --nscale 3.125 --zoom 1 --r0 470 --r1 640 --c0 3310 --c1 3570 \
  --vscale 0.85 --nx 12 --ny 8 --thickness 3 --base 12 --rib-depth 0 \
  --trans-frac 1.0 --smooth 0.6 --min-gap 7 \
  --tunnel --track daten/hoellental/hoellental_track_50.npy \
  --split-len 200 --finger 12 --fit -0.50 --gcode \
  --out modelle/hoellental_geruest_a3
```
→ `--snap-edges=True --snap-pct=80.0` sind JETZT DEFAULT. Nur Gips drüber → Relief mit allen Kanten kommt raus.
→ 203×133 mm, bis 195 mm hoch, **7 X-Rippen + 11 Y-Rippen** (X je a/b geteilt = 14 X-Teile), Schlitz 2,50.

## Auf A3-Bretter packen
```bash
python3 tools/laser_pack.py modelle/hoellental_geruest_a3 --sheet 410x297 \
  --passes 2 --nest --margin 4 --out modelle/hoellental_geruest_a3/bretter
```

## Fortschritt (Teile-genau, da Pack-Brettnummern je Lauf variieren)
- ✅ **GESCHNITTEN:** Y9, Y10, X0b, X1b, X4b, X5b, X6b (altes 410×200-Brett) + Y3, Y4, Y5, Y6, Y7, Y8, X2b, X3b (A3-Brett 1)
- 🔲 **OFFEN:** Y0, Y1, Y2, X0a, X1a, X2a, X3a, X4a, X5a, X6a (10 Teile → A3-Brett 2 + 3)
- Die X-Rippen sind a/b-geteilt (Fingerzinken, mehrere Finger — kein Einzelzahn); b-Hälften fast alle fertig, a-Hälften offen.

## Regeln
- `--fit -0.50` = lockere Slip-Fit-Schlitze (Vollgitter: eine Rippe kreuzt 8–11 Schlitze → lieber locker).
- Fingerzinken nur wo Rippe am Stoß hoch genug (mehrere Finger), nie Einzelzahn.
- **`--snap-edges --snap-pct 80.0` ist NOW DEFAULT** — erfasst ALLE scharfen topographischen Kanten (Bruchkanten, Felsgrate, Talränder, Hirsch-Felsvorsprünge), damit die Gips-Haut darüber alle Relief-Details zeigt. **Methode: Gitter schneiden → zusammenstecken → Gips drüber → fertig!**
- S9-USB **direkt an den Laptop** (nicht HP-Dock) — sonst Serial-Abbruch bei langen Läufen.

## Slot-Mund-Fix (2026-10-22) + Baustand-Marker
- `terrain_eggcrate.rib()`: Schlitzmund-**Zacken/Verengung beseitigt** (keine Kantenpunkte mehr im Mund; slotw/2 > 1mm-Schritt hatte Rückwärts-Haken erzeugt → Rippe klemmte) **+ Einführtrichter** (`flare=0.4` mm/Seite): Mund breiter, verjüngt sich auf slotw → Rippe gleitet rein, Griff bleibt 2,5 mm.
- **Die hier geschnittenen Teile sind VOR dem Fix** (alter Zacken) → Mundkanten entgraten ODER mit gefixtem Generator neu schneiden.
- Zusammenbau-HTML: **🧩 Baustand-Marker** — Teile anklicken = „hab ich" (solide), Rest blass; gespeichert pro Modell (localStorage). Öffnen via `./zusammenbau.sh`.
- **Naht-Versatz (choose_seams):** Fingerzinken-Nähte benachbarter Rippen strikt **abwechselnd (ABAB)** → **keine durchgehende Sollbruch-Linie** mehr (vorher lagen alle X-Nähte auf einer Linie bei Y8).
- **TUNNEL-Trasse SKALIERT (wichtig!):** `hoellental_track.npy` ist in VOLL-Modell-mm (bis ~424×250) → fiel beim 50%-Modell (203×133) komplett raus → „Trasse 0 Punkte, kein Tunnel". Fix: **`hoellental_track_50.npy`** (x/y/z ×0,5) — NUR die im Befehl nutzen. Die zuvor geschnittenen Teile hatten KEINEN Tunnel → beim Neuschnitt kommt er mit. (83 Punkte, 68 Tunnel/15 offen, 14 Rippen mit Lichtraum.)

## Kanten-Lineale: OBEN AUFKLEBEN statt Halb-Überblattung (2026-10-25)
- **Halb-Überblattung (Kerben in Rippen-Oberkanten) VERWORFEN.** Gründe: (1) Kerben konnten
  Rippen zerteilen (Tunnelnähe → Code behielt still nur das größere Bruchstück, z.B. Y4 −26 Vertices);
  (2) die Kerben landeten durch einen Bug **nie im SVG/G-Code** (nur im 3D-Tool + Vorschau =
  Phantom-Kerben) → „Tool zeigt was anderes als geschnitten"; (3) nachkerben = ~10 schon geschnittene
  Rippen neu schneiden.
- **Fix in `terrain_eggcrate.py`:** Rippen-Einkerb-Block (edge_notches auf ribdata) entfernt →
  Rippen behalten saubere Oberkante, **Schnitt == Tool == Vorschau**. K-Teile werden weiter
  geschnitten und **oben auf die Rippen-Oberkanten geklebt**.
- **Die bereits geschnittenen Rippen sind korrekt** — nichts neu schneiden. `_zusammenbau.html` +
  `_cut_layout.png` wurden passend neu erzeugt (nur Tool/Vorschau, keine Schnitt-Datei angefasst).

## Robustheit gegen Bruchstücke (2026-10-25)
`terrain_eggcrate.py` erzeugt jetzt keine abbrechenden Mini-Teile mehr:
- **Höhen-bewusste Fingerzinken-Naht:** Nähte nur wo die Rippe ≥ `--seam-min-h` (auto = 2×--finger)
  hoch ist → solide Zähne, kein Mini-Zahn im flachen Talauslauf.
- **Interlock-sichere Schlitz-Kappung:** gemeinsame Schlitz-Mittellinie wird so gekappt, dass immer
  ≥ `--min-web` Steg zur Oberkante bleibt (beide Rippen dieselbe Formel → Verzahnung stimmt).
- **Auto-Nudge:** Y-Rippe mit echtem Körper-Hals (Schlitz an Gelände-Klippe wie Hirschsprung-Felswand)
  wird um ±2–6 mm versetzt bis bruchfrei; X-Schlitze folgen automatisch (gleiches xpos).
- **Validierung am Ende:** meldet jede Rippe mit echtem Körper-Hals < `--min-web` (ignoriert verklebte
  Zinken-Nähte). Ziel: `✓ Alle Rippen robust`.
- **⚠ CAVEAT für DIESEN Satz:** Auto-Nudge/Naht-Logik **verschieben Positionen** → mit dem neuen Tool
  neu erzeugte Teile passen NICHT zu den schon geschnittenen. Der aktuelle Satz bleibt wie geschnitten;
  die eine Schwachstelle **ribY2** beim Entgittern mit Sekundenkleber stabilisieren. Neue Features
  greifen automatisch bei KÜNFTIGEN Modellen.
