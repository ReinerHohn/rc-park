# Hofgut Sternen — Vermesser-Modell aus Fotos + LOD2

Reales Gebäude am Eingang der Ravennaschlucht (Höllsteig 76, Breitnau), am Fuß des
Ravennaviadukts. Lage 47,9167 N / 8,0732 E. Erstnennung als Schänke 1446.

## Methode (grob → fein, jeder Schritt belegt)

| Phase | Werkzeug | Ergebnis | Beleg |
|---|---|---|---|
| 0 Lokalisieren | WebSearch + LGL-Kachel 429/5306 | Gebäude in `LoD2_32_430_5307`, `gml:name="Hofgut Sternen"` | Adresse+Name im GML |
| 1 Gerüst | `tools/lod2_gebaeude.py` | Baukörper 47×43×17,6 m, Grund 713,5 m ü.NN | LOD2 amtlich |
| 2 Vermessen | LOD2 Dach-Unterkante + Fotos | Traufe 9 m, Dachanteil 46% | LOD2 46% ↔ Foto ~50% = **PASS** |
| 3 Detail-3D | `tools/hofgut_sternen.py` | Sockel+2 Balkone, Krüppelwalm, 7+6 Gauben, 3 Kamine | Fotos g1–g4 gezählt |
| 4 Bauplan | `tools/hofgut_bauplan.py` | bemaßte Ansicht+Schnitt+Grundriss | Maßherkunft markiert |

## Dateien
- `schritt1_lod2.html` / `schritt2_lod2_sauber.html` / `schritt3_detail.html` — 3D je Schritt
- `hofgut_detail.stl` (+ Teil-STL) — Detail-Modell
- `hofgut_lod2.stl` / `.json` — amtliches Massenmodell + Maße
- `hofgut_bauplan.png` — Vermesser-Bauplan mit Maßen
- `../../daten/hofgut_sternen/fotos/` — Google-Fotos (Vermesser-Input)

## Offen (Phase 5, nächster Beleg)
- Foto-Overlay (Modell halbtransparent perspektivisch über g4) als Perspektiv-Beleg
- Fresko-Textur + Arkadenbögen im Sockel (Foto→Textur)
- Krüppelwalm exakt (aktuell Vollwalm-Näherung)
- Platzierung ins DGM1-Gelände + neben Viadukt (`tools/bauwerk_szene.py`)
