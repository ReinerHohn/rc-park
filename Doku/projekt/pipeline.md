# 🏛️ 3D-Pipeline & Validierung  ← [PROJEKT.md](../../PROJEKT.md)
Methoden: `modelle/archiv/METHODE_WAHRZEICHEN_AUS_FOTOS.md` · `METHODE_3D_AUS_ALLEN_DATEN.md` · `METHODE_GEBAEUDEGENERATOR.md` · `PROTOKOLL_VALIDATOR.md`

## Gilt
- **Kein Hardcoding:** jedes Detail aus dem Foto erkennen → JSON → Generator liest; bei Fehlern den Detektor bauen, nicht den Wert ändern.
- **Alle öffentlichen Daten mergen:** LOD2 = Massing, Luftbild = Dach, Laser = Form, Foto = Detail — nichts raten, wenn eine Quelle existiert.
- **Erst die Realität zählen**, dann bauen; die Zählung des Nutzers schlägt den Detektor.
- **Selbst hinschauen:** Render neben Foto Element für Element; nach jeder Änderung `tools/aenderung_check.py`, sonst git-Revert; nie „verbessert" nur wegen Score.
- Footprint vor dem Bau gegen Luftbild + nDOM gegenchecken; Wahrzeichen halbautomatisch, Masse-Gebäude vollautomatisch aus LOD2.

## Versucht
**Validierung**
- 28.10. · programmatische Metriken (Kante/FFT/Blob) für Anzahl/Form → ✗ versagen · Anzahl per Vision-Juror-Ensemble; programmatisch nur Orientierungs-Gate
- 27.10. · Ensemble-Mehrheit als Wahrheit → ⚠ 2/3 wollten rotes Dach, Foto zeigt grün · Foto schlägt Mehrheit
- 29.10. · Validator v1 unkalibriert → ✗ bewertete gute Modelle schlechter als kaputte · an bekannt-guten kalibrieren
- 29.10. · Farb-/Textur-Validator für 3D-Form → ✗ erpressbar (Score 81 trotz flachem Dachdeckel) · Form gegen Laser-nDOM
- 28.10. · selfcheck (Build/Bounds/Watertight/Crops) → ✗ testete die Fehlerklassen nicht · `elementcheck.py` + Quercheck-Suite
- 28.10. · Noten-Juror allein → ⚠ übersieht fehlende Elemente · erst Inventar-Juror, dann Note
- 28.10. · Bogen-Sweep über ARC_BW → ⚠ falscher Knopf · identischer Score über den ganzen Sweep = Parameter wirkt nicht

**Fenster & Formen**
- 28.10. · Fenster stückweise je Symptom fixen (8 Runden Oszillation) → ✗ · erst komplette Foto-Sezierung + Spec
- 28.10. · freie Multiplikatoren auf gemessene Geometrie → ✗ Fenster degenerierten · parametrisch-gültig + Guard
- 29.10. · Oberkirch Auto-Achsen (regularisierte x_fracs) → ✗ revertiert · zurück auf `fassade_messen` [5b6979a]
- 29.10. · adaptive Schwelle im `fenster_zaehler` → ✗ lief in Nachbar/Café · globale Schwelle [4b1a079]
- 29.10. · Detektor-Output wegregeln (Merge/Diamant) → ✗ 14 → 11 Fenster · Detektor fixen, nicht Generator
- 29.10. · Spalten-Projektion / Blob-Detektoren → ↺ SegFormer-ML · versagt bei Treppengiebel, ML farb-robust
- 29.10. · Kornhaus: Symmetrie-Regel statt echter Positionen → ↺ ML-Positionen [c3a373a]

**Datenquellen & Geometrie**
- 28.10. · Massing aus Frontfoto (First 15,4 m) → ✗ LOD2 sagt 21,4 m · Frontfoto verkürzt steile Dächer
- 28.10. · LOD2-BBox-Tiefe als Dachtiefe → ⚠ ganze Parzelle, Dach „zu lang" · auf Fassadenbreite kappen
- 28.10. · LOD2-Gebäude per Koordinatenpunkt → ⚠ traf Nachbarn · per `gml:name` wählen
- 30.10. · SfM/DUSt3R aus Saison-Fotos (Hofgut) → ✗ zerfällt · 3D-Modell als Geometrie-Anker, Fotos einzeln registrieren
- 29.10. · Laser-1m-Rohmesh als Geometrie → ✗ Details zu klein, RANSAC-Spike 20,9 m · Laser nur Grobform/Validator
- 30.10. · Hofgut-Dach per geratenem Sweep/Blob → ↺ Laser-nDOM-First + Gerade-Skelett aus Luftbild [b78288d]
- 30.10. · Google-3D-Tiles-EU-403 per VPN/RenderDoc umgehen → ✗ bewusst nicht (ToS) · Mapillary/OpenSfM
- 25.10. · LGL-Kachel 425/5306 für Hirschsprung → ✗ 2 km daneben · erst lokalisieren, Karten-Gegencheck
- 22.10. · OSM-Trasse beim 50-%-Modell nicht mitskaliert → ⚠ Tunnel fällt still weg · „Trasse N Punkte" > 0 prüfen
- 26.10. · Wikipedia-Bogenstich 4,20 m (Ravenna) → ✗ Foto zeigt Halbkreis · Textdaten meinen evtl. altes Bauwerk
- 26.10. · Gewölbe geschlossen sweepen / Sketchfab-Teilscan klonen → ✗ massive Wand bzw. Matsch · Polygon mit Bogenlöchern
- 29.10. · Foto-Rektifizierung per 2-VP-Homographie (Ravenna) → ✗ scheitert an Wald/Panorama · assistiert über mehrere Views

**Ausgabe**
- 27.10. · Render per chromium-WebGL / matplotlib-Per-Face → ✗ tot bzw. hässlich · nur pyrender + EGL
- 26.10. · Voll-Detail-Mesh als HTML (367 MB) / KI-Bild→3D für Architektur → ✗ Anti-Pattern

## Offen
- Uncommittete Modell-Arbeit vom 30.10. auf `kaufhaus-freiburg` (Hofgut, Kaufhaus, Martinstor, Münster …) sichten und committen (Nutzer)
