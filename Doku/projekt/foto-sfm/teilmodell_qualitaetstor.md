# Qualitätstor für eingepasste Teilmodelle (27.11.2026)
← [grundbegriffe](grundbegriffe.md) · [foto-sfm](../foto-sfm.md) · Werkzeug `tools/teilmodell_ausrichten.py` (Funktion `einpassung_guete`, Nachtketten-Tor `--tor`) · Test `tools/test_teilmodell_qualitaetstor.py`

## Gilt
- Die Einpassung eines Teilmodells über die Kamerazentren gemeinsamer Bilder heißt nur dann `ausgerichtet`, wenn alle Bedingungen halten. Sonst steht in `ausrichtung.json` `UNSICHER: <Gründe mit Zahlen>`, dazu `guete` mit allen Kennzahlen.
- Das eingepasste Modell wird nur bei `ausgerichtet` nach `<n>_ausgerichtet/` geschrieben, sonst nach `<n>_unsicher/` (zum Ansehen). Ein alter `<n>_ausgerichtet/` aus früheren Läufen bleibt liegen und wird nicht gelöscht. Maßgeblich ist der Status in der JSON-Datei.
- Nachtkette: `handy_fusion_nachlauf.sh` (EIN/TM) und `handy_dicht_nachlauf.sh` (wenn SP ein `*_ausgerichtet`/`*_unsicher`-Teilmodell ist oder EIN gesetzt ist) rufen vor dem ersten Rechenjob `teilmodell_ausrichten.py --tor EIN --modell TM` auf. Bei rc ≠ 0 bricht das Skript mit `ABBRUCH` und dem Grund im Protokoll ab.
- Bei `UNSICHER` als Nächstes die Spur-Einpassung (`tools/teilmodell_spuren_einpassen.py`, Zweig lage-bruecke) mit ihren unabhängigen Gegenproben (DOM1, DGM-Kamerahöhe, Lot) rechnen lassen.

Die Bedingungen, alle Restmaße in Modellmetern:
- (a) **Rest relativ:** mittlerer Rest der Anker geteilt durch den RMS-Radius der Anker-Kamerazentren ≤ 0,025.
- (b) **Anker:** mindestens 8 Anker, Inlier-Anteil ≥ 0,5, die Anker liegen nicht auf einer Linie (zweite durch erste Hauptachse ≥ 0,1), Hebel ≤ 3. Der Hebel ist das p90 des Abstands der Teilmodell-Punkte vom Anker-Schwerpunkt geteilt durch den Anker-Radius. Wird er überschritten, lautet der Grund „Extrapolation“.
- (c) **Drehfehler:** Median über die Ankerbilder des Winkels zwischen der Hauptmodell-Drehung und der eingepassten Teilmodell-Drehung ≤ 0,6°.

## Herkunft der Schwellen (drei echte Einpassungen, Daten unter `tools/testdaten/teilmodell_einpassung_echt.npz`)
- **26.11., Teil 0, gut** (55 gemeinsame Bilder): Rest 0,23 m, relativ 0,016, Drehfehler 0,28°, Hebel 1,5, Linie 0,54. Laut grundbegriffe „passt“.
- **26.11., Teil 2, schlecht** (32 gemeinsam, 27 Anker): Rest 1,02 m, relativ 0,042, Drehfehler 1,38°, Hebel 2,1. Laut grundbegriffe „unbrauchbar“.
- **27.11., Teil 0, schlecht** (634 Bilder, 324 gemeinsam, 294 Anker): Rest 1,43 m, relativ 0,049, Drehfehler 1,62°, Hebel 1,4, Linie 0,60. Die Spur-Einpassung zeigte: Steg 1 m zu hoch (DOM1), Maßstab +1,7 %.
- `REST_REL_MAX` 0,025 ist das geometrische Mittel aus gut (0,016) und dem besten schlechten Fall (0,042), abgerundet. `DREH_MAX_GRAD` 0,6 ist ebenso das Mittel aus 0,28 und 1,38.
- ANNAHME, nicht abgeleitet: `HEBEL_MAX` 3. Es gibt keinen belegten Extrapolationsfall, die gemessenen Werte liegen bei 1,4–2,1. `MIN_ANKER` 8, weil die Sim3 7 Freiheitsgrade hat. `MIN_ANTEIL` 0,5, übernommen aus `tools/sim3_robust.py`. `LINIE_MIN` 0,1 (gemessen 0,47–0,77).
- 26.11. Teil 3 (7 gemeinsame Bilder, 5 Anker, Rest 0,11 m) galt damals als „passt“. Das Tor nennt ihn jetzt UNSICHER: nur 5 Anker, Hebel 6,9, Drehfehler 2,1°. Ob er wirklich falsch lag, ist nicht geprüft.

## Grenzen
- Das Tor prüft nur die innere Stimmigkeit gegen die PnP-Posen des Hauptmodells. Diese Posen sind dort selbst schwach, wo das Hauptnetz kaum Punkte hat. Am 27.11. hatte auch die gute Spur-Einpassung gegen dieselben Kamerazentren einen Median von 0,81 m (p90 8,7 m) und einen Drehfehler-Median von 1,9°. Eine Einpassung über Kamerazentren lässt sich dort also gar nicht belegen; das Tor sagt dann zu Recht UNSICHER. Ein `ausgerichtet` ersetzt keine unabhängige Gegenprobe (DOM1, GPS, LoD2-Maß).
- Die Schwellen stützen sich auf nur einen guten und zwei schlechte Fälle. Bei neuen echten Fällen die Zahlen hier nachtragen und die Grenzen nachprüfen.
