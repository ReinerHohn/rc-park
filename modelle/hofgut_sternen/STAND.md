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

## Korrektur 2026-10-29 (LEHRE: Foto schlägt Notiz)
„7+6 Gauben" aus dieser STAND.md war FALSCH und wurde blind in den Generator übernommen → 13
kleine Schleppgauben = „völliger Schrott" (User). Am Foto g4 NACHGEZÄHLT: das riesige Krüppelwalm-
Dach ist GROSSTEILS ununterbrochen, mit nur ~3 GROSSEN Zwerchhäusern (Giebelgauben, holzverkleidet,
an der Traufe) + ~4 flachen Dachflächenfenstern (Velux). LEHRE (wie Kaufhaus F5/F9): geerbte
Mess-/STAND-Notizen NIE blind übernehmen — Stückzahlen/Formen am Foto neu zählen. Fix: big_dormer()
+ skylight() in hofgut_sternen.py. (Nur das GEBÄUDE bauen — keine Ravenna-Brücke/Landschaft, User.)

## Verfeinerung 2026-10-29 (parametrisch sauber, gegen g4)
- **Riesen-Arkade RAUS** (war schwarze Bogen-Tunnel = Hauptfehler „völliger Müll") → EG schlichte
  weiße Wand mit kleinen Fenstern + mittigem Haustür-Eingang (`eg_wall_windows`).
- **Dach = DAS prägende Element**: brauner Schindel-Krüppelwalm, als Solid mit Dachstärke (druckbar),
  weiter Überstand (1,15 m) über den Lauben; Farbe warm braun statt grau.
- **Blumen in Gruppen** (Kästen alle ~1,5 m) statt durchlaufendem rotem Streifen.
- **Zwerchhäuser** höher/grösser + 4 kleine Schleppgauben oben; **Fresko**-Panel mittig im 2.OG (g4).
- Offen: Zwerchhäuser von vorn klarer als Giebel durchbrechen lassen; Fensterläden; Krüppelwalm-Winkel
  exakt; Terrasse/Markise im EG. NUR Gebäude — keine Landschaft/Viadukt.

## FERTIG 2026-10-29 — alle Daten gemergt, jede Quelle an ihrer Stärke
- **Grundriss**: LOD2 (amtlich, 8-Teil → Hauptkörper verschmolzen); Fremdgebäude per Footprint-Gegencheck ausgeschlossen.
- **Dach-TOPOLOGIE**: DOP-Luftbild → EIN zusammenhängendes Dach (Guard `dach_dop_check` + test_8).
- **Dach-PLAN/Aufbauten**: DOP 20 cm (schärfer als Laser) → 2 Kaminpositionen (x 0,27/0,82).
- **Dach-FORM/Höhen**: Laser-nDOM → First 16,3 m, Dach-Unterkante 10,0 m, langer First (Krüppelwalm, inset 0,10).
- **Fassade**: amtliches Frontfoto (freigestellt+Maßstab) → 11 Achsen, 2 Lauben (weiße Baluster), 4 Gauben, Naturstein-EG, Fresko.
- **Farben**: zonenweise aus Foto via ML-Maske.
- **Validierung**: Overlay-Bewerter (perspektiv-genau, IoU), 8/8 harte Tests, Quellen-Gate grün.
- **Dateien**: hofgut_hybrid.glb (Ansicht/Farbe) · hofgut_3d.html (interaktiv) · hofgut_druckbar.stl (watertight, 52,8×24,2×19 m) · hofgut_ansichten.png.
