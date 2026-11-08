# Foto -> Punktwolke: wie es funktioniert (Kurzfassung zum Nachlesen)

Bild: Artifact "Foto zur Punktwolke" (Link im Chat 8.11.). Diese Datei ist der Text dazu.

## Die Kette in 5 Schritten

1. **Merkmale finden und abgleichen** (SIFT-GPU, Exhaustive Matching). In jedem Foto werden markante Punkte gesucht
   (Ecken, Muster). Dann wird je Fotopaar geprueft, welche Punkte dasselbe Ding zeigen.
   458 Bilder = rund 105 000 Paare (10 Bloecke).
2. **Strahlen schneiden = Triangulation.** Jeder Punkt ist ein Strahl von der Kamera durch das Pixel. Wo sich die Strahlen
   aus mehreren Fotos treffen, liegt der 3D-Punkt.
3. **Buendelausgleich (Bundle Adjustment).** Kamerapositionen UND Punkte werden gemeinsam so verschoben, dass der
   Reprojektionsfehler minimal wird. Ergebnis: **Kameras + duenne Wolke (Sparse)**. Nur Merkmale, die in mehreren Fotos
   gefunden wurden. Das ist das "SfM" (Structure from Motion).
4. **Tiefenkarte je Foto** (PatchMatch-Stereo). Fuer jedes Pixel eine Entfernung. Kleine Bildfenster werden mit den
   Nachbarfotos verglichen, deshalb gehen auch glatte Flaechen ohne Merkmale. Je Foto zwei Karten (photometrisch +
   geometrisch konsistent): 103 Fotos = 206 Karten.
5. **Fusion.** Alle Tiefenkarten werden in einem Raum uebereinandergelegt. Ein Punkt bleibt nur, wenn mehrere Karten ihn
   bestaetigen. Ausreisser fliegen raus. Ergebnis: **dichte farbige Wolke** (`fused.ply`).

## Grenzen
- Glas, Spiegelungen, Dunkelheit: keine Merkmale/Tiefe -> Loecher (Fenster, Gewoelbe, Durchgaenge).
- Wolke sieht nur Oberflaechen, die fotografiert wurden. Form und Anzahl von Bauteilen kommen aus den Fotos (Regel 9d).
- Massstab/Lage kommen nicht aus den Fotos allein: Ausrichtung per ICP auf die Netzrahmen-Wolke (`iphone_ausrichten.py`).

## Unsere Werkzeuge und Stand 8.11.
| Schritt | Werkzeug | Stand |
|---|---|---|
| 1-3 iPhone | `tools/iphone_sfm.py` | fertig, 130/134 Bilder in 3 Teilmodellen (103/43/10) |
| Ausrichtung | `tools/iphone_ausrichten.py`, `tools/sfm_kameras_export.py` | Median 0,163 m, 60 % Inlier |
| 4-5 iPhone | `tools/iphone_dicht.py` | PatchMatch 86/206, Fusion folgt (`dicht0/fused.ply`) |
| Gemeinsam alle | `kaufhaus_alle/sfm` | 458 Bilder (iPhone 134, Android 301, Nutzer 23), Matching Block 6/10 |

Daten: `/media/oem/scan/rc-park_daten/kaufhaus_iphone/sfm/` und `.../kaufhaus_alle/`.
