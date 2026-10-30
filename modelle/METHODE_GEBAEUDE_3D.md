# METHODE: 3D-Gebäudemodell aus allen Daten (generell, reproduzierbar)

Destillat aus dem Hofgut-Sternen-Projekt. Gilt für JEDES Gebäude. Kernprinzip:
**jede Quelle für ihre Stärke, Geometrie bleibt CLEAN parametrisch, jeder Schritt erzwungen + validiert.**

## 0. Config statt Hardcoding
Pro Gebäude `modelle/<name>/config.json`: Datenpfade (LOD2-GML, DOP-/DOM-/DGM-Kacheln, Foto-Dir),
UTM-Lage, bekannte Maße (First/Traufe aus LOD2), Element-Stückzahlen (aus Fotos gezählt). Alle Tools
lesen `--name` → config. Kein Pfad/Wert im Code.

## 1. Quellen mergen — ERZWUNGEN (nie eine vergessen)
`python3 tools/quellen_inventar.py --name <name>` → Gate über 16 kanonische Quellentypen
(LOD2/LOD1/DOP_RGB/DOP_CIR/DOM1/DGM1/nDOM/LAZ/ALKIS/Hist/Sentinel-2/-1/COP-DEM/OSM/Fotos/Street).
Exit≠0 solange eine offen ist; jede muss genutzt oder begründet n/a (`quellen_na.json`) sein.
→ Register `modelle/QUELLEN_REGISTER.md`. **Regel [[alle_oeffentlichen_daten_mergen]].**

## 2. Massing = LOD2-Grundriss (amtlich)
`tools/lod2_gebaeude.py` / Footprint-Extraktion → `footprint.json` (Teile-Ringe + Traufe/First).
**PFLICHT-Gegencheck** `tools/footprint_check.py --name <name>`: jeden Teil gegen DOP (Gebäude da?)
+ Laser-nDOM (Bauhöhe?) + Abstand prüfen → kein Fremdgebäude/Phantom reingerutscht. Niedrige/kleine
Teile → kleines Dach, Überstand GRÖSSENABHÄNGIG. **[[footprint_gegencheck]].**

## 3. Laser nDOM = Grob-Form/Proportion + Form-Grundwahrheit (NICHT Geometrie!)
`tools/ndom_dach.py` (nDOM = DOM1−DGM1): Firsthöhe-Quercheck gegen LOD2, Dachdominanz/Sweep, Gelände.
`tools/<name>_dom_mesh.py` baut daraus die Laser-FORM-Grundwahrheit (Höhenfeld-Solid) NUR zum
Validieren. **Nie das 1-m-Rohmesh als Modell-Geometrie** (blobbig, RANSAC-Spikes, Details zu klein).
**[[laser_plus_foto_merge]].**

## 4. Fotos = DETAILS, clean parametrisch (Kaufhaus-Methode)
Pro Element GEMESSEN, nicht geraten: `shape_extract` (Umrisse/Baluster), `fenster_struktur` (Pfosten/
Kämpfer via FFT), `foto_kanten_messen` (Bandhöhen in m), Vermesser-Ensemble (Stückzahlen). → JSON →
sauberer Generator. DOP → Gauben-/Kaminpositionen. Farben zonenweise aus Foto via ML-Maske
(`gebaeude_segment.py` → `farben.json`). Für harte Fakten: **Agenten-Flotte** (Fan-out-Recherche +
adversariale Verifikation) → `verified_spec.json` — fing viele Fehlannahmen (Krüppelwalm→Vollwalm,
Schindel→Flachziegel, 2→1 Laube, Ocker→Naturstein-EG). **[[foto_erkannte_stueckzahlen]].**

## 5. Bauen = CLEAN Parametrik, alle Quellen gemergt
LOD2-Grundriss-Wände + parametrisches Dach (Proportion/Sweep aus nDOM gefittet, Gauben aus DOP) +
Fassaden-Elemente aus Fotos + gemessene Farben. Spezial-Generator erbt Element-Bibliothek
([[bauwerk_generator_architektur]]).

## 6. Validieren — die ZIELGRÖSSE, nicht Farbe
- **3D-FORM** `tools/struktur_abgleich.py`: Dachanteil der Silhouette Modell vs Laser-Grundwahrheit
  (fing „flacher Deckel" 24/100). Farb-/Textur-Scores sind ERPRESSBAR → nie als Erfolgsmaß.
  **[[struktur_validator_statt_farbe]].**
- **Element-für-Element** Render↔Foto (element_compare + Juror-Ensemble), jeden Loop SELBST hinschauen.
  **[[selbst_hinschauen_harte_regel]] + [[score_ist_nicht_hinschauen]].**
- **Harte Tests** (`tests/test_*_hart.py`): Höhe=LOD2+nDOM, Grundriss≠Box, Farben gemessen≠geraten,
  keine Spikes, Struktur dominiert, Quellen-Gate grün. EHRLICH ROT lassen statt Fake-Pass; Metrik
  gegen die eigenen Augen prüfen (erste Struktur-Metrik gab 99/100 bei sichtbar falsch).

## 7. Mehrere Varianten → Validator wählt (vollautomatisch)
Bei jeder harten Formentscheidung (Dach-Sweep/Neigung, Proportionen, Gaubenzahl) NICHT raten:
mehrere Varianten parametrisch erzeugen (z.B. `ROOF_SWEEP` 0.3..0.7), jede mit dem Form-Validator
gegen die Grundwahrheit scoren, die beste nehmen. Pattern = Judge-Panel/Tournament. Demonstriert am
Dach: 5 Sweeps → Validator-Scores → bester automatisch.

**ABER (härteste Lehre): das Varianten-System ist nur so gut wie sein VALIDATOR.** Vor dem Vertrauen
den Validator gegen das FOTO verifizieren. Beispiel-Falle: der Laser-GT war nach unten verzerrt
(sauberer LOD2-Rand schneidet den tief ziehenden Dachüberstand ab → GT-Dachanteil 0,33 statt real
~0,45) → der Validator wählte ein ZU FLACHES Dach. Blind folgen = „Tool über Foto"-Fehler
([[score_ist_nicht_hinschauen]]). Erst Validator/Grundwahrheit robust machen (stabiler, höhen-
basierter Anker statt Silhouette; GT gegen Foto prüfen), DANN autonom wählen lassen.

## Reihenfolge (ein Befehl je Schritt)
1 `quellen_inventar --name X` → 2 footprint + `footprint_check --name X` → 3 `ndom_dach --name X` →
4 Foto-Messung + `gebaeude_segment` + ggf. Agenten-Spec → 5 Bau (config-getrieben) →
6 `struktur_abgleich` + `tests/test_*_hart.py`. Gate grün + Tests grün = „aus Daten vollständig".
