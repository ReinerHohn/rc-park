---
name: linien-features
description: Linienhafte Bauteile (Rippen, Baender, Leisten, Staebe, Gesimse) aus Fotos - NIE per Farbschwelle oder Wolke, sondern Mehrfoto-Sweep mit Stabilitaetskarten.
---
1. `tools/kanten_tiefe_sweep_flaeche.py --flaeche <STL> --band ...` (Tiefenband um die Flaeche).
2. `tools/kanten_features.py --farbe stabil --sweep <SWEEP.npz> --nur_ref [--maske]` (Luecken per Belegung/Spline, Rauschen faellt weg).
3. `tools/features_in_objekt.py` -> Skill `abnahme` + Render neben Foto ansehen.
4. Druck-Teilnetze: erst `druck.splitter_verwerfen` pruefen (Mini-Splitter), nicht Konsolen.
Beispiel/Lehren: `modelle/LOGBUCH_RIPPEN_2026-11-13.md`.
