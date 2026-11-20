---
name: fassaden
description: Fassaden, Fenster, Reliefs, Bruchstein, Fugen oder eine Wand ohne Foto (RC-Park). Wandbild = Bauplan. Vorher modelle/PIPELINE_FASSADEN.md gezielt lesen.
---
Kette: `tools/fassaden_kette.py` (Stufen `fassaden`, `fenster` der Gesamtkette). Einzeln:
1. Wandbild: `tools/fassade_fein.py` (1-cm-Raster) -> Tiefe `tools/tiefe_lokal.py` / `tools/relief_aus_fotos_mono.py` -> Gestalt `tools/form_aus_wandbild.py`. Feinausrichtung `tools/wand_feinausrichtung.py`.
2. Regelmaessige Teile scharf: `tools/bauteile.py`, Picks `tools/wand_ortho.py`, Masse `tools/foto_mass.py`.
3. Bruchstein `tools/relief_einsatz.py` -> Putz eben `tools/relief_putz.py` -> Loecher `tools/steine_generieren.py` (nie in Oeffnungen; generiert = ANNAHME). Glatte Quader `tools/relief_quader_eben.py`; Fugen bei Brei-Relief `tools/steine_aus_foto.py` (Bild `<x>_foto.jpg` ansehen).
4. Fenster = echte Loecher: am Generatorende `bauteile.aushoehlen` (WAND_MM 1,2).
5. Wand ohne Foto: `tools/seiten_luecken.py ... --download --holen`, sonst Kamera aus Modellpunkten + `tools/fassade_ein_foto.py`. Nie spiegeln/erfinden; keine Bauteile aus Schattenfotos.
6. Nutzerbild aus der 3D-Seite erst am STL nachrendern (`tools/modell_ansicht.py`). Danach Skill `abnahme`.
