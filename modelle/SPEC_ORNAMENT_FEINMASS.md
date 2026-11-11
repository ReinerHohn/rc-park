# SPEC Ornament-Feinmass (Nutzer 11.11. 17:5x: "wie machen wir sowas automatisiert? muss auch bei anderen Modellen gehen")

## Befund (bewiesen 11.11. 17:4x)
Die Foto-Metrik (`teil_fotoform.py`, Kanten nach 0,18-m-Glaettung) ist BLIND fuer Ornament: Erker-Konsole erker_polygon__1 mit/ohne
Netzrippen (b 0,06-0,12 m, vor 0,05-0,08 m) aendert den Foto-F1 nur 0,574 -> 0,570/0,574; die Overlays an der Konsole sind praktisch gleich.
Das schattierte Render aus der Fotokamera (`/media/oem/scan/rc-park_tmp/abend/teil_render.py`, Bild `render2_6164.jpg`) zeigt die Rippen dagegen
klar - und dass sie falsch verlaufen. Darum gewinnen Agenten bei Rippen, Sprossen, Masswerk, Schuppen nie am Tor, und dort ist das Modell am schwaechsten.

## Was (generisch, kein Objektname im Code)
1. `tools/teil_render_foto.py <objekt> <teil> --fotos a,b --teile_dir D --stl S [--vergleich D2:S2]`: schattiertes Teil-Render aus der
   kalibrierten Fotokamera neben dem Fotoausschnitt (Vorlage `teil_render.py` oben uebernehmen und haerten: Verzeichnung k1 wie foto_diff, Verdeckung
   durch das Gesamtmodell, GPU-Raster `render_kern`). Ausgabe JPG je Foto. Das ist das Pruefbild fuer Agenten und Pruefer.
2. **Feinmass** in `teil_fotoform.py` als Nebenzahl `f1_fein` (Standard an, Hauptzahl F1 unveraendert): im Bildbereich des Teils
   Fotokanten in VOLLER Aufloesung ohne 0,18-m-Glaettung (Canny/Strukturtensor, Schwelle adaptiv im ROI), Modellkanten aus dem Render
   (Tiefen- UND Normalenspruenge, damit Rippen/Sprossen auf einer Flaeche Kanten liefern), Toleranz in Pixeln aus der Kamera = 0,03 m.
   Bewertung Chamfer/F1 wie die Hauptzahl. Metrik-Etikett eigene Version, Cache getrennt.
3. Kreis (`bauteil_kreis.py`): NUR nach Beweis und mit Nutzer-Rueckmeldung: Formfund-Runden mit pruef_stichworte aus einer Ornamentliste
   (rippe, sprosse, masswerk, schuppe, ziegel, fiale, krabbe, zipfel) duerfen ueber `f1_fein` gewinnen (>= +0,02), wenn F1 hoechstens 0,005 faellt;
   Pruefer bekommt die Render-Bilder aus 1. Dieser Punkt 3 ist NICHT Teil des ersten Auftrags.

## Beweis (Pflicht)
- Synthetisch: Testflaeche mit aufgesetzten Rippen (bekannte Lage) in ein echtes Foto gerendert: f1_fein steigt mit richtiger Rippe, faellt bei
  um 0,15 m versetzter Rippe; Hauptzahl bleibt (fast) gleich.
- Echt: erker_polygon__1 Varianten basis / e_k16 / e_k06 / e_k25 (`/media/oem/scan/rc-park_tmp/abend/teile_*`, `stl_*.stl`) auf Fotos
  6162, 6164, 6261, 6145: f1_fein muss die Varianten UNTERSCHEIDEN (Spreizung > Rauschen aus 2 Wiederholungen); Render-Bilder ansehen und nennen,
  welche Variante dem Foto am naechsten kommt - stimmt das mit f1_fein ueberein?
- `tools/regression.py modelle/kaufhaus_grob3/objekt.json --pruefen` identisch; Hauptzahl F1 bitgleich (cmp JSON ohne die neue Nebenzahl).

## Nicht
Keine Generatoraenderung, keine Sollwerte, kein Kreis-/Regler-Code, nichts loeschen, GPU ueber job_start mit JOB_GPU_MB (vorher messen).
