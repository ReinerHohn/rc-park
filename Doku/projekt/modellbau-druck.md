# 🖨️ Modellbau & Druck  ← [PROJEKT.md](../../PROJEKT.md)
Kapitel: `Doku/modellbau/` · Methoden: `modelle/archiv/METHODIK_KOMPLETT.md`, `modelle/MASSSTAB.md`

## Gilt
- Merksatz: „Alles Flache lasern, alle Körper drucken, den Blickfang scannen/Resin."
- Generisches kaufen (Faller & Co.), nur Freiburg-Einzigartiges selbst drucken.
- Qualität vor Material: Detail nie für Verschnitt/Zeit opfern; Terrain-Laser mit smooth 0.
- Will der Nutzer lasern, den Laser-Lauf selbst starten (`grbl_send.py --yes`).

## Versucht
- 22.10. · Farbe per AMS „Scan → AMS → fertig farbig" → ✗ Irrtum · nur 2–8 Volltöne, langsam, Abfall; Hero über Vollfarb-Service, sonst bemalen
- · ganze Stadt selbst drucken → ↺ kaufen + nur Wahrzeichen drucken · ~90 % weniger Druckzeit
- · alles lasern bzw. alles drucken → ↺ Hybrid (flach lasern, Körper drucken, Blickfang scannen)
- · LAD-BW-Münsterscan kommerziell nutzen → ⚠ Lizenz CC BY-NC · Freigabe oder eigener Scan
- 06.10. · Drohnenscan-Detail per Höhenfeld-Solidify → ✗ rastert zu Blobs · Screened Poisson
- 25.10. · Kanten-Lineale per Halb-Überblattung (Kerben) → ✗ brachen Rippe Y4 · oben aufkleben
- 24.10. · clean-contour (Douglas-Peucker) für Terrain-Platten → ✗ zerzog flache Platten · Open3D + Grid-Clip [1c339f2]
- 18.10. · Terrain glätten (smooth 0.8) für dichteres Nesting → ✗ Qualität vor Material
- 18.10. · Band-Rippen (`--rib-depth`) → ↺ Rippen bis Boden · 6-mm-Bänder zu wabbelig [d30ebc7]
- 22.10. · Fingerzinken mit Einzelzahn → ⚠ Sollbruch · mehrere Finger je Stoß, nur bei hoher Rippe
- 14.10. · Mini-SMD-LED-Schlitze in der Petersdom-Kuppel → ↺ Ø3,3-Bohrungen für 3-mm-LED
- 11.10. · Gelände-Überhöhung 3,7× → ✗ zu spitz/fake · 1,5–2×, auf allen Kacheln gleich
- 08.10. · 0,8-Düse für Hohl-Gelände (4,5× schneller erwartet) → ⚠ nur ~1,6× und mehr Plastik
- 11.10. · 1,2-m-Hirschsprung true-scale → ⚠ Material ∝ Fläche² (~31 kg/700 €) · 60 cm Sweet Spot
- 28.10. · Feindetail als Mikro-Geometrie (31.560 Sprossenteile) → ✗ nicht watertight · Textur/Bemalung auf saubere Geometrie
- · S9-Laser über HP-Dock / Pack-Report vertraut → ⚠ Serial-Abbruch · USB direkt; echten G-Code-Bereich prüfen (442 statt 410 mm)

## Offen
- Stand Höllental-Gerüst: `modelle/hoellental_geruest_a3/STAND.md`
