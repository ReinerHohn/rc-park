# Befund: Druckbarkeit + fotorealistische Genauigkeit (Segment für Segment)

Autonomer Durchgang über alle 39 Segmente. Zwei Achsen: **(1) druckbar?** **(2) foto-genau?**

## Kern-Erkenntnis (die alles bestimmt)
Das Modell ist auf dem BILDSCHIRM detailliert, aber viel Detail ist **sub-druckbare, FREISCHWEBENDE
Geometrie** (tausende winzige, nicht verschmolzene Teile). Das macht die STL unschön/unwatertight und
bei kleinem Maßstab unbruckbar. **Lösung (Repo-Methodik „zwei Regime / Farbe für Feindetail"):**
- **Druck-Geometrie** = sauberer, WATERTIGHT verschmolzener Körper: Wände, Dach, Bögen, Pfeiler, Rahmen,
  Pfosten/Kämpfer, Statuen-Körper, Gesims, Balkonplatte. Features ≥ ~0,8 mm im Druckmaßstab.
- **Feindetail** (Waben-Bleiruten, Rauten-Glasur, Dachschuppen-Muster, Farbe) = **Textur/Bemalung /
  Farbdruck-Decal**, NICHT gedruckte Geometrie. Daraus kommt die „Fotorealistik", nicht aus Mikro-Druck.

## Maßstabs-Analyse (0,4-Düse, druckbar ab ~0,8 mm Wandstärke)
| Feature | real mm | @1:160 | @1:100 | @1:50 |
|---|--:|--:|--:|--:|
| Waben-Bleiruten (sprossen) | 15 | 0,09 | 0,15 | **0,30 ✗** |
| Dachschuppen-Relief | 40 | 0,25 | 0,40 | 0,80 (grenz) |
| Baldachin-Spitzen | 44 | 0,28 | 0,44 | 0,88 |
| Baluster-Hals | 52 | 0,33 | 0,52 | 1,04 |
| Gold-Fensterpfosten/-rahmen | 55 | 0,34 | 0,55 | 1,10 |
| Helm-Goldrippen | 90 | 0,56 | 0,90 | 1,80 |
| Gauben-Rahmen | 100 | 0,62 | 1,00 | 2,00 |
| Statue / Pfeiler | 460/600 | ✓ | ✓ | ✓ |
→ **Empfehlung Druckmaßstab ≈ 1:50** (Gebäude ~37 × 33 cm): fast alles druckbar; nur die Waben-
Bleiruten bleiben Textur/Bemalung. Bei 1:160 (N, 14 cm) ist praktisch das GANZE Feindetail nur Farbe.

## Druckbarkeit je Segment (aus STL-Audit)
**KRITISCH (so nicht druckbar):**
- `sprossen` — **31 560 Einzelteile, NICHT watertight, ~0 mm**. Waben-Bleiruten als tausende winzige,
  nicht verschmolzene Stege. → raus aus der Druck-Geometrie → als Relief/Textur auf solider Scheibe.
- `helm` (504 Teile) + `helm_gruen/rot/hell` (128/120/112 Rauten) — hunderte freischwebende Rauten/Rippen.
  → Rauten als flaches Relief AUF den soliden Helmkegel verschmelzen (oder Glasur = Bemalung).
- `gitter` (224 Teile) — gedrechselte Baluster einzeln, oben/unten NICHT verbunden. → mit durchgehender
  Ober-/Untergurt-Leiste verbinden (ein Solid) + Hals ggf. verdicken.
- `baldachin` (52 Teile, dünn) — dünne Gold-Spitzen, freischwebend. → solider Baldachin-Körper (s. u.).

**NICHT watertight (prüfen/schließen):** sprossen, helm_gruen, erker, waende. `erker`/`waende` sind offene
Schalen zum Vereinigen → beim Export per Boolean-Union je Farbe schließen.

**OK / druckbar (ggf. @1:50):** fassade, dach, waende(union), boegen, piers, balkon, laube, nische,
cornice, first, krabben, giebel, gauben/-dach/-rahmen, statuen, wappen, konsole(n), rahmen, lisenen.

## Foto-Genauigkeit je Region
- **Statuen-Baldachine (`baldachin`)** — im Modell 3 dünne Gold-Spitzen; im Foto SOLIDER gotischer
  Baldachin (spitze Nischen-Überdachung über jeder Figur). **Falsch → neu modellieren.**
- **Dach-Schuppen-Muster** — liest diagonal; Foto = waagrechte Biberschwanz-Reihen. Kosmetik → Textur.
- **Gauben-Dächlein** — etwas flach/pyramidal; Foto = höhere Ziegelhütchen. Klein.
- **Seitenwand/Giebel** — recht kahl; Foto-Seite hat mehr Fenster/Gliederung. (Nebenseite, niedrige Prio.)
- **Statuen** — mit Krone; Foto = Ritter/Kaiserfiguren (teils Krone). Grob ok.
- **Gut nach letzten Fixes:** Fenster (Ogee, hoch+schlank), Balkon (dunkel, nur vor Fenstern),
  Arkade (4 Bögen + Archivolt), Erker (Glockenhelm unter Traufe, rotes Mauerstück über den Fenstern),
  Gauben-Raster (gleichmäßig).

## Plan (priorisiert)
1. **Druckbar-Export bauen** (`tools/druckbar_export.py`): je Farbgruppe Boolean-UNION → watertight;
   sub-druckbare Teile (sprossen) aus der Druck-Geometrie nehmen; Baluster mit Gurten verbinden; Rauten
   aufs Helm-Solid; Ausgabe eine druckbare STL (oder wenige Farb-STLs) + `druckbar_check` (watertight,
   min-Wandstärke je Maßstab, freischwebende Teile = 0). Detaillierte GLB bleibt für die Optik.
2. **Baldachin** solide neu (gotische Spitznische).
3. **Feindetail als Textur** (Waben, Dachschuppen, Rauten, Farbe) fürs „fotorealistisch".
4. Kleinkram: Gauben-Dächlein höher, Seitengliederung.
