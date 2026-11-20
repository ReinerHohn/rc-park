# Spezifikation S3b: "Wolke zuerst" - Buendelwolke direkt zum druckbaren Solid, Modell nur als Fueller (Nutzer 5.11. 19:45)

Befund (Register CM, BEWEIS_ANSATZ_2026-11-06.md): Auf den echten Objekten passt das Poisson-Netz der Fotowolke (A) in den Fassadenkanten besser als unser Modell (C) -
kosten_lr Kaufhaus A -0,030 / C -0,011, Martinstor A -0,019 / C -0,009. A ist aber kein Modell: 49 % Dachloecher, Ballon-Volumen 2306 statt 7859 cm3, Front teils fehlend.
Nutzer: "Buendelwolke ist das Beste, wir muessen nur solid draus machen." Grenzen (bewiesen): Wolke am Dach 1,4 m zu tief (Spec S3 0b, Quelle gesperrt), 56 % der Dachzellen ohne Punkte, keine Rueckseite, Durchblicke hinter Arkaden.

## Verfahren (`tools/wolke_solid.py`, alles aus vorhandenen Werkzeugen zusammengesetzt)
1. **Flaechen** = `fassaden.json` (LoD2-Waende) + Vorbauflaechen (`fassade_ortho --waende-stl`, Mindestgroesse aus Aufloesung, S4) des besten Modellstands (Kaufhaus: null6 s3_v9; Martinstor: Objekt-STL).
2. **Tiefenfeld je Flaeche** (u, z, Zelle 0,10 m): `restfeld_fassade.py`-Funktionen importieren: Daten-Tiefe = Quantil q 0,8 der Wolkenpunkte mit >= 3 Kameras (fused.ply.vis), Band [-4, +2] m; Modell-Tiefe per Strahl. Plausibilitaet: |Daten - Modell| <= 2,0 m, sonst Zelle "unplausibel" (nicht uebernehmen, zaehlen).
3. **Fuellen + Glaetten**: Zellen ohne Daten (oder unplausibel) = Modell-Tiefe; dann Total-Variation-Glaettung (Chambolle, `skimage.restoration.denoise_tv_chambolle` falls vorhanden, sonst eigene 50 Iterationen) NUR auf Datenzellen mit Gewicht nach Kamerazahl, Modellzellen fest; Uebergang Daten/Modell 0,3 m weich. Quantisierung auf Druckaufloesung: `duese_mm x massstab / 1000` (0,4 mm x 87 = 3,5 cm; Objektparameter, ANNAHME 0,4).
4. **Durchblicke**: Zellen, in denen Daten-Tiefe > Modell + 1,0 m UND `freiraum_fassaden` Strahlen durch das Modell meldet (>= 6 Kameras), werden zu Oeffnungen (Tiefe = Freiraumtiefe, Rechteck-Huelle je Zusammenhangskomponente >= 0,5 m breit) - kein Hoehenfeld, sondern Schnitt (vorhandene Klasse `oeffnung`/Arkadenhalle in fassade_auto nutzen, Elementdatei erzeugen).
5. **Dach**: NICHT aus der Wolke. Dachflaechen als Hoehenfeld aus DOM1-Zellmaxima UND Stadtmesh (getrennt; Standard DOM1, Stadtmesh als Pruefung; Widerspruch > 0,5 m = Beobachtung), quantisiert, auf den LoD2-Dachumriss beschnitten; Gauben/Aufbauten nur, wenn beide Quellen sie zeigen.
6. **Solid**: je Flaeche das Tiefenfeld als geschlossenen Koerper extrudieren (Flaeche nach innen bis Rumpfmitte, Deckel/Boden), Vereinigung mit dem Rumpf (manifold3d, `~/.venvs/rcpark`), Oeffnungen subtrahieren, Vereinigung mit dem Dachkoerper; Ergebnis 1 Koerper, wasserdicht (Pruefstand `modell`-Zeilen), Mindestbreite >= 0,85 x Duese (Strahltest 200 Stichproben), Splitter < 1e-3 m3 weg. Beleg je Koerper (`beleg(...)`: Quelle Wolke/DOM1/Stadtmesh/Modell, Zellenanteile).
7. **Ausgabe**: `modelle/<objekt>/stl/<objekt>_wolke_solid_1-87.stl` + `audit/wolke_solid/`: je Flaeche Bild (Daten | Modell | Ergebnis | Herkunftsmaske), Zahlen: Anteil Datenzellen, unplausibel, Oeffnungen, Mindestbreite, Volumen.

## Beweise (`tools/test_wolke_solid.py`, vorab festgelegt)
- **T1 synthetisch**: Wahrheit = Martinstor-Generator-Variante (wie beweis_ansatz_synth "stark"), synthetische Wolke nur von den Kameras sichtbar (5 cm Rauschen) + synthetisches DOM1; Start-"Modell" = Standardgenerator. Erwartung: Chamfer C' < C (Standard) und Anteil > 3,5 cm faellt; dort, wo keine Kamera hinsieht, bleibt C' = Modell (Differenz 0).
- **T2 Kaufhaus**: C' = wolke_solid auf null6 s3_v9. Vergleich mit `tools/beweis_ansatz.py`-Metriken gegen A, B, C auf den 6 zurueckgehaltenen Fotos (001,024,054,083,211,234) mit kosten_lr: Kriterium C' < A gepaart t <= -2 UND C' < C; Dach gegen DOM1 (Strahl, getroffene Zellen) C' <= B + 0,1 m; Zaehlzeile Arkade = 4; druckbar (1 Koerper, wasserdicht, Slicer rc 0, Mindestbreite ok).
  Leck schliessen: fuer diesen Test die Wolke neu fusionieren OHNE die 6 Fotos (`sfm_dicht.py --fotos ...` bzw. Fusion ohne diese Tiefenkarten; wenn das > 1 h kostet: Variante "Punkte, die nur von den 6 Fotos gesehen werden, entfernen" und im Bericht nennen).
- **T3 Martinstor**: dasselbe mit martinstor_lod2 dicht_nord; Nordseite; nicht schlechter als C in jeder Metrik; Pruefstand gruen.
- **T4 Gegenprobe Dachsperre**: C' mit Wolke am Dach (absichtlich) -> Dachfehler gegen DOM1 waechst; mit Sperre nicht. Belegt, dass die Sperre wirkt.
- Bilder: je Objekt Bildblatt A | C | C' aus derselben Kamera + Flaechenbilder, ANSEHEN, je 3 Saetze.
Faellt T2 (C' < A) durch: Ursache je Flaeche (wo bleibt gelb?), nicht nachjustieren, Bericht. Register-Abschnitt "CP - Wolke zuerst: Solid aus Buendelwolke".

## Regeln
GPU nur frei / job_start (Sperre); Datenplatte; keine Aenderung an foto_diff.py (S2), fassade_parsing/ortho/baukasten_gen (S4), qualitaetsstufen/elementbuch (S3) - eigene Datei(en); Lizenz: skimage BSD, manifold3d Apache (LIZENZ_WERKZEUGE.md pruefen); kein Commit; Sollwerte unveraendert.
